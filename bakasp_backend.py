"""Functions implementing the bakasp internal logic"""

import os
import json
import time
from functools import lru_cache
from flask import redirect, render_template, Markup

import utils
import model_repr
from asp_model import ShowableModel
from asp import solve_encoding, compute_encoding


# Link between user choice range and the HTML template that the front must expose
RANGES_TO_TEMPLATES = {  # those who have the same name don't have to be specified, it will be mapped to 'range'
    (1, 1): 'single',
    (0, None): 'multiple',
    (None, None): 'multiple',
}
CHOICES_TO_TEMPLATES = {
    'multiple users': 'multiple',
}

def get_empty_state():
    return [{}, [], [], set()]


class ErrorBackend:
    def __init__(self, uid: str, admin_uid: str, _: None, errors: list):
        self.uid, self.admin_uid = uid, admin_uid
        self.errors = tuple(errors)

    def html_error_page(self):
        msg = 'Sorry, configuration problems prevent this website to behave normally. Logs are necessary for further debug.'
        return f"{msg}<br/><ul>\n" + ''.join(f'<li>{err}</li>\n' for err in self.errors) + '</ul>'

    @property
    def haserror(self) -> bool: return True


class Backend:
    @property
    def haserror(self) -> bool: return False

    def __init__(self, uid: str, admin_uid: str, cfg: dict, raw_cfg: dict):
        """Expect the configuration to be valid"""
        self.uid, self.admin_uid = uid, admin_uid
        self.template_folder = os.path.join('templates/', cfg['global options']['template'])
        self.users_who_changed_their_choices = set()
        self.stats = {}  # some stats about global state
        self.models = []  # list of all found models
        self.result_header, self.result_footer = '', ''  # header and footer of the result page
        self.history = []  # (datetime, userids -> choices, new_models, lost_models)
        self.previous_models_uid = set()  # uids of found models before last compilation
        self.cfg, self.raw_cfg = cfg, raw_cfg

        # initialize state
        self.filestate = os.path.join('states/', cfg['meta']['filesource'].replace('/', '--').replace(' ', '_') + '---' + self.uid)
        self.load_state()

        # initialize user choices  (userid -> choices)
        self.init_user_choices()

        # Get the renderer of models, headers and footers from the plugins system and accordingly to the configuration.
        self.model_repr_plugins = tuple(model_repr.gen_model_repr_plugins(cfg['output options']['model repr'], self.get_username_of, self.get_choicename_of))
        self.header_repr_plugins = tuple(model_repr.gen_model_repr_plugins(cfg['output options']['header repr'], self.get_username_of, self.get_choicename_of))
        self.footer_repr_plugins = tuple(model_repr.gen_model_repr_plugins(cfg['output options']['footer repr'], self.get_username_of, self.get_choicename_of))


    def init_user_choices(self):
        if self.cfg['users options']['type'] == 'restricted':
            users = self.cfg["users options"]["allowed"]
            self.user_choices = {u: self.cfg["choices options"]["default"] for u in users.values()}
        else:
            self.user_choices = {}

    def save_state(self):
        if self.cfg['meta']['save state']:
            with open(self.filestate, 'w') as fd:
                json.dump([self.user_choices, list(self.previous_models_uid), self.history], fd)


    @property
    def state(self):
        return self.user_choices, self.previous_models_uid, self.history, self.previous_models_uid

    @state.setter
    def state(self, state: [dict, list, list, set]):
        a, b, c, d = state
        a, b, c, d = dict(a), list(b), list(c), set(d)
        self.user_choices, self.previous_models_uid, self.history, self.previous_models_uid = a, b, c, d

    def load_state(self):
        if not self.cfg['meta']['save state']:
            loaded = get_empty_state()
        elif not os.path.exists(self.filestate):
            loaded = get_empty_state()
        else:
            try:
                with open(self.filestate) as fd:
                    loaded = json.load(fd)
            except Exception as err:
                print(err)
                print('Empty state loaded')
                loaded = get_empty_state()
        self.state = loaded


    # @lru_cache(maxsize=len(cfg["users options"]["allowed"]) if cfg["users options"]["type"] == 'restricted' else 1024)
    def get_username_of(self, targetid: str) -> str or None:
        users = self.cfg["users options"]["allowed"]
        for username, userid in users.items() if isinstance(users, dict) else zip(users, users):
            if str(userid) == str(targetid):
                return username
        return None

    # @lru_cache(maxsize=len(cfg["choices options"]["choices"]))
    def get_choicename_of(self, targetid: str) -> str or None:
        for name, uid in self.cfg["choices options"]["choices"].items():
            if str(uid) == str(targetid):
                return name
        return None


    def create_asp_model(self, idx: int, clyngor_model: frozenset) -> ShowableModel:
        return ShowableModel(idx, clyngor_model, (p.repr_model for p in self.model_repr_plugins), show_uid=self.cfg['output options']['show human-readable id'])


    def user_choice_repr_from_request_form(self, form) -> set:
        """form object -> user_choice dict value"""
        if form.__class__.__name__ == 'ImmutableMultiDict':
            return set(form.getlist('choice'))
        else:
            raise NotImplementedError(f"Form output of type {type(form)} is not handled. Value is: {repr(form)}")


    def compile_models(self, force_compilation: bool = False) -> float:
        "return runtime"
        starttime = time.time()
        self.users_who_changed_their_choices
        if not self.users_who_changed_their_choices and not force_compilation:
            return 0.
        self.previous_models_uid = {m.uid for m in self.models}  # remember previous uids
        self.models = []
        for idx, model in enumerate(sorted(list(solve_encoding(self.cfg, self.user_choices))), start=1):
            self.models.append(self.create_asp_model(idx, model))
        self.save_history(force_save=force_compilation)
        self.stats['compilation_runtime'] = time.time() - starttime
        self.render_page_elements()
        return self.stats['compilation_runtime']

    def render_page_elements(self):
        self.stats['models'] = list(self.models)
        self.stats['nb_models'] = len(self.models)
        self.stats['compilation_runtime_repr'] = utils.human_repr_of_runtime(self.stats['compilation_runtime'])
        self.stats['common_atoms'] = ShowableModel.intersection(self.models)
        self.result_header = Markup(''.join(p.repr_header(**self.stats) for p in self.header_repr_plugins))
        self.result_footer = Markup(''.join(p.repr_footer(**self.stats) for p in self.footer_repr_plugins))

    def save_history(self, force_save: bool = False):
        # NB: for this to work correctly, compilation must have been done just before
        if self.users_who_changed_their_choices or force_save:
            models_uid = set(m.uid for m in self.models)
            self.history.append((
                time.strftime(self.cfg['history options']['time format'], time.localtime()),
                sorted(list(self.users_who_changed_their_choices)) + (['autocompile'] if force_save else []),
                sorted(list(models_uid - self.previous_models_uid)),
                sorted(list(self.previous_models_uid - models_uid))
            ))
            self.users_who_changed_their_choices = set()


    def html_instance_page(self):
        return render_template(
            'instance-index.html',
            title=self.cfg["main page options"]["title"],
            description=self.cfg["main page options"]["description"],
            public_pages=self.cfg["global options"]["public pages"]
        )

    def html_user_list_page(self):
        users = self.cfg["users options"]["allowed"]
        if self.cfg["users options"]["type"] == 'restricted':
            elements = tuple(users.items() if isinstance(users, dict) else zip(users, users))
            return render_template("user.html", elements=elements, user_choice_text=self.cfg['users options']['description'])
        else:
            raise NotImplementedError("Sorry.")

    def html_user_choice_page(self, userid):
        username = self.get_username_of(userid) or "Unknown"
        choices = ((idx, cid, cval, cval in self.user_choices[userid])
                   for idx, (cid, cval) in enumerate(self.cfg['choices options']['choices'].items()))
        choicetype_repr = self.cfg['choices options']['type repr']
        choice_range = self.cfg['choices options']['type']
        is_range = choice_range != choicetype_repr
        if is_range and choice_range not in RANGES_TO_TEMPLATES:
            print(f"WARNING: {choice_range=} is not in {RANGES_TO_TEMPLATES=}")
        elif not is_range and choicetype_repr not in CHOICES_TO_TEMPLATES:
            print(f"WARNING: {choicetype_repr=} is not in {CHOICES_TO_TEMPLATES=}")
        if is_range:
            fname = f"user-choice-{RANGES_TO_TEMPLATES.get(choice_range, choice_range)}.html"
        else:
            fname = f"user-choice-{CHOICES_TO_TEMPLATES.get(choicetype_repr, choicetype_repr)}.html"
        if not os.path.exists(os.path.join(self.template_folder, fname)):
            fname = f"user-choice-not-implemented.html"
        print(f"{self.cfg['choices options']['type']=}")
        return render_template(
            fname, username=username, userid=userid,
            preference_choice_text=self.cfg['choices options']['description'],
            choicetype=utils.range_as_js(self.cfg['choices options']['type']) if is_range else None,
            choicetype_repr=choicetype_repr,
            choices=choices
        )

    def set_user_choice(self, userid, form):
        username = self.get_username_of(userid) or "Unknown"
        self.user_choices[userid] = list(self.user_choice_repr_from_request_form(form))  # keep list, because we need json serializable data
        self.users_who_changed_their_choices.add(username)
        return redirect('/thanks')

    def html_config(self, *, admin: str = None):
        if self.accepts('compilation', admin):
            return self.cfg
        else:
            return render_template('admin-access-required.html')
    def html_raw_config(self, *, admin: str = None):
        if self.accepts('compilation', admin):
            return self.raw_cfg
        else:
            return render_template('admin-access-required.html')

    def html_compilation(self, *, admin: str = None):
        if self.accepts('compilation', admin):
            runtime = self.compile_models(force_compilation=True)
            return f"done in {runtime}s"
        else:
            return render_template('admin-access-required.html')

    def html_history(self, *, admin: str = None):
        if self.accepts('history', admin):
            return render_template('history.html', history=reversed(self.history), no_history=not self.history)
        else:
            return render_template('admin-access-required.html')

    def html_overview(self, *, admin: str = None):
        if self.accepts('overview', admin):
            return repr(self.user_choices) + '<br/>' + repr(self.cfg["users options"]["allowed"]) + '<br/>' + repr(self.cfg["choices options"]["choices"]) + '<br/><br/>Encoding:\n<code>' + compute_encoding(self.cfg, self.user_choices) + '</code><br/>' + repr(self.history)
        else:
            return render_template('admin-access-required.html')

    def html_results(self, *, admin: str = None):
        if self.accepts('results', admin):
            if self.cfg["global options"]["compilation"] == 'direct access':
                self.compile_models()
            return render_template('results.html', models=self.models, header=self.result_header, footer=self.result_footer,
                                   message=self.cfg["output options"]["insatisfiability message"] if not self.models else "")
        else:
            return render_template('admin-access-required.html')

    def html_admin_access_required(self):
        return render_template('admin-access-required.html')

    def html_reset(self, *, admin: str = None):
        if self.accepts('reset', admin):
            self.init_user_choices()
            self.save_state()
            self.load_state()
            return 'done.'
        else:
            return render_template('admin-access-required.html')

    def html_thank_you_page(self):
        self.save_state()
        return render_template('thanks.html', username='dear user')

    def accepts(self, page: str, admin_code: str) -> bool:
        return page in self.cfg["global options"]["public pages"] or admin_code == self.admin_uid


    def link_to_flask_app(self, app, root: str = '/'):
        app.route(root)(self.html_instance_page)
        app.route(root+'thanks')(self.html_thank_you_page)

        app.route(root+'user')(self.html_user_list_page)

        @app.route(root+'user/<userid>', methods=['GET', 'POST'])
        def page_user_choice(userid):
            if request.method == 'POST':
                return self.set_user_choice(userid, request.form)
            else:
                return self.html_user_choice_page(userid)

        app.route(root+'configuration')(self.html_config)
        app.route(root+'configuration/raw')(self.html_raw_config)
        app.route(root+'compilation')(self.html_compilation)
        app.route(root+'history')(self.html_history)
        app.route(root+'overview')(self.html_overview)
        app.route(root+'results')(self.html_results)
        app.route(root+'reset')(self.html_reset)

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
        if cfg['users options']['type'] == 'restricted':
            users = cfg["users options"]["allowed"]
            self.user_choices = {u: cfg["choices options"]["default"] for u in users.values()}
        else:
            self.user_choices = {}

        # Get the renderer of models, headers and footers from the plugins system and accordingly to the configuration.
        self.model_repr_plugins = tuple(model_repr.gen_model_repr_plugins(cfg['output options']['model repr'], self.get_username_of, self.get_choicename_of))
        self.header_repr_plugins = tuple(model_repr.gen_model_repr_plugins(cfg['output options']['header repr'], self.get_username_of, self.get_choicename_of))
        self.footer_repr_plugins = tuple(model_repr.gen_model_repr_plugins(cfg['output options']['footer repr'], self.get_username_of, self.get_choicename_of))

    def save_state(self):
        if self.cfg['meta']['save state']:
            with open(self.filestate, 'w') as fd:
                json.dump([user_choices, list(previous_models_uid), history], fd)


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
        userid = self.users.get(username, username)
        users = cfg["users options"]["allowed"]
        if cfg["users options"]["type"] == 'restricted':
            elements = tuple(users.items() if isinstance(users, dict) else zip(users, users))
            return render_template("user.html", elements=elements, user_choice_text=self.cfg['users options']['description'])
        else:
            raise NotImplementedError("Sorry.")

    def html_user_choice_page(self, userid):
        username = get_username_of(userid) or "Unknown"
        choices = ((idx, cid, cval, cval in self.user_choices[userid])
                   for idx, (cid, cval) in enumerate(self.cfg['choices options']['choices'].items()))
        return render_template(
            'user-choice.html', username=username, userid=userid,
            preference_choice_text=self.cfg['choices options']['description'],
            choicetype=utils.range_as_js(cfg['choices options']['type']),
            choicetype_repr=self.cfg['choices options']['type repr'],
            choices=choices
        )

    def set_user_choice(self, userid, form):
        username = get_username_of(userid) or "Unknown"
        self.user_choices[userid] = list(self.user_choice_repr_from_request_form(form))  # keep list, because we need json serializable data
        self.users_who_changed_their_choices.add(username)
        return redirect('/thanks')

    def html_config(self):
        return self.cfg
    def html_raw_config(self):
        return self.raw_cfg

    def html_compilation(self):
        runtime = self.compile_models(force_compilation=True)
        return f"done in {runtime}s"

    def html_history(self):
        return render_template('history.html', history=reversed(self.history), no_history=not self.history)

    def html_overview(self):
        return repr(self.user_choices) + '<br/>' + repr(self.cfg["users options"]["allowed"]) + '<br/>' + repr(self.cfg["choices options"]["choices"]) + '<br/><br/>Encoding:\n<code>' + compute_encoding(self.cfg, self.user_choices) + '</code><br/>' + repr(self.history)

    def html_results(self):
        if self.cfg["global options"]["compilation"] == 'direct access':
            self.compile_models()
        return render_template('results.html', models=self.models, header=self.result_header, footer=self.result_footer,
                               message=self.cfg["output options"]["insatisfiability message"] if not self.models else "")

    def html_reset(self):
        self.init_user_choices()
        self.save_state()
        self.load_state()
        return 'done.'

    def html_thank_you_page(self):
        self.save_state()
        return render_template('thanks.html', username='dear user')


"""Functions implementing the bakasp internal logic"""

import os
import json
import time
from functools import lru_cache
from flask import redirect, render_template, Markup, request

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
    return [{}, set(), []]


class ErrorBackend:
    def __init__(self, uid: str, admin_uid: str, errors: list, raw_config: dict):
        self.uid, self.admin_uid = uid, admin_uid
        assert isinstance(raw_config, dict), repr(raw_config)
        self.cfg = self.raw_cfg = dict(raw_config)
        self.errors = tuple(errors)

    def html_error_page(self):
        msg = 'Sorry, configuration problems prevent this website to behave normally. Logs are necessary for further debug.'
        return f"{msg}<br/><ul>\n" + ''.join(f'<li>{err}</li>\n' for err in self.errors) + '</ul>'

    @property
    def haserror(self) -> bool: return True


class Backend:
    @property
    def haserror(self) -> bool: return False

    def __init__(self, uid: str, admin_uid: str, cfg: dict, raw_cfg: dict, *, rootpath: str = '/', render_template_func: callable = render_template):
        """Expect the configuration to be valid"""
        self.uid, self.admin_uid = (uid or ''), (admin_uid or '')
        self.root = rootpath.format(uid=self.uid)
        self.template_folder = os.path.join('templates/', cfg['global options']['template'])
        self.users_who_changed_their_choices = set()
        self.models = []  # list of all found models
        self.result_header, self.result_footer = '', ''  # header and footer of the result page
        self.history = []  # (datetime, userids -> choices, new_models, lost_models)
        self.previous_models_uid = set()  # uids of found models before last compilation
        self.cfg, self.raw_cfg = cfg, raw_cfg
        self.render_template = render_template_func

        # initialize state
        self.filestate = utils.filestate_from_uid_and_cfg(self.uid, self.cfg)
        self.load_state()

        # initialize user choices  (userid -> choices)
        self.init_user_choices()

        # Get the renderer of models, headers and footers from the plugins system and accordingly to the configuration.
        self.plugin_repr_plugins = tuple(model_repr.gen_model_repr_plugins(cfg['output options']['plugin repr'], self.get_username_of, self.get_choicename_of))
        self.model_repr_plugins = (
            *tuple(model_repr.gen_model_repr_plugins(cfg['output options']['model header repr'], self.get_username_of, self.get_choicename_of)),
            *tuple(model_repr.gen_model_repr_plugins(cfg['output options']['model repr'], self.get_username_of, self.get_choicename_of)),
            *self.plugin_repr_plugins,
            *tuple(model_repr.gen_model_repr_plugins(cfg['output options']['model footer repr'], self.get_username_of, self.get_choicename_of)),
        )
        self.header_repr_plugins = tuple(model_repr.gen_model_repr_plugins(cfg['output options']['header repr'], self.get_username_of, self.get_choicename_of)) + self.plugin_repr_plugins
        self.footer_repr_plugins = tuple(model_repr.gen_model_repr_plugins(cfg['output options']['footer repr'], self.get_username_of, self.get_choicename_of)) + self.plugin_repr_plugins


    def init_user_choices(self):
        if self.cfg['users options']['type'] == 'restricted':
            users = self.cfg["users options"]["allowed"]
            self.user_choices = {
                u: [
                    self.cfg['choices options'][choiceid]['default']
                    for choiceid in range(len(self.cfg['choices options']))
                ]
                for u in users.values()
            }
        else:
            self.user_choices = [{} for _ in range(len(self.cfg['choices options']))]

    def save_state(self):
        if self.cfg['meta']['save state']:
            with open(self.filestate, 'w') as fd:
                json.dump(self.state, fd)

    @property
    def state(self):
        return (self.user_choices, tuple(set(self.previous_models_uid)), self.history)

    @state.setter
    def state(self, state: [dict, set|list, list]):
        a, b, c = state
        a, b, c = dict(a), set(b), list(c)
        self.user_choices, self.previous_models_uid, self.history = a, b, c

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

    def get_choicename_of(self, targetid: str) -> str or None:
        for chop in self.cfg["choices options"]:
            for name, uid in chop["choices"].items():
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
        # self.users_who_changed_their_choices
        if not self.users_who_changed_their_choices and not force_compilation:
            return 0.
        self.previous_models_uid = {m.uid for m in self.models}  # remember previous uids
        self.models = []
        for idx, model in enumerate(sorted(list(solve_encoding(self.cfg, self.user_choices))), start=1):
            self.models.append(self.create_asp_model(idx, model))
        self.save_history(force_save=force_compilation)
        stats = {}
        stats['models'] = list(self.models)
        stats['nb_models'] = len(self.models)
        stats['common_atoms'] = ShowableModel.intersection(self.models)
        stats['compilation_runtime'] = time.time() - starttime
        stats['compilation_runtime_repr'] = utils.human_repr_of_runtime(stats['compilation_runtime'])
        self.result_header = Markup(''.join(p.repr_header(**stats) for p in self.header_repr_plugins))
        self.result_footer = Markup(''.join(p.repr_footer(**stats) for p in self.footer_repr_plugins))
        return stats['compilation_runtime']


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


    def html_instance_page(self, *, admin: str = None, remaining_instance_time: str = None):
        return self.render_template(
            'instance-index.html',
            title=self.cfg["main page options"]["title"],
            description=self.cfg["main page options"]["description"],
            public_pages=self.cfg["global options"]["public pages"],
            admin_code=('/admin/'+admin) if self.ok_admin(admin) else '',
            root=self.root,
            remaining_instance_time=remaining_instance_time,
        )

    def html_user_list_page(self):
        users = self.cfg["users options"]["allowed"]
        if self.cfg["users options"]["type"] == 'restricted':
            elements = tuple(users.items() if isinstance(users, dict) else zip(users, users))
            return self.render_template("user.html", elements=elements, user_choice_text=self.cfg['users options']['description'], root=self.root)
        else:
            raise NotImplementedError("Sorry. For now, users must be explicitely named.")

    def html_user_overview_page(self, userid):
        username = self.get_username_of(userid) or "Unknown"
        print(self.user_choices)
        print(self.user_choices[userid])
        return self.render_template(
            'user-overview.html', username=username, userid=userid,
            choices=[
                (choiceid, choices_dict['description'], self.human_readable_user_choice(userid, choiceid))
                for choiceid, choices_dict in enumerate(self.cfg['choices options'])
            ],
            root=self.root,
        )

    def human_readable_user_choice(self, userid: str, choiceid: int) -> str:
        choices = self.user_choices[userid][choiceid]
        if isinstance(choices, (list, tuple)):
            return ' or '.join(self.get_choicename_of(c) for c in choices)
        else:
            raise NotImplementedError(f"user choice for user {userid} and choice {choiceid} is {choices} of type {type(choices)}, which is not handled. List or tuple is expected.")

    def html_user_choice_page(self, userid, choiceid: int):
        choiceid = int(choiceid)
        if choiceid >= len(self.cfg['choices options']):
            print(f"WARNING access to choiceid {choiceid}, which doesn't exists (there is {len(self.cfg['choices options'])} choices). Redirecting to user overview.")
            return redirect(f'/user/{userid}')
        username = self.get_username_of(userid) or "Unknown"
        choices_dict = self.cfg['choices options'][choiceid]
        choicetype_repr = choices_dict['type repr']
        choice_range = choices_dict['type']
        is_range = choice_range != choicetype_repr
        # print(f'{choicetype_repr=}')
        # print(f'{choice_range=}')
        # print(f'{is_range=}')
        if is_range and choice_range not in RANGES_TO_TEMPLATES:
            fname = f"user-choice-range.html"
        elif not is_range and choicetype_repr not in CHOICES_TO_TEMPLATES:
            print(f"WARNING: {choicetype_repr=} is not in {CHOICES_TO_TEMPLATES=}")
            fname = f"user-choice-{CHOICES_TO_TEMPLATES.get(choicetype_repr, choicetype_repr)}.html"
        elif is_range:
            fname = f"user-choice-{RANGES_TO_TEMPLATES.get(choice_range, choice_range)}.html"
        else:
            fname = f"user-choice-{CHOICES_TO_TEMPLATES.get(choicetype_repr, choicetype_repr)}.html"
        if not os.path.exists(os.path.join(self.template_folder, fname)):
            fname = f"user-choice-not-implemented.html"
        print(f"{choices_dict['type']=}")
        return self.render_template(
            fname, username=username, userid=userid, choiceid=choiceid, nb_choices=len(self.cfg['choices options']),
            preference_choice_text=choices_dict['description'],
            choicetype=utils.range_as_js(choice_range) if is_range else None,
            choicetype_repr=choicetype_repr,
            choices=(
                (idx, cid, cval, cval in self.user_choices[userid][choiceid])
                for idx, (cid, cval) in enumerate(choices_dict['choices'].items())
            ),
            root=self.root,
        )

    def set_user_choice(self, userid, choiceid, form):
        choiceid = int(choiceid)
        username = self.get_username_of(userid) or "Unknown"
        self.user_choices[userid][choiceid] = list(self.user_choice_repr_from_request_form(form))  # keep list, because we need json serializable data
        self.users_who_changed_their_choices.add(username)
        if 1+int(choiceid) < len(self.cfg['choices options']):  # is there more choices to do ?
            return redirect(f'{self.root}user/{userid}/{choiceid+1}')  # +1 because index starts at 1 in URLs, and +1 to get to next choice
        else:  # its the last choice to make for this user
            return redirect(f'{self.root}thanks')

    def html_config(self, *, admin: str = None):
        if self.accepts('compilation', admin):
            return self.cfg
        else:
            return self.render_template('admin-access-required.html', root=self.root)
    def html_raw_config(self, *, admin: str = None):
        if self.accepts('compilation', admin):
            return self.raw_cfg
        else:
            return self.render_template('admin-access-required.html', root=self.root)

    def html_compilation(self, *, admin: str = None):
        if self.accepts('compilation', admin):
            runtime = self.compile_models(force_compilation=True)
            return f"done in {runtime}s"
        else:
            return self.render_template('admin-access-required.html', root=self.root)

    def html_history(self, *, admin: str = None):
        if self.accepts('history', admin):
            return self.render_template('history.html', history=reversed(self.history), no_history=not self.history, root=self.root)
        else:
            return self.render_template('admin-access-required.html', root=self.root)

    def html_overview(self, *, admin: str = None):
        if self.accepts('overview', admin):
            return repr(self.user_choices) + '<br/>' + repr(self.cfg["users options"]["allowed"]) + '<br/>' + repr([chop["choices"] for chop in self.cfg["choices options"]]) + '<br/><br/>Encoding:\n<code>' + compute_encoding(self.cfg, self.user_choices) + '</code><br/>' + repr(self.history)
        else:
            return self.render_template('admin-access-required.html', root=self.root)

    def html_results(self, *, admin: str = None):
        if self.accepts('results', admin):
            if self.cfg["global options"]["compilation"] == 'direct access':
                self.compile_models()
            return self.render_template('results.html', models=self.models, header=self.result_header, footer=self.result_footer,
                                   message=self.cfg["output options"]["insatisfiability message"] if not self.models else "",
                                   root=self.root)
        else:
            return self.render_template('admin-access-required.html', root=self.root)

    def html_admin_access_required(self):
        return self.render_template('admin-access-required.html', root=self.root)

    def html_reset(self, *, admin: str = None):
        if self.accepts('reset', admin):
            self.init_user_choices()
            self.save_state()
            self.load_state()
            return 'done.'
        else:
            return self.render_template('admin-access-required.html', root=self.root)

    def html_thank_you_page(self):
        self.save_state()
        return self.render_template('thanks.html', username='dear user', root=self.root)

    def accepts(self, page: str, admin_code: str) -> bool:
        return page in self.cfg['global options']['public pages'] or self.ok_admin(admin_code)

    def ok_admin(self, admin_code: str) -> bool:
        return admin_code and admin_code == self.admin_uid

    def post_user_choice_page(self, userid, choiceid):
        "show form to set user's choice for given choiceid"
        print('HTTVUW:', request.method)
        if request.method == 'POST':
            return self.set_user_choice(userid, choiceid, request.form)
        else:
            return self.html_user_choice_page(userid, choiceid)


    def link_to_flask_app(self, app, root: str = '/'):
        app.route(root)(self.html_instance_page)
        app.route(root+'/admin/<admin>')(self.html_instance_page)
        app.route(root+'thanks')(self.html_thank_you_page)

        app.route(root+'user')(self.html_user_list_page)
        app.route(root+'user/<userid>')(self.html_user_overview_page)
        app.route(root+'user/<userid>/<choiceid>', methods=['GET', 'POST'])(self.post_user_choice_page)


        app.route(root+'configuration')(self.html_config)
        app.route(root+'configuration/admin/<admin>')(self.html_config)
        app.route(root+'configuration/raw')(self.html_raw_config)
        app.route(root+'configuration/raw/admin/<admin>')(self.html_config)
        app.route(root+'compilation')(self.html_compilation)
        app.route(root+'compilation/admin/<admin>')(self.html_compilation)
        app.route(root+'history')(self.html_history)
        app.route(root+'history/admin/<admin>')(self.html_history)
        app.route(root+'overview')(self.html_overview)
        app.route(root+'overview/admin/<admin>')(self.html_overview)
        app.route(root+'results')(self.html_results)
        app.route(root+'results/admin/<admin>')(self.html_results)
        app.route(root+'reset')(self.html_reset)
        app.route(root+'reset/admin/<admin>')(self.html_reset)

        app.backend = self

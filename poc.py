"""
"""
import os
import sys
import json
import time
import itertools
from functools import lru_cache
from flask import Flask, request, redirect, url_for, render_template, Markup

import utils
import hashname
import model_repr
from config import parse_configuration_file



def create_website(cfg: dict, raw_cfg: dict) -> Flask:
    """Expect the configuration to be valid"""
    app = Flask(__name__, template_folder=os.path.join('templates/', cfg['global options']['template']))
    users_who_changed_their_choices = set()
    models = []
    history = []  # (datetime, userids -> choices, new_models, lost_models)
    user_choices = {}  # userid -> choices
    previous_models_uid = set()  # uids of found models before last compilation

    class ShowableModel:
        "Wrapper around model"
        def __init__(self, idx: int, clyngor_model: frozenset):
            self.model = model_repr.model_stable_repr(clyngor_model)
            self.uid = hashname.from_obj(self.model) if cfg['output options']['show human-readable id'] else None
            self.idx = idx
            repr_func = model_repr.from_name(cfg["output options"]["model repr"])
            # Markup is necessary for flask to render the html, instead of just writing it as-is
            self.html_repr = Markup(repr_func(self.idx, self.model, get_username_of, get_choicename_of, uid=self.uid))

        @staticmethod
        def minus(models_a, models_b) -> list:
            b_uids = frozenset(m.uid for m in models_b)
            for model in models_a:
                if model.uid not in b_uids:
                    yield model

    def init_user_choices():
        nonlocal user_choices
        if cfg['users options']['type'] == 'restricted':
            users = cfg["users options"]["allowed"]
            user_choices = {u: cfg["choices options"]["default"] for u in users.values()}
        else:
            user_choices = {}

    def save_state():
        if cfg['meta']['save state']:
            with open(filestate, 'w') as fd:
                json.dump([user_choices, list(previous_models_uid), history], fd)

    def load_state():
        nonlocal user_choices, previous_models_uid, history, users_who_changed_their_choices
        if cfg['meta']['save state']:
            try:
                with open(filestate) as fd:
                    loaded = json.load(fd)
            except Exception as err:
                print(err)
                print('Empty state loaded')
                loaded = [{}, [], []]
            if len(loaded) == 3:
                user_choices, previous_models_uid, history = loaded
            else:
                user_choices = loaded
            previous_models_uid = set(previous_models_uid)  # if loaded from json, is a list
        users_who_changed_their_choices = set(map(get_username_of, user_choices))


    @lru_cache(maxsize=len(cfg["users options"]["allowed"]) if cfg["users options"]["type"] == 'restricted' else 1024)
    def get_username_of(targetid: str) -> str or None:
        users = cfg["users options"]["allowed"]
        for username, userid in users.items() if isinstance(users, dict) else zip(users, users):
            if str(userid) == str(targetid):
                return username
        return None

    @lru_cache(maxsize=len(cfg["choices options"]["choices"]))
    def get_choicename_of(targetid: str) -> str or None:
        for name, uid in cfg["choices options"]["choices"].items():
            if str(uid) == str(targetid):
                return name
        return None


    init_user_choices()
    filestate = os.path.join('states/', cfg['meta']['filesource'].replace('/', '--').replace(' ', '_'))
    if os.path.exists(filestate):
        load_state()

    def user_choice_repr_from_request_form(form) -> set:
        """form object -> user_choice dict value"""
        if form.__class__.__name__ == 'ImmutableMultiDict':
            return set(form.getlist('choice'))
        else:
            raise NotImplementedError(f"Form output of type {type(form)} is not handled. Value is: {repr(form)}")


    def atoms_from_choices() -> str:
        atoms_templates = cfg["choices options"]["produced atoms"]
        for template in atoms_templates:
            for user, choices in user_choices.items():
                for choice in choices:
                    yield template.rstrip(".").format(user=user, choice=choice)+ '.'

    def atoms_from_data() -> [str]:
        # convert ranks to the values expected by ASP
        if cfg["choices options"]["ranks"]:
            ranks = [int(v) for v in cfg["choices options"]["ranks"].values() if not isinstance(v, bool)]
            absolute_ranks = ['yes' if v else 'no' for v in cfg["choices options"]["ranks"].values() if isinstance(v, bool)]

        for template in cfg["choices options"]["data atoms"]:
            valsets = {}
            if '{user}' in template:
                valsets['user'] = user_choices
            if '{choice}' in template:
                valsets['choice'] = cfg["choices options"]["choices"].values()
            if '{rank}' in template:
                valsets['rank'] = ranks
            if '{absolute_rank}' in template:
                valsets['absolute_rank'] = absolute_ranks
            if '{any_rank}' in template:
                valsets['any rank'] = ranks + absolute_ranks
            for values in itertools.product(*valsets.values()):
                yield template.rstrip(".").format(**dict(zip(valsets, values))) + '.'

    def atoms_from_shows() -> [str]:
        shows = cfg["global options"]["shows"]
        if shows:
            yield '#show.\n'
        for show in shows:
            yield f'#show {show.rstrip(".")}.'

    def compute_encoding() -> str:
        return cfg["global options"]["base encoding"] + ''.join(atoms_from_choices()) + ''.join(atoms_from_shows()) + ''.join(set(atoms_from_data()))

    def solve_encoding():
        encoding = compute_encoding()
        return utils.call_ASP_solver(
            encoding,
            n=cfg["output options"]["max models"],
            sampling=cfg["output options"]["model selection"] == 'sampling',
            cli_options=cfg['solver options']['cli'],
            constants=cfg['solver options']['constants']
        )

    def compile_models(force_compilation: bool = False) -> float:
        "return runtime"
        starttime = time.time()
        nonlocal users_who_changed_their_choices
        if not users_who_changed_their_choices and not force_compilation:
            return 0.
        nonlocal models, previous_models_uid
        previous_models_uid = {m.uid for m in models}  # remember previous uids
        models = []
        for idx, model in enumerate(solve_encoding(), start=1):
            models.append(ShowableModel(idx, model))
        save_history(force_save=force_compilation)
        return time.time() - starttime

    def save_history(force_save: bool = False):
        # NB: for this to work correctly, compilation must have been done just before
        nonlocal users_who_changed_their_choices
        if users_who_changed_their_choices or force_save:
            models_uid = set(m.uid for m in models)
            history.append((
                time.strftime(cfg['history options']['time format'], time.localtime()),
                sorted(list(users_who_changed_their_choices)) + (['autocompile'] if force_save else []),
                sorted(list(models_uid - previous_models_uid)),
                sorted(list(previous_models_uid - models_uid))
            ))
            users_who_changed_their_choices = set()

    @app.route('/')
    def main_page():
        return render_template('index.html', title=cfg["main page options"]["title"], description=cfg["main page options"]["description"], public_pages=cfg["global options"]["public pages"])

    @app.route('/user', methods=['GET', 'POST'])
    def user_page():
        elements = {}
        error = ""
        users = cfg["users options"]["allowed"]
        if request.method == 'POST':
            username = request.form['username']
            userid = users.get(username, username)
            if cfg["users options"]["type"] == 'restricted':
                if username in users:
                    return redirect(f'/user/{userid}')
                else:  # invalid choice
                    return render_template("user.html", elements=elements, message=error)
            else:
                raise NotImplementedError("Sorry.")
        if cfg["users options"]["type"] == 'restricted':
            elements = tuple(users.items() if isinstance(users, dict) else zip(users, users))
            return render_template("user.html", elements=elements, message=error, user_choice_text=cfg['users options']['description'])
        else:
            raise NotImplementedError("Sorry.")
        return header + form + footer

    @app.route('/user/<userid>', methods=['GET', 'POST'])
    def choice_page(userid):
        username = get_username_of(userid) or "Unknown"
        if request.method == 'POST':
            user_choices[userid] = list(user_choice_repr_from_request_form(request.form))  # keep list, because we need json serializable data
            users_who_changed_their_choices.add(username)
            return redirect(url_for('thank_you_page'))
        choices = ((cid, cval, cval in user_choices[userid]) for cid, cval in cfg['choices options']['choices'].items())
        return render_template('user-choice.html', username=username, userid=userid, preference_choice_text=cfg['choices options']['description'], choicetype=cfg['choices options']['type'], choices=choices)

    if 'configuration' in cfg["global options"]["public pages"]:
        @app.route('/configuration')
        def config_page():
            return cfg
        @app.route('/configuration/raw')
        def raw_config_page():
            return raw_cfg

    if 'compilation' in cfg["global options"]["public pages"]:
        @app.route('/compilation')
        def compilation_page():
            runtime = compile_models(force_compilation=True)
            return f"done in {runtime}s"

    if 'history' in cfg["global options"]["public pages"]:
        @app.route('/history')
        def history_page():
            return render_template('history.html', history=reversed(history), no_history=not history)

    if 'overview' in cfg["global options"]["public pages"]:
        @app.route('/overview')
        def overview_page():
            return repr(user_choices) + '<br/>' + repr(cfg["users options"]["allowed"]) + '<br/>' + repr(cfg["choices options"]["choices"]) + '<br/><br/>Encoding:\n<code>' + compute_encoding() + '</code><br/>' + repr(history)

    if 'results' in cfg["global options"]["public pages"]:
        @app.route('/results')
        def results_page():
            if cfg["global options"]["compilation"] == 'direct access':
                compile_models()
            return render_template('results.html', models=models,
                                   message=cfg["output options"]["insatisfiability message"] if not models else "")

    if 'reset' in cfg["global options"]["public pages"] and cfg['meta']['save state']:
        @app.route('/reset')
        def reset_page():
            init_user_choices()
            save_state()
            load_state()
            return 'done.'


    @app.route('/thanks')
    def thank_you_page():
        save_state()
        return render_template('thanks.html', username='dear user')


    if not models:
        compile_models(force_compilation=True)

    return app


def create_app(jsonfile: str) -> Flask or None:
    cfg, raw_cfg = parse_configuration_file(jsonfile)
    if cfg:
        return create_website(cfg, raw_cfg)
    else:
        return utils.create_errorlist_app(errors=raw_cfg)


if __name__ == "__main__":
    if app := create_app(sys.argv[1]):
        app.run(port=8080, debug=True)

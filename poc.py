"""
"""
import os
import sys
import time
import clyngor
from functools import lru_cache
from flask import Flask, request, redirect, url_for, render_template, Markup

import model_repr
from config import parse_configuration_file


def call_ASP_solver(encoding: str, n: int, sampling: bool) -> [frozenset]:
    "Call to the ASP solver with given encoding and n/sampling config values"
    if sampling:
        models = list(clyngor.solve(inline=encoding))
        if len(models) > n:
            models = random.sample(models, n)
        yield from models
    else:
        models = clyngor.solve(inline=encoding, nb_model=int(n))
        yield from models


def create_website(cfg: dict, raw_cfg: dict) -> Flask:
    """Expect the configuration to be valid"""
    app = Flask(__name__, template_folder=os.path.join('templates/', cfg['global options']['template']))
    a_user_changed_its_choices = True
    models = []

    if cfg['users options']['type'] == 'restricted':
        users = cfg["users options"]["allowed"]
        user_choices = {u: cfg["choices options"]["default"] for u in users.values()}
    else:
        user_choices = {}  # userid -> choices


    @lru_cache(maxsize=len(cfg["users options"]["allowed"]) if cfg["users options"]["type"] == 'restricted' else 1024)
    def get_username_of(targetid: str) -> str or None:
        users = cfg["users options"]["allowed"]
        for username, userid in users.items() if isinstance(users, dict) else zip(users, users):
            if userid == targetid:
                return username
        return None

    @lru_cache(maxsize=len(cfg["choices options"]["choices"]))
    def get_choicename_of(targetid: str) -> str or None:
        for name, uid in cfg["choices options"]["choices"].items():
            if uid == targetid:
                return name
        return None

    def user_choice_repr_from_request_form(form) -> set:
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
        atoms_templates = cfg["choices options"]["data atoms"]
        for template in atoms_templates:
            for user in user_choices:
                for choiceid in cfg["choices options"]["choices"].values():
                    yield template.rstrip(".").format(user=user, choice=choiceid)+ '.'

    def atoms_from_shows() -> [str]:
        shows = cfg["global options"]["shows"]
        if shows:
            yield '#show.\n'
        for show in shows:
            yield f'#show {show.rstrip(".")}.'

    def compile_models():
        nonlocal a_user_changed_its_choices
        if not a_user_changed_its_choices:
            return
        a_user_changed_its_choices = False
        nonlocal models
        encoding = cfg["global options"]["base encoding"] + ''.join(atoms_from_choices()) + ''.join(atoms_from_shows()) + ''.join(set(atoms_from_data()))
        model_repr_func = model_repr.from_name(cfg["output options"]["model repr"])
        models = []
        found_models = call_ASP_solver(encoding, n=cfg["output options"]["max models"], sampling=cfg["output options"]["model selection"] == 'sampling')
        for idx, model in enumerate(found_models, start=1):
            html_repr = model_repr_func(idx, model, get_username_of, get_choicename_of)
            models.append(Markup(html_repr))  # Markup is necessary for flask to render the html, instead of just writing it as-is

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
            return render_template("user.html", elements=elements, message=error)
        else:
            raise NotImplementedError("Sorry.")
        return header + form + footer

    @app.route('/user/<userid>', methods=['GET', 'POST'])
    def choice_page(userid):
        username = get_username_of(userid) or "Unknown"
        if request.method == 'POST':
            user_choices[userid] = user_choice_repr_from_request_form(request.form)
            a_user_changed_its_choices = True
            return redirect(url_for('thank_you_page'))
        return render_template('user-choice.html', username=username, userid=userid, preference_choice_text='Please select your preference(s)', choicetype=cfg['choices options']['type'], choices=cfg['choices options']['choices'])

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
            runtime = time.time()
            compile_models()
            runtime = time.time() - runtime
            return f"done in {runtime}s"

    if 'overview' in cfg["global options"]["public pages"]:
        @app.route('/overview')
        def overview_page():
            return repr(user_choices)

    if 'results' in cfg["global options"]["public pages"]:
        @app.route('/results')
        def results_page():
            if cfg["global options"]["compilation"] == 'direct access':
                compile_models()
            return render_template('results.html', models=models,
                                   message=cfg["output options"]["insatisfiability message"] if not models else "")

    @app.route('/thanks')
    def thank_you_page():
        return render_template('thanks.html', username='dear user')

    return app




if __name__ == "__main__":
    cfg, raw_cfg = parse_configuration_file(sys.argv[1])
    if cfg:
        ws = create_website(cfg, raw_cfg)
        ws.run(port=8080, debug=True)
    else:
        print("Abort because of malformed configuration")

"""Bakasp «As A Service»: like framapad.org

"""
import json
import uuid
import time
import utils
import functools
from collections import namedtuple
from flask import Flask, render_template, redirect, request, url_for

import config as config_module
import bakasp_backend
from bakasp_backend import Backend

InstanceControl = namedtuple('InstanceControl', 'backend, datetimelimit, period_label, haserror')
SECONDS_PER_DAY = 3600 * 24
TIMES = {
    'daily': 1*SECONDS_PER_DAY,
    'weekly': 7*SECONDS_PER_DAY,
    'monthly': 30*SECONDS_PER_DAY,
}
AVAILABLE_IMPLEMENTATIONS = {
    'One-to-One Association': 'data/asp/one-to-one-assoc.lp',
    'Team Maker': 'data/asp/making-teams.lp',
}


def create_from_config(title: str, input_config: dict, period: str, uids: set) -> (str, InstanceControl, str):
    """Create the backend, return its uid, its instance, the InstanceControl instance, and the page to which the user must be redirected"""
    config, raw_config = validate_config(input_config)
    uid = None
    while uid is None or uid in uids:
        uid, admin_uid = str(uuid.uuid4()), str(uuid.uuid4())

    if config is None:
        uid = admin_uid
        prefix = target = f'/b/{uid}'
        state = raw_config  # list of errors
        backend = bakasp_backend.ErrorBackend(uid, admin_uid, errors=raw_config, raw_config=input_config)
        ttl = 3600  # one hour is plenty time to debug
        period = 'errorly'
    else:
        prefix, target = f'/b/{uid}', f'/b/{uid}/{admin_uid}'
        state = bakasp.get_empty_state()  # empty state
        backend = Backend(uid, admin_uid, config, raw_config)
        ttl = TIMES[period]
    ic = InstanceControl(backend, time.time() + ttl, period, config is None)
    return uid, ic, target


def create_from_form(title: str, period: str, uids: set, asp_file: str, userline: str) -> (str, InstanceControl, str):
    config = {
        'global options': {
            'base encoding file': asp_file,
        },
        'users options': {
            'allowed': {u.title() for u in map(str.strip, userline.split(',')) if u}
        },
    }
    return create_from_config(title, config, period, uids)


def validate_config(config_text: str) -> (dict or None, list[str]):
    try:
        config = json.loads(config_text)
    except json.JSONDecodeError as err:
        return None, [str(err)]
    config, raw_config = parse_configuration(config, filesource='browser', verify=True)
    if config is None:
        return None, raw_config
    # everything looks ok
    return config_module.parse_default_configuration(config)


def create_app():
    bakasp_instances = {}  # uuid -> InstanceControl
    app = Flask(__name__, template_folder='templates/iamDziner/')

    @app.route('/create')
    def creation_of_new_instance():
        return render_template('creation-form.html', title='Form creation', description='Create a new instance from', methods=(('/create/byconfig', 'a raw configuration description in JSON'), ('/create/byform', 'create from a high level form preventing you to make mistakes')))

    @app.route('/create/byconfig', methods=['GET', 'POST'])
    def creation_of_new_instance_by_config():
        if request.method == 'POST':
            uid, control, target = create_from_config(
                request.form['Title'], request.form['Config'], request.form['period'], uids=bakasp_instances
            )
            assert uid not in bakasp_instances
            bakasp_instances[uid] = control
            return redirect(target)
        else:
            return render_template('creation-form-by-config.html', title='Form creation', description='', periods=((t, idx==0) for idx, t in enumerate(TIMES)))

    @app.route('/create/byform', methods=['GET', 'POST'])
    def creation_of_new_instance_by_form():
        if request.method == 'POST':
            uid, control, target = create_from_form(
                request.form['Title'], request.form['period'], bakasp_instances, AVAILABLE_IMPLEMENTATIONS[request.form['implementations']], request.form['userline'],
            )
            assert uid not in bakasp_instances
            bakasp_instances[uid] = control
            return redirect(target)
        else:
            return render_template('creation-form-by-form.html', title='Form creation', description='', periods=((t, idx==0) for idx, t in enumerate(TIMES)), implementations=((t, idx==0) for idx, t in enumerate(AVAILABLE_IMPLEMENTATIONS)))


    @app.route('/')
    def index():
        return render_template('index.html', title='Bakasp', description='Welcome !', public_pages=['create_instance'])

    @app.route('/clear')
    def index():
        nb_cleared = 0
        for uid, ctrl in tuple(bakasp_instances):
            ctrl = bakasp_instances[uid]
            if ctrl.datetimelimit > time.time():  # time is up ! Instance can be deleted
                del bakasp_instances[uid]
                nb_cleared += 1
        return '{nb_cleared} instances cleared.'

    @app.route('/stats')
    def index():
        stats = {
            'nb_instances': len(bakasp_instances),
            **Counter('nb_instances_'+c.period_label for c in bakasp_instances.values())
            'nb_error_instances': sum(1 for c in bakasp_instances if c.haserror)
        }

        return render_template('aas-stats.html', **stats)

    def path_for(page: str, admin=False) -> str:
        page = page.rstrip('/')
        if admin:
            return f"/b/<iuid>/{page or ''}admin/<admin_code>"
        return f"/b/<iuid>/{page}"

    def admin_path_for(page: str) -> str:
        return path_for(page, admin=True)

    def func_for(func: callable) -> callable:
        "Return the function that app can use as a page generator for a route"
        @functools.wraps(func)
        def wrapper(iuid: str, *, admin_code: str = None):
            instance_control = bakasp_instances.get(iuid)
            if instance_control:
                return func(instance_control.backend, admin=admin_code)
            else:  # given instance uid is not an existing one
                return redirect(url_for('index'))
        return wrapper

    UNRESTRICTED_PAGES = {
        'thanks': Backend.html_thank_you_page,
        'user/<userid>': Backend.html_user_choice_page,
        'user': Backend.html_user_list_page,
    }
    PAGES = {
        '': Backend.html_instance_page,
        'configuration': Backend.html_config,
        'configuration/raw': Backend.html_raw_config,
        'reset': Backend.html_reset,
        'results': Backend.html_results,
        'compilation': Backend.html_compilation,
        'history': Backend.html_history,
        'overview': Backend.html_overview,
    }
    for path, func in PAGES.items():
        rpath, apath = path_for(path), admin_path_for(path)
        func = func_for(func)
        print(f"\tPaths {rpath} and {apath} redirect to {func.__name__}")
        app.route(rpath)(func)
        app.route(apath)(func)
    for path, func in UNRESTRICTED_PAGES.items():
        path = path_for(path)
        func = func_for(func)
        app.route(path)(func)
        print(f"\tPath {path} redirects to {func.__name__}")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(port=8080, debug=True)

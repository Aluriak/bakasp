"""Bakasp «As A Service»: like framapad.org

usage:

    python aas.py <path to config file>

"""
import os
import sys
import json
import uuid
import time
import utils
import inspect
import functools
from collections import namedtuple, Counter
from flask import Flask, render_template, redirect, request, url_for

import config as config_module
import hashname
import aas_config as aasconfig_module
from aas_config import TIMES, AVAILABLE_CHOICE_TYPES, AVAILABLE_IMPLEMENTATIONS
import bakasp_backend
from bakasp_backend import Backend


InstanceControl = namedtuple('InstanceControl', 'backend, datetimelimit, period_label, haserror')


def gen_uid(cfg: dict, admin_password: bool = False) -> callable:
    mtd = cfg['admin options']['password format'] if admin_password else cfg['server options']['uid format']
    if mtd == 'short':
        return str(uuid.uuid4())[:8]
    elif mtd == 'long':
        return str(uuid.uuid4())
    elif mtd == 'memorable':
        return hashname.get_random_hash().replace(' ', '-').replace("'", '').lower()
    else:
        raise NotImplementedError(f"UID generation method {uid_gen_method} is not valid.")


def create_from_config(aas_config: dict, input_config: dict, period: str, uids: set) -> (str, InstanceControl, str):
    """Create the backend, return its uid, its instance, the InstanceControl instance, and the page to which the user must be redirected"""
    config, raw_config = validate_config(input_config)
    uid = None
    while uid is None or uid in uids:
        uid, admin_uid = gen_uid(aas_config), gen_uid(aas_config, admin_password=True)

    if config is None:
        uid = admin_uid
        prefix = target = f'/b/{uid}'
        backend = bakasp_backend.ErrorBackend(uid, admin_uid, errors=raw_config, raw_config=input_config)
        ttl = 3600  # one hour is plenty time to debug
        period = 'errorly'
    else:
        prefix, target = f'/b/{uid}', f'/b/{uid}/admin/{admin_uid}'
        backend = Backend(uid, admin_uid, config, raw_config, rootpath='/b/{uid}/')
        ttl = TIMES[period]

    ic = InstanceControl(backend, time.time() + ttl, period, config is None)
    return uid, ic, target


def create_from_form(aas_config: dict, title: str, period: str, uids: set, asp_file: str, userline: str, choicetype: str, choiceline: str) -> (str, InstanceControl, str):
    line_to_list = lambda line: [u.title() for u in map(str.strip, line.split(',')) if u]
    config = {
        'global options': {
            'base encoding file': asp_file,
        },
        'main page options': {
                'title': title,
        },
        'users options': {
            'allowed': line_to_list(userline),
        },
        'choices options': {
            'type': choicetype,
            'choices': line_to_list(choiceline),
        },
    }
    return create_from_config(aas_config, config, period, uids)


def validate_config(config_text: str) -> (dict or None, list[str]):
    # parse dict if it's a string
    if isinstance(config_text, str):
        try:
            config = json.loads(config_text)
        except json.JSONDecodeError as err:
            return None, [str(err)]
    else:
        assert isinstance(config_text, dict)
        config = config_text
    # parse configuration, and validate
    return config_module.parse_configuration(config, filesource='browser', verify=True)


def create_app(configpath: str):
    aascfg, _ = aasconfig_module.parse_config_file(configpath)
    bakasp_instances = {}  # uuid -> InstanceControl
    app = Flask(__name__, template_folder=os.path.join('templates/', aascfg['global options']['template']))


    @app.route('/create')
    def creation_of_new_instance():
        return render_template('creation-form.html', title='Form creation', description='Create a new instance from', methods=(('/create/byconfig', 'a raw configuration description in JSON'), ('/create/byform', 'create from a high level form preventing you to make mistakes')))

    @app.route('/create/byconfig', methods=['GET', 'POST'])
    def creation_of_new_instance_by_config():
        if request.method == 'POST':
            uid, control, target = create_from_config(
                aascfg, request.form['Config'], request.form['period'], uids=bakasp_instances, uid_creator=create_new_uid
            )
            assert uid not in bakasp_instances
            bakasp_instances[uid] = control
            return redirect(target)
        else:
            return render_template('creation-form-by-config.html', title='Form creation', description='', periods=((t, idx==0) for idx, t in enumerate(TIMES)))

    @app.route('/create/byform', methods=['GET', 'POST'])
    def creation_of_new_instance_by_form():
        if request.method == 'POST':
            choices = request.form['users'] if request.form['choose-set'] == 'choose-users' else request.form['choose-among-list']
            uid, control, target = create_from_form(
                aascfg,
                request.form['title'],
                request.form['period'],
                bakasp_instances,
                AVAILABLE_IMPLEMENTATIONS[request.form['implementation']],
                request.form['users'],
                request.form['choicetype'],
                choices
            )
            assert uid not in bakasp_instances
            bakasp_instances[uid] = control
            return redirect(target)
        else:
            return render_template(
                'creation-form-by-form.html',
                title='Form creation',
                description='',
                periods=((t, idx==0) for idx, t in enumerate(TIMES)),
                implementations=((t, idx==0) for idx, t in enumerate(AVAILABLE_IMPLEMENTATIONS)),
                choicetypes=((t, idx==0) for idx, t in enumerate(AVAILABLE_CHOICE_TYPES)),
            )


    @app.route('/')
    def index():
        return render_template('index.html', title='Bakasp', description='Welcome !', public_pages=['create_instance'])

    @app.route('/clear')
    def clear_page():
        nb_cleared = 0
        for uid, ctrl in tuple(bakasp_instances):
            ctrl = bakasp_instances[uid]
            if ctrl.datetimelimit > time.time():  # time is up ! Instance can be deleted
                del bakasp_instances[uid]
                nb_cleared += 1
        return '{nb_cleared} instances cleared.'

    @app.route('/stats')
    def stats_page():
        stats = {
            'nb_instances': len(bakasp_instances),
            **Counter('nb_instances_'+c.period_label for c in bakasp_instances.values()),
            'nb_error_instances': sum(1 for c in bakasp_instances.values() if c.haserror),
        }
        return render_template('aas-stats.html', stats=stats)

    @app.route('/stats/all')
    def all_stats_page():
        instances = (
            f"<a href='/b/{c.backend.uid}/admin/{c.backend.admin_uid}'>{c.backend.config.main_page_options.title or 'UNTITLED'}</a><br/>\n"
            for c in bakasp_instances.values()
        )
        return ''.join(instances)

    def path_for(page: str, admin=False) -> str:
        page = page.rstrip('/')
        if admin:
            return f"/b/<iuid>/{page+'/' if page else ''}admin/<admin_code>"
        return f"/b/<iuid>/{page}"

    def admin_path_for(page: str) -> str:
        return path_for(page, admin=True)

    # root to the instances index index pages
    @app.route(admin_path_for(''))
    @app.route(path_for(''))
    def page_instances_indexes(iuid: str, *, admin_code: str):
        instance_control = bakasp_instances.get(iuid)
        if instance_control:
            return Backend.html_instance_page(instance_control.backend, admin=admin_code, remaining_instance_time=utils.human_repr_of_timestamp(instance_control.datetimelimit))
        else:  # given instance uid is not an existing one
            return redirect(url_for('index'))

    # Now do the same for the remaining pages
    def func_for(func: callable) -> callable:
        "Return the function that app can use as a page generator for a route"
        @functools.wraps(func)
        def wrapper(iuid: str, *, admin_code: str = None):
            instance_control = bakasp_instances.get(iuid)
            if instance_control:
                if 'admin' in inspect.signature(func).parameters.keys():
                    return func(instance_control.backend, admin=admin_code)
                else:
                    return func(instance_control.backend)
            else:  # given instance uid is not an existing one
                return redirect(url_for('index'))
        return wrapper

    UNRESTRICTED_PAGES = {
        'thanks': Backend.html_thank_you_page,
        'user/<userid>': Backend.html_user_choice_page,
        'user': Backend.html_user_list_page,
    }
    PAGES = {
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
    app = create_app(sys.argv[1])
    app.run(port=8080, debug=True)

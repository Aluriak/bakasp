"""Bakasp «As A Service»: like framapad.org

usage:

    python aas.py <path to config file>

"""
import os
import sys
import json
import uuid
import time
import glob
import utils
import inspect
import functools
from collections import namedtuple, Counter
from flask import Flask, render_template, redirect, request, url_for

import config as config_module
import hashname
import aas_config as aasconfig_module
import bakasp_backend
from bakasp_backend import Backend


InstanceControl = namedtuple('InstanceControl', 'backend, datetimelimit, period_label, raw_config, haserror')


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


def create_from_config(aas_config: dict, input_config: dict, period: str|float, uids: set, *, state: tuple = None, admin_uid: str = None) -> (str, InstanceControl, str):
    """Create the backend, return its uid, its instance, the InstanceControl instance, and the page to which the user must be redirected"""
    config, raw_config = validate_config(input_config)
    if isinstance(uids, str):
        uid = uids
    else:  # uids is a set of already in-use uids
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
        if isinstance(period, (int, float)):
            ttl = period - time.time()
            period = utils.human_repr_of_diffstamp(ttl)
        else:
            assert isinstance(period, str)
            ttl = time.time() + aas_config['creation options']['available times'][period]

    if state is not None:
        backend.state = state

    ic = InstanceControl(backend, time.time() + ttl, period, raw_config, config is None)
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
            'type': 'restricted',
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
    return config_module.parse_configuration(config, filesource='browser', verify_and_normalize=True)


def create_aas_app(configpath: str):
    aascfg, _ = aasconfig_module.parse_config_file(configpath)
    bakasp_instances = {}  # uuid -> InstanceControl
    app = Flask(__name__, template_folder=os.path.join('templates/', aascfg['global options']['template']))
    filestate = utils.filestate_from_uid_and_cfg('aas', aascfg)

    def get_aas_state():
        return [aascfg, {uid: [ic[0].state, ic[1], ic[3], ic.backend.admin_uid] for uid, ic in bakasp_instances.items()}]
    def get_empty_state():
        return [aascfg, {}]
    def set_aas_state(new_state):
        nonlocal aascfg, bakasp_instances
        bakasp_instances = {}
        aascfg, ics = new_state
        for uid, ic in ics.items():
            uuid, control, _ = create_from_config(
                aascfg, state=ic[0], period=ic[1], input_config=ic[2], admin_uid=ic[3], uids=uid
            )
            assert uid == uuid, (uid, uuid)
            bakasp_instances[uuid] = control


    def save_state():
        if aascfg['meta']['save state']:
            with open(filestate, 'w') as fd:
                json.dump(get_aas_state(), fd)

    def load_state():
        if not aascfg['meta']['load state']:
            loaded = get_empty_state()
        elif not os.path.exists(filestate):
            loaded = get_empty_state()
        else:
            try:
                with open(filestate) as fd:
                    loaded = json.load(fd)
            except Exception as err:
                print(err)
                print('Empty state loaded')
                loaded = get_empty_state()
        set_aas_state(loaded)


    @app.route('/create')
    def creation_of_new_instance():
        return render_template('creation-form.html', title='Form creation', description='Create a new instance from', methods=(
            ('/create/byconfig', 'a raw configuration description in JSON'),
            ('/create/byform', 'create from a high level form preventing you to make mistakes'),
            ('/create/byexample', 'use an handmade example'),
        ), root='/')

    @app.route('/create/byconfig', methods=['GET', 'POST'])
    def creation_of_new_instance_by_config():
        if request.method == 'POST':
            uid, control, target = create_from_config(
                aascfg, request.form['Config'], request.form['period'], uids=bakasp_instances
            )
            assert uid not in bakasp_instances
            bakasp_instances[uid] = control
            save_state()
            return redirect(target)
        else:
            return render_template('creation-form-by-config.html', title='Form creation', description='', periods=((t, idx==0) for idx, t in enumerate(aascfg['creation options']['available times'])), root='/')

    @app.route('/create/byexample', methods=['GET', 'POST'])
    def creation_of_new_instance_by_example():
        if request.method == 'POST':
            example_name = request.form['example']
            with open('examples/' + example_name) as fd:
                config = fd.read()
            uid, control, target = create_from_config(
                aascfg, config, request.form['period'], uids=bakasp_instances
            )
            assert uid not in bakasp_instances
            bakasp_instances[uid] = control
            save_state()
            return redirect(target)
        else:
            examples = list(os.path.basename(f) for f in glob.glob('examples/*'))
            return render_template('creation-form-by-example.html', title='Example picker', description='choose which example you want to test', examples=examples, periods=((t, idx==0) for idx, t in enumerate(aascfg['creation options']['available times'])), root='/')

    @app.route('/create/byform', methods=['GET', 'POST'])
    def creation_of_new_instance_by_form():
        if request.method == 'POST':
            choices = request.form['users'] if request.form['choose-set'] == 'choose-users' else request.form['choose-among-list']
            uid, control, target = create_from_form(
                aascfg,
                request.form['title'],
                request.form['period'],
                bakasp_instances,
                aascfg['creation options']['available implementations'][request.form['implementation']],
                request.form['users'],
                request.form['choicetype'],
                choices
            )
            assert uid not in bakasp_instances
            bakasp_instances[uid] = control
            save_state()
            return redirect(target)
        else:
            return render_template(
                'creation-form-by-form.html',
                title='Form creation',
                description='',
                periods=((t, idx==0) for idx, t in enumerate(aascfg['creation options']['available times'])),
                implementations=((t, idx==0) for idx, t in enumerate(aascfg['creation options']['available implementations'])),
                choicetypes=((t, idx==0) for idx, t in enumerate(aascfg['creation options']['available choices types'])),
                root='/'
            )


    @app.route('/')
    def index():
        return render_template('index.html', title='Bakasp', description='Welcome !', public_pages=['create_instance'], root='/')

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
            '#instances': len(bakasp_instances),
            **Counter('#instances deleted in '+c.period_label for c in bakasp_instances.values()),
            '#error instances': sum(1 for c in bakasp_instances.values() if c.haserror),
        }
        save_state()
        return render_template('aas-stats.html', stats=stats, root='/')

    @app.route('/stats/all')
    def all_stats_page():
        instances = (
            f"<a href='/b/{c.backend.uid}/admin/{c.backend.admin_uid}'>{c.backend.cfg['main page options']['title'] + 'UNTITLED'}</a><br/>\n"
            for c in bakasp_instances.values()
        )
        return '<center>Instances:</center><br/>' + ''.join(instances) + repr(bakasp_instances)

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
    def page_instances_indexes(iuid: str, admin_code: str = None):
        instance_control = bakasp_instances.get(iuid)
        if instance_control:
            return Backend.html_instance_page(instance_control.backend, admin=admin_code, remaining_instance_time=utils.human_repr_of_timestamp(instance_control.datetimelimit))
        else:  # given instance uid is not an existing one
            return redirect(url_for('index'))

    @app.errorhandler(404)
    def page_not_found(e):
        # note that we set the 404 status explicitly
        # return render_template('404.html'), 404
        return redirect(url_for('index'))

    # Now do the same for the remaining pages
    def func_for(func: callable) -> callable:
        "Return the function that app can use as a page generator for a route"
        @functools.wraps(func)
        def wrapper(iuid: str, *, admin_code: str = None, **kwargs):
            instance_control = bakasp_instances.get(iuid)
            if instance_control:
                if 'admin' in inspect.signature(func).parameters.keys():
                    return func(instance_control.backend, admin=admin_code, **kwargs)
                else:
                    return func(instance_control.backend, **kwargs)
            else:  # given instance uid is not an existing one
                return redirect(url_for('index'))
        return wrapper

    PAGES = (  # path, func, restricted, post_allowed
        ('thanks', Backend.html_thank_you_page, False, False),
        ('user/<userid>/<choiceid>', Backend.post_user_choice_page, False, True),
        ('user/<userid>', Backend.html_user_overview_page, False, False),
        ('user', Backend.html_user_list_page, False, False),
        ('configuration', Backend.html_config, True, False),
        ('configuration/raw', Backend.html_raw_config, True, False),
        ('reset', Backend.html_reset, True, False),
        ('results', Backend.html_results, True, False),
        ('compilation', Backend.html_compilation, True, False),
        ('history', Backend.html_history, True, False),
        ('overview', Backend.html_overview, True, False),
    )
    for path, func, restricted, post_allowed in PAGES:
        rpath = path_for(path)
        func = func_for(func)
        methods = ['GET', 'POST'] if post_allowed else ['GET']
        if restricted:
            apath = admin_path_for(path)
            app.route(rpath, methods=methods)(func)
            app.route(apath, methods=methods)(func)
            print(f"\tPaths {rpath} and {apath} redirect to {func.__name__}")
        else:
            app.route(rpath, methods=methods)(func)
            print(f"\tPath {rpath} redirects to {func.__name__}")

    load_state()
    return app

if __name__ == "__main__":
    app = create_aas_app(sys.argv[1])
    app.run(port=8080, debug=True)

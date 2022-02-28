"""Bakasp «As A Service»: like framapad.org

"""
import json
import uuid
import time
import utils
from collections import namedtuple
from flask import Flask, render_template, redirect, request, url_for

import bakasp_backend
import bakasp_frontend

InstanceControl = namedtuple('InstanceControl', 'backend, datetimelimit, haserror')
SECONDS_PER_DAY = 3600 * 24
TIMES = {
    'weekly': 7*SECONDS_PER_DAY,
    'monthly': 30*SECONDS_PER_DAY,
}


def create_from_config(title: str, config: dict, period: str, bakasp_instances: dict, bakasp_controls: dict):
    config, raw_config = validate_config(config)
    if config is None:
        uid = admin_uid = str(uuid.uuid4())
        prefix = target = f'/b/{uid}'
        state = raw_config  # list of errors
        backend_type = bakasp_backend.ErrorBackend
    else:
        uid, admin_uid = str(uuid.uuid4()), str(uuid.uuid4())
        prefix, target = f'/b/{uid}', f'/b/{uid}/{admin_uid}'
        state = bakasp.get_empty_state()  # empty state
        backend_type = bakasp_backend.Backend
    backend = backend_type(uid, admin_uid, config, raw_config)
    ic = InstanceControl(backend, time.time() + TIMES[period], config is None)
    bakasp_controls[uid] = ic
    bakasp_instances[uid] = backend
    return redirect(target)


def validate_config(config_text: str) -> (dict or None, list[str]):
    try:
        config = json.loads(config_text)
    except json.JSONDecodeError as err:
        return None, [str(err)]
    config, raw_config = parse_configuration(config, filesource='browser', verify=True)
    if config is None:
        return None, raw_config
    # everything looks ok
    return config, raw_config


def create_app():
    bakasp_instances = {}  # uuid -> Backend
    bakasp_controls = {}  # uuid -> InstanceControl
    app = Flask(__name__, template_folder='templates/iamDziner/')
    bakasp_frontend.populate_app_routes(app, bakasp_instances, '/b/', uid_in_url=True)

    @app.route('/create', methods=['GET', 'POST'])
    def creation_of_new_instance():
        if request.method == 'POST':
            return create_from_config(
                request.form['Title'], request.form['Config'], request.form['period'], bakasp_instances, bakasp_controls
            )
        else:
            # print(list((t, idx==0) for idx, t in enumerate(TIMES)))
            return render_template('creation-form.html', title='Form creation', description='', periods=((t, idx==0) for idx, t in enumerate(TIMES)))


    @app.route('/')
    def index():
        return render_template('index.html', title='Bakasp', description='Welcome !', public_pages=['create_instance'])

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(port=8080, debug=True)

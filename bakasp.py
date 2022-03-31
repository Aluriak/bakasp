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
import model_repr
from config import parse_configuration_file
from asp_model import ShowableModel
from bakasp_backend import Backend


def get_empty_state():
    return [{}, [], []]


def create_website(cfg: dict, raw_cfg: dict, *, admin: str = None):
    """Expect the configuration to be valid"""
    template_folder = os.path.join('templates/', cfg['global options']['template'])
    app = Flask(__name__, template_folder=template_folder)
    back = Backend('', admin, cfg, raw_cfg)

    users_who_changed_their_choices = set()
    stats = {}  # some stats about global state
    models = []  # list of all found models
    result_header, result_footer = '', ''  # header and footer of the result page
    history = []  # (datetime, userids -> choices, new_models, lost_models)
    user_choices = {}  # userid -> choices
    previous_models_uid = set()  # uids of found models before last compilation


    app.route('/')(back.html_instance_page)
    app.route('/thanks')(back.html_thank_you_page)

    app.route('/user')(back.html_user_list_page)

    @app.route('/user/<userid>', methods=['GET', 'POST'])
    def page_user_choice(userid):
        if request.method == 'POST':
            return back.set_user_choice(userid, request.form)
        else:
            return back.html_user_choice_page(userid)


    if 'configuration' in cfg["global options"]["public pages"]:
        app.route('/configuration')(back.html_config)
        app.route('/configuration/raw')(back.html_raw_config)

    if 'compilation' in cfg["global options"]["public pages"]:
        app.route('/compilation')(back.html_compilation)

    if 'history' in cfg["global options"]["public pages"]:
        app.route('/history')(back.html_history)

    if 'overview' in cfg["global options"]["public pages"]:
        app.route('/overview')(back.html_overview)

    if 'results' in cfg["global options"]["public pages"]:
        app.route('/results')(back.html_results)

    if 'reset' in cfg["global options"]["public pages"] and cfg['meta']['save state']:
        app.route('/reset')(back.html_reset)

    return app


def create_app(jsonfile: str, blueprint:bool = False) -> Flask or None:
    cfg, raw_cfg = parse_configuration_file(jsonfile)
    if cfg:
        return create_website(cfg, raw_cfg)
    else:
        return utils.create_errorlist_app(errors=raw_cfg, blueprint=blueprint)


if __name__ == "__main__":
    app = create_app(sys.argv[1])
    app.run(port=8080, debug=True)

"""
"""
import os
import sys
import json
import time
import itertools
from functools import lru_cache
from flask import Flask, request, redirect, url_for, render_template
from markupsafe import Markup

import utils
import model_repr
from config import parse_configuration_file
from asp_model import ShowableModel
from bakasp_backend import Backend


def get_empty_state():
    return [{}, [], []]


def create_website(cfg: dict, raw_cfg: dict, *, admin: str = None, state: tuple = None):
    """Expect the configuration to be valid"""
    template_folder = os.path.join('templates/', cfg['global options']['template'])
    app = Flask(__name__, template_folder=template_folder)
    back = Backend('', admin, cfg, raw_cfg)
    back.link_to_flask_app(app)
    if state:
        back.state = state
    return app


def create_app(jsonfile: str, *, blueprint:bool = False, admin: str = None, state: tuple = None) -> Flask or None:
    cfg, raw_cfg = parse_configuration_file(jsonfile)
    if cfg:
        return create_website(cfg, raw_cfg, admin=admin, state=state)
    else:
        return utils.create_errorlist_app(errors=raw_cfg, blueprint=blueprint)


if __name__ == "__main__":
    app = create_app(sys.argv[1])
    app.run(port=8080, debug=True)

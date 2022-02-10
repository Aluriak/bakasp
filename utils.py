

import clyngor
import random
from flask import Flask, request, redirect, url_for, render_template, Markup


def create_sorry_app(msg: str = 'Sorry, a configuration problem prevent this website to behave normally. Logs are necessary for further debug.'):
    app = Flask(__name__)
    @app.route('/')
    def main_page():
        return msg
    return app


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

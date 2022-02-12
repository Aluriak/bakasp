

import random
import clyngor
from flask import Flask, request, redirect, url_for, render_template, Markup
from itertools import zip_longest


def create_sorry_app(msg: str = 'Sorry, a configuration problem prevent this website to behave normally. Logs are necessary for further debug.'):
    app = Flask(__name__)
    @app.route('/')
    def main_page():
        return msg
    return app


def create_errorlist_app(msg: str = 'Sorry, configuration problems prevent this website to behave normally. Logs are necessary for further debug.', errors: list = []):
    app = Flask(__name__)
    @app.route('/')
    def main_page():
        return f"{msg}<br/><ul>\n" + ''.join(f'<li>{err}</li>\n' for err in errors) + '</ul>'
    return app


def call_ASP_solver(encoding: str, n: int, sampling: bool, cli_options: list = [], constants: dict = {}, optimals_only: bool = False) -> [frozenset]:
    "Call to the ASP solver with given encoding and n/sampling config values"

    if optimals_only:
        if '--opt-mode=optN' not in cli_options:
            cli_options.append('--opt-mode=optN')
        converter = lambda ms: list(clyngor.opt_models_from_clyngor_answers(ms))
    else:
        converter = list

    models = converter(clyngor.solve(inline=encoding, nb_model=int(n), options=cli_options, constants=constants))
    if sampling:
        if len(models) > n:
            models = random.sample(models, n)
        yield from models
    else:
        yield from models


def by_chunks(iterable, n, fillvalue=None):
    """Collect data into fixed-length chunks or blocks

    >>> tuple(map(''.join, grouper('ABCDEFG', 3, 'x')))
    ('ABC', 'DEF', 'Gxx')
    >>> tuple(grouper('ABC', 2))
    (('A', 'B'), ('C', None))

    """
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

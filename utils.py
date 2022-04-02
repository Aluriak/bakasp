
import re
import time
import random
import clyngor
from flask import Flask, Blueprint
from itertools import zip_longest

clyngor.use_clingo_binary()


def create_sorry_app(msg: str = 'Sorry, a configuration problem prevent this website to behave normally. Logs are necessary for further debug.', blueprint: bool = False):
    app = Blueprint('bakasp-sorry-instance', 'bakasp-sorry-instance') if blueprint else Flask('bakasp-sorry-instance')
    @app.route('/')
    def main_page():
        return msg
    return app


def create_errorlist_app(msg: str = 'Sorry, configuration problems prevent this website to behave normally. Logs are necessary for further debug.',
                         errors: list = [], blueprint: bool = False) -> Flask:
    app = Blueprint('bakasp-error-instance', 'bakasp-error-instance') if blueprint else Flask('bakasp-error-instance')
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

    >>> tuple(map(''.join, by_chunks('ABCDEFG', 3, 'x')))
    ('ABC', 'DEF', 'Gxx')
    >>> tuple(by_chunks('ABC', 2))
    (('A', 'B'), ('C', None))

    """
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def human_repr_of_runtime(runtime:float) -> str:
    """return a human readable representation of given float value encoding a runtime in seconds

    >>> human_repr_of_runtime(1.0)
    '1s'
    >>> human_repr_of_runtime(3601)
    '1h0m1s'

    """
    if runtime >= 3600:
        h = int(runtime) // 3600
        s = int(runtime) % 3600
        return f"{h}h{s // 60}m{s % 60}s"
    if runtime > 100:
        return f"{int(runtime) // 60}m{int(runtime) % 60}s"
    elif runtime > 1:
        return f"{round(runtime, 1)}s"
    elif runtime == 1:
        return "1s"
    else:
        return f"{round(runtime, 5)}s"

def human_repr_of_timestamp(ts: float) -> str:
    """
    >>> human_repr_of_timestamp(time.time() + 10)
    'in 10s'
    >>> human_repr_of_timestamp(time.time() + 30*60)
    'in 30mn'
    >>> human_repr_of_timestamp(time.time() - 30*60)
    '30mn ago'
    >>> human_repr_of_timestamp(time.time() - 58)
    '1mn ago'
    >>> human_repr_of_timestamp(time.time() - 59*60)
    '1h ago'
    """
    diff = ts - time.time()
    if diff < 0:  # in the past
        prefix, suffix = '', ' ago'
    elif abs(diff) < 1:  # around now
        return 'now'
    else:  # in the future
        prefix, suffix = 'in ', ''
    return prefix + human_repr_of_diffstamp(round(diff)) + suffix

def human_repr_of_diffstamp(diff: int, *, subcall: bool = False) -> str:
    diff = abs(diff)
    if diff < 1:
        return '' if subcall else 'now'

    THRESHOLDS = {
        0: '{n}s',
        60: '{n}mn',
        3600: '{n}h',
        24*3600: '{n} day',
        7*24*3600: '{n} week',
        30*7*24*3600: '{n} month',
        365*7*24*3600: '{n} year',
        100*365*7*24*3600: '{n} century',
    }
    for real_time, template in reversed(THRESHOLDS.items()):
        # print(diff, real_time, diff >= real_time*0.90)
        if real_time == 0:
            return template.format(n=diff)
        elif diff >= real_time*0.90 and diff < real_time:  # almost !
            return template.format(n=1)
        elif diff >= real_time:
            return template.format(n=int(diff // real_time))





def range_from_human_repr(s: str, accept_impossible_range:bool = False) -> (int, int):
    """

    >>> range_from_human_repr('at least 1')
    (1, None)
    >>> range_from_human_repr('any')
    (None, None)
    >>> range_from_human_repr('between 3 and 7')
    (3, 7)
    >>> range_from_human_repr('at most -18')
    (None, -18)

    Combine with comma:

    >>> range_from_human_repr('less than 3, at least 1')
    (1, 2)
    >>> range_from_human_repr('7 or more, less than 10')
    (7, 9)

    Order doesn't count:

    >>> range_from_human_repr('less than 3, less than 10, less than 7')
    (None, 2)
    >>> range_from_human_repr('less than 3, less than 7, less than 10')
    (None, 2)
    >>> range_from_human_repr('less than 7, less than 10, less than 3')
    (None, 2)
    >>> range_from_human_repr('more than 0, 9 or less')
    (1, 9)
    >>> range_from_human_repr('more than 0, exactly 4, ')
    (4, 4)

    Impossible ranges raises ValueError unless explicitely accepted:

    >>> range_from_human_repr('more than 0, less than 0', accept_impossible_range=True)
    (1, -1)
    >>> range_from_human_repr('exactly 3, exactly 4', accept_impossible_range=True)
    (4, 3)

    """
    def get_constraint(s: str):
        def get(m, i=0):  return None if m.groups()[i] is None else int(m.groups()[i])
        if s == 'any':
            return None, None
        if m := re.fullmatch(r'at least (-?[0-9]+)', s):
            return get(m), None
        if m := re.fullmatch(r'at most (-?[0-9]+)', s):
            return None, get(m)
        if m := re.fullmatch(r'less than (-?[0-9]+)', s):
            return None, get(m)-1
        if m := re.fullmatch(r'more than (-?[0-9]+)', s):
            return get(m)+1, None
        if m := re.fullmatch(r'between (-?[0-9]+) and (-?[0-9]+)', s):
            return get(m), get(m,1)
        if m := re.fullmatch(r'(-?[0-9]+) or more', s):
            return get(m), None
        if m := re.fullmatch(r'(-?[0-9]+) or less', s):
            return None, get(m)
        if m := re.fullmatch(r'exactly (-?[0-9]+)', s):
            return get(m), get(m)
        raise ValueError(f"Invalid range format: {repr(s)}.")
    constraints = (get_constraint(sub) for sub in map(str.strip, s.split(',')) if sub)
    low, hih = next(constraints)
    for l, h in constraints:
        if l is not None:
            low = l if low is None else (l if l > low else low)
        if h is not None:
            hih = h if hih is None else (h if h < hih else hih)
    refuse_impossible_range = not accept_impossible_range
    if refuse_impossible_range and low is not None and hih is not None and low > hih:
        raise ValueError(f"Range [{low}:{hih}] obtained from {repr(s)} is not a valid range.")
    return low, hih

def is_human_repr_of_range(s: str) -> bool:
    try:
        range_from_human_repr(s)
    except ValueError:
        return False
    return True


def range_as_js(r):
    low, hih = r
    return ('-Infinity' if low is None else low), ('Infinity' if hih is None else hih)

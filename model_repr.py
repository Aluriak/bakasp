"""Functions creating html representation of ASP models.
"""

import hashname


def from_name(repr_name: str) -> callable:
    "Return the representation function corresponding to given representation name"
    return {
        'raw': as_raw,
        'table/2': as_table,
    }[repr_name]


def model_stable_repr(model: frozenset) -> tuple:
    """Return the same model, only everything is ordered so that models
    with exact same atoms get the exact same representation.

    This is used to ensure that each model is its own and unchanged identifier
    between two encoding compilation. Its representation change only
    if the atoms changes.

    """
    if isinstance(model, frozenset) and all(isinstance(e, tuple) and isinstance(e[0], str) and isinstance(e[1], tuple) for e in model):
        # model is frozenset of (predicate:str, args:tuple)
        # args are (since their order is data) left untouched.
        return tuple(sorted(list(model)))
    else:
        raise ValueError(f"Received model of type {type(model)} cannot be transformed into a stable representation: {model}")


def as_raw(idx: int, model: tuple, userid_to_label: callable, choiceid_to_label: callable) -> str:
    """Return html representation of given model"""

    by_pred = {}
    for atom, args in model:
        by_pred.setdefault(atom, []).append(args)
    html = []
    for atom, argss in by_pred.items():
        html.append(f'{len(argss)} <code>{atom}</code> atoms found: <code>' + ' '.join(f'{atom}({",".join(map(str, args))}).' for args in argss) + '</code>')
    # if only one atom of arity 2, then show it as a table
    if len(by_pred) == 1 and all(len(args) == 2 for args in next(iter(by_pred.values()))):
        html.append('')
        html.append(as_table(idx, model, userid_to_label, choiceid_to_label, integrated=True))
    return f'<h2>Solution {idx}</h2><b>— {hashname.from_obj(model)} —</b><br/><br/><br/>' + '<br/>'.join(html) + '<br/>'


def as_table(idx: int, model: tuple, obj_to_label: callable, att_to_label: callable, integrated: bool = False) -> str:
    """Return html representation of given model"""

    objs, atts, rels = set(), set(), {}
    for atom, args in model:
        if len(args) == 2:
            obj, att = args
            objs.add(obj)
            atts.add(att)
            rels.setdefault(obj, set()).add(att)
    html = [' <tr>\n  <td></td>\n' + ''.join(f'   <th>{att_to_label(att)}</th>\n' for att in atts) + ' </tr>\n']
    for obj in objs:
        html.append(f' <tr>\n  <td>{obj_to_label(obj)}</td>' + ''.join(f'   <td>{"×" if att in rels[obj] else ""}</td>\n' for att in atts) + ' </tr>\n')

    if integrated:
        return '<table>' + ''.join(html) + '</table>'
    else:
        return f'<h2>Solution {idx}</h2><br/><table>' + ''.join(html) + '</table><br/>'

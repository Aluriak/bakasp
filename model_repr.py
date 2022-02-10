"""Functions creating html representation of ASP models.
"""


def from_name(repr_name: str) -> callable:
    "Return the representation function corresponding to given representation name"
    return {
        'raw': as_raw,
        'table/2': as_table,
    }[repr_name]


def as_raw(idx: int, model: frozenset, userid_to_label: callable, choiceid_to_label: callable) -> str:
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
    return f'<h2>Solution {idx}</h2><br/>' + '<br/>'.join(html) + '<br/>'


def as_table(idx: int, model: frozenset, obj_to_label: callable, att_to_label: callable, integrated: bool = False) -> str:
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

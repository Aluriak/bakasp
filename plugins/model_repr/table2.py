

from model_repr import ModelReprPlugin


def fields_from_source(atoms: iter, source: str) -> (list, list, dict):
    """
    Returns list of rows, list of columns, and relations between the two
    found in given atoms and according to source.

    For instance, here:

    >>> fields_from_source([('assoc', (1, 2)), ('assoc', (2, 3))], "assoc/rows,columns")
    ([1, 2], [2, 3], {1: {2}, 2: {3}})

    We find rows/objs [1, 2], columns/atts [2, 3], and relations 1->2 and 2->3.
    When atom arguments are not relevant, underscore may be used.

    >>> fields_from_source([('assoc', (1, 8, 2, 7)), ('assoc', (2, 9, 3, 8))], "assoc/columns,_,rows,_")
    ({'rows': [2, 3], 'columns': [1, 2], 'relations': {3: {2}, 2: {1}}})
    ([2, 3], [1, 2], {3: {2}, 2: {1}})

    If an atom argument has a value different from rows, columns or underscore,
    it is understood as a value that the atom must have for it to be considered while building the outputs.
    Example :

    >>> fields_from_source([('assoc', (1, 2, 'yes')), ('assoc', (2, 3, 4))], "assoc/rows,columns,yes")
    ([1], [2], {1: {2}})

    """
    assert '/' in source, f"source is not properly formatted: expects '{{pred}}/{{arg1}},…,{{argN}}', not {repr(source)}"
    src_pred, src_args = source.split('/')
    src_args = src_args.split(',')
    # assert set(src_args) == {'rows', 'columns', '_'}, f"source arguments are not properly named: expects rows and columns, not {' and '.join(src_args)}."
    ret_rows, ret_columns, ret_relations = set(), set(), {}

    for pred, args in atoms:
        if pred == src_pred and len(args) == len(src_args):
            for field, value in zip(src_args, args):
                if field not in {'rows', 'columns', '_'} and field != str(value):
                    break  # this atom must be filtered out
            else:  # the atom corresponds to the source signature
                dargs = dict(zip(src_args, args))
                ret_rows.add(dargs['rows'])
                ret_columns.add(dargs['columns'])
                ret_relations.setdefault(dargs['rows'], set()).add(dargs['columns'])
    return sorted(list(ret_rows)), sorted(list(ret_columns)), ret_relations


class table2(ModelReprPlugin):
    OPTIONS = {
        "kind": 'table/2',
        "rows": 'user',
        "columns": 'choice',
        "source": 'assoc/rows,columns',
        "caption": '',
        "caption style": '<br/><small><i>{caption}</i></small><br/>',
    }

    def on_model(self, idx: int, uid: str, model: object):
        """Return html representation of given model"""

        def att_to_label(att: object) -> str:
            if self.options.columns == 'choice':
                return self.get_choicename_of(att)
            else:  # get the corresponding element of the columns list of items
                self.options.columns[atts.index(att) % len(self.options.columns)]

        def obj_to_label(obj: object) -> str:
            if self.options.rows == 'user':
                return self.get_username_of(obj)
            else:  # get the corresponding element of the rows list of items
                self.options.rows[objs.index(obj) % len(self.options.rows)]

        objs, atts, rels = fields_from_source(model.atoms, self.options.source)
        html = [' <tr>\n  <td></td>\n' + ''.join(f'   <th>{att_to_label(att)}</th>\n' for att in atts) + ' </tr>\n']
        for obj in objs:
            html.append(f' <tr>\n  <td>{obj_to_label(obj)}</td>' + ''.join(f'   <td>{"×" if att in rels[obj] else ""}</td>\n' for att in atts) + ' </tr>\n')
        caption = self.options.caption_style.format(caption=self.options.caption) if self.options.caption else ''
        return '<table>' + ''.join(html) + '</table>' + caption


    def on_header(self):
        pass

    def on_footer(self):
        pass

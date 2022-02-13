
from model_repr import ModelReprPlugin


class raw(ModelReprPlugin):
    """Plain lists of atoms of the found model"""
    OPTIONS = {
        "kind": 'raw',
        "atoms": 'all',
        "footer": '<br/>',
    }

    def on_model(self, idx: int, uid: str, model: object):
        """Return html representation of given model"""

        if self.options.atoms == 'all':
            def ok(pred: str) -> bool:
                return True
            def oka(pred: str, args: tuple) -> bool:
                return True
        else:
            raise NotImplementedError("Sorry.")

        by_pred = {}
        for atom, args in model.atoms:
            by_pred.setdefault(atom, []).append(args)
        html = []
        for atom, argss in by_pred.items():
            if not ok(atom): continue
            yield f'{len(argss)} <code>{atom}</code> atoms found: <code>' + ' '.join(f'{atom}({",".join(map(str, args))}).' for args in argss if oka(atom, args)) + '</code><br/>'
        yield self.options.footer


    def on_header(self, models: list[object]):
        pass


import hashname
import model_repr
from flask import Markup


class ShowableModel:
    "Wrapper around clyngor ASP model, with specific informations in it"

    def __init__(self, idx: int, clyngor_model: frozenset, repr_funcs: list[callable], show_uid: bool):
        self.atoms = model_stable_repr(clyngor_model)
        self.uid = hashname.from_obj(self.atoms) if show_uid else None
        self.idx, self.repr_funcs = idx, repr_funcs
        # Markup is necessary for flask to render the html, instead of just writing it as-is
        self.html_repr = Markup(''.join(func(self.idx, self.uid, self) for func in repr_funcs))

    @staticmethod
    def intersection(models: iter):
        models = iter(models)
        base_model = next(models)
        acc = {}
        for pred, args in base_model.atoms:
            acc.setdefault(pred, set()).add(args)
        for model in models:
            for pred, args in model.atoms:
                acc[pred] &= set(args)
        print(acc)
        # return {pred: list(argss) for pred, argss in acc.items() if argss}
        return ShowableModel(-1, acc, base_model.repr_funcs, show_uid=False)


def model_stable_repr(model: frozenset) -> tuple:
    """Return the same model, only everything is ordered so that models
    with exact same atoms get the exact same representation.

    This is used to ensure that each model is its own and unchanged identifier
    between two encoding compilation. Its representation change only
    if the atoms changes.

    """
    if isinstance(model, (list, tuple, frozenset)) and all(isinstance(e, tuple) and isinstance(e[0], str) and isinstance(e[1], tuple) for e in model):
        # model is frozenset of (predicate:str, args:tuple)
        # args are (since their order is data) left untouched.
        return tuple(sorted(list(model)))
    elif isinstance(model, dict) and all(isinstance(p, str) and isinstance(a, (set, list, tuple)) for p, a in model.items()):
        return model_stable_repr([(pred, args) for pred, argss in model.items() for args in argss])
    else:
        raise ValueError(f"Received model of type {type(model)} cannot be transformed into a stable representation: {model}")


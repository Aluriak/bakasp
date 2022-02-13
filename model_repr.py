"""Functions loading the plugins, and exposing all functions to
create html representation out of ASP models.

"""
from pluginsystem import ModelReprPlugin


def gen_model_repr_plugins(repr_options_list: list[dict], get_username_of: callable, get_choicename_of: callable) -> [ModelReprPlugin]:
    "Yield the ordered list of representation functions asked by given configuration"
    for rule in repr_options_list:
        repr_name = rule['kind']
        if repr_name not in MODEL_REPR_PLUGINS:
            assert False, "that shouldn't happen in configuration was properly verified"
        yield MODEL_REPR_PLUGINS[repr_name](rule, get_username_of, get_choicename_of)

def names() -> frozenset[str]:
    "Return the available representation names"
    return frozenset(MODEL_REPR_PLUGINS)

def get_plugin_by_name(name: str) -> ModelReprPlugin:
    return MODEL_REPR_PLUGINS[name]


MODEL_REPR_PLUGINS = ModelReprPlugin.get_plugins()

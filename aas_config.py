"""Routines related to extraction, interpretation and use of json configuration files for bakasp As A Service"""

import os
import copy
import json
import itertools

import utils
import model_repr


SECONDS_PER_DAY = 3600 * 24
TIMES = {
    'daily': 1*SECONDS_PER_DAY,
    'weekly': 7*SECONDS_PER_DAY,
    'monthly': 30*SECONDS_PER_DAY,
}
AVAILABLE_IMPLEMENTATIONS = {
    'One-to-One Association': 'data/asp/one-to-one-assoc.lp',
    'Team Maker': 'data/asp/making-teams.lp',
}
AVAILABLE_CHOICE_TYPES = {  # choice uids
    'at least 1',
    'at most 1',
    'exactly 1',
}


def parse_config_file(json_file:str):
    with open(json_file) as fd:
        data = json.load(fd)
    return parse_configuration(data, filesource=json_file)

def parse_configuration(data:dict, *, filesource: str, verify: bool = True):
    raw_data = copy.deepcopy(data)
    if not verify:
        return data, raw_data  # hope it's valid

    # put global options in their namespace
    data.setdefault("global options", {})
    for option_name, value in tuple(data.items()):
        if not option_name.endswith(' options'):
            data["global options"][option_name] = value
            del data[option_name]

    # ensure the presence of default values if necessary
    def set_default(key, subkey, default_value):
        data.setdefault(key, {})
        data[key].setdefault(subkey, default_value)

    set_default('admin options', 'password format', 'long')
    set_default('server options', 'max instances', 0)
    set_default('server options', 'uid format', 'memorable')
    set_default('creation options', 'available times', 'all')
    set_default('creation options', 'available implementations', 'all')
    set_default('global options', 'template', 'iamDziner')

    # derivate values
    if data["server options"]["max instances"] == -1:
        data["server options"]["max instances"] = 0
    if data["creation options"]["available times"] == 'all':
        data["creation options"]["available times"] = tuple(TIMES)
    if data["creation options"]["available implementations"] == 'all':
        data["creation options"]["available implementations"] = tuple(AVAILABLE_IMPLEMENTATIONS)

    # fix types
    def str_to_list(key, subkey, splitter=' '):
        if isinstance(data[key][subkey], str):
            data[key][subkey] = data[key][subkey].split(splitter)
        assert isinstance(data[key][subkey], (tuple, list))
    str_to_list("creation options", "available times")
    str_to_list("creation options", "available implementations")

    return data, raw_data


def errors_in_configuration(cfg: dict):
    errors = []  # list of all found errors
    base_keys = set(cfg.keys())

    # domain checking
    def ensure_in(key, subkey, ok_values, other_valid_values=set()):
        if (val := cfg[key][subkey]) not in ok_values:
            if just_false_on_error:
                return False
            errors.append(f"{key} '{subkey}' is invalid: '{val}'. Accepted values are {', '.join(map(repr, set(ok_values)+set(other_valid_values)))}")

    ensure_in("server options", "uid format", {'short', 'long', 'memorable'})
    ensure_in("admin options", "password format", {'short', 'long', 'memorable'})

    # type checking
    def ensure_is(key, subkey, *types):
        if not isinstance((val := cfg[key][subkey]), tuple(types)):
            errors.append(f"{key} '{subkey}' is of invalid type: value {repr(val)} of type {type(val)}. Accepted types are {', '.join(map(repr, types))}")

    ensure_is('server options', 'max instances', int)

    return errors


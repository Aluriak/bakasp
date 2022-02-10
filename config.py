"""Routines related to extraction, interpretation and use of json configuration files"""

import copy
import json


def parse_configuration_file(json_file:str):
    with open(json_file) as fd:
        data = json.load(fd)
    return parse_configuration(data)

def parse_configuration(data:dict, *, verify: bool = True):
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
    set_default("global options", "location", "/")
    set_default("global options", "base encoding", "")
    set_default("global options", "shows", "")
    set_default("global options", "engine", "ASP/clingo")
    set_default("global options", "compilation", "direct access")
    set_default("global options", "generated pages", 'all')
    set_default("global options", "public pages", None)
    set_default("global options", "raise warnings", True)
    set_default("global options", "raise errors", True)
    set_default("global options", "template", 'iamDziner')
    set_default("users options", "type", "valid-id")
    set_default("users options", "allowed", {})
    set_default("choices options", "default", "all")
    set_default("choices options", "type", "first")
    set_default("choices options", "choices", {})
    set_default("choices options", "data atoms", [])
    set_default("choices options", "produced atoms", [])
    set_default("output options", "max models", 0)
    set_default("output options", "model selection", "first")
    set_default("output options", "model repr", "table/2")
    set_default("output options", "insatisfiability message", "<i>That program is unsatisfiable.</i>")
    set_default("overview options", "public", True)
    set_default("overview options", "type", ["raw", "table"])
    set_default("main page options", "title", "")
    set_default("main page options", "description", "You are on the main page. Please provide your preferences on the user page, or/and consult the results page")

    # propagate values
    if data["global options"]["generated pages"] == 'all':
        data["global options"]["generated pages"] = ["user", "results", "overview", "compilation", "configuration"]
    if data["global options"]["public pages"] is None:
        data["global options"]["public pages"] = data["global options"]["generated pages"]
    if data["choices options"]["default"] == 'all':
        data["choices options"]["default"] = list(data["choices options"]["choices"].values())

    # fix types
    def str_to_list(key, subkey, splitter=' '):
        if isinstance(data[key][subkey], str):
            data[key][subkey] = data[key][subkey].split(splitter)
        assert isinstance(data[key][subkey], list)
    str_to_list("choices options", "data atoms")
    str_to_list("choices options", "produced atoms")
    str_to_list("global options", "shows")

    # raise warnings for weird situations
    if data["global options"]["raise warnings"]:
        if not data["global options"]["base encoding"].strip():
            print("WARNING: base encoding is empty. Looks weird.")
        public_pages = data["global options"]["public pages"]
        generated_pages = set(data["global options"]["generated pages"])
        for page in public_pages:
            if page not in generated_pages:
                print("WARNING: page {page} is set as public, but not generated. It will be removed from public.")
        data["global options"]["public pages"] = [p for p in data["global options"]["public pages"] if p in generated_pages]

    # check validity of the configuration dict
    if data["global options"]["raise errors"]:
        if errors := errors_in_configuration(data):
            print(f"Malformed configuration ({len(errors)} errors).")
            for error in errors:
                print("\tERROR:", error)
            return None

    return data, raw_data  # looks ok


def errors_in_configuration(cfg: dict):
    errors = []  # list of all found errors
    base_keys = set(cfg.keys())

    def get_error(key, subkey, ok_values):
        if val := cfg[key][subkey] not in ok_values:
            errors.append(f"{key} '{subkey}' is invalid: '{val}'. Accepted values are {', '.join(map(repr, ok_values))}")

    get_error("choices options", "type", {'single', 'multiple'})
    get_error("global options", "compilation", {'direct access', 'specific access'})
    ... # TODO
    return errors

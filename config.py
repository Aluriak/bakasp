"""Routines related to extraction, interpretation and use of json configuration files"""

import os
import copy
import json
import itertools

import utils
import model_repr


def parse_configuration_file(json_file:str):
    with open(json_file) as fd:
        data = json.load(fd)
    return parse_configuration(data, filesource=json_file)

def parse_configuration(data:dict, *, filesource: str, verify_and_normalize: bool = True):
    raw_data = copy.deepcopy(data)
    if not verify_and_normalize:
        return data, raw_data  # hope it's valid

    # put global options in their namespace
    data.setdefault("global options", {})
    for option_name, value in tuple(data.items()):
        if not option_name.endswith(' options'):
            data["global options"][option_name] = value
            del data[option_name]

    # if 'choices options' is not a list, make it one
    if 'choices options' in data and not isinstance(data['choices options'], (tuple, list)):
        assert isinstance(data['choices options'], dict), data['choices options']
        data['choices options'] = [data['choices options']]
    if 'choices options' not in data:
        data['choices options'] = []

    # ensure the presence of default values if necessary
    def set_default(key, subkey, default_value):
        data.setdefault(key, {})
        data[key].setdefault(subkey, default_value)

    set_default('global options', 'location', '/')
    set_default('global options', 'base encoding', '')
    set_default('global options', 'base encoding file', None)
    set_default('global options', 'shows', '')
    set_default('global options', 'compilation', 'direct access')
    set_default('global options', 'generated pages', 'all')
    set_default('global options', 'public pages', None)
    set_default('global options', 'raise warnings', True)
    set_default('global options', 'raise errors', True)
    set_default('global options', 'template', 'iamDziner')
    set_default('users options', 'type', 'valid-id')
    set_default('users options', 'allowed', {})
    set_default('users options', 'description', "Please indicate your username:")
    set_default('output options', 'max models', 0)
    set_default('output options', 'model selection', 'first')
    set_default('output options', 'model header repr', 'standard')
    set_default('output options', 'model repr', [])
    set_default('output options', 'model footer repr', 'standard')
    set_default('output options', 'insatisfiability message', "<i>That program is unsatisfiable.</i>")
    set_default('output options', 'show human-readable id', True)
    set_default('output options', 'plugin repr', [])
    set_default('output options', 'header repr', 'standard')
    set_default('output options', 'footer repr', 'standard')
    set_default('output options', 'sep repr', {})
    set_default('history options', 'time format', '%Y/%m/%d %H:%M')
    set_default('overview options', 'public', True)
    set_default('overview options', 'type', ['raw', 'table'])
    set_default('main page options', 'title', '')
    set_default('main page options', 'description', "You are on the main page. Please provide your preferences on the user page, or/and consult the results page")
    set_default('solver options', 'engine', 'ASP/clingo')
    set_default('solver options', 'cli', [])
    set_default('solver options', 'path', 'clingo')
    set_default('solver options', 'constants', {})
    set_default('solver options', 'solving mode', 'default')
    set_default('meta', 'filesource', filesource)
    set_default('meta', 'save state', True)


    def set_rec_default(key, subkey, default_value):
        data.setdefault(key, {})
        assert isinstance(data[key], list), data[key]
        # apply the default on all expected subdicts
        for subdict in data[key]:
            subdict.setdefault(subkey, default_value)

    set_rec_default('choices options', 'default', 'all')
    set_rec_default('choices options', 'type', 'multiple')
    set_rec_default('choices options', 'description', "Please indicate your preferences here:")
    set_rec_default('choices options', 'choices', {})
    set_rec_default('choices options', 'ranks', {})
    set_rec_default('choices options', 'data atoms', ['user({user})', 'choice({choice})'])
    set_rec_default('choices options', 'produced atoms', ['ok({user},{choice})'])


    # assign uids to choices and users, if necessary
    gen_uid = map(str, itertools.count(1))
    if data["users options"]["type"] == 'restricted':
        if isinstance(data["users options"]["allowed"], str):
            data["users options"]["allowed"] = data["users options"]["allowed"].split(' ')
        if isinstance(data["users options"]["allowed"], (list, tuple, set, frozenset)):
            data["users options"]["allowed"] = {user: next(gen_uid) for user in data["users options"]["allowed"]}
    for chop in data["choices options"]:
        if chop["type"] in {'multiple users', 'single user'}:
            chop["choices"] = data["users options"]["allowed"]
            assert isinstance(data["users options"]["allowed"], dict)
        if isinstance(chop["choices"], str):
            chop["choices"] = chop["choices"].split(' ')
        if isinstance(chop["choices"], (list, tuple, set, frozenset)):
            chop["choices"] = {choice: next(gen_uid) for choice in chop["choices"]}

    # derivate values
    if data["global options"]["generated pages"] == 'all':
        data["global options"]["generated pages"] = ["user", "results", "overview", "history", "compilation", "configuration/raw", "configuration", 'reset']
    if data["global options"]["public pages"] is None:
        data["global options"]["public pages"] = data["global options"]["generated pages"]

    for chop in data["choices options"]:
        if chop["default"] == 'all':
            chop["default"] = list(chop["choices"].values())
        if chop["default"] is None or chop["default"] == 'none':
            chop["default"] = []
        chop['type repr'] = chop['type']  # if type is a range, this ensure to conserve programmatic and human representation
        if utils.is_human_repr_of_range(chop['type']):
            chop['type'] = utils.range_from_human_repr(chop['type'])


    # get encoding file if any, and add its content the to base encoding
    if data['global options']['base encoding file']:
        try:
            with open(data['global options']['base encoding file']) as fd:
                encoding = fd.read()
        except:
            pass  # ignore that, error detector will take care of raising errors
        else:
            if '%*' not in encoding:  # not multiline comment, we can remove all comments safely
                encoding = ' '.join(l.split('%')[0].strip() for l in encoding.splitlines(False))
            else:  # there is some multilines comments. Arf.
                pass  # nothing to do
            data['global options']['base encoding'] += ' ' + encoding
    if data['output options']['model header repr'] == 'standard':
        data['output options']['model header repr'] = [
            {"kind": "title", "index": True, "uid": True},
        ]
    if data['output options']['model footer repr'] == 'standard':
        data['output options']['model footer repr'] = [
            {"kind": "raw", "shows": "all" },
            {"kind": "table/2", "rows": "user", "columns": "choice", "source": "assoc/rows,columns"},
            {"kind": "copy2clipboard"},
        ]
    if data['output options']['header repr'] == 'standard':
        data['output options']['header repr'] = [{"kind": "text", "text": "{nb_models} models found in {compilation_runtime_repr}."}]
    if data['output options']['footer repr'] == 'standard':
        data['output options']['footer repr'] = [{"kind": "text", "text": "{('All solutions share '+str(len(common_atoms.atoms))+'atoms.') if common_atoms.atoms else 'There is no common atoms across solutions.'}"}]

    # fix types
    def str_to_list(key, subkey, splitter=' '):
        if isinstance(data[key][subkey], str):
            data[key][subkey] = data[key][subkey].split(splitter)
        assert isinstance(data[key][subkey], list)

    str_to_list("global options", "shows")
    str_to_list("solver options", "cli")


    def rec_str_to_list(key, subkey, splitter=' '):
        assert isinstance(data[key], list), data[key]
        for sub in data[key]:
            if isinstance(sub[subkey], str):
                sub[subkey] = sub[subkey].split(splitter)

    rec_str_to_list("choices options", "data atoms")
    rec_str_to_list("choices options", "produced atoms")


    # expand model repr, header repr and footer repr if necessary
    for repr_opt in ('model header repr', 'model repr', 'model footer repr', 'header repr', 'footer repr', 'plugin repr'):
        value = data['output options'][repr_opt]
        if isinstance(value, str):  # probably a plugin name, let's run the default
            value = [{'kind': value}]
        elif isinstance(value, dict) and len(value) == 0:  # it's an empty element, like empty list
            value = []
        elif isinstance(value, dict) and len(value) == 1 and next(iter(value)) == 'text':  # it's a text element, we can handle it
            value = [{'kind': 'text', 'text': value['text']}]
        elif isinstance(value, dict):  # only one element, let's put in a singleton list
            value = [value]
        elif isinstance(value, list):  # looks ok
            pass  # nothing to change
        else:
            pass  # this will be catched by errors detection
        data['output options'][repr_opt] = value

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
            return None, errors

    # setup solver global states
    import clyngor
    clyngor.CLINGO_BIN_PATH = data['solver options']['path']

    return data, raw_data  # looks ok


def errors_in_configuration(cfg: dict):
    errors = []  # list of all found errors
    base_keys = set(cfg.keys())

    # domain checking
    def ensure_in(key, subkey, ok_values, other_valid_values=set()):
        if (val := cfg[key][subkey]) not in ok_values:
            errors.append(f"{key} '{subkey}' is invalid: '{val}'. Accepted values are {', '.join(map(repr, set(ok_values)|set(other_valid_values)))}")

    ensure_in("users options", "type", {'restricted', 'valid-id', 'convertible'})
    ensure_in("global options", "compilation", {'direct access', 'specific access'})
    ensure_in("solver options", "engine", {'ASP/clingo'})
    ensure_in("solver options", "solving mode", {'optimals', 'default'})

    def rec_ensure_in(key, subkey, ok_values, other_valid_values=set()):
        for sub in cfg[key]:
            if (val := sub[subkey]) not in ok_values:
                errors.append(f"{key} '{subkey}' is invalid: '{val}'. Accepted values are {', '.join(map(repr, set(ok_values)|set(other_valid_values)))}")

    for chop in cfg["choices options"]:
        if isinstance(chop['type'], tuple) and len(chop['type']) == 2 and isinstance(chop['type'][0], (int, type(None))) and isinstance(chop['type'][1], (int, type(None))):
            pass
        else:  # if it's not a range, must be a string providing one
            rec_ensure_in("choices options", "type", {'single', 'multiple', 'independant ranking', 'single user', 'multiple users'}, {'at least|most <N>', 'less|more than <N>', 'between <N> and <K>'})


    # type checking
    def ensure_is(key, subkey, *types):
        if not isinstance((val := cfg[key][subkey]), tuple(types)):
            errors.append(f"{key} '{subkey}' is of invalid type: value {repr(val)} of type {type(val)}. Accepted types are {', '.join(map(repr, types))}")

    ensure_is('solver options', 'cli', list)
    ensure_is("meta", "save state", bool)
    ensure_is("output options", "show human-readable id", bool)
    ensure_is("output options", "model repr", list)
    ensure_is("output options", "header repr", list)
    ensure_is("output options", "footer repr", list)
    ensure_is('solver options', 'constants', dict)

    def rec_ensure_is(key, subkey, *types):
        for idx, sub in enumerate(cfg[key], start=1):
            if not isinstance((val := sub[subkey]), tuple(types)):
                errors.append(f"In the {idx}-th {key}, '{subkey}' is of invalid type: value {repr(val)} of type {type(val)}. Accepted types are {', '.join(map(repr, types))}")

    rec_ensure_is("choices options", "choices", list, dict)


    # dependencies checking
    for idx, chop in enumerate(cfg["choices options"], start=1):
        if chop["type"] in {'single user', 'multiple users'}:
            if cfg["users options"]["type"] != 'restricted':
                errors.append(f"In the {idx}-th choices option, choices type is user-related ({repr(chop['type'])}), but user type is {repr(cfg['users options']['type'])}, not the expected 'restricted'. (NB: choice of users in an undetermined set is not implemented)")


    # verify existence of the template and its content
    full_path = lambda p: os.path.join('templates/', cfg["global options"]["template"], p)
    if not os.path.exists(full_path('')):
        errors.append(f"Template directory {cfg['global options']['template']} wasn't found in templates/ directory")

    def ensure_file(name: str):
        if not os.path.exists(full_path(name)):
            errors.append(f"File {name} should have been found in templates/{cfg['global options']['template']}/, but does not exists.")

    ensure_file('index.html')
    ensure_file('user.html')
    ensure_file('user-choice.html')
    ensure_file('results.html')
    ensure_file('thanks.html')


    # check existence of encoding file, if any
    if cfg['global options']['base encoding file']:
        try:
            with open(cfg['global options']['base encoding file']):
                pass
        except Exception as err:
            errors.append(f"Base encoding file {cfg['global options']['base encoding file']} was provided, but couldn't be opened because of: {str(err)}")


    # verify repr model/header/footer are well-formed
    def verify_repr_rules(subkey: str):
        for rule in cfg['output options'][subkey]:
            if not isinstance(rule, dict):
                errors.append(f"Representation rule for {repr(subkey)} {repr(rule)} is not a dict, which is not expected")
            if 'kind' not in rule:
                errors.append(f"Representation rule for {repr(subkey)} {repr(rule)} doesn't provide a 'kind' key, which prevent us to detect what repr plugin to call.")
            elif rule['kind'] not in model_repr.names():
                errors.append(f"Representation rule for {repr(subkey)} {repr(rule)} ask a repr plugin of kind {repr(rule['kind'])}, which doesn't exists. Available plugins: {', '.join(model_repr.names())}")
    verify_repr_rules('model repr')
    verify_repr_rules('header repr')
    verify_repr_rules('footer repr')

    ... # TODO
    return errors

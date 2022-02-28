import utils
import itertools

def atoms_from_choices(cfg: dict, user_choices: dict) -> str:
    atoms_templates = cfg["choices options"]["produced atoms"]
    for template in atoms_templates:
        for user, choices in user_choices.items():
            for choice in choices:
                yield template.rstrip(".").format(user=user, choice=choice)+ '.'

def atoms_from_data(cfg: dict, user_choices: dict) -> [str]:
    # convert ranks to the values expected by ASP
    if cfg["choices options"]["ranks"]:
        ranks = [int(v) for v in cfg["choices options"]["ranks"].values() if not isinstance(v, bool)]
        absolute_ranks = ['yes' if v else 'no' for v in cfg["choices options"]["ranks"].values() if isinstance(v, bool)]

    for template in cfg["choices options"]["data atoms"]:
        valsets = {}
        if '{user}' in template:
            valsets['user'] = user_choices
        if '{choice}' in template:
            valsets['choice'] = cfg["choices options"]["choices"].values()
        if '{rank}' in template:
            valsets['rank'] = ranks
        if '{absolute_rank}' in template:
            valsets['absolute_rank'] = absolute_ranks
        if '{any_rank}' in template:
            valsets['any rank'] = ranks + absolute_ranks
        for values in itertools.product(*valsets.values()):
            yield template.rstrip(".").format(**dict(zip(valsets, values))) + '.'

def atoms_from_shows(cfg: dict) -> [str]:
    shows = cfg["global options"]["shows"]
    if shows:
        yield '#show.\n'
    for show in shows:
        yield f'#show {show.rstrip(".")}.'

def compute_encoding(cfg: dict, user_choices: dict) -> str:
    return cfg["global options"]["base encoding"] + ''.join(atoms_from_choices(cfg, user_choices)) + ''.join(atoms_from_shows(cfg)) + ''.join(set(atoms_from_data(cfg, user_choices)))

def solve_encoding(cfg: dict, user_choices: dict):
    encoding = compute_encoding(cfg, user_choices)
    return utils.call_ASP_solver(
        encoding,
        n=cfg["output options"]["max models"],
        sampling=cfg["output options"]["model selection"] == 'sampling',
        cli_options=cfg['solver options']['cli'],
        constants=cfg['solver options']['constants'],
        optimals_only=cfg['solver options']['solving mode'] == 'optimals',
    )

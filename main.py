"""Example of bakasp instance creation from python"""

import os
import argparse
from bakasp import create_app
from utils import create_sorry_app


def readable_file(path:str) -> str:
    """Argparse type, raising an error if given path is not pointing to a readable file"""
    if not os.path.isfile(path):
        raise argparse.ArgumentTypeError(f"No such file: {path}")
    # all testable files are here
    return path

def parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('configuration', nargs='?', type=readable_file, help='configuration to run', default='examples/choose-your-character.json')
    parser.add_argument('--admin-code', '-a', type=str, help='admin code, if any', default=None)
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_cli()
    cfg = args.configuration
    app = cfg and create_app(cfg, admin=args.admin_code) or create_sorry_app('No configuration found.')
    app.run(port=8080, debug=True)

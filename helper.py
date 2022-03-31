"""Simple script to perform things.

"""

import json
import argparse


def parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='operation', required=True)

    # add nouns
    parser_nouns = subs.add_parser('nouns', description='Add nouns to the set of nouns')
    parser_nouns.add_argument('words', nargs='+', type=str, help='nouns to add to the nouns file')

    # add adjectives
    parser_nouns = subs.add_parser('adjectives', description='Add adjectives to the set of nouns')
    parser_nouns.add_argument('words', nargs='+', type=str, help='adjectives to add to the adjectives file')

    # show a (random) combination
    parser_nouns = subs.add_parser('show', description='show the hash of given json object')
    parser_nouns.add_argument('objects', nargs='+', type=str, help='json objects to hash')

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_cli()
    if args.operation == 'add':
        if args.sub_operation == 'nouns'
            target = 'data/nouns.json'
            new_words = set(n.strip().title() for n in args.words)
        elif args.operation == 'adjectives':
            target = 'data/adjectives.json'
            new_words = set(n.strip().title() for n in args.words)

        with open(target) as fd:
            data = set(json.load(fd))

        commons = data & new_words
        new_list = data | new_words
        added = new_list - data

        if commons:
            print(f"{len(commons)} word{'s were' if len(commons) > 1 else ' was'} already here: {', '.join(commons)}")

        with open(target, 'w') as fd:
            json.dump(sorted(list(new_list)), fd, indent=4)

        if len(added) == 1:
            print(f"word {next(iter(added))} was added to {target}.")
        elif added:
            print(f"{len(added)} words were added to {target}.")
        else:
            print(f"No word added ().")

    elif args.operation == 'show':
        args.

"""Simple script to perform things.

"""

import json
import uuid
import argparse
import hashname


def parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    ops_subs = parser.add_subparsers(dest='operation', required=True)


    # add subparser
    parser_add = ops_subs.add_parser('add', description='Add elements in data')
    parser_add_subs = parser_add.add_subparsers(dest='sub_operation', required=True)

    # add nouns subsubparser
    parser_nouns = parser_add_subs.add_parser('nouns', description='Add nouns to the set of nouns')
    parser_nouns.add_argument('words', nargs='+', type=str, help='nouns to add to the nouns file')
    # add adjectives
    parser_adjs = parser_add_subs.add_parser('adjectives', description='Add adjectives to the set of nouns')
    parser_adjs.add_argument('words', nargs='+', type=str, help='adjectives to add to the adjectives file')


    # show the hashname of given json object
    parser_shw = ops_subs.add_parser('show', description='show the hash of given json objects')
    parser_shw.add_argument('objects', nargs='+', type=str, help='json objects to hash')

    # show the hashnames of multiple randomly created objects
    parser_lst = ops_subs.add_parser('list', description='Generate random objects, show their hashes')
    parser_lst.add_argument('number', nargs='?', type=int, help='number of objects to yield', default=10)
    parser_lst.add_argument('--print-only-stats', '-s', action='store_true', help="don't show all yielded elements, only the final collision stats")

    # run the collision tests on a large randomly generated dataset
    parser_tst = ops_subs.add_parser('test', description='Run a collision test for the hashname module')

    return parser.parse_args()


def run_collision_test(nb_hits=100000, from_obj=hashname.from_obj):
    """Run collision tests on hashname module"""
    import os
    import json
    import random
    from pprint import pprint
    from itertools import islice
    from collections import Counter, defaultdict

    new_obj = lambda: tuple(random.randint(1, 1000) for _ in range(random.randint(1, 10)))

    def all_hashes():
        for n in hashname.NOUNS:
            for a in hashname.ADJECTIVES:
                yield a + ' ' + n
    # collisions = {f'{a} {n}': 0 for n in NOUNS for a in ADJECTIVES}
    collisions = defaultdict(int)
    total = 0
    # existing = set()
    NB_HITS = nb_hits
    for _ in range(0, NB_HITS):
        new = from_obj(new_obj())
        if new in collisions:
            total += 1
        collisions[new] += 1
        # existing.add(new)
        print(f'\r{_+1} {total} / {len(collisions)}  ', end='', flush=True)
    print()
    NB_HASHES = len(hashname.NOUNS) * len(hashname.ADJECTIVES)
    HASHES = set(all_hashes())
    missing_hashes = HASHES - set({k for k, v in collisions.items() if v > 0})
    # collisions = {k: v for k, v in collisions.items() if v > 1}
    # pprint({k: v for k, v in collisions.items() if v > 1})
    print('NB != HASHES:', NB_HASHES)
    print('NB != COKEYS:', len(collisions))
    print('unseen hashs:', len(missing_hashes))
    print('  ->includes:', ', '.join(list(missing_hashes)[:10]))
    print('  ->includes:', ', '.join(sorted(missing_hashes)[:10]))

    print('         hits:', NB_HITS)
    print('  #collisions:', sum(collisions.values()))
    print('expected mean:', round(NB_HITS / NB_HASHES, 3))
    print('         mean:', round(sum(collisions.values()) / len(collisions), 3))
    print('          min:', min(collisions.values()))
    print('          max:', max(collisions.values()))

    if os.path.exists('data/unseens.json'):
        print('data/unseens.json loaded with previously missing hashes')
        with open('data/unseens.json') as fd:
            previous = set(json.load(fd))
        both = len(previous | missing_hashes)
        print('#prev:', len(previous))
        print('#miss:', len(missing_hashes))
        print('miss - prev:', len(missing_hashes - previous), f'({round(100*len(missing_hashes - previous) / both, 1)}%)')
        print('prev - miss:', len(previous - missing_hashes), f'({round(100*len(previous - missing_hashes) / both, 1)}%)')
        print('prev | miss:', len(previous | missing_hashes), f'({round(100*len(previous | missing_hashes) / both, 1)}%)')
        print('prev & miss:', len(previous & missing_hashes), f'({round(100*len(previous & missing_hashes) / both, 1)}%)')
        with open('data/unseens.json', 'w') as fd:
            fd.write(json.dumps(sorted(previous - missing_hashes)))
    else:
        with open('data/unseens.json', 'w') as fd:
            fd.write(json.dumps(sorted(missing_hashes)))
    print('data/unseens.json created with missing hashes')

    # NB: after running that routine around twenty times, i got 11 remaining unseen hashes:
    # Bloody Buffoon, Broken Hawk, Cool Gears, Cool Warrior, Fluffy Base, Fluffy Fog, Fluffy Winter, Godless Cavern, Godless Rose, Patient Misery, Tiny Dog


if __name__ == '__main__':
    args = parse_cli()
    if args.operation == 'add':
        if args.sub_operation == 'nouns':
            target = 'data/nouns.json'
            new_words = set(n.strip().title() for n in args.words)
        elif args.sub_operation == 'adjectives':
            target = 'data/adjectives.json'
            new_words = set(n.strip().title() for n in args.words)
        else:
            raise NotImplementedError(f"Add operation can't handle adding {args.sub_operation}.")

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
        for idx, obj in enumerate(args.objects, start=1):
            obj = json.loads(obj)
            print(f'{idx}:', hashname.from_obj(obj))

    elif args.operation == 'list':
        hashes = {}  # hash -> number of time it was found
        for _ in range(args.number):
            obj = str(uuid.uuid4())
            h = hashname.from_obj(obj)
            if not args.print_only_stats:
                print(f"{obj}: {h}")
            hashes.setdefault(h, 0)
            hashes[h] += 1
        # show collision stats
        collisions = {k: v for k, v in hashes.items() if v > 1}
        if collisions:
            nb_collisions = sum(collisions.values()) - len(collisions)
            collision_ratio = (nb_collisions) / args.number
            print('Collisions:', collisions)
            print(f"{nb_collisions} collisions found, for a total of {len(collisions)} hashes that were found at least twice.")
            for nb in range(1, max(collisions.values())+1):
                nbc = {k: v for k, v in hashes.items() if v == nb}
                print(f"\t{len(nbc)} hashes were found {nb} times.")
            print(f"Collision rate = {round(100 * collision_ratio, 1)}%")
        else:
            print(f"No collision found \o/")
    elif args.operation == 'test':
        run_collision_test()



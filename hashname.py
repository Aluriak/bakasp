"""Function allowing to obtain a human-readable name from an hashable object

This is performed by converting object to json,
converting that json as string, encode it to unicode and blake2b it.
The digest is then used to pick a noun and an adjective we hope unique,
and assembling the 2.

Lists of nouns and adjectives are taken from https://github.com/kmkingsbury/xcom-mission-name-generator/
and updated with other words i found relevant.

"""


import json
import hashlib
from utils import by_chunks

WORD_SIZE=6


def as_json_object(obj: object) -> object:

    if isinstance(obj, (int, float, str, bytes)):
        return obj
    elif isinstance(obj, tuple):  # keep order
        return list(map(as_json_object, obj))
    elif isinstance(obj, (list, set, frozenset)):
        return sorted(list(map(as_json_object, obj)))
    elif isinstance(obj, dict):
        return [(as_json_object(k), as_json_object(v)) for k, v in sorted(list(obj.items()))]
    else:
        raise ValueError(f"given object '{obj}' of type {type(obj)} can't be processed as stable object")

def as_bytes(data: dict or list) -> bytes:
    return json.dumps(data, sort_keys=True, indent=0).encode()


try:
    with open('data/adjectives.json') as fd:
        ADJECTIVES = json.loads(fd.read())
except:
    ADJECTIVES = ['blue', 'big', 'proofread', 'magnificent', 'yodelling', 'venomous', 'holy', 'pure', 'red', 'green', 'adoptive', 'secret', 'fluffy', 'seismic', 'merry', 'black', 'short', 'loud', 'broken', 'sunny', 'cold', 'hot', 'small', 'silent', 'flying', 'walking', 'soft', 'cool', 'ninja', 'singing', 'malevolant', 'firing', 'lowcost', 'good', 'real', 'bitter', 'anomalous', 'regular', 'simili', 'awesome', 'hungry', 'cloned', 'mounted', 'yellow', 'orange', 'violet', 'purple', 'grey', 'pink', 'deep', 'tormenting', 'back']
try:
    with open('data/nouns.json') as fd:
        NOUNS = json.loads(fd.read())
except:
    NOUNS = ['jean', 'horse', 'invasion', 'rock', 'nitrite', 'vessel', 'base', 'leaf', 'thief', 'atom', 'well', 'saint', 'purity', 'velvet', 'unicorn', 'santa', 'yodeler', 'micro', 'dragon', 'spouse', 'night', 'sun', 'tree', 'dog', 'polder', 'heart', 'bean', 'turtle', 'battery', 'archetype', 'trope', 'mustache', 'paper', 'pine', 'luck', 'shock', 'cat', 'eye', 'paw', 'course', 'computer', 'predator', 'bus', 'apple', 'jewelry', 'spice', 'wings', 'submarine', 'juice', 'garden', 'rain', 'nose', 'plane', 'number', 'watchtower', 'cube', 'window', 'burger', 'sheep', 'driver', 'ocean', 'book', 'mountain', 'dress', 'god', 'ritual', 'light', 'lantern', 'queen', 'bear', 'office', 'shield', 'waters', 'lead', 'cloud', 'roof', 'sunday', 'monday', 'scream', 'pepper']

def as_noun(nb: str) -> str:
    return NOUNS[int(''.join(nb)) % len(NOUNS)]

def as_adj(nb: str) -> str:
    return ADJECTIVES[int(''.join(nb)) % len(ADJECTIVES)]




def from_obj(obj: object, nb_chunks: int = 2, **kwargs) -> str:
    h = hashlib.blake2b(digest_size=nb_chunks*WORD_SIZE, usedforsecurity=False)
    h.update(as_bytes(as_json_object(obj)))
    final_h = ''.join(str(val).ljust(3, '0') for val in h.digest())
    return __from_hash(final_h, nb_chunks=nb_chunks, **kwargs)


def __from_hash(h: str, nb_chunks: int, joiner: str=' ', style=str.title) -> str:
    # while len(h) % nb_chunks:
        # h += '0'
    rest = len(h) % nb_chunks
    assert rest == 0, rest
    chunk_size = len(h) // nb_chunks

    if nb_chunks == 2:
        one, two = by_chunks(h, chunk_size)
        cmps = as_adj(one), as_noun(two)

    elif nb_chunks == 3:
        one, two, tee = by_chunks(h, chunk_size)
        cmps = as_adj(one), as_noun(two), as_adj(tee)

    return style(joiner.join(cmps))



def test_collision():
    import os
    import json
    import random
    from pprint import pprint
    from itertools import islice
    from collections import Counter, defaultdict
    new_obj = lambda: tuple(random.randint(1, 1000) for _ in range(random.randint(1, 10)))
    def all_hashes():
        for n in NOUNS:
            for a in ADJECTIVES:
                yield a + ' ' + n
    # collisions = {f'{a} {n}': 0 for n in NOUNS for a in ADJECTIVES}
    collisions = defaultdict(int)
    total = 0
    # existing = set()
    NB_HITS = 100000
    for _ in range(0, NB_HITS):
        new = from_obj(new_obj())
        if new in collisions:
            total += 1
        collisions[new] += 1
        # existing.add(new)
        print(f'\r{_} {total} / {len(collisions)}  ', end='', flush=True)
    print()
    NB_HASHES = len(NOUNS) * len(ADJECTIVES)
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
    print('data/unseens.json created with missing hashes')

    # NB: after running that routine around twenty times, i got 11 remaining unseen hashes:
    # Bloody Buffoon, Broken Hawk, Cool Gears, Cool Warrior, Fluffy Base, Fluffy Fog, Fluffy Winter, Godless Cavern, Godless Rose, Patient Misery, Tiny Dog

if __name__ == "__main__":

    import random
    new_obj = lambda: tuple(random.randint(1, 1000) for _ in range(random.randint(1, 10)))
    mean_of = lambda t: round(sum(t) / len(t), 3)
    # for _ in range(10):
    test_collision()

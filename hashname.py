"""Function allowing to obtain a human-readable name from an hashable object

This is performed by converting object to json,
converting that json as string, encode it to unicode and blake2b it.
The digest is then used to pick a noun and an adjective we hope unique,
and assembling the 2.

Lists of nouns and adjectives are taken from https://github.com/kmkingsbury/xcom-mission-name-generator/
and updated with other words i found relevant.

"""


import uuid
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



def get_random_hash() -> str:
    return from_obj(str(uuid.uuid4()))


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




if __name__ == "__main__":

    import random
    # for _ in range(10):
    run_collision_test()

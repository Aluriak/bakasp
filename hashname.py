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
import itertools
from utils import by_chunks


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


from collections import defaultdict
FOUND_NOUNS = defaultdict(int)
FOUND_ADJS = defaultdict(int)

def as_noun(nb: str, NOUNS=NOUNS) -> str:
    nb = int(''.join(nb))
    # print('NOUN:', nb, '->', nb % len(NOUNS))
    FOUND_NOUNS[nb % len(NOUNS)] += 1
    return NOUNS[nb % len(NOUNS)]

def as_adj(nb: str, ADJECTIVES=ADJECTIVES) -> str:
    nb = int(''.join(nb))
    # print('ADJC:', int(''.join(nb)), '->', int(''.join(nb)) % len(ADJECTIVES))
    FOUND_ADJS[nb % len(NOUNS)] += 1
    return ADJECTIVES[nb % len(ADJECTIVES)]



def get_random_hash() -> str:
    return from_obj(str(uuid.uuid4()))

def from_obj(obj: object, nb_chunks: int = 2, word_size: int = 6, **kwargs) -> str:
    h = hashlib.blake2b(digest_size=nb_chunks*word_size, usedforsecurity=False)
    h.update(as_bytes(as_json_object(obj)))
    final_h = ''.join(str(val).ljust(3, '0') for val in h.digest())
    # (each val of h.digest is a byte (0-255), hence .ljust it allows to always get 3 digits per val.)
    assert (len(final_h) / 3) == (nb_chunks * word_size), final_h
    return __from_hash(final_h, nb_chunks=nb_chunks, **kwargs)


def __from_hash(h: str, nb_chunks: int, joiner: str=' ', style=str.title) -> str:
    # while len(h) % nb_chunks:
        # h += '0'
    rest = len(h) % nb_chunks
    assert rest == 0, rest
    assert h.isnumeric(), h
    chunk_size = len(h) // nb_chunks
    structure = itertools.cycle([as_adj, as_noun])

    cmps = (adj_or_noun(chunk) for adj_or_noun, chunk in zip(structure, by_chunks(h, chunk_size)))
    # print('t:', tuple(adj_or_noun(chunk) for adj_or_noun, chunk in zip(structure, by_chunks(h, chunk_size))))

    return style(joiner.join(cmps))



def run_collision_test():
    from collections import Counter
    SIZE = 100000
    c = Counter(from_obj(i) for i in range(SIZE))
    collisions = {k: v for k, v in c.items() if v > 1}
    print(f'collision: occurences (of {SIZE})')
    for k, v in sorted(tuple(Counter(collisions.values()).items())):
        print(f'\t{k}: {v} ({round(v/SIZE*100, 2)}%)')

    print(f'Total number of collisions: {sum(collisions.values())} ({round(sum(collisions.values())/SIZE*100, 2)}% of {SIZE})')
    print(f'Number of different hashes: {len(NOUNS) * len(ADJECTIVES)} ({round(len(NOUNS) * len(ADJECTIVES) / SIZE * 100, 2)}% of {SIZE})')
    print(f'Theoretical minimal number of collisions: {max(0, SIZE - len(NOUNS) * len(ADJECTIVES))} ({max(0, SIZE - len(NOUNS) * len(ADJECTIVES)) / SIZE * 100}% of {SIZE})')

    print(f'Number of used nouns: {len(FOUND_NOUNS)} ({round(len(FOUND_NOUNS) / len(NOUNS) * 100, 2)}% of {len(NOUNS)})')
    print(f'Number of used adjectives: {len(FOUND_ADJS)} ({round(len(FOUND_ADJS) / len(ADJECTIVES) * 100, 2)}% of {len(ADJECTIVES)})')




    nouns, nouns_occs = zip(*sorted(list(FOUND_NOUNS.items())))
    adjs, adjs_occs = zip(*sorted(list(FOUND_ADJS.items())))


    import statistics as stats
    print(f'Nouns Occurences:   mean: {round(stats.mean(nouns_occs), 2)}')
    print(f'                  pstdev: {round(stats.pstdev(nouns_occs), 2)}')

    print(f'Adjcs Occurences:   mean: {round(stats.mean(adjs_occs), 2)}')
    print(f'                  pstdev: {round(stats.pstdev(adjs_occs), 2)}')



    import seaborn as sns
    from pandas import DataFrame as df
    import matplotlib.pyplot as plt


    data_nouns = df({'noun': nouns, 'occs': nouns_occs})
    data_adjs = df({'adj': adjs, 'occs': adjs_occs})
    ax = sns.relplot(data=data_nouns, x='noun', y="occs")
    ax.set(title='Nouns')
    ax = sns.catplot(data=data_nouns, y="occs", kind='violin')
    ax.set(title='Nouns')
    ax = sns.relplot(data=data_adjs, x='adj', y="occs")
    ax.set(title='Adjectives')
    ax = sns.catplot(data=data_adjs, y="occs", kind='violin')
    ax.set(title='Adjectives')
    plt.show()






if __name__ == "__main__":

    import random
    run_collision_test()

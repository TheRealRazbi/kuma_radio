"""Disk cache for the crawl, so a re-run after a parser change costs no requests.

The wikis are slow enough that a full build is 20+ minutes; iterating on the parsing with
that in the loop would be unbearable. Delete tools/.cache to force a refetch.
"""

import json
import os

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')


def cache(key, produce):
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, key + '.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    value = produce()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(value, f)
    return value

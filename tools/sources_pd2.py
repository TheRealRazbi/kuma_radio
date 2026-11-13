"""Payday 2: Jimmy's pager lines.

The Payday 2 wiki has no audio for the heisters' pager answers, so rip_payday2.py cuts them
out of a YouTube compilation into sounds/payday2/ and tools/payday2.json says what each one
says. This only reads that list; like Custom, every clip carries its own url, which is also
the link pasted in chat.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LIST = os.path.join(HERE, 'payday2.json')
SOUNDS = os.path.join(os.path.dirname(HERE), 'sounds', 'payday2')
PAGES = 'https://therealrazbi.github.io/kuma_radio/sounds/payday2/'


def build(cache):
    with open(LIST, encoding='utf-8') as f:
        items = json.load(f)
    rows = []
    for it in items:
        if not os.path.exists(os.path.join(SOUNDS, it['file'])):
            print('  ! not ripped yet: %s' % it['file'], flush=True)
            continue
        rows.append({'file': it['file'], 'group': 'Jimmy', 'skin': 'Sharlto Copley',
                     'cat': 'Pager', 'sub': '', 'text': it['said'],
                     'url': PAGES + it['file'], 'page': PAGES + it['file']})
    return rows

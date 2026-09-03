"""Warcraft III, from Wowpedia.

Wowpedia hosts three games' worth of sound, `Category:Warcraft III sound files` is empty,
and no article embeds any of these clips. What each file *does* have is a licence template on
its description page -- `{{Warcraft III}}`, versus `{{Warcraft II}}` on the older ones -- and
that settles which game a clip belongs to without guessing. Reading 2.6k of those pages is 53
requests, batched 50 at a time.

Structure then comes from the file names, which are the game's own and carry more than they
look like they do:

    ArcherPissed3.wav      unit response  -- <Unit><Response><n>
    A07Illidan13.mp3       campaign line  -- <campaign><chapter><speaker><n>

"Pissed" is Blizzard's name for the lines a unit says when you keep clicking it, which is
exactly the set most people are hunting for, so the response codes are translated into
something a person would search for and the original is kept alongside.

There is no transcript here. Nothing on the wiki pairs these clips with their words, so the
finder falls back to showing the file name, and searching WC3 means searching names.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_audio import load as load_audio                        # noqa: E402
from wiki import api, chunks                                      # noqa: E402

HOST = 'warcraft.fandom.com'

UNIT = re.compile(r"^(?P<unit>[A-Z][A-Za-z0-9'\-]*?)"
                  r"(?P<kind>YesAttack|Yes|What|Pissed|Warcry|Ready|Death|Taunt)"
                  r"(?P<n>\d*)(?P<alt>[A-Z]?)"
                  r"(?:_(?P<form>[A-Za-z]+))?"     # KelThuzadWhat1_Lich: one unit, two forms
                  r"\.(wav|mp3)$")

# A07Illidan13.mp3, D09BRexxar05.mp3 -- campaign letter, chapter number, optional variant
# letter, speaker, take number.
CAMPAIGN = re.compile(r"^(?P<map>[A-Z]\d{2}[A-Z]?)"
                      r"(?P<who>[A-Z][A-Za-z'\-]+?)"
                      r"(?P<n>\d+)(?P<alt>[A-Za-z]?)\.(wav|mp3)$")

# One-offs like GhoulDinner.wav and DryadWeakness1.wav follow no scheme, but they do start
# with a unit name the response files already taught us.
ABILITY = re.compile(r"^(?P<rest>.+?)(?P<n>\d*)\.(wav|mp3)$")

RESPONSE = {
    'What': 'Selected',
    'Yes': 'Ordered',
    'YesAttack': 'Ordered to attack',
    'Pissed': 'Annoyed (clicked too often)',
    'Warcry': 'War cry',
    'Ready': 'Trained',
    'Death': 'Death',
    'Taunt': 'Taunt',
}

# Campaign letters, read off the speakers in the files themselves rather than guessed:
# D06AThrall/D10Rexxar is Founding of Durotar, A07Illidan/A07Kael/A07LadyVashj is the blood
# elf campaign. The rest keep their raw code, which is still what the game calls them.
CAMPAIGN_NAME = {'D': 'Founding of Durotar', 'A': 'Curse of the Blood Elves',
                 'H': 'Human', 'O': 'Orc', 'U': 'Undead', 'N': 'Night Elf'}

WC3_LICENCE = re.compile(r'\{\{\s*Warcraft ?III\b', re.I)
SPACED = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')


def spaced(name):
    """MortarTeam -> Mortar Team. The game's names are camel case, people's aren't."""
    return SPACED.sub(' ', name)


def warcraft3(names):
    """The subset whose description page is licensed as Warcraft III."""
    keep = []
    for i, batch in enumerate(chunks(names, 50)):
        j = api(HOST, prop='revisions', rvprop='content', rvslots='main',
                titles='|'.join('File:' + n for n in batch))
        for p in j['query']['pages']:
            try:
                text = p['revisions'][0]['slots']['main']['content']
            except (KeyError, IndexError):
                continue
            if WC3_LICENCE.search(text):
                keep.append(p['title'].split(':', 1)[1].replace(' ', '_'))
        if i % 10 == 0:
            print('  licences %d/%d' % (i * 50, len(names)), flush=True)
    return keep


def build(cache):
    names = [a['name'] for a in load_audio(HOST)]
    print('  %d audio files on the wiki' % len(names), flush=True)
    mine = cache('wc3-licensed', lambda: warcraft3(names))
    print('  %d licensed as Warcraft III' % len(mine), flush=True)

    units = sorted({UNIT.match(n).group('unit') for n in mine if UNIT.match(n)},
                   key=len, reverse=True)         # longest first: HeroDemonHunter before Hero

    rows = []
    for name in mine:
        m = UNIT.match(name)
        if m:
            rows.append({'file': name, 'group': spaced(m.group('unit')),
                         'skin': 'Unit sounds',
                         'cat': RESPONSE[m.group('kind')],
                         'sub': ' '.join(filter(None, [m.group('form'),
                                                       m.group('kind') + m.group('n')])),
                         'text': ''})
            continue
        m = CAMPAIGN.match(name)
        if m:
            code = m.group('map')
            rows.append({'file': name, 'group': spaced(m.group('who')),
                         'skin': CAMPAIGN_NAME.get(code[0], 'Campaign'),
                         'cat': 'Campaign dialogue', 'sub': code, 'text': ''})
            continue
        owner = next((u for u in units if name.startswith(u)), None)
        m = ABILITY.match(name)
        if owner and m:
            rows.append({'file': name, 'group': spaced(owner), 'skin': 'Unit sounds',
                         'cat': 'Ability and one-offs',
                         'sub': spaced(m.group('rest')[len(owner):]).strip(), 'text': ''})
            continue
        # licensed as Warcraft III but named in some other scheme -- real audio, just
        # nothing here to group it by
        rows.append({'file': name, 'group': 'Unsorted', 'skin': 'Other',
                     'cat': '', 'sub': '', 'text': ''})
    return rows

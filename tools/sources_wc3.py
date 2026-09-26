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

The words come from the Quotes of Warcraft III pages, which tag each line with its file in a
tag of the wiki's own -- one tag per form when a line is shared:

    *You called? <ab>KelThuzadWhat1 Lich.wav</ab><ab>KelThuzadWhat1 Necro.wav</ab>
    *Poke poke poke - is that all you do? <ab>GruntPissed3.wav</ab> (The poking jokes...)

That covers every unit and hero, about 2,060 clips, and the note after the tag is trivia, not
speech. The rest -- campaign dialogue, Furion, the morphed Demon Hunter, a few deaths and
taunts -- are on no page at all, so they were run through speech recognition once
(transcribe_wc3.py) and the result is committed as wc3_heard.json. Where one of those is a
line the wiki does spell out elsewhere, the wiki's spelling wins; see heard_text().
"""

import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_audio import load as load_audio                        # noqa: E402
from wiki import api, chunks                                      # noqa: E402
from wikitext import clean                                         # noqa: E402

HOST = 'warcraft.fandom.com'
HEARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wc3_heard.json')

QUOTE_PAGES = ['Quotes of Warcraft III/' + p for p in
               ['Human Alliance', 'Orc Horde', 'Undead Scourge', 'Night Elf Sentinels',
                'Neutral', 'Neutral Heroes']]
AB = re.compile(r'<ab>(.*?)</ab>')

# Units recorded under two names. Furion is the campaign's Malfurion, and the morphed Demon
# Hunter is the Demon Hunter's own lines in the demon voice; the quote pages only list the
# second name, so FurionYes2.wav borrows the words of MalfurionYes2.wav.
SAME_LINES = {'Furion': 'Malfurion', 'DemonHunterMorphed': 'HeroDemonHunter'}

# Whisper's own estimate that a clip holds no speech. It is what separates a noise from a line:
# a ghoul eating comes back as "TINA!" at 0.53, and a grunt as the credit line of the subtitles
# it was trained on at 0.89. The margin is thin -- FurionYes1's real "For Kalimdor" scores 0.43
# -- so check the top of that column after a rerun of transcribe_wc3.py.
NO_SPEECH = 0.5
# how close a heard line has to be to a line on the quote pages to take the wiki's spelling:
# "For King Terranus" is UtherWarcry1's "For King Terenas!", "Anodorini Tala" is Anu'dorini Talah
SNAP = 0.8

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


def quotes():
    """{file name: words} from the Quotes of Warcraft III pages. One request."""
    j = api(HOST, prop='revisions', rvprop='content', rvslots='main',
            titles='|'.join(QUOTE_PAGES))
    said = {}
    for p in j['query']['pages']:
        for line in p['revisions'][0]['slots']['main']['content'].split('\n'):
            if '<ab>' not in line:
                continue
            text = clean(line[:line.index('<ab>')].lstrip('*:# '))
            for f in AB.findall(line):
                said[f.strip().replace(' ', '_')] = text
    return said


def _plain(s):
    return ' '.join(re.sub(r"[^a-z0-9' ]", ' ', s.lower().replace('-', ' ')).split())


def heard_text(name, heard, said):
    """The words for a clip no quote page tags, or ''."""
    m = UNIT.match(name)
    if m and m.group('unit') in SAME_LINES:
        twin = SAME_LINES[m.group('unit')] + name[len(m.group('unit')):]
        if said.get(twin):
            return said[twin]
    h = heard.get(name)
    if not h or h['nospeech'] >= NO_SPEECH or not h['text']:
        return ''
    text = h['text']
    if text.isupper():                          # shouted lines come back in capitals
        text = text.capitalize()
    plain = _plain(text)
    best = max(said.values(), default='',
               key=lambda q: difflib.SequenceMatcher(None, plain, _plain(q)).ratio())
    if best and difflib.SequenceMatcher(None, plain, _plain(best)).ratio() >= SNAP:
        return best
    return text


def build(cache):
    names = [a['name'] for a in load_audio(HOST)]
    print('  %d audio files on the wiki' % len(names), flush=True)
    mine = cache('wc3-licensed', lambda: warcraft3(names))
    print('  %d licensed as Warcraft III' % len(mine), flush=True)

    units = sorted({UNIT.match(n).group('unit') for n in mine if UNIT.match(n)},
                   key=len, reverse=True)         # longest first: HeroDemonHunter before Hero

    said = cache('wc3-quotes', quotes)
    heard = {}
    if os.path.exists(HEARD):
        with open(HEARD, encoding='utf-8') as f:
            heard = json.load(f)
    text = {n: said.get(n) or heard_text(n, heard, said) for n in mine}
    print('  %d with words from the quote pages, %d more by ear'
          % (sum(n in said for n in mine), sum(bool(text[n]) and n not in said for n in mine)),
          flush=True)
    # words that are only Whisper's say so in the meta line, next to the file's own code
    quoted = set(said.values())
    ear = {n for n in mine if text[n] and text[n] not in quoted}

    def sub(s, name):
        return ' \u00b7 '.join(filter(None, [s, 'by ear' if name in ear else '']))

    rows = []
    for name in mine:
        m = UNIT.match(name)
        if m:
            rows.append({'file': name, 'group': spaced(m.group('unit')),
                         'skin': 'Unit sounds',
                         'cat': RESPONSE[m.group('kind')],
                         'sub': sub(' '.join(filter(None, [m.group('form'),
                                                           m.group('kind') + m.group('n')])),
                                    name),
                         'text': text[name]})
            continue
        m = CAMPAIGN.match(name)
        if m:
            code = m.group('map')
            rows.append({'file': name, 'group': spaced(m.group('who')),
                         'skin': CAMPAIGN_NAME.get(code[0], 'Campaign'),
                         'cat': 'Campaign dialogue', 'sub': sub(code, name),
                         'text': text[name]})
            continue
        owner = next((u for u in units if name.startswith(u)), None)
        m = ABILITY.match(name)
        if owner and m:
            rows.append({'file': name, 'group': spaced(owner), 'skin': 'Unit sounds',
                         'cat': 'Ability and one-offs',
                         'sub': sub(spaced(m.group('rest')[len(owner):]).strip(), name),
                         'text': text[name]})
            continue
        # licensed as Warcraft III but named in some other scheme -- real audio, just
        # nothing here to group it by
        rows.append({'file': name, 'group': 'Unsorted', 'skin': 'Other',
                     'cat': '', 'sub': sub('', name), 'text': text[name]})
    return rows

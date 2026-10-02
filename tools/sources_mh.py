"""Mordhau, from the Mordhau wiki.

Each voice set has a page, "Barbarian (Voice)", listing its lines by the voice command that
says them, with the clips next to the words:

    ===Charge===
    *Charge! [[File:BarbarianVP charge1.wav]]
    *Help! [[File:help1.WAV]] [[File:help4.WAV]]

The wiki is not one hand's work, so the same list comes in three other shapes too: a
'''Charge''' bold line in place of a heading, === '''Yes''' === with both, and the Irish
page's clip on its own line above the bullet it belongs to:

    [[File:SW_Irish_Yes_01.WAV|150px]]
    * "Aye!"

The pages are the voices in Category:Voices. Six of the fourteen (Knight, Plain, Raider,
Slavic, Spanish, Young) list their words with no clips at all, so they add nothing here
until someone uploads them; a page that gains clips is picked up on the next rebuild.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_audio import AUDIO, load as load_audio                  # noqa: E402
from wiki import api, chunks                                       # noqa: E402
from wikitext import clean, unquote                                # noqa: E402

HOST = 'mordhau.fandom.com'

HEADING = re.compile(r'^(={1,6})\s*(.+?)\s*\1\s*$')
BOLD = re.compile(r"^'''(.+?)'''\s*$")
FILE = re.compile(r'\[\[\s*(?:File|Image)\s*:\s*([^|\]]+?)\s*(?:\|[^\]]*)?\]\]', re.I)
ACTOR = re.compile(r'voiced by (?:voice actor )?\[\S+ ([^\]]+)\]', re.I)
VOICE = re.compile(r'\s*\(Voice\)$')

# The commands as the game's voice wheel names them; the pages spell some of them their own
# way, and a category box offering both Friendly and Friendlies helps nobody.
COMMAND = {'friendlies': 'Friendly', 'follow me': 'Follow Me'}

# Where the page and the clip disagree, checked by ear. The Irish page links Thanks_04 under
# four lines in a row, a copy-paste slip that leaves 05 to 07 on no page; they are those
# lines, in order. Cruel's retreat9 is listed under "Fall back!" and says "Retreat!".
# file -> (page, command, words, note)
FIXES = {
    'SW_Irish_Thanks_05.WAV': ('Irish (Voice)', 'Thanks',
                               "Thank you, I'm truly grateful to ya!", ''),
    'SW_Irish_Thanks_06.WAV': ('Irish (Voice)', 'Thanks', "That's very kind of ya!", ''),
    'SW_Irish_Thanks_07.WAV': ('Irish (Voice)', 'Thanks', 'Yer too kind!', ''),
    'Retreat9.WAV': ('Cruel (Voice)', 'Retreat', 'Retreat!', 'by ear'),
}


def voices():
    j = api(HOST, list='categorymembers', cmtitle='Category:Voices', cmlimit='max',
            cmnamespace=0)
    return [p['title'] for p in j['query']['categorymembers'] if VOICE.search(p['title'])]


def wikitexts(titles):
    out = {}
    for batch in chunks(sorted(titles), 50):
        j = api(HOST, prop='revisions', rvprop='content', rvslots='main', titles='|'.join(batch))
        for p in j['query']['pages']:
            try:
                out[p['title']] = p['revisions'][0]['slots']['main']['content']
            except (KeyError, IndexError):
                continue
    return out


def file_name(f):
    """The name as the wiki stores it: underscores, and a capital first letter, which is
    what [[File:charge3.WAV]] on the Cruel page actually links to."""
    f = f.strip().replace(' ', '_')
    return f[:1].upper() + f[1:]


def command(s):
    s = clean(s)
    return COMMAND.get(s.lower(), s[:1].upper() + s[1:])


def said(line):
    s = clean(FILE.sub('', line).lstrip('*:# '))
    s = unquote(s)
    # the Irish page leaves a few quotes open at one end: * "Who in the name of Jesus are you?
    if s.count('"') == 1:
        s = s.strip('"').strip()
    return s


def parse(text):
    """-> {file: (command, words)} for every clip on a voice page."""
    found, cat, waiting = {}, '', []
    for line in text.split('\n'):
        line = line.strip()
        h = HEADING.match(line) or BOLD.match(line)
        if h:
            name = command(h.group(h.lastindex))
            if name.lower() != 'voice lines':
                cat, waiting = name, []
            continue
        files = [file_name(f) for f in FILE.findall(line) if AUDIO.search(f.strip())]
        words = said(line) if line.startswith('*') else ''
        if files and not words:
            waiting += files                  # the Irish shape: the words are on the next line
            continue
        for f in waiting + files:
            found.setdefault(f, (cat, words))
        if words:
            waiting = []
    return found


def actor(text):
    m = ACTOR.search(text)
    return m.group(1).strip() if m else ''


def build(cache):
    text = cache('mh-wikitext', lambda: wikitexts(voices()))
    rows = {f: {'group': VOICE.sub('', page), 'skin': actor(text.get(page, '')),
                'cat': cat, 'sub': note, 'text': words}
            for f, (page, cat, words, note) in FIXES.items()}
    for title, t in sorted(text.items()):
        for f, (cat, words) in parse(t).items():
            rows.setdefault(f, {'group': VOICE.sub('', title), 'skin': actor(t),
                                'cat': cat, 'sub': '', 'text': words})

    names = {file_name(a['name']) for a in load_audio(HOST)}
    for f in sorted(names - set(rows)):
        print('  ! %s is on no voice page' % f, flush=True)
    return [dict(r, file=f) for f, r in rows.items()]

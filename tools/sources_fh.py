"""For Honor, from the For Honor wiki.

The wiki hosts hardly any audio -- 37 files, where the game has thousands of voiced lines, and
the language wikis have none at all -- so this is a small source read three ways.

Hero lines embedded in a hero's ==Quotes== section, the words and their translation on the
bullet and the move that says them under it:

    *'''Latin''': "Tenebris!"- '''English''': "(For) Darkness!"[[File:Tenebris.mp3|thumb]]
    **Tenebris Rising

Only Black Prior has any so far. The pages are found from the files rather than the other way
round, so a hero page that gains a clip is picked up without a change here.

1Apollyon.mp3 to 30Apollyon.mp3, her taunts from the campaign's boss fight, are embedded
nowhere. Her article lists her voice lines as plain bullets, in the order of the file numbers
-- checked by ear, all 30 -- so the Nth bullet is the words of NApollyon.mp3.

And a few that no page mentions at all, in LOOSE.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_audio import load as load_audio                         # noqa: E402
from wiki import api, chunks                                       # noqa: E402
from wikitext import clean, unquote                                # noqa: E402

HOST = 'forhonor.fandom.com'

HEADING = re.compile(r'^(={2,6})\s*(.+?)\s*\1\s*$')
FACTION = re.compile(r'\|\s*faction\s*=\s*\[\[([^\]|]+)')
# the '''Latin''': and '''English: ''' labels a quote bullet puts before each language
LABEL = re.compile(r"'''[^']*'''\s*:?")
FILE = re.compile(r'\[\[\s*File\s*:\s*([^|\]]+\.(?:mp3|ogg|wav))[^\]]*\]\]', re.I)

APOLLYON = 'Apollyon'
NUMBERED = re.compile(r'^(\d+)Apollyon\.mp3$')
# the Apollyon article capitalises its pronouns mid-sentence: "Kill me... If You can..."
SHOUTED = re.compile(r'(?<=[a-z,.] )(You|Your|Yourself|It)\b')

# file -> (page it belongs to, category, words, note); the page gives the character and faction.
# Kyoshin's two are the opening of The Tale of the Heike, recited; no page says so, but the
# passage is well known and the recording is word for word.
LOOSE = {
    'Kyoshin_voice_clip_1.ogg': (
        'Kyoshin/Main', 'The Tale of the Heike',
        '祇園精舎の鐘の声、諸行無常の響きあり。娑羅双樹の花の色、盛者必衰の理をあらはす。'
        ' — Gion shōja no kane no koe, shogyō mujō no hibiki ari. Sara sōju no hana no iro,'
        ' jōsha hissui no kotowari wo arawasu.', 'by ear'),
    'Kyoshin_voice_clip_2.ogg': (
        'Kyoshin/Main', 'The Tale of the Heike',
        '驕れる人も久しからず、ただ春の夜の夢のごとし。猛き者もつひには滅びぬ、ひとへに風の前の塵に同じ。'
        ' — Ogoreru hito mo hisashikarazu, tada haru no yo no yume no gotoshi. Takeki mono mo'
        ' tsui ni wa horobinu, hitoe ni kaze no mae no chiri ni onaji.', 'by ear'),
    'Apollyon_Death_sounds.wav': (APOLLYON, 'Death sounds', '', ''),
}


def under(name):
    return name.replace(' ', '_')


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


def pages():
    """Every page that embeds an audio file, plus the ones read for the files nothing embeds."""
    used = set()
    names = [a['name'] for a in load_audio(HOST)]
    for batch in chunks(names, 50):
        j = api(HOST, prop='fileusage', fulimit='max', titles='|'.join('File:' + n for n in batch))
        for p in j['query']['pages']:
            used.update(u['title'] for u in p.get('fileusage', []))
    return wikitexts(used | {APOLLYON} | {page for page, *_ in LOOSE.values()})


def character(title):
    return title[:-len('/Main')] if title.endswith('/Main') else title


def faction(text):
    m = FACTION.search(text)
    return m.group(1).strip() if m else ''


def said(line):
    """'Tenebris! — (For) Darkness!' from a bullet giving the words and their translation."""
    parts = [unquote(clean(p).strip(' -')) for p in LABEL.split(FILE.sub('', line.lstrip('*')))]
    return ' — '.join(dict.fromkeys(p for p in parts if p))


def embedded(title, text):
    """-> {file: row} for each [[File:...]] on a quote bullet of this page."""
    rows, lines = {}, text.split('\n')
    for i, line in enumerate(lines):
        for f in FILE.findall(line):
            # the move is the sub-bullet under the line, when there is one
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
            move = clean(nxt.lstrip('*').strip()) if nxt.startswith('**') else ''
            rows[under(f.strip())] = {'group': character(title), 'skin': faction(text),
                                      'cat': move or 'Quotes', 'sub': '', 'text': said(line)}
    return rows


def voicelines(text):
    """The bullets of the Apollyon article's voice line section, in order."""
    out, inside = [], False
    for line in text.split('\n'):
        h = HEADING.match(line.strip())
        if h:
            inside = 'voiceline' in h.group(2).lower()
            continue
        if inside and line.startswith('*'):
            s = clean(line.lstrip('*')).replace('´', "'")
            out.append(SHOUTED.sub(lambda m: m.group(1).lower(), s))
    return out


def build(cache):
    text = cache('fh-wikitext', pages)
    rows = {}
    for title, t in text.items():
        for f, r in embedded(title, t).items():
            rows.setdefault(f, r)

    names = {under(a['name']) for a in load_audio(HOST)}
    numbered = sorted((int(m.group(1)), n) for n in names for m in [NUMBERED.match(n)] if m)
    lines = voicelines(text.get(APOLLYON, ''))
    if len(lines) != len(numbered):
        # the pairing is by position, so a list that has grown or shrunk pairs nothing
        print('  ! %d Apollyon files but %d voice lines -- left without words'
              % (len(numbered), len(lines)), flush=True)
        lines = [''] * len(numbered)
    for (_, f), words in zip(numbered, lines):
        rows.setdefault(f, {'group': APOLLYON, 'skin': faction(text.get(APOLLYON, '')),
                            'cat': 'Boss fight', 'sub': '', 'text': words})

    for f, (page, cat, words, note) in LOOSE.items():
        rows.setdefault(f, {'group': character(page), 'skin': faction(text.get(page, '')),
                            'cat': cat, 'sub': note, 'text': words})

    for f in sorted(names - set(rows)):
        print('  ! %s is on no page read here' % f, flush=True)
    return [dict(r, file=f) for f, r in rows.items()]

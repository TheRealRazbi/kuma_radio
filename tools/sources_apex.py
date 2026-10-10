"""Apex Legends, from the Apex Legends wiki.

Each legend has a "<Legend>/Voice lines" page, sorted by section -- Character Select, Intro,
Kills, Gameplay, Pings, Quip and so on -- with the situation that sets a line off on a ;
line, or a '''bold''' one, under the section, and the clip in an <sm2> tag beside the words:

    == Gameplay ==
    ; Another Squad attacking
    * <sm2>diag_mp_bloodhound_bc_anotherSquadAttackingUs_01_01_1p.wav</sm2> "..."

Intro and kill quips are cosmetics, so they come wrapped in their rarity instead,
{{Rare|"Remember me, friends. I may kill you."}}, and that stands in for the situation. A line
said only to one legend opens with a note naming them, [To {{Symbol|Ash}}] "...", kept as
[To Ash]; the other {{Symbol}} icons, events like Fight or Fright, are dropped.

Most of the lines are listed with no clip at all -- the wiki hosts a few hundred against the
game's tens of thousands -- so this is the legends someone uploaded clips for, Bloodhound,
Axle, Fuse, Mirage, Bangalore and Wraith above all. The pages are found from the files
rather than the other way round, so a voice page that gains clips is picked up on the next
rebuild. Two of Bloodhound's Trials clips are on the Trials page and not on his, so that
page is read too. The wiki moved to apexlegends.wiki.gg in 2023; the Fandom copy it left
behind has the same pages and more of the clips (555 to 452), and is the one the app's CDN
scheme fits.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_audio import load as load_audio                         # noqa: E402
from wiki import api, chunks                                       # noqa: E402
from wikitext import clean, unquote                                # noqa: E402

HOST = 'apexlegends.fandom.com'

HEADING = re.compile(r'^(={2,6})\s*(.+?)\s*\1')
SITUATION = re.compile(r"^(?:;\s*(.+?)|'''(.+?)''')\s*$")
SM2 = re.compile(r'<sm2>\s*(.+?)\s*</sm2>', re.I)
RARITY = re.compile(r'\{\{\s*(Common|Rare|Epic|Legendary)\s*\|', re.I)
CLASS = re.compile(r'^\|\s*class\s*=\s*([^<\n]+)', re.M)
COMMENT = re.compile(r'<!--.*?-->', re.S)
VOICE_LINES = re.compile(r'^(.+)/Voice lines$', re.I)
# [[File: Loba Icon.svg|22px|link=Loba]] in a note: the legend it is said to
ICON = re.compile(r'\[\[\s*File\s*:[^\[\]]*?\blink=([^\]|]+)\]\]', re.I)
SYMBOL = re.compile(r'\{\{\s*symbol\s*\|[^{}]*\}\}', re.I)
# a leading [note], which may hold a [[File:]] icon or a {{Symbol}}
LEAD = re.compile(r'^(\[(?:[^\[\]]|\[\[[^\[\]]*\]\])*\])\s*:?\s*(.*)$', re.S)

# the pages call the same section by more than one name
SECTION = {'character selection': 'Character Select', 'intro': 'Intro Quip',
           'kills': 'Kill Quip'}

# page -> (legend, section), for the pages besides the voice pages that a clip is only on.
# Their clips sit in a table, the thing examined in one cell and the words in the next.
EXTRA = {"Bloodhound's Trials": ('Bloodhound', 'Trials')}


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
    """Every voice-lines page that embeds an audio file, the legend pages they belong to, and
    EXTRA. Other pages quote a clip or two -- the Indonesian Wraith/id, Town Takeover -- but
    always one of these has it too."""
    used = set()
    names = [a['name'] for a in load_audio(HOST)]
    for batch in chunks(names, 50):
        j = api(HOST, prop='fileusage', fulimit='max', titles='|'.join('File:' + n for n in batch))
        for p in j['query']['pages']:
            used.update(u['title'] for u in p.get('fileusage', []) if VOICE_LINES.match(u['title']))
    legends = {VOICE_LINES.match(t).group(1) for t in used}
    return wikitexts(used | legends | set(EXTRA))


def file_name(f):
    """<sm2>Diag mp caustic menu selectReady 01 01 3p.wav</sm2> and the lowercase
    <sm2>diag_mp_...</sm2> are both the wiki's Diag_mp_... file."""
    f = f.strip().replace(' ', '_')
    return f[:1].upper() + f[1:]


def said(line):
    """'[To Ash] Yes, I know.' from * <sm2>...</sm2> [To {{Symbol|Ash}}] "Yes, I know." """
    s = SM2.sub(' ', line).strip().lstrip('*:# ')
    notes = []
    m = LEAD.match(s)
    if m:
        notes.append(clean(ICON.sub(lambda i: i.group(1).strip(), m.group(1))))
        s = m.group(2)
    s = clean(SYMBOL.sub('', s)).replace('“', '"').replace('”', '"')
    m = LEAD.match(s)                  # {{Common|[hyped up] "..."}} puts it inside the rarity
    if m:
        notes.append(m.group(1))
        s = m.group(2)
    s = unquote(s)
    # Crypto's "끝내버리자. is left open at the front
    if s.count('"') == 1:
        s = s.strip('"').strip()
    s = re.sub(r'\s+([.,!?])', r'\1', s)     # The {{Texttip|óséður|...}} . The promise
    return ' '.join(notes + [s]).strip()


def section(s):
    s = clean(s)
    return SECTION.get(s.lower(), s)


def parse(text):
    """-> {file: (section, situation, words)} for every clip on a voice page."""
    found, cat, sit = {}, '', ''
    for line in COMMENT.sub('', text).split('\n'):
        line = line.strip()
        h = HEADING.match(line)
        if h:
            if len(h.group(1)) == 2:
                cat, sit = section(h.group(2)), ''
            else:
                sit = clean(h.group(2))          # === Ranked === under == Lobby ==
            continue
        s = SITUATION.match(line)
        if s:
            sit = clean(s.group(s.lastindex))
            continue
        files = SM2.findall(line)
        if not files:
            continue
        rarity = RARITY.search(line)
        sub = sit or (rarity.group(1).capitalize() if rarity else '')
        for f in files:
            found.setdefault(file_name(f), (cat, sub, said(line)))
    return found


def extra(text, cat):
    """-> {file: (section, situation, words)} for the table rows of a page in EXTRA."""
    found = {}
    for line in text.split('\n'):
        files = SM2.findall(line)
        if not files or '||' not in line:
            continue
        thing, words = line.lstrip('|').rsplit('||', 1)
        for f in files:
            found.setdefault(file_name(f), (cat, 'Examining ' + clean(thing), said(words)))
    return found


def legend_class(text):
    m = CLASS.search(text or '')
    return clean(m.group(1)) if m else ''


def build(cache):
    text = cache('apex-wikitext', pages)
    rows = {}
    for title, t in sorted(text.items()):
        m = VOICE_LINES.match(title)
        if not m:
            continue
        legend = m.group(1)
        for f, (cat, sub, words) in parse(t).items():
            rows.setdefault(f, {'group': legend, 'skin': legend_class(text.get(legend)),
                                'cat': cat, 'sub': sub, 'text': words})

    for title, (legend, cat) in EXTRA.items():
        for f, (cat, sub, words) in extra(text.get(title, ''), cat).items():
            rows.setdefault(f, {'group': legend, 'skin': legend_class(text.get(legend)),
                                'cat': cat, 'sub': sub, 'text': words})

    names = {a['name'] for a in load_audio(HOST)}
    for f in sorted(names - set(rows)):
        print('  ! %s is on no voice page' % f, flush=True)
    return [dict(r, file=f) for f, r in rows.items()]

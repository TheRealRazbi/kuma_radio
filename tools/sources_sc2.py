"""StarCraft II, from the StarCraft wiki.

Every voiced line with a clip is on one of three pages, StarCraft II unit quotations/Protoss,
/Terran and /Zerg. The pages themselves are just headings; each unit's lines live in a
template of their own that the page transcludes:

    ====[[Zealot (StarCraft II)|Zealot]]====
    {{QuotesSC2Zealot}}

and that template is a {{UnitQuoteBox}} whose parameters are the response types, one clip
and its words per bullet:

    {{UnitQuoteBox
    |select=*{{sm2|Zealot_What00.ogg|My meditation is over.}}
    |witty=*{{sm2|Zealot_Pissed00.ogg|I am [[Templar Caste|Templar]]! I am the sword of truth!}}

So a unit is its level-4 heading, the category is the parameter, and the words come with the
clip. The campaign and Co-op quotation pages are transcripts with no clips on them, and the
StarCraft 1 files on the wiki are the other game, so neither is read.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki import api, chunks                                       # noqa: E402
from wikitext import clean, unquote                                # noqa: E402

HOST = 'starcraft.fandom.com'
RACES = ['Protoss', 'Terran', 'Zerg']
PAGE = 'StarCraft II unit quotations/'

HEADING = re.compile(r'^(={2,6})\s*(.+?)\s*\1\s*$')
# "Versus Units", "Campaign and Co-op Missions Units", "Heroes" -- kept without the tail
MODE = re.compile(r'^(Versus|Campaign and Co-op|Heroes)\b(?: Missions)?(?: Units)?$')
TRANSCLUDE = re.compile(r'^\{\{\s*(Quotes[^|{}\n]+?)\s*\}\}\s*$')
SM2 = re.compile(r'\{\{\s*sm2\s*\|')
PARAM = re.compile(r'^\|\s*([a-z]+)\s*=(.*)$')
# {{link|High templar|SC2|High Templar}}: the display text is the third argument when there
# is one, and the article name otherwise -- not the first-argument guess clean() makes
LINK = re.compile(r'\{\{\s*link\s*\|([^{}|]*)\|[^{}|]*(?:\|([^{}|]*))?\}\}', re.I)

# the headings {{UnitQuoteBox}} puts over each parameter
CATEGORY = {
    'arrive': 'Trained', 'hurt': 'When attacked', 'select': 'Selected',
    'move': 'Move order', 'attack': 'Attack order', 'confirm': 'Confirming order',
    'witty': 'Repeatedly selected', 'other': 'Other lines',
}
# Marine_What00 is both a Selected line and one of the lines a Marine says when trained, and
# the box lists it under both. Kept once, under the one the file is named for.
KIND = {'Ready': 'arrive', 'Help': 'hurt', 'What': 'select', 'Yes': 'move',
        'Attack': 'attack', 'Pissed': 'witty', 'Death': 'other'}
FILE_KIND = re.compile(r'_(%s)\d*\.ogg$' % '|'.join(KIND), re.I)


def wikitexts(titles):
    out = {}
    for batch in chunks(titles, 50):
        j = api(HOST, prop='revisions', rvprop='content', rvslots='main', redirects=1,
                titles='|'.join(batch))
        # a redirected template has to be found again under the name the page asked for
        back = {r['to']: r['from'] for r in j['query'].get('redirects', [])}
        for p in j['query']['pages']:
            try:
                text = p['revisions'][0]['slots']['main']['content']
            except (KeyError, IndexError):
                continue
            out[back.get(p['title'], p['title'])] = text
    return out


def pages():
    """The three race pages, and every Quotes template they transclude."""
    text = wikitexts([PAGE + r for r in RACES])
    names = sorted({m.group(1) for t in text.values() for line in t.split('\n')
                    for m in [TRANSCLUDE.match(line.strip())] if m})
    return {'pages': text, 'templates': wikitexts(['Template:' + n for n in names])}


def heading(s):
    return clean(LINK.sub(lambda m: m.group(2) or m.group(1), s))


def top_split(s, sep):
    """Split on a separator that is outside links and templates."""
    depth, cur, out = 0, '', []
    for i, ch in enumerate(s):
        if ch in '[{':
            depth += 1
        elif ch in ']}':
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    out.append(cur)
    return out


def clips(line):
    """-> [(file, words)] for each {{sm2|file|words}} on a line."""
    out = []
    for m in SM2.finditer(line):
        depth, i = 1, m.end()
        while i < len(line) and depth:
            if line.startswith('{{', i):
                depth, i = depth + 1, i + 2
            elif line.startswith('}}', i):
                depth, i = depth - 1, i + 2
            else:
                i += 1
        args = top_split(line[m.end():i - 2], '|')
        f = args[0].strip()
        if not f:
            continue
        words = unquote(clean(args[1])) if len(args) > 1 else ''
        out.append(((f[:1].upper() + f[1:]).replace(' ', '_'), words))
    return out


def quote_box(text):
    """-> [(param, file, words)] from a {{UnitQuoteBox}}. A parameter runs until the next
    one starts, so its bullets are simply every line in between."""
    out, param = [], 'other'
    for line in text.split('\n'):
        m = PARAM.match(line.strip())
        if m and m.group(1) in CATEGORY:
            param, line = m.group(1), m.group(2)
        out += [(param, f, w) for f, w in clips(line)]
    return out


def parse(race, text, templates):
    """The pages don't agree on depth: Protoss and Terran put units at level 4 under a level-3
    Versus / Campaign / Heroes, Zerg puts them at 3 under a level-2 one, and then files its
    Heroes at 3 anyway. So a heading is a mode by its name, a unit by sitting one level under
    the mode, and anything deeper is a variant of that unit."""
    rows, mode, depth, unit, variant = [], '', 2, '', ''
    for line in text.split('\n'):
        s = line.strip()
        h = HEADING.match(s)
        if h:
            name, level = heading(h.group(2)), len(h.group(1))
            m = MODE.match(name)
            if m:
                mode, depth, unit, variant = m.group(1), level, '', ''
            elif level <= depth + 1:
                unit, variant = name, ''
                # every race has a "Structures" heading, and one list of structures a race
                if 'Structures' in name:
                    unit = race + ' structures'
            else:
                # "High Templar (Legacy of the Void ...)" under High Templar says it twice
                m = re.match(re.escape(unit) + r'\s*\((.+)\)$', name)
                variant = m.group(1) if m else name
            continue
        m = TRANSCLUDE.match(s)
        found = (quote_box(templates.get('Template:' + m.group(1), '')) if m
                 # the few lines written straight onto the page: Aiur zealot's two
                 else [('select' if 'What' in f else 'other', f, w) for f, w in clips(s)])
        for param, f, words in found:
            rows.append({'file': f, 'group': unit or race, 'skin': race,
                         'cat': CATEGORY[param], 'param': param,
                         'sub': ' · '.join(filter(None, [mode, variant])), 'text': words})
    return rows


def build(cache):
    got = cache('sc2-wikitext', pages)
    print('  %d quote templates' % len(got['templates']), flush=True)
    rows = []
    for race in RACES:
        rows += parse(race, got['pages'].get(PAGE + race, ''), got['templates'])
    print('  %d clip mentions parsed' % len(rows), flush=True)

    best = {}
    for r in rows:
        k = FILE_KIND.search(r['file'])
        rank = (bool(r['text']), bool(k) and KIND[k.group(1).capitalize()] == r['param'])
        if r['file'] not in best or rank > best[r['file']][0]:
            best[r['file']] = (rank, r)
    return [r for _, r in best.values()]

"""Overwatch 1 and 2, from the Fandom wiki.

Every hero, map, mission and announcer has a /Quotes page, and those pages are wikitables
whose last two columns are the line and the clip that says it:

    | rowspan="8" | <center><big>'''Blink'''</big></center>
    |All right!
    |{{Audio|Tracer - Alright.ogg}}

The leading columns are the trigger, and they carry a rowspan over every line that shares
them, so a row is only complete once the cells still spanning down from earlier rows are put
back in front of it. Section headings supply the category -- Voice Lines, Eliminations,
Interactions -- which is the other half of what makes these browsable.

Two more shapes are worth reading. The map pages use bullets instead of a table:

    *{{Audio|Numbani Announcement (2).ogg}} "Flight 1147 ... is preparing for pre-boarding."

and hero interactions put a whole conversation in one cell against a column of clips:

    |
    *'''Tracer''': I don't know how you do it, Ana!
    *'''Ana''': Do what?
    |
    {{Audio|Tracer - I don't know how you do it, Ana.ogg}}<br>
    {{Audio|Ana - Do what.ogg}}

Those pair up one for one, which is what lets Ana's half of the conversation be filed under
Ana rather than under whichever hero's page it happened to be read from.

A line that is still in the game is written up on <Hero>/Quotes, and the pre-sequel version
of the same page lives at <Hero>/Quotes/Overwatch 1. Clips on both are kept once, as
Overwatch 2, so "Overwatch 1" in the game box means a line that only the old page has --
which is roughly the set that was cut.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki import api, chunks                                       # noqa: E402
from wikitext import clean, unquote                                # noqa: E402

HOST = 'overwatch.fandom.com'

AUDIO = re.compile(r'\{\{\s*Audio\s*\|\s*([^{}|]+?)\s*(?:\|[^{}]*)?\}\}', re.I)
HEADING = re.compile(r'^(={2,6})\s*(.+?)\s*\1\s*$')
# {{QuoteTranslation|quote = Tire pou geri!|translation = Shoot to heal!}} wraps every line
# that isn't spoken in English, and the English is in a named field, not the first one.
QTRANS = re.compile(r'\{\{\s*QuoteTranslation\s*\|', re.I)
FIELD = re.compile(r'^\s*(quote|translation|native)\s*=\s*(.*)$', re.I | re.S)
BULLET = re.compile(r'^\*+\s*(.+)$')
SPEAKER = re.compile(r'^([^:]{1,28}):\s+(.+)$', re.S)
# an html attribute list: "rowspan=\"3\" style=\"...\"", never markup
ATTRS = re.compile(r'^[^\[{]*=[^\[{]*$')
ROWSPAN = re.compile(r'rowspan\s*=\s*"?(\d+)', re.I)

# Trivia and navigation link clips that are listed properly elsewhere on the page, next to
# text that is about them rather than said in them.
SKIP_SECTIONS = {'trivia', 'references', 'external links', 'notes', 'see also', 'navigation',
                 'gallery'}


def quote_pages():
    """Every /Quotes page. The wiki has 2.7k articles, which is six requests, so read the
    lot and filter here rather than guessing at a category."""
    out, cont = [], {}
    while True:
        j = api(HOST, list='allpages', apnamespace=0, aplimit=500,
                apfilterredir='nonredirects', **cont)
        out += [p['title'] for p in j['query']['allpages']]
        if 'continue' not in j:
            break
        cont = j['continue']
    return sorted(t for t in out if '/Quotes' in t)


def wikitexts(titles):
    """Page text for many titles; the api takes 50 at a time."""
    out = {}
    for batch in chunks(titles, 50):
        j = api(HOST, prop='revisions', rvprop='content', rvslots='main',
                titles='|'.join(batch))
        for p in j['query']['pages']:
            try:
                out[p['title']] = p['revisions'][0]['slots']['main']['content']
            except (KeyError, IndexError):
                pass                               # redirect or empty page, nothing to parse
    return out


def files_in(s):
    # a page is free to write {{Audio|lúcio - ...}}; mediawiki upper-cases the first letter
    # of a title, so the crawl only ever knows the file as Lúcio - ...
    return [(f[:1].upper() + f[1:]).replace(' ', '_') for f in AUDIO.findall(s)]


def top_split(s, sep):
    """Split on a separator that is outside links and templates."""
    depth, cur, out, i = 0, '', [], 0
    while i < len(s):
        if s.startswith(sep, i) and depth <= 0:
            out.append(cur)
            cur = ''
            i += len(sep)
            continue
        ch = s[i]
        if ch in '[{':
            depth += 1
        elif ch in ']}':
            depth -= 1
        cur += ch
        i += 1
    out.append(cur)
    return out


def cell(raw):
    """-> (content, rowspan). `rowspan="3" | <center>Blink</center>` -> the centre bit, 3."""
    parts = top_split(raw, '|')
    if len(parts) > 1 and ATTRS.match(parts[0]):
        m = ROWSPAN.search(parts[0])
        return '|'.join(parts[1:]).strip(), int(m.group(1)) if m else 1
    return raw.strip(), 1


def said(text):
    """The spoken line in a cell: English where the wiki offers a translation, and without
    the clip templates that sit in the same cell on the bullet-list pages."""
    m = QTRANS.search(text)
    if m:
        # to its own closing braces, not to the last ones on the line -- a {{OW2 Quote}} tag
        # often follows, and swallowing it would put "}} {{OW2 Quote" in the transcript
        depth, i = 1, m.end()
        while i < len(text) and depth:
            if text.startswith('{{', i):
                depth, i = depth + 1, i + 2
            elif text.startswith('}}', i):
                depth, i = depth - 1, i + 2
            else:
                i += 1
        fields = {}
        for part in top_split(text[m.end():i - 2], '|'):
            f = FIELD.match(part)
            if f:
                fields[f.group(1).lower()] = f.group(2)
        text = fields.get('translation') or fields.get('quote') or text
    return unquote(clean(AUDIO.sub('', text)))


def unclosed(s):
    """How many templates and links this line leaves open. A cell only ends where its
    markup does: a {{QuoteTranslation}} spread over eight lines has `|translation=` sitting
    at the start of one of them, and that pipe starts no new cell."""
    return s.count('{{') + s.count('[[') - s.count('}}') - s.count(']]')


def table_rows(lines):
    """Walk one wikitable, yielding each row as a list of cell strings.

    A cell with a rowspan is put back at the front of the rows below it, which is where it
    belongs in all of these tables -- the spanning columns are the leading ones.
    """
    out, held, row, open_depth = [], [], None, 0

    def flush():
        nonlocal row
        if row is None:
            return
        out.append([h[0] for h in held] + [c[0] for c in row])
        keep = [[h[0], h[1] - 1] for h in held if h[1] > 1]
        keep += [[c[0], c[1] - 1] for c in row if c[1] > 1]
        held[:] = keep
        row = None

    for line in lines:
        s = line.strip()
        if open_depth > 0 and row:                # a template left open on an earlier line
            row[-1][0] += '\n' + line
            open_depth = max(0, open_depth + unclosed(s))
            continue
        if s.startswith('|-') or s.startswith('|}'):
            flush()
            row, open_depth = [], 0
            continue
        if s.startswith('!') or s.startswith('{|') or s.startswith('|+'):
            continue                              # header row or caption: nothing said in it
        if s.startswith('|'):
            if row is None:
                row = []
            row += [list(cell(p.lstrip('|'))) for p in top_split(s[1:], '||')]
            open_depth = max(0, unclosed(s))
        elif row:
            row[-1][0] += '\n' + line
            open_depth = max(0, unclosed(s))
    flush()
    return out


def split_speaker(line, names):
    """"Soldier: 76: Get behind me!" -> ('Soldier: 76', 'Get behind me!'). The colon in a
    hero's own name is why this tries the known names before falling back to a regex."""
    for n in names:
        if line.lower().startswith(n.lower() + ':'):
            return n, line[len(n) + 1:].strip()
    m = SPEAKER.match(line)
    return (m.group(1).strip(), m.group(2).strip()) if m else ('', line)


def from_row(cells, names):
    """-> list of (file, speaker, text, label) for one table row."""
    audio = [i for i, c in enumerate(cells) if files_in(c)]
    if not audio:
        return []
    i = audio[-1]
    files = files_in(cells[i])
    # the quote is the column before the clips, except on the pages that put both in one cell
    quote = cells[i - 1] if i and i - 1 not in audio else cells[i]
    label = ' · '.join(filter(None, (clean(c) for c in cells[:max(i - 1, 0)])))

    # an interaction: one bullet per clip, each naming who says it
    bullets = [BULLET.match(l.strip()).group(1)
               for l in quote.split('\n') if BULLET.match(l.strip())]
    if len(bullets) == len(files) > 1:
        out = []
        for f, b in zip(files, bullets):
            who, line = split_speaker(said(b), names)
            # the name still comes off the line either way; it only decides who the clip
            # belongs to when it is someone the wiki has a page for, so that a one-off
            # like "*'Asteroid' Wrecking Ball:" doesn't invent a hero
            out.append((f, who if who in names else '', line, label))
        return out
    return [(f, '', said(quote), label) for f in files]


def parse(title, text, names):
    """-> list of dicts: file, group, skin, cat, sub, text."""
    subject = title.split('/')[0]
    game = 'Overwatch 1' if title.endswith('/Overwatch 1') else 'Overwatch 2'
    rows, cat, head, skipping, table = [], '', '', False, None

    def add(found, sub):
        for f, who, line, label in found:
            rows.append({'file': f, 'group': who or subject, 'skin': game, 'cat': cat,
                         'sub': ' · '.join(filter(None, [sub, label])), 'text': line})

    for line in text.split('\n'):
        s = line.strip()
        if table is not None:
            table.append(line)
            if s.startswith('|}'):
                for cells in table_rows(table):
                    add(from_row(cells, names), head)
                table = None
            continue
        h = HEADING.match(s)
        if h:
            name = clean(h.group(2))
            if len(h.group(1)) == 2:
                cat, head = name, ''
                skipping = name.lower() in SKIP_SECTIONS
            else:
                head = name
            continue
        if skipping:
            continue
        if s.startswith('{|'):
            table = [line]
            continue
        # the map pages: "*{{Audio|Numbani Announcement (2).ogg}} "Flight 1147 ...""
        if BULLET.match(s) and files_in(s):
            add([(f, '', said(s), '') for f in files_in(s)], head)
    if table:                                     # a page that forgot to close its table
        for cells in table_rows(table):
            add(from_row(cells, names), head)
    return rows


def same_heading(s):
    """Map-Specific, Map Specific and map specifics all land on the same key."""
    return re.sub(r'[^a-z]', '', s.lower()).rstrip('s')


def build(cache):
    titles = cache('ow-pages', quote_pages)
    print('  %d quote pages' % len(titles), flush=True)
    texts = cache('ow-wikitext', lambda: wikitexts(titles))
    # longest first so "Soldier: 76" wins over "Soldier", and only real page subjects are
    # ever trusted as a speaker
    names = sorted({t.split('/')[0] for t in texts}, key=len, reverse=True)

    rows = []
    for t in sorted(texts):
        rows += parse(t, texts[t], names)
    print('  %d clip mentions parsed' % len(rows), flush=True)

    # A line usually appears on both the Overwatch 2 page and the Overwatch 1 one, and an
    # interaction appears on both heroes' pages, so keep the best mention of each clip:
    # the one that has the words, then the one from the current game.
    best = {}
    for r in rows:
        rank = (bool(r['text']), r['skin'] == 'Overwatch 2', bool(r['cat']))
        if r['file'] not in best or rank > best[r['file']][0]:
            best[r['file']] = (rank, r)
    kept = [r for _, r in best.values()]

    # Headings are hand-typed on 111 pages, so "Mission Specific" and "Mission-Specific" are
    # both in there. Two spellings of one category means two entries in the box, so the rare
    # one loses to the common one -- 63 rows against 3,275, and likewise for the other pair.
    spellings = {}
    for r in kept:
        seen = spellings.setdefault(same_heading(r['cat']), {})
        seen[r['cat']] = seen.get(r['cat'], 0) + 1
    winner = {k: max(v, key=v.get) for k, v in spellings.items()}
    for r in kept:
        r['cat'] = winner[same_heading(r['cat'])]
    return kept

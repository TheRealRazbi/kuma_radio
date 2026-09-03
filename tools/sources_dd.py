"""Darkest Dungeon 1 and 2 (one wiki covers both).

There is no per-character audio page here the way League has one, so the shape is inverted:
read every article on the wiki (703 of them, 17 requests) and note which clips each one
mentions and what it says about them. Asking the api which pages embed a given file would
be the direct route, but imageusage takes one request per file and Fandom rate-limits long
before 800 of them are done. The narrator's page is the payoff -- it puts {{Quote|...}}
immediately above the clip that says it.

Three markup shapes carry audio, all seen in the wild:

    {{Quote|Ruin has come to our family.}}
    [[File:SoundIcon.png|20px|left|link=]]<sm2>Vo_narr_tut_firstdungeon.ogg</sm2>

    {{Quote|The fiends must be driven back.
    [[File:Narration_ruins_cleanse.wav|60px]]|The Ancestor|entering a Skirmish}}

    |sound1=[[File:Char al hll wickedhack.wav]]      (inside a skill infobox)
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_audio import AUDIO, CACHE, load as load_audio           # noqa: E402
from wiki import api, chunks                                       # noqa: E402
from wikitext import clean                                         # noqa: E402

HOST = 'darkestdungeon.fandom.com'

SM2 = re.compile(r'<sm2>\s*([^<>]+?)\s*</sm2>', re.I)
FILEREF = re.compile(r'\[\[\s*(?:File|Image)\s*:\s*([^|\]]+?)\s*(?:\||\]\])', re.I)
HEADING = re.compile(r'^(={2,6})\s*(.+?)\s*\1\s*$')
BOLD = re.compile(r"^'''(.+?)'''\s*$")
NAME_FIELD = re.compile(r'^\|\s*name\s*=\s*(.+?)\s*$', re.I)
QUOTE_START = re.compile(r'\{\{\s*(?:Quote|quote)\s*\|')
# "(Darkest Dungeon II)" on a page title, "Dd2_" on a filename -- the only two tells the
# wiki gives for which game a clip belongs to.
DD2_PAGE = re.compile(r'\(Darkest Dungeon II\)|Darkest Dungeon II', re.I)


def articles():
    """Every real article, redirects excluded."""
    out, cont = [], {}
    while True:
        j = api(HOST, list='allpages', apnamespace=0, aplimit=500,
                apfilterredir='nonredirects', **cont)
        out += [p['title'] for p in j['query']['allpages']]
        if 'continue' not in j:
            return out
        cont = j['continue']


def wikitexts(titles):
    out = {}
    for batch in chunks(sorted(titles), 50):
        j = api(HOST, prop='revisions', rvprop='content', rvslots='main',
                titles='|'.join(batch))
        for p in j['query']['pages']:
            try:
                out[p['title']] = p['revisions'][0]['slots']['main']['content']
            except (KeyError, IndexError):
                pass
    return out


def first_arg(body):
    """The text of a {{Quote|text|speaker|context}}, splitting on top-level pipes only.

    A naive split eats quotes that contain a piped link -- "Send [[Brigand Bloodletter|these
    vermin]] a message" would end at the first bracket.
    """
    depth, out = 0, []
    for ch in body:
        if ch in '[{':
            depth += 1
        elif ch in ']}':
            depth -= 1
        elif ch == '|' and depth <= 0:
            break
        out.append(ch)
    return ''.join(out)


def files_in(line):
    return [f.strip().replace(' ', '_') for f in SM2.findall(line) + FILEREF.findall(line)
            if AUDIO.search(f.strip())]


def parse(title, text):
    """-> {file: {cat, sub, text}} for every audio clip this article ties to a line."""
    found, cat, sub, pending, label = {}, '', '', '', ''
    quote_buf, depth = None, 0

    for line in text.split('\n'):
        # a {{Quote|...}} can wrap several lines and can hold the clip itself, so collect
        # the whole template before deciding what it is
        if quote_buf is None and QUOTE_START.search(line):
            quote_buf, depth = '', 0
        if quote_buf is not None:
            quote_buf += line + '\n'
            depth += line.count('{{') - line.count('}}')
            if depth > 0:
                continue
            body = QUOTE_START.sub('', quote_buf, count=1)
            body = body.rsplit('}}', 1)[0]
            said = clean(first_arg(body))
            for f in files_in(quote_buf):
                found.setdefault(f, {'cat': cat, 'sub': sub, 'text': said})
            if not files_in(quote_buf):
                pending = said                      # the clip is on a following line
            quote_buf = None
            continue

        h = HEADING.match(line)
        if h:
            if len(h.group(1)) == 2:
                cat, sub = clean(h.group(2)), ''
            else:
                sub = clean(h.group(2))
            pending = ''
            continue
        b = BOLD.match(line)
        if b:
            label = clean(b.group(1))
            continue
        n = NAME_FIELD.match(line)
        if n:
            label = clean(n.group(1))
            continue

        here = files_in(line)
        for f in here:
            found.setdefault(f, {'cat': cat, 'sub': sub or label,
                                 'text': pending or label})
        # a quote only speaks for the clip right after it. Without this, an article that
        # opens with a {{Quote}} blurb would hand that blurb to its first skill sound.
        if line.strip():
            pending = ''
    return found


def build(cache):
    audio = load_audio(HOST)
    names = [a['name'] for a in audio]
    print('  %d audio files' % len(names), flush=True)
    titles = cache('dd-pages', articles)
    texts = cache('dd-wikitext', lambda: wikitexts(titles))
    print('  %d articles read' % len(texts), flush=True)

    parsed = {t: parse(t, texts[t]) for t in texts}
    used = {}
    for title, found in parsed.items():
        for f in found:
            used.setdefault(f, []).append(title)
    print('  %d clips are mentioned somewhere' % len(used), flush=True)

    rows = []
    for name in names:
        pages = sorted(used.get(name) or [])
        # prefer the article that actually names the line over one that only links the clip
        best = next((p for p in pages if parsed.get(p, {}).get(name, {}).get('text')), None)
        page = best or (pages[0] if pages else '')
        info = parsed.get(page, {}).get(name, {})
        dd2 = bool(DD2_PAGE.search(page)) or name.lower().startswith('dd2')
        rows.append({'file': name,
                     'group': re.sub(r'\s*\(Darkest Dungeon I{1,2}\)\s*$', '', page) or 'Unsorted',
                     'skin': 'Darkest Dungeon II' if dd2 else 'Darkest Dungeon',
                     'cat': info.get('cat', ''), 'sub': info.get('sub', ''),
                     'text': info.get('text', '')})
    return rows

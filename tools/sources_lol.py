"""League of Legends: champion voice lines, with the spoken text.

Everything worth having is in the wikitext of the <Champion>/LoL/Audio pages, where each
line pairs one or more {{sm2|file|champion|skin}} templates with the quote they all say:

    * {{sm2|Lulu_Original_Move_7.ogg|Lulu}} {{sm2|Lulu_CosmicEnchantress_Move_5.ogg|Lulu|Cosmic Enchantress}} ''"Yup, that tasted purple."''

so one parsed line becomes several rows that share one quote. Section headings carry the
category (Taunt, Joke, Recall...), which is the other half of what makes these browsable.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re                                                          # noqa: E402
from wiki import api, chunks                                       # noqa: E402
from wikitext import clean, unquote                                # noqa: E402

HOST = 'leagueoflegends.fandom.com'
CATEGORY = 'Category:LoL Champion audio'

SM2 = re.compile(r'\{\{\s*sm2\s*\|([^{}|]+?)(?:\|([^{}|]*))?(?:\|([^{}]*?))?\}\}', re.I)
HEADING = re.compile(r'^(={2,6})\s*(.+?)\s*\1\s*$')
SUBLABEL = re.compile(r"^;\s*(.+?)\s*$")
ITALIC = re.compile(r"''(.+)''")
# Trivia repeats clips already listed above, next to text that isn't what is said in them.
SKIP_SECTIONS = {'trivia', 'references', 'external links', 'notes', 'see also'}


def audio_pages():
    out, cont = [], {}
    while True:
        j = api(HOST, list='categorymembers', cmtitle=CATEGORY, cmlimit=500,
                cmnamespace=0, **cont)
        out += [m['title'] for m in j['query']['categorymembers']]
        if 'continue' not in j:
            return sorted(out)
        cont = j['continue']


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
                pass                                   # redirect or empty page, nothing to parse
    return out


def parse(title, text):
    """-> list of dicts: file, group, skin, cat, sub, text."""
    champ = title.split('/')[0]
    rows, cat, sub, skipping = [], '', '', False

    for line in text.split('\n'):
        h = HEADING.match(line)
        if h:
            name = clean(h.group(2))
            if len(h.group(1)) == 2:
                cat, sub = name, ''
                skipping = name.lower() in SKIP_SECTIONS
            else:
                sub = name
            continue
        if skipping:
            continue
        s = SUBLABEL.match(line)
        if s and '{{' not in line[:2]:
            sub = clean(s.group(1))
            continue

        hits = list(SM2.finditer(line))
        if not hits:
            continue
        # the quote is the italic run after the last clip, shared by every clip on the line.
        # it has to start at the end of the last sm2, not the last "}}" -- quotes contain
        # templates of their own, e.g. ''"...destroy it, {{tt|FYI|for your information}}."''
        said = ITALIC.search(line[hits[-1].end():])
        said = unquote(clean(said.group(1))) if said else ''
        for m in hits:
            fname, _champ_arg, skin = m.group(1), m.group(2), m.group(3)
            fname = fname.strip().replace(' ', '_')
            if not fname:
                continue
            rows.append({'file': fname, 'group': champ,
                         'skin': clean(skin).strip() or 'Original',
                         'cat': cat, 'sub': sub, 'text': said})
    return rows


def build(cache):
    titles = cache('lol-pages', audio_pages)
    print('  %d champion audio pages' % len(titles), flush=True)
    texts = cache('lol-wikitext', lambda: wikitexts(titles))
    rows = []
    for t in sorted(texts):
        rows += parse(t, texts[t])
    return rows

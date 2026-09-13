"""Turn wikitext fragments into the plain sentence a human would read.

Only what the quote lines actually contain: link syntax, bold/italic ticks, refs, and the
handful of inline templates the wikis use for cross-links. Anything unrecognised collapses
to its first positional argument, which is right far more often than dropping it.
"""

import html
import re

# {{f|Futurama|Philip J. Fry}} and friends put the display text last, not first.
DISPLAY_LAST = {'f', 'fq', 'w'}

IMAGE_ARG = re.compile(r'\.(png|jpe?g|gif|svg|webp)$', re.I)
TICKS = re.compile(r"'{2,5}")
REF = re.compile(r'<ref[^>]*>.*?</ref>|<ref[^>]*/>', re.I | re.S)
TAG = re.compile(r'<[^>]+>')
FILELINK = re.compile(r'\[\[\s*(?:File|Image)\s*:[^\[\]]*(?:\[\[[^\[\]]*\]\][^\[\]]*)*\]\]', re.I)
LINK = re.compile(r'\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]')
EXTLINK = re.compile(r'\[(?:https?|//)\S+?(?: ([^\]]*))?\]')
TEMPLATE = re.compile(r'\{\{([^{}]*)\}\}')


def _template(m):
    parts = [p.strip() for p in m.group(1).split('|')]
    name = parts[0].strip().lower()
    args = [p for p in parts[1:]
            if '=' not in p.split(' ')[0]
            and not IMAGE_ARG.search(p)]     # icon templates: {{ccib|Gold.png|size=32}}Shopping
    if not args:
        return ''
    return args[-1] if name in DISPLAY_LAST else args[0]


def clean(s):
    if not s:
        return ''
    s = REF.sub('', s)
    s = FILELINK.sub(' ', s)                # headings like "== [[File:Gold.png|20px]] Shopping =="

    for _ in range(4):                      # templates nest; peel from the inside out
        s, n = TEMPLATE.subn(_template, s)
        if not n:
            break
    s = LINK.sub(lambda m: (m.group(2) or m.group(1)).strip(), s)
    s = EXTLINK.sub(lambda m: (m.group(1) or '').strip(), s)
    s = TICKS.sub('', s)
    s = TAG.sub(' ', s)
    s = html.unescape(s)
    s = s.replace(' ', ' ')          # nbsp reads as a space, not a word joiner
    return re.sub(r'\s+', ' ', s).strip()


def unquote(s):
    """Drop the surrounding double quotes the wikis wrap spoken lines in: "", “”, and the
    « » and „” of the French and Polish wikis."""
    s = s.strip()
    if len(s) > 1 and s[0] in '"“«„' and s[-1] in '"”»“':
        return s[1:-1].strip()
    # the Spanish wiki puts the full stop outside: "Se acabaron los juegos".
    m = re.match(r'^["“«„]([^"“”«»„]+)["”»“]([.!?…]+)$', s)
    if m:
        inner = m.group(1).strip()
        return inner if inner[-1:] in '.!?…' else inner + m.group(2)
    return s

"""League of Legends: champion voice lines, with the spoken text.

Everything worth having is in the wikitext of the <Champion>/LoL/Audio pages, where each
line pairs one or more {{sm2|file|champion|skin}} templates with the quote they all say:

    * {{sm2|Lulu_Original_Move_7.ogg|Lulu}} {{sm2|Lulu_CosmicEnchantress_Move_5.ogg|Lulu|Cosmic Enchantress}} ''"Yup, that tasted purple."''

so one parsed line becomes several rows that share one quote. Section headings carry the
category (Taunt, Joke, Recall...), which is the other half of what makes these browsable.

The language wikis are separate wikis one path segment over, and each files its voice lines
somewhere else, mostly as a two-argument template with the quote inside it:

    fr     Rammus/Historique   {{sm2|Rammus.attaque01|''« Oui. »''}}
    es     Rammus/LoL/Audio    {{sm2 | Rammus 0002 es_MX.ogg | ''"Sí."''}}    in LATAM / EUW tabs
    pl     Rammus/cytaty       {{sm2|Rammus.atak1.ogg|'' „Ta.”''}}
    pt-br  Ahri/LoL/Áudio      the English layout, translated
    cs     Ahri/Příběh         {{ogg|Ahri.attack1|''"Hra skončila."''}}

so localized() finds its pages by what embeds the template rather than by page name.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re                                                          # noqa: E402
from crawl_audio import AUDIO, load as load_audio                  # noqa: E402
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


def wikitexts(titles, host=HOST):
    """Page text for many titles; the api takes 50 at a time."""
    out = {}
    for batch in chunks(titles, 50):
        j = api(host, prop='revisions', rvprop='content', rvslots='main',
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


# ---------------------------------------------------------------- other languages

LANGS = {
    'fr':    {'name': 'Français', 'templates': ['Sm2'], 'orphans': True},
    'es':    {'name': 'Español', 'templates': ['Sm2'], 'tabs': True},     # LATAM and EUW tabs
    'pl':    {'name': 'Polski', 'templates': ['Sm2']},
    'pt-br': {'name': 'Português (Brasil)', 'templates': ['Sm2']},
    'cs':    {'name': 'Čeština', 'templates': ['Ogg']},
}

# Subpages that embed clips but are not where the lines live: trivia and skin pages repeat
# clips beside text that isn't what is said in them, and the rest are patch history or other
# games.
SKIP_PAGES = {'curiosidades', 'skinstrivia', 'skórki i ciekawostki', 'rozwój', 'lor', 'tft',
              'universo principal', 'lol/historial', 'lol/histórico'}
SKIP_SECTIONS_LOCAL = SKIP_SECTIONS | {
    'anecdotes', 'références', 'voir aussi', 'historique des mises à jour',
    'curiosidades', 'referencias', 'referências', 'véase también', 'notas',
    'ciekawostki', 'przypisy', 'zobacz też', 'zajímavosti', 'reference', 'poznámky'}
# A heading that only says "these are the quotes": the ;labels under it are the categories.
GENERIC = {'dialogue', 'dialogues', 'répliques', 'citations', 'frases', 'diálogo', 'diálogos',
           'cytaty', 'falas', 'citações', 'citáty', 'hlášky', 'quotes'}
QUOTES = '"“„«\''
# written in where nobody has transcribed the line yet
PLACEHOLDERS = {'por transcribir', 'por traducir', 'do przetłumaczenia', 'a transcrever'}
EN_LINK = re.compile(r'\[\[\s*en\s*:\s*([^\]|]+)', re.I)
CLIP = re.compile(r'\{\{\s*(?:sm2|ogg)\s*\|', re.I)
TAB = re.compile(r'^\s*(?:\|-\|)?\s*([^=<>{}\[\]|*;:#]{1,40}?)\s*=\s*$')

# Clips no page embeds any more: the French wiki deleted Ahri/Historique (and others) but kept
# the files, whose names still say what kind of line they are -- Ahri.attaque01.ogg,
# Ahri_Selection.ogg, and Zeri's uploaded under English words (Zeri_moving_3.ogg).
ORPHAN_CATS = {'attaque': 'Attaque', 'mouvement': 'Mouvement', 'blague': 'Blague',
               'provocation': 'Provocation', 'rire': 'Rire', 'selection': 'En sélection',
               'moving': 'Mouvement', 'long_moove': 'Mouvement', 'joke': 'Blague',
               'taunt': 'Provocation', 'laugh': 'Rire', 'pick': 'En sélection',
               'start': 'En début de partie'}
NUMBERED = re.compile(r'^([^\W\d_]+)_?\d+$')        # the .attaque01 in Ahri.attaque01.ogg


def embedding(host, templates):
    out = set()
    for t in templates:
        cont = {}
        while True:
            j = api(host, list='embeddedin', eititle='Template:' + t, eilimit=500,
                    einamespace=0, **cont)
            out.update(m['title'] for m in j['query']['embeddedin'])
            if 'continue' not in j:
                break
            cont = j['continue']
    return sorted(out)


def _args(body):
    """Split template arguments on its own pipes, not those of a nested {{}} or [[]]."""
    out, cur, depth, i = [], '', 0, 0
    while i < len(body):
        two = body[i:i + 2]
        if two in ('{{', '[['):
            depth, cur, i = depth + 1, cur + two, i + 2
        elif two in ('}}', ']]'):
            depth, cur, i = depth - 1, cur + two, i + 2
        elif body[i] == '|' and depth == 0:
            out.append(cur)
            cur, i = '', i + 1
        else:
            cur, i = cur + body[i], i + 1
    return out + [cur]


def _clips(line):
    """-> [(args, end)] for every clip template on a line. Scanned for the matching braces
    rather than matched with a regex, because quotes carry templates of their own."""
    out, pos = [], 0
    while True:
        m = CLIP.search(line, pos)
        if not m:
            return out
        depth, i = 1, m.end()
        while i < len(line) and depth:
            if line.startswith('{{', i):
                depth, i = depth + 1, i + 2
            elif line.startswith('}}', i):
                depth, i = depth - 1, i + 2
            else:
                i += 1
        if depth:
            return out                     # unclosed: the rest of the line is not a clip
        out.append((_args(line[m.end():i - 2]), i))
        pos = i


def champion_of(title, text, champs):
    """Canonical English name, so a champion is the same dropdown entry in every language:
    the French wiki files Master Yi under "Maître Yi", but links the English page."""
    names = [m.strip().split('/')[0] for m in EN_LINK.findall(text)] + [title.split('/')[0]]
    return next((n for n in names if n in champs), None)


def parse_local(group, text, champs, tabs=False):
    """-> list of dicts: file, group, skin, cat, sub, text."""
    rows, cat, sub, tab = [], '', '', ''
    skipping = generic = in_tabber = False

    for line in text.split('\n'):
        low = line.strip().lower()
        if low.startswith('<tabber'):
            in_tabber, tab = True, ''
            t = TAB.match(line.split('>', 1)[1]) if '>' in line else None
            if tabs and t:
                tab = clean(t.group(1))
            continue
        if low.startswith('</tabber'):
            in_tabber, tab = False, ''
            continue
        if in_tabber and tabs and '{{' not in line:
            t = TAB.match(line)
            if t:
                tab = clean(t.group(1))
                continue

        h = HEADING.match(line)
        if h:
            name = clean(h.group(2))
            if len(h.group(1)) == 2:
                cat, sub = name, ''
                skipping = name.lower() in SKIP_SECTIONS_LOCAL
                generic = name.lower() in GENERIC
            else:
                sub = name
            continue
        if skipping:
            continue
        s = SUBLABEL.match(line)
        if s and '{{' not in line[:2]:
            if generic:
                cat, sub = clean(s.group(1)), ''
            else:
                sub = clean(s.group(1))
            continue

        hits = _clips(line)
        if not hits:
            continue
        trailing = ITALIC.search(line[hits[-1][1]:])
        trailing = unquote(clean(trailing.group(1))) if trailing else ''
        where = ' · '.join(x for x in (tab, sub) if x)
        for args, _end in hits:
            fname = args[0].strip().replace(' ', '_')
            if not fname:
                continue
            if not AUDIO.search(fname):
                fname += '.ogg'            # {{sm2|Rammus.attaque01|...}} leaves the .ogg off
            said, skin = trailing, 'Original'
            if len(args) >= 2:
                a = args[1].strip()
                # the second argument is either the champion (English layout) or the quote
                if "''" in a or a[:1] in QUOTES or (len(args) == 2 and clean(a) not in champs):
                    said = unquote(clean(a))
                elif len(args) >= 3:
                    skin = clean(args[2]).strip() or 'Original'
            rows.append({'file': fname, 'group': group, 'skin': skin,
                         'cat': cat, 'sub': where, 'text': said})
    return rows


def orphans(names, champs, have):
    """-> rows for clips in `names` that no page lists, going by the file name alone. Only
    names that read as a voice line get in: Ahri.<anything>01.ogg, or a known kind of line
    after an underscore. The rest are login themes, lore and sound effects."""
    prefixes = sorted(((v, c) for c in champs
                       for v in {c, c.replace(' ', '_'), re.sub(r'[\W_]', '', c)}),
                      key=lambda p: -len(p[0]))
    rows = []
    for name in sorted(n.replace(' ', '_') for n in names):
        if name in have or not name.lower().endswith('.ogg') or 'sfx' in name.lower():
            continue
        hit = next(((v, c) for v, c in prefixes
                    if name.startswith(v) and name[len(v):len(v) + 1] in ('.', '_')), None)
        if not hit:
            continue                       # a skin (DravenFaucheur.rire02) or not a champion
        v, champ = hit
        stem = name[len(v) + 1:-len('.ogg')]
        n = NUMBERED.match(stem)
        if name[len(v)] == '.' and n:
            cat = ORPHAN_CATS.get(n.group(1).lower(), '')
        else:
            cat = ORPHAN_CATS.get(re.sub(r'_?\d+$', '', stem).lower())
            if cat is None:
                continue
        rows.append({'file': name, 'group': champ, 'skin': 'Original',
                     'cat': cat, 'sub': '', 'text': ''})
    return rows


def localized(lang):
    spec = LANGS[lang]
    host = HOST + '/' + lang

    def build(cache):
        champs = {t.split('/')[0] for t in cache('lol-pages', audio_pages)}
        titles = cache('lol-%s-pages' % lang, lambda: embedding(host, spec['templates']))
        titles = [t for t in titles
                  if '/' not in t or t.split('/', 1)[1].lower() not in SKIP_PAGES]
        texts = cache('lol-%s-wikitext' % lang, lambda: wikitexts(titles, host))
        print('  %d %s pages embed a clip' % (len(texts), lang), flush=True)

        # a champion's article and its quotes subpage can both list a clip; keep the subpage's
        rows, seen, used = [], set(), 0
        for t in sorted(texts, key=lambda t: ('/' not in t, t)):
            group = champion_of(t, texts[t], champs)
            if not group:
                continue
            used += 1
            for r in parse_local(group, texts[t], champs, spec.get('tabs', False)):
                if r['text'].lower().rstrip('.') in PLACEHOLDERS:
                    r['text'] = ''         # no transcript: the finder shows the file name instead
                key = (r['file'], r['group'], r['skin'], r['text'])
                if key not in seen:
                    seen.add(key)
                    rows.append(r)
        print('  %d of them are champion pages' % used, flush=True)
        if spec.get('orphans'):
            extra = orphans([a['name'] for a in load_audio(host)], champs,
                            {r['file'] for r in rows})
            print('  %d more clips no page lists' % len(extra), flush=True)
            rows += extra
        return rows

    return build

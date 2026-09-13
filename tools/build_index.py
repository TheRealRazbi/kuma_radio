"""Build the JSON indexes that sfx.html ships with.

Run this, commit index/. The app never talks to a wiki: enumerating audio takes hundreds of
API requests per wiki (see crawl_audio.py), which is fine offline and hopeless in a browser.

    python tools/build_index.py            # all sources, using tools/.cache
    python tools/build_index.py lol dd     # just these
    python tools/build_index.py lol-fr     # League in one other language (see sources_lol.LANGS)

Columns are interned into side tables and rows are arrays, because the same champion, skin,
category and quote repeat thousands of times and the whole file is downloaded by the app.
"""

import datetime
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from cache import cache                                            # noqa: E402
from crawl_audio import load as load_audio                         # noqa: E402
import sources_dd                                                  # noqa: E402
import sources_lol                                                 # noqa: E402
import sources_ow                                                  # noqa: E402
import sources_wc3                                                 # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), 'index')

# https://static.wikia.nocookie.net/<wiki>/images/4/44/Foo.ogg -- the two hex chars are an
# md5 of the file name, so storing them costs 2 bytes a row instead of a whole url.
CDN = re.compile(r'^(https://static\.wikia\.nocookie\.net/[^/]+(?:/[a-z-]+)?/images)'
                 r'/([0-9a-f])/([0-9a-f]{2})/', re.I)

SOURCES = {
    'lol': {'name': 'League of Legends', 'host': sources_lol.HOST, 'family': 'lol',
            'lang': 'English',
            'group_label': 'Champion', 'skin_label': 'Skin', 'build': sources_lol.build},
    # the finder shows these as a language picker on League rather than as sources of their own
    **{'lol-' + code: {'name': 'League of Legends', 'host': sources_lol.HOST + '/' + code,
                       'family': 'lol', 'lang': lang['name'],
                       'group_label': 'Champion', 'skin_label': 'Skin',
                       'build': sources_lol.localized(code)}
       for code, lang in sources_lol.LANGS.items()},
    'ow':  {'name': 'Overwatch 1 & 2', 'host': sources_ow.HOST,
            'group_label': 'Hero', 'skin_label': 'Game', 'build': sources_ow.build},
    'dd':  {'name': 'Darkest Dungeon 1 & 2', 'host': sources_dd.HOST,
            'group_label': 'Character', 'skin_label': 'Game', 'build': sources_dd.build},
    'wc3': {'name': 'Warcraft III', 'host': sources_wc3.HOST,
            'group_label': 'Unit', 'skin_label': 'Kind', 'build': sources_wc3.build},
}


def cdn_url(url):
    """A language wiki's files come back from the api as .../leagueoflegends/images/...
    ?path-prefix=fr. The bare path is the only form that serves audio, and it only finds the
    file with the language moved into it: .../leagueoflegends/fr/images/..."""
    parts = urllib.parse.urlsplit(url)
    lang = urllib.parse.parse_qs(parts.query).get('path-prefix', [''])[0]
    path = re.sub(r'(\.[a-z0-9]+)/revision/.*$', r'\1', parts.path, flags=re.I)
    if lang:
        path = re.sub(r'^(/[^/]+)/images/', r'\1/%s/images/' % lang, path)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, '', ''))


class Table:
    """Interns strings and hands back their index."""

    def __init__(self):
        self.values, self.seen = [], {}

    def __call__(self, s):
        s = s or ''
        if s not in self.seen:
            self.seen[s] = len(self.values)
            self.values.append(s)
        return self.seen[s]


def build(sid):
    spec = SOURCES[sid]
    print('== %s' % sid, flush=True)
    rows = spec['build'](cache)

    # the crawl is the source of truth for what exists: wikitext happily links clips that
    # were renamed or never uploaded, and those would be dead play buttons in the app
    files = {a['name']: a for a in load_audio(spec['host'])}
    files.update({a['name'].replace(' ', '_'): a for a in load_audio(spec['host'])})

    groups, skins, cats, subs, texts = Table(), Table(), Table(), Table(), Table()
    out, missing, seen, base = [], 0, set(), None
    for r in rows:
        hit = files.get(r['file'])
        if not hit:
            missing += 1
            continue
        m = CDN.match(cdn_url(hit['url']))
        if not m:
            missing += 1
            continue
        base = base or m.group(1)
        key = (r['file'], r['group'], r['skin'], r['cat'], r['sub'], r['text'])
        if key in seen:
            continue
        seen.add(key)
        out.append([hit['name'].replace(' ', '_'), groups(r['group']), skins(r['skin']),
                    cats(r['cat']), subs(r['sub']), texts(r['text']), m.group(3)])

    doc = {
        'id': sid, 'name': spec['name'], 'wiki': spec['host'], 'cdn': base,
        'family': spec.get('family', sid), 'lang': spec.get('lang', ''),
        'groupLabel': spec['group_label'], 'skinLabel': spec['skin_label'],
        'built': datetime.date.today().isoformat(),
        'cols': ['file', 'group', 'skin', 'cat', 'sub', 'text', 'hash'],
        'groups': groups.values, 'skins': skins.values, 'cats': cats.values,
        'subs': subs.values, 'texts': texts.values, 'rows': out,
    }
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, sid + '.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print('   %d clips, %d dropped (not on the wiki), %.1f MB'
          % (len(out), missing, os.path.getsize(path) / 1e6), flush=True)
    return {'id': sid, 'name': spec['name'], 'wiki': spec['host'],
            'family': spec.get('family', sid), 'lang': spec.get('lang', ''),
            'clips': len(out), 'groups': len(groups.values),
            'quotes': sum(1 for r in out if doc['texts'][r[5]]),
            'bytes': os.path.getsize(path), 'built': doc['built']}


if __name__ == '__main__':
    wanted = sys.argv[1:] or list(SOURCES)
    manifest = [build(s) for s in wanted]
    mpath = os.path.join(OUT, 'sources.json')
    old = []
    if os.path.exists(mpath):
        with open(mpath, encoding='utf-8') as f:
            old = json.load(f)['sources']
    by_id = {s['id']: s for s in old}
    by_id.update({s['id']: s for s in manifest})
    with open(mpath, 'w', encoding='utf-8') as f:
        json.dump({'sources': [by_id[k] for k in SOURCES if k in by_id]}, f,
                  ensure_ascii=False, indent=1)
    print('wrote', mpath)

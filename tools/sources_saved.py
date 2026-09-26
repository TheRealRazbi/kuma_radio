"""Saved: hand-picked clips from games the finder doesn't index whole.

Indexing all of Hearthstone for the two lines anyone asks for is a half-hour crawl and a few
megabytes of index; copying the files into sounds/ would be re-hosting someone else's audio.
So tools/saved.json keeps just the links, one entry per clip:

    {"game": "Hearthstone", "who": "SI:7 Agent", "cat": "Card played",
     "said": "Heh, this guy's toast.",
     "link": "https://hearthstone.fandom.com/wiki/File:VO_EX1_134_Play_01.wav"}

A wiki File: page is looked up for its file url, the same way the overlay does it, and stays
the link that gets pasted in chat. Anything else (a sounds/ file, a direct audio url) is
used as it is.
"""

import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki import api, chunks                                       # noqa: E402

LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saved.json')
# host keeps a language wiki's path (leagueoflegends.fandom.com/fr), which is where its api is
FILE_PAGE = re.compile(r'^https?://([^/]+\.fandom\.com(?:/[a-z]{2,3}(?:-[a-z]+)?)?)'
                       r'/wiki/[^:/]+:(.+)$', re.I)


def build(cache):
    with open(LIST, encoding='utf-8') as f:
        items = json.load(f)

    pages = {}                                         # host -> {file name: item}
    rows = []
    for it in items:
        m = FILE_PAGE.match(it['link'])
        name = (urllib.parse.unquote(m.group(2)) if m
                else urllib.parse.unquote(urllib.parse.urlsplit(it['link']).path.rsplit('/', 1)[-1]))
        row = {'file': name.replace(' ', '_'), 'group': it['game'], 'skin': it.get('who', ''),
               'cat': it.get('cat', ''), 'sub': '', 'text': it.get('said', ''),
               'url': None if m else it['link'], 'page': it['link']}
        rows.append(row)
        if m:
            pages.setdefault(m.group(1), {})[row['file']] = row

    for host, by_name in pages.items():
        for batch in chunks(sorted(by_name), 50):
            j = api(host, prop='imageinfo', iiprop='url',
                    titles='|'.join('File:' + n for n in batch))
            for p in j['query']['pages']:
                info = p.get('imageinfo')
                if info:
                    by_name[p['title'].split(':', 1)[1].replace(' ', '_')]['url'] = info[0]['url']

    for r in rows:
        if not r['url']:
            print('  ! no such file: %s' % r['page'], flush=True)
    return [r for r in rows if r['url']]

"""Dump every audio file on a wiki to tools/.cache/<host>-audio.json.

`filetype:audio` search is broken on Fandom and mime filtering is off in miser mode, so the
only way to enumerate audio is to page through every image on the wiki and filter by
extension here. That is 400+ requests on the big wikis, which is exactly why the index is
built offline and shipped as JSON instead of being fetched by the app.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki import api                                              # noqa: E402

AUDIO = re.compile(r'\.(ogg|oga|opus|mp3|wav|m4a|aac|flac|weba)$', re.I)
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')


def crawl(host):
    """400+ requests on the big wikis, so checkpoint: a rate-limit near the end of a
    20-minute crawl should not cost the whole crawl."""
    part = os.path.join(CACHE, host + '-partial.json')
    out, cont, pages = [], {}, 0
    if os.path.exists(part):
        with open(part, encoding='utf-8') as f:
            saved = json.load(f)
        out, cont = saved['items'], saved['cont']
        print('  resuming %s at %d audio files' % (host, len(out)), flush=True)
    seen = {i['name'] for i in out}

    while True:
        j = api(host, list='allimages', ailimit=500, aiprop='url|size|mime', **cont)
        pages += 1
        for im in j.get('query', {}).get('allimages', []):
            name = im['name']
            if AUDIO.search(name) and name not in seen:
                seen.add(name)
                out.append({'name': name, 'url': im['url'],
                            'size': im.get('size'), 'mime': im.get('mime')})
        cont = j.get('continue')
        if not cont:
            break
        if pages % 20 == 0:
            print('  %s: %d requests, %d audio' % (host, pages, len(out)), flush=True)
            with open(part, 'w', encoding='utf-8') as f:
                json.dump({'cont': cont, 'items': out}, f)
    if os.path.exists(part):
        os.remove(part)
    return out


def load(host):
    """Cached crawl. Delete the cache file to refresh."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, host + '-audio.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    print('crawling %s ...' % host, flush=True)
    out = crawl(host)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f)
    print('  %s: %d audio files' % (host, len(out)), flush=True)
    return out


if __name__ == '__main__':
    for h in sys.argv[1:]:
        print(h, len(load(h)))

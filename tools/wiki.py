"""Shared MediaWiki API access for the index builder.

Fandom drops connections often enough that a plain urlopen loop dies partway through a
30-minute crawl, so get() retries, and long lists are always drained by following the api's
own `continue` object rather than by guessing offsets.
"""

import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = 'kuma-radio-index/1.0 (https://github.com/TheRealRazbi/kuma_radio)'
PAUSE = 0.4           # be a polite crawler; the whole build is a few thousand requests
THROTTLED = 120       # fandom answers 429 for a long while once it decides you are
                      # too fast, and running two crawls at once is enough to trip it


def get(url, tries=12):
    """GET with backoff. Returns bytes."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA,
                                                       'Accept-Encoding': 'gzip'})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    raw = gzip.decompress(raw)
                return raw
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            # a 429 is not a hiccup, it is a cool-off; retrying in 2s just extends it
            print('  ! rate limited -- waiting %ds' % THROTTLED, file=sys.stderr, flush=True)
            time.sleep(THROTTLED)
        except Exception as e:                       # noqa: BLE001 - any transport hiccup retries
            if attempt == tries - 1:
                raise
            wait = 2 ** attempt
            print('  ! %s -- retry in %ds' % (e, wait), file=sys.stderr, flush=True)
            time.sleep(wait)


def api(host, **params):
    params.setdefault('action', 'query')
    params.setdefault('format', 'json')
    params.setdefault('formatversion', '2')
    url = 'https://%s/api.php?%s' % (host, urllib.parse.urlencode(params))
    time.sleep(PAUSE)
    return json.loads(get(url).decode('utf-8'))


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]

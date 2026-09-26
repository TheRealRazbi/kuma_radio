"""Write tools/wc3_heard.json: speech recognition for the WC3 clips no quote page tags.

The index builder never runs this, it only reads the json it leaves behind, so building stays
stdlib-only. Run it again when the quote pages change which clips they cover; a clip they
start tagging simply stops using its entry here. It needs faster-whisper, which is not a
dependency of anything else, so give it a venv of its own:

    py -3.12 -m venv .local/asr
    .local/asr/Scripts/python -m pip install faster-whisper nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
    .local/asr/Scripts/python tools/transcribe_wc3.py

The two nvidia packages are the CUDA libraries for the gpu; without them it falls back to the
cpu, which is several times slower but still minutes for ~170 clips.

Scored against 150 clips the wiki does transcribe, whole sentences come back word for word.
What it gets wrong is the grunts and the invented languages -- "Hashtag Rodanado" for
Ash'thero danador -- which heard_text() in sources_wc3.py repairs where the wiki spells the
same line out elsewhere. no_speech_prob is kept for the same place to throw away noises.
"""

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cache import DIR, cache                                       # noqa: E402
from crawl_audio import load as load_audio                         # noqa: E402
from sources_wc3 import HEARD, HOST, quotes                        # noqa: E402
from wiki import get                                               # noqa: E402

CLIPS = os.path.join(DIR, 'wc3-clips')


def cuda_libs():
    """pip's nvidia packages put their dlls where Windows won't look for them."""
    try:
        import nvidia
    except ImportError:
        return
    for d in glob.glob(os.path.join(nvidia.__path__[0], '*', 'bin')):
        os.add_dll_directory(d)
        os.environ['PATH'] = d + os.pathsep + os.environ['PATH']


def model():
    from faster_whisper import WhisperModel
    try:
        m = WhisperModel('large-v3', device='cuda', compute_type='float16')
        # transcribe() is lazy, so a missing cuda library only shows up once it is consumed
        list(m.transcribe(os.path.join(CLIPS, os.listdir(CLIPS)[0]))[0])
        return m
    except Exception as e:                       # noqa: BLE001 - any gpu trouble means cpu
        print('  gpu unavailable (%s), using the cpu' % str(e)[:80], flush=True)
        return WhisperModel('large-v3', device='cpu', compute_type='int8')


def main():
    mine = cache('wc3-licensed', lambda: sys.exit('build the wc3 index once first'))
    said = cache('wc3-quotes', quotes)
    todo = sorted(set(mine) - set(said))
    print('%d clips have no quote page' % len(todo), flush=True)

    os.makedirs(CLIPS, exist_ok=True)
    urls = {a['name'].replace(' ', '_'): re.sub(r'/revision/.*$', '', a['url'])
            for a in load_audio(HOST)}
    for name in todo:
        path = os.path.join(CLIPS, name)
        if not os.path.exists(path):
            with open(path, 'wb') as f:
                f.write(get(urls[name]))

    cuda_libs()
    m = model()
    heard = {}
    for i, name in enumerate(todo):
        segs, _ = m.transcribe(os.path.join(CLIPS, name), language='en', beam_size=5,
                               condition_on_previous_text=False)
        segs = list(segs)
        heard[name] = {'text': ' '.join(s.text.strip() for s in segs).strip(),
                       'nospeech': round(max((s.no_speech_prob for s in segs), default=1), 2)}
        if i % 25 == 0:
            print('  %d/%d %s: %s' % (i, len(todo), name, heard[name]['text']), flush=True)

    with open(HEARD, 'w', encoding='utf-8') as f:
        f.write('{\n' + ',\n'.join(' %s: %s' % (json.dumps(k), json.dumps(v, ensure_ascii=False))
                                   for k, v in heard.items()) + '\n}\n')
    print('wrote', HEARD)


if __name__ == '__main__':
    main()

"""Copy a legend's whole voice set out of a local Apex install into sounds/apex/.

The wiki hosts clips for a few hundred lines; the game ships every one of them, ~5,000 a
legend once the third-person copies are left out. This pulls one legend's out of the
game's Miles sound bank with RSX (https://github.com/r-ex/rsx), encodes them as 32k mono
Opus, about 6 kB a clip, and writes what each one says to tools/apex_heard.json, which is
what sources_apex.py reads. Like transcribe_wc3.py, the index builder never runs this, so
building needs neither the game nor any of this:

    py -3.12 -m venv .local/venv
    .local/venv/Scripts/python -m pip install faster-whisper nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
    .local/venv/Scripts/python tools/rip_apex.py Bangalore "Mad Maggie"

It wants rsx_nogui.exe in .local/rsx/ (or RSX=path) and ffmpeg on the path, and finds the
game under Steam's default library unless APEX=<install dir> says otherwise. A clip already
in apex_heard.json is not transcribed again, so a second legend costs only its own clips.

A line comes as _1p, what the speaker hears, and _3p / _3p_L2, the same words with the
filtering for everyone else; the 1p one is kept, or a 3p one for the few lines that have no
1p. Left out: the efforts (grunts, breaths, pain), anything Whisper hears no words in, and
anything over MAX_SECONDS -- a line is a few seconds, and what runs longer is a season's
story vignette, 54 and 113 seconds of Octane.
"""

import glob
import json
import os
import re
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HEARD = os.path.join(HERE, 'apex_heard.json')
SOUNDS = os.path.join(ROOT, 'sounds', 'apex')
WORK = os.path.join(ROOT, '.local', 'apex')
RSX = os.environ.get('RSX') or os.path.join(ROOT, '.local', 'rsx', 'rsx_nogui.exe')
GAME = os.environ.get('APEX') or r'C:\Program Files (x86)\Steam\steamapps\common\Apex Legends'

TAKE = re.compile(r'^(.*?)(_1p|_3p_L2|_3p)\.wav$', re.I)
RANK = {'_1p': 0, '_3p': 1, '_3p_L2': 2}
MAX_SECONDS = 15
# Whisper's own estimate that a clip is not speech; above this its words are made up
NO_SPEECH = 0.6


def seconds(wav):
    """RSX writes 32-bit float wavs, which the wave module won't open."""
    with open(wav, 'rb') as f:
        f.seek(12)
        while True:
            head = f.read(8)
            if len(head) < 8:
                return 0
            cid, size = head[:4], struct.unpack('<I', head[4:])[0]
            if cid == b'fmt ':
                fmt = f.read(size)
                channels, rate = struct.unpack('<HI', fmt[2:8])
                bits = struct.unpack('<H', fmt[14:16])[0]
            elif cid == b'data':
                return size / (rate * channels * bits / 8)
            else:
                f.seek(size, 1)


def worded(h):
    return h and h['text'] and (h['nospeech'] is None or h['nospeech'] < NO_SPEECH)


def token(legend):
    """'Mad Maggie' is madmaggie in the game's file names."""
    return re.sub(r'[^a-z0-9]', '', legend.lower())


def export(legend):
    """-> {stem: wav} with one wav per line, the 1p take where there is one."""
    out = os.path.join(WORK, token(legend))
    wavs = os.path.join(out, 'audio')
    if not os.path.isdir(wavs):
        os.makedirs(out, exist_ok=True)
        # rsx leaves its cache db in the working directory
        subprocess.run([RSX, '-nogui', '-export', '--exporttypes', 'asrc', '--exportthreads', '8',
                        '--exportfilter', 'diag_mp_%s_' % token(legend), '--exportdir', out,
                        os.path.join(GAME, 'audio', 'ship', 'general.mbnk')],
                       cwd=out, check=True)
    best = {}
    for p in glob.glob(os.path.join(wavs, '*.wav')):
        m = TAKE.match(os.path.basename(p))
        if not m or '_effort_' in p or seconds(p) > MAX_SECONDS:
            continue
        if m.group(1) not in best or RANK[m.group(2)] < RANK[best[m.group(1)][1]]:
            best[m.group(1)] = (p, m.group(2))
    return {os.path.basename(p)[:-4]: p for p, _ in best.values()}


def encode(wavs):
    os.makedirs(SOUNDS, exist_ok=True)
    for i, (name, wav) in enumerate(sorted(wavs.items())):
        ogg = os.path.join(SOUNDS, name + '.ogg')
        if not os.path.exists(ogg):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', wav, '-ac', '1',
                            '-c:a', 'libopus', '-b:a', '32k', ogg], check=True)
        if i % 500 == 0:
            print('  encoded %d/%d' % (i, len(wavs)), flush=True)


def transcribe(wavs, heard):
    todo = sorted(n for n in wavs if n not in heard)
    if not todo:
        return
    # pip's nvidia packages put their dlls where Windows won't look for them
    for d in glob.glob(os.path.join(sys.prefix, 'Lib', 'site-packages', 'nvidia', '*', 'bin')):
        os.add_dll_directory(d)
        os.environ['PATH'] = d + os.pathsep + os.environ['PATH']
    from faster_whisper import WhisperModel
    m = WhisperModel('medium.en', device='cuda', compute_type='float16')
    for i, name in enumerate(todo):
        segs, _ = m.transcribe(wavs[name], language='en', beam_size=5,
                               condition_on_previous_text=False)
        segs = list(segs)
        heard[name] = {'text': ' '.join(s.text.strip() for s in segs).strip(),
                       'nospeech': round(max((s.no_speech_prob for s in segs), default=1), 2)}
        if i % 100 == 0:
            # an hour or more a legend, so a stop part way loses only the last few minutes
            save(heard)
            print('  %d/%d %s: %s' % (i, len(todo), name, heard[name]['text']), flush=True)


def save(heard):
    with open(HEARD, 'w', encoding='utf-8') as f:
        f.write('{\n' + ',\n'.join(' %s: %s' % (json.dumps(k), json.dumps(v, ensure_ascii=False))
                                   for k, v in sorted(heard.items())) + '\n}\n')


def main(legends):
    if not shutil.which('ffmpeg'):
        sys.exit('ffmpeg is not on the path')
    heard = {}
    if os.path.exists(HEARD):
        with open(HEARD, encoding='utf-8') as f:
            heard = json.load(f)
    for legend in legends:
        wavs = export(legend)
        print('%s: %d lines' % (legend, len(wavs)), flush=True)
        transcribe(wavs, heard)
        save(heard)
        encode({n: w for n, w in wavs.items() if worded(heard.get(n))})
        for n in wavs:
            ogg = os.path.join(SOUNDS, n + '.ogg')
            if not worded(heard.get(n)) and os.path.exists(ogg):
                os.remove(ogg)


if __name__ == '__main__':
    main(sys.argv[1:] or sys.exit('name the legends to rip, e.g. Bangalore'))

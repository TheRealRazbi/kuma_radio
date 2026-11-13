"""Cut Jimmy's pager lines out of a YouTube compilation into sounds/payday2/.

The Payday 2 wiki has no clips for Jimmy, so the lines come from 11Jake's "Payday 2 Jimmy
Pager Voice lines" (VIDEO below): five minutes of the pager going off and Jimmy answering
it. The lines run into each other with pauses no longer than the ones inside a line, so
there is no silence to split on; tools/payday2.json holds where each one starts and ends,
picked by hand from a Whisper transcript cut at every pause. Between Jimmy's lines are the
pager's beep and the dispatcher, both much quieter, and those are left out. So are the six
lines the video plays twice.

Each clip is cut a little wide into the pause on either side, faded at the ends, brought to
-16 LUFS (the video is quiet, about -30) with a limiter on the peaks, and written as mono
Vorbis. Like rip_apex.py, the index builder never runs this, so building needs neither yt-dlp
nor the video:

    .local/venv/Scripts/python -m pip install yt-dlp
    .local/venv/Scripts/python tools/rip_payday2.py            # downloads the video's audio
    .local/venv/Scripts/python tools/rip_payday2.py some.wav   # or cuts a copy you already have

It wants ffmpeg on the path. Re-running overwrites the clips, so a changed start or end in
payday2.json is picked up by running it again.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIST = os.path.join(HERE, 'payday2.json')
SOUNDS = os.path.join(ROOT, 'sounds', 'payday2')
WORK = os.path.join(ROOT, '.local', 'payday2')
VIDEO = 'https://www.youtube.com/watch?v=SbtlFXMFvw4'

LUFS, PEAK = -16, -1.5
FADE_IN, FADE_OUT = 0.01, 0.04
# the video is stereo with the same thing in both channels. Left to -ac 1, ffmpeg downmixes
# after the filters at 0.707 a channel, which lands 3 dB over the limiter; averaging them
# first keeps the level the filters set.
MONO = 'pan=mono|c0=0.5*c0+0.5*c1'


def download():
    os.makedirs(WORK, exist_ok=True)
    wav = os.path.join(WORK, 'jimmy-pager.wav')
    if not os.path.exists(wav):
        subprocess.run([sys.executable, '-m', 'yt_dlp', '-f', 'bestaudio', '-x',
                        '--audio-format', 'wav', '-o', os.path.join(WORK, 'jimmy-pager.%(ext)s'),
                        VIDEO], check=True)
    return wav


def loudness(src, start, end):
    """The clip's integrated loudness in LUFS, from loudnorm's measuring pass."""
    p = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-ss', str(start), '-to', str(end),
                        '-i', src, '-af', MONO + ',loudnorm=print_format=json',
                        '-f', 'null', '-'], capture_output=True, text=True, check=True)
    tail = p.stderr[p.stderr.rindex('{'):]
    return float(json.loads(tail[:tail.index('}') + 1])['input_i'])


def cut(src, item):
    start, end = item['start'], item['end']
    # one gain for the whole clip, so the level isn't ridden up and down inside a line; the
    # radio filter leaves sharp peaks that gain would push past full scale, so a limiter
    # catches those
    gain = LUFS - loudness(src, start, end)
    af = (MONO + ',afade=t=in:d=%s,afade=t=out:st=%.3f:d=%s,volume=%.2fdB,'
          'alimiter=limit=%.3f:attack=1:release=50:level=false'
          % (FADE_IN, end - start - FADE_OUT, FADE_OUT, gain, 10 ** (PEAK / 20)))
    out = os.path.join(SOUNDS, item['file'])
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-ss', str(start), '-to', str(end), '-i', src,
                    '-af', af, '-c:a', 'libvorbis', '-q:a', '4', out], check=True)
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else download()
    with open(LIST, encoding='utf-8') as f:
        items = json.load(f)
    os.makedirs(SOUNDS, exist_ok=True)
    for it in items:
        out = cut(src, it)
        print('%-40s %5.2fs %6d bytes' % (it['file'], it['end'] - it['start'],
                                          os.path.getsize(out)), flush=True)
    print('wrote %d clips to %s' % (len(items), SOUNDS))


if __name__ == '__main__':
    main()

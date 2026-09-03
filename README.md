# kuma radio

Chat-driven sound effects for Twitch. Whitelisted viewers paste a sound link in chat and it plays
on the stream.

It's one static HTML file in an OBS Browser Source. No server, no bot account, no OAuth token, and
nothing installed on the streamer's machine — they paste a URL into OBS and that's the entire setup.

Built for one streamer at their request, but nothing in it is specific to them: point it at any
channel.

## Why there's no token

Twitch IRC accepts anonymous read-only connections (`justinfan<random>` as the nick, no password),
so a plain web page can read any public channel's chat without credentials.

That's also the safe choice, not just the convenient one. The streamer loads this page in their own
browser source, so anything embedded in it is effectively theirs — and if the page is hosted
publicly, everyone's. A token put here to let the bot post in chat would be a token given away. So
the overlay reports what it's doing with an on-screen toast instead of a chat message.

Chat replies, a web control panel, or a whitelist you can edit without re-sending a URL all need a
small server that holds the token. That's deliberately out of scope here.

## Setup

**1. Host the file.** Fork or clone this repo, then Settings → Pages → deploy from `main` / root.
You'll get `https://<user>.github.io/kuma_radio/overlay.html`. Any static host works — it just has
to be a URL the streamer's OBS can load.

**2. Build the link** with the channel and the whitelist:

```
https://<user>.github.io/kuma_radio/overlay.html?channel=<channel>&users=<name1>,<name2>
```

**3. The streamer adds it in OBS:** Sources → **+** → **Browser**, paste the URL, 1920×1080, then:

- ☑ **Control audio via OBS** — this is the volume control. The overlay appears as a normal channel
  in the Audio Mixer with a fader, a mute button, and filters.
- ☐ **Shutdown source when not visible** — leave unchecked so it stays connected to chat.
- ☐ **Refresh browser when scene becomes active** — leave unchecked; it would drop the connection on
  every scene switch.

**4. Turn on monitoring, or the streamer won't hear it.** "Control audio via OBS" sends the audio to
the *stream* but defaults to **Monitor Off**, so viewers hear the sounds and the streamer doesn't.
Audio Mixer → ⋮ on the source → **Advanced Audio Properties** → **Audio Monitoring** → **Monitor and
Output**. If it's still silent, check Settings → Audio → Advanced → **Monitoring Device** points at
the right output.

If the streamer also captures Desktop Audio from the device they monitor to, "Monitor and Output"
can put the sound on stream twice, heard as an echo. In that case use **Monitor Only** and let the
Desktop Audio capture carry it to stream.

Put the source in a scene that's always live. Nothing is drawn except small toasts in the
bottom-left, and the background is transparent.

## Commands

| command | who | what |
|---|---|---|
| `!sfx <link>` | whitelist | play it |
| `!sfx vol 40` | whitelist, mods, broadcaster | set volume 0–100 |
| `!sfx vol` | whitelist, mods, broadcaster | show current volume |
| `!sfx stop` / `!sfx skip` | whitelist, mods, broadcaster | cut the current sound |
| `!sfx clear` | whitelist, mods, broadcaster | drop everything queued |

Links that work:

- a **`File:` page on any Fandom wiki** — the file page, not the article. Tested on the Darkest
  Dungeon, League of Legends and Warcraft wikis:
  - `https://darkestdungeon.fandom.com/wiki/File:Affliction_abusive.ogg`
  - `https://leagueoflegends.fandom.com/wiki/File:Ahri_Ban.ogg`
  - `https://warcraft.fandom.com/wiki/File:GhoulDinner.wav`
- any direct audio link ending in `.ogg .mp3 .wav .m4a .opus .flac .aac .webm`

Finding those links by hand is the tedious part, so there's a second page for it —
see [Finding sounds](#finding-sounds).

Use the **underscore** form of the URL, which is what the address bar gives you. A URL pasted with
literal spaces gets cut at the first space, since chat can't tell a URL with spaces from a URL
followed by a comment. When that happens the overlay says `no file called "Ahri"` — a title that's
obviously too short is the tell.

Long clips are cut off at `maxlen` (15s by default). Plenty of wiki audio is longer than that —
LoL recall music runs 10s and up — so raise it if things are getting clipped.

## Finding sounds

Hunting for a clip is harder than playing one. The League wiki plays its audio through a
JavaScript widget with no right-click-copy, so getting a usable link out of it means reading the
page source, and no wiki here lets you search for a line by what is actually said in it.

`sfx.html` is a second static page that does that work ahead of time:

```
https://<user>.github.io/kuma_radio/sfx.html
```

Type what you remember hearing — `nobody touches the hat` — press **▶** to check it's the right
clip, then **copy**, which puts `!sfx <link>` on the clipboard ready to paste in chat. Or pick a
champion or a character and browse everything they say.

| source | clips | with a transcript | browse by |
|---|---|---|---|
| League of Legends | 75,980 | 75,966 | champion, skin, category |
| Darkest Dungeon 1 & 2 | 821 | 622 | character, game, category |
| Warcraft III | 2,233 | none | unit, campaign, response type |

**Warcraft III is the weak one, and it's worth saying why.** Nothing on the Warcraft wiki
writes down what these clips say, so there is nothing to search by phrase — searching WC3
searches file names. The names are the game's own, though, so they carry a lot: `GhoulDinner`,
`ArcherPissed3` (Blizzard's word for the lines a unit says when you keep clicking it),
`A07Illidan13`. Browsing by unit and response type is the way in, and the response codes are
translated — "Annoyed", "Selected", "Ordered to attack" — so the dropdowns read like English.

Details worth knowing:

- The **command** box changes the `!sfx` prefix if the channel uses a different one, and **copy the
  link only** drops the command word entirely.
- Filters live in the URL, so `sfx.html#s=lol&g=Braum` links straight to every Braum line.
- Clip length shows up next to a clip once you've previewed it — the wikis don't publish
  durations, and the overlay cuts anything past `maxlen`.
- No audio is copied into this repo. The index holds names, quotes and links; previews and the
  overlay both stream from the wikis.

### Rebuilding the index

`index/*.json` is committed, so the page needs no server and no build step to run. Regenerate it
when a wiki gains content:

```bash
python tools/build_index.py
```

Standard library only, and a full run takes half an hour or so. It has to page through *every*
image on each wiki — `filetype:audio` search returns jpgs on these wikis and MIME filtering is
switched off in miser mode, so there is no shortcut — and then read the article wikitext that
pairs each clip with the line said in it. Responses are cached under `tools/.cache`, so a second
run is quick; delete that folder to force a refetch. Fandom rate-limits hard, and two crawls at
once is enough to trip it, so let one finish before starting the next.

## Custom sounds

Not everything is on a wiki, and the overlay can't play YouTube or Spotify links — it needs a direct
audio file. Drop your own into `sounds/` and GitHub Pages serves them alongside the overlay:

```
https://<user>.github.io/kuma_radio/sounds/braum-nu-pierde.ogg
```

Two rules for the filename: **no spaces** (use hyphens — a URL with spaces gets cut at the first
one), and prefer **`.ogg`**, which decodes in every OBS build. To convert anything to Ogg:

```bash
ffmpeg -i input.mp3 -c:a libvorbis -q:a 5 sounds/output.ogg
```

Sounds play one at a time; extras wait in a queue. The volume set with `!sfx vol` is remembered
across restarts, and a remembered value beats the `vol=` in the URL — so once it's been set from
chat, keep changing it from chat. The OBS fader is independent of both and always wins.

## URL options

| param | default | |
|---|---|---|
| `channel` | — | **required** — the channel whose chat to read |
| `users` | — | **required** — comma-separated, who may play sounds |
| `vol` | `50` | starting volume, 0–100 |
| `maxlen` | `15` | hard cutoff in seconds, so nobody parks a long file on the stream |
| `cooldown` | `3` | per-user seconds between sounds |
| `queue` | `5` | max sounds waiting |
| `mods` | `0` | `1` lets any mod play sounds, not just the whitelist |
| `prefix` | `!sfx` | change the command word |
| `overlap` | `0` | `1` plays sounds on top of each other instead of queueing |
| `quiet` | `0` | `1` hides the toasts entirely |
| `debug` | `0` | `1` shows a status panel — use this while setting up |

## Testing it on your own channel

The overlay only *reads* chat, so you can test the whole thing against your own channel without
involving anyone else. Point `channel` at yourself, put yourself in `users`, and type in your own
chat:

```
overlay.html?channel=<you>&users=<you>&debug=1
```

`debug=1` shows a status panel: a **green dot and "live"** means it's connected and reading chat.
It'll also show the last thing that happened, which is usually enough to tell a rejected link from
a permissions problem.

To test without publishing anything, serve the folder locally and open it in a browser:

```bash
python -m http.server 8791
```

then `http://localhost:8791/overlay.html?channel=<you>&users=<you>&debug=1`.

In a normal browser tab you have to click once before audio is allowed — that's the browser's
autoplay policy. OBS browser sources don't need the click.

## Known gotchas

**Chat link blocking.** If the channel has "Block hyperlinks" enabled in AutoMod, non-exempt users'
messages are held before anyone sees them and never reach IRC — so the overlay receives nothing and
there is nothing to debug; it just silently does nothing. Give whitelisted users **VIP or mod**,
which exempts them.

**Codecs.** `.ogg` and `.wav` always work. `.mp3` works on current OBS builds, but has been missing
from stripped-down CEF builds in the past — if mp3s are silent and oggs aren't, that's why.

**The whitelist lives in the URL,** so adding someone means giving the streamer a new URL. Fine for a
few people; past that it's the point to move the list server-side.

**Fandom / Wikia links** have two traps, both handled, both worth knowing if you adapt this:

- `/wiki/File:Foo.ogg` is an HTML page whose URL happens to end in `.ogg`. Feed it to an `<audio>`
  element and you get a decode error, so the wiki API lookup has to run *before* any file-extension
  check.
- Wikia's CDN returns 404 and a small JPEG placeholder for audio at
  `.../Foo.ogg/revision/latest?cb=...` — that URL form only works for images. It is also exactly
  what the wiki API hands back, so URLs get trimmed to the bare path, which serves the real file.

## Not included

Each of these needs a server, which is what v1 avoids:

- a web panel to paste links from instead of chat (would also sidestep chat link blocking)
- bot replies in chat confirming what played
- editing the whitelist without re-sending a URL
- channel point redemptions instead of chat commands

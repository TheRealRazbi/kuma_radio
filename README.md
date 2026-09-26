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

**Picking up a new version.** The streamer's OBS holds the copy it last downloaded, so pushing a
change here doesn't reach them on its own. Switching scenes doesn't fetch it either, with
*Refresh browser when scene becomes active* left unchecked as above. To pull the latest: right-click
the source → **Properties** → **Refresh cache of current page**. That re-downloads the page
ignoring the cached copy; it does not touch the remembered volume and cutoff, which live in local
storage. Closing and reopening OBS works too.

## Commands

| command | who | what |
|---|---|---|
| `!sfx <link>` | whitelist | play it |
| `!sfx <link> 1:05` | whitelist | play it from 1:05 in |
| `!sfx vol 40` | whitelist, mods, broadcaster | set volume 0–100 |
| `!sfx vol` | whitelist, mods, broadcaster | show current volume |
| `!sfx stop` / `!sfx skip` | whitelist, mods, broadcaster | cut the current sound |
| `!sfx clear` | whitelist, mods, broadcaster | drop everything queued |
| `!sfx maxlen 30` | mods, broadcaster | set the cutoff in seconds, 0.5–300 |
| `!sfx maxlen` | mods, broadcaster | show the current cutoff |

`maxlen` is the leash on how long one person can hold the stream, so unlike the other controls it
is **mods and the broadcaster only** — not the whitelist, who would otherwise be lengthening their
own leash. It applies to the sound already playing too, so if something is being cut off mid-word,
raising it rescues that sound rather than needing it played again.

Links that work:

- a **`File:` page on any Fandom wiki** — the file page, not the article. Tested on the Darkest
  Dungeon, League of Legends, Overwatch, StarCraft and Warcraft wikis:
  - `https://darkestdungeon.fandom.com/wiki/File:Affliction_abusive.ogg`
  - `https://leagueoflegends.fandom.com/wiki/File:Ahri_Ban.ogg`
  - `https://overwatch.fandom.com/wiki/File:D.Va_-_Nerf_this.ogg`
  - `https://starcraft.fandom.com/wiki/File:Marine_What00.ogg`
  - `https://warcraft.fandom.com/wiki/File:GhoulDinner.wav`

  Language wikis work too, whatever the namespace is called there:
  `https://leagueoflegends.fandom.com/fr/wiki/Fichier:Rammus.provocation01.ogg`
- any direct audio link ending in `.ogg .mp3 .wav .m4a .opus .flac .aac .webm`

Finding those links by hand is the tedious part, so there's a second page for it —
see [Finding sounds](#finding-sounds).

Use the **underscore** form of the URL, which is what the address bar gives you. A URL pasted with
literal spaces gets cut at the first space, since chat can't tell a URL with spaces from a URL
followed by a comment. When that happens the overlay says `no file called "Ahri"` — a title that's
obviously too short is the tell.

Long clips are cut off at `maxlen` (15s by default). Plenty of wiki audio is longer than that —
LoL recall music runs 10s and up — so raise it with `!sfx maxlen 30` if things are getting clipped.
The new value is remembered across restarts, the same way `!sfx vol` is.

### Starting part-way in

A number after the link is where to start, as seconds (`30`, `12.5`) or `m:ss` (`1:05`, `2:07.5`):

```
!sfx https://leagueoflegends.fandom.com/wiki/File:Aatrox_Original_SFX_Recall.ogg 5
```

That is the way to play something longer than `maxlen` on a stream where raising the cutoff is not
an option — send the clip once per chunk and let the queue run them back to back:

```
!sfx <link> 0
!sfx <link> 15
!sfx <link> 30
```

The cutoff is counted from where playback starts, so each of those plays a full `maxlen` seconds.
Chunks are separate files playing one after another, so expect a small gap at each seam — this
gets a long clip heard, not a seamless one.

Two things to watch: `cooldown` (3s by default) is per user and applies to each message, so with the
default the chunks have to be typed a few seconds apart, and the queue holds `queue` of them (5).
Lower the cooldown or raise the queue in the URL if a long chain keeps getting dropped.

Anything after the link that isn't a time is ignored, so `!sfx <link> loud one` still plays from the
start. A start past the end of the file says so instead of playing silence.

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
| — in Polski | 29,304 | 28,641 | champion, category |
| — in Español | 9,943 | 5,500 | champion, category |
| — in Português (Brasil) | 7,270 | 5,437 | champion, skin, category |
| — in Français | 6,047 | 5,895 | champion, category |
| — in Čeština | 938 | 938 | champion, category |
| Overwatch 1 & 2 | 39,834 | 39,637 | hero, game, category |
| Darkest Dungeon 1 & 2 | 821 | 622 | character, game, category |
| Warcraft III | 2,233 | 2,231 | unit, campaign, response type |
| StarCraft II | 3,977 | 3,977 | unit, race, category |
| Saved | 2 | 2 | game, character, category |

**Saved is a hand-picked list** for games not worth indexing whole — the Hearthstone pack
opening's "Wooah, Legendary!", SI:7 Agent's "Heh, this guy's toast." It lives in
`tools/saved.json`, one entry per clip, and holds links only, never audio: a wiki `File:` page
is looked up for its file and pasted in chat as is, and any other link (a `sounds/` file, a
direct audio url) is used as given. Add an entry, then `python tools/build_index.py saved`.

**Overwatch is the tidiest of the big ones.** Every hero, map and mission has a `/Quotes` page,
and those pages are tables with the line in one column and the clip in the next, so all but a
few hundred clips come with the words. Interactions pair up line for line, which is why Ana's
half of a conversation is filed under Ana even though it was read off Tracer's page. The game
box separates the two games: a line still in Overwatch 2 is listed as such, and *Overwatch 1*
is roughly the set that was cut. The wiki writes up more lines than it has files for, so about
9,000 of them are dropped rather than shipped as dead play buttons.

**Warcraft III gets its words from two places.** The wiki's *Quotes of Warcraft III* pages tag
each line with the file that says it, which covers every unit and hero — about 2,060 clips,
including the ones people hunt for: `ArcherPissed3` is Blizzard's name for a line a unit says when
you keep clicking it, filed here as "Annoyed (clicked too often)". The other 170-odd, mostly
campaign dialogue plus Furion and the morphed Demon Hunter, are on no page at all, so they were
put through speech recognition once and the result is committed in `tools/wc3_heard.json`. Where
that heard line is one the wiki spells out elsewhere — Furion's lines are Malfurion's, and
"For King Terranus" is Uther's "For King Terenas!" — the wiki's spelling is used; the rest are
marked **by ear** next to the file name. Whole sentences come back word for word; it is the
grunts and the invented languages it can't spell. Two clips, a ghoul eating and a villager's cry, have
no words at all.

**StarCraft II is small but complete.** The StarCraft wiki keeps each unit's lines in a quote
box — selected, move order, attack order, repeatedly selected — with the clip and its words
side by side, so every clip comes with a transcript. That covers the units and heroes of all
three races across Versus, the campaigns and Co-op, and the section plus any variant (the
female Ghost, Tychus in the Odin) is shown next to each clip. The wiki's campaign and Co-op
mission transcripts have no clips attached, so story dialogue isn't in here.

Details worth knowing:

- The **command** box changes the `!sfx` prefix if the channel uses a different one, and **copy the
  link only** drops the command word entirely.
- **League opens on the Original skin**, because a skin with its own voice-over re-records most of
  the base lines — Lulu's 117 clips are 40 lines said three times over. Switch the skin box to
  *every skin* to see the alternates; the choice sticks as you move between champions. Darkest
  Dungeon, Overwatch, StarCraft II and Warcraft III have no Original, so they open
  unfiltered.
- **League comes in other languages** — French, Spanish, Polish, Brazilian Portuguese and
  Czech — from a language box next to the search once League is picked. Each language wiki
  uploads its own recordings, so coverage is whatever that wiki got round to: Polish has nearly
  every champion, Brazilian Portuguese has 25 of them in depth, Czech only 21 and those from the
  old 2014 voice-overs. French also has a few champions whose quote pages were deleted but whose
  clips are still up (Ahri, Aatrox, Gangplank, Leona, Zeri): those are found by file name, so
  they're sorted into Attaque, Rire and so on but have no transcript. Spanish has both the Latin American and the Spain dubs, marked LATAM and
  EUW. Champions keep their English names in every language, so switching language keeps the
  champion you were looking at. Search ignores accents: `deja` finds `déjà`.
- Filters live in the URL, so `sfx.html#s=lol&g=Braum` links straight to every Braum line, and
  `#s=lol-fr&g=Rammus` to every French one.
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

Or name the sources to rebuild — `lol`, `ow`, `dd`, `wc3`, and `lol-fr`, `lol-es`, `lol-pl`,
`lol-pt-br`, `lol-cs` for League's language wikis (listed in `tools/sources_lol.py`).

Standard library only, and a full run takes half an hour or so. It has to page through *every*
image on each wiki — `filetype:audio` search returns jpgs on these wikis and MIME filtering is
switched off in miser mode, so there is no shortcut — and then read the article wikitext that
pairs each clip with the line said in it. Responses are cached under `tools/.cache`, so a second
run is quick; delete that folder to force a refetch. Fandom rate-limits hard, and two crawls at
once is enough to trip it, so let one finish before starting the next.

The one step that isn't stdlib is `tools/transcribe_wc3.py`, which rewrites
`tools/wc3_heard.json` and needs `faster-whisper` in a venv of its own (setup in its docstring).
The builder only reads the json, so this is only worth rerunning when the Warcraft quote pages
change which clips they cover.

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
chat, keep changing it from chat. `!sfx maxlen` works the same way. The OBS fader is independent of
both and always wins.

Both are remembered in the browser source's local storage, keyed by channel. That survives an OBS
restart, a page refresh, and even deleting and re-adding the source, because the storage belongs to
the page's origin rather than to the source. It is lost only if OBS's browser cache folder
(`%APPDATA%\obs-studio\plugin_config\obs-browser`) is deleted, and then they fall back to the
`vol=` and `maxlen=` in the URL.

## URL options

| param | default | |
|---|---|---|
| `channel` | — | **required** — the channel whose chat to read |
| `users` | — | **required** — comma-separated, who may play sounds |
| `vol` | `50` | starting volume, 0–100 |
| `maxlen` | `15` | starting hard cutoff in seconds, so nobody parks a long file on the stream |
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

**Fandom / Wikia links** have three traps, all handled, all worth knowing if you adapt this:

- `/wiki/File:Foo.ogg` is an HTML page whose URL happens to end in `.ogg`. Feed it to an `<audio>`
  element and you get a decode error, so the wiki API lookup has to run *before* any file-extension
  check.
- Wikia's CDN returns 404 and a small JPEG placeholder for audio at
  `.../Foo.ogg/revision/latest?cb=...` — that URL form only works for images. It is also exactly
  what the wiki API hands back, so URLs get trimmed to the bare path, which serves the real file.
- A language wiki's file comes back as `.../leagueoflegends/images/...?path-prefix=fr`. Trimming
  the query throws the language away and the CDN looks on the English wiki, which 404s. The
  language has to move into the path instead: `.../leagueoflegends/fr/images/...`. The same goes
  for the API itself, which for `/fr/wiki/Fichier:...` lives at `/fr/api.php`.

## License and attribution

The code in this repository — the overlay, the finder, and the indexer — is MIT licensed. See
[LICENSE](LICENSE). Fork it, host it, change it.

**That licence covers the code only.** It does not cover the audio, which this project never
copies: `index/*.json` holds names, quotes and links, and both pages stream the files from the
wikis that host them. The clips themselves remain the property of their respective owners, and
the transcripts come from the wikis under their own licences.

kuma radio was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot
Games. Riot Games does not endorse or sponsor this project.

Warcraft III, Overwatch and StarCraft II audio are the property of Blizzard Entertainment;
Darkest Dungeon audio is the property of Red Hook Studios. This project is unaffiliated with,
and unendorsed by, any of them.

## Not included

Each of these needs a server, which is what v1 avoids:

- a web panel to paste links from instead of chat (would also sidestep chat link blocking)
- bot replies in chat confirming what played
- editing the whitelist without re-sending a URL
- channel point redemptions instead of chat commands

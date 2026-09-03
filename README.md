# kuma radio

Whitelisted people paste a sound link in the streamer's Twitch chat, the sound plays on stream.

One static HTML file. No server, no bot account, no token, nothing installed on the streamer's PC —
he pastes a URL into an OBS Browser Source and that's the whole setup.

## Why there's no token

Twitch IRC accepts anonymous read-only connections (`justinfan<random>` as the nick, no password),
so a plain web page can read any public channel's chat. A token is only needed to *send* messages.

That's not just convenience — it's the safe choice. Whatever page the streamer loads, he can
view-source. A token embedded in it to make the bot reply in chat would be handed to him and to
anyone else who ever gets the link. So the overlay reports what it's doing with an on-screen toast
instead of a chat message. If chat replies are wanted later, that needs a small server that holds
the token, never the overlay.

## Setup

**1. Publish the file.** Push `overlay.html` to a GitHub repo, then Settings → Pages → deploy from
`main` / root. You get `https://<you>.github.io/<repo>/overlay.html`. Any static host works; it just
has to be a URL the streamer can load.

**2. Send him this link** (his channel, your whitelist):

```
https://<you>.github.io/<repo>/overlay.html?channel=lessvalgaav&users=razbith3player
```

**3. He adds it in OBS:** Sources → **+** → **Browser**, paste the URL, 1920×1080, then:

- ☑ **Control audio via OBS** — this is the volume slider. The overlay shows up as a normal channel
  in his Audio Mixer with a fader, a mute button, and filters. Nothing to learn.
- ☐ **Shutdown source when not visible** — leave unchecked so it stays connected to chat.
- ☐ **Refresh browser when scene becomes active** — leave unchecked, it would drop the connection
  on every scene switch.

Put the source in a scene that's always live so it never disconnects. Nothing is drawn except small
toasts in the bottom-left; the background is transparent.

## Using it

| command | who | what |
|---|---|---|
| `!sfx <link>` | whitelist | play it |
| `!sfx vol 40` | whitelist, mods, streamer | set volume 0–100 |
| `!sfx vol` | whitelist, mods, streamer | show current volume |
| `!sfx stop` / `!sfx skip` | whitelist, mods, streamer | cut the current sound |
| `!sfx clear` | whitelist, mods, streamer | drop everything queued |

Links that work:

- a Darkest Dungeon wiki file page — `https://darkestdungeon.fandom.com/wiki/File:Affliction_abusive.ogg`
- any direct audio link ending in `.ogg .mp3 .wav .m4a .opus .flac .aac .webm`

Wiki `File:` pages are HTML, not audio, so the overlay asks the wiki's API for the real file URL
first. Works on any Fandom wiki, not just Darkest Dungeon.

Sounds play one at a time; extras wait in a queue. `!sfx vol` is remembered across restarts, and a
remembered value beats the `vol=` in the URL — so once it's been set from chat, change it from chat
(or from the OBS fader, which is independent of both).

## URL options

| param | default | |
|---|---|---|
| `channel` | — | **required**, the streamer's channel |
| `users` | — | **required**, comma-separated, who may play sounds |
| `vol` | `50` | starting volume, 0–100 |
| `maxlen` | `15` | hard cutoff in seconds, so nobody parks a long file on the stream |
| `cooldown` | `3` | per-user seconds between sounds |
| `queue` | `5` | max sounds waiting |
| `mods` | `0` | `1` lets any mod play sounds, not just the whitelist |
| `prefix` | `!sfx` | change the command word |
| `overlap` | `0` | `1` plays sounds on top of each other instead of queueing |
| `quiet` | `0` | `1` hides the toasts entirely |
| `debug` | `0` | `1` shows a status panel — use this while setting up |

Open the URL with `&debug=1` in a normal browser to check it: a **green dot and "live"** means it's
reading chat. In a browser tab you have to click once to allow audio — OBS doesn't need that.

## Things that will bite you

**Chat link blocking.** If the channel has "Block hyperlinks" on in AutoMod, your messages get held
before anyone sees them and the overlay never receives them. Held messages don't reach IRC at all,
so there's nothing to debug — it just silently does nothing. Fix: have him make the whitelisted
users **VIP or mod**, which exempts them.

**Codecs.** `.ogg` and `.wav` always work. `.mp3` works on current OBS builds but has been missing
from stripped-down CEF builds in the past — if mp3s are silent and oggs aren't, that's why.

**Whitelist is in the URL,** so adding a person means sending him a new URL. Fine for two or three
people. If it grows, that's the moment to move the list server-side.

## What v1 deliberately doesn't do

Everything above is client-side, which is why it's this simple. These each need a small server:

- a web panel to paste links from instead of chat (would also dodge the link-blocking problem)
- bot replies in chat confirming what played
- editing the whitelist without re-sending a URL
- a per-sound volume/mute UI for the streamer beyond the OBS fader
- channel point redemptions instead of chat commands

## Tested

Against `#lessvalgaav` live chat: anonymous connect, wiki `File:` resolution, real ogg playback,
queueing, mid-playback volume change, skip, cooldown, and rejection of both non-whitelisted users
and non-audio links.

Two bugs found and fixed during that:

- `/wiki/File:Foo.ogg` ends in `.ogg`, so it matched the direct-audio check and the overlay tried to
  play an HTML page as audio. The wiki lookup now runs first.
- Wikia's CDN 404s audio at `.../Foo.ogg/revision/latest?cb=...` and returns a JPEG placeholder —
  that URL form only works for images. It's also the URL the wiki API hands back. Wikia links are
  now trimmed to the bare path, which serves the real file.

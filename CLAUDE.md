# CLAUDE.md

Fork of [DubStage](https://github.com/xmrius/dubstage), a dubbing tool modelled on the "Dub Mode" of *The Choicer Voicer*. This fork adds **co-op multiplayer**: friends join over the internet and split a scene's lines between them.

## What's in the repo

| File | Role |
|---|---|
| `DubForge.pyw` / `dubforge_core.py` | Builds dub packs from a video (clip detection, Demucs, captions). |
| `DubStage.pyw` | Tkinter game: menu → stage (record per line) → finale. Everything is drawn on one `Canvas`; screens are `show_menu`, `build_lobby`, `build_stage`, `build_finale`. |
| `dubstage_core.py` | Game logic without GUI: `load_pack`, `Line`, `render_dub`, `Mic`, `read_wav_mono`/`write_wav_mono`. |
| `dubstage_net.py` | Multiplayer: `Room` (host state), `Server` (HTTP), `Client`, pack zip/extract, `auto_assign`, Cloudflare quick tunnel. |
| `transcription.py`, `caption_pack.py` | Optional Whisper captions. |
| `updater.py`, `installer/` | Self-update and Windows installer. |
| `tests/` | `unittest` suite. |

## Multiplayer design

- **Transport.** Plain HTTP + JSON with long-polling (`GET /state?since=V`) and the stdlib only. It has to work through Cloudflare quick tunnels, which only carry HTTP(S). Don't introduce WebSockets or raw TCP.
- **Host.** The host runs `Server` and talks to it as a normal `Client` over `127.0.0.1`. Host-only actions (assign, start, back to lobby) call `Room` methods directly and are not HTTP endpoints.
- **Auth.** Every request carries `X-Room` (room code) and `X-Token` (per player). Takes can only be uploaded by the line's owner. Line names are validated against the pack and are never used as paths.
- **Takes.** Each client records locally, uploads WAV bytes, and fetches the others' takes when the state's `takes[file].rev` changes. Each client renders its finale locally with `ds.render_dub`.
- **Packs.** Guests download them into `packs/_net/<name>-<hash8>/`.
- **Single-player.** In `DubStage.pyw`, everything multiplayer is gated on `self.net` (a `NetSession`). With `self.net is None` the app must behave exactly like upstream.
- **Threading.** Network calls never run on the Tk thread. Use `_run_bg` / `_net_bg`. Results come back through `self.msgq` and `_pump`.

## Conventions

- **Commits.** Use Conventional Commits (`feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`), optionally scoped (`feat(net): …`). Keep commits small and focused on one logical step.
- **Branches.** Work on feature branches (e.g. `feature/multiplayer`) and keep `main` clean.
- **Code style.** Match the existing style. Comments are short and often German, with English in docstrings where upstream does that. UI strings go into the `T` dict in **both** German and English.
- **Docs.** `README_EN.md` and `LIESMICH.md` are kept in sync (EN/DE). User-facing changes get a `CHANGELOG.md` entry under `[Unreleased]`.
- **Line endings.** Text files are LF (`.gitattributes`). On Windows, write files with `newline=""` or normalize to LF before committing.
- **Dependencies.** No new runtime dependencies without a good reason. The installer bundles `requirements.txt`.

## Testing

```bash
py -m unittest discover tests
```

- `tests/test_net.py` starts a real `Server` on port 0 and covers joining, room-code rejection, take exchange, ownership checks, pack download/hash, long-polling and host shutdown.
- For a GUI check, run two DubStage instances: host in one, join `127.0.0.1:47800` in the other. The microphone needs `sounddevice`; `py -m pip install -r requirements.txt`.
- Hosting binds `0.0.0.0`, so Windows Firewall asks once whether Python may use the network.

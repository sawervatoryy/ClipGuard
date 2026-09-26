# 🔒 ClipGuard

**A clipboard history manager that cleans up after itself.**

ClipGuard quietly records what you copy so you can search and reuse it later - but the moment it notices something that *looks* sensitive (a password, an API key, a credit card number, a private key, a JWT), it flags it and automatically scrubs it from the stored history after a short grace period. No cloud sync, no telemetry - everything lives in a local JSON file on your machine.

## Why

Clipboard managers are genuinely useful, right up until you paste a password or an API token and it sits in plaintext history forever. ClipGuard keeps the convenience and removes that specific risk.

## Install

```bash
git clone https://github.com/<you>/clip-guard.git
cd clip-guard
pip install -r requirements.txt
```

Requires Python 3.8+. Works on macOS, Windows, and Linux (Linux may need `xclip` or `xsel` installed for clipboard access — `sudo apt install xclip`).

## Usage

Start the watcher (run it in a spare terminal tab, or set it up as a background service — see below):

```bash
python clipguard.py start
```

```
ClipGuard watching clipboard (poll every 1.0s).
Sensitive entries auto-redact after 2 min.
Press Ctrl+C to stop.

[captured]
[captured] (password_label detected — will auto-redact)
```

Other commands:

```bash
python clipguard.py list              # show the last 20 entries
python clipguard.py list --limit 100  # show more
python clipguard.py search "invoice"  # search history text
python clipguard.py clean             # run a cleanup pass immediately
python clipguard.py clear             # wipe everything
```

## What counts as "sensitive"

Out of the box, ClipGuard flags:

- Credit card–shaped number sequences
- Common API key prefixes (`sk-`, `AKIA`, `ghp_`, Slack `xox*` tokens, etc.)
- JWTs (`eyJ...`)
- Anything that looks like `password: ...` or `password=...`
- PEM-style private key blocks
- SSH public keys

Flagged entries are still searchable and usable normally — they're only redacted (replaced with a `[redacted]` placeholder) once the grace period passes, so a password you copy and paste right away still works like any other clipboard manager entry. It just won't sit around afterward.

## Configuration

On first run, ClipGuard creates `~/.clipguard/config.json` (see `config.example.json`

History is stored at `~/.clipguard/history.json`.

## Running it in the background

**macOS/Linux (simple):**
```bash
nohup python clipguard.py start > ~/.clipguard/watcher.log 2>&1 &
```

**Linux (systemd user service):** create `~/.config/systemd/user/clipguard.service` pointing at the script, then `systemctl --user enable --now clipguard`.

**Windows:** use Task Scheduler to run `pythonw clipguard.py start` at login.

## Project structure

```
clip-guard/
├── clipguard.py           # the whole tool
├── requirements.txt
├── config.example.json
└── README.md
```

## Limitations

- Pattern matching is heuristic — it won't catch everything sensitive, and may occasionally flag something harmless. Treat it as a safety net, not a guarantee.
- It only cleans its *own* history file — it doesn't touch your OS clipboard managers or other apps.

## License

MIT — do whatever you want with it.

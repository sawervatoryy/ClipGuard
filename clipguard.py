#!/usr/bin/env python3
"""
ClipGuard — a clipboard history manager that automatically scrubs
sensitive-looking data (passwords, API keys, card numbers, tokens)
out of its own history after a short grace period.

Usage:
    clipguard start                 # run the watcher (foreground)
    clipguard list [--limit N]      # show recent history
    clipguard search TERM           # search history text
    clipguard clean                 # run one cleanup pass now
    clipguard clear                 # wipe all history
"""

import argparse
import json
import re
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pyperclip
except ImportError:
    print("Missing dependency. Run: pip install -r requirements.txt")
    sys.exit(1)

APP_DIR = Path.home() / ".clipguard"
HISTORY_FILE = APP_DIR / "history.json"
CONFIG_FILE = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "poll_interval_seconds": 1.0,
    "sensitive_clean_after_minutes": 2,
    "normal_retain_days": 14,
    "max_entries": 500,
    "patterns": {
        "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
        "api_key_generic": r"\b(sk|pk|AKIA|ghp|xox[baprs])[A-Za-z0-9_-]{10,}\b",
        "jwt": r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
        "password_label": r"(?i)\bpassword\s*[:=]\s*\S+",
        "private_key_block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        "ssh_key": r"\bssh-(rsa|ed25519) [A-Za-z0-9+/=]{20,}",
    },
}

REDACTED_LABEL = "[redacted — sensitive content auto-cleaned]"


def ensure_app_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text("[]")


def load_config():
    ensure_app_dir()
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError:
        cfg = {}
    merged = {**DEFAULT_CONFIG, **cfg}
    merged["patterns"] = {**DEFAULT_CONFIG["patterns"], **cfg.get("patterns", {})}
    return merged


def load_history():
    ensure_app_dir()
    try:
        return json.loads(HISTORY_FILE.read_text())
    except json.JSONDecodeError:
        return []


def save_history(entries):
    HISTORY_FILE.write_text(json.dumps(entries, indent=2))


def compile_patterns(cfg):
    return {name: re.compile(pat) for name, pat in cfg["patterns"].items()}


def classify(text, compiled_patterns):
    """Return the name of the first matching sensitive pattern, or None."""
    for name, pattern in compiled_patterns.items():
        if pattern.search(text):
            return name
    return None


def add_entry(text, cfg, compiled_patterns):
    entries = load_history()

    if entries and entries[-1].get("text") == text:
        return entries  # skip exact duplicate of last clip

    sensitive_type = classify(text, compiled_patterns)
    entry = {
        "id": str(uuid.uuid4()),
        "text": text,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "sensitive": sensitive_type,
        "redacted": False,
    }
    entries.append(entry)

    max_entries = cfg.get("max_entries", 500)
    if len(entries) > max_entries:
        entries = entries[-max_entries:]

    save_history(entries)
    return entries


def clean_pass(cfg, verbose=True):
    entries = load_history()
    now = datetime.now()
    sensitive_cutoff = timedelta(minutes=cfg.get("sensitive_clean_after_minutes", 2))
    normal_cutoff = timedelta(days=cfg.get("normal_retain_days", 14))

    changed = 0
    kept = []
    for e in entries:
        ts = datetime.fromisoformat(e["ts"])
        age = now - ts

        if e.get("sensitive") and not e.get("redacted"):
            if age >= sensitive_cutoff:
                e["text"] = REDACTED_LABEL
                e["redacted"] = True
                changed += 1
            kept.append(e)
        elif not e.get("sensitive") and age >= normal_cutoff:
            changed += 1  # dropped entirely
            continue
        else:
            kept.append(e)

    save_history(kept)
    if verbose and changed:
        print(f"Cleaned {changed} entr{'y' if changed == 1 else 'ies'}.")
    return kept


def cmd_start(args):
    cfg = load_config()
    compiled = compile_patterns(cfg)
    ensure_app_dir()
    print(f"ClipGuard watching clipboard (poll every {cfg['poll_interval_seconds']}s).")
    print(f"Sensitive entries auto-redact after {cfg['sensitive_clean_after_minutes']} min.")
    print("Press Ctrl+C to stop.\n")

    last_seen = None
    last_clean = time.time()

    try:
        while True:
            try:
                current = pyperclip.paste()
            except Exception:
                current = None

            if current and current != last_seen:
                last_seen = current
                add_entry(current, cfg, compiled)
                tag = classify(current, compiled)
                if tag:
                    print(f"[captured] ({tag} detected — will auto-redact)")
                else:
                    print("[captured]")

            if time.time() - last_clean > 30:
                clean_pass(cfg, verbose=False)
                last_clean = time.time()

            time.sleep(cfg.get("poll_interval_seconds", 1.0))
    except KeyboardInterrupt:
        print("\nStopped.")


def cmd_list(args):
    cfg = load_config()
    clean_pass(cfg, verbose=False)
    entries = load_history()
    entries = entries[-args.limit:]
    if not entries:
        print("No history yet.")
        return
    for e in entries:
        preview = e["text"].replace("\n", " ")[:80]
        flag = f" ⚠ {e['sensitive']}" if e.get("sensitive") and not e.get("redacted") else ""
        print(f"{e['ts']}  {preview}{flag}")


def cmd_search(args):
    cfg = load_config()
    clean_pass(cfg, verbose=False)
    entries = load_history()
    term = args.term.lower()
    matches = [e for e in entries if term in e["text"].lower()]
    if not matches:
        print("No matches.")
        return
    for e in matches:
        preview = e["text"].replace("\n", " ")[:100]
        print(f"{e['ts']}  {preview}")


def cmd_clean(args):
    cfg = load_config()
    clean_pass(cfg, verbose=True)


def cmd_clear(args):
    save_history([])
    print("History cleared.")


def main():
    parser = argparse.ArgumentParser(prog="clipguard", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("start", help="Watch the clipboard and record history")

    p_list = sub.add_parser("list", help="Show recent history")
    p_list.add_argument("--limit", type=int, default=20)

    p_search = sub.add_parser("search", help="Search clipboard history")
    p_search.add_argument("term")

    sub.add_parser("clean", help="Run a cleanup pass now")
    sub.add_parser("clear", help="Wipe all history")

    args = parser.parse_args()
    {
        "start": cmd_start,
        "list": cmd_list,
        "search": cmd_search,
        "clean": cmd_clean,
        "clear": cmd_clear,
    }[args.command](args)


if __name__ == "__main__":
    main()

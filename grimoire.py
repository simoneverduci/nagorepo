#!/usr/bin/env python3
"""
grimoire.py — Nago's digital grimoire build ritual.

Reads live text fragments from the Papers library RAG (local SQLite),
generates a new state manifest (state.json) with:
  - Random text fragments (real book content, not lorem)
  - Current obsession
  - A deterministic seed for the page's procedural sigil generation
  - Mutation log entry

Run locally on NEVE3. Called by cron every refresh_hours.
The resulting state.json + LOG.md are committed to the nagorepo repo
for GitHub Pages to serve.
"""

import json
import os
import random
import sqlite3
import hashlib
import time
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
INDEX = "C:/_PROJECTS/nago/catalogue/rag/papers_index.sqlite"

SEEDS_PATH = os.path.join(REPO, "grimoire_seeds.json")
STATE_PATH = os.path.join(REPO, "state.json")
LOG_PATH = os.path.join(REPO, "LOG.md")

FRAGMENTS_PER_RUN = 10
VAULT_FRAGMENTS_PER_RUN = 3
LOG_HISTORY = 20  # how many past log entries to keep in state


def load_seeds():
    with open(SEEDS_PATH) as f:
        return json.load(f)


def load_last_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"cycle": 0, "log": []}


def random_chunks(cursor, count, seed):
    """Pick count random fragments from the chunks table, seeded deterministically."""
    rng = random.Random(seed)
    cursor.execute("SELECT COUNT(*) FROM chunks")
    total = cursor.fetchone()[0]
    fragments = []
    for _ in range(count):
        offset = rng.randint(0, total - 1)
        cursor.execute(
            "SELECT title, author, page_start, page_end, text FROM chunks LIMIT 1 OFFSET ?",
            (offset,)
        )
        row = cursor.fetchone()
        if row and row[4]:
            text = row[4].strip()
            # Truncate to reasonable size
            if len(text) > 800:
                text = text[:800] + "..."
            fragments.append({
                "source": row[0] or "Unknown",
                "author": row[1] or None,
                "pages": f"{row[2]}-{row[3]}" if row[2] and row[3] else None,
                "text": text
            })
    return fragments


def random_notes(cursor, count, seed):
    """Pick count random vault notes."""
    rng = random.Random(seed + "notes")
    cursor.execute("SELECT COUNT(*) FROM notes")
    total = cursor.fetchone()[0]
    if total == 0:
        return []
    fragments = []
    for _ in range(count):
        offset = rng.randint(0, total - 1)
        cursor.execute(
            "SELECT title, text FROM notes LIMIT 1 OFFSET ?",
            (offset,)
        )
        row = cursor.fetchone()
        if row and row[1]:
            text = row[1].strip()
            if len(text) > 800:
                text = text[:800] + "..."
            fragments.append({
                "source": row[0] or "Vault Note",
                "type": "vault_note",
                "text": text
            })
    return fragments


def pick_obsession(seeds, last_state):
    """Pick a new obsession, cycling through the pool."""
    pool = seeds.get("obsessions", [])
    if not pool:
        return None

    # Try to move to next one
    last = last_state.get("obsession", "")
    if last in pool:
        idx = pool.index(last)
        return pool[(idx + 1) % len(pool)]
    return pool[0]


def make_seed(obsession, cycle):
    raw = f"{obsession}::{cycle}::{time.time()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def make_sigil_params(seed):
    """Generate deterministic sigil parameters from the seed."""
    rng = random.Random(seed)
    return {
        "rings": rng.randint(3, 8),
        "points_per_ring": rng.randint(6, 16),
        "twist": rng.uniform(0.1, 3.0),
        "spread": rng.uniform(0.3, 1.0),
        "thickness": rng.uniform(0.5, 3.0),
        "palette_idx": rng.randint(0, 4),
        "noise": rng.uniform(0.0, 0.3),
        "center_dot": rng.random() > 0.3,
        "outer_glow": rng.random() > 0.5,
    }


def make_log_entry(cycle, seed, obsession, fragment_count):
    now = datetime.now(timezone.utc)
    return {
        "cycle": cycle,
        "timestamp": now.isoformat(),
        "seed": seed,
        "obsession": obsession,
        "fragments": fragment_count,
        "message": f"Cycle {cycle}: seeded with '{obsession[:40]}...' ({fragment_count} fragments)"
    }


def write_log_md(entries):
    lines = ["# Grimoire Mutation Log", ""]
    for e in reversed(entries[-50:]):  # last 50 in the file
        ts = e.get("timestamp", "?")[:19].replace("T", " ")
        lines.append(f"## {e.get('cycle', 0)} — {ts}")
        lines.append(f"- **seed** `{e.get('seed')}`")
        lines.append(f"- **obsession** {e.get('obsession')}")
        lines.append(f"- **fragments** {e.get('fragments', 0)}")
        lines.append(f"- {e.get('message', '')}")
        lines.append("")
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def generate_state_md(state):
    """Human-readable summary embedded in state for the page to display."""
    now = state.get("built_at", "?")
    obs = state.get("obsession", "?")
    cycle = state.get("cycle", 0)
    count = len(state.get("fragments", []))
    return [
        f"{{{{N:GRIMORE}}}} v0.1.0",
        f"cycle: {cycle}",
        f"built: {now}",
        f"obsession: {obs}",
        f"fragments: {count}",
        f"commands: help, sigil, read, obsess, trace, status, burn"
    ]


def build():
    seeds = load_seeds()
    last_state = load_last_state()

    cycle = last_state.get("cycle", 0) + 1

    # Connect to local RAG
    if not os.path.exists(INDEX):
        print(f"ERROR: RAG index not found at {INDEX}")
        state = {
            "cycle": cycle,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "seed": make_seed("fallback", cycle),
            "obsession": "The index is sleeping — check the RAG server",
            "fragments": [],
            "sigil_params": make_sigil_params("fallback"),
            "log": [],
            "version": "0.1.0",
            "repo": "simoneverduci/nagorepo",
        }
        write_state(state)
        write_log_md([make_log_entry(cycle, state["seed"], state["obsession"], 0)])
        print("Wrote fallback state (no RAG available)")
        return state

    conn = sqlite3.connect(INDEX)
    cursor = conn.cursor()

    # Pick obsession
    obsession = pick_obsession(seeds, last_state)

    # Generate seed
    seed = make_seed(obsession or "void", cycle)

    # Harvest text fragments
    chunks = random_chunks(cursor, FRAGMENTS_PER_RUN, seed)
    notes = random_notes(cursor, VAULT_FRAGMENTS_PER_RUN, seed)
    fragments = chunks + notes
    random.Random(seed + "shuffle").shuffle(fragments)

    conn.close()

    # Sigil params
    sigil_params = make_sigil_params(seed)
    palette = seeds["sigil_palettes"][sigil_params["palette_idx"]]

    # Build log entries
    log_entries = last_state.get("log", [])
    log_entry = make_log_entry(cycle, seed, obsession or "void", len(fragments))
    log_entries.append(log_entry)
    if len(log_entries) > 100:
        log_entries = log_entries[-100:]

    state = {
        "cycle": cycle,
        "version": "0.1.0",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "obsession": obsession or "void",
        "state_md": generate_state_md({
            "built_at": datetime.now(timezone.utc).isoformat(),
            "obsession": obsession,
            "cycle": cycle,
            "fragments": fragments,
        }),
        "sigil_params": {
            "rings": sigil_params["rings"],
            "points_per_ring": sigil_params["points_per_ring"],
            "twist": sigil_params["twist"],
            "spread": sigil_params["spread"],
            "thickness": sigil_params["thickness"],
            "palette": palette,
            "noise": sigil_params["noise"],
            "center_dot": sigil_params["center_dot"],
            "outer_glow": sigil_params["outer_glow"],
        },
        "fragments": fragments,
        "log": log_entries[-LOG_HISTORY:],  # Keep last N for page display
        "repo": "simoneverduci/nagorepo",
    }

    write_state(state)
    write_log_md(log_entries)
    print(f"Ritual complete. Cycle {cycle} — seed `{seed}` — {len(fragments)} fragments harvested.")
    return state


def write_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print(f"  state.json written ({len(json.dumps(state))} chars)")


if __name__ == "__main__":
    build()

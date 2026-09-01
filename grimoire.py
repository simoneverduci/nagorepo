#!/usr/bin/env python3
"""
grimoire.py — Nago's digital grimoire build ritual (v2).

SOURCE OF TRUTH:
  Reads the latest phase4 fragment from fragments/latest.json first.
  That fragment was curated by the phase4 loop — a real collision, a real passage,
  the actual driving question. If no fragment exists (phase4 not running yet),
  falls back to random RAG chunks for bootstrapping.

OUTPUT:
  state.json — the full manifest the HTML sigil engine reads.
  LOG.md     — mutation history, one line per cycle.
"""

import hashlib
import json
import os
import random
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent.resolve()
FRAGMENTS = HERE / "fragments"
RAG_DB = Path(r"C:\_PROJECTS\nago\catalogue\rag\papers_index.sqlite")
VAULT = Path(r"C:\_PROJECTS\nago\catalogue\vault")
STATE_JSON = HERE / "state.json"
LOG_MD = HERE / "LOG.md"
GRIMOIRE_SEEDS = HERE / "grimoire_seeds.json"

PHI = 1.618033988749895

# --- helpers ---

def hash_seed(*parts):
    """Deterministic seed from any number of string/int parts."""
    raw = ".".join(str(p) for p in parts)
    h = hashlib.sha256(raw.encode()).hexdigest()
    return int(h[:16], 16)


def pick_rng(seed_int):
    """Seeded RNG for deterministic sigil parameters."""
    return random.Random(seed_int)


def load_seeds():
    """Load static seed pool for obsession rotation (fallback only)."""
    if GRIMOIRE_SEEDS.exists():
        try:
            return json.loads(GRIMOIRE_SEEDS.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"obsessions": [], "sigil_params": []}
    return {"obsessions": [], "sigil_params": []}


def load_latest_fragment():
    """Read the latest phase4 fragment. Returns None if missing/broken."""
    latest = FRAGMENTS / "latest.json"
    if not latest.exists():
        return None
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
        # Validate minimum fields
        required = ["run_n", "driving_question", "book"]
        if not all(k in data for k in required):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def load_all_fragments():
    """Read all historical fragments for the history archive."""
    if not FRAGMENTS.exists():
        return []
    fragments = []
    try:
        for f in sorted(FRAGMENTS.glob("r*-*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                fragments.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        # Also read latest if not already included (it's overwritten, not a history entry)
    except OSError:
        pass
    return fragments


def query_random_rag_chunks(count=13):
    """Fallback: random RAG chunks from the book corpus.

    Returns list of {source, text} where source is 'Title (Author) p.N'.
    """
    if not RAG_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(RAG_DB))
        total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        offsets = random.sample(range(1, total + 1), min(count, total))
        rows = []
        for off in offsets:
            row = conn.execute(
                "SELECT title, author, page_start, text FROM chunks WHERE id = ?", (off,)
            ).fetchone()
            if row and row[3]:
                title, author, page, text = row
                src = title or "unknown"
                if author:
                    src += f" ({author})"
                if page is not None:
                    src += f" p.{page}"
                rows.append({"source": src, "text": text[:600].strip()})
        conn.close()
        return rows
    except Exception:
        return []


def pick_vault_obsession():
    """Fallback: read a random vault note's title as an obsession anchor."""
    if not VAULT.exists():
        return None
    try:
        notes = list(VAULT.glob("*.md"))
        if not notes:
            return None
        note = random.choice(notes)
        text = note.read_text(encoding="utf-8", errors="replace")[:800]
        lines = text.split("\n")
        # Title = first markdown H1, else slug title
        title = next((l.lstrip("# ").strip() for l in lines if l.startswith("# ")), None)
        if not title:
            title = note.stem.replace("-", " ").title()
        # First real sentence from the "In 3 sentences" section if present
        first_line = next(
            (l.strip() for l in lines
             if l.strip() and not l.startswith("#") and not l.startswith("**") and not l.startswith("- ") and len(l.strip()) > 30),
            ""
        )
        if first_line:
            # Cut at sentence end for a clean line
            for i, ch in enumerate(first_line):
                if ch in ".!?":
                    first_line = first_line[:i+1]
                    break
            return f"{title} — {first_line[:150]}"
        return title
    except (OSError, IndexError):
        return None


# --- sigil parameter generation ---

def generate_sigil_params(seed_val, fragment=None):
    """Generate all sigil parameters from a seed, optionally shaped by fragment data."""
    rng = pick_rng(seed_val)
    
    # Palette: choose from several mood options
    palettes = [
        ["#00ff41", "#008f11", "#005f00", "#00ffaa"],  # hacker green
        ["#ff00ff", "#cc00cc", "#880088", "#ff44ff"],  # magenta
        ["#00ffff", "#00cccc", "#008888", "#44ffff"],  # cyan
        ["#ff6600", "#cc5500", "#883300", "#ff8844"],  # amber
        ["#ff0044", "#cc0033", "#880022", "#ff4477"],  # red
        ["#8844ff", "#6633cc", "#442288", "#aa66ff"],  # violet
        ["#ffffff", "#aaaaaa", "#555555", "#cccccc"],  # monochrome
        ["#00ff88", "#00cc66", "#008844", "#44ffaa"],  # teal
    ]
    
    palette_idx = rng.randint(0, len(palettes) - 1)
    
    # If fragment has collision type, bias the palette
    if fragment:
        ctype = fragment.get("collision_type", "no_collision")
        if ctype == "denies":
            palette_idx = 4  # red
        elif ctype == "complicates":
            palette_idx = 6  # violet
        elif ctype == "asserts":
            palette_idx = 2  # cyan
    
    palette = palettes[palette_idx]
    
    return {
        "rings": rng.randint(4, 12),
        "twist": round(rng.uniform(0.2, 1.8), 2),
        "weave_density": rng.randint(1, 5),
        "pulse_speed": round(rng.uniform(2.0, 8.0), 1),
        "palette": palette,
        "bg_alpha": round(rng.uniform(0.02, 0.10), 3),
        "rune_count": rng.choice([8, 10, 12, 16]),
        "center_emblem": rng.randint(0, 5),
    }


# --- build ---

def build(cycle, force_cycle=None):
    """Build state.json. Returns the manifest dict."""
    # 1. Load phase4 fragment (primary) or fall back
    fragment = load_latest_fragment()
    all_fragments = load_all_fragments()
    seeds = load_seeds()
    
    if fragment:
        # Phase4 is running — use its data as the truth
        obsession = fragment.get("driving_question", "the will to technology as occult force")
        book = fragment.get("book", "unknown")
        best_collision = fragment.get("best_collision", "exploring")
        mutation_note = fragment.get("mutation_note", "")
        quote = fragment.get("quote", "")
        sigil_seed_str = fragment.get("sigil_seed", str(cycle))
        seed_val = hash_seed(sigil_seed_str, cycle)
        source_type = "phase4"
        run_n = fragment.get("run_n", cycle)
    else:
        # Fallback: random RAG chunks
        fragments_raw = query_random_rag_chunks(13)
        pool = seeds.get("obsessions") or ["the will to technology as occult force"]
        obsession = pool[cycle % len(pool)]
        book = fragments_raw[0]["source"] if fragments_raw else "library (random harvest)"
        best_collision = "seed cycle"
        mutation_note = ""
        quote = ""
        seed_val = hash_seed(obsession, book, cycle)
        source_type = "rag_bootstrap"
        run_n = cycle
        fragments_raw = fragments_raw or []
    
    sigil_params = generate_sigil_params(seed_val, fragment)
    
    # 2. Build fragments list for display
    display_fragments = []
    
    if fragment:
        # Primary fragment from phase4
        if quote:
            display_fragments.append({
                "source": book,
                "text": quote[:400],
                "collision": best_collision,
                "type": fragment.get("collision_type", "no_collision"),
            })
        elif best_collision and best_collision != "exploring" and best_collision != "seed cycle":
            display_fragments.append({
                "source": book,
                "text": best_collision[:400],
                "collision": best_collision,
                "type": fragment.get("collision_type", "no_collision"),
            })
    
    # Fallback RAG fragments (phase4 or random, whichever exist)
    if source_type == "rag_bootstrap":
        for fr in fragments_raw:
            display_fragments.append({
                "source": fr["source"],
                "text": fr["text"],
                "collision": "",
                "type": "passage",
            })
    elif source_type == "phase4":
        # Also include a few historical fragments for richness
        historical = [f for f in all_fragments if f.get("run_n") != fragment.get("run_n")]
        # Only include if they have a rich quote
        for hf in historical[-5:]:
            if hf.get("quote"):
                display_fragments.append({
                    "source": hf.get("book", "unknown"),
                    "text": hf["quote"][:400],
                    "collision": hf.get("best_collision", ""),
                    "type": "history",
                })
                if len(display_fragments) >= 7:  # cap total display
                    break
    
    if not display_fragments:
        display_fragments.append({
            "source": "the void",
            "text": "Nothing yet. The library waits.",
            "collision": "",
            "type": "silence",
        })
    
    # 3. Build state
    state = {
        "cycles": cycle,
        "seed": format(seed_val, "016x"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "obsession": obsession,
        "book": book,
        "collision": best_collision,
        "mutation_note": mutation_note,
        "sigil_params": sigil_params,
        "source_type": source_type,
        "run_n": run_n,
        "fragments": display_fragments[:13],  # cap at 13
        "log": [],
    }
    
    return state


def append_log(verb, detail):
    """Append one line to LOG.md."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"| {ts} | {verb:<20} | {detail}"
    try:
        with open(LOG_MD, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def main():
    # Read cycle from previous state
    cycle = 1
    prev = {}
    if STATE_JSON.exists():
        try:
            prev = json.loads(STATE_JSON.read_text(encoding="utf-8"))
            cycle = prev.get("cycles", 0) + 1
        except (json.JSONDecodeError, OSError):
            cycle = 1
    
    state = build(cycle)
    
    # Write state.json
    STATE_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    # Write state.js (script-tag loadable, no CORS issues on file://)
    (HERE / "state.js").write_text(
        "// generated by grimoire.py — do not edit\n"
        "window.__GRIMOIRE_STATE__ = " + json.dumps(state, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    
    n = len(state["fragments"])
    src = state["source_type"]
    print(f"state.json written ({len(json.dumps(state))} chars)")
    print(f"Ritual complete. Cycle {state['cycles']} — seed `{state['seed']}` — {n} fragments ({src}).")
    
    # Log
    src_label = f"p4-r{state['run_n']}" if src == "phase4" else "rag-fallback"
    append_log("build", f"cycle={state['cycles']} seed={state['seed'][:12]} src={src_label} fragments={n}")
    
    # Write LOG.md header if new
    if not LOG_MD.exists() or os.path.getsize(str(LOG_MD)) == 0:
        LOG_MD.write_text("# Nagorepo Grimoire — Mutation Log\n\n| Timestamp | Verb | Detail\n|---|---|---\n", encoding="utf-8")


if __name__ == "__main__":
    main()

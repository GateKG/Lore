# -*- coding: utf-8 -*-
"""3.31 THE PER-GAME SOURCES LEDGER - built from a scratch shelf.

Lifts the REAL ledger functions out of lore.py by name (the path, the
row, the increments, the verdicts, the night gate, the rebuild, the
debounced note, the daily hook) together with scan_library and
_library_signature, points them at a temp shelf (never D:\\Records, never
%LOCALAPPDATA%) and proves:
  - the verdicts and their thresholds (120 s voice chat, 60 s game
    speech, three honest quiet nights = false, else null);
  - the rebuild walks the shelf: a by-source night votes, an old
    transcript does not, a Mix-only reader-6 night does not, a sidecar
    whose video is on no shelf is ignored, a night whose reader stood
    media detection down is skipped, a night whose .src.json says the
    voice tap died is skipped, a tap that simply went (Discord closed)
    still votes;
  - the key is scan_library's (aliases merge into one row and one badge);
  - lib mismatch on load returns the empty shape;
  - scan_library joins g['voices'] and _library_signature moves with the
    ledger's clock;
  - the note after a transcribe is ONE debounced rebuild (never an
    increment), and a Mix-only night schedules nothing;
  - the daily hook claims the day once and skips a fresh ledger."""
import ast
import io
import json
import os
import re
import shutil
import sys
import tempfile
import textwrap
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def extract(name, ns):
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


def lift_assign(name, ns):
    for node in TREE.body:
        if not isinstance(node, ast.Assign):
            continue
        names = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                names.append(t.id)
            elif isinstance(t, ast.Tuple):
                names += [e.id for e in t.elts if isinstance(e, ast.Name)]
        if name in names:
            code = "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not assigned")


TMP = tempfile.mkdtemp(prefix="lore_shelf331_")
LIB = os.path.join(TMP, "Records")
TH = os.path.join(LIB, ".lore_thumbs")
DATA = os.path.join(TMP, "data")
os.makedirs(TH)
os.makedirs(DATA)
LOGS = []
ALIAS = {"Trackmania2020": "Trackmania"}


def wjson(p, d):
    io.open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))


ns = {"os": os, "json": json, "re": re, "time": time, "threading": threading,
      "log": LOGS.append, "SETTINGS": {"output_dir": LIB},
      "_data_dir": lambda: DATA, "_atomic_write_json": wjson,
      "_display_name": lambda raw: ALIAS.get(raw, raw),
      "_finish_badge": lambda p: None, "_dur_load_once": lambda: None,
      "_DUR_LOCK": threading.Lock(), "_DUR_CACHE": {}}
for nm in ("_GS_VOICE_S", "_GS_GAME_S", "_GS_MEDIA_S", "_GS_QUIET_NIGHTS",
           "_GS_DEBOUNCE_S", "_GS_OK_VOICE", "_GS"):
    lift_assign(nm, ns)
for nm in ("_parse_clip_name", "_library_dirs", "_thumb_dir",
           "_scan_dir_mp4s", "scan_library", "_library_signature",
           "_game_sources_path", "_game_sources_lib", "_game_sources_empty",
           "_game_sources_load", "_game_sources_row", "_game_sources_add",
           "_game_sources_verdicts", "_game_sources_key",
           "_game_sources_night_ok", "_game_sources_rebuild",
           "_game_sources_rebuild_safe", "_game_sources_note",
           "_game_sources_daily"):
    extract(nm, ns)
verdicts = ns["_game_sources_verdicts"]
row_of = ns["_game_sources_row"]
add = ns["_game_sources_add"]
rebuild = ns["_game_sources_rebuild"]
load = ns["_game_sources_load"]
note = ns["_game_sources_note"]
scan = ns["scan_library"]
sig = ns["_library_signature"]

print("--- the verdicts and their thresholds ---")
check("the thresholds are the reader's: 120 / 60 / 60 s, three quiet nights",
      ns["_GS_VOICE_S"] == 120 and ns["_GS_GAME_S"] == 60
      and ns["_GS_MEDIA_S"] == 60 and ns["_GS_QUIET_NIGHTS"] == 3)


def row_with(**kw):
    r = row_of()
    r.update(kw)
    verdicts(r)
    return r


check("one voice-chat night -> voice_chat True",
      row_with(voice_seen=1, voice_nights=1)["voice_chat"] is True)
check("two quiet nights with a Voice track -> still unknown (None)",
      row_with(voice_seen=2, voice_nights=0)["voice_chat"] is None)
check("three quiet nights -> False",
      row_with(voice_seen=3, voice_nights=0)["voice_chat"] is False)
check("no Voice track ever -> None whatever the nights",
      row_with(nights=9, voice_seen=0)["voice_chat"] is None)
check("voice_lines likewise on the Game track",
      row_with(game_seen=1, game_nights=1)["voice_lines"] is True
      and row_with(game_seen=3, game_nights=0)["voice_lines"] is False
      and row_with(game_seen=2, game_nights=0)["voice_lines"] is None)
r = row_of()
add(r, {"voice": True, "voice_s": 119.9, "game": True, "game_s": 60.0,
        "media_s": 59.9}, 100)
check("the increments: 119.9 s of voice is not a voice night, 60 s of game is,"
      " 59.9 s of media is not",
      r["nights"] == 1 and r["voice_seen"] == 1 and r["voice_nights"] == 0
      and r["game_seen"] == 1 and r["game_nights"] == 1
      and r["media_nights"] == 0 and r["voice_s"] == 119.9 and r["last"] == 100)
add(r, {"voice": False, "game": None, "media_s": 400}, 50)
check("a night without the layers counts as a night and a media night only",
      r["nights"] == 2 and r["voice_seen"] == 1 and r["game_seen"] == 1
      and r["media_nights"] == 1 and r["last"] == 100)

print("\n--- the rebuild from a scratch shelf ---")


def vid(game, stamp, sub="Videos"):
    d = os.path.join(LIB, game, sub)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s_%s.mp4" % (game, stamp))
    io.open(p, "wb").write(b"\0" * 200000)
    return p


def side(p, kind):
    return os.path.join(TH, os.path.splitext(os.path.basename(p))[0]
                        + "." + kind + ".json")


def stt(p, sources=None, when=1_700_000_000, reader=6):
    head = {"v": 3, "model": "m", "engine": "qwen3-asr", "counters": {},
            "reader": reader, "run": {"elapsed_s": 1.0, "when": when}}
    if sources is not None:
        head["sources"] = sources
    head["segments"] = [{"a": 1000, "b": 2000, "t": "x" * 200}] * 60
    wjson(side(p, "stt"), head)


def src_of(sources, voice_s=0, game=False, game_s=0, media_s=0,
           media_off=0):
    return {"v": 1, "voice": bool(sources), "game": game, "media": True,
            "voice_s": voice_s, "mic_s": 0, "room_s": voice_s,
            "game_s": (game_s if game else None), "media_s": media_s,
            "media_read_s": media_s, "game_read_s": 0, "media_dropped": 0,
            "game_dropped": 0, "media_off": media_off}


a = vid("Bazaar", "20260901_120000")
stt(a, src_of(True, voice_s=300, game=True, game_s=0, media_s=90))
led = rebuild()
row = led["games"].get("bazaar")
check("one by-source night: voice_nights 1, voice_chat True, voice_lines "
      "None (game_seen 1 < 3), media_nights 1",
      row and row["voice_nights"] == 1 and row["voice_chat"] is True
      and row["game_seen"] == 1 and row["voice_lines"] is None
      and row["media_nights"] == 1 and row["nights"] == 1)
check("...keyed as scan_library keys the chapter (lower-case display name)",
      list(led["games"]) == ["bazaar"])
check("...stamped for this library, written to the data dir",
      led["lib"] == os.path.normcase(os.path.abspath(LIB))
      and os.path.isfile(os.path.join(DATA, "game_sources.json")))
b = vid("Bazaar", "20260902_120000")
c = vid("Bazaar", "20260903_120000")
stt(b, src_of(True, voice_s=10, game=True, game_s=0))
stt(c, src_of(True, voice_s=0, game=True, game_s=0))
row = rebuild()["games"]["bazaar"]
check("two more quiet-game nights: voice_lines False (three quiet), "
      "voice_chat still True (one night was enough)",
      row["game_seen"] == 3 and row["voice_lines"] is False
      and row["voice_chat"] is True and row["nights"] == 3)
old = vid("Bazaar", "20260101_120000")
stt(old, None, reader=5)
mixonly = vid("Bazaar", "20260904_120000")
stt(mixonly, {"v": 1, "voice": False, "game": False, "media": False,
              "voice_s": 0, "mic_s": 500, "room_s": 500, "game_s": None,
              "media_s": 0, "media_read_s": 0, "game_read_s": 0,
              "media_dropped": 0, "game_dropped": 0, "media_off": 0})
row = rebuild()["games"]["bazaar"]
check("an old transcript (no sources) and a Mix-only reader-6 night add no vote",
      row["nights"] == 3)
stt(os.path.join(LIB, "Orphan_20260905_120000.mp4"),
    src_of(True, voice_s=500, game=True, game_s=500))
led = rebuild()
check("a sidecar whose video is on no shelf is ignored",
      "orphan" not in led["games"] and led["games"]["bazaar"]["nights"] == 3)
d = vid("Bazaar", "20260906_120000")
stt(d, src_of(True, voice_s=0, game=True, game_s=0, media_off=1))
row = rebuild()["games"]["bazaar"]
check("a night whose reader stood media detection down is skipped",
      row["nights"] == 3 and row["voice_seen"] == 3)
e = vid("Bazaar", "20260907_120000")
stt(e, src_of(True, voice_s=0, game=True, game_s=0))
wjson(side(e, "src"), {"layers": {"media": True}, "runs": [
    {"sources": {"voice": {"state": "dead", "gap_s": 900}}}]})
row = rebuild()["games"]["bazaar"]
check("a night whose voice tap DIED is skipped (it would vote 'no voice chat')",
      row["nights"] == 3 and row["voice_seen"] == 3)
wjson(side(e, "src"), {"layers": {"media": True}, "runs": [
    {"sources": {"voice": {"state": "live", "gap_s": 0}}},
    {"sources": {"voice": {"state": "gone", "gap_s": 30}}}]})
row = rebuild()["games"]["bazaar"]
check("...a tap that went live then gone (Discord closed) still votes",
      row["nights"] == 4 and row["voice_seen"] == 4)
wjson(side(e, "src"), {"layers": {"media": True}, "runs": [
    {"sources": {"voice": {"state": "failed", "gap_s": 0}}}]})
row = rebuild()["games"]["bazaar"]
check("...a tap that failed does not", row["nights"] == 3)
t1 = vid("Trackmania", "20260910_120000")
t2 = vid("Trackmania2020", "20260911_120000")
stt(t1, src_of(True, voice_s=200, game=True, game_s=100))
stt(t2, src_of(True, voice_s=200, game=True, game_s=100))
led = rebuild()
check("two raw folder names one display name maps together share ONE row",
      "trackmania" in led["games"] and "trackmania2020" not in led["games"]
      and led["games"]["trackmania"]["nights"] == 2
      and led["games"]["trackmania"]["voice_lines"] is True)
g = vid("Hades", "20260912_120000")
stt(g, src_of(False, game=True, game_s=200, media_s=0))
row = rebuild()["games"]["hades"]
check("a Game-only night (the voice app closed): no Voice vote, the game talks",
      row["voice_seen"] == 0 and row["voice_chat"] is None
      and row["game_nights"] == 1 and row["voice_lines"] is True)

print("\n--- load, scan_library, the signature ---")
check("load returns the ledger it wrote",
      load()["games"]["bazaar"]["nights"] == 3 and load()["v"] == 1)
ns["SETTINGS"]["output_dir"] = os.path.join(TMP, "Elsewhere")
check("lib mismatch on load returns the empty shape",
      load() == {"v": 1, "lib": "", "at": 0, "games": {}})
ns["SETTINGS"]["output_dir"] = LIB
lib = scan()
byk = {g["key"]: g for g in lib["games"]}
check("scan_library joins voices by the same key",
      byk["bazaar"]["voices"] == {"chat": 1, "lines": 0, "nights": 3,
                                  "voice_chat": True, "voice_lines": False}
      and byk["trackmania"]["voices"]["nights"] == 2)
n = vid("Nothing", "20260913_120000")
lib = scan()
byk = {g["key"]: g for g in lib["games"]}
check("a game never heard by source carries voices null",
      byk["nothing"]["voices"] is None)
s0 = sig()
time.sleep(1.1)
lp = ns["_game_sources_path"]()
os.utime(lp, (time.time(), time.time()))
check("the signature moves when the ledger's clock moves", sig() != s0)
s1 = sig()
check("...and stays put otherwise", sig() == s1)
os.remove(lp)
check("no ledger at all: the signature still answers, voices null",
      isinstance(sig(), str) and load()["games"] == {}
      and {g["key"]: g for g in scan()["games"]}["bazaar"]["voices"] is None)

print("\n--- the note after a transcribe: one debounced rebuild ---")
RUNS = []
real_safe = ns["_game_sources_rebuild_safe"]


def spy_safe():
    RUNS.append(time.time())
    real_safe()


ns["_game_sources_rebuild_safe"] = spy_safe
ns["_GS_DEBOUNCE_S"] = 0.3
note(a, {"voice": False, "game": False})
time.sleep(0.6)
check("a Mix-only night schedules nothing", RUNS == [] and not os.path.isfile(lp))
note(a, src_of(True, voice_s=300))
note(b, src_of(True, voice_s=300))
note(c, src_of(True, voice_s=300))
time.sleep(0.15)
check("three notes inside the window: nothing yet", RUNS == [])
time.sleep(0.6)
check("...then ONE rebuild, from the shelf (no increments: 3 nights, not 6)",
      len(RUNS) == 1 and os.path.isfile(lp)
      and load()["games"]["bazaar"]["nights"] == 3)
note(a, src_of(True, voice_s=300))
time.sleep(0.6)
check("a redo of the same night rebuilds to the same count",
      len(RUNS) == 2 and load()["games"]["bazaar"]["nights"] == 3)

print("\n--- the daily hook ---")
THREADS = []


class FakeThread:
    def __init__(self, target=None, daemon=None, name=None):
        THREADS.append((target, name))

    def start(self):
        pass


ns["threading"] = type("T", (), {"Thread": FakeThread,
                                 "Timer": threading.Timer,
                                 "Lock": threading.Lock})
ns["_GS"]["daily_at"] = 0.0
ns["_game_sources_daily"]()
check("a fresh ledger (written seconds ago): no rebuild", THREADS == [])
os.remove(lp)
ns["_game_sources_daily"]()
check("no ledger: one rebuild on a daemon thread named game-sources",
      len(THREADS) == 1 and THREADS[0][1] == "game-sources"
      and THREADS[0][0] is ns["_game_sources_rebuild_safe"])
ns["_game_sources_daily"]()
check("...claimed for the hour: a second beat does not walk again",
      len(THREADS) == 1)
ns["_GS"]["daily_at"] = 0.0
wjson(lp, {"v": 1, "lib": ns["_game_sources_lib"](),
           "at": time.time() - 90000, "games": {}})
ns["_game_sources_daily"]()
check("a ledger older than a day is rebuilt", len(THREADS) == 2)
check("the daily hook rides the tick beside _self_check_daily, and boot",
      "    _self_check_daily()\n    _game_sources_daily()" in SRC
      and "_self_check_daily()     # one health line a day in the log\n"
          "    _game_sources_daily()" in SRC)
check("_transcribe_one tells the ledger after the log line",
      "_game_sources_note(video_path, data.get(\"sources\") or {})" in SRC
      and SRC.index("_game_sources_note(video_path, data.get(\"sources\")")
      > SRC.index("_med = sum(1 for s in segs if s.get(\"src\") == \"media\")"))
check("api.game_sources() returns the ledger",
      "    def game_sources(self):" in SRC
      and "return _game_sources_load()" in SRC)
check("nothing keeps the old per-transcribe increments or the twin file",
      "_note_game_voices" not in SRC and "game_voices.json" not in SRC
      and "stt_sources" not in SRC)

shutil.rmtree(TMP, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

# -*- coding: utf-8 -*-
"""3.19: the four things his log caught tonight, each proven dead.

  1. "All of it" began at the review because it was not fresh
  2. four Ask-again presses ran ONE recording and binned three
  3. Stop on one recording stood the whole tome down
  4. 185 waiting rows left the line with no way back
"""
import io
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

SAID = []
lore.log = lambda m: SAID.append(m)
lore.load_settings()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


api = lore._JsApi.__new__(lore._JsApi)
api._safe_path = lambda p: p

TMP = tempfile.mkdtemp(prefix="fresh319_")
VID = os.path.join(TMP, "ELDENRING_20260418_165025.mp4")
io.open(VID, "w").write("x")
THUMBS = os.path.join(TMP, ".lore_thumbs")
os.makedirs(THUMBS, exist_ok=True)
lore._thumb_dir = lambda out: THUMBS


def sidecar(kind, body="{}"):
    p = lore._ai_sidecar(VID, kind)
    with io.open(p, "w", encoding="utf-8") as fh:
        fh.write(body)
    return p


def reset():
    with lore._AI_FORCE_LOCK:
        lore._AI["force_queue"] = []
    lore._AI["force"] = None
    lore._AI["force_want"] = None
    lore._AI["force_redo"] = False
    lore._AI["busy"] = None
    lore._AI["busy_path"] = None
    lore._AI["dropped"] = []
    lore._AI["skipped"] = {}
    for k in ("listening", "hearing", "thinking", "auditing"):
        lore._AI.setdefault("held", {})[k] = False


print("--- 1. the old reading is ARCHIVED, never deleted ---")
for k in ("hl", "lvl", "stt", "ins"):
    sidecar(k, '{"v":1,"mine":"%s"}' % k)
moved = lore._ai_attic(VID, ["listening"])
check("a fresh sound pass files hl and lvl away",
      sorted(moved) == ["hl", "lvl"])
# IT COPIES. IT MUST NEVER MOVE. Taking the live file away broke five
# separate guards that read the previous reading at write time - the
# .v1/.v2/.v3 bank, his typed voice names, the eye's better-pass test,
# the review's carry-forward and the .ins staging. What makes a redo
# fresh is redo=True, which the passes already honour.
check("the live reading STAYS - the writers still need to read it",
      os.path.isfile(lore._ai_sidecar(VID, "hl")))
att = os.path.join(THUMBS, ".attic")
kept = os.listdir(att)
check("nothing was deleted - both are in the attic", len(kept) == 2)
check("and each keeps its own name and hour",
      all(f.startswith("ELDENRING_20260418_165025.") for f in kept))
body = json.load(io.open(os.path.join(att, kept[0]), encoding="utf-8"))
check("the archived copy is the real old file, intact",
      body.get("mine") in ("hl", "lvl"))
check("a lane he never ran keeps its reading",
      os.path.isfile(lore._ai_sidecar(VID, "stt")))
# and because the live file survives, the writers' own banking still
# works exactly as it did in 3.18 - the attic does not bank as well,
# which would rotate a real generation off the end of the chain
check("the attic does not double-bank",
      not os.path.isfile(lore._ai_sidecar(VID, "hl") + ".v1"))
_a = io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()
_a = _a.split("def _ai_attic")[1].split("def _read_sidecar")[0]
check("...because it copies rather than moves",
      "_sh.copy2(src, dst)" in _a and "os.replace(src, dst)" not in _a)
check("archiving a lane with nothing to file is harmless",
      lore._ai_attic(VID, ["hearing"], 0) == [])

print("\n--- and 'from scratch' owes every lane, even when all is fresh ---")
for k in ("hl", "lvl", "stt", "ins", "sns", "aud"):
    sidecar(k, '{"v":99}')
_rf = lore._ai_sidecar_fresh
_rp = lore._reader_paths
_dp = lore._describer_paths
lore._ai_sidecar_fresh = lambda p, k: True      # everything looks done
lore._reader_paths = lambda: ("py", "asr")
lore._describer_paths = lambda: ("py", "desc")
lore._lvl_coarse_cached = lambda p: False
try:
    lazy = lore._force_owes(VID, "all", False)
    fresh = lore._force_owes(VID, "all", True)
finally:
    lore._ai_sidecar_fresh = _rf
    lore._reader_paths = _rp
    lore._describer_paths = _dp
check("'fill in what is missing' on a finished night skips the sound",
      "listening" not in lazy)
check("...which is exactly why his ask began at the review",
      "thinking" in lazy or not lazy)
check("'from scratch' owes the sound", "listening" in fresh)
check("'from scratch' owes the words", "hearing" in fresh)
check("'from scratch' owes the review", "thinking" in fresh)

print("\n--- 2. four Ask-again presses queue FOUR recordings ---")
reset()
vids = []
for n in ("Drova-ForsakenKin", "hearthstone", "rocketleague", "Trackmania"):
    p = os.path.join(TMP, n + "_20260101_010101.mp4")
    io.open(p, "w").write("x")
    vids.append(p)
_fo = lore._force_owes
lore._force_owes = lambda p, w="all", r=False: {"thinking"}
# the describer is not installed in the dev tree; _force_blocked would
# refuse every "think" ask before the queue ever saw it
lore._describer_paths = lambda: ("py", "desc")
lore._ai_abort = lambda *a, **k: None
lore._ai_state_save = lambda: None
try:
    res = [api.prioritise(p, "think") for p in vids]
    q = [it[0] for it in (lore._AI.get("force_queue") or [])]
    check("all four presses were accepted", all(r.get("ok") for r in res))
    check("and ALL FOUR are in the line - none was evicted and forgotten",
          all(v in q for v in vids))
    check("the newest press is at the front",
          q and q[0] == vids[-1])
    # AND IT IS *NOT* A FROM-SCRATCH ASK. The first cut of 3.19 made
    # every by-name ask redo=True, which archived the senses sidecar -
    # and that file is where his typed voice names live, so asking
    # again for a description would have blanked every one of them.
    # Being forced already zeroes the three-try wall and already
    # restarts a completed review, so redo bought nothing anyway.
    check("a by-name ask fills in; it does not throw the old work away",
          all(not it[2] for it in (lore._AI.get("force_queue") or [])))
    check("...while the from-scratch door still asks for it explicitly",
          bool(lore._force_owes(vids[0], "all", True)))

    print("\n--- 3. Skip lets ONE go; it does not silence the tome ---")
    reset()
    lore._AI["busy"] = ("thinking", "Trackmania2020_20260128_212331.mp4")
    lore._AI["busy_path"] = vids[3]
    with lore._AI_FORCE_LOCK:
        lore._AI["force_queue"] = [(vids[3], "think", True, []),
                                   (vids[0], "think", True, [])]
    SAID[:] = []
    r = api.ai_skip_current()
    held = lore._AI.get("held") or {}
    check("the job in hand is let go", r.get("ok") is True)
    check("NOT ONE lane was stood down",
          not any(held.get(k) for k in
                  ("listening", "hearing", "thinking", "auditing")))
    check("the skipped recording leaves the line",
          all(it[0] != vids[3]
              for it in (lore._AI.get("force_queue") or [])))
    check("everything else keeps its place",
          any(it[0] == vids[0]
              for it in (lore._AI.get("force_queue") or [])))
    check("and the sweep will not hand it straight back",
          lore._ai_skipped_recently(vids[3]) is True)
    check("a recording he never skipped is untouched",
          lore._ai_skipped_recently(vids[0]) is False)
    check("the skip says nothing else was paused",
          any("Nothing else was paused" in m for m in SAID))
    # the worker thread is what clears `busy` when its child dies;
    # _ai_abort only asks it to stop, so stand in for that here
    lore._AI["busy"] = None
    lore._AI["busy_path"] = None
    check("skipping when nothing runs is refused, not crashed",
          api.ai_skip_current().get("ok") is False)
finally:
    lore._force_owes = _fo
    lore._describer_paths = _dp

print("\n--- 3b. and what Skip takes out is recoverable too ---")
reset()
lore._AI["busy"] = ("thinking", "Trackmania.mp4")
lore._AI["busy_path"] = vids[3]
lore._AI["next_pick"] = (time.time(), {"name": "Trackmania.mp4"})
with lore._AI_FORCE_LOCK:
    lore._AI["force_queue"] = [(vids[3], "think", True, []),
                               (vids[0], "think", True, [])]
api.ai_skip_current()
check("Skip was the last door that deleted rows outright - not now",
      any(it[0] == vids[3] for it in (lore._AI.get("dropped") or [])))
check("and the shelf stops calling it 'next' immediately",
      lore._AI.get("next_pick") is None)
check("putting it back works like any other let-go",
      api.ai_queue_restore().get("restored") == 1)

print("\n--- 3c. a skipped AUDIT does not re-arm itself ---")
# the audit worker's own `finally` re-queues an interrupted audit, and
# it runs AFTER Skip has filtered the line - so the row came straight
# back and Skip was a no-op for every audit he ever pressed it on
LSRC = io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()
check("an interrupted audit still returns to the line",
      'q3.insert(at3, (live[0], "audit"' in LSRC)
check("...but a deliberately skipped one is let go first",
      "if live and _ai_skipped_recently(live[0]):" in LSRC
      and LSRC.index("if live and _ai_skipped_recently(live[0]):")
          < LSRC.index('q3.insert(at3, (live[0], "audit"'))
# A QUEUE-DRIVEN AUDIT IS NOT IN THE LINE WHILE IT RUNS - its row sits
# in aud_live, so the purge cannot see it and the worker re-files it
check("the skip drops the audit's recovery memo itself",
      'if (_AI.get("aud_live") or ("",))[0] == path:' in LSRC)
_tk = LSRC.split("def _takeable")[1].split("forced_now")[0]
check("and a skipped row cannot re-take the card if it races back",
      "if _ai_skipped_recently(it[0]):" in _tk)
check("...nor be handed over by the drain",
      "if _ai_skipped_recently(it0[0]):" in LSRC)
# functional: aud_live for the skipped path really is gone
reset()
lore._AI["busy"] = ("thinking", "the audit · Trackmania.mp4")
lore._AI["busy_path"] = vids[3]
lore._AI["aud_live"] = (vids[3], True, 0)
api.ai_skip_current()
check("proved: the memo for THAT recording is dropped",
      lore._AI.get("aud_live") is None)
lore._AI["busy"] = ("thinking", "other.mp4")
lore._AI["busy_path"] = vids[0]
lore._AI["aud_live"] = (vids[2], True, 0)
api.ai_skip_current()
check("and another recording's memo is left alone",
      (lore._AI.get("aud_live") or ("",))[0] == vids[2])

print("\n--- 4. the line has a door back ---")
reset()
with lore._AI_FORCE_LOCK:
    lore._AI["force_queue"] = [(v, "think", False, []) for v in vids]
d = api.ai_queue_drop(vids[1])
check("one row let go", d.get("ok") is True)
check("and it is recoverable", d.get("restorable") == 1)
c = api.ai_queue_clear()
check("the whole line let go", c.get("dropped") == 3)
check("all four are recoverable", c.get("restorable") == 4)
check("the line really is empty now",
      not (lore._AI.get("force_queue") or []))
back = api.ai_queue_restore()
check("and every one comes back", back.get("restored") == 4)
q2 = [it[0] for it in (lore._AI.get("force_queue") or [])]
check("all four, by name", sorted(q2) == sorted(vids))
check("restoring twice does not double the line",
      api.ai_queue_restore().get("ok") is False)
check("a restore never duplicates a row already waiting",
      len(q2) == len(set(q2)))

print("\n--- and the tome side says the same thing ---")
UI = io.open(r"D:\Gate LLC\ui.html", encoding="utf-8").read()
check("the menu offers a from-scratch row",
      "Everything, from scratch" in UI)
check("...which passes redo=true", "runIt(want,fresh)" in UI)
check("the card's red button skips", "Skip this one" in UI)
check("and it calls the skip door, not the silence door",
      "api.ai_skip_current()" in UI
      and "r=await api.ai_stop_current();}catch(e){}" not in UI)
check("the line offers the way back", "ai_queue_restore" in UI)
check("a chapter page counts itself in words",
      "page ${sp.k+1} of ${sp.pagesN}" in UI)
check("the refusals shelf explains what three tries meant",
      "stops retrying by itself" in UI)
# THE UNDO MUST BE DRAWN ON THE EMPTY PATH TOO. Letting the WHOLE line
# go is the press it exists to undo, and paint() returns early when no
# rows are left - the first cut of this drew the button only under a
# non-empty list, so it was invisible exactly when it was needed.
_empty = UI.split("if(!items.length){")[1].split("return;")[0]
check("the undo is drawn when the line is empty", "putBack();" in _empty)
check("and rf() exists where the whole-line press calls it",
      UI.count("const rf=()=>{sig=null;paint();};") == 1
      and UI.index("const rf=()=>{sig=null;paint();};")
          < UI.index("const lg=el('button','wbtn danger qletgo'"))

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

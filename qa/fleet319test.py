# -*- coding: utf-8 -*-
"""What the adversarial fleet caught in MY OWN 3.19 change, locked so it
cannot come back. Every one of these was a defect I introduced while
fixing his complaints."""
import io
import sys

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


UI = io.open(r"D:\Gate LLC\ui.html", encoding="utf-8").read()
LP = io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()

print("--- the shared red button ---")
# ONE button object serves the reader, an export, a save and colour
# restoration. I renamed it at CREATION, so an export's cancel would
# have read "Skip this one".
check("it is still born 'Stop'",
      "el('button','wbtn danger','Stop')" in UI)
check("the label is set per job",
      "o.stop.textContent=stopLabel||'Stop';" in UI)
check("and only the reader's job asks for the skip wording",
      "null,'Skip this one');" in UI)
check("set() actually takes that label",
      "const set=(o,live,what,name,pct,onStop,queued,stopLabel)=>{" in UI)

print("\n--- a total may not out-count the page it sits on ---")
check("a chapter's total counts what the pages show",
      "const tot=mediaItems(g).length;" in UI)
check("...not everything the game owns",
      "const tot=g.sessions.length+g.clips.length;" not in UI)
check("the page in flight says what the landed page says",
      UI.count("page ${sp.k+1} of ${sp.pagesN}") == 2)
check("the bare roman page mark is gone from both",
      "` \u00b7 ${roman(sp.k+1)}`" not in UI)

print("\n--- controls that would have been dead on arrival ---")
check("'fill in what is missing' still honours the do-it-again tick",
      "['all','Fill in what is missing',null]" in UI)
# ASKING AGAIN IS NOT ASKING FRESH. Being forced already zeroes the
# three-try wall and already restarts a completed review, so redo buys
# nothing on this path - while the archiving it switches on moves the
# senses sidecar, which is where his TYPED VOICE NAMES live.
check("the refusals shelf does not ask for a from-scratch pass",
      "api.prioritise(rw.path,WANT[rw.kind]||'all')" in UI
      and "rw.kind!=='file'" not in UI)
check("prioritise defaults to filling in, not redoing",
      'def prioritise(self, path, want="all", redo=False):' in LP)
# the audit is the one lane the attic never touches - the drain only
# ever archives listening/hearing/thinking - so a fresh audit has
# nothing to lose and "read it again" is all that press can mean
check("...but an audit ask is still always a fresh read",
      'if str(want or "").lower() == "audit":' in LP.split("def prioritise")[1]
      .split("def ai_force_many")[0])
check("...and the deliberate from-scratch door still passes true itself",
      "runIt(want,fresh)" in UI
      and "['all','Everything, from scratch',true]" in UI)
# THE ATTIC MUST NOT TAKE THE LIVE FILE AWAY. Moving it broke five
# guards that read the previous reading at write time: the .v1/.v2/.v3
# bank, his typed voice names, the eye's better-pass test, the review's
# carry-forward and the .ins staging. It copies.
_a = LP.split("def _ai_attic")[1].split("def _read_sidecar")[0]
check("the attic copies and never moves",
      "_sh.copy2(src, dst)" in _a and "os.replace(" not in _a)
check("...and leaves the banking to the writers that always did it",
      "_bank_sidecar" not in _a)
check("the undo is drawn on the empty-line path too",
      "putBack();" in UI.split("if(!items.length){")[1].split("return;")[0])
check("rf() is declared before the whole-line press calls it",
      UI.count("const rf=()=>{sig=null;paint();};") == 1
      and UI.index("const rf=()=>{sig=null;paint();};")
          < UI.index("const lg=el('button','wbtn danger qletgo'"))

print("\n--- and nothing references a name that was never declared ---")
# the first cut of "Ask again for all" called made.find(...) with no
# `made` anywhere: a ReferenceError on his first press
check("no orphaned `made` lookup", "made.find" not in UI)
check("the shelf rows carry the handle it does use",
      "r.dataset.refusal=String(rw.path||'');" in UI
      and "x.dataset&&x.dataset.refusal===String(rw.path||'')" in UI)

print("\n--- and Skip's three doors against a QUEUED audit ---")
# a queue-driven audit is NOT in force_queue while it runs: its row
# sits in aud_live and the worker's `finally` re-files it AFTER any
# purge. Stop was safe only because it held every lane; Skip holds
# none by design, so it needs all three of these.
_sk = LP.split("def ai_skip_current")[1].split("def ai_queue_clear")[0]
check("1: the skip drops the audit's own recovery memo",
      'if (_AI.get("aud_live") or ("",))[0] == path:' in _sk)
_tk = LP.split("def _takeable")[1].split("forced_now")[0]
check("2: a skipped row cannot take the card if it races back",
      "if _ai_skipped_recently(it[0]):" in _tk)
check("3: nor be handed over by the forced drain",
      "if _ai_skipped_recently(it0[0]):" in LP)
check("an interrupted audit STILL returns to the line",
      'q3.insert(at3, (live[0], "audit"' in LP)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

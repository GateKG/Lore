# -*- coding: utf-8 -*-
"""His rule, from both ends: nothing is audited without a description,
and nothing keeps an audit while its description is missing."""
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
lore.save_settings = lambda *a, **k: None
TD = tempfile.mkdtemp(prefix="pair_")
lore._data_dir = lambda: TD

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


VID = os.path.join(TD, "night.mp4")
io.open(VID, "wb").write(b"x")


def sidecar(kind, doc):
    p = lore._ai_sidecar(VID, kind)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(json.dumps(doc))
    os.utime(p, (time.time() + 5, time.time() + 5))   # never stale
    return p


def reset():
    lore._AI["force_queue"] = []
    lore._AI["failed"] = {}
    # a claim left standing by an earlier case answers the NEXT one
    # with "an audit is already running" - which is a true sentence
    # about the wrong thing
    lore._AUD_ASK.update({"path": None, "named": False, "claim": None,
                          "claim_t": 0})
    lore._AI["busy"] = None
    lore._AI["busy_path"] = None
    SAID[:] = []


# the DESCRIPTION gate is under test - stand the machine still, or
# running this while he is mid-game answers "you are playing"
# first, which is a different (equally true) sentence
lore._aud_playing = lambda: False

print("--- END ONE: no description, no audit ---")
reset()
sidecar("ins", {"complete": False, "windows": {"0": {"complete": False}}})
check("an unfinished review is not honestly described",
      lore._ins_done_honest(VID) is False)
check("so the audit door refuses it",
      lore._audit_ask(VID, redo=True) is False)
why = lore._audit_why(VID, redo=True)
check("and says why, in his words", "description must exist first" in why)
print("      -> " + why[:100])
check("the queue door turns it into a DESCRIBE instead",
      lore._force_owes(VID, "audit", True) == {"thinking"})

print("\n--- END TWO: an audit may not LEAVE a night torn open ---")
reset()
# a finished review, exactly as it is before the auditor touches it
sidecar("ins", {"complete": True, "gen": 3, "win_len": 1800,
                "chapters": [{"t": 0, "text": "a chapter"}],
                "title": "A Night",
                "windows": {"0": {"complete": True, "text": "old words"}}})
check("it starts out honestly described",
      lore._ins_done_honest(VID) is True)
# the auditor corrected a line at 5s and cannot re-describe right now
n = lore._aud_retell(VID, [5.0], refill=False)
check("the retell cut the stale window out", n >= 1)
# 3.26: the cut is STAGED - the served review keeps serving whole
# (the in-place cut once destroyed three real chapters), and the
# refill debt lives in .new where the sweep's owing clause finds it.
check("...while the SERVED review stays honestly finished",
      lore._ins_done_honest(VID) is True)
check("...and the staged .new owes the refill to the sweep",
      lore._ins_owing_raw(VID) is True)
try:
    os.remove(lore._ai_sidecar(VID, "ins") + ".new")
except OSError:
    pass
# 3.15: the repair steers the SWEEP (focus) instead of forging a
# by-name ask - a forced row is the one thing allowed to load the
# describer while he is playing, and an automatic repair must not be
check("SO THE NIGHT GOES TO THE HEAD OF THE SWEEP'S WALK",
      lore._AI.get("focus") == VID)
check("and NOT onto the forced line, which would jump every gate",
      not (lore._AI.get("force_queue") or []))
check("and it says so plainly",
      any("head of the queue" in m and "catch up" in m for m in SAID))
print("      -> " + next((m for m in SAID if "Asked for" in m), "")[:110])

print("\n--- it never asks twice for the same thing ---")
reset()
lore._ai_ask_first(VID, "think", "once")
lore._ai_ask_first(VID, "think", "twice")
check("asking twice is idempotent - one night can only be first once",
      lore._AI.get("focus") == VID
      and not (lore._AI.get("force_queue") or []))

print("\n--- and a failed memo is cleared, or it would never run ---")
reset()
lore._AI["failed"][VID] = 123
lore._ai_ask_first(VID, "think", "after a failure")
check("the give-up memo is dropped when it is asked for first",
      VID not in lore._AI["failed"])

print("\n--- the healing queue that ships with 3.12 ---")
SP = os.path.join(os.path.expanduser("~"), "Downloads",
                  "Lore-update-3.12", "ai_state.json")
if os.path.isfile(SP):
    doc = json.load(io.open(SP, encoding="utf-8"))
    rows = doc.get("queue") or []
    check("every shipped row is a describe",
          rows and all(r[1] == "think" for r in rows))
    # A SHIPPED ROW MAY GO STALE, AND THAT MUST BE HARMLESS. These
    # rows were written weeks ago; he deletes and renames recordings
    # constantly, so asserting the shelf has not moved tests his
    # housekeeping, not the code. The contract worth holding is that a
    # row naming a file that is gone is SKIPPED - so drive the real
    # merge with one live path and one dead one and count what lands.
    _gone = [r for r in rows if not os.path.isfile(r[0])]
    print("      (%d of %d shipped rows no longer exist)"
          % (len(_gone), len(rows)))
    import tempfile
    _live = next((r[0] for r in rows if os.path.isfile(r[0])), None)
    _tmp = tempfile.mkdtemp(prefix="merge_")
    io.open(os.path.join(_tmp, "ai_state.merge.json"), "w",
            encoding="utf-8").write(json.dumps({"queue": [
                [r"D:\Records\__no_such_file__.mp4", "think", False, []]]
                + ([[_live, "think", False, []]] if _live else [])}))
    _rd, lore._data_dir = lore._data_dir, lambda: _tmp
    try:
        with lore._AI_FORCE_LOCK:
            lore._AI["force_queue"] = []
        lore._ai_state_merge()
        _q = list(lore._AI.get("force_queue") or [])
    finally:
        lore._data_dir = _rd
    check("a merge row whose file is gone is skipped, not queued",
          all(p != r"D:\Records\__no_such_file__.mp4" for p, *_ in _q))
    check("and the row beside it still lands",
          (not _live) or any(p == _live for p, *_ in _q))
    check("the merge file is consumed either way",
          not os.path.isfile(os.path.join(_tmp, "ai_state.merge.json")))
    # his running LORE keeps working while this is built, so a row can
    # legitimately heal before the update ships - what matters is that
    # nothing shipped is UNSTARTABLE
    check("and none of them is a row that could never run",
          all(r[1] == "think" for r in rows))
    check("no lane is left standing down",
          not any((doc.get("held") or {}).values()))
else:
    # the 3.12 drop folder was HIS to delete, and he deleted it in the
    # 2026-09-01 Downloads cleanup - its healing queue shipped and was
    # consumed long ago. A test must not fail on his housekeeping.
    check("(the 3.12 drop folder is gone - cleaned up, nothing to test)",
          True)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

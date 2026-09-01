# -*- coding: utf-8 -*-
"""3.02 proven on the real module - the noise verdict end to end, the
rubber-stamp gates, the strike, the retell, and the two scheduling laws
he hit live (Stop holds the lane; audit-now outranks the sweep)."""
import io
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

# A SUITE THAT TICKS MUST PEN THE LIBRARY WALK. _ai_tick carries the
# once-per-boot migrations (strikes, the eye's gate, the re-fold) and
# every one of them WRITES. Without this the walk would be pointed at
# the real D:\Records the moment a guard above the hook stops
# returning early.
import lore as _pen_lore
_pen_lore._library_dirs = lambda out: []
_pen_lore._scan_dir_mp4s = lambda d, k: []

lore.log = lambda m: None
lore._here = lambda: r"C:\Program Files\Lore"
try:
    lore.load_settings()
except Exception:
    pass
lore.SETTINGS["output_dir"] = r"D:\Records"

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


AR_GIB = "\u0625\u0628\u0627 \u0647\u0646\u0627 \u062a\u0648\u0644\u064a\u0644\u0627 \u0633\u0648 \u0645\u064a\u0644"  # أوبا هنا كاريلادا سو نيل
AR_REAL = "\u0627\u0644\u062d\u0645\u062f \u0644\u0644\u0647 \u0648\u0627\u0644\u0644\u0647"  # الحمد لله والله

print("--- the word-safe clip ---")
check("short passes through", lore._aud_clip("hello there") == "hello there")
long = ("the earlier pass is correct because the word fits the chaotic "
        "excited tone of the moment and the speaker is clearly reacting "
        "to the game while his friends are laughing in the background "
        "and the sniper rifle discussion continues for a while after "
        "this line lands which supports the whole reading completely")
c = lore._aud_clip(long, 160)
check("long is cut", len(c) <= 162)
check("cut ends at a word + ellipsis",
      c.endswith("\u2026") and not c[-2].isspace()
      and " " + c[:-1].split(" ")[-1] + " " in long + " ")

print("\n--- the parser: noise accepted, rubber-stamps gated ---")
freq, _low = lore._aud_vocab()
garble = [
    {"t": 10.0, "b": 12.0, "text": "Oba hna karilada su neel.",
     "standing": AR_GIB, "odd": ["karilada"]},
    {"t": 20.0, "b": 22.0, "text": "Alhamdulillah wallah",
     "standing": AR_REAL, "odd": []},
    {"t": 30.0, "b": 32.0, "text": "Vontrelle.", "odd": ["Vontrelle"]},
]
got = {"fixes": [],
       "checked": [{"n": 0, "verdict": "right",
                    "why": "plausible transcription of the exclamation"},
                   {"n": 1, "verdict": "right",
                    "why": "he is thanking God - ordinary Gulf speech"},
                   {"n": 2, "verdict": "noise", "why": "spells nothing"}]}
lore._aud_parse(got, garble)
check("a 'right' stamped on standing gibberish becomes NOISE",
      garble[0]["verdict"] == "noise")
check("a 'right' on real standing Arabic stays right",
      garble[1]["verdict"] == "right")
check("a noise verdict lands as noise", garble[2]["verdict"] == "noise")

g2 = [{"t": 10.0, "b": 12.0, "text": "Oba hna karilada su neel.",
       "standing": AR_GIB, "odd": []},
      {"t": 20.0, "b": 22.0, "text": "Alhamdulillah wallah",
       "standing": AR_REAL, "odd": []}]
got2 = {"fixes": [{"n": 0, "heard": AR_GIB, "why": "the earlier pass is correct"},
                  {"n": 1, "heard": AR_REAL, "why": "confirmed by the story"}],
        "checked": []}
_b, _g, _w, _r, _h, fx2 = lore._aud_parse(got2, g2)
check("re-affirming standing gibberish verbatim becomes NOISE, not right",
      g2[0]["verdict"] == "noise")
check("re-affirming real standing Arabic converts to right",
      g2[1]["verdict"] == "right")
check("neither verbatim re-affirmation becomes a fix", fx2 == [])

longwhy = {"fixes": [],
           "checked": [{"n": 0, "verdict": "unclear", "why": long}]}
g3 = [{"t": 5.0, "b": 6.0, "text": "x y z", "odd": []}]
lore._aud_parse(longwhy, g3)
check("vwhy under the roomy cap is kept WHOLE (his ask: the full thing)",
      g3[0]["vwhy"] == long and len(g3[0]["vwhy"]) <= 600)

print("\n--- the strike, on a temp transcript ---")
td = tempfile.mkdtemp(prefix="aud302_")
VID = os.path.join(td, "night.mp4")
io.open(VID, "w").write("x")
STT = os.path.join(td, "night.stt.json")
INS = os.path.join(td, "night.ins.json")
_real_sidecar = lore._ai_sidecar
lore._ai_sidecar = (lambda p, k, _t=td:
                    os.path.join(_t, "night." + k + ".json")
                    if os.path.dirname(p) == _t else _real_sidecar(p, k))

segs = [
    {"a": 9800, "b": 12000, "t": "Oba hna karilada su neel."},
    {"a": 20000, "b": 22000, "t": AR_GIB, "fx": 1,
     "was": "Charat snapo bas ah"},
    {"a": 30000, "b": 31000, "t": "pinned line", "pin": 1},
    {"a": 40000, "b": 41000, "t": "a clean line nobody doubts"},
]
json.dump({"segments": segs}, io.open(STT, "w", encoding="utf-8"))
gar = [
    {"t": 9.8, "b": 12.0, "text": "Oba hna karilada su neel.",
     "verdict": "noise", "vwhy": "spells nothing in either language",
     "odd": ["karilada"]},
    {"t": 20.0, "b": 22.0, "text": "Charat snapo bas ah",
     "standing": AR_GIB, "verdict": "noise",
     "vwhy": "the guess just redrew the static", "odd": []},
    {"t": 30.0, "b": 31.0, "text": "pinned line", "verdict": "noise",
     "vwhy": "should never land", "odd": []},
]
n = lore._aud_apply_strikes(VID, gar)
d = json.load(io.open(STT, encoding="utf-8"))
sg0, sg1, sg2 = d["segments"][0], d["segments"][1], d["segments"][2]
check("two lines struck, the pinned one untouched", n == 2)
check("struck text is the honest marker",
      sg0["t"] == "[unintelligible]" and sg0["nn"] == 1)
check("the original survives under was",
      sg0["was"] == "Oba hna karilada su neel.")
check("a standing bad guess dies and the TRUE original is kept",
      sg1["t"] == "[unintelligible]"
      and sg1["was"] == "Charat snapo bas ah")
check("the pinned line was never touched",
      sg2["t"] == "pinned line" and "nn" not in sg2)
check("struck rows are marked for the retell",
      gar[0].get("struck") and gar[1].get("struck")
      and not gar[2].get("struck"))
n2 = lore._aud_apply_strikes(VID, gar)
check("a second pass strikes nothing (nn is the idempotency)", n2 == 0)

print("\n--- struck lines are settled everywhere ---")
d2 = json.load(io.open(STT, encoding="utf-8"))
g_after = lore._aud_garble(d2["segments"], freq)
check("the garble list steps around struck lines",
      all(abs(r["t"] - 9.8) > 0.5 and abs(r["t"] - 20.0) > 0.5
          for r in g_after))
rv = lore._aud_revert_nonsense(VID, freq)
d3 = json.load(io.open(STT, encoding="utf-8"))
check("the reverter never takes back a strike ([unintelligible] would "
      "fail its own gate)", rv == 0
      and d3["segments"][0]["t"] == "[unintelligible]")
rows = lore._aud_corrected(VID)
r0 = [r for r in rows if abs(r["t"] - 9.8) < 0.3]
check("the panel hears nn on the corrected row",
      r0 and r0[0]["nn"] is True)

print("\n--- the retell: only the dirty windows go back ---")
ins = {"complete": True, "win_len": 1800, "title": "t", "chapters": [],
       "windows": {"0": {"segments": [], "moments": []},
                   "1800": {"segments": [], "moments": []},
                   "3600": {"segments": [], "moments": []}}}
json.dump(ins, io.open(INS, "w", encoding="utf-8"))
calls = []
_real_ins_one = lore._insights_one
lore._insights_one = lambda p, forced=False, fresh=False: \
    calls.append((os.path.basename(p), forced)) or True
try:
    rt = lore._aud_retell(VID, [10.0, 20.0, 3999.0])
finally:
    lore._insights_one = _real_ins_one
# 3.26: A COMPLETE SERVED REVIEW IS NEVER TOUCHED. The cut goes to
# .new; the upgrade lane refills it and only a complete result swaps.
# The old in-place cut destroyed three real chapters on the shelf -
# this suite used to ASSERT that behavior (Codex round four caught it).
d4 = json.load(io.open(INS, encoding="utf-8"))
check("the SERVED review is byte-identical - complete, all windows",
      d4["complete"] is True and set(d4["windows"]) == {"0", "1800",
                                                        "3600"})
d4n = json.load(io.open(INS + ".new", encoding="utf-8"))
check("the staged .new carries the cut: two dirty windows gone",
      rt == 2 and set(d4n["windows"]) == {"1800"}
      and d4n["complete"] is False and d4n["tries"] == 0)
check("the describer was sent, forced",
      calls == [("night.mp4", True)])
os.remove(INS + ".new")
json.dump({"complete": False, "windows": {"0": {}}},
          io.open(INS, "w", encoding="utf-8"))
lore._insights_one = lambda *a, **k: calls.append("NO") or True
try:
    rt2 = lore._aud_retell(VID, [10.0])
finally:
    lore._insights_one = _real_ins_one
d5 = json.load(io.open(INS, encoding="utf-8"))
check("an incomplete review still gets the MARK - refilled by the "
      "sweep, never described twice",
      rt2 == 1 and "NO" not in calls and d5["windows"] == {})
json.dump({"complete": True, "win_len": 1800,
           "windows": {"0": {}, "1800": {}}},
          io.open(INS, "w", encoding="utf-8"))
lore._insights_one = lambda *a, **k: calls.append("NO2") or True
try:
    rt3 = lore._aud_retell(VID, [10.0], refill=False)
finally:
    lore._insights_one = _real_ins_one
d6 = json.load(io.open(INS, encoding="utf-8"))
d6n = json.load(io.open(INS + ".new", encoding="utf-8"))
check("refill=False (abort/wind) marks without loading any model - "
      "and stages, never cuts, the served review",
      rt3 == 1 and "NO2" not in calls
      and d6["complete"] is True
      and set(d6["windows"]) == {"0", "1800"}
      and set(d6n["windows"]) == {"1800"}
      and d6n["complete"] is False)
os.remove(INS + ".new")
seg_tw = [{"a": 50000, "b": 51000, "t": "same twin words"},
          {"a": 51500, "b": 52400, "t": "same twin words"}]
d_tw = json.load(io.open(STT, encoding="utf-8"))
d_tw["segments"].extend(seg_tw)
json.dump(d_tw, io.open(STT, "w", encoding="utf-8"))
g_tw = [{"t": 51.5, "b": 52.4, "text": "same twin words",
         "verdict": "noise", "vwhy": "the second one is noise",
         "odd": []}]
n_tw = lore._aud_apply_strikes(VID, g_tw, [50.0])
d_tw2 = json.load(io.open(STT, encoding="utf-8"))
tw = [x for x in d_tw2["segments"] if x.get("a") in (50000, 51500)]
check("a twin next to a just-fixed line: the fix survives, the noise "
      "twin is struck",
      n_tw == 1 and tw[0]["t"] == "same twin words"
      and tw[1]["t"] == "[unintelligible]")

print("\n--- audit-now outranks the sweep; named is never eaten ---")
aborts = []


def _fake_abort():
    aborts.append(1)
    lore._AUD_ASK["path"] = None       # the dying worker clears the slot


_real_abort = lore._ai_abort
_real_playing = lore._aud_playing
_real_owing = lore._aud_owing
_real_audit_one = lore._audit_one
lore._ai_abort = _fake_abort
lore._aud_playing = lambda: False
lore._aud_owing = lambda p: True
lore._audit_one = lambda p: True
# 3.12 refuses to audit a night without a finished description. This
# block is about TAKEOVER priority, so stand the description up - the
# gate itself is proven end-to-end in pairtest.py
_real_honest2 = lore._ins_done_honest
lore._ins_done_honest = lambda p: True
lore._AI["busy"] = None
lore._AI["held"] = {"listening": False, "hearing": False,
                    "thinking": False, "auditing": False}
try:
    lore._AUD_ASK.update({"path": r"D:\Records\a.mp4", "named": False,
                          "claim": None})
    check("the sweep never stacks on a running audit",
          lore._audit_ask(r"D:\Records\b.mp4", redo=False) is False
          and not aborts)
    got_it = lore._audit_ask(VID, redo=True)
    time.sleep(0.3)
    check("asked BY NAME takes the card off the sweep's audit",
          got_it is True and len(aborts) == 1)
    check("the claim is released after the takeover",
          lore._AUD_ASK.get("claim") is None)
    for _ in range(50):
        if lore._AUD_ASK.get("path") is None:
            break
        time.sleep(0.1)
    lore._AUD_ASK.update({"path": r"D:\Records\a.mp4", "named": True,
                          "claim": None})
    aborts.clear()
    check("a NAMED audit is never eaten by another ask",
          lore._audit_ask(VID, redo=True) is False and not aborts)
    lore._AUD_ASK.update({"path": None, "named": False,
                          "claim": r"D:\Records\c.mp4"})
    check("a foreign claim locks the door",
          lore._audit_ask(VID, redo=True) is False)
    lore._AUD_ASK.update({"path": None, "named": False, "claim": None})

    lore._ins_done_honest = _real_honest2

    print("\n--- _audit_why mirrors the law ---")
    lore._AUD_ASK.update({"path": r"D:\Records\a.mp4", "named": False})
    _real_honest = lore._ins_done_honest
    lore._ins_done_honest = lambda p: True
    try:
        check("why: by-name passes a sweep audit",
              lore._audit_why(VID, redo=True) == "")
        lore._AUD_ASK["named"] = True
        check("why: a named audit refuses politely",
              "asked for by name" in lore._audit_why(VID, redo=True))
        lore._AUD_ASK["named"] = False
        check("why: without redo it still explains itself",
              "already running" in lore._audit_why(VID, redo=False))
    finally:
        lore._ins_done_honest = _real_honest
    lore._AUD_ASK.update({"path": None, "named": False, "claim": None})

    print("\n--- the sweep honours the claim window ---")
    # a claim carries its CLOCK - an unstamped one is stale by
    # definition and the tick is right to clear it (it used to inherit
    # a timestamp from an earlier _audit_ask in this file, which now
    # returns before claiming)
    lore._AUD_ASK["claim"] = VID
    lore._AUD_ASK["claim_t"] = time.time()
    lore._AI["force_queue"] = []      # a queued describe is not this test
    ticked = []
    _real_slate = None
    lore._AI["busy"] = None
    lore._ai_tick(None)                # must return before any sweep work
    check("_ai_tick stands down during a takeover",
          lore._AI.get("busy") is None)
    lore._AUD_ASK["claim"] = None

    print("\n--- Stop on an audit holds the lane ---")
    api = lore._JsApi.__new__(lore._JsApi)
    lore._AI["busy"] = ("thinking", "the audit \u00b7 night.mp4")
    lore._AI["busy_path"] = VID
    lore._AI["force_queue"] = []
    r = api.ai_stop_current()
    check("the lane is held so the backlog cannot skip-restart",
          r.get("lane") == "auditing"
          and lore._AI["held"]["auditing"] is True)
    lore._AI["held"]["auditing"] = False
    lore._AI["busy"] = ("listening", "song.mp4")
    lore._AI["busy_path"] = None
    r2 = api.ai_stop_current()
    check("a sound stop names its own lane, and quiets them all (3.08)",
          r2.get("lane") == "listening"
          and lore._AI["held"]["listening"] is True
          and lore._AI["held"]["auditing"] is True)
    lore._AI["busy"] = None
finally:
    lore._ai_abort = _real_abort
    lore._aud_playing = _real_playing
    lore._aud_owing = _real_owing
    lore._audit_one = _real_audit_one
    lore._ai_sidecar = _real_sidecar
    lore._AI["busy"] = None
    lore._AUD_ASK.update({"path": None, "named": False, "claim": None})

print("\n--- the prompt carries the new law ---")
P = lore._AUD_SYSTEM
check("noise is a licensed verdict", "noise " in P and "unintelligible" in P)
check("plausible is banned by name", "BANNED" in P and "Plausible" in P)
check("right must state the meaning", "STATES WHAT THE LINE MEANS" in P)
check("the earlier-guess law is spelt out",
      "GUESS earns no respect" in P)
check("the worked noise example survives",
      "redrew the same static" in P)
check("v7 stamped (app version checked at staging, not here)",
      lore._AUD_V == 7)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

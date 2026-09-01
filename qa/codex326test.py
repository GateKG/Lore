# -*- coding: utf-8 -*-
"""3.26: the evidence-lifecycle round, proven on the real functions.
A served review cannot be gutted; a stale ear cannot look current; an
old strike meets the new gates once; no-evidence prose cannot stand;
the strongest peaks survive; a tone word needs its laughter."""
import io
import json
import os
import shutil
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


TMP = tempfile.mkdtemp(prefix="c326_")
VID = os.path.join(TMP, "night.mp4")
io.open(VID, "w").write("x")
lore._thumb_dir = lambda o: TMP
STT = lore._ai_sidecar(VID, "stt")
INS = lore._ai_sidecar(VID, "ins")
AUD = lore._ai_sidecar(VID, "aud")

print("--- the ear-veto, one source of truth ---")
lore._AUD_VOCAB.clear()
lore._AUD_VOCAB["freq"] = {w: 10 for w in
                           ("yep", "got", "this", "boys", "door")}
lore._AUD_VOCAB["at"] = time.time()
lore._AUD_VOCAB["low"] = {}
check("Dagestan-class: a readable multi-word ear vetoes",
      lore._aud_ear_veto("Dagestan.", "Yep, we got this boys") is True)
check("a prompt-echo ear vetoes NOTHING",
      lore._aud_ear_veto("Dagestan.",
                         "Friends gaming on Discord. They speak "
                         "Emirati Gulf Arabic and English.") is False)
check("an unrelated one-word ear vetoes nothing",
      lore._aud_ear_veto("Vontrelle", "door") is False)
check("a verbatim repetition vetoes",
      lore._aud_ear_veto("Vontrelle", "Vontrelle.") is True)

print("\n--- the strike migration, end to end ---")
json.dump({"v": 3, "engine": "qwen3-asr", "reader": 2, "segments": [
    {"a": 5000, "b": 6500, "t": "[unintelligible]", "nn": 1,
     "was": "Dagestan."},
    {"a": 9000, "b": 9800, "t": "[unintelligible]", "nn": 1,
     "was": "zz static", "pin": 1}]},
    io.open(STT, "w", encoding="utf-8"))
json.dump({"complete": True, "win_len": 1800, "title": "t",
           "chapters": [], "windows": {"0": {"segments": [],
                                             "moments": []}}},
          io.open(INS, "w", encoding="utf-8"))
json.dump({"garble": [
    {"t": 5.0, "text": "Dagestan.", "verdict": "noise", "struck": True,
     "ear": "Yep, we got this boys"},
    {"t": 9.0, "text": "zz static", "verdict": "noise", "struck": True,
     "ear": "Yep, we got this boys", "pin_test": 1}]},
    io.open(AUD, "w", encoding="utf-8"))
lore._library_dirs = lambda out: [(TMP, "x")]
lore._scan_dir_mp4s = lambda d, k: [{"path": VID}]
lore._aud_strike_migration()
d1 = json.load(io.open(STT, encoding="utf-8"))
check("the struck line is given back from 'was'",
      d1["segments"][0]["t"] == "Dagestan."
      and "nn" not in d1["segments"][0])
check("a pinned row is never touched",
      d1["segments"][1]["t"] == "[unintelligible]"
      and d1["segments"][1].get("nn") == 1)
check("the transcript was banked first",
      os.path.isfile(STT + ".v1"))
a1 = json.load(io.open(AUD, encoding="utf-8"))
check("the aud row re-litigates: unclear + ear_kept, strike flag gone",
      a1["garble"][0]["verdict"] == "unclear"
      and a1["garble"][0].get("ear_kept") is True
      and "struck" not in a1["garble"][0])
check("the sidecar is generation-stamped - the walk never repeats",
      int(a1.get("sg") or 0) >= 2)
check("the dirty window was STAGED for re-describe, served intact",
      os.path.isfile(INS + ".new")
      and json.load(io.open(INS, encoding="utf-8"))["complete"] is True)
os.remove(INS + ".new")

print("\n--- a stale ear cannot look current ---")
check("an older reader is not current, whatever the app expects now",
      lore._stt_current_doc({"v": 3, "engine": "qwen3-asr",
                             "reader": lore._STT_READER - 1}) is False)
check("a gguf-routed engine is still the qwen family",
      lore._stt_current_doc({"v": 3, "engine": "qwen3-asr-gguf",
                             "reader": lore._STT_READER}) is True)
check("the head-read sees the stale reader",
      lore._stt_stale_reader(VID) is True)

print("\n--- no-evidence prose cannot stand (Ask) ---")
api = lore._JsApi.__new__(lore._JsApi)
api._safe_path = lambda p: p
json.dump({"v": 3, "engine": "qwen3-asr",
           "reader": lore._STT_READER, "segments": [
    {"a": 5000, "b": 8000, "t": "I know the way"}]},
    io.open(STT, "w", encoding="utf-8"))
_real = lore._ask_llm


def ask(answer, hits):
    lore._ask_llm = lambda *a, **k: ({"answer": answer, "hits": hits},
                                     "")
    try:
        return api.ask_video(VID, "what?")
    finally:
        lore._ask_llm = _real


r = ask("Alice buried the treasure at dawn.", [])
check("hits=[] + confident prose -> replaced with not-found",
      "could not verify" in r["answer"] and "Alice" not in r["answer"])
r = ask("Nothing about treasure was said.", [])
check("hits=[] + an honest negative -> the negative stands",
      "Nothing about treasure" in r["answer"])
r = ask("He knew the way.", [{"t": 5.0, "quote": "I know the way"}])
check("a grounded answer still stands untouched",
      r["answer"] == "He knew the way." and len(r["hits"]) == 1)

print("\n--- the strongest peaks survive (hype) ---")
SNS = lore._ai_sidecar(VID, "sns")
v = [0.1] * 3000
for i, x in [(100, 0.9), (200, 0.8), (300, 0.7)] + \
        [(400 + 20 * k, 0.5 + 0.001 * k) for k in range(45)]:
    v[i] = x
json.dump({"hype": {"v": v, "hop": 3.0}},
          io.open(SNS, "w", encoding="utf-8"))
h = api.hype(VID)
check("the three strongest peaks are all retained",
      h["ok"] and 300.0 in h["peaks"] and 600.0 in h["peaks"]
      and 900.0 in h["peaks"])
check("peaks come back in time order, capped at 40",
      h["peaks"] == sorted(h["peaks"]) and len(h["peaks"]) <= 40)

print("\n--- a tone word needs its laughter ---")
moments = [{"t": 100.0, "kind": "funny"},
           {"t": 200.0, "kind": "funny"},
           {"t": 300.0, "kind": "funny"}]
sns = {"hype": {"v": [0.1] * 200, "hop": 3.0}, "events": []}
for i in range(95, 105):
    sns["hype"]["v"][i] = 0.9          # t=300 area hot
hl = {"events": [{"t": 102.0, "kind": "laugh"}]}
# baseline 0.1, a real hot region so p85 sits at 0.5: t=200 (idx 66)
# is hot at 0.9, t=300 (idx 100) is genuinely cold at 0.1
_v2 = [0.1] * 200
for _i in range(150, 190):
    _v2[_i] = 0.5
for _i in range(60, 70):
    _v2[_i] = 0.9
sns2 = {"hype": {"v": _v2, "hop": 3.0}, "events": []}
n = lore._ins_retone(moments, sns2, hl)
check("funny with a real HL laugh stands",
      moments[0]["kind"] == "funny")
check("funny + hot + no laugh becomes excited",
      moments[1]["kind"] == "excited"
      and moments[1].get("kind0") == "funny")
check("funny + cold + no laugh becomes a plain moment",
      moments[2]["kind"] == "" and moments[2].get("kind0") == "funny")

shutil.rmtree(TMP, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

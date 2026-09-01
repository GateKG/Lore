# -*- coding: utf-8 -*-
"""3.03 proven on the real module - the splitter, the partial strike,
the retro-heal, the why refresh, and the pn settlement rules."""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

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


freq, _low = lore._aud_vocab()
UNK = "[unintelligible]"

print("--- the sentence splitter, on his real vocabulary ---")
k, n = lore._aud_keep_split(
    "She's downstairs. I saw her. Nulika nujai nulik anqadri oh.", freq)
check("the readable head survives, only the static is struck",
      k == "She's downstairs. I saw her. " + UNK and n == 2)
k2, n2 = lore._aud_keep_split("Ostam vekkuri shonaas wat? Yeah.", freq)
check("a readable TAIL survives too", k2 == UNK + " Yeah." and n2 == 1)
k3, _ = lore._aud_keep_split("At Riyaat Mur.", freq)
check("a single-sentence line still strikes whole", k3 is None)
k4, _ = lore._aud_keep_split("I saw her. She ran away.", freq)
check("an all-clean line is never split (not the splitter's call)",
      k4 is None)
k5, n5 = lore._aud_keep_split(
    "Okay let's go. Nulika nujai barlo. Wagra fintok shal. I saw her.",
    freq)
check("a RUN of static collapses to one marker",
      k5 == "Okay let's go. " + UNK + " I saw her." and n5 == 2)

print("\n--- the partial strike, end to end ---")
td = tempfile.mkdtemp(prefix="aud303_")
VID = os.path.join(td, "night.mp4")
io.open(VID, "w").write("x")
STT = os.path.join(td, "night.stt.json")
_real_sidecar = lore._ai_sidecar
lore._ai_sidecar = (lambda p, kk, _t=td:
                    os.path.join(_t, "night." + kk + ".json")
                    if os.path.dirname(p) == _t else _real_sidecar(p, kk))

segs = [
    {"a": 9800, "b": 12000,
     "t": "She's downstairs. I saw her. Nulika nujai nulik anqadri oh."},
    {"a": 30000, "b": 31000, "t": "At Riyaat Mur."},
    {"a": 50000, "b": 51000, "t": "Wagra fintok shal barlo.", "nn": 1,
     "fx": 1, "was": "Okay let's go. Wagra fintok shal barlo.",
     "fxw": "old strike why"},
]
segs[2]["t"] = "[unintelligible]"
json.dump({"segments": segs}, io.open(STT, "w", encoding="utf-8"))

gar = [
    {"t": 9.8, "b": 12.0,
     "text": "She's downstairs. I saw her. Nulika nujai nulik anqadri oh.",
     "verdict": "noise", "vwhy": "the tail spells nothing", "odd": []},
    {"t": 30.0, "b": 31.0, "text": "At Riyaat Mur.", "verdict": "noise",
     "vwhy": "no words in either language", "odd": []},
]
n = lore._aud_apply_strikes(VID, gar, [], freq)
d = json.load(io.open(STT, encoding="utf-8"))
s0, s1 = d["segments"][0], d["segments"][1]
check("both noise lines were struck", n == 2)
check("the mixed line is a PARTIAL strike - words kept, static out",
      s0["t"] == "She's downstairs. I saw her. " + UNK
      and s0.get("pn") == 1 and not s0.get("nn"))
check("its original survives under was",
      s0["was"].startswith("She's downstairs"))
check("the all-noise line still strikes whole",
      s1["t"] == UNK and s1.get("nn") == 1 and not s1.get("pn"))

print("\n--- pn is settled, but stays alive on the page ---")
g_after = lore._aud_garble(d["segments"], freq)
check("the garble list steps around partial strikes",
      all(abs(r["t"] - 9.8) > 0.5 for r in g_after))
rv = lore._aud_revert_nonsense(VID, freq)
d2 = json.load(io.open(STT, encoding="utf-8"))
check("the reverter never touches a partial strike",
      rv == 0 and d2["segments"][0]["t"].startswith("She's downstairs"))
rows = [(sg["a"], sg["t"].lower(), sg["t"])
        for sg in d2["segments"] if sg.get("t") and not sg.get("nn")]
check("a partial line stays searchable (only full strikes leave)",
      any("downstairs" in r[1] for r in rows)
      and not any(r[2] == UNK and r[0] == 30000 for r in rows))

print("\n--- the retro-heal of old full strikes ---")
healed = lore._aud_restrike(VID, freq)
d3 = json.load(io.open(STT, encoding="utf-8"))
s2 = d3["segments"][2]
check("an old whole-line strike gives its readable head back",
      len(healed) == 1 and abs(healed[0] - 50.0) < 0.2
      and s2["t"] == "Okay let's go. " + UNK
      and s2.get("pn") == 1 and not s2.get("nn"))
check("the healed line's why says what came back",
      "readable sentences were given back" in s2.get("fxw", ""))
check("healing is idempotent", lore._aud_restrike(VID, freq) == [])

print("\n--- W1: a partial strike never absorbs its twin's strike ---")
d3["segments"].append({"a": 70000, "b": 71000,
                       "t": "Same twin sentence. " + UNK, "pn": 1,
                       "fx": 1,
                       "was": "Same twin sentence. Blorgo fizzun gah."})
d3["segments"].append({"a": 71500, "b": 72400,
                       "t": "Same twin sentence. Blorgo fizzun gah."})
json.dump(d3, io.open(STT, "w", encoding="utf-8"))
g_tw = [{"t": 71.5, "b": 72.4,
         "text": "Same twin sentence. Blorgo fizzun gah.",
         "verdict": "noise", "vwhy": "the tail is static", "odd": []}]
n_tw = lore._aud_apply_strikes(VID, g_tw, [], freq)
d7 = json.load(io.open(STT, encoding="utf-8"))
twA = [x for x in d7["segments"] if x.get("a") == 70000][0]
twB = [x for x in d7["segments"] if x.get("a") == 71500][0]
check("the pn twin is untouched and the REAL noise line is struck",
      n_tw == 1 and twA["t"] == "Same twin sentence. " + UNK
      and twB.get("pn") == 1
      and twB["t"] == "Same twin sentence. " + UNK)

print("\n--- W2: struck static never trains the judge ---")
import tempfile as _tf
vtd = _tf.mkdtemp(prefix="aud303v_")
json.dump({"segments": [
    {"a": 1000, "b": 2000, "t": "Realwords kept fine. " + UNK,
     "pn": 1, "fx": 1,
     "was": "Realwords kept fine. Gibbozap jibbotron wexal."},
]}, io.open(os.path.join(vtd, "x.stt.json"), "w", encoding="utf-8"))
_real_thumb = lore._thumb_dir
_sav = dict(lore._AUD_VOCAB)
lore._thumb_dir = lambda p: vtd
lore._AUD_VOCAB["freq"] = None
lore._AUD_VOCAB["at"] = 0
try:
    f2, _l2 = lore._aud_vocab()
finally:
    lore._thumb_dir = _real_thumb
    lore._AUD_VOCAB.update(_sav)
check("kept words count; the struck static and the marker never do",
      f2.get("realwords") == 1 and f2.get("kept") == 1
      and "gibbozap" not in f2 and "unintelligible" not in f2)

print("\n--- W3: put-it-back matches a long partial strike by its head ---")
longkeep = ("This sentence is real and long " * 12).strip() + ". " + UNK
d7["segments"].append({"a": 90000, "b": 91000, "t": longkeep,
                       "fx": 1, "pn": 1, "was": "orig " * 80})
json.dump(d7, io.open(STT, "w", encoding="utf-8"))
api2 = lore._JsApi.__new__(lore._JsApi)
_rs = lore._JsApi._safe_path
lore._JsApi._safe_path = lambda self, p: p
try:
    r3 = api2.aud_unfix(VID, 90.0, longkeep[:300])
finally:
    lore._JsApi._safe_path = _rs
d8 = json.load(io.open(STT, encoding="utf-8"))
s90 = [x for x in d8["segments"] if x.get("a") == 90000][0]
check("a 300-char panel row still releases its line",
      r3.get("ok") and s90["t"].startswith("orig")
      and "pn" not in s90)
check("the panel's now cap matches what unfix accepts",
      len(lore._aud_public({"corrected": [{"t": 1, "was": "x",
                                           "now": "y" * 400}]})
          ["corrected"][0]["now"]) == 300)

print("\n--- W6: a word's truest form count wins ---")
fr = {"الكلمة": 50,
      "كلمة": 1}
check("a 1-count raw form no longer masks a 50-count al- form",
      lore._aud_word_seen("كلمة", fr) is True)

print("\n--- the why refresh heals the 160-char legacy cuts ---")
d3["segments"].append(
    {"a": 85900, "b": 86500, "t": "\u0645\u0631\u062d\u0628\u0627",
     "fx": 1, "was": "Minar? Harit? Harit?",
     "fxw": "replacing the nonsensical"})
json.dump(d3, io.open(STT, "w", encoding="utf-8"))
LONGWHY = ("The 'listening again' ear clearly hears 'Marhaba' (Hello), "
           "which fits the context of someone greeting or checking if "
           "others are there before the round begins, replacing the "
           "nonsensical phonetic guess entirely.")
g_r = [{"t": 85.9, "standing": "\u0645\u0631\u062d\u0628\u0627",
        "verdict": "right", "vwhy": LONGWHY}]
nr = lore._aud_refresh_whys(VID, g_r)
d4 = json.load(io.open(STT, encoding="utf-8"))
check("the fresh full reasoning replaces the truncated one",
      nr == 1 and d4["segments"][-1]["fxw"] == LONGWHY)
g_r[0]["verdict"] = "unclear"
g_r[0]["vwhy"] = "the ear is no longer sure"
nr2 = lore._aud_refresh_whys(VID, g_r)
d5 = json.load(io.open(STT, encoding="utf-8"))
check("a doubted standing correction says so in its why",
      nr2 == 1 and d5["segments"][-1]["fxw"].startswith(
          "the auditor doubts this reading now - "))

print("\n--- unfix releases a partial strike completely ---")
api = lore._JsApi.__new__(lore._JsApi)
_real_safe = lore._JsApi._safe_path
lore._JsApi._safe_path = lambda self, p: p
try:
    r = api.aud_unfix(VID, 9.8, "She's downstairs. I saw her. " + UNK)
finally:
    lore._JsApi._safe_path = _real_safe
d6 = json.load(io.open(STT, encoding="utf-8"))
s0b = d6["segments"][0]
check("put-it-back restores the original and drops pn",
      r.get("ok") and s0b["t"].endswith("anqadri oh.")
      and "pn" not in s0b and s0b.get("pin") == 1)

print("\n--- contracts ---")
pub = lore._aud_public({"garble": [{"t": 1.0, "text": "x",
                                    "standing": "\u0645", "verdict": "unclear",
                                    "vwhy": "y" * 900}]})
check("the panel hears standing and the fuller why",
      pub["garble"][0]["standing"] is True
      and len(pub["garble"][0]["vwhy"]) == 800)
check("clip default is roomy now",
      lore._aud_clip("w " * 400).endswith("\u2026")
      and len(lore._aud_clip("w " * 400)) <= 600)
check("the prompt teaches the per-sentence strike",
      "PER SENTENCE" in lore._AUD_SYSTEM)
check("v7 stamped (app version checked at staging, not here)",
      lore._AUD_V == 7)

lore._ai_sidecar = _real_sidecar
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

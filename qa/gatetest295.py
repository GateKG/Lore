# -*- coding: utf-8 -*-
"""The sense gate and the dossier, proven on his real data.

The gate is tested against LAST NIGHT'S ACTUAL CORRECTIONS - the ones he
called gibberish must fail, and the ones with real Arabic must pass.
The dossier is built for real doubtful lines and checked for the things
he said were missing: the conversation, the tone, the sights, the sound.
Imports the module itself - no extraction drift.
"""
import io
import json
import os
import sys
import time

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8",
                           errors="replace")
except Exception:
    pass

lore.log = lambda m: None
lore._here = lambda: r"C:\Program Files\Lore"
try:
    lore.load_settings()
except Exception:
    pass
lore.SETTINGS["output_dir"] = r"D:\Records"

TH = r"D:\Records\.lore_thumbs"
ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


t0 = time.time()
freq, low = lore._aud_vocab()
ar = sum(1 for w in freq if "\u0600" <= w[0] <= "\u06ff")
print("vocab: %d words, %d Arabic (%.1fs)\n" % (len(freq), ar,
                                                time.time() - t0))
check("the vocabulary now knows Arabic", ar > 3000)

print("\n--- the sense gate, on last night's real corrections ---")
GIBBERISH = [  # he called these out; not one is an Arabic word
    "\u064a\u0648\u0645\u0648\u0646 \u062f\u0631\u0633\u0627\u0646\u061f",                    # يومون درسان؟
    "\u0627\u0647\u060c \u0646\u0627\u0641\u0648 \u0627\u0647 \u0645\u0627\u0643\u0633\u064a\u0645\u0648\u0645 \u062f\u0642\u0648\u0647",   # نافو ماكسيموم دقوه
    "\u0648\u0627\u0644\u0643\u0648\u0646\u061f \u0646\u062d\u0641\u064a \u0646\u062d\u064a\u0645",              # والكون؟ نحفي نحيم
    "\u0643\u0648\u0631\u0627 \u0633\u0648\u062f\u0627 \u0642\u064a\u0632\u0647\u061f \u0644\u063a\u0648\u062f\u0627 \u0625\u064a\u0634",  # كورا سودا قيزه؟ لغودا
]
REAL = [
    "\u0627\u064a\u0634 \u062a\u0642\u0648\u0644\u061f Tika tika.",   # ايش تقول؟ + English kept
    "\u0642\u0627\u0644 \u0644\u064a Hey Hey",                        # قال لي Hey Hey
    "\u0627\u0644\u062d\u0645\u062f \u0644\u0644\u0647 \u0648\u0627\u0644\u0644\u0647",  # الحمد لله والله
    "\u0648\u064a\u0646\u0647 \u0645\u0648\u0633\u0649\u061f okay",   # وينه موسى؟ okay
]
for g in GIBBERISH:
    okS, badW = lore._aud_sense(g, freq)
    check("gibberish refused: %s" % g[:24], not okS)
for r in REAL:
    okS, badW = lore._aud_sense(r, freq)
    check("real speech passes: %s" % r[:24], okS)

print("\n--- the dossier, built for a real doubtful line ---")
B = "rocketleague_20260820_233433"
# find the REAL video path - _aud_read's freshness check compares against
# the video's own mtime, so a made-up path reads every layer as empty
vp = None
for d0, kind in lore._library_dirs(lore.SETTINGS["output_dir"]):
    for v in lore._scan_dir_mp4s(d0, kind):
        if os.path.basename(v["path"]).startswith(B):
            vp = v["path"]
if vp is None:
    raise SystemExit("recording not found")
stt_doc, _ = lore._aud_read(vp, "stt")
segs = lore._aud_clocked(stt_doc.get("segments") or [], "a")
sns, _ = lore._aud_read(vp, "sns")
vis, _ = lore._aud_read(vp, "vis")
ins, _ = lore._aud_read(vp, "ins")
src = {"stt": segs, "sns": sns, "vis": vis, "ins": ins}
garble = lore._aud_garble(segs, freq)
# the auditor STRIKES and CORRECTS these as it works, so this
# number legitimately falls over time (measured: 6 doubtful ->
# 4 struck -> 2 left). The finder still has to find them.
check("doubtful lines still found on Rocket League",
      len(garble) >= 1)
if garble:
    d = lore._aud_dossier(garble[0], src, ins)
    print("\nDOSSIER for %.1fs:\n%s\n" % (garble[0]["t"], d[:900]))
    check("the line itself is marked", ">>>" in d)
    check("conversation around it is present", d.count("\n") >= 4)
    check("language tags present", "[en]" in d or "[ar]" in d)
    check("tone is present when the night has a curve",
          ("the room is" in d) == bool((sns or {}).get("hype")))

print("\n--- re-correction: a standing fix is judged by its original ---")
fake = [{"a": 100000, "t": "\u0646\u0627\u0641\u0648 \u062a\u0631\u0648\u0646\u0648\u0645", "was": "Ah nafo thronum", "fx": 1},
        {"a": 200000, "t": "kept line", "pin": 1, "was": "x", "fx": 1},
        {"a": 300000, "t": "Normal words here friend", "lang": "english"}]
g2 = lore._aud_garble(fake, freq)
ts = [r["t"] for r in g2]
check("a standing fix re-enters by its ORIGINAL text",
      any(abs(t - 100.0) < 1 for t in ts)
      and any("standing" in r for r in g2))
check("a pinned line never re-enters", not any(abs(t - 200.0) < 1
                                               for t in ts))

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

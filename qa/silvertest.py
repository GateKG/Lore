# -*- coding: utf-8 -*-
"""Silver vs gold vs nothing, and the sweep finishing a night before
it starts another."""
import io
import json
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

lore.log = lambda m: None
lore.load_settings()
lore.SETTINGS["output_dir"] = r"D:\Records"

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


api = lore._JsApi.__new__(lore._JsApi)
api._safe_path = lambda p: p

print("--- the three states, on temp sidecars ---")
TD = tempfile.mkdtemp(prefix="mark_")
_real = lore._ai_sidecar
lore._ai_sidecar = (lambda p, k, _t=TD:
                    os.path.join(_t, os.path.basename(p) + "." + k
                                 + ".json"))


def night(name, ins=None, aud=None, covers=False):
    """covers=True stamps the audit with the clock of the description
    it read - which is the whole difference between gold and silver."""
    p = os.path.join(TD, name + ".mp4")
    with io.open(p, "wb") as fh:
        fh.write(b"x")
    if ins is not None:
        # CLOSE IT BEFORE READING ITS CLOCK. Reading the mtime of a
        # handle that has not been flushed yet made this test fail
        # about one run in ten - and a flaky test is worse than none.
        with io.open(lore._ai_sidecar(p, "ins"), "w",
                     encoding="utf-8") as fh:
            fh.write(json.dumps(ins))
    if aud is not None:
        if covers:
            aud = dict(aud)
            aud["src"] = {"ins": round(os.path.getmtime(
                lore._ai_sidecar(p, "ins")), 1)}
        with io.open(lore._ai_sidecar(p, "aud"), "w",
                     encoding="utf-8") as fh:
            fh.write(json.dumps(aud))
    return p


gold = night("gold", ins={"complete": True, "chapters": [{"t": 0}]},
             aud={"complete": True, "v": lore._AUD_V}, covers=True)
silver_a = night("silver_audit",
                 ins={"complete": True, "chapters": [{"t": 0}]},
                 aud={"complete": True, "v": lore._AUD_V - 2})
silver_d = night("silver_desc",
                 ins={"complete": False, "chapters": [{"t": 0}],
                      "windows": {"0": {}}},
                 aud={"complete": True, "v": lore._AUD_V})
nothing = night("nothing")

f = api.have_flags([gold, silver_a, silver_d, nothing])
check("a current audit that read THIS description is GOLD",
      f[gold]["aud_lvl"] == 2)
check("an audit that did not read this description is SILVER",
      f[silver_a]["aud_lvl"] == 1 and f[silver_a]["aud"] is False)
check("and it says WHICH version it was",
      f[silver_a]["aud_v"] == lore._AUD_V - 2)
check("no audit at all is nothing (0)", f[nothing]["aud_lvl"] == 0)
check("a described night whose audit read it is GOLD",
      f[gold]["ins_lvl"] == 2)
check("a description no audit has read is SILVER, not nothing",
      f[silver_d]["ins_lvl"] == 1)
check("and it says why, in his terms",
      bool(f[silver_d]["ins_why"]))
check("no review at all is nothing", f[nothing]["ins_lvl"] == 0)
lore._ai_sidecar = _real

print("\n--- and on HIS shelf: Big Walk reads silver, both marks ---")
BW = r"D:\Records\Big Walk\Videos\big walk_20260807_183128.mp4"
if os.path.isfile(BW):
    g = api.have_flags([BW])[BW]
    # NOT A SNAPSHOT - AN INVARIANT. Big Walk was silver when this was
    # written and he has since re-run its transcript and audit, so
    # asserting "it is silver" now tests how recently he pressed a
    # button. What must ALWAYS hold is that the mark and the reason
    # agree: gold exactly when the audit has read the description the
    # tome is showing, silver whenever it read an older one, and never
    # a silver that cannot say why.
    covers = lore._aud_covers_now(BW)
    check("gold exactly when the audit covers today's description",
          (g["aud_lvl"] == 2) == bool(covers))
    check("a silver mark always carries its reason",
          g["aud_lvl"] != 1 or bool(g["aud_why"]))
    check("a described night is never marked as undescribed",
          (g["ins_lvl"] > 0) == bool(lore._ins_done_honest(BW)))
    print("      ins_lvl=%s  aud_lvl=%s  aud_v=%s"
          % (g["ins_lvl"], g["aud_lvl"], g["aud_v"]))
else:
    check("(Big Walk not on the shelf)", True)

print("\n--- how many nights are SILVER-audited right now? ---")
n_sil = n_gold = n_non = 0
paths = []
for d0, kind in lore._library_dirs(r"D:\Records"):
    for v in lore._scan_dir_mp4s(d0, kind):
        paths.append(v["path"])
for i in range(0, len(paths), 300):
    for p, row in api.have_flags(paths[i:i + 300]).items():
        n_sil += row["aud_lvl"] == 1
        n_gold += row["aud_lvl"] == 2
        n_non += row["aud_lvl"] == 0
print("      gold %d  ·  SILVER %d  ·  none %d" % (n_gold, n_sil, n_non))
# HONEST: his shelf has NO silver-audited nights - every audit on it is
# already v7. That half of the mark is for the day v8 lands; the half
# that earns its keep today is the silver REVIEW (Big Walk above). A
# test must not demand a condition of his data.
check("every audited night is accounted for as gold or silver",
      n_gold + n_sil == sum(
          1 for i in range(0, len(paths), 300)
          for row in api.have_flags(paths[i:i + 300]).values()
          if row["aud_lvl"] > 0))
n_sil_ins = 0
for i in range(0, len(paths), 300):
    for row in api.have_flags(paths[i:i + 300]).values():
        n_sil_ins += row["ins_lvl"] == 1
print("      reviews torn open and shown SILVER: %d" % n_sil_ins)
check("and the silver REVIEW mark has real nights to show",
      n_sil_ins > 0)

print("\n--- the sweep keeps a night until it is finished ---")
src = io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()
check("the walk puts the focused night first",
      "_focus = _AI.get(\"focus\")" in src
      and "vids = [_focus] + [x for x in vids if x != _focus]" in src)
# "= path" contains "= p" as a substring - count the dispatch sites
# exactly, or the assertion passes and fails for the wrong reasons
check("every sweep dispatch claims the night",
      len(re.findall(r'_AI\["focus"\] = p(?![a-z])', src)) == 4)
check("and it is released when nothing is left to start",
      '_AI["focus"] = None' in src)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

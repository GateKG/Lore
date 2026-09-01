# -*- coding: utf-8 -*-
"""3.27: the round-four items that needed real surgery, on the real
functions. A generation belongs to the words, not the run; a banked
audit's ear still counts."""
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
lore.log = lambda m: SAID.append(str(m))
lore.load_settings()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


TMP = tempfile.mkdtemp(prefix="c327_")
VID = os.path.join(TMP, "night.mp4")
io.open(VID, "w").write("x")
lore._thumb_dir = lambda o: TMP
# THE LIBRARY WALK IS PENNED IN BEFORE ANY MIGRATION RUNS. Both of
# this round's migrations walk _library_dirs/_scan_dir_mp4s and WRITE;
# stubbing them anywhere below the first call would point a real
# mutation at D:\Records. (The _thumb_dir stub above is the second
# lock: a real video's sidecars resolve into this temp dir and are
# simply not there.)
lore._library_dirs = lambda out: [(TMP, "x")]
lore._scan_dir_mp4s = lambda d, k: [{"path": VID}]
STT = lore._ai_sidecar(VID, "stt")
INS = lore._ai_sidecar(VID, "ins")
AUD = lore._ai_sidecar(VID, "aud")
NOW = time.time()


def wr(path, doc, age=100):
    json.dump(doc, io.open(path, "w", encoding="utf-8"))
    os.utime(path, (NOW - age, NOW - age))


os.utime(VID, (NOW - 1000, NOW - 1000))
SEGS = [{"a": i * 90000, "b": i * 90000 + 4000,
         "t": "we push the bridge now boys what a night"}
        for i in range(60)]
WINS = {"0": {"segments": [{"name": "Old A", "what": "old a",
                            "from": 10.0, "to": 700.0}], "moments": []},
        "1800": {"segments": [{"name": "Old B", "what": "old b",
                               "from": 1810.0, "to": 2400.0}],
                 "moments": []}}


def ins_doc(gen, complete=True, wins=None):
    return {"v": 3, "engine": "local", "gen": gen,
            "src_stt": {"mt": 0, "reader": 3},
            "title": "Old Night", "summary": "s",
            "chapters": [{"t": 10.0, "b": 600.0, "label": "Old A",
                          "what": "old a"}],
            "segments": [], "moments": [], "clips": [],
            "names_fixed": [],
            "windows": WINS if wins is None else wins,
            "win_len": 1800, "vdur": 3600.0,
            "complete": complete, "tries": 0}


class FakePr:
    def poll(self):
        return None


class FakeSrv:
    def __init__(self):
        self.pr = FakePr()

    def ask(self, sysp, user, max_tokens=0, schema=None, images=None):
        if schema is lore._TITLE_SCHEMA:
            return json.dumps({"title": "Boys Night",
                               "summary": "the boys push the bridge"})
        return json.dumps({"segments": [
            {"name": "New Bridge Fight", "what": "they push it",
             "from_line": 0, "to_line": 5, "topics": ["bridge"],
             "quote": ""}], "moments": []})

    def stop(self):
        pass


lore._describer_paths = lambda: ("exe", "mdl")
lore._video_duration = lambda p: 3600.0
lore._av_durations = lambda p: (3600.0, 3600.0)
lore._desc_mmproj = lambda: None
lore._grab_frames = lambda *a, **k: []
lore._AI["abort"] = False
lore._AI["wind"] = False
lore.SETTINGS["insights_auto"] = True

print("--- a generation belongs to the words, not the run ---")
wr(STT, {"v": lore._STT_V, "engine": "qwen3-asr", "reader": 3,
         "segments": SEGS}, 500)
# a review told by an OLDER describer, resumed after a staged retell:
# the run is current, the surviving words are not
wr(INS, ins_doc(2), 100)
wr(INS + ".new", ins_doc(2, complete=False,
                         wins={"0": WINS["0"]}), 50)
lore._INS_OWE_CACHE.clear()
lore._DESC_KEEP["srv"] = FakeSrv()
lore._insights_one(VID, forced=True)
d = json.load(io.open(INS, encoding="utf-8"))
check("kept old-engine windows keep their generation",
      int(d.get("gen") or 0) == 2)
lore._desc_mmproj = lambda: "mm"     # the upgrade lane is eye-gated
lore._INS_OWE_CACHE.clear()
check("...so the night is still honestly owed its upgrade",
      lore._ins_owing_raw(VID) is True)
lore._desc_mmproj = lambda: None

for p in (INS, INS + ".new", INS + ".v1", INS + ".v2"):
    if os.path.isfile(p):
        os.remove(p)
wr(INS, ins_doc(3), 100)
wr(INS + ".new", ins_doc(3, complete=False,
                         wins={"0": WINS["0"]}), 50)
lore._INS_OWE_CACHE.clear()
lore._DESC_KEEP["srv"] = FakeSrv()
lore._insights_one(VID, forced=True)
d = json.load(io.open(INS, encoding="utf-8"))
check("a current-generation resume stays current",
      int(d.get("gen") or 0) == lore._INS_GENERATION)

print("\n--- the describer covers the window it was given ---")
# the real failure, reproduced: a model that answers about the first
# ~48 lines of whatever it is handed and stops (measured median 48,
# because the head used to say "three to five stretches")
BIG = [{"a": i * 10000, "b": i * 10000 + 6000, "t": "row %d here" % i}
       for i in range(155)]


class LazySrv:
    """Covers lines 0..47 of any slice, then stops - like the real one."""

    def __init__(self):
        self.pr = FakePr()
        self.saw = []          # the rows each ask actually received

    def ask(self, sysp, user, max_tokens=0, schema=None, images=None):
        if schema is lore._TITLE_SCHEMA:
            return json.dumps({"title": "A Night", "summary": "s"})
        body = user.split("\n\n", 1)[-1]
        rows = [int(w[4:]) for ln in body.splitlines()
                for w in ln.split() if w.startswith("row=")]
        rows = rows or [int(x.split("row ")[1].split()[0])
                        for x in body.splitlines() if "row " in x]
        self.saw.append(rows)
        return json.dumps({"segments": [
            {"name": "Part %d" % len(self.saw), "what": "stuff",
             "from_line": 0, "to_line": 47, "topics": [], "quote": ""}],
            "moments": []})

    def stop(self):
        pass


for p in (INS, INS + ".new", INS + ".v1", INS + ".v2", INS + ".v3"):
    if os.path.isfile(p):
        os.remove(p)
wr(STT, {"v": lore._STT_V, "engine": "qwen3-asr", "reader": 3,
         "segments": BIG}, 500)
lore._video_duration = lambda p: 1600.0
lore._av_durations = lambda p: (1600.0, 1600.0)
lore._INS_OWE_CACHE.clear()
lazy = LazySrv()
lore._DESC_KEEP["srv"] = lazy
lore._insights_one(VID, forced=True)
d = json.load(io.open(INS, encoding="utf-8"))
w0 = (d.get("windows") or {}).get("0") or {}
segs = w0.get("segments") or []
check("one lazy ask is no longer the whole window",
      len(lazy.saw) >= 3 and w0.get("asks", 0) >= 3)
check("the ask budget is finite - it cannot grind the card",
      w0.get("asks", 99) <= 5 and len(lazy.saw) <= 6)
seen = set()
for rows in lazy.saw:
    seen.update(rows)
check("every row was actually shown to the model - nothing sampled "
      "away (%d of 155)" % len(seen), len(seen) == 155)
for rows in lazy.saw:
    if rows:
        check_contig = rows == list(range(rows[0], rows[0] + len(rows)))
        if not check_contig:
            break
else:
    check_contig = True
check("each ask saw a CONTIGUOUS run, never every k-th line",
      check_contig)
covered = set()
for sg in segs:
    if isinstance(sg.get("src"), list) and len(sg["src"]) == 2:
        covered.update(range(sg["src"][0], sg["src"][1] + 1))
check("the stretches carry their source rows and cover the window "
      "(%d of 155)" % len(covered), len(covered) >= 147)
check("the window records what it spent and what it left",
      w0.get("rows") == 155 and w0.get("left", -1) == 0)
cov = d.get("cov") or {}
check("the review states how much of the night it tells",
      cov.get("rows") == 155 and cov.get("frac", 0) >= 0.94
      and cov.get("owed") is False)
check("...and a fully-told night reads as finished",
      lore._ins_done_honest(VID) is True)

# a window that stopped early with asks to spare is NOT done
d2 = json.load(io.open(INS, encoding="utf-8"))
d2["windows"]["0"]["asks"] = 2
d2["windows"]["0"]["left"] = 40
d2["cov"]["owed"] = True
wr(INS, d2, 10)
lore._INS_OWE_CACHE.clear()
check("a half-told window is owed, not 'complete'",
      lore._ins_done_honest(VID) is False
      and lore._ins_owing_raw(VID) is True)
# ...but a window that SPENT its budget is terminal - no endless loop
d2["windows"]["0"]["asks"] = 5
d2["cov"]["owed"] = False
wr(INS, d2, 10)
lore._INS_OWE_CACHE.clear()
check("a window that spent its whole budget is finished for good",
      lore._ins_done_honest(VID) is True
      and lore._ins_owing_raw(VID) is False)
# an old review with no coverage count owes exactly one pass
d2.pop("cov")
wr(INS, d2, 10)
lore._INS_OWE_CACHE.clear()
check("a legacy review owes one coverage pass",
      lore._ins_owing_raw(VID) is True)

print("\n--- a count is not a re-telling ---")
# a finished review that predates the coverage count owes the count
# and nothing else: no model, no bank, no swap - and above all its
# clock must not move, because the audit recorded that clock
for p in (INS, INS + ".new", INS + ".v1", INS + ".v2", INS + ".v3"):
    if os.path.isfile(p):
        os.remove(p)
# a genuinely fully-told legacy night: every row falls inside a
# stretch, so the only thing it owes is the count itself
_TOLD = ([{"a": 20000 + i * 20000, "b": 24000 + i * 20000,
           "t": "row %d" % i} for i in range(25)]
         + [{"a": 1820000 + i * 20000, "b": 1824000 + i * 20000,
             "t": "late row %d" % i} for i in range(25)])
wr(STT, {"v": lore._STT_V, "engine": "qwen3-asr",
         "reader": lore._STT_READER, "segments": _TOLD}, 500)
_legacy = ins_doc(3)
_legacy.pop("cov", None)
wr(INS, _legacy, 100)
_mt_before = os.path.getmtime(INS)
_title_before = _legacy["title"]


class NoSrv:
    """Any model call at all is a failure of this path."""

    pr = FakePr()

    def ask(self, *a, **k):
        raise AssertionError("the coverage stamp asked the model")

    def stop(self):
        pass


lore._INS_OWE_CACHE.clear()
check("a legacy review owes its coverage count", lore._ins_owing_raw(VID))
_warm = lore._ins_owing(VID)      # warm the cached judge, as a real
#                                   sweep beat would, and never touch
#                                   it again for the rest of this test
lore._DESC_KEEP["srv"] = NoSrv()
lore._insights_one(VID, forced=False)
d = json.load(io.open(INS, encoding="utf-8"))
check("the count lands without one model call",
      isinstance(d.get("cov"), dict) and d["cov"].get("rows"))
check("the telling is untouched - same title, same chapters",
      d.get("title") == _title_before
      and len(d.get("chapters") or []) == len(_legacy["chapters"]))
check("THE CLOCK DOES NOT MOVE - the audit that read this review "
      "stays gold",
      abs(os.path.getmtime(INS) - _mt_before) < 0.5)
check("nothing was banked and nothing was staged",
      not os.path.isfile(INS + ".v1") and not os.path.isfile(INS + ".new"))
lore._INS_OWE_CACHE.clear()
check("...and the debt is settled", not lore._ins_owing_raw(VID))
# AND THE CACHED JUDGE MUST AGREE - without clearing it by hand.
# The stamp restores the mtime on purpose, so the signature cannot
# see the change: the writer has to tell the caches itself, or the
# very next sweep beat sends the night down the staged lane and
# re-describes the whole thing (measured: 200 of 346 nights).
check("THE CACHED JUDGE AGREES TOO - no hand-clearing",
      lore._ins_owing(VID) is False)

# a review with NO gen key must NOT be promoted to the current one -
# that would settle an engine upgrade it never had
for p in (INS, INS + ".v1"):
    if os.path.isfile(p):
        os.remove(p)
_nogen = ins_doc(3)
_nogen.pop("cov", None)
_nogen.pop("gen")
wr(INS, _nogen, 100)
lore._INS_OWE_CACHE.clear()
lore._DESC_KEEP["srv"] = NoSrv()
lore._insights_one(VID, forced=False)
d = json.load(io.open(INS, encoding="utf-8"))
check("a review with no generation is not promoted by a count",
      int(d.get("gen") or 0) < lore._INS_GENERATION)
lore._desc_mmproj = lambda: "mm"
lore._INS_OWE_CACHE.clear()
check("...so it still owes its engine upgrade",
      lore._ins_owing_raw(VID) is True)
lore._desc_mmproj = lambda: None

print("\n--- a window resumes, it does not restart ---")
for p in (INS, INS + ".new", INS + ".v1", INS + ".v2"):
    if os.path.isfile(p):
        os.remove(p)
wr(STT, {"v": lore._STT_V, "engine": "qwen3-asr",
         "reader": lore._STT_READER, "segments": BIG}, 500)
lore._video_duration = lambda p: 1600.0
lore._av_durations = lambda p: (1600.0, 1600.0)


class HalfSrv:
    """Answers the opener, then refuses to be parsed - the model's
    likeliest failure."""

    def __init__(self):
        self.pr = FakePr()
        self.n = 0

    def ask(self, sysp, user, max_tokens=0, schema=None, images=None):
        if schema is lore._TITLE_SCHEMA:
            return json.dumps({"title": "A Night", "summary": "s"})
        self.n += 1
        if self.n == 1:
            return json.dumps({"segments": [
                {"name": "Part one", "what": "stuff", "from_line": 0,
                 "to_line": 29, "topics": [], "quote": ""}],
                "moments": []})
        return "not json at all"

    def stop(self):
        pass


lore._INS_OWE_CACHE.clear()
h1 = HalfSrv()
lore._DESC_KEEP["srv"] = h1
lore._insights_one(VID, forced=True)
d = json.load(io.open(INS, encoding="utf-8"))
w0 = (d.get("windows") or {}).get("0") or {}
check("a window that could not be finished says what it left",
      int(w0.get("left") or 0) >= 6 and (d.get("cov") or {}).get("owed"))
check("...and the review does not call itself complete",
      lore._ins_done_honest(VID) is False)
n_first = len(w0.get("segments") or [])
asks_first = int(w0.get("asks") or 0)
lore._INS_OWE_CACHE.clear()
h2 = HalfSrv()
lore._DESC_KEEP["srv"] = h2
lore._insights_one(VID, forced=False)
d2 = json.load(io.open(INS, encoding="utf-8"))
w1 = (d2.get("windows") or {}).get("0") or {}
check("the next run RESUMES - the first run's chapters survive",
      len(w1.get("segments") or []) >= n_first)
check("...and the ask budget is spent across runs, not reset",
      int(w1.get("asks") or 0) > asks_first)
lore._INS_OWE_CACHE.clear()
budget_hit = False
for _ in range(6):
    lore._DESC_KEEP["srv"] = HalfSrv()
    lore._insights_one(VID, forced=False)
    lore._INS_OWE_CACHE.clear()
    if not lore._ins_owing_raw(VID):
        budget_hit = True
        break
check("a night the model cannot finish STOPS being re-swept forever",
      budget_hit)

print("\n--- a hole inside an answer is owed like a tail ---")


class HoleSrv:
    """Answers about the head and the far end of every slice, and
    silently skips its own middle - the shape that used to bank
    'nothing left' over a 29-row hole."""

    def __init__(self):
        self.pr = FakePr()
        self.n = 0

    def ask(self, sysp, user, max_tokens=0, schema=None, images=None):
        if schema is lore._TITLE_SCHEMA:
            return json.dumps({"title": "A Night", "summary": "s"})
        self.n += 1
        return json.dumps({"segments": [
            {"name": "head %d" % self.n, "what": "x", "from_line": 0,
             "to_line": 10, "topics": [], "quote": ""},
            {"name": "tail %d" % self.n, "what": "x", "from_line": 40,
             "to_line": 47, "topics": [], "quote": ""}], "moments": []})

    def stop(self):
        pass


for p in (INS, INS + ".new", INS + ".v1", INS + ".v2", INS + ".v3"):
    if os.path.isfile(p):
        os.remove(p)
wr(STT, {"v": lore._STT_V, "engine": "qwen3-asr",
         "reader": lore._STT_READER, "segments": BIG}, 500)
lore._video_duration = lambda p: 1600.0
lore._av_durations = lambda p: (1600.0, 1600.0)
lore._INS_OWE_CACHE.clear()
lore._DESC_KEEP["srv"] = HoleSrv()
lore._insights_one(VID, forced=True)
d = json.load(io.open(INS, encoding="utf-8"))
w0 = (d.get("windows") or {}).get("0") or {}
told = set()
for sg in (w0.get("segments") or []):
    if isinstance(sg.get("src"), list) and len(sg["src"]) == 2:
        told.update(range(sg["src"][0], sg["src"][1] + 1))
check("the HOLE is tracked, not just the tail - the ranges owed are "
      "banked with their positions",
      isinstance(w0.get("pend"), list) and w0.get("pend")
      and any(a > 0 for a, _b in w0["pend"]))
check("a model that will not cover its middle still terminates",
      int(w0.get("asks") or 0) <= 5)
check("...and the review SAYS it is short rather than reading whole",
      (d.get("cov") or {}).get("short") is True
      and (d.get("cov") or {}).get("owed") is False)


class FillSrv(HoleSrv):
    """A realistic model: it skips its middle once, then answers the
    range it is actually handed."""

    def ask(self, sysp, user, max_tokens=0, schema=None, images=None):
        if schema is lore._TITLE_SCHEMA:
            return json.dumps({"title": "A Night", "summary": "s"})
        self.n += 1
        if self.n == 1:
            return HoleSrv.ask(self, sysp, user, max_tokens, schema,
                               images)
        body = user.split("\n\n", 1)[-1]
        n = len([x for x in body.splitlines() if x.strip()])
        return json.dumps({"segments": [
            {"name": "filled %d" % self.n, "what": "x", "from_line": 0,
             "to_line": max(0, n - 1), "topics": [], "quote": ""}],
            "moments": []})


for p in (INS, INS + ".new", INS + ".v1", INS + ".v2", INS + ".v3"):
    if os.path.isfile(p):
        os.remove(p)
lore._INS_OWE_CACHE.clear()
lore._DESC_KEEP["srv"] = FillSrv()
lore._insights_one(VID, forced=True)
d2 = json.load(io.open(INS, encoding="utf-8"))
w2 = (d2.get("windows") or {}).get("0") or {}
told2 = set()
for sg in (w2.get("segments") or []):
    if isinstance(sg.get("src"), list) and len(sg["src"]) == 2:
        told2.update(range(sg["src"][0], sg["src"][1] + 1))
check("a model that answers what it is asked fills the hole "
      "(%d of 155 rows told)" % len(told2), len(told2) >= 150)
check("...and the review reads whole, not short",
      not (d2.get("cov") or {}).get("short")
      and (d2.get("cov") or {}).get("frac", 0) >= 0.95)

print("\n--- gold is not gold over a retelling nobody read ---")
for p in (INS, INS + ".new"):
    if os.path.isfile(p):
        os.remove(p)
wr(INS, ins_doc(3), 100)
wr(AUD, {"v": 7, "complete": True, "when": int(NOW - 50),
         "src": {"ins": os.path.getmtime(INS),
                 "stt": os.path.getmtime(STT)}}, 50)
check("with nothing staged, the audit reads as covering the review",
      lore._aud_covers_now(VID) is True)
wr(INS + ".new", ins_doc(3, complete=False, wins={"0": WINS["0"]}), 40)
check("with a retell staged, it does NOT - the words it read are "
      "queued for replacement", lore._aud_covers_now(VID) is False)
os.remove(INS + ".new")

print("\n--- a sighting earns the gold timeline ---")


def look(c, d="attacking the player", pl="a dark corridor", t=10.0):
    return {"t": t, "creature": c, "doing": d, "place": pl}


check("a monster doing something is worth a mark",
      lore._eye_worth(look("a horned monster", "fighting a monster")))
check("a monster standing still is still a monster",
      lore._eye_worth(look("a skeletal warrior", "standing, holding "
                                                 "a sword")))
check("his own car is not a creature",
      not lore._eye_worth(look("purple car", "driving toward the ball")))
check("the Hearthstone board is not a creature",
      not lore._eye_worth(look("minions and heroes", "attacking")))
check("a teammate is not a creature",
      not lore._eye_worth(look("player character", "attacking")))
check("a gamertag standing around is not a creature",
      not lore._eye_worth(look("zek", "standing near a wall")))
check("a menu frame promotes nothing",
      not lore._eye_worth(look("a horned monster", "attacking",
                               "the loadout menu")))

# the migration: a mark minted by a look today's gate rejects goes;
# one whose look is unknown is left alone; the sound marks never move
for p in (INS, INS + ".new"):
    if os.path.isfile(p):
        os.remove(p)
HL = lore._ai_sidecar(VID, "hl")
VIS = lore._ai_sidecar(VID, "vis")
wr(HL, {"v": 2, "events": [
    {"t": 10.0, "z": 9.0, "kind": "creature"},     # a car - goes
    {"t": 20.0, "z": 9.0, "kind": "creature"},     # a monster - stays
    {"t": 30.0, "z": 9.0, "kind": "creature"},     # no look - stays
    {"t": 40.0, "z": 12.0, "kind": "laugh"},       # sound - untouched
    {"t": 50.0, "z": 11.0}]}, 50)                  # bare peak
wr(VIS, {"looks": [look("purple car", "driving at the ball", "", 10.0),
                   look("a horned monster", "attacking", "a crypt",
                        20.0)]}, 60)
lore._vis_promote_migration()
h1 = json.load(io.open(HL, encoding="utf-8"))
ts = [g["t"] for g in h1["events"]]
check("the car loses its gold mark", 10.0 not in ts)
check("the monster keeps its gold mark", 20.0 in ts)
check("a mark whose look cannot be found is left alone", 30.0 in ts)
check("the sound marks are untouched", 40.0 in ts and 50.0 in ts)
check("the gold sidecar was banked before it changed",
      os.path.isfile(HL + ".v1"))
check("the walk is stamped and never repeats",
      int(h1.get("eg") or 0) >= 1)
n1 = len(h1["events"])
lore._vis_promote_migration()
check("...proven by a second pass changing nothing",
      len(json.load(io.open(HL, encoding="utf-8"))["events"]) == n1)

print("\n--- two things in one second are both kept ---")
for p in (HL + ".v1", HL):
    if os.path.isfile(p):
        os.remove(p)
# laughter lands first (it rides the gold pass); the senses arrive to
# find the seat taken - and used to be dropped on the floor
wr(HL, {"v": 2, "events": [{"t": 100.0, "z": 14.0, "kind": "laugh"},
                           {"t": 300.0, "z": 9.0}]}, 40)
SNS = lore._ai_sidecar(VID, "sns")
wr(SNS, {"events": [{"t": 101.0, "kind": "groan", "sc": 0.9},
                    {"t": 300.5, "kind": "cheer", "sc": 0.9}],
         "ocr": [{"t": 100.5, "kind": "victory", "text": "WINNER"}]}, 30)
n, _e = lore._merge_sns_into_hl(VID)
h2 = json.load(io.open(HL, encoding="utf-8"))
g100 = [g for g in h2["events"] if abs(g["t"] - 100.0) < 2.0][0]
check("the laugh keeps the mark it won",
      g100.get("kind") == "laugh")
check("the groan and the WINNER ride along instead of vanishing",
      set(g100.get("also") or []) >= {"groan", "victory"})
g300 = [g for g in h2["events"] if abs(g["t"] - 300.0) < 2.0][0]
check("an unlabelled mark still simply takes the label",
      g300.get("kind") == "cheer" and not g300.get("also"))
# a re-pick with the words must not erase the recovery
prior = list(h2["events"])
kept = [e for e in prior if e.get("kind")]
ev2 = [{"t": 100.2, "z": 15.0}]
for kv in kept:
    near = [g for g in ev2 if abs(g["t"] - kv["t"]) <= 8.0]
    if near:
        near[0]["kind"] = kv["kind"]
        if kv.get("also"):
            near[0]["also"] = kv["also"]
check("a re-pick carries the second signals forward",
      set(ev2[0].get("also") or []) >= {"groan", "victory"})

print("\n--- the leash asks instead of assuming ---")
# the REAL shipped block, text-sliced out of the worker and driven
# with fake answers - a hand copy of a gate is how the recorder
# oracle spent months reporting a bug that was already fixed
WSRC = io.open(r"D:\Gate LLC\ai\asr_worker.py", encoding="utf-8").read()


import ast as _ast          # noqa: E402
import re as _re            # noqa: E402
import textwrap             # noqa: E402

_WTREE = _ast.parse(WSRC)
_WLINES = WSRC.splitlines()


def _wfunc(name):
    """The real nested guard, lifted out by the parser - never retyped."""
    for node in _ast.walk(_WTREE):
        if isinstance(node, _ast.FunctionDef) and node.name == name:
            return textwrap.dedent(
                "\n".join(_WLINES[node.lineno - 1:node.end_lineno]))
    raise AssertionError("worker has no " + name)


i0 = WSRC.index("        if lang and lang not in KEEP:")
LEASH = textwrap.dedent(
    WSRC[i0:WSRC.index("        if txt and _foreign(txt):", i0)])
NS = {"KEEP": ("english", "arabic"), "sr": 16000, "re": _re}
for fn in ("_foreign", "_impossible", "_ctx_echo", "_arabic_frac"):
    exec(compile(_wfunc(fn), "<w>", "exec"), NS)
def leash(first, first_lang, retry, retry_lang, ctx="", pin="english"):
    """Run the shipped block with these two candidates."""
    ns = dict(NS)
    ns.update({"lang": first_lang, "txt": first, "out": [1],
               "audio": [0.0] * 16000, "ctx": ctx, "last": pin,
               "lost": None, "np": None,
               "stats": {"leash": 0, "leash_kept": 0},
               "ask": lambda a, p, use_ctx=True: (retry, retry_lang)})
    ns["audio"] = type("A", (), {"__len__": lambda s: 16000})()
    exec(compile(LEASH, "<leash>", "exec"), ns)
    return ns["txt"], ns["lost"], ns["stats"]["leash_kept"]


t, lost, kept = leash("\u064a\u0644\u0627 \u0646\u0631\u0648\u062d", "dutch",
                      "Yalla we go now", "english")
check("an Arabic line is not overwritten by the Latin the pin forced",
      t == "\u064a\u0644\u0627 \u0646\u0631\u0648\u062d" and kept == 1)
check("...and the answer that lost is kept beside it",
      lost == "Yalla we go now")
t, lost, kept = leash("Hallo daar vriend", "dutch",
                      "Hello there friend", "english")
check("a plausible retry still wins - two Latin candidates, no pin "
      "effect", t == "Hello there friend" and kept == 0)
t, lost, kept = leash("we push the bridge", "dutch", "", "english")
check("an empty retry never replaces a real line", t ==
      "we push the bridge" and kept == 1)
t, lost, kept = leash("we push the bridge", "dutch",
                      "\u3053\u3093\u306b\u3061\u306f\u4e16\u754c", "japanese")
check("an unreadable alphabet never replaces a real line",
      t == "we push the bridge" and kept == 1)
# THE LATCH: the script guard must ask which way the pin pointed. With
# an ARABIC pin, a Latin retry is real evidence - not the pin talking -
# so it must be allowed to win, or Arabic wins every argument forever.
t, lost, kept = leash("\u064a\u0644\u0627 \u0646\u0631\u0648\u062d", "dutch",
                      "Yalla we go now", "english", pin="arabic")
check("under an ARABIC pin a Latin retry can still win - the guard "
      "does not latch", t == "Yalla we go now" and kept == 0)

print("\n--- nearby is not agreeing ---")
SRC = {"stt": [{"a": 0, "b": 1500, "t": "Okay. Okay."},
               {"a": 2600, "b": 4200, "t": "get behind the door now"}],
       "sns": {"events": [], "ocr": []}, "vis": {"looks": []},
       "ins": {"moments": [{"t": 60.0, "why": "a chapter away"}],
               "chapters": [{"t": 3.0, "label": "The Curio and Malice"}]},
       "laughs": []}
lay, det = lore._aud_says(3.2, SRC)
check("the line that COVERS the second wins, not the first one near it",
      "get behind the door" in det.get("words", ""))
check("a chapter label is shown but does not vote",
      "review" not in lay and "Curio" in det.get("review", ""))
lay2, det2 = lore._aud_says(2.0, SRC)   # in the gap between the two
check("a line that only sits nearby says how far away it was",
      "away:" in det2.get("words", ""))
SRC2 = dict(SRC)
SRC2["ins"] = {"moments": [{"t": 3.2, "why": "he opens the door"}],
               "chapters": []}
lay3, _d3 = lore._aud_says(3.2, SRC2)
check("a moment that names THIS second still counts as a layer",
      "review" in lay3)

print("\n--- a banked audit's ear still counts ---")
lore._AUD_VOCAB.clear()
lore._AUD_VOCAB["freq"] = {w: 10 for w in ("yep", "got", "this",
                                           "boys", "hold", "the",
                                           "door")}
lore._AUD_VOCAB["low"] = {}
lore._AUD_VOCAB["at"] = time.time()
for p in (INS, INS + ".new", INS + ".v1", INS + ".v2", INS + ".v3"):
    if os.path.isfile(p):
        os.remove(p)
wr(INS, ins_doc(3), 100)
# two struck lines; TODAY's audit remembers neither - the audit that
# struck them is banked beside it
wr(STT, {"v": lore._STT_V, "engine": "qwen3-asr", "reader": 3,
         "segments": [
             {"a": 5000, "b": 6500, "t": "[unintelligible]", "nn": 1,
              "was": "Dagestan."},
             {"a": 30000, "b": 31000, "t": "[unintelligible]",
              "nn": 1, "was": "Marwol."}]}, 200)
wr(AUD, {"garble": [{"t": 60.0, "text": "something else",
                     "verdict": "unclear"}]}, 100)
wr(AUD + ".v1", {"garble": [
    {"t": 5.0, "text": "Dagestan.", "verdict": "noise", "struck": True,
     "ear": "Yep, we got this boys"}]}, 300)
wr(AUD + ".v2", {"garble": [
    {"t": 30.0, "text": "Marwol.", "verdict": "noise", "struck": True,
     "ear": "\u0648\u064a\u0646 \u0627\u0644\u0628\u0627\u0628"}]}, 400)
lore._library_dirs = lambda out: [(TMP, "x")]
lore._scan_dir_mp4s = lambda d, k: [{"path": VID}]
lore._aud_strike_migration()
d1 = json.load(io.open(STT, encoding="utf-8"))
check("a line struck two audits ago comes back on the banked ear",
      d1["segments"][0]["t"] == "Dagestan."
      and "nn" not in d1["segments"][0])
check("an ear that agrees with nothing leaves its strike alone",
      d1["segments"][1]["t"] == "[unintelligible]")
a1 = json.load(io.open(AUD, encoding="utf-8"))
rows = [g for g in a1["garble"] if abs(float(g["t"]) - 5.0) < 0.2]
check("the restored line gets a row in TODAY's audit, not a copy "
      "nobody reads",
      rows and rows[0]["verdict"] == "unclear"
      and rows[0].get("ear_kept") is True)
check("the attic itself is never written",
      json.load(io.open(AUD + ".v1", encoding="utf-8"))
      ["garble"][0]["verdict"] == "noise")

n_before = len(a1["garble"])
lore._aud_strike_migration()
a2 = json.load(io.open(AUD, encoding="utf-8"))
check("the walk is idempotent - a second boot changes nothing",
      len(a2["garble"]) == n_before
      and json.load(io.open(STT, encoding="utf-8"))
      ["segments"][0]["t"] == "Dagestan.")

print("\n--- the shelf marker names the walks that finished ---")
MDIR = tempfile.mkdtemp(prefix="c327m_")
lore._data_dir = lambda: MDIR
MARK = os.path.join(MDIR, "shelf.mig")
ran = []


def _fake(nm, boom=False):
    def f():
        ran.append(nm)
        if boom:
            raise RuntimeError("fell over")
    return f


_real_walks = (lore._hl_refold_migration, lore._vis_promote_migration,
               lore._aud_strike_migration)
try:
    # an OLD marker format (a bare number, which is what his machine
    # carries) must prove nothing at all
    io.open(MARK, "w", encoding="utf-8").write("3")
    lore._hl_refold_migration = _fake("refold")
    lore._vis_promote_migration = _fake("eye")
    lore._aud_strike_migration = _fake("strike")
    lore._shelf_migrations()
    for _ in range(60):
        if not lore._MIG_BUSY[0]:
            break
        time.sleep(0.05)
    check("a stale marker retires nothing - all three walks run",
          sorted(ran) == ["eye", "refold", "strike"])
    got = json.load(io.open(MARK, encoding="utf-8"))
    check("the marker records them by name",
          sorted(got.get("done") or []) == ["eye", "refold", "strike"])
    ran[:] = []
    lore._shelf_migrations()
    time.sleep(0.2)
    check("...and a named marker stops the walk entirely", ran == [])

    # a walk that FALLS OVER is not recorded, so it runs again
    io.open(MARK, "w", encoding="utf-8").write(json.dumps({"done": []}))
    ran[:] = []
    lore._hl_refold_migration = _fake("refold")
    lore._vis_promote_migration = _fake("eye", boom=True)
    lore._aud_strike_migration = _fake("strike")
    lore._shelf_migrations()
    for _ in range(60):
        if not lore._MIG_BUSY[0]:
            break
        time.sleep(0.05)
    got = json.load(io.open(MARK, encoding="utf-8"))
    check("a walk that stumbled is NOT retired",
          "eye" not in (got.get("done") or [])
          and "refold" in (got.get("done") or []))
    ran[:] = []
    lore._shelf_migrations()
    for _ in range(60):
        if not lore._MIG_BUSY[0]:
            break
        time.sleep(0.05)
    check("...so it runs again next boot, alone", ran == ["eye"])

    # an empty shelf earns no marker at all
    os.remove(MARK)
    ran[:] = []
    _rs = lore._scan_dir_mp4s
    lore._scan_dir_mp4s = lambda d, k: []
    lore._vis_promote_migration = _fake("eye")
    lore._shelf_migrations()
    for _ in range(60):
        if not lore._MIG_BUSY[0]:
            break
        time.sleep(0.05)
    lore._scan_dir_mp4s = _rs
    check("a shelf nobody could read is never stamped as migrated",
          not os.path.isfile(MARK) and ran == [])
finally:
    (lore._hl_refold_migration, lore._vis_promote_migration,
     lore._aud_strike_migration) = _real_walks

print("\n--- the bank holds what was there BEFORE ---")
for p in (HL, HL + ".v1", HL + ".v2"):
    if os.path.isfile(p):
        os.remove(p)
lore._MIG_BANKED.clear()
wr(HL, {"v": 2, "events": [{"t": 100.0, "z": 14.0, "kind": "laugh"}]}, 40)
_orig = io.open(HL, "rb").read()
wr(SNS, {"events": [{"t": 101.0, "kind": "groan", "sc": 0.9}],
         "ocr": []}, 30)
io.open(MARK, "w", encoding="utf-8").write(json.dumps({"done": []}))
lore._hl_refold_migration()
check("the fold recovered the second signal",
      any(g.get("also") for g in
          json.load(io.open(HL, encoding="utf-8"))["events"]))
check("THE BANK IS THE TIMELINE AS IT STOOD, not the rewritten one",
      os.path.isfile(HL + ".v1")
      and io.open(HL + ".v1", "rb").read() == _orig)
lore._MIG_BANKED.clear()
shutil.rmtree(MDIR, ignore_errors=True)

shutil.rmtree(TMP, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

# -*- coding: utf-8 -*-
"""3.36 - THE NO-LOOPS AUDIT: the owing tests.

Every check here is the same shape: a writer runs, and the owing test
that dispatched it must say NO afterwards with the clock the writer
left (law 1 of the audit); a second beat on the same inputs must be a
no-op (law 2). One check per confirmed finding; fixers append.

R3-1  THE [] WINDOW ARMED THE LEGACY-GAP RULE. The describer stores a
      half hour with fewer than three lines as the bare list [] ("a
      silent half hour is done"). _assemble's coverage count read any
      non-dict window as a LEGACY window (the pre-budget shape) and so
      applied the legacy-gap rule to the whole night: beside a window
      that had spent its five asks, or one told-empty after two parsed
      empty answers, the untold rows behind it tripped the six-row
      clause and cov.owed was stamped True on a review that had just
      finished. _ins_owing_raw returns True on cov.owed with no tries
      bound; the next beat found no missing window, took the staged
      lane with tries 0, re-told every window and the title, banked
      and swapped the served review (a new clock), and the count
      stamped cov.owed True again. Never audited, never done, a full
      re-describe per beat, a byte-identical copy rotated through the
      attic each time. The fix is one line in _assemble: only a DICT
      window without an "asks" key is legacy.

R4-1  THE EAR THAT ADMITTED A FIX DID NOT KEEP IT. _aud_parse lets a
      fix whose words are library-new in when a non-junk relisten ear
      backs it (verbatim or by skeleton); the reverter judged the
      standing fix with the segment's d only, so it was taken back at
      the next audit, re-shortlisted, re-listened, re-admitted and
      re-told - every audit. Fix: the ear rides with the fix to the
      transcript (fxe), and the reverter and both confirmation doors
      in _aud_parse fold it into the sense gate's extra.
R4-2  THE TRIES-2 .NEW LEFT BY N3'S QUIT. Two empty retells leave the
      night as it was (not owed) but the staged file stays; one file
      made _aud_covers_now False (silver for ever), the tally count an
      audit LEFT that no judge owes, and ai_whynot say 'finished'.
      Fix, read-side: a .new condemns the served review only while it
      is LIVE (the owing judge's own bound), the version cache keys on
      the review and the .new too, and the page carries N3's sentence.

Everything runs on tempdirs with a fake describer. No model, no port,
no device, and nothing under D:\\Records or %LOCALAPPDATA%\\Lore is
read or written. The words in the fixtures are game words, never a
person.
"""
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time

ROOT = r"D:\Gate LLC"
sys.path.insert(0, ROOT)
import lore  # noqa: E402

# THE PARITY BASE IS A COMMIT, NOT HEAD. e3212c6 is 3.36 drop N, the
# tree the audit measured; the witness at the foot lifts it whole to
# show the loop was there and is not here.
PARITY_BASE = "e3212c6"

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  ok    " if cond else "  FAIL  ") + name)


def pen(L):
    """A SUITE THAT TICKS MUST PEN THE LIBRARY WALK (aud302's law):
    close every door onto the machine before any call into the module."""
    L._library_dirs = lambda out: []
    L._scan_dir_mp4s = lambda d, k: []
    L.LOG = []
    L.log = lambda m: L.LOG.append(str(m))
    here = tempfile.mkdtemp(prefix="loops336_here_")
    os.makedirs(os.path.join(here, "ai", "packs"))
    L._here = lambda: here
    L._ai_state_save = lambda: None


pen(lore)


def mount(L, root):
    try:
        L.load_settings()
    except Exception:
        pass
    L.SETTINGS["output_dir"] = root
    L.SETTINGS["insights_auto"] = True
    L.SETTINGS["bg_shutdown"] = False
    L.SETTINGS["ffmpeg_path"] = "ffmpeg.exe"
    L._ai_sidecar = lambda p, k: os.path.join(
        os.path.dirname(p),
        os.path.splitext(os.path.basename(p))[0] + "." + k + ".json")
    L._work_dir = lambda: root
    L._AI["abort"] = False
    L._AI["wind"] = False
    L._AI["job_secs"] = 0.0
    L._AI["failed"] = {}
    L._AI["focus"] = None
    L._DESC_KEEP["srv"] = None
    L._INS_OWE_CACHE.clear()
    L._AUD_OWE_CACHE.clear()
    L._STT_RD_CACHE.clear()
    L._PIC_CACHE.clear()
    L._describer_paths = lambda: ("exe", "mdl")
    L._desc_mmproj = lambda: None
    L._pic_black = lambda p: False
    L._grab_frames = lambda p, t, stats=None: []
    L._eye_seen = lambda p: []


VOCAB = ("we push the lane and the tower falls then the round resets "
         "and the timer runs down again").split()


def room_lines(win, n, step=60):
    out = []
    for i in range(n):
        t = int((win * 1800 + 30 + i * step) * 1000)
        out.append({"a": t, "b": t + 2500,
                    "t": " ".join(VOCAB[i % 7:] + VOCAB[:i % 7])})
    return out


def build_night(L, root, per_window, vdur):
    """A reader-7 room transcript with per_window lines in each half
    hour, an empty hl sidecar, and a video of vdur seconds."""
    os.makedirs(root, exist_ok=True)
    vid = os.path.join(root, "night.mp4")
    io.open(vid, "w").write("v")
    os.utime(vid, (time.time() - 300, time.time() - 300))
    segs = []
    for w, n in enumerate(per_window):
        segs += room_lines(w, n)
    json.dump({"v": 3, "engine": "qwen3-asr", "reader": 7,
               "sources": {"voice": False, "game": False, "media": False},
               "segments": segs},
              io.open(L._ai_sidecar(vid, "stt"), "w", encoding="utf-8"))
    json.dump({"v": L._HL_V, "events": []},
              io.open(L._ai_sidecar(vid, "hl"), "w", encoding="utf-8"))
    L._video_duration = lambda p: vdur
    L._story_seconds = lambda p, d: (vdur, "")
    return vid


ASKS = []


def describer(L, answers):
    """answers: window-minute -> callable(use_len, ask_index) -> text.
    Every ask is recorded in ASKS as 'wN' or 'title'."""
    counts = {}

    class FakeDesc(object):
        def __init__(self, port=None):
            self.pr = None

        def start(self, budget=900):
            return True

        def ask(self, system, user, max_tokens=900, schema=None,
                images=None, **kw):
            m = re.search(r"runs from minute (\d+) to minute", user)
            if not m:
                ASKS.append("title")
                return json.dumps({"title": "the lane push",
                                   "summary": "a night of pushing lanes"})
            key = int(m.group(1))
            ASKS.append("w%d" % key)
            n = int(re.search(r"\(0 to (\d+)\)", user).group(1)) + 1
            counts[key] = counts.get(key, 0) + 1
            f = answers.get(key)
            return f(n, counts[key]) if f else ""

        def stop(self):
            pass
    L._DescServer = FakeDesc
    L._DESC_KEEP["srv"] = None


def whole(n, k):
    return json.dumps({"segments": [
        {"name": "the lane push", "what": "they push the lane",
         "topics": ["lane"], "from_line": 0, "to_line": n - 1,
         "quote": ""}], "moments": []})


def empty(n, k):
    return json.dumps({"segments": [], "moments": []})


def one_row(n, k):
    return json.dumps({"segments": [
        {"name": "a single row", "what": "one line only",
         "topics": ["row"], "from_line": 0, "to_line": 0,
         "quote": ""}], "moments": []})


def rd(p):
    return json.load(io.open(p, encoding="utf-8"))


def cov(d):
    return d.get("cov") or {}


def beats(L, vid, n):
    """n unforced beats exactly as the sweep takes them (the cached
    judge, then _insights_one(forced=False) only when it says owed);
    returns per beat (owed, ret, asks, ins mtime, tries, cov.owed)."""
    out = []
    for _ in range(n):
        owed = L._ins_owing(vid)
        ASKS[:] = []
        r = L._insights_one(vid, forced=False) if owed else None
        d = rd(L._ai_sidecar(vid, "ins"))
        out.append((owed, r, list(ASKS),
                    os.path.getmtime(L._ai_sidecar(vid, "ins")),
                    d.get("tries"), cov(d).get("owed")))
        time.sleep(0.03)
    return out


def scenario(L, tag, per_window, vdur, answers):
    root = tempfile.mkdtemp(prefix="loops336_%s_" % tag)
    mount(L, root)
    vid = build_night(L, root, per_window, vdur)
    describer(L, answers)
    ASKS[:] = []
    r1 = L._insights_one(vid, forced=True)
    return root, vid, r1, rd(L._ai_sidecar(vid, "ins")), list(ASKS)


# =======================================================================
print("--- R3-1a: a told window, a told-empty window and a [] window - "
      "the write extinguishes the owe ---")
root, vid, r1, d1, a1 = scenario(lore, "a", (12, 12, 2), 5400.0,
                                 {0: whole, 30: empty})
w = d1.get("windows") or {}
check("run 1 completes with chapters; w0 told whole, w30 told-empty "
      "(asks 2, left 0), w60 stored as []",
      r1 is True and d1.get("complete") and d1.get("chapters")
      and (w.get("0") or {}).get("asks") == 1
      and (w.get("1800") or {}).get("asks") == 2
      and (w.get("1800") or {}).get("left") == 0
      and w.get("3600") == [])
check("the count stamps cov.owed False (the [] marker is not a legacy "
      "window) and cov.short True: cov=%r"
      % ({k: v for k, v in cov(d1).items() if k != "gaps"},),
      cov(d1).get("owed") is False and cov(d1).get("short") is True)
check("_ins_owing says not owed with the clock the writer left",
      lore._ins_owing(vid) is False)
check("_ins_done_honest says finished", lore._ins_done_honest(vid) is True)
m1 = os.path.getmtime(lore._ai_sidecar(vid, "ins"))
b = beats(lore, vid, 2)
check("two more sweep beats are no-ops: not owed, nothing asked, the "
      "sidecar's clock unchanged",
      all(x[0] is False and x[1] is None and x[2] == [] for x in b)
      and all(x[3] == m1 for x in b))
check("the attic banked nothing after the first write",
      not [f for f in os.listdir(root) if ".ins.json.v" in f])

print("--- R3-1b: a window that SPENT its five asks beside a [] window ---")
root, vid, r1, d1, a1 = scenario(lore, "b", (12, 2), 3000.0, {0: one_row})
w = d1.get("windows") or {}
check("run 1 completes; w0 asks 5, w30 == []",
      r1 is True and d1.get("complete")
      and (w.get("0") or {}).get("asks") == 5 and w.get("1800") == [])
check("cov.owed False, not owed, two beats no-ops",
      cov(d1).get("owed") is False and lore._ins_owing(vid) is False
      and all(x[0] is False and x[2] == [] for x in beats(lore, vid, 2)))

print("--- R3-1 controls: the rule still holds where it should ---")
root, vid, r1, d1, a1 = scenario(lore, "c", (12, 12), 3600.0,
                                 {0: whole, 30: empty})
check("told / told-empty with NO [] window: cov.owed False, cov.short "
      "True, not owed (unchanged by the fix)",
      r1 is True and d1.get("complete")
      and cov(d1).get("owed") is False and cov(d1).get("short") is True
      and lore._ins_owing(vid) is False)
root, vid, r1, d1, a1 = scenario(lore, "d", (12, 2), 3000.0, {0: whole})
check("told whole / [] window: cov.owed False, not owed",
      cov(d1).get("owed") is False and lore._ins_owing(vid) is False)

# A GENUINE PRE-BUDGET REVIEW (dict windows without "asks", no cov) is
# what the legacy-gap rule exists for: it must still owe its count,
# stamp cov.owed on the free cov-only pass, be re-told once on the
# staged lane, land budgets, and settle.
root = tempfile.mkdtemp(prefix="loops336_legacy_")
mount(lore, root)
vid = build_night(lore, root, (12, 12), 3600.0)
legacy = {"v": 3, "engine": "local", "gen": 3, "tgen": lore._TITLE_GEN,
          "src_stt": {"mt": os.path.getmtime(lore._ai_sidecar(vid, "stt")),
                      "reader": 7},
          "title": "old", "summary": "old", "chapters": [{"x": 1}],
          "segments": [], "moments": [], "clips": [],
          "windows": {"0": {"segments": [
              {"name": "the lane push", "what": "w", "topics": [],
               "from": 30.0, "to": 40.0, "src": [0, 0]}],
              "moments": []},
              "1800": {"segments": [], "moments": []}},
          "win_len": 1800, "vdur": 3600.0, "complete": True, "tries": 0}
json.dump(legacy, io.open(lore._ai_sidecar(vid, "ins"), "w",
                          encoding="utf-8"))
check("a pre-budget legacy review (no cov) is owed its count",
      lore._ins_owing(vid) is True)
describer(lore, {0: whole, 30: whole})
ASKS[:] = []
lore._insights_one(vid, forced=False)
d = rd(lore._ai_sidecar(vid, "ins"))
check("the cov-only pass keeps the legacy-gap rule for real legacy "
      "windows: cov.owed True, no ask spent: asks=%r" % (ASKS,),
      cov(d).get("owed") is True and ASKS == [])
check("the next beat re-tells it once on the staged lane, lands budgets "
      "and converges",
      lore._insights_one(vid, forced=False) is True
      and cov(rd(lore._ai_sidecar(vid, "ins"))).get("owed") is False
      and lore._ins_owing(vid) is False)

# =======================================================================
print("--- R3-1 witness: the tree before the fix (%s) looped on the "
      "same fixture ---" % PARITY_BASE)
BASE_PY = os.path.join(tempfile.mkdtemp(prefix="loops336_base_"),
                       "lore_base.py")
io.open(BASE_PY, "wb").write(subprocess.run(
    ["git", "show", PARITY_BASE + ":lore.py"], cwd=ROOT,
    capture_output=True).stdout)
_spec = importlib.util.spec_from_file_location("lore_base", BASE_PY)
lore_base = importlib.util.module_from_spec(_spec)
sys.modules["lore_base"] = lore_base
lore_base.__dict__["log"] = lambda m: None
_spec.loader.exec_module(lore_base)
pen(lore_base)
root, vid, r1, d1, a1 = scenario(lore_base, "base", (12, 12, 2), 5400.0,
                                 {0: whole, 30: empty})
bb = beats(lore_base, vid, 2)
check("before: the same finished review was stamped cov.owed True and "
      "each unforced beat re-told every window and the title: %r"
      % ([x[2] for x in bb],),
      cov(d1).get("owed") is True
      and all(x[0] is True and x[1] is True and x[2] == a1 for x in bb))
del sys.modules["lore_base"]


# =======================================================================
# THE DESCRIBE AREA (R4-1, R4-2). The auditor's real functions are
# AST-lifted out of a lore.py SOURCE TEXT (the tree, then PARITY_BASE)
# into a stub namespace on a tempdir; only ffmpeg, the ASR server and
# urllib are stubbed, so the relisten's own write-gate runs. The words
# in the fixture are invented game words, never a person.
import ast
import shutil
import types
import unicodedata

R41_DEFS = {
    "_aud_sense", "_aud_revert_nonsense", "_aud_ear_extra", "_aud_parse",
    "_aud_apply_fixes", "_aud_garble", "_aud_carry", "_aud_ear_toks",
    "_aud_lat", "_aud_skel", "_aud_phon", "_aud_filler", "_aud_ear_agrees",
    "_aud_prompt_ear", "_aud_ear_veto", "_aud_clip", "_atomic_write_json",
    "_aud_relisten", "_aud_ear_gap", "_aud_ear_union", "_aud_overlap",
    "_aud_hints", "_aud_apply_strikes", "_aud_keep_split", "_aud_word_seen",
}
R41_NEW = {"_aud_ear_backs"}          # only the fixed tree has it
R41_ASSIGN = {"_AUD_AR", "_AUD_VOWEL", "_AUD_PAIRS", "_AUD_STOP",
              "_AUD_EAR_STOP", "_AUD_EAR_TOK", "_AUD_EAR_CAP",
              "_AUD_EAR_ASK", "_AUD_ASK_CHARS", "_AUD_VOCAB"}


def r41_lift(src, tag):
    """The auditor's road, lifted from one source text."""
    tree = ast.parse(src)
    chunks = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) \
                and node.name in (R41_DEFS | R41_NEW):
            chunks.append((node.lineno, ast.get_source_segment(src, node)))
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(n in R41_ASSIGN for n in names):
                chunks.append((node.lineno,
                               ast.get_source_segment(src, node)))
        elif isinstance(node, ast.For) and isinstance(node.target,
                                                       ast.Tuple):
            seg = ast.get_source_segment(src, node)
            if "_AUD_PAIRS.add" in seg:
                chunks.append((node.lineno, seg))
    chunks.sort()
    found = set()
    for _, seg in chunks:
        m = re.match(r"(?:def\s+)?(_\w+)", seg)
        if m:
            found.add(m.group(1))
    missing = (R41_DEFS | R41_ASSIGN) - found
    assert not missing, "%s: not lifted: %r" % (tag, missing)
    tmp = tempfile.mkdtemp(prefix="loops336_r41_%s_" % tag)
    vid = os.path.join(tmp, "night_20260912_010203.mkv")
    io.open(vid, "wb").write(b"\x00")
    logs = []

    class _Resp(object):
        def __init__(self, txt):
            self._b = json.dumps({"choices": [{"message": {
                "content": "language Arabic<asr_text>" + txt}}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._b

    class _Url(object):
        Request = staticmethod(lambda url, body, hdr: (url, body))

        def __init__(self):
            self.ear = ""

        def urlopen(self, req, timeout=0):
            return _Resp(self.ear)

    class _Srv(object):
        pr = None
        base = "http://127.0.0.1:0"

        def __init__(self, port=0):
            pass

        def start(self):
            return True

        def stop(self):
            pass

    def _run(cmd, timeout, flags, env=None):
        io.open(cmd[-1], "wb").write(b"RIFF")     # the wav ffmpeg would cut
        return 0, "", ""

    url = _Url()
    NS = {
        "re": re, "os": os, "json": json, "time": time,
        "unicodedata": unicodedata, "subprocess": subprocess,
        "_urlreq": url, "log": lambda s: logs.append(str(s)),
        "_AI": {"abort": False, "proc": None},
        "SETTINGS": {"ffmpeg_path": "ffmpeg", "output_dir": tmp},
        "_ai_sidecar": lambda vp, kind: os.path.join(
            tmp, os.path.splitext(os.path.basename(vp))[0]
            + "." + kind + ".json"),
        "_aud_bank_orig": lambda vp, kind: None,
        "_room_names": lambda: [],
        "_aud_gamewords": lambda vp: [],
        "_eye_stamp": lambda t: "%.1fs" % float(t or 0),
        "_asr_gguf_paths": lambda: ("a", "b"),
        "_desc_keep_drop": lambda: None,
        "_aud_keep_drop": lambda: None,
        "_audio_track_names": lambda p: [],
        "_mic_track": lambda p, names=None: None,
        "_mix_audio_args": lambda p, names=None: ["-map", "0:a:0"],
        "_AsrServer": _Srv, "_ai_run": _run, "_work_dir": lambda: tmp,
    }
    for _, seg in chunks:
        exec(compile(seg, "lore_" + tag, "exec"), NS)
    # THE LIBRARY: 6000 ordinary words (past _AUD_VOCAB_MIN and the
    # reverter's 1000 guard), the common filler with real counts, and
    # NOT the two invented words the fixture turns on.
    freq = {"w%04d" % i: 3 for i in range(6000)}
    for w in ("here", "yeah", "okay", "the", "you", "and", "this",
              "that", "guy", "over", "there", "look", "now", "come",
              "back", "man", "bro", "what", "was", "with", "hey"):
        freq[w] = 400
    NS["_AUD_VOCAB"]["freq"], NS["_AUD_VOCAB"]["low"] = freq, dict(freq)
    NS["_AUD_VOCAB"]["at"] = time.time()
    return types.SimpleNamespace(NS=NS, url=url, logs=logs, vid=vid,
                                 freq=freq, tag=tag)


def r41_stt(H, orig):
    segs = [{"a": 1000, "b": 4000, "t": "okay look over there guy"},
            {"a": 10000, "b": 14000, "t": orig},
            {"a": 20000, "b": 23000, "t": "come back here man"}]
    H.NS["_atomic_write_json"](H.NS["_ai_sidecar"](H.vid, "stt"),
                               {"segments": segs})


def r41_seg(H):
    return json.load(io.open(H.NS["_ai_sidecar"](H.vid, "stt"),
                             encoding="utf-8"))["segments"][1]


def r41_audit(H, ear, heard, prior):
    """_audit_one's road from 'checking old corrections' through the
    strike walk to the retell trigger, the thinker answering `heard`
    for every asked row and the relisten hearing `ear`."""
    NS = H.NS
    took = NS["_aud_revert_nonsense"](H.vid, H.freq)
    stt = [s for s in json.load(io.open(NS["_ai_sidecar"](H.vid, "stt"),
                                        encoding="utf-8"))["segments"]
           if isinstance(s, dict)]
    garble = NS["_aud_garble"](stt, H.freq)
    garble = NS["_aud_ear_union"](garble, NS["_aud_ear_gap"](stt))
    for g in garble:
        g["hints"] = []
    NS["_aud_carry"](garble, prior)
    ask = [g for g in garble if not g.get("carried")]
    H.url.ear = ear
    if ask:
        NS["_aud_relisten"](H.vid, ask)          # the REAL write-gate
    fixes = []
    if ask:
        got = {"checked": [],
               "fixes": [{"n": i, "heard": heard, "why": "the ear heard it"}
                         for i in range(len(ask))]}
        fixes = NS["_aud_parse"](got, ask, H.vid)[5]
    applied = NS["_aud_apply_fixes"](H.vid, fixes) if fixes else 0
    struck = NS["_aud_apply_strikes"](
        H.vid, garble, [float(f.get("t") or 0) for f in fixes
                        if f.get("applied")], H.freq) if garble else 0
    return {"took": took, "asked": len(ask), "applied": applied,
            "struck": struck, "retold": 1 if (applied or struck) else 0,
            "garble": garble, "t": r41_seg(H).get("t"),
            "verdicts": [g.get("verdict") for g in garble],
            "ear_junk": [bool(g.get("ear_junk")) for g in ask]}


def r41_run(H, orig, ear, heard):
    r41_stt(H, orig)
    del H.logs[:]
    prior, out = [], []
    for _ in range(3):
        r = r41_audit(H, ear, heard, prior)
        prior = r["garble"]
        out.append(r)
    return out


R41_ORIG = "varkoth zemmiel here yeah okay"     # 2 library-new of 5
R41_EAR = "Varkoth Zemmiel here yeah okay"      # passes the bare gate
R41_FIX = "Varkoth Zemmiel, here!"              # 2 of 3: fails it bare

print("--- R4-1: a fix the ear admitted, three audits ---")
H = r41_lift(io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8",
                     newline="").read(), "tree")
_okE, _ = H.NS["_aud_sense"](R41_EAR, H.freq)
_okF, _ = H.NS["_aud_sense"](R41_FIX, H.freq)
check("the premise: the ear passes the bare gate, the fix fails it, "
      "and the fix skeleton-agrees with the ear without being it",
      _okE and not _okF and H.NS["_aud_ear_agrees"](R41_EAR, R41_FIX)
      and re.findall(r"[a-z0-9]+", H.NS["_aud_lat"](R41_EAR))
      != re.findall(r"[a-z0-9]+", H.NS["_aud_lat"](R41_FIX)))
C = r41_run(H, R41_ORIG, R41_EAR, R41_FIX)
print("     audits: %s" % [(r["took"], r["asked"], r["applied"], r["struck"],
                            r["verdicts"]) for r in C])
check("audit 1 admits the fix through the ear and lands it",
      C[0]["applied"] == 1 and C[0]["t"] == R41_FIX)
check("the segment carries the ear that admitted it (fxe)",
      r41_seg(H).get("fxe") == R41_EAR and r41_seg(H).get("fx") == 1)
check("no audit takes it back: 'took back' lines == 0, took == [0,0,0]",
      [r["took"] for r in C] == [0, 0, 0]
      and not [l for l in H.logs if "took back" in l])
check("applied == [1,0,0] and retold == [1,0,0] - told once, not "
      "every audit", [r["applied"] for r in C] == [1, 0, 0]
      and [r["retold"] for r in C] == [1, 0, 0])
check("the fix stands after every audit", all(r["t"] == R41_FIX for r in C))
check("audits 2-3 never call the standing line noise (the confirmation "
      "door reads the same evidence) and the strike walk strikes nothing: "
      "verdicts=%r" % ([r["verdicts"] for r in C[1:]],),
      all(v in ("right", "unclear") for r in C[1:] for v in r["verdicts"])
      and all(r["struck"] == 0 for r in C))
check("audit 3 carries audit 2's verdict - asked == [1,1,0], it settles",
      [r["asked"] for r in C] == [1, 1, 0])
check("_aud_ear_extra on the landed segment folds the ear in",
      set(H.NS["_aud_ear_toks"](R41_EAR, stop=False))
      <= (H.NS["_aud_ear_extra"](r41_seg(H), H.vid) or set()))
# the negative control: an ear the relisten's own gate refuses (2 of 3
# library-new) is junk, backs nothing, and the fix is refused ONCE
A = r41_run(H, "varkoth zemmiel here", "Varkoth Zemmiel here",
            "Varkoth Zemmiel here")
check("control: a junk ear admits nothing - refused once, the refusal "
      "carries (asked [1,0,0]), nothing landed, nothing taken back",
      A[0]["ear_junk"] == [True] and [r["asked"] for r in A] == [1, 0, 0]
      and all(r["applied"] == 0 and r["took"] == 0 for r in A)
      and all(r["t"] == "varkoth zemmiel here" for r in A)
      and bool([l for l in H.logs if "refused its own correction" in l]))
# a taken-back fix loses its ear: the reverter's pop list
_sg = {"a": 10000, "t": "qorvex blyntar", "was": "okay look", "fx": 1,
       "fxe": "Varkoth Zemmiel here yeah okay"}
H.NS["_atomic_write_json"](H.NS["_ai_sidecar"](H.vid, "stt"),
                           {"segments": [_sg]})
_tb = H.NS["_aud_revert_nonsense"](H.vid, H.freq)
_s0 = json.load(io.open(H.NS["_ai_sidecar"](H.vid, "stt"),
                        encoding="utf-8"))["segments"][0]
check("a standing fix its banked ear does NOT back is still taken back, "
      "and loses its ear with the rest of the markers",
      _tb == 1 and _s0.get("t") == "okay look" and "fxe" not in _s0
      and "fx" not in _s0 and "was" not in _s0)

print("--- R4-1 witness: the tree before the fix (%s) ping-ponged the "
      "same fixture ---" % PARITY_BASE)
HB = r41_lift(subprocess.run(["git", "show", PARITY_BASE + ":lore.py"],
                             cwd=ROOT, capture_output=True).stdout
              .decode("utf-8"), "base")
CB = r41_run(HB, R41_ORIG, R41_EAR, R41_FIX)
print("     audits: %s" % [(r["took"], r["asked"], r["applied"])
                           for r in CB])
check("before: took == [0,1,1], applied == [1,1,1], retold every audit, "
      "'took back' logged twice",
      [r["took"] for r in CB] == [0, 1, 1]
      and [r["applied"] for r in CB] == [1, 1, 1]
      and [r["retold"] for r in CB] == [1, 1, 1]
      and len([l for l in HB.logs if "took back" in l]) == 2)

# =======================================================================
print("--- R4-2: the tries-2 .new left by two empty retells ---")
R42_FREQ = {"word%d" % i: 5 for i in range(6000)}
for w in ("the ball rolls across the arena and the match runs long "
          "again tonight goal boost save shot car field play").split():
    R42_FREQ[w] = 50
R42_WORDS = ("the ball rolls across the arena and the match runs long "
             "again tonight").split()
R42_ASKS = []


class _R42Pr(object):
    def poll(self):
        return None

    def terminate(self):
        pass


def r42_describer(per_window):
    class D(object):
        def __init__(self, port=None):
            self.pr = None
            self.base = "http://127.0.0.1:0"

        def start(self, budget=900):
            self.pr = _R42Pr()
            return True

        def ask(self, system, user, max_tokens=900, schema=None,
                images=None, **kw):
            m = re.search(r"runs from minute (\d+) to minute", user)
            if m:
                R42_ASKS.append(int(m.group(1)))
                return per_window.get(int(m.group(1)), "")
            return json.dumps({"title": "the long arena night",
                               "summary": "a long night of matches"})

        def stop(self):
            self.pr = None
    return D


class _R42Thinker(object):
    def __init__(self):
        self.pr = None
        self.base = "http://127.0.0.1:0"

    def start(self, budget=600):
        self.pr = _R42Pr()
        return True

    def ask(self, system, user, max_tokens=2500):
        return json.dumps({"checked": [], "fixes": []})

    def stop(self):
        self.pr = None


def r42_mount(L, root, vdur, per_window):
    mount(L, root)
    L.SETTINGS["room_names"] = ""
    L._my_name = lambda: ""
    L._room_names = lambda: []
    L._picture_seconds = lambda p: None
    L._stt_reader_of = lambda p: 7
    L._DescServer = r42_describer(per_window)
    L._AUD_KEEP["srv"] = None
    L._AI["busy"] = None
    L._AI["_tally"] = None
    L._AI.pop("_mig_quiet", None)
    L._aud_playing = lambda: False
    L._game_has_focus = lambda: False
    L._aud_llm_paths = lambda: ("exe", "mdl")
    L._AudServer = _R42Thinker
    L._aud_relisten = lambda p, g: 0
    L._asr_gguf_paths = lambda: None
    L._persist_setting = lambda k, v: None
    L._ai_note_rate = lambda *a, **k: None
    L._AUD_SETTLED.clear()
    L._AUD_LAST.clear()
    L._AUD_VCACHE.clear()
    L._RETELL_QUIT.clear()
    L._AUD_VOCAB["freq"] = R42_FREQ
    L._AUD_VOCAB["low"] = {}
    L._AUD_VOCAB["at"] = time.time() + 86400
    L._video_duration = lambda p: vdur
    L._story_seconds = lambda p, d: (vdur, "")
    R42_ASKS[:] = []


def r42_night(L, root, name, windows, per_win=12):
    vid = os.path.join(root, name + ".mp4")
    io.open(vid, "w").write("x")
    segs = []
    for w in range(windows):
        for i in range(per_win):
            t = int((w * 1800 + 60 + i * (1740 // per_win)) * 1000)
            segs.append({"a": t, "b": t + 3000,
                         "t": " ".join(R42_WORDS[i % len(R42_WORDS):]
                                       + R42_WORDS[:i % len(R42_WORDS)])})
    time.sleep(0.02)
    json.dump({"segments": segs, "sources": {}},
              io.open(L._ai_sidecar(vid, "stt"), "w", encoding="utf-8"))
    json.dump({"events": [{"t": 70.0, "kind": "loud", "z": 1.0},
                          {"t": 2000.0, "kind": "laugh", "z": 0.8}]},
              io.open(L._ai_sidecar(vid, "hl"), "w", encoding="utf-8"))
    L._library_dirs = lambda out: [(root, "game")]
    L._scan_dir_mp4s = lambda d, k: [{"path": vid, "dur": 3000.0,
                                      "mtime": os.path.getmtime(vid)}]
    return vid


def r42_told(label, n=12):
    return json.dumps({"segments": [
        {"name": label, "what": "they play a long match",
         "topics": ["arena"], "from_line": 0, "to_line": n - 1,
         "quote": ""}], "moments": []})


def r42_judges(L, v):
    L._AI["_tally"] = None
    L._INS_OWE_CACHE.clear()
    L._AUD_OWE_CACHE.clear()
    api = L._JsApi.__new__(L._JsApi)
    api._ctl = types.SimpleNamespace(session=None, saving=0)
    tal = L._ai_tally()
    why = api.ai_whynot(v)
    flags = api.have_flags([v]).get(v) or {}
    return {"covers": L._aud_covers_now(v),
            "done_current": L._aud_done_current(v),
            "aud_owing": L._aud_owing(v),
            "aud_owing_swept": L._aud_owing_swept(v),
            "ins_owing_raw": L._ins_owing_raw(v),
            "left": tal["auditing"]["left"], "done": tal["auditing"]["done"],
            "ins_why": [k for k in why["kinds"] if k["kind"] == "ins"][0],
            "aud_lvl": flags.get("aud_lvl"), "aud_why": flags.get("aud_why")}


R42_ROOT = tempfile.mkdtemp(prefix="loops336_r42_")
R42_TOLD = {0: r42_told("the opening"), 30: r42_told("the closing")}
r42_mount(lore, R42_ROOT, 3000.0, R42_TOLD)
v = r42_night(lore, R42_ROOT, "arena", 2)
sp = lore._ai_sidecar(v, "ins")
check("the describe lands complete (2 windows)",
      lore._insights_one(v, forced=True) is True
      and set((rd(sp)).get("windows") or {}) == {"0", "1800"})
lore._audit_one(v)
_aud0 = rd(lore._ai_sidecar(v, "aud"))
j0 = r42_judges(lore, v)
check("the audit is gold over it: tally done 1 left 0, nothing owed",
      bool(_aud0.get("complete")) and j0["covers"] is True
      and j0["done"] == 1 and j0["left"] == 0 and not j0["aud_owing"])
_served = io.open(sp, "rb").read()
_mt = os.path.getmtime(sp)
lore._DescServer = r42_describer({0: "I cannot help with that.",
                                  30: R42_TOLD[30]})
lore._DESC_KEEP["srv"] = None
n_dirty = lore._aud_retell(v, [70.0])            # retell 1, inside the audit
_beats = 0
for _ in range(3):                                # the sweep's beats
    if lore._ins_owing(v):
        lore._insights_one(v)
        _beats += 1
_nw = rd(sp + ".new")
check("two empty retells: the .new stays at tries 2 with retold ['0'], "
      "N3 said once, the focus let go, the served review byte-identical "
      "with its clock unmoved (unchanged by the fix)",
      n_dirty == 1 and _beats == 1 and _nw.get("tries") == 2
      and _nw.get("retold") == ["0"] and _nw.get("complete") is False
      and len([l for l in lore.LOG if "came back empty twice" in l]) == 1
      and lore._AI.get("focus") is None
      and io.open(sp, "rb").read() == _served
      and os.path.getmtime(sp) == _mt)
jA = r42_judges(lore, v)
lore._AUD_VCACHE.clear()                          # = a restart
jB = r42_judges(lore, v)
print("     in-session: %s" % {k: jA[k] for k in ("covers", "done_current",
                                                   "left", "done", "aud_lvl")})
print("     restarted:  %s" % {k: jB[k] for k in ("covers", "done_current",
                                                   "left", "done", "aud_lvl")})
check("the audit still covers the served review (a tries-2 retold .new "
      "is a refused retell, not a live staging): covers True, "
      "done_current True", jB["covers"] is True and jB["done_current"] is True)
check("the tally says done 1 left 0 - and in-session and post-restart "
      "agree", jA["left"] == 0 and jA["done"] == 1
      and jB["left"] == 0 and jB["done"] == 1)
check("nothing owes it: _aud_owing, _aud_owing_swept, _ins_owing_raw all "
      "False", not jB["aud_owing"] and not jB["aud_owing_swept"]
      and not jB["ins_owing_raw"])
check("the shelf: gold (aud_lvl 2), no 'older description' sentence",
      jB["aud_lvl"] == 2 and not jB["aud_why"])
check("ai_whynot's ins kind is done, not owed, and carries N3's sentence: "
      "%r" % (jB["ins_why"].get("why"),),
      jB["ins_why"].get("done") is True and jB["ins_why"].get("owed") is False
      and "came back empty twice" in str(jB["ins_why"].get("why")))
R42_ASKS[:] = []
for _ in range(3):
    if lore._ins_owing(v):
        lore._insights_one(v)
    if lore._aud_owing_swept(v):
        lore._audit_one(v)
check("three more beats are a no-op: nothing asked, the .new at tries 2, "
      "the served clock unmoved",
      R42_ASKS == [] and rd(sp + ".new").get("tries") == 2
      and os.path.getmtime(sp) == _mt)
# the bound is the owing judge's own: a LIVE staging still condemns
_live = dict(_nw)
_live["tries"] = 1
lore._atomic_write_json(sp + ".new", _live)
lore._INS_OWE_CACHE.clear()
lore._AUD_VCACHE.clear()
check("a tries-1 retold .new is still live: owed, covers False, "
      "done_current False (the old answer where it was right)",
      lore._ins_owing_raw(v) is True and lore._aud_covers_now(v) is False
      and lore._aud_done_current(v) is False)
_up = dict(_nw)
_up.pop("retold", None)
_up["tries"] = 2
lore._atomic_write_json(sp + ".new", _up)
lore._INS_OWE_CACHE.clear()
lore._AUD_VCACHE.clear()
check("an upgrade's .new keeps its three: tries 2 without a retold "
      "ledger is live (covers False), tries 3 is not",
      lore._aud_covers_now(v) is False
      and (lambda: (_up.__setitem__("tries", 3),
                    lore._atomic_write_json(sp + ".new", _up),
                    lore._AUD_VCACHE.clear(),
                    lore._aud_covers_now(v) is True)[-1])())
lore._atomic_write_json(sp + ".new", _nw)         # the quit's state again
lore._AUD_VCACHE.clear()
lore._library_dirs = lambda out: []
lore._scan_dir_mp4s = lambda d, k: []

print("--- R4-2 witness: the tree before the fix (%s) on the same files ---"
      % PARITY_BASE)
BASE_PY_R4 = os.path.join(tempfile.mkdtemp(prefix="loops336_base_r4_"),
                          "lore_base_r4.py")
io.open(BASE_PY_R4, "wb").write(subprocess.run(
    ["git", "show", PARITY_BASE + ":lore.py"], cwd=ROOT,
    capture_output=True).stdout)
_spec2 = importlib.util.spec_from_file_location("lore_base_r4", BASE_PY_R4)
lore_base_r4 = importlib.util.module_from_spec(_spec2)
sys.modules["lore_base_r4"] = lore_base_r4
lore_base_r4.__dict__["log"] = lambda m: None
_spec2.loader.exec_module(lore_base_r4)
pen(lore_base_r4)
r42_mount(lore_base_r4, R42_ROOT, 3000.0, R42_TOLD)
lore_base_r4._library_dirs = lambda out: [(R42_ROOT, "game")]
lore_base_r4._scan_dir_mp4s = lambda d, k: [
    {"path": v, "dur": 3000.0, "mtime": os.path.getmtime(v)}]
jX = r42_judges(lore_base_r4, v)
check("before: covers False, tally auditing left 1 while no judge owes "
      "it, silver 'it read an older description', whynot 'finished'",
      jX["covers"] is False and jX["left"] == 1 and not jX["aud_owing"]
      and not jX["aud_owing_swept"] and not jX["ins_owing_raw"]
      and jX["aud_lvl"] == 1 and jX["ins_why"].get("why") == "finished")
lore_base_r4._library_dirs = lambda out: []
lore_base_r4._scan_dir_mp4s = lambda d, k: []
del sys.modules["lore_base_r4"]

# =========================================================================
#  THE QUEUE (3.36 F1, F5, F6, F2). Four findings on the beat itself,
#  each proved on a lifted twin: the REAL _ai_tick, _force_owes, the
#  lane/hold/state helpers, _ai_attic, the owing tests and (for F5) the
#  real _insights_one as far as its refusal, out of the tree's lore.py by
#  AST into a stub namespace on a tempdir shelf, with a synchronous
#  Thread (one beat = one job) and a hand clock. The witness at the foot
#  of each lifts the SAME functions out of PARITY_BASE and shows the
#  fault there. Writers are stubs whose honesty is a knob.
#
#  F5  A HELD WORDS LANE MADE AN 'ALL' ASK DESCRIBE WITHOUT WORDS. The
#      forced road zeroed owed_stt for the hold and left owed_ins
#      standing, so the describer was spawned on a night with no
#      transcript, refused, and was stamped ran anyway; on Resume the
#      words ran and the ask cleared satisfied with no review. Fix:
#      under 'all' the review waits for the words, held or not.
#  F1  THE SWEEP TRUSTED THE WRITER'S OK. A writer that returned True
#      and wrote nothing was spawned every beat for ever - no memo, no
#      log. Fix: a session memo of the writer's own output (the mp4's
#      clock + the lane's attic sidecars' clocks); a second ok run that
#      left them all unchanged is logged once and memoed refused.
#  F6  A RESUMED REDO-ALL HEARD AND LOOKED AGAIN FROM SCRATCH. Only the
#      whole kind was memoed as ran, and 'thinking' lands when the
#      describer finishes - so every interruption cost the senses and
#      the eye again. Fix: they stamp 'sns' / 'vis' into force_ran.
#  F2  THE WORKING PAGE'S HELD-BACK NUMBER WAS NOT 'OF THE LEFT'. One
#      shelf-wide count of a never game's nights, done or owed, printed
#      on every lane row. Fix: per lane, counted inside the left branch.
# =========================================================================
import ast as _q_ast
import datetime as _q_dt
import shutil as _q_shutil
import textwrap as _q_textwrap
import threading as _q_threading
import time as _q_real_time

print("\n=== THE QUEUE: F5 / F1 / F6 / F2 ===")
Q_SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
Q_BASE = subprocess.run(["git", "show", PARITY_BASE + ":lore.py"],
                        cwd=ROOT, capture_output=True).stdout.decode(
                            "utf-8")
assert "def _ai_tick" in Q_BASE, "git show of the parity base failed"
_Q_TREES = {}


def q_lift(src, name, ns):
    tree = _Q_TREES.get(id(src))
    if tree is None:
        tree = _Q_TREES[id(src)] = _q_ast.parse(src)
    lines = src.splitlines()
    for node in tree.body:
        if isinstance(node, _q_ast.FunctionDef) and node.name == name:
            code = _q_textwrap.dedent("\n".join(
                lines[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
        if isinstance(node, _q_ast.Assign) and any(
                isinstance(t, _q_ast.Name) and t.id == name
                for t in node.targets):
            code = "\n".join(lines[node.lineno - 1:node.end_lineno])
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found at top level")


Q_CLOCK = [_q_real_time.time()]


class QTime(object):
    @staticmethod
    def time():
        return Q_CLOCK[0]

    @staticmethod
    def sleep(s):
        Q_CLOCK[0] += float(s)


class QThread(object):
    """the worker runs INSIDE start(): a beat and its job are one call"""
    def __init__(self, target=None, daemon=None, name=None, args=()):
        self._t, self._a = target, args

    def start(self):
        if self._t:
            self._t(*self._a)

    def join(self, *a):
        pass


class QThreading(object):
    RLock = staticmethod(_q_threading.RLock)
    Lock = staticmethod(_q_threading.Lock)
    Thread = QThread
    local = staticmethod(_q_threading.local)
    get_ident = staticmethod(_q_threading.get_ident)


class QCtl(object):
    session = None
    saving = 0


Q_CTL = QCtl()


def q_ns(src, out, data, logs):
    """The shared namespace: the real beat and every helper it walks
    with, over a scratch shelf; the writers are wired per section."""
    ns = {"os": os, "json": json, "re": re, "io": io, "time": QTime,
          "threading": QThreading, "_dt": _q_dt,
          "log": lambda m: logs.append(str(m)),
          "SETTINGS": {"output_dir": out, "ai_transcribe": True,
                       "ai_highlights": True, "insights_auto": True,
                       "always_read": False, "reread_old": False,
                       "game_rank": {}, "sdr_finish": True,
                       "bg_shutdown": False, "afk_ai": False},
          "_data_dir": lambda: data,
          "_SLATE_BUSY": [0], "_MIG_BUSY": [False],
          "_FINISHING": {"busy": False}, "_TRIM_BUSY": [0],
          "_EMB": {"down_t": 0.0}, "_EMB_STANDDOWN": 600.0,
          "_GAME_RANK_KEY": {},
          "_queued_finish_paths": lambda: []}
    for nm in ("_AI", "AI_KINDS", "AI_LABEL", "_AFKAI", "_AUD_ASK",
               "_GAME_RANKS", "_RANK_ORDER", "_ATTIC_OF"):
        q_lift(src, nm, ns)
    ns["_AI_FORCE_LOCK"] = _q_threading.RLock()
    ns["_AFKAI_LOCK"] = _q_threading.Lock()
    ns["_AI"].setdefault("failed", {})
    for fn in ("_bg_work_allowed", "_ai_want_lanes", "_ai_lanes_free",
               "_ai_effective_lane", "_ai_skipped_recently", "_ai_sidecar",
               "_ai_sidecar_fresh", "_queued_finish_badge",
               "_ins_done_honest", "_library_dirs", "_scan_dir_mp4s",
               "_thumb_dir", "_game_rank", "_force_owes", "_ai_state_path",
               "_afk_ai_true_held", "_ai_state_save", "_attic_dir",
               "_ai_attic", "_sns_owing", "_vis_owing",
               "_atomic_write_json", "_ai_tick"):
        q_lift(src, fn, ns)
    for fn in ("_ask_idle_tick", "_emb_idle_tick", "_desc_keep_tick",
               "_aud_keep_tick", "_self_check_daily", "_game_sources_daily",
               "_shelf_migrations", "_ask_srv_drop", "_desc_keep_drop",
               "_aud_keep_drop", "_ai_note_rate", "_ai_note_speech",
               "_audit_one"):
        ns[fn] = lambda *a, **k: None
    ns["_afk_ai_tick"] = lambda *a: False   # takes the ctl since 3.36 AFK-2
    ns["_reader_paths"] = lambda: "reader"
    ns["_describer_paths"] = lambda: "describer"
    ns["_senses_paths"] = lambda: ("py", "work")
    ns["_desc_mmproj"] = lambda: "mmproj"
    ns["_emb_paths"] = lambda: None
    ns["_game_has_focus"] = lambda: False
    ns["_stt_stale_reader"] = lambda p: False
    ns["_lvl_coarse_cached"] = lambda p: False
    ns["_video_duration"] = lambda p: 60.0
    ns["_secs_no_probe"] = lambda item: 1.0
    ns["_hud_owing"] = lambda p: False
    ns["_outcome_owing"] = lambda p: False
    ns["_emb_owing"] = lambda p: False
    ns["_aud_owing"] = lambda p: False
    ns["_aud_owing_swept"] = lambda p: False
    ns["_audit_ask"] = lambda p, **k: False
    ns["_audit_why"] = lambda p, **k: ""
    ns["_ins_owing"] = lambda p: not ns["_ai_sidecar_fresh"](p, "ins")
    ns["_highlights_one"] = lambda p: True
    ns["_transcribe_one"] = lambda p: True
    ns["_senses_one"] = lambda p: True
    ns["_eyes_one"] = lambda p: True
    ns["_insights_one"] = lambda p, forced=False, fresh=False: True
    ns["_hud_topup_one"] = lambda p: True
    ns["_outcome_topup_one"] = lambda p: True
    ns["_emb_one"] = lambda p: True

    def _ai_abort(force_too=True):
        ns["_AI"]["abort"] = True
        ns["_AI"]["wind"] = False
        ns["_AI"]["wind_src"] = None
    ns["_ai_abort"] = _ai_abort
    return ns


def q_shelf(tag):
    tmp = tempfile.mkdtemp(prefix="loops336_q_" + tag + "_")
    out = os.path.join(tmp, "out")
    data = os.path.join(tmp, "data")
    os.makedirs(os.path.join(out, ".lore_thumbs"))
    os.makedirs(data)
    return tmp, out, data


def q_night(out, game, stamp, age_s):
    d = os.path.join(out, game, "Videos")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, game + "_" + stamp + ".mp4")
    with io.open(p, "wb") as fh:
        fh.truncate(120000)
    t = Q_CLOCK[0] - age_s
    os.utime(p, (t, t))
    return p


def q_side(ns, p, kind, doc=None):
    sp = ns["_ai_sidecar"](p, kind)
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    with io.open(sp, "w", encoding="utf-8") as fh:
        json.dump(doc if doc is not None else {"v": 2, "ok": 1}, fh)
    return sp


def q_reset(ns):
    AI = ns["_AI"]
    for k in ("force", "force_want", "busy", "busy_path", "focus"):
        AI[k] = None
    AI["force_redo"] = False
    AI["force_ran"] = set()
    AI["force_queue"] = []
    AI["abort"] = False
    AI["wind"] = False
    AI["t_last"] = 0
    AI["failed"] = {}
    AI["soft_n"] = {}
    AI["ran_sig"] = {}
    AI["held"] = {"listening": False, "hearing": False,
                  "thinking": False, "auditing": False}
    AI["_sg2"] = True
    AI["rate"] = {"listening": [], "hearing": [], "thinking": []}
    AI.pop("next_pick", None)
    ns["_AUD_ASK"].update({"path": None, "named": False, "claim": None})
    ns["_GAME_RANK_KEY"].clear()


def q_beat(ns, n=1, gap=6.0):
    for _ in range(n):
        Q_CLOCK[0] += gap
        ns["_AI"]["t_last"] = 0
        ns["_AI"].pop("next_pick", None)
        ns["_ai_tick"](Q_CTL)


# ------------------------------------------------------------- F5
print("--- F5: an 'all' ask whose words lane is held waits for the "
      "words ---")


def q_f5_ns(src):
    """verify_F5's fixture: sidecar freshness is a dict the writers
    mark, and the REAL _insights_one is lifted as far as its 'has no
    transcript yet' refusal (a night WITH words is described by the
    stub, so the road can finish)."""
    tmp, out, data = q_shelf("f5")
    logs, calls, fresh = [], [], {}
    ns = q_ns(src, out, data, logs)
    A = q_night(out, "somegame", "20260910_210000", 3600)
    ns["_library_dirs"] = lambda o: [(os.path.dirname(A), "videos")]
    ns["_scan_dir_mp4s"] = lambda d, k: [
        {"path": A, "mtime": os.path.getmtime(A)}]
    ns["_ai_sidecar_fresh"] = lambda p, k: fresh.get((p, k), False)
    ns["_ai_sidecar"] = lambda p, k: p + "." + k + ".json"   # never exists
    ns["_ai_attic"] = lambda *a, **k: []
    ns["_ins_done_honest"] = lambda p: fresh.get((p, "ins"), False)
    ns["_ins_owing"] = lambda p: not fresh.get((p, "ins"), False)
    ns["_sns_owing"] = lambda p: False
    ns["_vis_owing"] = lambda p: False
    ns["_video_duration"] = lambda p: 3600.0
    ns["_night_era"] = lambda p: "split"
    ns["_night_mine"] = lambda segs: 0
    ns["_seg_layer"] = lambda sg: "room"
    ns["_room_words"] = lambda segs: 0
    ns["_INS_SAID"] = _q_threading.local()
    ns["_DRESS_SRC"] = {}
    ns["_insights_wanted"] = lambda: True
    ns["traceback"] = __import__("traceback")

    def _hl(p):
        calls.append("listening")
        fresh[(p, "hl")] = fresh[(p, "lvl")] = True
        return True

    def _stt(p):
        calls.append("hearing")
        fresh[(p, "stt")] = True
        return True
    ns["_highlights_one"] = _hl
    ns["_transcribe_one"] = _stt
    real_ins = q_lift(src, "_insights_one", ns)
    FR = fresh

    def _ins(p, forced=False, fresh=False):
        calls.append("thinking")
        if FR.get((p, "stt")):
            FR[(p, "ins")] = True             # a night WITH words: told
            return True
        r = real_ins(p, forced=forced, fresh=fresh)    # the real refusal
        if r:
            FR[(p, "ins")] = True
        return r
    ns["_insights_one"] = _ins
    q_reset(ns)
    return ns, A, calls, logs, fresh, tmp


def q_f5_drive(src):
    ns, A, calls, logs, fresh, tmp = q_f5_ns(src)
    AI = ns["_AI"]
    AI["force_queue"] = [(A, "all", False, [])]
    r = {}
    q_beat(ns)                                       # 1: the sound
    r["b1"] = list(calls)
    AI["held"]["hearing"] = True                     # Transcripts paused
    q_beat(ns)                                       # 2
    r["b2_calls"] = list(calls)
    r["b2_ran"] = set(AI.get("force_ran") or ())
    r["b2_soft"] = dict(AI.get("soft_n") or {})
    r["b2_refused"] = [l for l in logs if "has no transcript yet" in l]
    q_beat(ns)                                       # 3: parks
    r["b3_force"] = AI.get("force")
    r["b3_queue"] = list(AI.get("force_queue") or [])
    AI["held"]["hearing"] = False                    # Resume
    q_beat(ns, 3)                                    # 4-6
    r["b6_calls"] = list(calls)
    r["b6_force"] = AI.get("force")
    r["b6_queue"] = list(AI.get("force_queue") or [])
    r["b6_ins"] = fresh.get((A, "ins"), False)
    r["b6_failed"] = dict(AI["failed"])
    q_beat(ns, 2)                                    # 7-8: no-ops
    r["b8_calls"] = list(calls)
    r["b8_force"] = AI.get("force")
    _q_shutil.rmtree(tmp, ignore_errors=True)
    return r, A


r5, A5 = q_f5_drive(Q_SRC)
check("F5 (1) beat 1 spawns the sound only", r5["b1"] == ["listening"])
check("F5 (2) the words held: the beat spawns NOTHING - no describe "
      "without a transcript, no refusal logged, no soft strike, "
      "force_ran == {listening}",
      r5["b2_calls"] == ["listening"] and r5["b2_refused"] == []
      and r5["b2_soft"] == {} and r5["b2_ran"] == {"listening"})
check("F5 (3) the ask parks at the FRONT with its memory of the sound",
      r5["b3_force"] is None and len(r5["b3_queue"]) == 1
      and r5["b3_queue"][0][0] == A5 and r5["b3_queue"][0][1] == "all"
      and list(r5["b3_queue"][0][3]) == ["listening"])
check("F5 (4) Resume: words then review, the review lands, the ask "
      "clears satisfied, nothing memoed failed",
      r5["b6_calls"] == ["listening", "hearing", "thinking"]
      and r5["b6_ins"] is True and r5["b6_force"] is None
      and r5["b6_queue"] == [] and r5["b6_failed"] == {})
check("F5 (5) two more beats are no-ops",
      r5["b8_calls"] == r5["b6_calls"] and r5["b8_force"] is None)

# the controls that must hold before AND after
ns, A, calls, logs, fresh, tmp = q_f5_ns(Q_SRC)
ns["_AI"]["force_queue"] = [(A, "all", False, [])]
q_beat(ns, 4)
check("F5 control: nothing held -> sound, words, review, once each",
      calls == ["listening", "hearing", "thinking"]
      and fresh.get((A, "ins")) is True and ns["_AI"]["force"] is None)
_q_shutil.rmtree(tmp, ignore_errors=True)
ns, A, calls, logs, fresh, tmp = q_f5_ns(Q_SRC)
fresh[(A, "hl")] = fresh[(A, "lvl")] = fresh[(A, "stt")] = True
ns["_AI"]["force_queue"] = [(A, "think", False, [])]
ns["_AI"]["held"]["hearing"] = True
q_beat(ns, 2)
check("F5 control: a 'think' ask on a night WITH words is untouched by "
      "a held words lane", calls == ["thinking"]
      and fresh.get((A, "ins")) is True)
_q_shutil.rmtree(tmp, ignore_errors=True)
ns, A, calls, logs, fresh, tmp = q_f5_ns(Q_SRC)
fresh[(A, "hl")] = fresh[(A, "lvl")] = fresh[(A, "stt")] = True
ns["_AI"]["force_queue"] = [(A, "all", False, [])]
ns["_AI"]["held"]["hearing"] = True
q_beat(ns, 2)
check("F5 control: an 'all' ask on a night whose words are fresh "
      "describes at once under a held words lane",
      calls == ["thinking"] and fresh.get((A, "ins")) is True)
_q_shutil.rmtree(tmp, ignore_errors=True)
ns, A, calls, logs, fresh, tmp = q_f5_ns(Q_SRC)
ns["_AI"]["force_queue"] = [(A, "words", False, [])]
ns["_AI"]["held"]["hearing"] = True
q_beat(ns, 3)
check("F5 control: a 'words' ask under a held words lane never spawns "
      "the words and keeps its row",
      "hearing" not in calls and len(ns["_AI"]["force_queue"]) == 1
      and ns["_AI"]["force"] is None)
_q_shutil.rmtree(tmp, ignore_errors=True)

print("--- F5 witness: the tree before the fix (%s) on the same fixture "
      "---" % PARITY_BASE)
r5b, A5b = q_f5_drive(Q_BASE)
check("before: the held beat spawned the describer, the real "
      "_insights_one refused it ('has no transcript yet'), a soft "
      "strike burned, 'thinking' stamped ran",
      r5b["b2_calls"] == ["listening", "thinking"]
      and len(r5b["b2_refused"]) == 1 and r5b["b2_soft"].get(A5b) == 1
      and r5b["b2_ran"] == {"listening", "thinking"})
check("before: on Resume the words ran and the ask cleared SATISFIED "
      "with the review never written",
      r5b["b6_calls"][:3] == ["listening", "thinking", "hearing"]
      and r5b["b6_force"] is None and r5b["b6_queue"] == [])

# ------------------------------------------------------------- F1
print("--- F1: a writer that says ok and writes nothing is bounded ---")


def q_f1_ns(src):
    tmp, out, data = q_shelf("f1")
    logs, calls, tails = [], [], []
    knobs = {"write": {"hl": True, "stt": True, "ins": True},
             "owe_ins": {}, "owe_hud": {}}
    ns = q_ns(src, out, data, logs)
    ns["_ins_owing"] = lambda p: bool(knobs["owe_ins"].get(p, False))
    ns["_ins_done_honest"] = lambda p: os.path.isfile(
        ns["_ai_sidecar"](p, "ins"))
    ns["_sns_owing"] = lambda p: False
    ns["_vis_owing"] = lambda p: False
    ns["_hud_owing"] = lambda p: bool(knobs["owe_hud"].get(p, False))

    def _hl(p):
        calls.append(("listening", p))
        if knobs["write"]["hl"]:
            q_side(ns, p, "hl")
            q_side(ns, p, "lvl")
        return True

    def _stt(p):
        calls.append(("hearing", p))
        if knobs["write"]["stt"]:
            q_side(ns, p, "stt")
        return True

    def _ins(p, forced=False, fresh=False):
        calls.append(("thinking", p))
        if knobs["write"]["ins"]:
            q_side(ns, p, "ins", {"complete": True, "tries": 0,
                                  "chapters": [{"t": 0, "title": "x"}]})
            knobs["owe_ins"].pop(p, None)
        return True

    def _hud(p):
        tails.append(("screen", p))
        knobs["owe_hud"].pop(p, None)
        return True
    ns["_highlights_one"] = _hl
    ns["_transcribe_one"] = _stt
    ns["_insights_one"] = _ins
    ns["_hud_topup_one"] = _hud
    A = q_night(out, "somegame", "20260910_210000", 3600)
    q_reset(ns)
    return ns, A, calls, tails, logs, knobs, tmp


def q_f1_lie(src, lane):
    """one night owing only `lane`, whose writer returns True and writes
    nothing; 10 beats 6 s apart"""
    ns, A, calls, tails, logs, knobs, tmp = q_f1_ns(src)
    side = {"listening": "hl", "hearing": "stt", "thinking": "ins"}[lane]
    for k in ("hl", "lvl", "stt", "ins"):
        if k not in (side, "lvl" if side == "hl" else None):
            q_side(ns, A, k, {"complete": True, "tries": 0,
                              "chapters": [{"t": 0}]} if k == "ins"
                   else None)
    knobs["write"][side] = False
    if lane == "thinking":
        knobs["owe_ins"][A] = True
    q_beat(ns, 10)
    n = sum(1 for c in calls if c == (lane, A))
    said = [l for l in logs if "said done twice" in l]
    _q_shutil.rmtree(tmp, ignore_errors=True)
    return n, dict(ns["_AI"]["failed"]), said, A, os.path.getmtime


for _lane in ("listening", "hearing", "thinking"):
    _n, _failed, _said, _A, _ = q_f1_lie(Q_SRC, _lane)
    check("F1 %s: a lying writer is spawned at most twice in 10 beats "
          "(%d), memoed failed, and said once in the log"
          % (_lane, _n),
          _n == 2 and len(_failed) == 1 and _A in _failed
          and len(_said) == 1 and _lane in _said[0])

# the guards for the memo's own hazards
ns, A, calls, tails, logs, knobs, tmp = q_f1_ns(Q_SRC)
q_side(ns, A, "stt")
q_side(ns, A, "ins", {"complete": True, "tries": 0, "chapters": [{"t": 0}]})
q_beat(ns)                                   # the honest sound run
knobs["owe_hud"][A] = True                   # now the screen owes
q_beat(ns)
check("F1 guard: after an honest sound run the SCREEN tail visit on the "
      "same night still runs (it rides kind listening with hl/lvl "
      "untouched) and nothing is memoed",
      [c[0] for c in calls] == ["listening"] and tails == [("screen", A)]
      and int(ns["_AI"].get("done_rev") or 0) == 2
      and ns["_AI"]["failed"] == {}
      and not any("said done twice" in l for l in logs))
_q_shutil.rmtree(tmp, ignore_errors=True)

ns, A, calls, tails, logs, knobs, tmp = q_f1_ns(Q_SRC)
q_side(ns, A, "stt")
q_side(ns, A, "ins", {"complete": True, "tries": 0, "chapters": [{"t": 0}]})
knobs["write"]["hl"] = False
ns["_AI"]["force_queue"] = [(A, "all", False, [])]
q_beat(ns, 2)
check("F1 guard: a forced 'all' ask on a night whose writer lies is "
      "cleared by force_ran, never by this memo (a direct ask always "
      "runs)",
      [c[0] for c in calls] == ["listening"] and ns["_AI"]["force"] is None
      and ns["_AI"]["force_queue"] == [] and ns["_AI"]["failed"] == {}
      and not any("said done twice" in l for l in logs))
_q_shutil.rmtree(tmp, ignore_errors=True)

ns, A, calls, tails, logs, knobs, tmp = q_f1_ns(Q_SRC)
q_side(ns, A, "stt")
q_side(ns, A, "ins", {"complete": True, "tries": 0, "chapters": [{"t": 0}]})
q_beat(ns, 3)                                # honest run, then idle
_t = _q_real_time.time()
for _k in ("hl", "lvl"):                     # the first run's sidecars...
    os.utime(ns["_ai_sidecar"](A, _k), (_t - 100.0, _t - 100.0))
os.utime(A, (_t - 50.0, _t - 50.0))          # ...and then the recording changed
q_beat(ns, 3)
check("F1 guard: a night whose mp4 changed is run again (a new "
      "signature), not refused",
      [c[0] for c in calls] == ["listening", "listening"]
      and ns["_AI"]["failed"] == {}
      and not any("said done twice" in l for l in logs))
_q_shutil.rmtree(tmp, ignore_errors=True)

print("--- F1 witness: the tree before the fix (%s) on the same fixture "
      "---" % PARITY_BASE)
_n, _failed, _said, _A, _ = q_f1_lie(Q_BASE, "listening")
check("before: 10 beats -> 10 spawns of the same (night, kind), no memo, "
      "nothing logged (%d)" % _n,
      _n == 10 and _failed == {} and _said == [])

# ------------------------------------------------------------- F6
print("--- F6: a resumed redo-all does not hear and look again ---")


def q_f6_run(src, interrupt_on, ran0):
    """one redo-all ask; the describer is interrupted by the REAL
    pause-for-play road (lore.py's Pause: requeue at the front with
    sorted(force_ran), clear force, _ai_abort()) mirrored verbatim,
    fired from inside the describer after the senses and the eye have
    landed their sidecars"""
    tmp, out, data = q_shelf("f6")
    logs = []
    ns = q_ns(src, out, data, logs)
    AI = ns["_AI"]
    A = q_night(out, "somegame", "20240404_000626", 86400 * 30)
    q_side(ns, A, "hl", {"v": 2, "events": []})
    q_side(ns, A, "lvl", {"v": 2})
    q_side(ns, A, "stt", {"v": 2, "segments": []})
    got = {"sns": 0, "eye": 0, "ins": 0, "queued": []}

    def pause_for_play():
        path = AI.get("busy_path")
        with ns["_AI_FORCE_LOCK"]:
            if path and AI.get("force") == path:
                AI["force_queue"] = ([(path, AI.get("force_want") or "all",
                                       bool(AI.get("force_redo")),
                                       sorted(AI.get("force_ran") or set()))]
                                     + list(AI.get("force_queue") or []))
                got["queued"].append(list(AI["force_queue"][0][3]))
                AI["force"] = None
                AI["force_want"] = None
                AI["force_redo"] = False
        ns["_ai_abort"]()
        logs.append("Paused everything for you - " + str(path))

    def _senses_one(p):
        got["sns"] += 1
        q_side(ns, p, "sns", {"v": 1, "complete": True, "tries": 0,
                              "sounds": [], "voices": []})
        return True

    def _eyes_one(p):
        got["eye"] += 1
        q_side(ns, p, "vis", {"v": 1, "complete": True, "tries": 0,
                              "looks": [1, 2, 3], "places": [],
                              "counters": {"wanted": 3}})
        return True

    def _insights_one(p, forced=False, fresh=False):
        got["ins"] += 1
        if got["ins"] in interrupt_on:
            pause_for_play()
            return False
        q_side(ns, p, "ins", {"complete": True, "tries": 0,
                              "chapters": [{"t": 0, "title": "x"}]})
        return True
    ns["_senses_one"] = _senses_one
    ns["_eyes_one"] = _eyes_one
    ns["_insights_one"] = _insights_one
    q_reset(ns)
    AI["force_queue"] = [(A, "all", True, list(ran0))]
    for _ in range(5):
        q_beat(ns)
    got["force"] = AI.get("force")
    got["queue"] = list(AI.get("force_queue") or [])
    got["ins_fresh"] = ns["_ai_sidecar_fresh"](A, "ins")
    got["vis_owing"] = ns["_vis_owing"](A)
    _q_shutil.rmtree(tmp, ignore_errors=True)
    return got


g6 = q_f6_run(Q_SRC, {1, 2}, ["listening", "hearing"])
check("F6 (a) one redo-all ask interrupted twice: the senses ran ONCE",
      g6["sns"] == 1)
check("F6 (b) ...and the eye ran ONCE (its .vis was complete on disk)",
      g6["eye"] == 1 and g6["vis_owing"] is False)
check("F6 (c) the describer landed on try 3, the ask cleared, the "
      "review is fresh, and the fifth beat was a no-op",
      g6["ins"] == 3 and g6["force"] is None and g6["queue"] == []
      and g6["ins_fresh"] is True)
check("F6 (d) the memory rode the queue tuple through both requeues: "
      "sns and vis beside listening and hearing",
      len(g6["queued"]) == 2
      and all(set(q) >= {"listening", "hearing", "sns", "vis"}
              for q in g6["queued"]))
g6f = q_f6_run(Q_SRC, set(), [])
check("F6 guard: a fresh redo-all (ran=[]) still hears and looks again "
      "from scratch, once each, and lands",
      g6f["sns"] == 1 and g6f["eye"] == 1 and g6f["ins"] == 1
      and g6f["force"] is None and g6f["ins_fresh"] is True)

print("--- F6 witness: the tree before the fix (%s) on the same fixture "
      "---" % PARITY_BASE)
g6b = q_f6_run(Q_BASE, {1, 2}, ["listening", "hearing"])
check("before: the senses and the eye re-ran on every resume (3 each "
      "for one ask), the describer landed on try 3",
      g6b["sns"] == 3 and g6b["eye"] == 3 and g6b["ins"] == 3)

# ------------------------------------------------------------- F2
print("--- F2: the Working page's held-back count is OF THE LEFT, per "
      "lane ---")


def q_f2_tally(src, done):
    N1, N2, X1 = (r"D:\shelf\nevergame_1.mp4", r"D:\shelf\nevergame_2.mp4",
                  r"D:\shelf\other_1.mp4")
    never = {N1, N2}
    ns = {"time": QTime, "os": os, "_AI": {},
          "SETTINGS": {"output_dir": r"D:\shelf"},
          "_library_dirs": lambda out: [(r"D:\shelf", "video")],
          "_scan_dir_mp4s": lambda d, k: [
              {"path": N1, "mtime": 1, "size": 1},
              {"path": N2, "mtime": 2, "size": 1},
              {"path": X1, "mtime": 3, "size": 1}],
          "_ai_sidecar_fresh": lambda p, s: p in done,
          "_ins_done_honest": lambda p: p in done,
          "_ins_owing": lambda p: p not in done,
          "_ai_sidecar": lambda p, s: p + "." + s + ".json",
          "_secs_no_probe": lambda v: 60.0,
          "_aud_done_current": lambda p: p in done,
          "_desc_mmproj": lambda: None,
          "_describer_paths": lambda: None,
          "_vis_owing": lambda p: False,
          "_game_rank": lambda p: "never" if p in never else "normal"}
    q_lift(src, "_ai_tally", ns)
    return ns["_ai_tally"](), N2


_lanes = ("listening", "hearing", "thinking", "auditing")
T2, _N2 = q_f2_tally(Q_SRC, {r"D:\shelf\nevergame_1.mp4",
                             r"D:\shelf\nevergame_2.mp4"})
check("F2 two never nights done on every lane + one normal night owing "
      "all: every lane's held is 0 beside its left (1, 1, 1, 0)",
      all(T2[j].get("held") == 0 for j in _lanes)
      and all(T2[j]["left"] == 1 for j in _lanes[:3])
      and T2["auditing"]["left"] == 0)
T2b, _ = q_f2_tally(Q_SRC, {r"D:\shelf\nevergame_1.mp4"})
check("F2 un-do the second never night's every lane: it is back in left "
      "AND in held on each (2 left, 1 never on its own), and held <= "
      "left everywhere",
      all(T2b[j]["left"] == 2 and T2b[j].get("held") == 1
          for j in _lanes[:3])
      and T2b["auditing"]["left"] == 0 and T2b["auditing"].get("held") == 0
      and all((T2b[j].get("held") or 0) <= T2b[j]["left"] for j in _lanes))
check("F2 the un-owe law still holds: a rank never un-owes a night",
      T2b["thinking"]["left"] == 2)
check("F2 the status road hands each lane ITS OWN held, and the page "
      "still prints k.held beside k.left",
      '"held": k.get("held", 0),' in Q_SRC
      and '"held": t.get("held_back", 0),' not in Q_SRC
      and "(k.held?num(k.held)+' never on their own':null)," in io.open(
          os.path.join(ROOT, "ui.html"), encoding="utf-8").read())
print("--- F2 witness: the tree before the fix (%s) on the same fixture "
      "---" % PARITY_BASE)
T2x, _ = q_f2_tally(Q_BASE, {r"D:\shelf\nevergame_1.mp4",
                             r"D:\shelf\nevergame_2.mp4"})
check("before: no per-lane held at all, and the one shelf number (2) "
      "exceeded every lane's left (1) - '1 left - 2 never on their own'",
      all("held" not in T2x[j] for j in _lanes)
      and T2x.get("held_back") == 2
      and all(T2x["held_back"] > T2x[j]["left"] for j in _lanes))

# =========================================================================
# THE AFK AREA (AFK-1, AFK-4). The detector's real functions are
# AST-lifted out of the tree and out of PARITY_BASE into a stub
# namespace with a fake clock (no device, no process); the describer
# checks run the real _insights_one on a tempdir night with a fake
# describer whose ask is killed under it.
#
#  AFK-1 TWO AFK CLOCKS DISAGREED ON THE SAME BEAT. _afk_track folded
#        the mic into its idle reading ("a voice is a person") while
#        _afk_ai_tick read the raw keyboard/mouse/pad clock beside it -
#        so at ten quiet-handed minutes of a LIVE recording (he is
#        talking, hands off the pad; his recorder pause is 4 min, his
#        catch-up 10) the catch-up armed, announced the whole suite,
#        lifted his holds, counted a wake, and then ran nothing at all:
#        the live-session gate in _ai_tick refuses every job until he
#        touches something. 191 h of log: 45 arms, 0 recorder pauses.
#        Fix: one reading, _afk_person_seconds, for both.
#  AFK-4 AN INTERRUPTION WAS COUNTED AS AN ANSWER ON THE WINDOW BUDGET.
#        The catch-up's end (and a Stop, and a game start) kills the
#        describer under the open ask; the window loop then asked the
#        dead server a second time, logged 'did not parse', spent one
#        of the window's five asks on it and banked the window empty
#        with that ask - five such ends settled a half hour as FINISHED
#        with nothing told and the next clean run never asked for it.
#        The tries law already said an interruption spends no try; now
#        the ask budget says the same, and the popped range goes back.
# =========================================================================
import threading as _afk_threading

print("\n=== THE AFK AREA: AFK-1 / AFK-4 ===")
print("--- AFK-1: the recorder's AFK clock and the catch-up's are ONE "
      "clock ---")
AFK_READ = {"kbms": 0}
AFK_FUNCS = ("_afk_idle_seconds", "_afk_idle_recent", "_afk_track",
             "_afk_ai_release", "_afk_ai_tick", "_bg_work_allowed")
# the live-session gate exactly as _ai_tick applies it (asserted to
# still be the text on the tree, then evaluated on the fixture)
AFK_GATE = ('_live = _sess is not None and not getattr(_sess, '
            '"suspended", False)\n'
            '        _afk_ok = bool(_AFKAI.get("on")) and not _live')
check("AFK-1 the live-session gate still stands in _ai_tick (a job "
      "never runs beside a rolling recording)", Q_SRC.count(AFK_GATE) == 1)


def afk_ns(src):
    ns = {"time": QTime, "threading": _afk_threading, "LOG": [],
          "SETTINGS": {"afk_pause": True, "afk_minutes": 4,
                       "afk_ai": True, "afk_ai_minutes": 10,
                       "bg_shutdown": False},
          "_kbms_idle_ms": lambda: AFK_READ["kbms"],
          "_pad_check": lambda: None, "_PAD": {"active_t": 0.0},
          "_AFK_CLK": {"prev": 0.0, "said": 0.0, "pos": (0, 0)},
          "_AFK_SEEN": {"t": 0.0, "v": 0.0},
          "_cursor_pos": lambda: (0, 0),
          "_MICWATCH": {"last_sound": None},
          "_afk_deaf_seconds": lambda ctl, s: 0.0,
          "_loop_sound": lambda ctl, w: None,
          "_AFKAI": {"on": False, "since": 0.0, "idle": 0.0,
                     "held": None, "shut": None, "set": None, "woke": 0},
          "_AFKAI_LOCK": _afk_threading.Lock(),
          "_AI": {"held": {}, "paused": False, "busy": None, "t_last": 1},
          "_afk_ai_off_kinds": lambda: [],
          "_ai_state_save": lambda: None,
          "_ai_abort": lambda *a, **k: None,
          "_ai_effective_lane": lambda k, p: k}
    ns["log"] = lambda m: ns["LOG"].append(str(m))
    for nm in AFK_FUNCS:
        q_lift(src, nm, ns)
    if "def _afk_person_seconds" in src:
        q_lift(src, "_afk_person_seconds", ns)
    return ns


class AfkSession(object):
    def __init__(self):
        self.afk_paused = False
        self.suspended = False
        self.audio = None

    def suspend(self):
        self.suspended = True


class AfkCtl(object):
    def __init__(self, session):
        self.session = session
        self.saving = 0
        self.status = ""
        self.rec_t0 = Q_CLOCK[0]

    def set_status(self, s):
        self.status = s

    def notify(self, *a):
        pass


def afk_readings(ns, kb_idle_s, pad_ago_s, mic_ago_s):
    AFK_READ["last"] = (kb_idle_s, pad_ago_s, mic_ago_s)
    AFK_READ["kbms"] = int(kb_idle_s * 1000)
    ns["_PAD"]["active_t"] = ((Q_CLOCK[0] - pad_ago_s)
                              if pad_ago_s is not None else 0.0)
    ns["_MICWATCH"]["last_sound"] = ((Q_CLOCK[0] - mic_ago_s)
                                     if mic_ago_s is not None else None)


def afk_gate_refuses(ns, ctl):
    _sess = ctl.session
    _live = _sess is not None and not getattr(_sess, "suspended", False)
    _afk_ok = bool(ns["_AFKAI"].get("on")) and not _live
    return (_sess is not None and not _afk_ok) or ctl.saving > 0


def afk_beat(ns, ctl, session):
    """one watcher beat then one AI beat, in the order the app runs
    them; the clock moves 6 s first so the shared poll is re-read, and
    the readings are re-laid against the moved clock ('mic 3 s ago'
    is 3 s ago on the beat that reads it)"""
    Q_CLOCK[0] += 6
    afk_readings(ns, *AFK_READ["last"])
    ns["_afk_track"](ctl, session, "game.exe")
    return ns["_afk_ai_tick"]()


def afk_case_a(src):
    """his live shape: 15 min no keyboard/mouse/pad, the mic heard him
    20 s ago, every lane held and the master pause on"""
    ns = afk_ns(src)
    s = AfkSession()
    c = AfkCtl(s)
    ns["_AI"]["held"] = {k: True for k in ("listening", "hearing",
                                           "thinking", "auditing")}
    ns["_AI"]["paused"] = True
    afk_readings(ns, 900, None, 20)
    armed = afk_beat(ns, c, s)
    return ns, s, c, armed


ns, s, c, armed = afk_case_a(Q_SRC)
check("AFK-1 (A) the recorder keeps rolling (a voice is a person)",
      not s.afk_paused and not s.suspended)
check("AFK-1 (A) ...and the catch-up on the SAME beat does not arm: "
      "on=%r idle=%r" % (ns["_AFKAI"]["on"], int(ns["_AFKAI"]["idle"])),
      armed is False and ns["_AFKAI"]["on"] is False
      and ns["_AFKAI"]["idle"] < 60)
check("AFK-1 (A) nothing announced, nothing counted, his holds and "
      "the master pause untouched",
      not any("AFK catch-up" in m for m in ns["LOG"])
      and ns["_AFKAI"]["woke"] == 0
      and all(ns["_AI"]["held"].values()) and ns["_AI"]["paused"] is True)
check("AFK-1 (A) _bg_work_allowed still answers his master switch",
      ns["_bg_work_allowed"]() is True)
# the voice stops: 10 more quiet minutes and he is gone by BOTH clocks
Q_CLOCK[0] += 600
afk_readings(ns, 1506, None, 626)
armed2 = afk_beat(ns, c, s)
check("AFK-1 (A') the mic quiet for 10 min: the recorder pauses AND "
      "the catch-up arms on the same beat, the gate allows",
      s.afk_paused and s.suspended and c.status == "paused"
      and armed2 is True and ns["_AFKAI"]["on"] is True
      and not afk_gate_refuses(ns, c))
check("AFK-1 (A') the holds it lifted were snapshotted for the release",
      ns["_AFKAI"]["held"] == {k: True for k in ("listening", "hearing",
                                                 "thinking", "auditing")}
      and not any(ns["_AI"]["held"].values()))
# he speaks: the recorder resumes-by-flag and the catch-up ends, holds back
afk_readings(ns, 1512, None, 3)
ns["LOG"][:] = []
afk_beat(ns, c, s)
check("AFK-1 (A'') a word into the mic ends both: flag cleared, "
      "catch-up released, holds restored exactly",
      s.afk_paused is False and ns["_AFKAI"]["on"] is False
      and any("AFK catch-up ended" in m for m in ns["LOG"])
      and all(ns["_AI"]["held"].values()) and ns["_AI"]["paused"] is True)

print("--- AFK-1 (B) control: mic silent, 15 min no input ---")
ns = afk_ns(Q_SRC)
s = AfkSession()
c = AfkCtl(s)
afk_readings(ns, 900, None, None)
armed = afk_beat(ns, c, s)
check("AFK-1 (B) recorder paused at >= 4 min and the catch-up armed on "
      "the same beat; the gate allows work",
      s.afk_paused and s.suspended and c.status == "paused"
      and armed is True and ns["_AFKAI"]["on"] is True
      and not afk_gate_refuses(ns, c)
      and sum("AFK catch-up:" in m for m in ns["LOG"]) == 1)
afk_readings(ns, 906, None, None)
armed2 = afk_beat(ns, c, s)
check("AFK-1 (C) a second beat on the same readings re-arms nothing "
      "and says nothing twice",
      armed2 is False and ns["_AFKAI"]["on"] is True
      and ns["_AFKAI"]["woke"] == 1
      and sum("AFK catch-up:" in m for m in ns["LOG"]) == 1)
check("AFK-1 (D) with no recording at all the mic stamp is old and the "
      "catch-up arms exactly as before",
      (lambda n: (afk_readings(n, 900, None, 7200),
                  n["_afk_ai_tick"]())[1] is True)(afk_ns(Q_SRC)))
check("AFK-1 the fold lives in ONE place: _afk_person_seconds reads "
      "the mic, and neither _afk_track nor _afk_ai_tick does",
      "_MICWATCH" in Q_SRC.split("def _afk_person_seconds")[1]
      .split("\ndef ")[0]
      and "_MICWATCH" not in Q_SRC.split("def _afk_track")[1]
      .split("\ndef ")[0]
      and "_MICWATCH" not in Q_SRC.split("def _afk_ai_tick")[1]
      .split("\ndef ")[0]
      and "_afk_person_seconds(fresh=True)" in Q_SRC.split(
          "def _afk_track")[1].split("\ndef ")[0]
      and "_afk_person_seconds()" in Q_SRC.split(
          "def _afk_ai_tick")[1].split("\ndef ")[0])
print("--- AFK-1 witness: the tree before the fix (%s) on the same "
      "readings ---" % PARITY_BASE)
nsb, sb, cb, armedb = afk_case_a(Q_BASE)
check("before: the recorder kept rolling while the catch-up armed on "
      "the same beat, lifted every hold, counted a wake - and the gate "
      "refused every job",
      not sb.suspended and armedb is True and nsb["_AFKAI"]["on"] is True
      and not any(nsb["_AI"]["held"].values())
      and nsb["_AFKAI"]["woke"] == 1 and afk_gate_refuses(nsb, cb))

# -------------------------------------------------------------- AFK-4
print("--- AFK-4: an ask killed under the describer spends no ask ---")
lore.LOG = []
lore.log = lambda m: lore.LOG.append(str(m))


def afk4_docs(L, vid):
    p = L._ai_sidecar(vid, "ins")
    return [rd(q) for q in (p, p + ".new") if os.path.isfile(q)]


def afk4_second(n, k):
    """the second window under its own name - two names, two chapters"""
    return json.dumps({"segments": [
        {"name": "the tower falls", "what": "the tower comes down",
         "topics": ["tower"], "from_line": 0, "to_line": n - 1,
         "quote": ""}], "moments": []})


def afk4_killer(L):
    def f(n, k):
        L._AI["abort"] = True      # the server taken from under the ask
        return None                # ...is what .ask hands back
    return f


def afk4_run(L, root, vid, answers):
    mount(L, root)
    describer(L, answers)
    ASKS[:] = []
    L.LOG[:] = []
    L._insights_one(vid, forced=True)
    return list(ASKS), list(L.LOG), afk4_docs(L, vid)


def afk4_fixture(L, tag):
    root = tempfile.mkdtemp(prefix="loops336_afk4_%s_" % tag)
    mount(L, root)
    vid = build_night(L, root, (12, 12), 3000.0)
    return root, vid


root, vid = afk4_fixture(lore, "cut")
a1, l1, d1 = afk4_run(lore, root, vid, {0: afk4_killer(lore), 30: afk4_second})
check("AFK-4 (a) one ask only - the dead server is not asked again: %r"
      % (a1,), a1 == ["w0"])
check("AFK-4 (b) no 'did not parse', no parse-retry count, and no "
      "'-> 0 stretch(es)' line on an interruption",
      not any("did not parse" in m for m in l1)
      and not any("parse retr" in m for m in l1)
      and not any("stretch(es)" in m for m in l1))
check("AFK-4 (c) nothing banked for the window, tries 0",
      all("0" not in (d.get("windows") or {}) and not d.get("tries")
          for d in d1))
for _ in range(4):
    a5, l5, d5 = afk4_run(lore, root, vid, {0: afk4_killer(lore), 30: afk4_second})
check("AFK-4 (d) five interruptions later the window is still unbanked "
      "and still owed",
      all("0" not in (d.get("windows") or {}) and not d.get("tries")
          for d in d5))
a6, l6, d6 = afk4_run(lore, root, vid, {0: whole, 30: afk4_second})
d6s = rd(lore._ai_sidecar(vid, "ins"))
check("AFK-4 (e) the next clean run asks the window in full and the "
      "review is whole: %r" % (a6,),
      a6 == ["w0", "w30", "title"] and d6s.get("complete") is True
      and len(d6s.get("chapters") or []) == 2
      and len(((d6s.get("windows") or {}).get("0") or {})
              .get("segments") or []) == 1)

print("--- AFK-4 (f) an ask that LANDED before the kill is kept ---")
root = tempfile.mkdtemp(prefix="loops336_afk4_partial_")
mount(lore, root)
vid = os.path.join(root, "night.mp4")
io.open(vid, "w").write("v")
json.dump({"v": 3, "engine": "qwen3-asr", "reader": 7,
           "sources": {"voice": False, "game": False, "media": False},
           "segments": room_lines(0, 40, 40)},
          io.open(lore._ai_sidecar(vid, "stt"), "w", encoding="utf-8"))
json.dump({"v": lore._HL_V, "events": []},
          io.open(lore._ai_sidecar(vid, "hl"), "w", encoding="utf-8"))
lore._video_duration = lambda p: 1800.0
lore._story_seconds = lambda p, d: (1800.0, "")


def afk4_partial(n, k):
    if k == 1:
        return json.dumps({"segments": [
            {"name": "the opening", "what": "they warm up",
             "topics": ["lane"], "from_line": 0, "to_line": 9,
             "quote": ""}], "moments": []})
    lore._AI["abort"] = True
    return None


af, lf, df = afk4_run(lore, root, vid, {0: afk4_partial})
w0f = ((df[0] if df else {}).get("windows") or {}).get("0") or {}
check("AFK-4 (f) the landed ask is banked (1 stretch, asks 1) and the "
      "killed one spent nothing: left 30, pend [[10, 40]]: %r"
      % ({k: w0f.get(k) for k in ("asks", "left", "pend")},),
      len(af) == 2 and len(w0f.get("segments") or []) == 1
      and w0f.get("asks") == 1 and w0f.get("left") == 30
      and w0f.get("pend") == [[10, 40]])

print("--- AFK-4 witness: the tree before the fix (%s) on the same "
      "fixture ---" % PARITY_BASE)
AFK_BASE_PY = os.path.join(tempfile.mkdtemp(prefix="loops336_afkbase_"),
                           "lore_afk_base.py")
io.open(AFK_BASE_PY, "w", encoding="utf-8", newline="").write(Q_BASE)
_spec = importlib.util.spec_from_file_location("lore_afk_base", AFK_BASE_PY)
lore_afk_base = importlib.util.module_from_spec(_spec)
sys.modules["lore_afk_base"] = lore_afk_base
lore_afk_base.__dict__["log"] = lambda m: None
_spec.loader.exec_module(lore_afk_base)
pen(lore_afk_base)
root, vid = afk4_fixture(lore_afk_base, "base")
ab, lb, db = afk4_run(lore_afk_base, root, vid,
                      {0: afk4_killer(lore_afk_base), 30: afk4_second})
w0b = ((db[0] if db else {}).get("windows") or {}).get("0")
check("before: the dead server was asked twice, the kill logged as "
      "'did not parse', and the window banked empty with one ask spent",
      ab == ["w0", "w0"] and any("did not parse" in m for m in lb)
      and isinstance(w0b, dict) and w0b.get("asks") == 1
      and w0b.get("segments") == [])
del sys.modules["lore_afk_base"]

# =========================================================================
# THE LEAD'S LEFTOVERS (the audit's lows the lead took himself): AFK-2 the
# catch-up beside a live recording, F4 the preview's head and gates,
# UI-A1/A2 the dark pen's reason. Same fixtures as the sections above.
# =========================================================================
print("\n=== THE LEAD'S LEFTOVERS: AFK-2 / F4 / UI-A1-A2 ===")
print("--- AFK-2: the catch-up does not arm beside a live recording ---")


def afk2_case(src, suspended, with_ctl=True):
    """15 min of no input, pad never, mic never - the recorder's own
    pause switched OFF so the session stays live on its own."""
    ns = afk_ns(src)
    ns["SETTINGS"]["afk_pause"] = False
    s = AfkSession()
    s.suspended = suspended
    c = AfkCtl(s)
    Q_CLOCK[0] += 6
    afk_readings(ns, 900, None, None)
    ns["_afk_track"](c, s, "game.exe")
    armed = ns["_afk_ai_tick"](c) if with_ctl else ns["_afk_ai_tick"]()
    return ns, s, c, armed


ns2, s2, c2, a2 = afk2_case(Q_SRC, False)
check("AFK-2 a live, unsuspended recording: the catch-up does not arm, "
      "lifts no hold, counts no wake, says nothing",
      a2 is False and not ns2["_AFKAI"]["on"]
      and ns2["_AFKAI"]["woke"] == 0 and not ns2["LOG"]
      and afk_gate_refuses(ns2, c2))
ns3, s3, c3, a3 = afk2_case(Q_SRC, True)
check("AFK-2 a SUSPENDED session (the recorder itself paused for AFK) "
      "still arms on the same readings",
      a3 is True and ns3["_AFKAI"]["on"] and ns3["_AFKAI"]["woke"] == 1)
ns4, s4, c4, a4 = afk2_case(Q_SRC, False, with_ctl=False)
check("AFK-2 a caller with no ctl (the older suites) arms as before",
      a4 is True and ns4["_AFKAI"]["on"])
nsb2, sb2, cb2, ab2 = afk2_case(Q_BASE, False, with_ctl=False)
check("before (%s): armed beside the live recording - holds lifted, a "
      "wake counted - while the gate refused every job" % PARITY_BASE,
      ab2 is True and nsb2["_AFKAI"]["on"] and afk_gate_refuses(nsb2, cb2))

# ------------------------------------------------------------------ F4
print("--- F4: the preview names the walk's head and takes the walk's "
      "gates ---")
F4_NIGHTS = [("D:/f4/new.mp4", 200.0), ("D:/f4/old.mp4", 100.0)]


def f4_pick(src, focus, game_front, live, owes):
    class _C(object):
        pass
    c = _C()
    c.session = object() if live else None
    ns = {"time": QTime, "os": os,
          "SETTINGS": {"output_dir": "x", "ai_transcribe": True,
                       "ai_highlights": True, "insights_auto": True,
                       "reread_old": False},
          "_AI": {"held": {}, "focus": focus, "ctl": c, "failed": {},
                  "next_pick": None},
          "_bg_work_allowed": lambda: True,
          "_library_dirs": lambda out: [("d", "k")],
          "_scan_dir_mp4s": lambda d, k: [{"path": p_, "mtime": m_}
                                          for p_, m_ in F4_NIGHTS],
          "_game_rank": lambda p_: "normal",
          "_RANK_ORDER": {"first": 0, "normal": 1, "later": 2},
          "_reader_paths": lambda: ("exe", "mdl"),
          "_describer_paths": lambda: ("exe", "mdl"),
          "_queued_finish_badge": lambda p_: False,
          "_ai_skipped_recently": lambda p_: False,
          "_ai_sidecar_fresh": lambda p_, k: k not in owes.get(p_, set()),
          "_stt_stale_reader": lambda p_: False,
          "_ins_owing": lambda p_: "ins" in owes.get(p_, set()),
          "_sns_owing": lambda p_: False,
          "_aud_owing_swept": lambda p_: "aud" in owes.get(p_, set()),
          "_game_has_focus": lambda: game_front}
    q_lift(src, "_ai_next_sweep", ns)
    v = ns["_ai_next_sweep"]()
    return (v or {}).get("name"), (v or {}).get("kind")


NEW, OLD = F4_NIGHTS[0][0], F4_NIGHTS[1][0]
both_hl = {NEW: {"hl"}, OLD: {"hl"}}
check("F4 (a) the focus night is named first, whatever its age",
      f4_pick(Q_SRC, OLD, False, False, both_hl) == ("old.mp4", "listening"))
check("F4 (a) control: no focus, the newest owed night is named",
      f4_pick(Q_SRC, None, False, False, both_hl) == ("new.mp4", "listening"))
check("F4 (b) a game in front: the describer is not named (the walk "
      "would not take it)",
      f4_pick(Q_SRC, None, True, False, {NEW: {"ins"}}) == (None, None))
check("F4 (b) control: no game in front, the describer is named",
      f4_pick(Q_SRC, None, False, False, {NEW: {"ins"}}) == ("new.mp4", "thinking"))
check("F4 (c) a live recording: the audit is not named",
      f4_pick(Q_SRC, None, False, True, {NEW: {"aud"}}) == (None, None))
check("F4 (c) control: nothing rolling, the audit is named",
      f4_pick(Q_SRC, None, False, False, {NEW: {"aud"}}) == ("new.mp4", "auditing"))
check("F4 the sound pass is still named under a game in front (the walk "
      "takes it)",
      f4_pick(Q_SRC, None, True, False, both_hl) == ("new.mp4", "listening"))
check("before (%s): the preview ignored the focus and named the gated "
      "describer and audit" % PARITY_BASE,
      f4_pick(Q_BASE, OLD, False, False, both_hl) == ("new.mp4", "listening")
      and f4_pick(Q_BASE, None, True, False, {NEW: {"ins"}}) == ("new.mp4", "thinking")
      and f4_pick(Q_BASE, None, False, True, {NEW: {"aud"}}) == ("new.mp4", "auditing"))

# ------------------------------------------------------------ UI-A1/A2
print("--- UI-A1/A2: the dark pen says why ---")
A_ROOT = tempfile.mkdtemp(prefix="loops336_a1_")
mount(lore, A_ROOT)
A_VID = build_night(lore, A_ROOT, [12], 1800)
json.dump({"v": 1, "chapters": [], "failed": True, "tries": 3,
           "windows": {}},
          io.open(lore._ai_sidecar(A_VID, "ins"), "w", encoding="utf-8"))


class _A1Ctl(object):
    session = None
    saving = 0


A_ASKED = []


def a1_flags(done, owing):
    keep = (lore._ins_done_honest, lore._ins_owing)
    lore._ins_done_honest = lambda p_: (A_ASKED.append("done"), done)[1]
    lore._ins_owing = lambda p_: (A_ASKED.append("owing"), owing)[1]
    try:
        return lore._JsApi(_A1Ctl()).have_flags([A_VID])[A_VID]
    finally:
        lore._ins_done_honest, lore._ins_owing = keep


r = a1_flags(False, False)
check("UI-A1 a review neither done nor owed (three tries spent) comes "
      "back at level 0 WITH the reason the shelf's button answers",
      r.get("ins_lvl") == 0 and not r.get("ins")
      and str(r.get("ins_why", "")).startswith("gave up after three tries"))
r = a1_flags(True, False)
check("UI-A2 an honestly-empty review comes back at level 0 with 'nothing "
      "here to tell' - never 'not described yet'",
      r.get("ins_lvl") == 0
      and r.get("ins_why") == "described - the tome found nothing here to tell")
r = a1_flags(False, True)
check("UI-A1 a review still owed (in flight) carries no reason - the mark "
      "keeps saying 'not described yet'",
      r.get("ins_lvl") == 0 and r.get("ins_why") == "")
A_ASKED[:] = []
os.remove(lore._ai_sidecar(A_VID, "ins"))
r = a1_flags(False, False)
check("UI-A1 a night with no review file asks neither judge (a batch of "
      "300 stays cheap)",
      r.get("ins_why") == "" and A_ASKED == [])
check("UI-A1 the lane row carries this lane's given-up count (the tally "
      "line reads k.gaveup)",
      Q_SRC.count('"gaveup": int((t.get("gaveup") or {}).get(kind) or 0),') == 1)
check("before (%s): have_flags had no reason for a gave-up or empty night "
      "and no lane row carried gaveup" % PARITY_BASE,
      "gave up after three tries - Ask again on" not in Q_BASE
      and "nothing here to tell" not in Q_BASE
      and '"gaveup": int((t.get("gaveup")' not in Q_BASE)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

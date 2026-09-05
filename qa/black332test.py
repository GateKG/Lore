# -*- coding: utf-8 -*-
"""3.32 THE BLACK-FRAME GUARD - the luma rule, the clock, the verdict
table, the bind tag and the lanes that honour it.

Drives the REAL functions lifted out of lore.py by name: _frame_black
on synthetic BGRA frames (an all-black frame, a limited-range black, a
dark game frame with one lit block, a short buffer); the feed's
_sample on a stand-in with a fake clock (the black clock, the stall
clock, a sampler that dies quietly); _black_track's verdict table with
every witness injected (in front / minimised / alt-tabbed, the screen
lit or black or unreadable, the size-parity 'split' against 'rotate',
the once-per-game toast, the twelve-hour ban); then, against the
installed ffmpeg, _picture_probe on a black mp4 and a lit one, the
pic.json fact and the settled vis, _pic_black's cache, _vis_owing on
both, the boot walk on a scratch shelf, visions() with the fact, the
lane gates and the eye's honest message read from the source, the
Settings key and the page. Scratch dirs live in tempfile and are
cleaned; nothing under D:\\Records is written (one read-only replay of
the 20 Aug file runs only when it is on the shelf)."""
import ast
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
USRC = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()
TREE = ast.parse(SRC)

ok = bad = 0


def check(what, cond):
    global ok, bad
    if cond:
        ok += 1
        print("  OK  ", what)
    else:
        bad += 1
        print("  FAIL", what)


def extract(name, ns):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


def method(cls_name, name, ns):
    for node in TREE.body:
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    code = textwrap.dedent("\n".join(
                        SRC.splitlines()[f.lineno - 1:f.end_lineno]))
                    exec(compile(code, "<%s.%s>" % (cls_name, name),
                                 "exec"), ns)
                    return ns[name]
    raise AssertionError(cls_name + "." + name)


def const(name):
    m = re.search(r"^%s\s*=\s*([0-9.]+)" % re.escape(name), SRC, re.M)
    return float(m.group(1))


def body_of(name):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
    raise AssertionError(name)


# ---------------------------------------------------------------------------
print("--- the luma rule ---")
import numpy as np  # noqa: E402

fns = {}
_frame_black = extract("_frame_black", fns)


def bgra(w, h, fill=0):
    return np.full((h, w, 4), fill, dtype=np.uint8)


for (w, h) in ((1920, 1080), (2560, 1440)):
    f = bgra(w, h)
    check("all-zero %dx%d is black" % (w, h),
          _frame_black(f.tobytes(), w, h) is True)
    d = np.random.randint(0, 4, size=(h, w, 4)).astype(np.uint8)
    check("a 0-3 dither (limited-range black after decode) is black at %dx%d"
          % (w, h), _frame_black(d.tobytes(), w, h) is True)
    f2 = bgra(w, h)
    f2[300:308, 400:408, :3] = 200
    check("one lit 8x8 block at (400,300) is NOT black at %dx%d" % (w, h),
          _frame_black(f2.tobytes(), w, h) is False)
d7 = np.random.randint(0, 8, size=(1080, 1920, 4)).astype(np.uint8)
check("a 0-7 dither has a mean over 2 - not black by the rule "
      "(the mean is the guard against a grey-dark game)",
      _frame_black(d7.tobytes(), 1920, 1080) is False)
f16 = bgra(1920, 1080, 16)
check("a flat 16,16,16 frame is not black (max reaches the limit)",
      _frame_black(f16.tobytes(), 1920, 1080) is False)
check("a buffer shorter than the frame is never black by accident",
      _frame_black(b"\0" * 1000, 1920, 1080) is False)
check("junk never raises",
      _frame_black(None, 1920, 1080) is False
      and _frame_black(b"", 0, 0) is False)
big = bgra(2560, 1440).tobytes()
t0 = time.perf_counter()
for _ in range(200):
    _frame_black(big, 2560, 1440)
took = time.perf_counter() - t0
print("      200 samples at 1440p took %.3f s (%.2f ms each)"
      % (took, took * 5))
check("200 samples at 1440p stay under a second (measured ~0.86 ms each)",
      took < 1.0)

# ---------------------------------------------------------------------------
print("\n--- the feed's clocks ---")
sns = {}
_sample = method("_WGCFeed", "_sample", sns)


class Feed:
    def __init__(self):
        self.w, self.h = 64, 36
        self.frames_in = 0
        self.black_since = None
        self.black_n = 0
        self.lit_at = 0.0
        self.seen_in = 0
        self.stalled_since = None
        self.sampler_dead = False


black_buf = bgra(64, 36).tobytes()
lit_buf = bgra(64, 36, 120).tobytes()
sns["_frame_black"] = _frame_black
fd = Feed()
fd.frames_in = 1
_sample(fd, black_buf, 1000.0)
_sample(fd, black_buf, 1000.5)
_sample(fd, black_buf, 1001.0)
check("black frames set black_since ONCE and count the run",
      fd.black_since == 1000.0 and fd.black_n == 3)
fd.frames_in = 2
_sample(fd, lit_buf, 1001.5)
check("a lit frame clears the black clock and stamps lit_at",
      fd.black_since is None and fd.lit_at == 1001.5)
# frames_in frozen from here: the stall clock starts at the first
# sample that sees no movement and holds
_sample(fd, lit_buf, 1002.0)
_sample(fd, lit_buf, 1012.0)
check("frames_in frozen for 10 s sets stalled_since once and keeps it",
      fd.stalled_since == 1002.0)
fd.frames_in = 3
_sample(fd, lit_buf, 1012.5)
check("a fresh frame clears the stall clock", fd.stalled_since is None
      and fd.seen_in == 3)


def _boom(*a, **k):
    raise RuntimeError("sampler fell over")


sns["_frame_black"] = _boom
fd2 = Feed()
try:
    _sample(fd2, black_buf, 1.0)
    raised = False
except Exception:
    raised = True
check("a raising sampler marks itself dead and never propagates",
      not raised and fd2.sampler_dead is True)
sns["_frame_black"] = _frame_black
_sample(fd2, black_buf, 2.0)
check("...and stays quiet afterwards", fd2.black_since is None)
check("the ticker samples every 30th write, only while the sampler lives",
      "self._tick_n % 30 == 0 and not self.sampler_dead" in SRC
      and "self._sample(buf, time.time())" in SRC)

# ---------------------------------------------------------------------------
print("\n--- the verdict table ---")
tns = {"time": time, "SETTINGS": {"black_guard": True,
                                  "min_keep_seconds": 45}}
LOGS = []
tns["log"] = lambda m: LOGS.append(m)
tns["_BLACK_PATIENCE"] = const("_BLACK_PATIENCE")
tns["_BLACK_PATIENCE_BLIND"] = const("_BLACK_PATIENCE_BLIND")
tns["_WGC_BLACK"] = {}
tns["_WGC_BLACK_TTL"] = 12 * 3600.0
check("the ban lasts twelve hours in the source",
      "_WGC_BLACK_TTL = 12 * 3600.0" in SRC)
W = {"rect": {"hwnd": 77, "mon": 0, "x": 0, "y": 0, "w": 1920, "h": 1080},
     "fg": 77, "screen": 120.0, "idle": 300.0, "loud": False,
     "captured": 60}
tns["_game_window_rect"] = lambda p, hwnd=None: W["rect"]
tns["_foreground_root"] = lambda: W["fg"]
tns["_root_hwnd"] = lambda h: h
tns["_screen_probe"] = lambda r: W["screen"]
tns["_afk_idle_recent"] = lambda *a: W["idle"]
tns["_ring_loud"] = lambda aud, within=10.0: W["loud"]
tns["_captured_seconds"] = lambda s: W["captured"]
_black_track = extract("_black_track", tns)
_wgc_black_banned = extract("_wgc_black_banned", tns)
check("the patience is ten seconds, twenty when the screen cannot answer",
      tns["_BLACK_PATIENCE"] == 10.0 and tns["_BLACK_PATIENCE_BLIND"] == 20.0)


class Ctl:
    def __init__(self):
        self.toasts = []
        self._black_toasted = set()

    def notify(self, title, msg, force=False):
        self.toasts.append((title, msg, force))


def sess(black_since, cap_wh=(1920, 1080), game="rocketleague.exe"):
    s = types.SimpleNamespace()
    s._wgc = types.SimpleNamespace(black_since=black_since, stalled_since=None)
    s.suspended = False
    s.win_paused = False
    s.game = game
    s.win = {"hwnd": 77, "mon": 0, "x": 0, "y": 0, "w": 1920, "h": 1080}
    s.cap_wh = cap_wh
    s.audio = None
    s.tmp = ""
    return s


NOW = 5000.0
ctl = Ctl()
check("black for 9 s: nothing yet",
      _black_track(ctl, sess(NOW - 9.0), "rocketleague.exe", now=NOW) is None)
check("no feed (the screen-region path): nothing, ever",
      _black_track(ctl, types.SimpleNamespace(_wgc=None, suspended=False,
                                              win_paused=False),
                   "x", now=NOW) is None)
s0 = sess(None)
s0._black_probe_t = 4999.0
check("a lit feed resets the probe clock",
      _black_track(ctl, s0, "rocketleague.exe", now=NOW) is None
      and s0._black_probe_t == 0.0)
W["captured"] = 12
check("10 s, in front, screen lit, 12 s captured -> 'restart' (a launch)",
      _black_track(ctl, sess(NOW - 10.0), "rocketleague.exe", now=NOW)
      == "restart")
check("...the log line is exact",
      LOGS and LOGS[-1] == "Capture: the window gave only black frames for "
      "10 s - recording the screen region instead.")
check("...and the game is banned from WGC",
      _wgc_black_banned("rocketleague.exe", now=NOW) is True
      and _wgc_black_banned("ROCKETLEAGUE.EXE", now=NOW + 11 * 3600) is True)
check("...for twelve hours, not longer",
      _wgc_black_banned("rocketleague.exe", now=NOW + 12 * 3600 + 1) is False
      and _wgc_black_banned("other.exe", now=NOW) is False)
check("the toast fired once, forced over the game",
      len(ctl.toasts) == 1 and ctl.toasts[0][0] == "Recording"
      and ctl.toasts[0][2] is True
      and "recording the screen region instead" in ctl.toasts[0][1])
W["captured"] = 60
s1 = sess(NOW - 10.0)
v = _black_track(ctl, s1, "rocketleague.exe", now=NOW)
check("60 s captured and cap_wh == rect -> 'rotate' (1920x1080 on both paths)",
      v == "rotate" and s1.win is W["rect"])
check("a second verdict for the same game does not toast again",
      len(ctl.toasts) == 1)
W["rect"] = {"hwnd": 77, "mon": 0, "x": 0, "y": 0, "w": 2552, "h": 678}
check("rect 2552x678 (WGC) vs cap_wh 2552x672 (ddagrab) -> 'split', never rotate",
      _black_track(ctl, sess(NOW - 10.0, cap_wh=(2552, 672)),
                   "rocketleague.exe", now=NOW) == "split")
check("a fresh game toasts on its own verdict",
      _black_track(ctl, sess(NOW - 10.0, game="nine sols.exe"),
                   "nine sols.exe", now=NOW) == "split"
      and len(ctl.toasts) == 2)
W["rect"] = {"hwnd": 77, "mon": 0, "x": 0, "y": 0, "w": 1920, "h": 1080}
# the screen is black too
W["screen"] = 3.0
LOGS[:] = []
s2 = sess(NOW - 15.0)
r1 = _black_track(ctl, s2, "rocketleague.exe", now=NOW)
r2 = _black_track(ctl, s2, "rocketleague.exe", now=NOW + 6.0)
said = [m for m in LOGS if "so is the screen" in m]
check("screen black -> None, and exactly one 'so is the screen' line per session",
      r1 is None and r2 is None and len(said) == 1
      and said[0].startswith("Capture: the window has been black for 15 s"))
# the probe is rate-limited to one per five seconds
probes = []
tns["_screen_probe"] = lambda r: probes.append(r) or 120.0
s3 = sess(NOW - 10.0)
_black_track(ctl, s3, "rocketleague.exe", now=NOW)
_black_track(ctl, s3, "rocketleague.exe", now=NOW + 2.0)
_black_track(ctl, s3, "rocketleague.exe", now=NOW + 5.5)
check("the screen probe runs at most every five seconds", len(probes) == 2)
tns["_screen_probe"] = lambda r: W["screen"]
# no witness: the tie-breaker
W["screen"] = None
W["idle"] = 3.0
check("probe None + idle 3 s -> None at 12 s",
      _black_track(ctl, sess(NOW - 12.0), "rocketleague.exe", now=NOW) is None)
check("...and the verdict at 20 s",
      _black_track(ctl, sess(NOW - 20.0), "rocketleague.exe", now=NOW)
      == "rotate")
W["idle"] = 300.0
W["loud"] = False
check("probe None + idle 300 s + no loud ring -> None even at 30 s",
      _black_track(ctl, sess(NOW - 30.0), "rocketleague.exe", now=NOW) is None)
W["loud"] = True
check("...a loud game ring stands in for the pad",
      _black_track(ctl, sess(NOW - 30.0), "rocketleague.exe", now=NOW)
      == "rotate")
W["loud"] = False
W["screen"] = 120.0
# not the guard's call
W["rect"] = {"hwnd": 77, "iconic": True}
check("minimised -> None (the pause law owns it)",
      _black_track(ctl, sess(NOW - 30.0), "rocketleague.exe", now=NOW) is None)
W["rect"] = None
check("no window at all -> None",
      _black_track(ctl, sess(NOW - 30.0), "rocketleague.exe", now=NOW) is None)
W["rect"] = {"hwnd": 77, "mon": 0, "x": 0, "y": 0, "w": 1920, "h": 1080}
W["fg"] = 99
check("another root in front (alt-tabbed) -> None",
      _black_track(ctl, sess(NOW - 30.0), "rocketleague.exe", now=NOW) is None)
W["fg"] = 77
sp = sess(NOW - 30.0)
sp.win_paused = True
check("a window-paused session -> None", _black_track(ctl, sp, "x", now=NOW)
      is None)
sp = sess(NOW - 30.0)
sp.suspended = True
check("a suspended session -> None", _black_track(ctl, sp, "x", now=NOW)
      is None)
sd = sess(NOW - 30.0)
sd._wgc.sampler_dead = True
check("a dead sampler's frozen black clock is never acted on",
      _black_track(ctl, sd, "rocketleague.exe", now=NOW) is None)
tns["SETTINGS"]["black_guard"] = False
check("black_guard off -> None",
      _black_track(ctl, sess(NOW - 30.0), "rocketleague.exe", now=NOW) is None)
tns["SETTINGS"]["black_guard"] = True
tns["SETTINGS"]["min_keep_seconds"] = 0
W["captured"] = 4
check("min_keep_seconds 0: a 4 s head is never 'restart'",
      _black_track(ctl, sess(NOW - 30.0), "rocketleague.exe", now=NOW)
      == "rotate")
tns["SETTINGS"]["min_keep_seconds"] = 45
W["captured"] = 60
# _ring_loud itself
rns = {"time": time}
_ring_loud = extract("_ring_loud", rns)
import threading  # noqa: E402
aud = types.SimpleNamespace(_ring_lock=threading.Lock(), rings=[
    {"kind": "mic", "loud_t": time.time()},
    {"kind": "game", "loud_t": time.time() - 30},
])
check("_ring_loud: a mic ring never counts, an old game ring is quiet",
      _ring_loud(aud, 10.0) is False and _ring_loud(None) is False)
aud.rings[1]["loud_t"] = time.time() - 2
check("_ring_loud: a game ring loud two seconds ago counts",
      _ring_loud(aud, 10.0) is True)

# ---------------------------------------------------------------------------
print("\n--- the wiring, read from the source ---")
sr = SRC[SRC.index("    def _start_run(self):"):SRC.index("    def err_text(self):")]
check("_start_run's WGC condition carries the ban",
      "and not _wgc_black_banned(self.game)):" in sr)
check("...and the why-ladder names it",
      "gave only black frames earlier tonight" in sr)
beat = SRC[SRC.index("def _watch_core"):]
i_b = beat.index("bv = _black_track(ctl, session, current)")
i_w = beat.index("act = bv or _window_track(ctl, session, current)")
check("the healthy beat asks _black_track before _window_track", 0 < i_b < i_w)
check("...a 'rotate' verdict swaps the run inside the file, under _rotating",
      "if bv == \"rotate\":" in beat
      and beat.index("session._rotating = True", i_b) < i_w)
sn = body_of("_senses_one")
check("_senses_one: the whole OCR block sits under one _pic_black gate",
      "if _pic_black(video_path):" in sn
      and sn.index("if _pic_black(video_path):") < sn.index("elif os.path.isfile(ow)")
      and sn.index("elif os.path.isfile(ow)") < sn.index("[py, ow, video_path"))
check("...a black night writes hud {step, rows: [], black} and screen []",
      "sns[\"hud\"] = {\"step\": _HUD_STEP, \"rows\": [], \"black\": True}" in sn
      and "sns[\"screen\"] = []" in sn
      and "is black - the HUD reader did" in sn)
ins = body_of("_insights_one")
check("_insights_one: no frames are grabbed on a black night",
      "and not _black_pic):" in ins and "_black_pic = _pic_black(video_path)" in ins)
check("...and the frames sentence is swapped for the black one",
      "The picture of this recording is black" in ins
      and "never guess what " in ins and "was on screen. " in ins)
ey = body_of("_eyes_one")
check("_eyes_one asks the picture fact before it picks its looks",
      ey.index("if _pic_settle(video_path):") < ey.index("times = _eye_looks(video_path)")
      and "_settle({\"black\": 4}, black=True)" in ey)
check("...and a batch of under-floor jpegs says black, not ffmpeg",
      "the frames were black or empty" in ey
      and "ffmpeg could not reach those seconds" in ey)
ss = SRC[SRC.index("class Session:"):SRC.index("class _Ctl:")]
i1 = ss.index("self._write_src_sidecar()")
i2 = ss.index("_picture_probe(self.final)")
i3 = ss.index("_record_made_file(self.final)")
check("Session.stop probes after the src sidecar and before the file is owned",
      i1 < i2 < i3)
attic = re.search(r"_ATTIC_OF = \{(.*?)\}", SRC, re.S).group(1)
check("'pic' is a recording fact - never in _ATTIC_OF", "\"pic\"" not in attic
      and "'pic'" not in attic)
check("the finalize toast says the picture is black when it is",
      "\"Saved - but the picture is black\"" in SRC)
pb = body_of("_pic_black")
check("_pic_black never opens a video or spawns ffmpeg (the ONE JOB SLOT law)",
      "subprocess" not in pb and "_picture_probe" not in pb
      and "_PIC_CACHE" in pb)
check("the boot walk is the fifth named walk",
      re.search(r'_MIG_WALKS = \("refold", "eye", "strike", "echo", "black"\)',
                SRC) is not None
      and "(\"black\", _black_vis_migration," in SRC)
check("a changed transport forgets the bans",
      "if \"capture_backend\" in patch:" in SRC
      and "_WGC_BLACK.clear()" in SRC)

# ---------------------------------------------------------------------------
print("\n--- the Settings key ---")
sys.path.insert(0, ROOT)
import lore  # noqa: E402
lore.log = lambda m: None
lore.load_settings()
check("DEFAULTS carries black_guard = True",
      lore.DEFAULTS.get("black_guard") is True)
d = {"black_guard": "yes"}
lore._sanitize_settings(d)
d2 = {}
lore._sanitize_settings(d2)
d3 = {"black_guard": 0}
lore._sanitize_settings(d3)
check("_sanitize_settings coerces the key to a bool, default on",
      d["black_guard"] is True and d2["black_guard"] is True
      and d3["black_guard"] is False)
check("the page has the row under Housekeeping, before Shelf space",
      "ctlToggle('black_guard')" in USRC
      and USRC.index("divider(L,'Housekeeping')")
      < USRC.index("ctlToggle('black_guard')")
      < USRC.index("row(L,'Shelf space'"))
check("the MOCK settings know the key", "black_guard:true" in USRC)

# ---------------------------------------------------------------------------
print("\n--- the bind tag, against the installed ffmpeg ---")
FF = lore.SETTINGS["ffmpeg_path"]
TD = tempfile.mkdtemp(prefix="blk332_")
lore.SETTINGS["output_dir"] = TD        # every sidecar lands in scratch


def mk(name, src, secs):
    p = os.path.join(TD, name)
    r = subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i",
                        "%ssize=64x36:rate=10:duration=%d" % (src, secs),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", p],
                       capture_output=True)
    return p if r.returncode == 0 and os.path.isfile(p) else None


BLACK = mk("black.mp4", "color=black:", 14)
LIT = mk("lit.mp4", "testsrc=", 14)
SHORT = mk("short.mp4", "color=black:", 5)
have = bool(BLACK and LIT and SHORT)
check("scratch mp4s rendered (black, lit, a 5 s clip)", have)
if have:
    b, lu, mx, sc = lore._picture_probe(BLACK)
    check("a black mp4 -> black True, every luma 0, every max under 16",
          b is True and len(lu) == 4 and all(x < 2.0 for x in lu)
          and all(x < 16 for x in mx) and len(sc) == 4)
    print("      black: luma %s max %s at %s" % (lu, mx, sc))
    b2, lu2, mx2, sc2 = lore._picture_probe(LIT)
    check("a testsrc mp4 -> black False, lit samples",
          b2 is False and len(lu2) == 4 and max(mx2) > 80)
    b3, lu3, mx3, sc3 = lore._picture_probe(SHORT)
    check("a 5 s clip -> no answer (None), nothing sampled",
          b3 is None and lu3 == [] and sc3 == [])
    lore._write_black_tag(BLACK, sc, lu, mx, b)
    pic = json.load(io.open(lore._ai_sidecar(BLACK, "pic"), encoding="utf-8"))
    vis = json.load(io.open(lore._ai_sidecar(BLACK, "vis"), encoding="utf-8"))
    check("pic.json: {v, black:true, sampled, luma, max, at}",
          pic.get("v") == 1 and pic.get("black") is True
          and pic.get("sampled") == sc and pic.get("luma") == lu
          and pic.get("max") == mx and pic.get("at"))
    check("vis.json settled: complete, black, no looks, tries 0",
          vis.get("complete") is True and vis.get("black") is True
          and vis.get("looks") == [] and vis.get("tries") == 0)
    vm = os.path.getmtime(lore._ai_sidecar(BLACK, "vis"))
    time.sleep(0.05)
    lore._write_black_tag(BLACK, sc, lu, mx, b)
    check("a second tag leaves a settled black vis alone (mtime-is-lineage)",
          os.path.getmtime(lore._ai_sidecar(BLACK, "vis")) == vm)
    lore._write_black_tag(LIT, sc2, lu2, mx2, b2)
    check("a lit file gets pic.json black:false and no vis at all",
          json.load(io.open(lore._ai_sidecar(LIT, "pic"),
                            encoding="utf-8")).get("black") is False
          and not os.path.isfile(lore._ai_sidecar(LIT, "vis")))
    check("_pic_black reads the facts: black True, lit False, absent False",
          lore._pic_black(BLACK) is True and lore._pic_black(LIT) is False
          and lore._pic_black(SHORT) is False)
    # the cache: same clock + size -> the cached answer; a changed file -> re-read
    pp = lore._ai_sidecar(LIT, "pic")
    stt = os.stat(pp)
    body = io.open(pp, encoding="utf-8").read()
    io.open(pp, "w", encoding="utf-8").write(body.replace("false", "true "))
    os.utime(pp, (stt.st_atime, stt.st_mtime))
    check("_pic_black is cached on (mtime, size): a same-clock rewrite is not re-read",
          lore._pic_black(LIT) is False)
    io.open(pp, "w", encoding="utf-8").write(body.replace("false", "true"))
    check("...a changed fact is re-read", lore._pic_black(LIT) is True)
    io.open(pp, "w", encoding="utf-8").write(body)
    check("...and back", lore._pic_black(LIT) is False)
    # the owe gate, with the eye installed
    _mm, _dp = lore._desc_mmproj, lore._describer_paths
    lore._desc_mmproj = lambda: "mmproj"
    lore._describer_paths = lambda: ("a", "b")
    try:
        check("_vis_owing: the black night is settled, the lit one still owed",
              lore._vis_owing(BLACK) is False and lore._vis_owing(LIT) is True)
    finally:
        lore._desc_mmproj, lore._describer_paths = _mm, _dp
    # the lane-side reader probes once and tags either way
    LIT2 = mk("lit2.mp4", "testsrc=", 14)
    BLK2 = mk("black2.mp4", "color=black:", 14)
    check("_pic_settle: no fact yet -> probes, tags, answers",
          lore._pic_settle(BLK2) is True and lore._pic_settle(LIT2) is False
          and os.path.isfile(lore._ai_sidecar(LIT2, "pic"))
          and os.path.isfile(lore._ai_sidecar(BLK2, "vis")))
    check("_pic_settle on the 5 s clip: no answer, nothing written",
          lore._pic_settle(SHORT) is False
          and not os.path.isfile(lore._ai_sidecar(SHORT, "pic")))

    # ---- the boot walk on a scratch shelf ------------------------------
    print("\n--- the boot walk ---")
    SH = os.path.join(TD, "shelf")
    os.makedirs(SH)
    lore.SETTINGS["output_dir"] = SH
    items = []
    for nm, src in (("stuck.mp4", "color=black"), ("dark.mp4", "testsrc"),
                    ("fine.mp4", "testsrc"), ("tiny.mp4", "color=black")):
        p = os.path.join(SH, nm)
        shutil.copy2({"color=black": BLACK, "testsrc": LIT}[src]
                     if nm != "tiny.mp4" else SHORT, p)
        items.append({"path": p, "file": nm, "kind": "session",
                      "mtime": os.path.getmtime(p), "size": 1})
    os.makedirs(lore._thumb_dir(SH), exist_ok=True)
    failed = {"v": 1, "failed": True, "tries": 3,
              "why": "0 ask(s) came back with nothing - ffmpeg could not "
                     "reach those seconds"}
    for nm in ("stuck.mp4", "dark.mp4", "tiny.mp4"):
        lore._atomic_write_json(lore._ai_sidecar(os.path.join(SH, nm), "vis"),
                                dict(failed))
    lore._atomic_write_json(lore._ai_sidecar(os.path.join(SH, "fine.mp4"),
                                             "vis"),
                            {"v": 1, "complete": True, "looks": [{"t": 5}]})
    dark_vp = lore._ai_sidecar(os.path.join(SH, "dark.mp4"), "vis")
    dark_m = os.path.getmtime(dark_vp)
    _ld, _sc = lore._library_dirs, lore._scan_dir_mp4s
    lore._library_dirs = lambda out: [(SH, "session")]
    lore._scan_dir_mp4s = lambda d0, k: list(items)
    lore._MIG_SKIPPED[0] = 0
    try:
        time.sleep(0.05)
        lore._black_vis_migration()
        sv = json.load(io.open(lore._ai_sidecar(os.path.join(SH, "stuck.mp4"),
                                                "vis"), encoding="utf-8"))
        check("the stuck black night: pic.json black + a settled vis",
              lore._pic_black(os.path.join(SH, "stuck.mp4")) is True
              and sv.get("complete") is True and sv.get("black") is True
              and not sv.get("failed"))
        check("a failed vis over a LIT file: pic.json black:false, the vis untouched",
              os.path.isfile(lore._ai_sidecar(os.path.join(SH, "dark.mp4"), "pic"))
              and lore._pic_black(os.path.join(SH, "dark.mp4")) is False
              and os.path.getmtime(dark_vp) == dark_m
              and json.load(io.open(dark_vp, encoding="utf-8")).get("failed"))
        check("a complete vis is not probed at all",
              not os.path.isfile(lore._ai_sidecar(os.path.join(SH, "fine.mp4"),
                                                  "pic")))
        check("a clip too short for a verdict is skipped without owing the walk",
              not os.path.isfile(lore._ai_sidecar(os.path.join(SH, "tiny.mp4"),
                                                  "pic"))
              and lore._MIG_SKIPPED[0] == 0)
        stuck_vp = lore._ai_sidecar(os.path.join(SH, "stuck.mp4"), "vis")
        sm = os.path.getmtime(stuck_vp)
        time.sleep(0.05)
        lore._black_vis_migration()
        check("the walk is idempotent - a second boot writes nothing",
              os.path.getmtime(stuck_vp) == sm)
    finally:
        lore._library_dirs, lore._scan_dir_mp4s = _ld, _sc

    # ---- visions() with the fact --------------------------------------
    print("\n--- the panel's contract ---")
    api = types.SimpleNamespace(_safe_path=lambda p: p)
    vns = {"_read_sidecar": lore._read_sidecar, "_pic_black": lore._pic_black,
           "_eye_places": lore._eye_places, "os": os, "json": json}
    visions = method("_JsApi", "visions", vns)
    v_black = visions(api, os.path.join(SH, "stuck.mp4"))
    check("visions(): a settled black vis -> black True, complete, nothing to see",
          v_black and v_black.get("black") is True
          and v_black.get("complete") is True and v_black.get("looks") == [])
    v_dark = visions(api, os.path.join(SH, "dark.mp4"))
    check("visions(): a failed vis over a lit file stays None (as today)",
          v_dark is None)
    # a failed vis beside a black fact (the walk has not run yet): the
    # fact wins, so the panel never says the eye failed on a black night
    lore._atomic_write_json(stuck_vp, dict(failed))
    v_pre = visions(api, os.path.join(SH, "stuck.mp4"))
    check("visions(): a failed vis beside a black pic.json -> black True",
          v_pre and v_pre.get("black") is True and v_pre.get("eye") is False)
    v_fine = visions(api, os.path.join(SH, "fine.mp4"))
    check("visions(): a lit night carries black False beside its looks",
          v_fine and v_fine.get("black") is False and len(v_fine["looks"]) == 1)
    lore.SETTINGS["output_dir"] = TD

# ---- the eye's honest message ------------------------------------------------
print("\n--- the eye's honest message ---")
gns = {"os": os, "subprocess": types.SimpleNamespace(
    CREATE_NO_WINDOW=0, BELOW_NORMAL_PRIORITY_CLASS=0),
    "_AI": {"abort": False}, "SETTINGS": {"ffmpeg_path": "ffmpeg"},
    "_work_dir": lambda: TD}


class _R:
    returncode = 0


def fake_run(cmd, **k):
    jp = cmd[-1]
    io.open(jp, "wb").write(b"\xff\xd8" + b"\0" * 2898)   # a 2,900-byte jpeg
    return _R()


gns["subprocess"].run = fake_run
_grab_frames = extract("_grab_frames", gns)
gst = {}
got = _grab_frames("x.mp4", [10.0, 70.0], stats=gst)
check("_grab_frames: a 2,900-byte jpeg falls under the floor and is COUNTED",
      got == [] and gst.get("small") == 2)
check("...the count is optional (the describer's call passes none)",
      _grab_frames("x.mp4", [10.0]) == [])
ei = ey.index("gst = {}")
check("_eyes_one reads that count into the skip reason",
      "stats=gst)" in ey and ey.index("if gst.get(\"small\")", ei) > ei)

# ---- the page -------------------------------------------------------------------
print("\n--- the page ---")
ps = USRC[USRC.index("function paintSeen()"):USRC.index("async function renderHlMarks")]
check("paintSeen: the black line comes first in the empty branch",
      "if(vis.black){" in ps
      and ps.index("if(vis.black){")
      < ps.index("the eye looked and found nothing it could name"))
check("...says what it is, and returns before the invitation to look",
      "the picture of this one is black" in ps
      and ps.index("return;", ps.index("if(vis.black){"))
      < ps.index("the eye looked and found nothing"))
check("...the signature moves with the fact, #vsaw stays unlit (black never "
      "joins any; 3.32's outcomes do)",
      "(vis.black?'black':'')" in ps
      and "const any=!!(places.length||crs.length||looks.length||scr.length\n"
          "    ||outs.length);" in ps
      and "black" not in ps[ps.index("const any="):ps.index("const any=") + 90])
check("the MOCK visions know 'black' (and #black paints the one-line night)",
      "black:false," in USRC and "black:true,eye:false" in USRC
      and "location.hash.includes('black')" in USRC)
check("still one <script> block, no new inline '</script'",
      USRC.count("</script") == 1)

# ---- the shelf, read-only, only when the file is there ----------------------------
print("\n--- the shelf replay (read-only) ---")
RL = r"D:\Records\Rocket League\Videos\rocketleague_20260820_233433.mp4"
RL_OK = r"D:\Records\Rocket League\Videos\rocketleague_20260830_214752.mp4"
if os.path.isfile(RL) and os.path.isfile(RL_OK):
    b, lu, mx, sc = lore._picture_probe(RL)
    check("the 20 Aug night probes black: lumas all 0, maxes all 0",
          b is True and all(x == 0 for x in lu) and all(x == 0 for x in mx))
    b2, lu2, mx2, sc2 = lore._picture_probe(RL_OK)
    check("the 30 Aug night probes lit", b2 is False and max(mx2) > 16)
else:
    print("      (the 20/30 Aug files are not on the shelf - replay skipped)")

try:
    shutil.rmtree(TD, ignore_errors=True)
except Exception:
    pass
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

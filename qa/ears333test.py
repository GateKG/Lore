# -*- coding: utf-8 -*-
"""3.33 drop E - THE SECOND EAR, proven.

Whisper turbo on the CPU drafts every ROOM utterance in English and the
reader (Qwen3-ASR) leans on that draft through its context. These lift
the REAL functions out of ai/asr_worker.py and lore.py by name and drive
them against a FAKE whisper-server (a tiny http.server on a free port
answering /inference from a table keyed on the wav's sample count):
the clean draft passes; "Thank you.", a language nobody here speaks, a
low mean word probability, a looping 3-gram and a foreign alphabet are
junk; a timeout is ""; the counts. Then the source pins (READER 7, the
echo tests compare against `base`, the room writer files "d" and the
media/game writers never do), the DORMANT PARITY diff of _read against
HEAD, the app's side (_whisper_paths, _WhisperServer with a fake
process, the room's names, the reader's context byte-identical to
HEAD's without names, the seed from room_names.txt on a tempdir, the
_transcribe_one pins, the stamps and the settings rows). Names in these
tests are Wanderer / Faris / Marid - never a real person. Nothing under
D:\\Records is touched; no port in 8906-8912 is spoken to."""
import ast
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import types
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WSRC = io.open(os.path.join(ROOT, "ai", "asr_worker.py"),
               encoding="utf-8").read()
LSRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
USRC = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()
WTREE = ast.parse(WSRC)
LTREE = ast.parse(LSRC)
OK = FAIL = 0


def check(what, cond):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("FAIL:", what)


def node_of(tree, name, kinds=(ast.FunctionDef, ast.ClassDef)):
    for node in ast.walk(tree):
        if isinstance(node, kinds) and node.name == name:
            return node
    raise KeyError(name)


def seg(src, tree, name):
    return textwrap.dedent(ast.get_source_segment(src, node_of(tree, name)))


def extract(src, tree, name, ns):
    exec(compile(seg(src, tree, name), "<" + name + ">", "exec"), ns)
    return ns[name]


def lift_assign(src, tree, name, ns):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tg in node.targets:
                if isinstance(tg, ast.Name) and tg.id == name:
                    exec(compile(ast.get_source_segment(src, node),
                                 "<" + name + ">", "exec"), ns)
                    return ns[name]
    raise KeyError(name)


def head_of(rel):
    return subprocess.run(["git", "show", "HEAD:" + rel], cwd=ROOT,
                          capture_output=True).stdout.decode("utf-8")


# =========================================================================
print("--- T1: the fake whisper-server ---")
# a fake soundfile: 44 header bytes + 2 per sample, so the wav's byte
# length names the utterance and the table answers by sample count
def _fake_write(buf, audio, sr, format=None, subtype=None):
    buf.write(b"RIFF" + b"\0" * 40 + b"\0\0" * len(audio))


sys.modules["soundfile"] = types.SimpleNamespace(write=_fake_write)

SEEN = []
TABLE = {
    16000: {"language": "english", "duration": 1.0,
            "text": " We just entered the duos Hearthstone match.",
            "segments": [{"text": " We just entered the",
                          "words": [{"word": "We", "probability": 0.9},
                                    {"word": "just", "probability": 0.8}]},
                         {"text": "  duos   Hearthstone match. ",
                          "words": [{"word": "duos", "probability": 0.7}]}]},
    32000: {"language": "english", "text": " Thank you.",
            "segments": [{"text": " Thank you."}]},
    48000: {"language": "hindi", "text": "yeh ek line hai",
            "segments": [{"text": "yeh ek line hai"}]},
    64000: {"language": "english", "text": "eight gold so not ready",
            "segments": [{"text": "eight gold so not ready",
                          "words": [{"word": "eight", "probability": 0.2},
                                    {"word": "gold", "probability": 0.4},
                                    {"word": "so", "probability": 0.3}]}]},
    80000: {"language": "english", "text": "loop",
            "segments": [{"text": "I got wild gun I got wild gun I got "
                                  "wild gun yes"}]},
    96000: "SLEEP",
    112000: {"language": "english", "text": "x",
             "segments": [{"text": "\u4f60\u597d\u4e16\u754c\u4f60\u597d"}]},
    128000: {"language": "arabic", "text": "ok",
             "segments": [{"text": " \u0623\u062e\u0648\u064a \u0645\u0627 "
                                   "\u0639\u0644\u064a\u0643 MMR"}]},
}


class FakeWhisper(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        body = b"whisper.cpp server"
        self.send_response(200)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n)
        ctype = self.headers.get("content-type") or ""
        bnd = ctype.split("boundary=")[-1].encode("ascii")
        fields, wav = {}, b""
        for part in body.split(b"--" + bnd):
            if b"\r\n\r\n" not in part:
                continue
            hd, val = part.split(b"\r\n\r\n", 1)
            val = val[:-2] if val.endswith(b"\r\n") else val
            m = re.search(rb'name="([^"]+)"', hd)
            if not m:
                continue
            if m.group(1) == b"file":
                wav = val
            else:
                fields[m.group(1).decode()] = val.decode("utf-8")
        samples = (len(wav) - 44) // 2
        SEEN.append((self.path, dict(fields), samples))
        ans = TABLE.get(samples, {"language": "english", "text": "?",
                                  "segments": [{"text": "?"}]})
        if ans == "SLEEP":
            time.sleep(4)
            ans = {"language": "english", "text": "late",
                   "segments": [{"text": "late"}]}
        out = json.dumps(ans).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        try:
            self.wfile.write(out)
        except OSError:
            pass            # the timed-out client is gone; that is the test


_s = socket.socket()
_s.bind(("127.0.0.1", 0))
FAKE_PORT = _s.getsockname()[1]
_s.close()
assert not (8906 <= FAKE_PORT <= 8912)
httpd = HTTPServer(("127.0.0.1", FAKE_PORT), FakeWhisper)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
check("the fake whisper is up on a free port outside 8906-8912",
      FAKE_PORT > 0 and not (8906 <= FAKE_PORT <= 8912))

# =========================================================================
print("--- T2: _draft, lifted, against the fake ---")
WNS = {"io": io, "re": re, "json": json, "time": time, "os": os,
       "urllib": urllib, "socket": socket, "threading": threading,
       "DRAFT_SERVER": "http://127.0.0.1:%d" % FAKE_PORT,
       "DRAFT_THREADS": 10}
for nm in ("_DRAFT_JUNK", "_DRAFT_TAG", "_CTX_STOP", "DRAFT_WINDOW_S",
           "DRAFT_PAD_S", "DRAFT_LOGPROB", "DRAFT_DEAD"):
    lift_assign(WSRC, WTREE, nm, WNS)
for nm in ("_foreign", "_ctx_echo", "_draft_timeout", "_is_timeout",
           "_echo_base", "_draft_echo", "_draft_judge", "_draft_post",
           "_draft_many", "_draft_pack", "_Drafter"):
    extract(WSRC, WTREE, nm, WNS)
_draft = WNS["_draft"] = extract(WSRC, WTREE, "_draft", WNS)
_draft_many = WNS["_draft_many"]
stats = {"draft_ask": 0, "draft_junk": 0, "draft_ok": 0}


def counts(st):
    """the three the spec named, so the old checks read as written"""
    return {k: st.get(k, 0) for k in ("draft_ask", "draft_junk", "draft_ok")}



got = _draft([0.0] * 16000, 16000, "Hearthstone. Friends on Discord: "
                                   "Wanderer, Faris. Alt-F4, MMR.", stats)
check("a clean english reply passes, segments joined, whitespace "
      "collapsed", got == "We just entered the duos Hearthstone match.")
p, f, n = SEEN[-1]
check("POST /inference, multipart, the contract's fields",
      p == "/inference" and f.get("response_format") == "verbose_json"
      and f.get("temperature") == "0" and f.get("language") == "auto"
      and f.get("prompt") == "Hearthstone. Friends on Discord: Wanderer, "
                             "Faris. Alt-F4, MMR." and n == 16000)
check("'Thank you.' is junk", _draft([0.0] * 32000, 16000, "", stats) == "")
check("a hindi `language` is junk",
      _draft([0.0] * 48000, 16000, "", stats) == "")
check("a mean word probability under 0.35 is junk",
      _draft([0.0] * 64000, 16000, "", stats) == "")
check("a 3-gram said three times is junk (the 'I got wild gun' loop)",
      _draft([0.0] * 80000, 16000, "", stats) == "")
check("a foreign alphabet is junk",
      _draft([0.0] * 112000, 16000, "", stats) == "")
check("an arabic reply with a game word passes",
      _draft([0.0] * 128000, 16000, "", stats)
      == "\u0623\u062e\u0648\u064a \u0645\u0627 \u0639\u0644\u064a\u0643 MMR")
check("stats: asked 7, ok 2, junk 5 (and 7 windows)",
      counts(stats) == {"draft_ask": 7, "draft_junk": 5, "draft_ok": 2}
      and stats.get("draft_win") == 7)
# the timeout: the lifted urlopen is held to 1.5 s (the real call scales
# with the ear's threads - see T10)
real_urlopen = urllib.request.urlopen
WNS["urllib"] = types.SimpleNamespace(request=types.SimpleNamespace(
    Request=urllib.request.Request,
    urlopen=lambda req, timeout=60: real_urlopen(req, timeout=1.5)))
t0 = time.time()
got = _draft([0.0] * 96000, 16000, "", stats)
check("a timeout returns '' and never raises",
      got == "" and time.time() - t0 < 10)
check("a timeout is asked, not junk - and COUNTED as a timeout",
      counts(stats) == {"draft_ask": 8, "draft_junk": 5, "draft_ok": 2}
      and stats.get("draft_timeout") == 1)
WNS["DRAFT_SERVER"] = "http://127.0.0.1:1"
check("a dead server returns ''", _draft([0.0] * 16000, 16000, "") == "")
check("_draft without a stats dict counts nothing and still answers",
      counts(stats) == {"draft_ask": 8, "draft_junk": 5, "draft_ok": 2})
WNS["DRAFT_SERVER"] = "http://127.0.0.1:%d" % FAKE_PORT
WNS["urllib"] = urllib
check("the draft is cut at 400 characters",
      len(_draft([0.0] * 16000, 16000, "x" * 10)) <= 400)
check("the junk pattern: thanks for watching / you / bye / subscribe",
      all(WNS["_DRAFT_JUNK"].match(t) for t in
          ("Thank you.", " thanks for watching ", "You", "Bye!",
           "Please subscribe to my channel", "Subscribe.")))
check("the junk pattern leaves speech alone",
      not any(WNS["_DRAFT_JUNK"].match(t) for t in
              ("Thank you for the triple", "you made me lose", "bye bye",
               "okay so we go left", "thanks for the save man")))

# =========================================================================
print("--- T3: the worker's source pins ---")
check("READER = 7", re.search(r"^READER\s*=\s*7\b", WSRC, re.M) is not None)
check("DRAFT_SERVER / DRAFT_PROMPT come from the environment",
      'DRAFT_SERVER = os.environ.get("LORE_ASR_WHISPER") or ""' in WSRC
      and 'DRAFT_PROMPT = os.environ.get("LORE_ASR_DRAFT_PROMPT") or ""'
      in WSRC)
rd = node_of(WTREE, "_read")
rsrc = ast.get_source_segment(WSRC, rd)
check("_read binds base = cur_ctx[0] at entry",
      re.search(r"^\s+base = cur_ctx\[0\]", rsrc, re.M) is not None)
check("_read takes the draft only for the room, only with a server, "
      "BY INDEX from the room loop - never a POST of its own",
      "if walls and DRAFT_SERVER:" in rsrc
      and 'd, next_draft[0] = next_draft[0], ""' in rsrc
      and "_draft(" not in rsrc and "_draft_many(" not in rsrc)
check("_read binds ectx = _echo_base(base) - the names clause out of "
      "the echo tests",
      re.search(r"^\s+ectx = _echo_base\(base\)", rsrc, re.M) is not None)
check("the draft is appended to the context in the spec's words",
      "A first pass by another ear " in rsrc
      and 'heard, in English: "' in rsrc)
fin = [n for n in ast.walk(rd) if isinstance(n, ast.Try) and n.finalbody]
check("_read restores cur_ctx[0] = base in a finally",
      len(fin) == 1 and "cur_ctx[0] = base" in
      "\n".join(ast.get_source_segment(WSRC, x) for x in fin[0].finalbody))
echoes = [n for n in ast.walk(rd) if isinstance(n, ast.Call)
          and isinstance(n.func, ast.Name) and n.func.id == "_ctx_echo"]
check("every _ctx_echo( inside _read takes ectx (2 of them)",
      len(echoes) == 2 and all(isinstance(c.args[1], ast.Name)
                               and c.args[1].id == "ectx" for c in echoes))
check("no _ctx_echo inside _read reads the widened cur_ctx or bare base",
      "_ctx_echo(txt, ctx)" not in rsrc and "_ctx_echo(t2, ctx)" not in rsrc
      and "_ctx_echo(txt, base)" not in rsrc
      and "_ctx_echo(t2, base)" not in rsrc
      and "cur_ctx[0])" not in rsrc.replace("base = cur_ctx[0]", ""))
check("the room loop hands the draft in before _read, from the drafter",
      re.search(r"if drafter is not None:\s*\n\s+next_draft\[0\] = "
                r"drafter\.get\(i\)[^\n]*\n\s+txt, lang, lost = "
                r"_read\(audio, True,", WSRC) is not None)
check("the drafter wakes only with a server and only for the room's groups, "
      "ahead of the reader on the card (USE_GGUF), on the app's gate",
      re.search(r"if DRAFT_SERVER and groups:\s*\n\s+drafter = _Drafter\("
                r"[\s\S]{0,300}stats, wanted_ear2, bool\(USE_GGUF\), notes\)",
                WSRC) is not None)
check("the room writer files the draft as \"d\", cut at 300",
      'sg_new["d"] = last_draft[0][:300]' in WSRC)
mn = node_of(WTREE, "main")
writers = [n for n in ast.walk(mn) if isinstance(n, ast.Call)
           and isinstance(n.func, ast.Attribute) and n.func.attr == "append"
           and isinstance(n.func.value, ast.Name) and n.func.value.id == "out"
           and n.args and isinstance(n.args[0], ast.Dict)]
srcw = [w for w in writers
        if any(isinstance(k, ast.Constant) and k.value == "why"
               for k in w.args[0].keys)]
check("the media/game writer (the one with 'why') carries no \"d\"",
      len(srcw) == 1 and not any(isinstance(k, ast.Constant)
                                 and k.value == "d"
                                 for k in srcw[0].args[0].keys))
check("stats initialise draft_ask / junk / ok + win / skip / timeout",
      '"draft_ask": 0, "draft_junk": 0, "draft_ok": 0,' in WSRC
      and '"draft_win": 0, "draft_skip": 0, "draft_timeout": 0}' in WSRC)
check("the sources block carries draft_ok / junk / skip / timeout",
      '"draft_ok": int(stats.get("draft_ok", 0))' in WSRC
      and '"draft_junk": int(stats.get("draft_junk", 0))' in WSRC
      and '"draft_skip": int(stats.get("draft_skip", 0))' in WSRC
      and '"draft_timeout": int(stats.get("draft_timeout", 0))' in WSRC)
check("the note goes through the notes road, only with a server, and "
      "says the windows, the timeouts and the skips",
      re.search(r"if DRAFT_SERVER:\s*\n(?:\s*#.*\n)*\s*notes\.append\("
                r"\"the second ear drafted %d of %d room utterance\(s\) \"",
                WSRC) is not None
      and "%d window(s), %d timed out; %d not asked " in WSRC
      and 'stats["draft_timeout"], stats["draft_skip"]))' in WSRC)
# the sources block, run
SNS = {}
_sources_block = extract(WSRC, WTREE, "_sources_block", SNS)
sb = _sources_block(True, True, True, 1, 2, 3, 4, 5, 6, 7,
                    {"draft_ok": 3, "draft_junk": 1, "draft_skip": 4,
                     "draft_timeout": 2})
check("_sources_block writes the four counts",
      sb.get("draft_ok") == 3 and sb.get("draft_junk") == 1
      and sb.get("draft_skip") == 4 and sb.get("draft_timeout") == 2)

# =========================================================================
print("--- T4: DORMANT PARITY - _read against HEAD ---")
HSRC = head_of("ai/asr_worker.py")
HTREE = ast.parse(HSRC)
for nm in ("_ctx_echo", "_foreign", "_impossible", "_arabizi"):
    check(nm + " is byte-identical to HEAD's",
          seg(HSRC, HTREE, nm) == seg(WSRC, WTREE, nm))
old = [ln.strip() for ln in seg(HSRC, HTREE, "_read").splitlines()]
new = [ln.strip() for ln in seg(WSRC, WTREE, "_read").splitlines()]
# BY POSITION, not by text: the added block is everything between
# `nonlocal last` and the first `try:`, and the finally is the last two
# lines - so a `try:` the old body already had (the English wall's) is
# never mistaken for the new one
i_nl = new.index("nonlocal last")
i_try = new.index("try:", i_nl)
check("the added head opens with base = cur_ctx[0] and ends at try:",
      new[i_nl + 1].startswith("base = cur_ctx[0]")
      and "if walls and DRAFT_SERVER:" in new[i_nl + 1:i_try]
      and new[-2:] == ["finally:", "cur_ctx[0] = base"])
new_core = new[:i_nl + 1] + new[i_try + 1:-2]
old_core = [ln for ln in old
            if ln != "ctx = cur_ctx[0]         # the context THIS pass is sending"]
if "nonlocal last" in old and old[old.index("nonlocal last") + 1] \
        .startswith("base = cur_ctx[0]"):
    # drop E is COMMITTED: HEAD carries the added head and the finally
    # too, so the same block is stripped from both sides (3.33 F)
    o_nl = old.index("nonlocal last")
    o_try = old.index("try:", o_nl)
    old_core = old[:o_nl + 1] + old[o_try + 1:-2]
old_core = [ln.replace("or (ctx and _ctx_echo(t2, ctx)))",
                       "or (ectx and _ctx_echo(t2, ectx)))")
            .replace("if txt and ctx and _ctx_echo(txt, ctx):",
                     "if txt and ectx and _ctx_echo(txt, ectx):")
            for ln in old_core]
check("_read's body is HEAD's, modulo the base / draft / finally lines "
      "(%d vs %d lines)" % (len(old_core), len(new_core)),
      old_core == new_core)
if old_core != new_core:
    for a, b in zip(old_core, new_core):
        if a != b:
            print("   first difference:\n    HEAD:", a, "\n    tree:", b)
            break
check("HEAD's _read had exactly the two echo calls the tree has",
      seg(HSRC, HTREE, "_read").count("_ctx_echo(") == 2)
check("with LORE_ASR_WHISPER unset nothing drafts: the drafter is built "
      "only under `if DRAFT_SERVER and groups`, _draft_many is called only "
      "by _draft and the drafter, _draft only by what lifts it",
      WSRC.count("_Drafter(") == 1 and WSRC.count("_draft_many(") == 3
      and len(re.findall(r"\b_draft\(", WSRC)) == 1)   # the def alone
check("the room writer's \"d\" sits under `if last_draft[0]:`",
      re.search(r"if last_draft\[0\]:\s*\n(?:\s*#.*\n)*\s*sg_new\[\"d\"\]",
                WSRC) is not None)

# =========================================================================
print("--- T5: _whisper_paths / _WhisperServer ---")
tmp = tempfile.mkdtemp(prefix="lore_ear_")
app = os.path.join(tmp, "app")
models = os.path.join(tmp, "models")
os.makedirs(os.path.join(app, "ai", "whisper"))
os.makedirs(os.path.join(models, "whisper"))
PNS = {"os": os, "_here": lambda: app,
       "_model_file": lambda *p: os.path.join(models, *p)}
_whisper_paths = extract(LSRC, LTREE, "_whisper_paths", PNS)
check("no exe, no model -> None", _whisper_paths() is None)
exe = os.path.join(app, "ai", "whisper", "whisper-server.exe")
io.open(exe, "wb").write(b"MZ")
check("the exe alone -> None", _whisper_paths() is None)
mdl = os.path.join(models, "whisper", "ggml-large-v3-turbo-q5_0.bin")
io.open(mdl, "wb").write(b"lmgg")
check("exe under ai\\whisper + model under models\\whisper -> both",
      _whisper_paths() == (exe, mdl))
check("_WHISPER_PORT = 8911",
      re.search(r"^_WHISPER_PORT\s*=\s*8911\s*$", LSRC, re.M) is not None)


class FakeProc:
    def __init__(self):
        self.killed = self.terminated = False
        self.rc = None

    def poll(self):
        return self.rc

    def terminate(self):
        self.terminated = True
        self.rc = 0

    def wait(self, timeout=None):
        return self.rc

    def kill(self):
        self.killed = True
        self.rc = -9


SPAWNS, FREED, LOGS = [], [], []


def fake_popen(cmd, **kw):
    SPAWNS.append((list(cmd), dict(kw)))
    pr = FakeProc()
    SPAWNS[-1][1]["pr"] = pr
    return pr


SNS2 = {"os": os, "subprocess": subprocess, "time": time,
        "_AI": {"abort": False, "proc": None},
        "log": LOGS.append, "_free_port": FREED.append,
        "_popen": fake_popen, "_whisper_paths": lambda: (exe, mdl),
        "_DESC_PORT": 8906, "_WHISPER_PORT": 8911,
        "_describer_paths": lambda: None,
        "_desc_mmproj": lambda: None, "_DESC_CTX": 4096}
extract(LSRC, LTREE, "_DescServer", SNS2)
_WhisperServer = extract(LSRC, LTREE, "_WhisperServer", SNS2)
URL = {"mode": "refuse"}


def fake_urlopen(url, timeout=None, **kw):
    if URL["mode"] == "404":
        raise urllib.error.HTTPError(url, 404, "nf", {}, None)
    if URL["mode"] == "ok":
        return io.BytesIO(b"whisper.cpp")
    raise urllib.error.URLError("refused")


urllib.request.urlopen = fake_urlopen
try:
    ws = _WhisperServer()
    URL["mode"] = "ok"
    up = ws.start(3)
    cmd, kw = SPAWNS[-1][0], SPAWNS[-1][1]
    check("start() spawns and answers True on a 200 from /", up is True)
    check("the command: exe -m model --host 127.0.0.1 --port 8911 -t 3 "
          "-l auto, nothing else",
          cmd == [exe, "-m", mdl, "--host", "127.0.0.1", "--port", "8911",
                  "-t", "3", "-l", "auto"])
    check("no -ngl anywhere (the card is never touched)",
          "-ngl" not in cmd and "--gpu" not in " ".join(cmd))
    check("BELOW_NORMAL + CREATE_NO_WINDOW",
          kw.get("creationflags", 0) & subprocess.BELOW_NORMAL_PRIORITY_CLASS
          and kw.get("creationflags", 0) & subprocess.CREATE_NO_WINDOW)
    check("_free_port etiquette on 8911", FREED == [8911])
    check("never _AI['proc']", SNS2["_AI"]["proc"] is None)
    ws.stop()
    check("stop() terminates the child",
          kw["pr"].terminated and ws.pr is None)
    URL["mode"] = "404"
    ws2 = _WhisperServer()
    check("any HTTP status counts as alive (a 404 from /)",
          ws2.start(2) is True and SPAWNS[-1][0][7:9] == ["-t", "2"])
    ws2.stop()
    URL["mode"] = "refuse"
    ws3 = _WhisperServer()
    t0 = time.time()
    check("the budget is respected: no answer -> False, child stopped",
          ws3.start(2, budget=1.2) is False
          and 1.0 <= time.time() - t0 < 6 and SPAWNS[-1][1]["pr"].terminated)
    SNS2["_AI"]["abort"] = True
    ws4 = _WhisperServer()
    check("an abort mid-start stops it", ws4.start(2) is False
          and SPAWNS[-1][1]["pr"].terminated)
    SNS2["_AI"]["abort"] = False
    SNS2["_whisper_paths"] = lambda: None
    check("no paths -> False without a spawn",
          _WhisperServer().start(2) is False and len(SPAWNS) == 4)
finally:
    urllib.request.urlopen = real_urlopen

# =========================================================================
print("--- T6: the room's names ---")
RNS = {"os": os, "re": re, "SETTINGS": {}, "_display_name": lambda x: x,
       "_parse_clip_name": lambda x: "Recording"}
for nm in ("_room_names_clamp", "_room_names", "_room_aliases_of",
           "_asr_game_name", "_draft_prompt_for", "_asr_context_for",
           "_seed_room_names"):
    extract(LSRC, LTREE, nm, RNS)
RNS["SETTINGS"]["room_names"] = "Wanderer, Faris / Fares, Marid / \u0645\u0627\u0631\u062f / Mar"
check("'A, B / Bee' -> [['A'], ['B', 'Bee']] (an Arabic alias kept)",
      RNS["_room_names"]() == [["Wanderer"], ["Faris", "Fares"],
                               ["Marid", "\u0645\u0627\u0631\u062f", "Mar"]])
RNS["SETTINGS"]["room_names"] = " Wanderer ,, Faris/Fares ,\u060cMarid "
check("spaces, doubled commas and the Arabic comma are forgiven",
      RNS["_room_names"]() == [["Wanderer"], ["Faris", "Fares"], ["Marid"]])
RNS["SETTINGS"]["room_names"] = ""
check("empty -> []", RNS["_room_names"]() == [])
RNS["SETTINGS"]["room_names"] = ", ".join("N%03d" % i for i in range(200))
check("the 600-character clamp holds in the parser too",
      sum(len(a) + 2 for p in RNS["_room_names"]() for a in p) <= 606)
RNS["SETTINGS"]["room_names"] = "Wanderer, Faris / Fares / \u0641\u0627\u0631\u0633, Marid"
check("_room_aliases_of gives the OTHER spellings, case-blind",
      RNS["_room_aliases_of"]("fares") == ["Faris", "\u0641\u0627\u0631\u0633"]
      and RNS["_room_aliases_of"]("Wanderer") == []
      and RNS["_room_aliases_of"]("Nobody") == [])
shelf = os.path.join(tmp, "Hearthstone", "Videos", "hearthstone_x.mp4")
loose = os.path.join(tmp, "loose", "x.mp4")
check("_draft_prompt_for: the game, the first spelling of each person, "
      "the words Whisper mishears",
      RNS["_draft_prompt_for"](shelf) == "Hearthstone. Friends on Discord: "
      "Wanderer, Faris, Marid. Alt-F4, MMR, duos, tavern, triple, GG.")
RNS["SETTINGS"]["room_names"] = ""
check("_draft_prompt_for without names or a shelf still names the words",
      RNS["_draft_prompt_for"](loose)
      == "Friends on Discord. Alt-F4, MMR, duos, tavern, triple, GG.")
check("_draft_prompt_for stays short (Whisper's ~224-token cap)",
      len(RNS["_draft_prompt_for"](shelf)) < 200)
HL = head_of("lore.py")
HLT = ast.parse(HL)
HNS = {"os": os, "_display_name": lambda x: x,
       "_parse_clip_name": lambda x: "Recording"}
extract(HL, HLT, "_asr_context_for", HNS)
check("_asr_context_for WITHOUT names is byte-identical to HEAD's "
      "(shelf + loose)",
      RNS["_asr_context_for"](shelf) == HNS["_asr_context_for"](shelf)
      and RNS["_asr_context_for"](loose) == HNS["_asr_context_for"](loose))
RNS["SETTINGS"]["room_names"] = "Wanderer, Faris / \u0641\u0627\u0631\u0633"
check("_asr_context_for WITH names appends every alias after HEAD's text",
      RNS["_asr_context_for"](shelf) == HNS["_asr_context_for"](shelf)
      + " Names in the room: Wanderer, Faris, \u0641\u0627\u0631\u0633.")
# the reader's echo test must not see the names as the prompt talking
ENS = {"re": re}
lift_assign(WSRC, WTREE, "_CTX_STOP", ENS)
ctx_echo = extract(WSRC, WTREE, "_ctx_echo", ENS)
check("a callout with a friend's name is not an echo of the widened context",
      ctx_echo("Faris come here, come on, we need the sniper now",
               RNS["_asr_context_for"](shelf)) is False)

# =========================================================================
print("--- T7: _seed_room_names on a tempdir ---")
data = os.path.join(tmp, "data")
os.makedirs(data)
SAVED, SLOG = [], []
RNS.update({"_data_dir": lambda: data, "save_settings": SAVED.append,
            "log": SLOG.append})
RNS["SETTINGS"] = {"room_names": ""}
check("no file -> untouched, nothing saved",
      RNS["_seed_room_names"]() is False and RNS["SETTINGS"]["room_names"] == ""
      and not SAVED)
io.open(os.path.join(data, "room_names.txt"), "w", encoding="utf-8").write(
    "\ufeffWanderer\n# a comment\nFaris / \u0641\u0627\u0631\u0633\n\n"
    "Marid/Mar, Id\n")
check("empty setting + file -> seeded, saved, logged with the count "
      "(a comma on a line is a person boundary, as in the setting)",
      RNS["_seed_room_names"]() is True
      and RNS["SETTINGS"]["room_names"]
      == "Wanderer, Faris / \u0641\u0627\u0631\u0633, Marid / Mar, Id"
      and len(SAVED) == 1 and SAVED[0] is RNS["SETTINGS"]
      and any("room_names.txt: 4 people" in m for m in SLOG))
RNS["SETTINGS"] = {"room_names": "Wanderer"}
del SAVED[:]
check("a filled setting is never touched by the file",
      RNS["_seed_room_names"]() is False
      and RNS["SETTINGS"]["room_names"] == "Wanderer" and not SAVED)
check("boot seeds right after the settings load",
      re.search(r"^    load_settings\(\)\n    _seed_room_names\(\)",
                LSRC, re.M) is not None)

# =========================================================================
print("--- T8: the settings, _transcribe_one, the auditor, the manifest ---")
check("DEFAULTS: second_ear True, room_names ''",
      re.search(r'^    "second_ear":\s+True,', LSRC, re.M) is not None
      and re.search(r'^    "room_names":\s+"",', LSRC, re.M) is not None)
check("the clamp: a bool and _room_names_clamp (<= 600, at a boundary)",
      'd["second_ear"] = bool(d.get("second_ear", DEFAULTS["second_ear"]))'
      in LSRC and 'd["room_names"] = _room_names_clamp(' in LSRC
      and '[:600].strip()' not in LSRC)
check("state() carries both", '"second_ear": bool(SETTINGS.get("second_ear", '
      'True)),' in LSRC and '"room_names": str(SETTINGS.get("room_names") or '
      '""),' in LSRC)
tsrc = seg(LSRC, LTREE, "_transcribe_one")
check("_transcribe_one gates on SETTINGS second_ear (default on)",
      'if SETTINGS.get("second_ear", True) and not _AI["abort"]:' in tsrc)
check("it wakes _WhisperServer with half the reader's IDLE threads, "
      "floor 2 - never this moment's count",
      "_wt = max(2, _reader_threads(False) // 2)" in tsrc
      and "_reader_threads() // 2" not in tsrc
      and "wsrv = _WhisperServer()" in tsrc and "wsrv.start(_wt)" in tsrc)
check("the env keys: LORE_ASR_WHISPER + LORE_ASR_DRAFT_PROMPT via "
      "_draft_prompt_for(video_path) + LORE_ASR_WHISPER_THREADS",
      'env["LORE_ASR_WHISPER"]' in tsrc and 'env["LORE_ASR_DRAFT_PROMPT"]'
      in tsrc and "_draft_prompt_for(video_path)" in tsrc
      and 'env["LORE_ASR_WHISPER_THREADS"] = str(_wt)' in tsrc)
check("a missing ai\\whisper is said once per launch, with the toggle on",
      re.search(r"if _wp is None:\s*\n(?:\s*#.*\n)*\s*if not _AI\.get\("
                r"\"ear2_missing_said\"\):\s*\n\s*_AI\[\"ear2_missing_said\"\]"
                r" = True\s*\n\s*log\(\"The second ear is not installed "
                r"\(ai\\\\whisper\) - \"", tsrc) is not None)
check("the two log lines, as specified",
      'log(f"The second ear is up: whisper turbo on the "' in tsrc
      and "CPU, {_wt} threads." in tsrc
      and tsrc.count("The second ear would not wake - reading") == 2)
tn = node_of(LTREE, "_transcribe_one")
fins = [n for n in ast.walk(tn) if isinstance(n, ast.Try) and n.finalbody
        and "asrv.stop()" in "\n".join(ast.get_source_segment(LSRC, x)
                                        for x in n.finalbody)]
fsrc = "\n".join(ast.get_source_segment(LSRC, x) for x in fins[0].finalbody) \
    if fins else ""
check("the same finally that stops the GPU reader stops the second ear",
      len(fins) == 1 and "wsrv.stop()" in fsrc
      and fsrc.index("asrv.stop()") < fsrc.index("wsrv.stop()"))
check("the second ear's start sits after the ASR road and before the "
      "worker's spawn",
      tsrc.index("The GPU reader would not start") < tsrc.index(
          "wsrv = _WhisperServer()") < tsrc.index('_AI["prog_file"] = prog_file'))
check("wsrv is declared beside asrv, before the try",
      re.search(r"^    asrv = None .*\n    wsrv = None ", tsrc, re.M)
      is not None)
check("_WhisperServer is a _DescServer (shares stop())",
      "class _WhisperServer(_DescServer):" in LSRC)
check("_STT_READER is 7 with the worker (3.33: the second ear changes every file, so the stale-reader law re-reads the shelf - his word, 6 Sep: archive and start from the beginning)",
      re.search(r"^_STT_READER = 7", LSRC, re.M) is not None and re.search(r"^_STT_READER_TRACKS = 7", LSRC, re.M) is not None)
# the manifest
MNS = {}
lift_assign(LSRC, LTREE, "_HF", MNS)
sets = lift_assign(LSRC, LTREE, "_MODEL_SETS", MNS)
keys = [it["key"] for it in sets]
ear2 = [it for it in sets if it["key"] == "ear2"]
check("_MODEL_SETS: ear2 right after the reader",
      keys.index("ear2") == keys.index("reader") + 1)
check("ear2: reader tier, dir whisper, the turbo q5_0 file, its bytes, "
      "its ggerganov url",
      ear2 and ear2[0]["tier"] == "reader" and ear2[0]["dir"] == "whisper"
      and ear2[0]["title"] == "The second ear"
      and ear2[0]["files"] == [("ggml-large-v3-turbo-q5_0.bin",
                                "https://huggingface.co/ggerganov/whisper.cpp/"
                                "resolve/main/ggml-large-v3-turbo-q5_0.bin",
                                574041195)])
# the auditor: the room's names fold
ANS = {"re": re, "os": os, "SETTINGS": {"room_names": "Wanderer / Wander, "
                                                     "Faris / Fares"}}
for nm in ("_room_names", "_room_aliases_of"):
    extract(LSRC, LTREE, nm, ANS)
ANS["_aud_people"] = lambda text, gamew, low: re.findall(r"[A-Z]\w+", text)
ANS["_aud_gamewords"] = lambda p: set()
ANS["_aud_lat"] = lambda w: w.lower()
ANS["_aud_skel"] = lambda w: ""
ANS["_aud_grounded"] = lambda nm, words, skels, spoken: (
    ("said", "said outright", "") if nm.lower() in words
    else ("", "nobody in this recording says this", ""))
_aud_names = extract(LSRC, LTREE, "_aud_names", ANS)
low = {"w%d" % i: 5 for i in range(300)}
stt = [{"t": "Wander come on, Marid is not here " * 3}]
rows, warn = _aud_names("x.mp4", {"title": "Wanderer Faris Marid"}, stt, low)
byname = {r["name"]: r for r in rows}
check("a name said under ANOTHER of the room's spellings is 'said', "
      "folded onto that spelling",
      byname["Wanderer"]["verdict"] == "said"
      and byname["Wanderer"].get("alias") == "Wander"
      and "one of the room's names" in byname["Wanderer"]["how"]
      and byname["Wanderer"]["said"] == "Wander")
check("a room name nobody says under any spelling stays unsaid",
      byname["Faris"]["verdict"] == "unsaid" and "alias" not in byname["Faris"])
check("a name said outright needs no fold",
      byname["Marid"]["verdict"] == "said" and "alias" not in byname["Marid"])
check("the unsaid warning names only Faris",
      len(warn) == 1 and "Faris" in warn[0])
check("the auditor adds the folded names to the merged list "
      "(the 'N name(s) folded' count)",
      re.search(r"names, nwarn = _aud_names\(video_path, ins, stt, _low\)"
                r"[\s\S]{0,400}merged\.append\(\{\"kept\": str\(_r\.get\("
                r"\"name\"\) or \"\"\)\[:70\],[\s\S]{0,120}"
                r"\"why\": \"the room's names\"", LSRC) is not None)

# =========================================================================
print("--- T9: the stamps and the settings page ---")
check("APP_VERSION 3.33", 'APP_VERSION = "3.33"' in LSRC)
check("ui.html version:'3.33' x2 and no 3.32 stamp left",
      USRC.count("version:'3.33'") == 2 and "version:'3.32'" not in USRC)
VT = io.open(os.path.join(ROOT, "version.txt"), encoding="utf-8").read()
check("version.txt (3, 33, 0, 0) x2 + '3.33.0.0' x2",
      VT.count("(3, 33, 0, 0)") == 2 and VT.count("'3.33.0.0'") == 2
      and "3, 32" not in VT and "3.32" not in VT)
ISS = io.open(os.path.join(ROOT, "installer.iss"), encoding="utf-8",
              errors="replace").read()
check("installer.iss AppVersion=3.33 / VersionInfoVersion=3.33.0",
      "AppVersion=3.33\n" in ISS.replace("\r\n", "\n")
      and "VersionInfoVersion=3.33.0\n" in ISS.replace("\r\n", "\n"))
check("the settings page: the second ear toggle with its note",
      "row(R,'The second ear',ctlToggle('second_ear')," in USRC
      and "about a minute of CPU for every minute of talk, never the card"
      in USRC and "20 minutes of CPU per hour" not in USRC)
check("the settings page: the room's names text row with the placeholder",
      "ctlText('room_names',true,'A, B / Bee, C / CC \\u2014 people by comma, "
      "other spellings by slash')" in USRC)
hi = USRC.index("row(R,'Your in-game name'")
check("both rows sit beside 'Your in-game name' (within the same page, "
      "before the Compatibility divider)",
      hi < USRC.index("ctlToggle('second_ear')")
      < USRC.index("ctlText('room_names'") < USRC.index(
          "divider(R,'Compatibility')"))
check("MOCK settings carry both", "second_ear:true,room_names:''," in USRC)
check("the MOCK state carries both",
      "librarian_ready:true,second_ear:true,room_names:'',version:'3.33'"
      in USRC)
# the tests' three names must never reach the code: only the lines this
# drop ADDS are judged (ui.html's own mock fixture says Marid since 3.2x)
added = "\n".join(
    ln[1:] for ln in subprocess.run(
        ["git", "diff", "-U0", "HEAD", "--", "lore.py", "ui.html",
         "ai/asr_worker.py"], cwd=ROOT, capture_output=True)
    .stdout.decode("utf-8", "replace").splitlines()
    if ln.startswith("+") and not ln.startswith("+++"))
check("no test name (Wanderer / Faris / Marid) in the lines this drop adds",
      not re.search(r"Wanderer|Faris|Marid", added))

# =========================================================================
print("--- T10: the windows - one POST per packed run, split by time ---")
WNS["DRAFT_SERVER"] = "http://127.0.0.1:%d" % FAKE_PORT
WNS["urllib"] = urllib
# two utterances (1 s + 2 s) and the 0.5 s pad between = 56000 samples:
# the fake answers with segments whose times straddle the boundary
TABLE[56000] = {"language": "english", "text": "x",
                "segments": [{"text": " Let's go.", "start": 0.0, "end": 0.9,
                              "avg_logprob": -0.2,
                              "words": [{"word": "go", "probability": 0.9}]},
                             {"text": " *BOOM*", "start": 0.9, "end": 1.6,
                              "avg_logprob": -1.5},
                             {"text": " You made me lose a MMR game.",
                              "start": 1.6, "end": 3.5, "avg_logprob": -0.3,
                              "words": [{"word": "MMR", "probability": 0.8}]}]}
del SEEN[:]
st = {}
got = _draft_many([[0.0] * 16000, [0.0] * 32000], 16000, "P", st)
check("ONE POST for two utterances, laid end to end with the pad "
      "(16000 + 8000 + 32000 samples)",
      len(SEEN) == 1 and SEEN[0][2] == 56000 and SEEN[0][1]["prompt"] == "P")
check("each utterance gets the segments that overlap it most - the "
      "boundary segment went where most of it lay",
      got == ["Let's go.", "You made me lose a MMR game."])
check("the *BOOM* under the logprob floor is dropped on its own, the "
      "utterance keeps the rest",
      "BOOM" not in got[0] and st == {"draft_ask": 2, "draft_win": 1,
                                       "draft_ok": 2})
check("DRAFT_WINDOW_S 30 / DRAFT_PAD_S 0.5 / DRAFT_LOGPROB -0.8 / DRAFT_DEAD 2",
      WNS["DRAFT_WINDOW_S"] == 30.0 and WNS["DRAFT_PAD_S"] == 0.5
      and WNS["DRAFT_LOGPROB"] == -0.8 and WNS["DRAFT_DEAD"] == 2)
pack = WNS["_draft_pack"]
sr = 16000
check("_draft_pack: 12 + 12 + 12 s -> [0, 1] and [2] (24.5 s fits, 37 does not)",
      pack([12 * sr, 12 * sr, 12 * sr], sr) == [[0, 1], [2]])
check("_draft_pack: a 28 s utterance is a window of its own; the ones the "
      "reader skips (< 0.4 s) are left out",
      pack([28 * sr, 3 * sr, 4000, 3 * sr, 27 * sr], sr)
      == [[0], [1, 3], [4]])
check("_draft_pack on last night's shape: 407 lines of 3.66 s mean pack "
      "into ~65 windows, not 407",
      50 <= len(pack([int(3.66 * sr)] * 407, sr)) <= 70)
check("_draft_timeout scales with the ear's threads: 10 -> ~102 s, "
      "4 -> 210, 3 -> 270; never the flat 60",
      WNS["_draft_timeout"]() == 102
      and (WNS.__setitem__("DRAFT_THREADS", 4) or WNS["_draft_timeout"]() == 210)
      and (WNS.__setitem__("DRAFT_THREADS", 3) or WNS["_draft_timeout"]() == 270)
      and (WNS.__setitem__("DRAFT_THREADS", 10) or True))
check("the app's thread count reaches the worker as LORE_ASR_WHISPER_THREADS",
      'DRAFT_THREADS = int(os.environ.get("LORE_ASR_WHISPER_THREADS") or 0)'
      in WSRC)
check("_draft_post sends the timeout it was given",
      "urllib.request.urlopen(req, timeout=timeout)" in WSRC
      and "timeout=60" not in seg(WSRC, WTREE, "_draft_post"))
# the drafter: ahead of the reader, on the app's gate
GATE = {"on": True}
AUD = {0: [0.0] * 16000, 1: [0.0] * 32000, 2: [0.0] * 16000, 3: [0.0] * 32000}
# four utterances + three pads = 120000 samples; the fake's segments sit
# at 0-1 / 1.5-3.5 / 4-5 / 5.5-7.5 s, one per utterance
TABLE[120000] = {"language": "english", "text": "x", "segments": [
    {"text": " Let's go.", "start": 0.0, "end": 0.9, "avg_logprob": -0.2},
    {"text": " You made me lose a MMR game.", "start": 1.6, "end": 3.4,
     "avg_logprob": -0.3},
    {"text": " Alt-F4.", "start": 4.1, "end": 4.9, "avg_logprob": -0.1},
    {"text": " It's all good.", "start": 5.6, "end": 7.4, "avg_logprob": -0.1}]}
del SEEN[:]
st = {}
notes = []
dr = WNS["_Drafter"](lambda k: AUD[k], [16000, 32000, 16000, 32000], sr, "P",
                     st, lambda: GATE["on"], True, notes)
check("the drafter packs by index: [[0, 1, 2, 3]] is 7.5 s - one window",
      dr.bufs == [[0, 1, 2, 3]])
check("get(i) waits for its window and answers by index",
      dr.get(0) == "Let's go." and dr.get(3) == "It's all good."
      and dr.get(2) == "Alt-F4." and dr.get(1) == "You made me lose a MMR game.")
dr.th.join(5)
check("one POST for the whole window, ahead of the reader (no get() needed "
      "for 1..3)", len(SEEN) == 1 and st.get("draft_win") == 1
      and st.get("draft_ask") == 4)
# the gate: a game has the machine -> the window the reader reaches is
# skipped (counted), never waited for; the next window drafts again
GATE["on"] = False
del SEEN[:]
st = {}
dr = WNS["_Drafter"](lambda k: AUD[k % 4], [16000] * 2 + [29 * sr] + [16000],
                     sr, "P", st, lambda: GATE["on"], True, [])
check("gated: three windows, nothing posted yet (no run-ahead while a game "
      "has the machine)", dr.bufs == [[0, 1], [2], [3]] and len(SEEN) == 0)
t0 = time.time()
got0 = dr.get(0)
check("the reader's get() on a gated window comes back at once with '' "
      "and the two utterances count as skipped",
      got0 == "" and time.time() - t0 < 2 and st.get("draft_skip") == 2
      and len(SEEN) == 0)
GATE["on"] = True
got2 = dr.get(2)
dr.th.join(5)
check("out of the game: the next windows draft again (2 POSTs, 2 asked)",
      len(SEEN) == 2 and st.get("draft_ask") == 2 and st.get("draft_skip") == 2)
# the dead switch: DRAFT_DEAD timed-out windows in a row end the night
WNS["urllib"] = types.SimpleNamespace(request=types.SimpleNamespace(
    Request=urllib.request.Request,
    urlopen=lambda req, timeout=60: real_urlopen(req, timeout=1.5)))
st = {}
notes = []
del SEEN[:]
dr = WNS["_Drafter"](lambda k: [0.0] * 96000, [28 * sr] * 4, sr, "P", st,
                     lambda: True, True, notes)
dr.th.join(20)
time.sleep(5)      # the single-threaded fake finishes its sleeps
check("two timed-out windows in a row: the ear is dead for the night, the "
      "other two windows are skipped without a POST, and a note says so",
      dr.dead is True and st.get("draft_timeout") == 2
      and st.get("draft_skip") == 2 and len(SEEN) == 2
      and any("went quiet after 2 timed-out window(s)" in n for n in notes))
check("get() on a dead drafter answers '' at once",
      dr.get(3) == "")
WNS["urllib"] = urllib
# the CPU road: no run-ahead - the window is drafted only when asked for
del SEEN[:]
st = {}
dr = WNS["_Drafter"](lambda k: AUD[k], [16000, 32000], sr, "P", st,
                     lambda: True, False, [])
time.sleep(0.6)
check("on the CPU road (ahead=False) nothing is posted until the reader asks",
      len(SEEN) == 0)
dr.get(0)
dr.th.join(5)
check("...and then it is", len(SEEN) == 1 and st.get("draft_win") == 1)

# =========================================================================
print("--- T11: the junk widened - what the real server said on noise ---")
judge = WNS["_draft_judge"]
PR = "Hearthstone. Friends on Discord: Wanderer, Faris. Alt-F4, MMR, duos, tavern, triple, GG."


def J(text, lp=-0.3, lang="english", prompt=PR, probs=None):
    sg = {"text": text, "avg_logprob": lp}
    if probs:
        sg["words"] = [{"word": "w", "probability": p} for p in probs]
    return judge([sg], lang, prompt)


check("Whisper reading its own prompt back is junk (measured 2026-09-06)",
      J(PR) == "" and J("Friends on Discord, Wanderer, Faris, Alt-F4, MMR, "
                        "duos, tavern.") == "")
check("the line that made the case still passes beside the prompt",
      J(" We just entered the duos Hearthstone match.")
      == "We just entered the duos Hearthstone match."
      and J("You made me lose a MMR game, that's fine.")
      == "You made me lose a MMR game, that's fine.")
check("'Thank you. Thank you. Thank you.' is junk; so is 'Thanks so much.'",
      J("Thank you. Thank you. Thank you.") == ""
      and J(" Thanks so much for watching!") == "")
check("the subtitle-credit family is junk",
      all(J(t) == "" for t in ("Subtitles by the Amara.org community",
                               "Transcribed by ESO, translated by -",
                               "Captions by Wanderer", "www.example.com")))
check("*tags* are stripped, a tag alone is nothing",
      J("*BOOM* *BOOM* Jool! Jool!") == "Jool! Jool!"
      and J(" *crunch*") == "" and J("[Music]") == ""
      and J("(laughs) okay go") == "okay go")
check("the noise clip: 'And now we're going to go to the next video.' at "
      "avg_logprob -0.98 is under the floor -> junk; the same at -0.3 passes",
      J("And now we're going to go to the next video.", lp=-0.98) == ""
      and J("And now we're going to go to the next video.", lp=-0.3) != "")
check("real speech measured at -0.2..-0.6 passes the floor",
      J("Do you want us to leave? You want to play?", lp=-0.28) != ""
      and J("It's all good.", lp=-0.59) != "")
check("a segment without avg_logprob is not judged by it",
      J("eight gold so not ready", lp=None) == "eight gold so not ready")
check("the 0.35 word-probability bar and the 3-gram loop still hold",
      J("eight gold so not ready", probs=[0.2, 0.4, 0.3]) == ""
      and J("I got wild gun I got wild gun I got wild gun yes") == "")
check("a language nobody here speaks is junk whatever the text",
      J("We just entered the duos match", lang="hindi") == "")
check("_draft_echo: three words up, most prefixes in the prompt; a real "
      "short callout with one prompt word is not",
      WNS["_draft_echo"]("tavern triple duos", PR) is True
      and WNS["_draft_echo"]("go to the tavern now guys", PR) is False
      and WNS["_draft_echo"]("Alt-F4", PR) is False
      and WNS["_draft_echo"]("anything", "") is False)
# the names clause out of the echo base (the low finding): a six-word
# callout that is mostly names is not the prompt talking
eb = WNS["_echo_base"]
CTXN = ("Gaming session of Hearthstone. Friends on Discord playing together; "
    "casual gaming chat, callouts, jokes. They speak Emirati Gulf Arabic "
    "and English, often switching within one sentence. Names in the room: "
    "Wanderer, Faris, Marid, Fares.")
check("_echo_base cuts the names clause and nothing else; None stays None",
      eb(CTXN) == CTXN.split(" Names in the room:")[0] and eb(None) is None
      and eb("") == "" and eb("plain") == "plain")
line = "Wanderer Faris Marid Fares gaming friends"
check("the harness case: a six-word callout that is mostly names is an echo "
      "of the widened context but NOT of the echo base",
      ctx_echo(line, CTXN) is True and ctx_echo(line, eb(CTXN)) is False)

# =========================================================================
print("--- T12: the app's side of the fixes ---")
# the .ctl carries ear2 from the same question the budget asks
BNS = {"os": os, "json": json, "_AI": {}, "_game_has_focus": lambda: False}
for nm in ("_reader_playing", "_reader_threads", "_write_reader_budget"):
    extract(LSRC, LTREE, nm, BNS)
ctl = os.path.join(tmp, "x.wav.ctl")
ncpu = os.cpu_count() or 8
n_idle = BNS["_write_reader_budget"](ctl)
j_idle = json.load(io.open(ctl, encoding="utf-8"))
BNS["_game_has_focus"] = lambda: True
n_play = BNS["_write_reader_budget"](ctl)
j_play = json.load(io.open(ctl, encoding="utf-8"))
check("idle: threads = n-4 and ear2 = 1; playing: n//4 and ear2 = 0",
      j_idle == {"threads": max(2, ncpu - 4), "ear2": 1} and n_idle == j_idle["threads"]
      and j_play == {"threads": max(2, ncpu // 4), "ear2": 0})
check("_reader_threads(False) is the idle count whatever has focus",
      BNS["_reader_threads"](False) == max(2, ncpu - 4)
      and BNS["_reader_threads"]() == max(2, ncpu // 4))
BNS["_game_has_focus"] = lambda: False
# the worker's gate reads it (lifted from main's source by regex, since
# it closes over ctl_path)
gsrc = re.search(r"    def wanted_ear2\(\):[\s\S]*?\n(?=\n    have_threads)",
                 WSRC).group(0)
GNS = {"json": json, "os": os, "ctl_path": ctl}
exec(compile(textwrap.dedent(gsrc), "<wanted_ear2>", "exec"), GNS)
we = GNS["wanted_ear2"]
io.open(ctl, "w", encoding="utf-8").write(json.dumps({"threads": 6, "ear2": 0}))
check("wanted_ear2: the app's 0 wins over any thread count", we() is False)
io.open(ctl, "w", encoding="utf-8").write(json.dumps({"threads": 3, "ear2": 1}))
check("wanted_ear2: the app's 1 wins", we() is True)
io.open(ctl, "w", encoding="utf-8").write(json.dumps({"threads": max(2, ncpu // 4)}))
check("an older .ctl without ear2: the playing count means no",
      we() is False)
io.open(ctl, "w", encoding="utf-8").write(json.dumps({"threads": ncpu}))
check("...and a full budget means yes; no .ctl at all means yes",
      we() is True and (os.remove(ctl) or we() is True))
# the clamp at a person's boundary + the file's comma
CNS = {}
clamp = extract(LSRC, LTREE, "_room_names_clamp", CNS)
long = ", ".join("N%03d" % i for i in range(200))       # 1198 chars
got = clamp(long)
check("_room_names_clamp: <= 600, ends on a whole name, never mid-name",
      len(got) <= 600 and got.endswith("N099") and not got.endswith(",")
      and got == long[:got.index("N099") + 4])
check("_room_names_clamp: 700 X's with no separator -> 600 (nothing to "
      "cut at); short input untouched but stripped",
      clamp("X" * 700) == "X" * 600 and clamp("  Wanderer, Faris ") == "Wanderer, Faris")
RNS["SETTINGS"] = {"room_names": ""}
RNS["_room_names_clamp"] = clamp
del SAVED[:]
io.open(os.path.join(data, "room_names.txt"), "w", encoding="utf-8").write(
    "Wanderer, Faris / Fares\nMarid\n")
check("a comma in room_names.txt separates PEOPLE, as the setting does",
      RNS["_seed_room_names"]() is True
      and RNS["SETTINGS"]["room_names"] == "Wanderer, Faris / Fares, Marid"
      and "3 people" in SLOG[-1])
# the missing ear is said once per launch (the source pin sits in T8);
# run the block's shape: _AI remembers
check("the once-per-launch flag lives in _AI, set before the log",
      tsrc.index('_AI["ear2_missing_said"] = True')
      < tsrc.index("The second ear is not installed"))
# ai\whisper travels with the build; the installer stops an orphan
BAT = io.open(os.path.join(ROOT, "build.bat"), encoding="utf-8",
              errors="replace").read()
check("build.bat copies ai\\whisper beside the other ai folders",
      "for %%D in (packs torchlibrosa vendor_ocr vendor_sb whisper) do (" in BAT)
check("installer.iss stops whisper-server.exe before install and on uninstall",
      ISS.count("taskkill /F /IM whisper-server.exe") == 2
      and 'RunOnceId: "StopWhisperServer"' in ISS)
wdir = os.path.join(ROOT, "ai", "whisper")
have = set(os.listdir(wdir)) if os.path.isdir(wdir) else set()
check("ai\\whisper holds whisper-server.exe + whisper.dll + ggml.dll + "
      "ggml-base.dll + the ggml-cpu-*.dll set (the drop-in's payload)",
      {"whisper-server.exe", "whisper.dll", "ggml.dll", "ggml-base.dll"}
      <= have and any(n.startswith("ggml-cpu-") for n in have)
      and not any(n.endswith(".bin") for n in have))

httpd.shutdown()
shutil.rmtree(tmp, ignore_errors=True)
print("%d ok, %d failed" % (OK, FAIL))
sys.exit(1 if FAIL else 0)

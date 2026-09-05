# -*- coding: utf-8 -*-
"""3.32 ASK THE SHELF - the librarian, and every hand that touches it.

Drives the REAL functions lifted out of lore.py by name against a FAKE
embedding server (a tiny http.server on a free port answering /health
and /v1/embeddings with deterministic bag-of-words vectors), so the whole
index/query road runs for real without a model and without the card:
the items a night puts on the shelf (media/game/nn lines left out, the
chunks keeping the first line's second), the sidecar write and the
no-rewrite on an unchanged signature (the mtime law), the owe gate
(False without the model, cached on the sidecar's clock AND the
signature, never a spawn), the tail's 'index' branch as written (the
screen visit first on a night that owes both, the newest night's index
before an older night's screen), the merged index and a query that
ranks the right night and second, the exact-word blend (a name never
depends on a vector), the answer gate (a game on the screen -> None; the
describer asked with the numbered excerpts and the cite rule; a cite
that points nowhere is dropped), the bridge shapes, the UI read from
its source, and the DORMANT parity block: with no model on disk every
touched road answers exactly as HEAD's. Scratch dirs live in tempfile;
nothing under D:\\Records is touched; no port in 8906-8912 is ever
spoken to."""
import ast
import base64
import hashlib
import io
import json
import os
import random
import re
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
USRC = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()
TREE = ast.parse(SRC)
try:
    HSRC = subprocess.run(["git", "show", "HEAD:lore.py"], cwd=ROOT,
                          capture_output=True, timeout=60).stdout \
        .decode("utf-8", "replace").replace("\r\n", "\n")
except Exception:
    HSRC = ""
HTREE = ast.parse(HSRC) if HSRC else None

ok = bad = 0


def check(what, cond):
    global ok, bad
    if cond:
        ok += 1
        print("  OK  ", what)
    else:
        bad += 1
        print("  FAIL", what)


def extract(src, name, ns, tree=None):
    """A module-level function, lifted as written."""
    tree = tree or ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                src.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


def extract_class(src, name, ns, tree=None):
    tree = tree or ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                src.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


def extract_method(src, cls, name, ns, tree=None):
    """A method of a class, lifted as a plain function taking self."""
    tree = tree or ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    code = textwrap.dedent("\n".join(
                        src.splitlines()[f.lineno - 1:f.end_lineno]))
                    exec(compile(code, "<" + cls + "." + name + ">",
                                 "exec"), ns)
                    return ns[name]
    raise AssertionError(cls + "." + name)


def fsrc(src, name, tree=None):
    tree = tree or ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) \
                and node.name == name:
            return "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
    raise AssertionError(name)


def msrc(src, cls, name, tree=None):
    tree = tree or ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    return "\n".join(
                        src.splitlines()[f.lineno - 1:f.end_lineno])
    raise AssertionError(cls + "." + name)


def assign(src, name, ns, tree=None):
    tree = tree or ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name
                for t in node.targets):
            code = "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


# =========================================================================
print("--- the fake librarian: a bag-of-words embedder on a free port ---")
DIM_OUT = 768           # the real model's width; the app cuts to 256


def _wordvec(word):
    r = random.Random(int(hashlib.sha1(word.encode("utf-8")).hexdigest()[:8],
                          16))
    return [r.gauss(0, 1) for _ in range(DIM_OUT)]


def fake_embed(text):
    """The text after the prompt head, as a bag of words: shared words
    mean shared direction, so a question finds the line it paraphrases."""
    body = text
    for head in ("| text: ", "| query: "):
        if head in body:
            body = body.split(head, 1)[1]
    words = re.findall(r"[^\W\d_]{2,}", body.lower())
    v = [0.0] * DIM_OUT
    for w in words or ["empty"]:
        for i, x in enumerate(_wordvec(w)):
            v[i] += x
    n = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / n for x in v]


SERVED = {"n": 0, "batches": []}


class FakeHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/health":
            body = b'{"status":"ok"}'
            self.send_response(200)
        else:
            body = b"{}"
            self.send_response(404)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        d = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        inp = d.get("input")
        if isinstance(inp, str):
            inp = [inp]
        SERVED["n"] += 1
        SERVED["batches"].append(len(inp))
        # answered out of order on purpose: the app must sort by index
        rows = [{"index": i, "embedding": fake_embed(t), "object": "embedding"}
                for i, t in enumerate(inp)]
        rows.reverse()
        body = json.dumps({"data": rows, "model": "fake"}).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


_s = socket.socket()
_s.bind(("127.0.0.1", 0))
FAKE_PORT = _s.getsockname()[1]
_s.close()
assert not (8906 <= FAKE_PORT <= 8912)
httpd = HTTPServer(("127.0.0.1", FAKE_PORT), FakeHandler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
check("the fake embedder is up on a free port outside 8906-8912",
      FAKE_PORT > 0 and not (8906 <= FAKE_PORT <= 8912))

# =========================================================================
print("\n--- the namespace: the real functions, a scratch shelf ---")
tmp = tempfile.mkdtemp(prefix="lore_ask332_")
LIB = os.path.join(tmp, "Records")
TDIR = os.path.join(LIB, ".lore_thumbs")
os.makedirs(TDIR)
logs = []
WRITES = {"n": 0}


def side(video_path, kind):
    name = os.path.splitext(os.path.basename(video_path))[0]
    return os.path.join(TDIR, name + "." + kind + ".json")


def atomic(p, d):
    WRITES["n"] += 1
    tmpp = p + ".tmp"
    io.open(tmpp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))
    os.replace(tmpp, p)


import urllib.request as _urlreq   # noqa: E402  (the module lore.py uses)

MODEL = [None]          # what _emb_paths answers: None = no librarian
ns = {"os": os, "json": json, "re": re, "time": time, "threading": threading,
      "subprocess": subprocess, "_urlreq": _urlreq,
      "SETTINGS": {"output_dir": LIB},
      "_ai_sidecar": side, "_atomic_write_json": atomic,
      "_thumb_dir": lambda out: TDIR,
      "log": lambda m: logs.append(m),
      "_display_name": lambda s: {"RocketLeague": "Rocket League",
                                  "Hearthstone": "Hearthstone",
                                  "EldenRing": "Elden Ring"}.get(s, s),
      "_runtime_dir": lambda n: os.path.join(tmp, "rt", n),
      "_model_file": lambda *p: os.path.join(tmp, "models", *p),
      "_popen": None, "_free_port": lambda p: None,
      "_describer_paths": lambda: ("exe", "gguf"),
      "_game_has_focus": lambda: False,
      "_AUD_ASK": {"path": None},
      "_ask_negish": None, "_dt": __import__("datetime")}
for c in ("_EMB", "_EMB_OWE_CACHE", "_EMB_LOCK", "_EMB_STANDDOWN",
          "_EMB_PORT", "_EMB_MODEL", "_EMB_DIM",
          "_EMB_DOZE", "_EMB_BATCH", "_SHELF_PATHS", "_SHELF_ANS",
          "_SHELF_STOP", "_DESC_PORT"):
    assign(SRC, c, ns, TREE)
ns["_AI"] = {"abort": False, "busy": None, "index": None, "index_t": 0.0,
             "shelf": None, "shelf_t": 0.0, "failed": {}, "veto": None,
             "proc": None}
for f in ("_read_sidecar", "_parse_clip_name", "_shelf_items", "_emb_sig",
          "_emb_owing", "_emb_srv", "_emb_drop", "_emb_idle_tick", "_emb_one",
          "_emb_paths", "_emb_ready", "_search_index", "_search_words",
          "_shelf_paths", "_shelf_index", "_shelf_hit", "_shelf_exact",
          "_shelf_query", "_shelf_card_why", "_shelf_busy_why",
          "_shelf_answer", "_ask_negish"):
    extract(SRC, f, ns, TREE)
extract_class(SRC, "_DescServer", ns, TREE)
extract_class(SRC, "_EmbServer", ns, TREE)
real_emb_paths = ns["_emb_paths"]
ns["_emb_paths"] = lambda: MODEL[0]
_shelf_items = ns["_shelf_items"]
_emb_sig, _emb_owing, _emb_one = ns["_emb_sig"], ns["_emb_owing"], ns["_emb_one"]
check("_MODEL_SETS carries the librarian: the verified file, bytes, dir, "
      "the reader tier",
      '{"key": "librarian", "tier": "reader",' in SRC
      and '"dir": "embeddinggemma-gguf",' in SRC
      and '_HF % ("ggml-org/embeddinggemma-300M-GGUF",\n'
          '                 "embeddinggemma-300M-Q8_0.gguf"), 333590944),' in SRC
      and 'ns' and ns["_EMB_PORT"] == 8910 and ns["_EMB_DIM"] == 256)
check("_emb_paths reads the same runtime dir and models dir the fetcher "
      "fills, and answers None while either is missing",
      real_emb_paths() is None
      and 'os.path.join(_runtime_dir("llama"), "llama-server.exe")'
      in fsrc(SRC, "_emb_paths", TREE)
      and '_model_file("embeddinggemma-gguf", _EMB_MODEL + ".gguf")'
      in fsrc(SRC, "_emb_paths", TREE))

# ---- three nights on the scratch shelf
V_RL = os.path.join(LIB, "RocketLeague_20260904_233625.mp4")
V_HS = os.path.join(LIB, "Hearthstone_20260819_200623.mp4")
V_ER = os.path.join(LIB, "EldenRing_20260701_210000.mp4")
for v in (V_RL, V_HS, V_ER):
    io.open(v, "wb").write(b"\0" * 64)
    os.utime(v, (1000000.0, 1000000.0))


def put(v, kind, doc, mt=1000500.0):
    io.open(side(v, kind), "w", encoding="utf-8").write(
        json.dumps(doc, ensure_ascii=False))
    os.utime(side(v, kind), (mt, mt))


def seg(a, b, t, **k):
    d = {"a": a, "b": b, "t": t}
    d.update(k)
    return d


put(V_RL, "ins", {
    "title": "The night the overtime goals would not stop",
    "summary": "Three overtime matches, a rage quit in the second, and a "
               "comeback that nobody in the room believed.",
    "chapters": [{"t": 0.6, "b": 124.0, "label": "warming up",
                  "what": "free play and a quiet first match"},
                 {"t": 640.0, "b": 900.0, "label": "the rage quit",
                  "what": "a teammate leaves after the overtime goal"},
                 {"t": 1500.0, "b": 1800.0, "label": "the comeback",
                  "what": "down three, back to four; the room erupts"}],
    "windows": {"1": {"segments": [], "moments": [
        {"t": 655.0, "why": "the rage quit lands and everyone laughs"}]},
        "0": {"segments": [], "moments": [
            {"t": 30.0, "why": "a whiff in the first minute"}]}},
    "moments": [{"t": 655.0, "why": "dup of the window moment"}]})
put(V_RL, "stt", {"segments": [
    seg(1000, 3000, "okay first match let us warm up"),
    seg(4000, 6000, "watch the boost on the left"),
    seg(640000, 643000, "he just left the match, he rage quit in overtime"),
    seg(644000, 646000, "unbelievable, a rage quit after the overtime goal"),
    seg(700000, 702000, "and that is why the Quilboar build is dead",
        src="media"),
    seg(705000, 707000, "The enemy has scored", src="game"),
    seg(710000, 711000, "hmm", nn=True),
    seg(1500000, 1503000, "down three, do not give up"),
    seg(1790000, 1792000, "we came back, we actually came back"),
] + [seg(1800000 + i * 2000, 1801000 + i * 2000,
         "line number %d of a long stretch of talking about nothing" % i)
     for i in range(12)]})
put(V_HS, "ins", {
    "title": "Battlegrounds: the Quilboar lobby",
    "summary": "A long Battlegrounds session that ended fourth.",
    "chapters": [{"t": 10.0, "b": 300.0, "label": "the early shop",
                  "what": "rolling for Quilboars and finding none"}],
    "windows": {}, "moments": []})
put(V_HS, "stt", {"segments": [
    seg(12000, 14000, "no Quilboars in this shop at all"),
    seg(300000, 303000, "Godskin is streaming again tonight"),
]})
put(V_ER, "stt", {"segments": [
    seg(5000, 8000, "the Godskin Apostle again, third try"),
    seg(9000, 12000, "roll left, then the jump attack"),
]})

# =========================================================================
print("\n--- what one night puts on the shelf ---")
it = _shelf_items(V_RL)
kinds = [i["k"] for i in it]
check("the order is title, summary, chapters, moments, then the lines",
      kinds[:2] == ["title", "summary"]
      and kinds[2:5] == ["chapter"] * 3
      and kinds[5:7] == ["moment"] * 2
      and set(kinds[7:]) == {"line"})
check("a chapter carries its name and its what, and its span",
      it[3]["x"] == "the rage quit. a teammate leaves after the overtime goal"
      and it[3]["t"] == 640.0 and it[3]["b"] == 900.0)
check("window moments come in window order (0 before 1); the top-level "
      "duplicate is not indexed twice",
      [i["x"] for i in it if i["k"] == "moment"]
      == ["a whiff in the first minute",
          "the rage quit lands and everyone laughs"]
      and not any("dup of" in i["x"] for i in it))
lines = [i for i in it if i["k"] == "line"]
check("a media line, a game line and an nn line never reach the vectors",
      not any("Quilboar build" in i["x"] or "enemy has scored" in i["x"]
              or i["x"] == "hmm" for i in lines))
check("the room's words fold into stretches that keep the FIRST line's "
      "second (the first stretch starts at 1.0 s)",
      lines[0]["t"] == 1.0 and lines[0]["x"].startswith("okay first match"))
check("a stretch closes at ~300 characters or 45 s of silence, so the "
      "rage-quit lines sit in a stretch of their own at 640 s",
      any(i["t"] == 640.0 and "rage quit" in i["x"] for i in lines))
check("the long stretch of chatter folds by size, not one vector a line",
      3 <= len([i for i in lines if "line number" in i["x"]]) <= 5)
check("deterministic: the same sidecars give the same list",
      _shelf_items(V_RL) == it)
check("a night with a transcript and no review still has lines",
      [i["k"] for i in _shelf_items(V_ER)] == ["line"])
check("an empty review contributes nothing but the lines",
      (put(V_ER, "ins", {"empty": True, "title": "x"}),
       [i["k"] for i in _shelf_items(V_ER)])[1] == ["line"])
os.remove(side(V_ER, "ins"))

# =========================================================================
print("\n--- the signature and the owe gate ---")
sig = _emb_sig(V_RL)
check("the signature is the clock and size of ins and stt, plus the model "
      "and width", sig["model"] == "embeddinggemma-300M-Q8_0"
      and sig["dim"] == 256 and sig["ins"][0] == 1000500.0
      and sig["stt"][1] == os.path.getsize(side(V_RL, "stt")))
check("no sidecars at all: no signature, nothing owed even with a model",
      _emb_sig(os.path.join(LIB, "Nothing_20260101_000000.mp4")) is None)
MODEL[0] = None
calls = {"items": 0}
_real_items = ns["_shelf_items"]
ns["_shelf_items"] = lambda p: (calls.__setitem__("items", calls["items"] + 1),
                                _real_items(p))[1]
check("NO MODEL: nothing is owed, and no sidecar is even opened",
      _emb_owing(V_RL) is False and calls["items"] == 0)
MODEL[0] = ("exe", "gguf")
check("with the model, a night with sidecars and no index is owed",
      _emb_owing(V_RL) is True and calls["items"] == 1)
check("...and the answer is remembered: the second ask opens nothing",
      _emb_owing(V_RL) is True and calls["items"] == 1)
V_NN = os.path.join(LIB, "Quiet_20260102_000000.mp4")
io.open(V_NN, "wb").write(b"\0")
put(V_NN, "stt", {"segments": [seg(1000, 2000, "x", nn=True)]})
check("a night with nothing to index is never owed",
      _emb_owing(V_NN) is False)
ns["_shelf_items"] = _real_items
check("the tail's owe test never spawns anything: no subprocess, no server "
      "in _emb_owing", "subprocess" not in fsrc(SRC, "_emb_owing", TREE)
      and "_emb_srv" not in fsrc(SRC, "_emb_owing", TREE)
      and "_EmbServer" not in fsrc(SRC, "_emb_owing", TREE))

# =========================================================================
print("\n--- the index visit against the fake librarian ---")


class FakeProc:
    def __init__(self):
        self.alive = True

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.alive = False

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.alive = False


def fake_srv():
    s = ns["_EmbServer"](port=FAKE_PORT)
    s.pr = FakeProc()
    return s


SRV = fake_srv()
ns["_EMB"]["srv"] = SRV
ns["_emb_srv"] = lambda budget=90: SRV
check("the embedder's health probe answers on the fake port", SRV.alive())
_ref = fake_embed("title: none | text: rage quit in overtime")[:256]
vecs = SRV.embed(["title: none | text: rage quit in overtime",
                  "title: none | text: a comeback nobody believed"])
check("embed() returns one unit row per text, cut to 256 and re-normalised, "
      "in input order whatever order the server answered",
      vecs and len(vecs) == 2 and len(vecs[0]) == 256
      and abs(sum(x * x for x in vecs[0]) - 1.0) < 1e-4
      and abs(sum(a * b for a, b in zip(vecs[0], _ref)) / (
          sum(x * x for x in _ref) ** 0.5)) > 0.999)
SERVED["n"] = 0
SERVED["batches"] = []
WRITES["n"] = 0
ok1 = _emb_one(V_RL)
ep = side(V_RL, "emb")
d = json.load(io.open(ep, encoding="utf-8"))
st1 = os.stat(ep)
check("_emb_one writes <base>.emb.json atomically: v, model, dim, sig, "
      "items, vec", ok1 is True and WRITES["n"] == 1 and d["v"] == 1
      and d["model"] == "embeddinggemma-300M-Q8_0" and d["dim"] == 256
      and d["sig"] == _emb_sig(V_RL) and len(d["items"]) == len(it))
check("the vectors are float16 rows, base64, N x 256",
      len(base64.b64decode(d["vec"])) == len(it) * 256 * 2)
check("each item carries its kind, seconds, a hash of the FULL text and a "
      "160-character preview",
      all(set(x) == {"k", "t", "b", "h", "x"} for x in d["items"])
      and d["items"][3]["h"] == hashlib.sha1(
          it[3]["x"].encode("utf-8")).hexdigest()[:12]
      and all(len(x["x"]) <= 160 for x in d["items"]))
check("the items went in batches of 32 at most",
      SERVED["batches"] and max(SERVED["batches"]) <= 32
      and sum(SERVED["batches"]) == len(it))
check("...and the index is now paid: not owed, and the merged matrix is "
      "dropped for a rebuild", _emb_owing(V_RL) is False
      and ns["_AI"]["shelf"] is None)
time.sleep(0.05)
SERVED["n"] = 0
ok2 = _emb_one(V_RL)
st2 = os.stat(ep)
check("THE MTIME LAW: a second visit on an unchanged night rewrites "
      "nothing - same clock, same size, no embed call",
      ok2 is True and WRITES["n"] == 1 and SERVED["n"] == 0
      and (st1.st_mtime, st1.st_size) == (st2.st_mtime, st2.st_size))
put(V_RL, "stt", json.load(io.open(side(V_RL, "stt"), encoding="utf-8")),
    mt=1000600.0)
check("the transcript moved (its clock): the night is owed again",
      _emb_owing(V_RL) is True)
ok3 = _emb_one(V_RL)
check("...and the new index carries the new signature",
      ok3 is True and json.load(io.open(ep, encoding="utf-8"))["sig"]["stt"][0]
      == 1000600.0 and _emb_owing(V_RL) is False)
os.remove(ep)
check("the index deleted: owed", _emb_owing(V_RL) is True)
ok4 = _emb_one(V_RL)
d4 = json.load(io.open(ep, encoding="utf-8"))
d4["model"] = "some-other-model"
d4["sig"]["model"] = "some-other-model"
io.open(ep, "w", encoding="utf-8").write(json.dumps(d4))
check("an index written by another model mismatches the signature: owed",
      ok4 and _emb_owing(V_RL) is True)
_emb_one(V_RL)
check("the empty night writes an honest empty index and is done",
      _emb_one(V_NN) is True
      and json.load(io.open(side(V_NN, "emb"), encoding="utf-8"))["items"] == []
      and _emb_owing(V_NN) is False)

# abort
ns["_AI"]["abort"] = True
dropped = []
_real_drop = ns["_emb_drop"]
ns["_emb_drop"] = lambda: dropped.append(1)
os.remove(side(V_HS, "emb")) if os.path.isfile(side(V_HS, "emb")) else None
WRITES["n"] = 0
r_ab = _emb_one(V_HS)
check("ABORT (a game starts): the visit returns False within one batch, "
      "writes no sidecar, and lets the embedder go",
      r_ab is False and WRITES["n"] == 0 and not os.path.isfile(side(V_HS, "emb"))
      and dropped == [1])
ns["_AI"]["abort"] = False
ns["_emb_drop"] = _real_drop

# failure: the server gives nothing
_real_embed = ns["_EmbServer"].embed
ns["_EmbServer"].embed = lambda self, texts, dim=None: None
r_f = [_emb_one(V_HS) for _ in range(3)]
df = json.load(io.open(side(V_HS, "emb"), encoding="utf-8"))
check("a failure is written into the sidecar with its count; three "
      "strikes and the tail leaves the night alone until it moves",
      r_f == [False] * 3 and df.get("failed") and df["tries"] == 3
      and _emb_owing(V_HS) is False)
ns["_EmbServer"].embed = _real_embed
put(V_HS, "stt", json.load(io.open(side(V_HS, "stt"), encoding="utf-8")),
    mt=1000700.0)
check("...a moved sidecar forgives the strikes", _emb_owing(V_HS) is True
      and _emb_one(V_HS) is True and _emb_owing(V_HS) is False)
check("the failed sidecar never carried vectors and the good one does",
      json.load(io.open(side(V_HS, "emb"), encoding="utf-8"))["vec"])
_emb_one(V_ER)
check("the abort path in _emb_one is checked per batch, not per night",
      'for i in range(0, len(items), _EMB_BATCH):\n'
      '            if _AI["abort"]:' in fsrc(SRC, "_emb_one", TREE))

# the doze
ns["_EMB"]["t"] = time.time() - 700
stops = []
_real_drop2 = ns["_emb_drop"]
ns["_emb_drop"] = lambda: stops.append(1)
ns["_emb_idle_tick"]()
check("the librarian dozes after ten quiet minutes, like the ask server",
      stops == [1] and "ten quiet minutes" in logs[-1])
ns["_EMB"]["srv"] = None
ns["_emb_idle_tick"]()
check("...and with no server ever woken the tick does nothing",
      stops == [1])
ns["_emb_drop"] = _real_drop2
ns["_EMB"]["srv"] = SRV
ns["_EMB"]["t"] = time.time()

# =========================================================================
print("\n--- the server: --device none, port 8910, never the card's slot ---")
es = fsrc(SRC, "_EmbServer", TREE)
check("_EmbServer is a _DescServer with its own start() and the parent's "
      "stop()", "class _EmbServer(_DescServer):" in es
      and "def start(self, budget=90):" in es and "def stop(" not in es)
check("it spawns ai/llama's llama-server with --embedding --pooling mean "
      "--device none -ngl 0 --no-webui on 8910",
      '"--embedding", "--pooling", "mean",' in es
      and '"--device", "none", "-ngl", "0",' in es
      and '"--no-webui"' in es and "_EMB_PORT = 8910" in SRC
      and "int(port or _EMB_PORT)" in es)
check("it never registers in _AI['proc'] - the card's abort path must not "
      "reach it", '_AI["proc"]' not in es and "never _AI['proc']" in es)
check("a stale abort flag from the last job does not gag a question",
      'if _AI["abort"] and _AI.get("busy") is not None:' in es)
check("the parent describer server is untouched",
      HSRC and fsrc(HSRC, "_DescServer", HTREE) == fsrc(SRC, "_DescServer", TREE))
check("the idle tick rides beside the ask server's at every call site",
      SRC.count("    _emb_idle_tick()\n") == 3
      and SRC.count("_ask_idle_tick()\n        _emb_idle_tick()\n"
                    "        _desc_keep_tick()") == 2
      and SRC.count("_ask_idle_tick()\n    _emb_idle_tick()\n"
                    "    _desc_keep_tick()") == 1)

# =========================================================================
print("\n--- the tail: one seat, the index branch as written ---")
_at = fsrc(SRC, "_ai_tick", TREE).splitlines()
i0 = next(i for i, ln in enumerate(_at)
          if ln.strip().startswith("emb_ok = bool(do_hl and not playing")
          and "Neither owing test opens a video." in _at[i - 1])
i1 = next(i for i in range(i0, len(_at))
          if '_AI["tail"] = ("index", p)' in _at[i]) + 2
frag = "\n".join(_at[i0:i1 + 1])
assert frag.rstrip().endswith("return"), frag[-200:]
frag_fn = "def _frag(vids, do_hl, playing):\n" + textwrap.indent(
    textwrap.dedent(frag), "    ")
spawns = []
asked = {"emb": 0}
tns = {"os": os, "time": time, "_AI": ns["_AI"],
       "_EMB": ns["_EMB"], "_EMB_STANDDOWN": ns["_EMB_STANDDOWN"],
       "_ai_skipped_recently": lambda p: False,
       "_queued_finish_badge": lambda p: False,
       "_ai_sidecar_fresh": lambda p, k: True,
       "_spawn": lambda kind, p, mt: spawns.append((kind, p))}
exec(compile(frag_fn, "<tail>", "exec"), tns)
OWE = {"hud": set(), "out": set(), "emb": set()}
tns["_hud_owing"] = lambda p: p in OWE["hud"]
tns["_outcome_owing"] = lambda p: p in OWE["out"]
tns["_emb_owing"] = lambda p: (asked.__setitem__("emb", asked["emb"] + 1),
                               p in OWE["emb"])[1]
tns["_emb_paths"] = lambda: MODEL[0]
NEW, OLD = V_RL, V_HS           # newest first, as the sweep walks
MODEL[0] = None
OWE["emb"] = {NEW, OLD}
tns["_frag"]([NEW, OLD], True, False)
check("NO MODEL: the tail never owes an index - _emb_owing is not even "
      "asked, nothing spawns", spawns == [] and asked["emb"] == 0)
MODEL[0] = ("exe", "gguf")
ns["_EMB"]["down_t"] = time.time()
tns["_frag"]([NEW, OLD], True, False)
check("a librarian that would not start stands the tail down for ten "
      "minutes: nothing spawns, _emb_owing is not even asked (drop D)",
      spawns == [] and asked["emb"] == 0 and ns["_EMB_STANDDOWN"] == 600.0)
ns["_EMB"]["down_t"] = time.time() - 601
tns["_frag"]([NEW, OLD], True, False)
check("...and ten minutes later the tail knocks again",
      asked["emb"] >= 1 and len(spawns) == 1)
ns["_EMB"]["down_t"] = 0.0
del spawns[:]
asked["emb"] = 0
tns["_frag"]([NEW, OLD], True, False)
check("with the model: the newest night's index spawns on the listening "
      "lane with the 'index' key", spawns == [("listening", NEW)]
      and ns["_AI"]["tail"] == ("index", NEW))
spawns.clear()
OWE["hud"] = {NEW}
tns["_frag"]([NEW, OLD], True, False)
check("a night that owes both: the screen visit first (the index waits "
      "for the next beat)", spawns == [("listening", NEW)]
      and ns["_AI"]["tail"] == ("screen", NEW))
spawns.clear()
OWE["hud"] = {OLD}
OWE["emb"] = {NEW}
tns["_frag"]([NEW, OLD], True, False)
check("PER NIGHT, NEWEST FIRST: a new night's index lands before an older "
      "night's screen work", spawns == [("listening", NEW)]
      and ns["_AI"]["tail"] == ("index", NEW))
spawns.clear()
tns["_frag"]([NEW, OLD], True, True)
check("...never while he plays", spawns == [])
tns["_frag"]([NEW, OLD], False, False)
check("...and only on the listening lane's switch (do_hl)", spawns == [])
ns["_AI"]["failed"][NEW] = os.path.getmtime(NEW)
tns["_frag"]([NEW, OLD], True, False)
check("a night the sweep gave up on is skipped like any other; the older "
      "night's screen visit takes the seat", spawns == [("listening", OLD)]
      and ns["_AI"]["tail"] == ("screen", OLD))
ns["_AI"]["failed"].clear()
spawns.clear()
check("_emb_paths is asked once a beat, before the loop, never once a night",
      "emb_ok = bool(do_hl and not playing and _emb_paths() is not None)"
      in frag and "elif emb_ok and _emb_owing(p):" in frag
      and "if do_hl and not playing:\n        for p in vids:" in SRC)
wk = fsrc(SRC, "_ai_tick", TREE)
check("work(): the index visit runs _emb_one alone, before the kind "
      "branches, and never the ears, the grid or the card",
      'if tail == "index":\n' in wk
      and wk.index('if tail == "index":') < wk.index('elif kind == "hearing":')
      and "ok = _emb_one(path)" in wk)
check("...its busy row reads 'the librarian · name' and, like the screen "
      "visit, it never drops the warm describer",
      '"index": "the librarian"}.get(tail, tail)' in wk
      and "if not tail:\n" in wk and "_ask_srv_drop()" in wk)

# =========================================================================
print("\n--- the merged index and the query ---")
ns["_shelf_paths"] = lambda: {
    os.path.splitext(os.path.basename(v))[0]: (v, os.path.getmtime(v))
    for v in (V_RL, V_HS, V_ER, V_NN)}
ns["_AI"]["shelf"] = None
idx = ns["_shelf_index"]()
check("every night's index merges into one unit matrix with its rows",
      idx is not None and idx["M"].shape[1] == 256
      and len(idx["rows"]) == idx["M"].shape[0]
      and {r[0] for r in idx["rows"]} == {
          os.path.splitext(os.path.basename(v))[0] for v in (V_RL, V_HS, V_ER)}
      and abs(float((idx["M"][0] ** 2).sum()) - 1.0) < 1e-4)
check("the merge is cached: the same object comes back until an emb.json "
      "moves", ns["_shelf_index"]() is idx)
d_er = json.load(io.open(side(V_ER, "emb"), encoding="utf-8"))
d_er["model"] = "another"
io.open(side(V_ER, "emb"), "w", encoding="utf-8").write(json.dumps(d_er))
ns["_AI"]["shelf_t"] = 0.0
idx2 = ns["_shelf_index"]()
check("an emb.json that moved rebuilds the merge; one written by another "
      "model is skipped (it stays owed to the tail)",
      idx2 is not idx and "EldenRing_20260701_210000" not in
      {r[0] for r in idx2["rows"]})
d_er["model"] = "embeddinggemma-300M-Q8_0"
io.open(side(V_ER, "emb"), "w", encoding="utf-8").write(json.dumps(d_er))
ns["_AI"]["shelf_t"] = 0.0
idx3 = ns["_shelf_index"]()
check("...and comes back once it matches again",
      "EldenRing_20260701_210000" in {r[0] for r in idx3["rows"]})
check("the merge never writes to disk (no npz, nothing under LOCALAPPDATA)",
      "savez" not in fsrc(SRC, "_shelf_index", TREE)
      and "_data_dir" not in fsrc(SRC, "_shelf_index", TREE)
      and "Nothing is written to disk" in fsrc(SRC, "_shelf_index", TREE))

hits = ns["_shelf_query"]("when did someone rage quit in overtime")
check("a question in the night's own words ranks that night's rage-quit "
      "second first (the stretch at 640 s or the chapter there)",
      hits and hits[0]["file"] == "RocketLeague_20260904_233625"
      and 630 <= hits[0]["t"] <= 660)
check("a hit carries base, game, when, t, kind, text, why, score, and a "
      "1-based n the answer cites by",
      {"file", "base", "path", "game", "when", "t", "t_ms", "b_ms", "kind",
       "text", "why", "score", "exact", "n"} <= set(hits[0])
      and hits[0]["n"] == 1 and hits[0]["game"] == "Rocket League"
      and hits[0]["t_ms"] == int(hits[0]["t"] * 1000))
check("no night takes more than three seats",
      max(sum(1 for h in hits if h["file"] == b)
          for b in {h["file"] for h in hits}) <= 3)
hg = ns["_shelf_query"]("what did Godskin say")
check("A NAME NEVER DEPENDS ON A VECTOR: the exact-word hits come first, "
      "marked exact, above any cosine, on both nights that say it",
      hg and hg[0]["exact"] is True and hg[0]["score"] >= 1.0
      and {h["file"] for h in hg if h["exact"]} == {
          "Hearthstone_20260819_200623", "EldenRing_20260701_210000"}
      and all(h["score"] >= 1.0 for h in hg if h["exact"])
      and "Godskin" in hg[0]["why"])
hc = ns["_shelf_query"]("the comeback when we were down three")
check("a chapter and the stretch inside it collapse to one seat per ten "
      "seconds", hc and len([h for h in hc if h["file"].startswith("Rocket")
                            and int(h["t"] // 10) == 150]) == 1)
check("a common word is not an exact hit (only rare or capitalised words "
      "are looked up)", not any(h["exact"] and h["why"].startswith("the word 'the'")
                                for h in ns["_shelf_query"]("the the match")))
check("a short question is nothing", ns["_shelf_query"]("a") == [])
_q_srv = ns["_emb_srv"]
ns["_emb_srv"] = lambda budget=60: None
hw = ns["_shelf_query"]("Godskin")
check("the embedder would not wake: the exact words still answer, never "
      "an empty box", hw and all(h["exact"] for h in hw))
ns["_emb_srv"] = _q_srv

# =========================================================================
print("\n--- the answer: the describer over the excerpts, gated ---")
asked_llm = []


def fake_ask_llm(system, user, schema, max_tokens=900, wait=0):
    asked_llm.append((system, user, schema, max_tokens, wait))
    return ({"answer": "It was the overtime one [2].", "cites": [2]}, "")


ns["_ask_llm"] = fake_ask_llm
ns["_game_has_focus"] = lambda: True
a, c, w = ns["_shelf_answer"]("q", hits)
check("A GAME HAS THE SCREEN: no answer, the describer is not asked",
      a is None and c == [] and "game has the screen" in w and asked_llm == [])
ns["_game_has_focus"] = lambda: False
ns["_AI"]["busy"] = ("thinking", "night.mp4")
a, c, w = ns["_shelf_answer"]("q", hits)
check("THE CARD IS BUSY: no answer, the one-model-one-job wording",
      a is None and "one model cannot do two things at once" in w
      and asked_llm == [])
ns["_AI"]["busy"] = ("listening", "the librarian \u00b7 night.mp4")
a, c, w = ns["_shelf_answer"]("q", hits)
check("A TAIL VISIT holds nothing: the screen or the librarian in the seat "
      "never stands between a question and the card",
      a is not None and len(asked_llm) == 1)
ns["_AI"]["busy"] = ("listening", "the screen \u00b7 night.mp4")
check("...(the screen visit too)", ns["_shelf_card_why"]() == "")
ns["_AI"]["busy"] = ("listening", "night.mp4")
check("...but the ears on a night do (the abort path would kill a private "
      "describer under them)", "cannot do two things" in ns["_shelf_card_why"]())
ns["_AI"]["busy"] = None
asked_llm.clear()
a, c, w = ns["_shelf_answer"]("when did someone rage quit", hits)
sysm, user, schema, mx, wt = asked_llm[-1]
check("free: the describer is asked through _ask_llm with the numbered "
      "excerpts and the question",
      len(asked_llm) == 1 and user.startswith("Question: when did someone rage quit")
      and "\n[1] " in user and "\n[2] " in user
      and "Rocket League" in user and "(line)" in user or "(chapter)" in user)
check("...the cite rule is strict: ONLY the excerpts, cite by number, "
      "never invent, STRICT JSON", "ONLY the numbered excerpts" in sysm
      and "by number" in sysm and "Never invent a night, a time or a quote"
      in sysm and "STRICT JSON" in sysm)
check("...the schema fences answer + cites, 700 tokens, a watched wait",
      schema["required"] == ["answer", "cites"] and mx == 700 and wt == 150)
check("the answer and its cites come back as hit numbers",
      a == "It was the overtime one [2]." and c == [2] and w == "")
check("each excerpt row carries the night, the game and the second, so "
      "the model has nothing to invent",
      re.search(r"\[1\] \d\d \w\w\w \d{4} Rocket League \d+:\d\d \(", user))
ns["_ask_llm"] = lambda *a, **k: ({"answer": "Yes, it was on the ninth.",
                                   "cites": [99]}, "")
a, c, w = ns["_shelf_answer"]("q", hits)
check("a cite that points nowhere is dropped, and an affirmative with no "
      "cite becomes the not-found sentence",
      c == [] and a.startswith("LORE could not tie that answer"))
ns["_ask_llm"] = lambda *a, **k: ({"answer": "No, nothing here says so.",
                                   "cites": []}, "")
a, c, w = ns["_shelf_answer"]("q", hits)
check("an honest negative survives with no cites",
      a == "No, nothing here says so." and c == [])
ns["_ask_llm"] = lambda *a, **k: ({"answer": "See [1] and [3].", "cites": []}, "")
a, c, w = ns["_shelf_answer"]("q", hits)
check("a [n] written in the prose counts as a cite", c == [1, 3])
ns["_ask_llm"] = lambda *a, **k: (None, "the sage would not wake")
a, c, w = ns["_shelf_answer"]("q", hits)
check("the model gave nothing: None and its why", a is None and w)
check("nothing to answer from is said, not asked",
      ns["_shelf_answer"]("q", [])[2] == "nothing to answer from")

# =========================================================================
print("\n--- the bridge: ask_shelf / ask_shelf_poll ---")
ask_shelf = extract_method(SRC, "_JsApi", "ask_shelf", ns, TREE)
ask_shelf_poll = extract_method(SRC, "_JsApi", "ask_shelf_poll", ns, TREE)


class FakeCtl:
    session = None


class FakeApi:
    _ctl = FakeCtl()

    def __init__(self):
        self.lib_calls = []

    def ask_library(self, q):
        self.lib_calls.append(q)
        return {"ok": True, "answer": "old road", "hits": [], "tag": id(self)}


api = FakeApi()
MODEL[0] = None
r0 = ask_shelf(api, "  rage quit  ")
check("NO MODEL: ask_shelf IS ask_library - the very object it returned, "
      "for the stripped question", r0 is not None and r0["tag"] == id(api)
      and api.lib_calls == ["rage quit"] and "shelf" not in r0)
MODEL[0] = ("exe", "gguf")
ns["_shelf_busy_why"] = lambda ctl=None: ""
ns["_shelf_answer"] = lambda q, h: ("Answer [1].", [1], "")
r1 = ask_shelf(api, "when did someone rage quit in overtime")
check("with the model: hits at once, a ticket, answering, the shelf mark",
      r1["ok"] is True and r1["shelf"] is True and r1["hits"]
      and r1["ticket"] and r1["answering"] is True and r1["why"] == ""
      and api.lib_calls == ["rage quit"])
time.sleep(0.3)
p1 = ask_shelf_poll(api, r1["ticket"])
check("the poll hands the answer over when it lands, with its cites",
      p1["state"] == "done" and p1["answer"] == "Answer [1]." and p1["cites"] == [1])
check("an unknown ticket is gone, never an error",
      ask_shelf_poll(api, "nope")["state"] == "gone")
r2 = ask_shelf(api, "rage quit", want_answer=False)
check("want_answer=False: hits only, no ticket, no thread",
      r2["hits"] and r2["ticket"] is None and r2["answering"] is False)
ns["_shelf_busy_why"] = lambda ctl=None: "a game has the screen"
r3 = ask_shelf(api, "rage quit")
check("gated: hits with the why, no ticket", r3["hits"] and r3["ticket"] is None
      and r3["answering"] is False and r3["why"] == "a game has the screen")
_q_srv2 = ns["_emb_srv"]
ns["_emb_srv"] = lambda budget=60: None
r4 = ask_shelf(api, "zzzz qqqq")
ns["_emb_srv"] = _q_srv2
check("nothing matches: ok False with a why, still the shelf shape",
      r4["ok"] is False and r4["shelf"] is True and r4["hits"] == []
      and "nothing on the shelf matches" in r4["why"])
_q_idx = ns["_shelf_index"]
ns["_shelf_index"] = lambda: None
r5 = ask_shelf(api, "zzzz qqqq")
ns["_shelf_index"] = _q_idx
check("nothing indexed yet: ask_shelf hands back ask_library's very object "
      "- the box is never worse than 3.31 (drop D)",
      r5 is not None and r5.get("tag") == id(api) and "shelf" not in r5
      and api.lib_calls[-1] == "zzzz qqqq"
      and "still reading the nights in" not in SRC)
check("an empty question is refused", ask_shelf(api, " ")["ok"] is False)
extract(SRC, "_shelf_busy_why", ns, TREE)
class RecCtl:
    session = object()
class RecApi(FakeApi):
    _ctl = RecCtl()
check("the gate: a recording running, a game on the screen, a job in hand, "
      "the auditor at a question, one answer at a time",
      "recording is running" in ns["_shelf_busy_why"](RecApi._ctl)
      and (ns.__setitem__("_game_has_focus", lambda: True) or
           "game has the screen" in ns["_shelf_busy_why"](FakeCtl()))
      and (ns.__setitem__("_game_has_focus", lambda: False) or
           ns["_AI"].__setitem__("busy", ("describing", "x.mp4")) or
           "cannot do two things at once" in ns["_shelf_busy_why"](FakeCtl()))
      and (ns["_AI"].__setitem__("busy", None) or
           ns["_AUD_ASK"].__setitem__("path", "p") or
           "auditor" in ns["_shelf_busy_why"](FakeCtl()))
      and (ns["_AUD_ASK"].__setitem__("path", None) or
           ns["_SHELF_ANS"].__setitem__("t", {"state": "thinking", "at": time.time()}) or
           "one answer at a time" in ns["_shelf_busy_why"](FakeCtl()))
      and (ns["_SHELF_ANS"].pop("t") and ns["_shelf_busy_why"](FakeCtl()) == ""))
ns["_SHELF_ANS"]["self"] = {"state": "thinking", "at": time.time()}
check("the answer thread never refuses itself: the card's reasons alone "
      "gate _shelf_answer, one-at-a-time is the bridge's",
      ns["_shelf_card_why"]() == "" and "one answer at a time"
      in ns["_shelf_busy_why"](FakeCtl())
      and "one answer at a time" not in fsrc(SRC, "_shelf_answer", TREE)
      and "why = _shelf_card_why()" in fsrc(SRC, "_shelf_answer", TREE))
ns["_SHELF_ANS"].pop("self")
check("state() carries librarian_ready for the box, cheaply",
      '"librarian_ready": _emb_ready(),' in SRC
      and "now - _EMB[\"ready_t\"] > 10" in fsrc(SRC, "_emb_ready", TREE))
MODEL[0] = None
ns["_EMB"]["ready"] = None
check("_emb_ready: False without the model, remembered ten seconds",
      ns["_emb_ready"]() is False
      and (MODEL.__setitem__(0, ("e", "g")) or ns["_emb_ready"]() is False))
ns["_EMB"]["ready"] = None
check("...True with it", ns["_emb_ready"]() is True)
MODEL[0] = None
ns["_EMB"]["ready"] = None

# =========================================================================
print("\n--- DORMANT WITHOUT THE MODEL: every road answers as HEAD ---")
if HSRC:
    same = []
    for f in ("_search_index", "_search_words", "_hud_owing", "_hud_topup_one",
              "_outcome_owing", "_outcome_topup_one",
              "_ask_idle_tick", "_desc_keep_tick", "_read_sidecar",
              "_ai_sidecar", "_ai_sidecar_fresh", "_model_have",
              "_free_port", "_DescServer", "_AsrServer", "_ask_negish",
              "_moment_of"):
        same.append(fsrc(HSRC, f, HTREE) == fsrc(SRC, f, TREE))
    check("the roads the box, the tail and the sidecars already used are "
          "byte-identical to HEAD (17 functions and classes)", all(same))
    _ask_new = fsrc(SRC, "_ask_llm", TREE)
    _ask_old = fsrc(HSRC, "_ask_llm", HTREE)
    check("_ask_llm is HEAD's plus the tail exemption in the borrowed "
          "branch: a screen or librarian visit holds no card, so the "
          "borrowed warm describer answers instead of refusing (drop D)",
          _ask_old.replace(
              '        _busy = _AI.get("busy")\n'
              '        if _busy:\n',
              '        _busy = _AI.get("busy")\n'
              '        # a tail visit (the screen, the librarian) holds no card: the\n'
              '        # borrowed warm describer answers at once, so no refusal there\n'
              '        if _busy and not str(_busy[1] or "").startswith(\n'
              '                ("the screen \\u00b7", "the librarian \\u00b7")):\n')
          == _ask_new and _ask_old != _ask_new)
    for m in ("ask_library", "ask_video", "search_words", "models_status",
              "models_fetch", "have_flags"):
        same.append(msrc(HSRC, "_JsApi", m, HTREE) == msrc(SRC, "_JsApi", m, TREE))
    check("...and so are ask_library, ask_video, search_words, models_status, "
          "models_fetch, have_flags", all(same[-6:]))
    import difflib
    ha = fsrc(HSRC, "_ai_tick", HTREE).splitlines()
    na = fsrc(SRC, "_ai_tick", TREE).splitlines()
    added = [ln for ln in difflib.unified_diff(ha, na, lineterm="", n=0)
             if ln.startswith("+") and not ln.startswith("+++")]
    removed = [ln for ln in difflib.unified_diff(ha, na, lineterm="", n=0)
               if ln.startswith("-") and not ln.startswith("---")]
    check("_ai_tick differs from HEAD ONLY by the index branch, the once-a-"
          "beat _emb_paths, the work() branch and the busy label",
          all(any(k in ln for k in ("emb_ok", "_emb_owing(p)", '("index", p)',
                                    "_qdirty", "ai_state.json", "5 Sep 2026",
                                    "no dirt, no write", "_EMB_STANDDOWN",
                                    "_spawn(\"listening\", p, mt)", "return",
                                    'tail == "index"', "_emb_one(path)",
                                    'elif kind == "hearing":',
                                    "_emb_idle_tick()", "once a beat",
                                    "the librarian", "CPU only", "card untouched",
                                    "nothing else rides"))
              for ln in added)
          and removed == ['-                                      "index": "the index"}.get(tail, tail)',
                          '-                if kind == "hearing":'])
    hs = fsrc(HSRC, "_ai_tick", HTREE)
    check("the HEAD tail spawned on hud/outcomes only; the new tail keeps "
          "that branch verbatim ahead of the index",
          '_AI["tail"] = ("screen", p)' in hs and "_emb_owing" not in hs
          and fsrc(SRC, "_ai_tick", TREE).count('_AI["tail"] = ("screen", p)') == 1)
    check("_ATTIC_OF is HEAD's: emb stays outside the attic",
          re.search(r"^_ATTIC_OF = \{.*?\}", HSRC, re.S | re.M).group(0)
          == re.search(r"^_ATTIC_OF = \{.*?\}", SRC, re.S | re.M).group(0)
          and '"emb"' not in re.search(r"^_ATTIC_OF = \{.*?\}", SRC,
                                       re.S | re.M).group(0))
    check("the word-index drops now drop the shelf too, at every HEAD site "
          "and no other",
          HSRC.count('_AI["index"] = None') == 9
          and SRC.count('_AI["index"] = None') == 9
          and len(re.findall(r'^([ \t]*)_AI\["index"\] = None[^\n]*\n'
                             r'\1_AI\["shelf"\] = None$', SRC, re.M)) == 9)
    check("state() is HEAD's plus the one flag",
          msrc(HSRC, "_JsApi", "state", HTREE).replace(
              '                "version": APP_VERSION}',
              '                "librarian_ready": _emb_ready(),\n'
              '                "version": APP_VERSION}')
          == msrc(SRC, "_JsApi", "state", TREE))
else:
    check("(no git: the HEAD parity block was skipped)", False)
MODEL[0] = None
ns["_EMB"]["srv"] = None
extract(SRC, "_emb_srv", ns, TREE)          # the real one, not the fake
srv_calls = []
ns["_EmbServer"] = lambda *a, **k: srv_calls.append(1)
check("no model: _emb_srv never builds a server, _emb_owing is False for "
      "every night, the doze tick is silent, _emb_ready is False",
      ns["_emb_srv"]() is None and srv_calls == []
      and all(_emb_owing(v) is False for v in (V_RL, V_HS, V_ER, V_NN))
      and (ns["_emb_idle_tick"]() or True) and ns["_emb_ready"]() is False)
check("no model: ask_shelf is ask_library (again, after the model came and "
      "went)", ask_shelf(api, "x")["tag"] == id(api))
MODEL[0] = ("exe", "gguf")
ns["_EmbServer"] = lambda *a, **k: type("Dead", (), {
    "start": lambda self, budget=90: (srv_calls.append("start"), False)[1],
    "pr": None})()
ns["_EMB"]["srv"] = None
ns["_EMB"]["down_t"] = 0.0
_before = [_emb_owing(v) for v in (V_RL, V_HS, V_ER, V_NN)]
_t_down = time.time()
check("a start that fails is remembered: _emb_srv None, down_t stamped, "
      "and _emb_owing answers False for every night for ten minutes - one "
      "dead server costs one visit, not one per night (drop D)",
      ns["_emb_srv"]() is None and srv_calls == ["start"]
      and ns["_EMB"].get("down_t", 0) >= _t_down
      and all(_emb_owing(v) is False for v in (V_RL, V_HS, V_ER, V_NN)))
ns["_EMB"]["down_t"] = time.time() - 601
check("...and after the stand-down the owe gate judges as before",
      [_emb_owing(v) for v in (V_RL, V_HS, V_ER, V_NN)] == _before)
ns["_EMB"]["down_t"] = 0.0
check("_emb_srv's check-then-spawn sits under _EMB_LOCK (two callers in "
      "the same second never spawn two servers on 8910)",
      "with _EMB_LOCK:" in fsrc(SRC, "_emb_srv", TREE)
      and "_EMB_LOCK = threading.Lock()" in SRC
      and fsrc(SRC, "_emb_srv", TREE).index("with _EMB_LOCK:")
      < fsrc(SRC, "_emb_srv", TREE).index("_EMB.get(\"srv\")"))
check("_EmbServer.start waits by the wall clock, not by iteration count "
      "(a 3 s health probe used to stretch the budget threefold)",
      "while time.time() - t0_up < max(5, int(budget)):"
      in fsrc(SRC, "_EmbServer", TREE)
      and "for _ in range(max(5, int(budget))):"
      not in fsrc(SRC, "_EmbServer", TREE))
check("_shelf_query merges a title or a summary by kind, everything else "
      "by the ten-second bucket (drop D)",
      'key = ((h["file"], h["kind"])\n'
      '               if h.get("kind") in ("title", "summary")\n'
      '               else (h["file"], int(h["t"] // 10)))'
      in fsrc(SRC, "_shelf_query", TREE))
MODEL[0] = None
srv_calls[:] = []
check("_EmbServer.start refuses without the model (no spawn, no port sweep)",
      (ns.__setitem__("_EmbServer", extract_class(SRC, "_EmbServer", {
          "_DescServer": ns["_DescServer"], "_emb_paths": lambda: None,
          "_EMB_PORT": 8910, "_free_port": lambda p: srv_calls.append("port"),
          "_popen": lambda *a, **k: srv_calls.append("spawn"),
          "os": os, "time": time, "subprocess": subprocess, "log": print,
          "_AI": ns["_AI"], "json": json, "_urlreq": _urlreq, "_EMB_DIM": 256}))
       or ns["_EmbServer"]().start() is False) and srv_calls == [])

# =========================================================================
print("\n--- the UI, read from its source ---")
check("the stamps: 3.32 in both mocks, lore.py APP_VERSION 3.32, no 3.31 "
      "version left", USRC.count("version:'3.32'") == 2
      and "version:'3.31'" not in USRC and 'APP_VERSION = "3.32"' in SRC)
check("the MOCK bridge carries ask_shelf, ask_shelf_poll and "
      "librarian_ready, so the harness box is never dead",
      "ask_shelf:async(q)=>window.__mockShelf||{ok:true,shelf:true," in USRC
      and "ask_shelf_poll:async(t)=>window.__mockShelfAns||{state:'done'," in USRC
      and "librarian_ready:true,version:'3.32'" in USRC)
ab = USRC[USRC.index("const askShelfPaint=async(r,q)=>{"):USRC.index(
    "  sw.addEventListener('input',()=>{")]
check("ask() takes the shelf road when the bridge has it, else the old "
      "call, and the old paint stands untouched below",
      "if(api.ask_shelf)r=await api.ask_shelf(FQ.any?(FQ.q||q):q);" in ab
      and "else if(api.ask_library)r=await api.ask_library(FQ.any?(FQ.q||q):q);" in ab
      and "if(r&&r.shelf){ await askShelfPaint(r,q); return; }" in ab
      and "if(!r||(!r.ok&&!(r.hits||[]).length)){" in ab
      and "pa.addEventListener('click',()=>reelStart(cites.map(c=>({v:c.v,t:c.t}))));" in ab)
check("TWO BEATS: the hits paint first as numbered srich rows - game · "
      "night · second · why - each a jump to its second",
      "qrow.append(el('span','shn','['+c.n+']'));" in ab
      and "esc(c.v.gname)+' \\u00b7 '+esc(fmtWhen(c.v.mtime))" in ab
      and "(c.t?' \\u00b7 '+fmtT(c.t):'')+(c.h.why?' \\u00b7 '+esc(c.h.why):'')" in ab
      and "rw.addEventListener('click',()=>openViewer(c.v,c.t));" in ab
      and ab.index("c.node=rw; sres.append(rw);") < ab.index("const a=el('div','askans');"))
check("...then the answer polls in by ticket every 700 ms under them, with "
      "the counting wait, and stops when the question moves on",
      "p=await api.ask_shelf_poll(r.ticket);" in ab
      and "setTimeout(poll,700)" in ab and "window.askWait(w)" in ab
      and "if(S.searchQ!==q||!a.isConnected){stop();return;}" in ab)
check("...[n] in the answer links to its row and lights the cited rows; "
      "'play all' covers the cited hits only",
      "String(p.answer).split(/(\\[\\d+\\])/g)" in ab
      and "el('span','shcite'+(c?'':' dead'),seg)" in ab
      and "cited.forEach(c=>c.node.classList.add('cited'));" in ab
      and "reelStart(cited.map(c=>({v:c.v,t:c.t})))" in ab)
check("the gated case says why under the hits; nothing matching says so",
      "if(r.why)sres.append(el('div','vwhen',esc(r.why)));" in ab
      and "esc(r.why||'nothing on the shelf matches')" in ab)
check("the quiet no-librarian line rides the old road only, and the "
      "placeholder says which road", "the librarian is not here yet \\u2014 "
      "fetch it from the Models panel" in ab
      and "if(api.ask_shelf&&S.librarianReady===false)" in ab
      and "S.librarianReady=!!st.librarian_ready;" in USRC
      and "(S.librarianReady?'ask the shelf\\u2026 then press Enter'" in USRC)
check("the CSS for the number, the cite, the cited row and the quiet line",
      all(k in USRC for k in (".shn{", ".shcite{", ".shcite.dead{",
                              ".sresrow.cited{", ".shlib{")))
check("Words mode is untouched (runSearch as HEAD's ui.html)",
      "let hits=[];try{hits=await api.search_words(qw)||[];}catch(e){}" in USRC)
check("the Models panel renders every _MODEL_SETS row from models_status - "
      "the librarian needs no UI code",
      "sets.forEach(x=>{" in USRC and "if(api.models_status)st=await api.models_status();" in USRC
      and "x.tier==='reader'&&!x.have" in USRC)
check("no '</script' in the new inline strings",
      "</script" not in ab.replace("<\\/script", ""))
httpd.shutdown()
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

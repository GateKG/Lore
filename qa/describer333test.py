# -*- coding: utf-8 -*-
"""3.33 drop G - THE DESCRIBER IS QWEN3.8, proven.

One model for the describer and the thinker: the manifest's describer
set names the thinker's file plus unsloth's F16 projector, the default
describe_model is that file, the last-resort fallback prefers a qwen3.8
over a gemma, the projector follows the model (a describe_model set back
to gemma keeps its eye), and every describer-road ask carries THINKING
OFF (reasoning_budget 0 + enable_thinking False) - measured on his card:
Qwen3.8 handed a json_schema and left to think returns an EMPTY content.
The auditor's thinker keeps thinking on purpose: _AudServer is pinned
byte-identical to 5443273, and the other two chat bodies (the Anthropic
Messages call and the reader's relisten) are pinned flag-free. These lift
the REAL functions out of lore.py by name into a stub namespace and drive
them on a scratch models folder and a fake urlopen. No model, no port,
nothing under D:\\Records."""
import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)
OK = FAIL = 0
PARITY_BASE = "5443273"       # 3.33 drops E+F, the lore.py before drop G


def check(what, cond):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("FAIL:", what)


def node_of(tree, name):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) \
                and node.name == name:
            return node
    raise KeyError(name)


def fsrc(src, tree, name):
    n = node_of(tree, name)
    return "\n".join(src.splitlines()[n.lineno - 1:n.end_lineno])


def extract(src, tree, name, ns):
    exec(compile(textwrap.dedent(fsrc(src, tree, name)),
                 "<" + name + ">", "exec"), ns)
    return ns[name]


def assign_src(src, tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tg in node.targets:
                if isinstance(tg, ast.Name) and tg.id == name:
                    return ast.get_source_segment(src, node)
    raise KeyError(name)


def lift_assign(src, tree, name, ns):
    exec(compile(assign_src(src, tree, name), "<" + name + ">", "exec"), ns)
    return ns[name]


def msrc(src, tree, cls, meth):
    c = node_of(tree, cls)
    for node in c.body:
        if isinstance(node, ast.FunctionDef) and node.name == meth:
            return "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
    raise KeyError(cls + "." + meth)


try:
    HSRC = subprocess.run(["git", "show", PARITY_BASE + ":lore.py"], cwd=ROOT,
                          capture_output=True, timeout=60).stdout \
        .decode("utf-8", "replace").replace("\r\n", "\n")
except Exception:
    HSRC = ""
HTREE = ast.parse(HSRC) if HSRC else None
check("the parity base's lore.py could be read", len(HSRC) > 100000)

QWEN = "Qwen3.8-27B-i1-IQ4_XS-GGUF-Smaller.gguf"
QMM = "mmproj-Qwen3.8-27B-F16.gguf"
GEMMA = "google_gemma-3-27b-it-Q3_K_M.gguf"
GMM = "mmproj-gemma-3-27b-it-f16.gguf"

# ---------------------------------------------------------------- the stub
TD = tempfile.mkdtemp(prefix="desc333_")
MODELS = os.path.join(TD, "models")
RT = os.path.join(TD, "runtime", "llama")
os.makedirs(MODELS)
os.makedirs(RT)
EXE = os.path.join(RT, "llama-server.exe")
LOGS = []


def build(src, tree):
    ns = {"os": os, "json": json, "re": re, "time": time,
          "subprocess": subprocess, "threading": None,
          "SETTINGS": {},
          "log": lambda m: LOGS.append(m),
          "_AI": {"abort": False, "proc": None},
          "_models_dir": lambda for_writing=False: MODELS,
          "_model_file": lambda *p: os.path.join(MODELS, *p),
          "_runtime_dir": lambda name: os.path.join(TD, "runtime", name),
          "_free_port": lambda port: None,
          "_popen": lambda *a, **k: None}
    lift_assign(src, tree, "_HF", ns)
    lift_assign(src, tree, "_MODEL_SETS", ns)
    lift_assign(src, tree, "_DESC_PORT", ns)
    lift_assign(src, tree, "_DESC_CTX", ns)
    for nm in ("_describer_paths", "_desc_mmproj", "_model_have",
               "_DescServer", "_AudServer"):
        extract(src, tree, nm, ns)
    return ns


ns = build(SRC, TREE)


def shelf(*names):
    """Empty the scratch models folder and put these files on it."""
    for f in os.listdir(MODELS):
        os.remove(os.path.join(MODELS, f))
    for n in names:
        io.open(os.path.join(MODELS, n), "wb").write(b"x")


def exe(present=True):
    if present and not os.path.isfile(EXE):
        io.open(EXE, "wb").write(b"x")
    if not present and os.path.isfile(EXE):
        os.remove(EXE)


# ================================================== T1 _describer_paths
print("--- T1: _describer_paths - the Qwen default, the fallback ---")
exe(True)
ns["SETTINGS"].clear()
shelf(QWEN, GEMMA)
r = ns["_describer_paths"]()
check("the default describe_model is the thinker's Qwen file",
      r is not None and r[0] == EXE
      and os.path.basename(r[1]) == QWEN)
shelf("qwen3.8-27b-other-quant.gguf", GEMMA, QMM, GMM)
r = ns["_describer_paths"]()
check("default absent: the fallback prefers a qwen3.8 file over the gemma "
      "the alphabet would pick first",
      r is not None and os.path.basename(r[1]) == "qwen3.8-27b-other-quant.gguf")
shelf(GEMMA, GMM)
r = ns["_describer_paths"]()
check("only a gemma on the shelf: the fallback picks the gemma",
      r is not None and os.path.basename(r[1]) == GEMMA)
shelf(QWEN, GEMMA)
ns["SETTINGS"]["describe_model"] = GEMMA
r = ns["_describer_paths"]()
check("describe_model set to the gemma name -> the gemma",
      r is not None and os.path.basename(r[1]) == GEMMA)
ns["SETTINGS"].clear()
shelf(QMM, GMM)
check("a shelf of projectors only is no describer",
      ns["_describer_paths"]() is None)
shelf(QWEN)
exe(False)
check("no llama-server -> None even with the model there",
      ns["_describer_paths"]() is None)
exe(True)
shelf("zz-some-other.gguf", GMM)
r = ns["_describer_paths"]()
check("the last resort is still any non-projector gguf",
      r is not None and os.path.basename(r[1]) == "zz-some-other.gguf")
src_dp = fsrc(SRC, TREE, "_describer_paths")
check("the fallback no longer refuses the audit model by name",
      "audit_model" not in src_dp and "never adopt" not in src_dp
      and 'or "Qwen3.8-27B-i1-IQ4_XS-GGUF-Smaller.gguf")' in src_dp)
if HSRC:
    hns = build(HSRC, HTREE)
    shelf(QWEN, GEMMA)
    ns["SETTINGS"]["describe_model"] = GEMMA
    hns["SETTINGS"]["describe_model"] = GEMMA
    check("a describe_model set to gemma resolves exactly as it did at the "
          "parity base", ns["_describer_paths"]() == hns["_describer_paths"]())
    ns["SETTINGS"].clear()

# ================================================== T2 _desc_mmproj
print("--- T2: _desc_mmproj - the projector follows the model ---")
exe(True)
shelf(QWEN, QMM, GMM)
check("a Qwen describer gets the Qwen projector",
      ns["_desc_mmproj"]() == os.path.join(MODELS, QMM))
ns["SETTINGS"]["describe_model"] = GEMMA
shelf(QWEN, GEMMA, QMM, GMM)
check("a describe_model set back to gemma keeps gemma's eye",
      ns["_desc_mmproj"]() == os.path.join(MODELS, GMM))
ns["SETTINGS"].clear()
shelf(QWEN, GMM)
check("the Qwen projector missing -> None (the gemma one does not stand in)",
      ns["_desc_mmproj"]() is None)
shelf(QWEN)
check("no projector at all -> None", ns["_desc_mmproj"]() is None)
exe(False)
shelf(QMM)
check("with no llama-server the projector still resolves from the setting's "
      "name (the eye gate reads it before any server is up)",
      ns["_desc_mmproj"]() == os.path.join(MODELS, QMM))
exe(True)
shelf("qwen3.8-27b-other-quant.gguf", QMM)
check("any qwen3.8-named describer (case-blind) takes the Qwen projector",
      ns["_desc_mmproj"]() == os.path.join(MODELS, QMM))
ns["SETTINGS"]["describe_model"] = "QWEN3.8-custom.gguf"
shelf("QWEN3.8-custom.gguf", QMM)
check("...upper case too",
      ns["_desc_mmproj"]() == os.path.join(MODELS, QMM))
ns["SETTINGS"].clear()

# ================================================== T3 _DescServer.ask
print("--- T3: _DescServer.ask carries THINKING OFF on every road ---")
SENT = []


class _FakeResp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


class _FakeUrlreq:
    def __init__(self, answer):
        self.answer = answer

    def Request(self, url, data=None, headers=None, method=None):
        SENT.append({"url": url, "body": json.loads(data.decode("utf-8")),
                     "headers": headers or {}})
        return SENT[-1]

    def urlopen(self, req, timeout=0):
        SENT[-1]["timeout"] = timeout
        return _FakeResp(self.answer)


class _Alive:
    def poll(self):
        return None


def desc_ask(answer, **kw):
    ns["_urlreq"] = _FakeUrlreq(answer)
    srv = ns["_DescServer"]()
    srv.pr = _Alive()
    return srv.ask("SYS", "USER", **kw)


def off(body):
    return (body.get("reasoning_budget") == 0
            and isinstance(body.get("chat_template_kwargs"), dict)
            and body["chat_template_kwargs"].get("enable_thinking") is False)


ok_answer = {"choices": [{"message": {"content": '{"segments": []}'}}]}
SENT.clear()
t = desc_ask(ok_answer, max_tokens=300)
b = SENT[-1]["body"]
check("a plain ask: the pair is in the body and the answer comes back",
      off(b) and t == '{"segments": []}'
      and b["messages"][0] == {"role": "system", "content": "SYS"}
      and b["messages"][1] == {"role": "user", "content": "USER"}
      and b["max_tokens"] == 300 and b["temperature"] == 0.4
      and b["stream"] is False and "response_format" not in b
      and SENT[-1]["url"].endswith(":8907/v1/chat/completions"))
SENT.clear()
sch = {"type": "object", "properties": {"segments": {"type": "array"}}}
t = desc_ask(ok_answer, schema=sch)
b = SENT[-1]["body"]
check("a schema ask: the pair rides beside the json_schema grammar",
      off(b) and b["response_format"] == {
          "type": "json_schema",
          "json_schema": {"name": "answer", "schema": sch}})
SENT.clear()
t = desc_ask(ok_answer, images=[("at 01:02", "QUJD"), ("at 01:09", "REVG")],
             schema=sch, timeout=240)
b = SENT[-1]["body"]
u = b["messages"][1]["content"]
check("the eye's frame ask: the pair, the schema and the labelled images",
      off(b) and isinstance(u, list) and u[0] == {"type": "text",
                                                  "text": "USER"}
      and u[1] == {"type": "text", "text": "at 01:02"}
      and u[2] == {"type": "image_url", "image_url": {
          "url": "data:image/jpeg;base64,QUJD"}}
      and u[3]["text"] == "at 01:09"
      and u[4]["image_url"]["url"].endswith("REVG")
      and SENT[-1]["timeout"] == 240)
SENT.clear()
t = desc_ask({"choices": [{"message": {
    "content": "<think>no</think>\n  {\"a\": 1}  "}}]})
check("a stray <think> block is still stripped from the content",
      t == '{"a": 1}')
SENT.clear()
t = desc_ask({"choices": [{"message": {"content": "",
                                       "reasoning_content": "thought"}}]})
check("reasoning_content is NOT the describer's answer - an empty content "
      "stays empty (the flags exist so this never happens)", t == "")
SENT.clear()
ns["_urlreq"] = _FakeUrlreq(ok_answer)
srv = ns["_DescServer"]()
srv.pr = None
srv.borrowed = True
started = []
srv.start = lambda *a, **k: started.append(1) or True
t = srv.ask("s", "u")
check("a borrowed server (someone else's process, no handle) is asked "
      "without ever being respawned - and the pair rides that road too",
      not started and t == '{"segments": []}' and off(SENT[-1]["body"]))
srv2 = ns["_DescServer"]()
srv2.pr = None
started2 = []
srv2.start = lambda *a, **k: started2.append(1) or False
check("our own server that fell over gets one start() and a None when "
      "that fails", srv2.ask("s", "u") is None and started2 == [1])

# ================================================== T4 _AudServer.ask
print("--- T4: the auditor's thinker keeps thinking ---")
SENT.clear()
ns["_urlreq"] = _FakeUrlreq({"choices": [{"message": {
    "content": "verdict", "reasoning_content": "because"}}]})
asrv = ns["_AudServer"]()
t = asrv.ask("SYS", "USER")
b = SENT[-1]["body"]
check("no reasoning_budget in the thinker's body",
      "reasoning_budget" not in b
      and b["chat_template_kwargs"] == {"enable_thinking": False}
      and b["max_tokens"] == 2500 and b["temperature"] == 0.4)
check("it reads BOTH fields - content and reasoning_content",
      t == "verdict\nbecause"
      and SENT[-1]["url"].endswith(":8909/v1/chat/completions"))
check("_AudServer is byte-identical to the parity base",
      HSRC and fsrc(HSRC, HTREE, "_AudServer") == fsrc(SRC, TREE, "_AudServer"))
check("_aud_llm_paths is byte-identical to the parity base",
      HSRC and fsrc(HSRC, HTREE, "_aud_llm_paths")
      == fsrc(SRC, TREE, "_aud_llm_paths"))

# ================================================== T5 the manifest
print("--- T5: _MODEL_SETS - the describer set names the thinker's file ---")
sets = {it["key"]: it for it in ns["_MODEL_SETS"]}
d = sets.get("describer") or {}
tk = sets.get("thinker") or {}
HF = ns["_HF"]
check("the describer set: the Qwen file at the thinker's size and url, "
      "then unsloth's F16 projector",
      d.get("tier") == "full" and d.get("dir") == ""
      and d.get("files") == [
          (QWEN, HF % ("jrell/Qwen3.8-27B-i1-IQ4_XS-GGUF-Smaller", QWEN),
           13543869408),
          (QMM, HF % ("unsloth/Qwen3.8-27B-GGUF", "mmproj-F16.gguf"),
           927607488)])
check("its url pair reads as the two huggingface files",
      d["files"][0][1] == "https://huggingface.co/jrell/Qwen3.8-27B-i1-IQ4_XS"
                          "-GGUF-Smaller/resolve/main/" + QWEN
      and d["files"][1][1] == "https://huggingface.co/unsloth/Qwen3.8-27B-"
                              "GGUF/resolve/main/mmproj-F16.gguf")
check("the title and the what say what it is",
      d.get("title") == "The describer"
      and d.get("what") == "Qwen3.8-27B, the same model as the thinker: one "
                           "file on disk, chapters, titles and the eye")
check("no Gemma licence line on it any more; no gemma file in it",
      "licence" not in d and not any("gemma" in f[0].lower()
                                     for f in d["files"]))
check("the thinker set stays, and names the very same file (the fetcher "
      "sees it present and skips it)",
      tk.get("files") and tk["files"][0] == d["files"][0])
if HSRC:
    hsets = {it["key"]: it for it in lift_assign(HSRC, HTREE, "_MODEL_SETS",
                                                 {"_HF": HF})}
    check("every other set is the parity base's, byte for byte",
          all(hsets[k] == sets[k] for k in hsets if k != "describer")
          and set(hsets) == set(sets))
    check("the manifest keeps its order",
          [it["key"] for it in ns["_MODEL_SETS"]]
          == [it["key"] for it in lift_assign(HSRC, HTREE, "_MODEL_SETS",
                                              {"_HF": HF})])
shelf(QWEN, QMM)
ok_, got_, tot_ = ns["_model_have"](d)
check("_model_have walks the two files and wants their true sizes",
      ok_ is False and tot_ == 13543869408 + 927607488 and got_ == 0)

# ================================================== T6 the source pins
print("--- T6: every chat-completions body, classified ---")
s_desc = msrc(SRC, TREE, "_DescServer", "ask")
s_aud = msrc(SRC, TREE, "_AudServer", "ask")
s_claude = fsrc(SRC, TREE, "_claude")
s_rel = fsrc(SRC, TREE, "_aud_relisten")
check("_DescServer.ask: reasoning_budget 0 + enable_thinking False, once",
      s_desc.count('"reasoning_budget": 0,') == 1
      and s_desc.count('"chat_template_kwargs": {"enable_thinking": False},')
      == 1 and "THINKING OFF" in s_desc)
check("_AudServer.ask: enable_thinking False stays, no reasoning_budget "
      "(it concatenates reasoning_content on purpose)",
      "reasoning_budget" not in s_aud
      and '"chat_template_kwargs": {"enable_thinking": False},' in s_aud
      and 'msg.get("reasoning_content")' in s_aud)
check("_claude: the Anthropic Messages body carries neither flag (not a "
      "llama-server road)",
      "reasoning_budget" not in s_claude
      and "chat_template_kwargs" not in s_claude
      and '"messages": [{"role": "user", "content": user}],' in s_claude
      and (not HSRC or fsrc(HSRC, HTREE, "_claude") == s_claude))
check("_aud_relisten: the reader's audio body carries neither flag and is "
      "the parity base's (no reader changes)",
      "reasoning_budget" not in s_rel and "chat_template_kwargs" not in s_rel
      and '"input_audio"' in s_rel
      and (not HSRC or fsrc(HSRC, HTREE, "_aud_relisten") == s_rel))
check("those four are every chat-completions body in the file",
      SRC.count('"messages":') == 4
      and SRC.count("/v1/chat/completions") == 3
      and SRC.count('"reasoning_budget"') == 1
      and SRC.count('"enable_thinking": False') == 2)
s_start = msrc(SRC, TREE, "_DescServer", "start")
check("_DescServer.start's argv is model-neutral: -ngl auto, the 8192 "
      "window, the projector only when it shipped, nothing gemma-specific",
      '"-ngl", "auto",' in s_start and '"-c", str(_DESC_CTX)' in s_start
      and '+ (["--mmproj", mmp] if mmp else [])' in s_start
      and "gemma" not in s_start.lower()
      and 'log("The describer is up on port " + str(self.port)' in s_start
      and '+ ": " + os.path.basename(mdl) + ", loaded in "' in s_start
      and ns["_DESC_CTX"] == 8192)
check("_DescServer.start is the parity base's - only ask() moved",
      HSRC and msrc(HSRC, HTREE, "_DescServer", "start") == s_start)
s_ask = fsrc(SRC, TREE, "_ask_llm")
check("_ask_llm's borrowed and own roads both go through _DescServer.ask "
      "(covered), and so do the eye's frame asks",
      "probe = _DescServer()" in s_ask and "_DescServer(port=_ASK_PORT)" in s_ask
      and "srv.ask(system, user, max_tokens=max_tokens, schema=schema," in s_ask
      and SRC.count("images=") >= 3)
check("describe_model is read in two places and validated against no "
      "list - nothing to clamp",
      SRC.count('SETTINGS.get("describe_model")') == 2
      and "describe_model" in fsrc(SRC, TREE, "_desc_mmproj"))
check("_desc_mmproj names both projectors and picks by 'qwen3.8'",
      '"qwen3.8" in name.lower()' in fsrc(SRC, TREE, "_desc_mmproj")
      and '_model_file("mmproj-Qwen3.8-27B-F16.gguf")' in fsrc(
          SRC, TREE, "_desc_mmproj")
      and '_model_file("mmproj-gemma-3-27b-it-f16.gguf")' in fsrc(
          SRC, TREE, "_desc_mmproj"))
bat = io.open(os.path.join(ROOT, "qa", "run_all.bat"),
              encoding="utf-8").read()
check("the roster runs this suite after ears333audit",
      "ears333audit describer333test" in bat)

# ================================================== T7 the fetcher
print("--- T7: the fetcher - one file budgeted once, present where the "
      "reads look ---")
# The reviewer's two findings on the shared file: with both sets missing
# the budget summed the 13.5 GB file twice (28 GB asked of the drive, the
# bar ending near 52%), and an install that keeps its models beside the
# exe in Program Files checked presence only in the writing home - so the
# describer set would have fetched the thinker's file AGAIN into a folder
# the describer never reads. The real models_status / models_fetch are
# lifted out of the API class and driven on a scratch shelf; the files
# are 1 byte and os.path.getsize is told their pretended sizes.


def api_method(src, tree, meth):
    """The API class's method (whichever class holds it), as a plain
    function of (self, ...)."""
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            for m in n.body:
                if isinstance(m, ast.FunctionDef) and m.name == meth:
                    return textwrap.dedent("\n".join(
                        src.splitlines()[m.lineno - 1:m.end_lineno]))
    raise KeyError(meth)


class _SyncThread:
    def __init__(self, target=None, daemon=None, args=()):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


class _FakeThreading:
    Thread = _SyncThread

    class Lock:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False


SIZES = {}          # basename -> pretended byte size (the files are 1 byte)


class _OsPath:
    def __getattr__(self, k):
        return getattr(os.path, k)

    def getsize(self, p):
        n = os.path.getsize(p)      # raises OSError when absent, as real
        return SIZES.get(os.path.basename(p), n)


class _Os:
    path = _OsPath()

    def __getattr__(self, k):
        return getattr(os, k)


FOS = _Os()
WMODELS = os.path.join(TD, "models_w")      # the for_writing home
os.makedirs(WMODELS)


def build_fetch(src, tree, split_home=False):
    ns2 = {"os": FOS, "json": json, "re": re, "time": time,
           "subprocess": subprocess, "threading": _FakeThreading,
           "SETTINGS": {}, "log": lambda m: LOGS.append(m),
           "_AI": {"abort": False, "proc": None, "t_last": 0},
           "_models_dir": (lambda for_writing=False:
                           (WMODELS if (split_home and for_writing)
                            else MODELS)),
           "_model_file": lambda *p: os.path.join(MODELS, *p),
           "_runtime_dir": lambda name: os.path.join(TD, "runtime", name),
           "_data_dir": lambda: TD,
           "_free_bytes": lambda p: 10 ** 12,
           "_human_bytes": lambda n: str(n),
           "_RUNTIME_SETS": [], "DLS": []}
    for a in ("_HF", "_MODEL_SETS", "_DL"):
        lift_assign(src, tree, a, ns2)
    ns2["_DL_LOCK"] = _FakeThreading.Lock()
    extract(src, tree, "_model_have", ns2)
    for m in ("models_status", "models_fetch"):
        exec(compile(api_method(src, tree, m), "<" + m + ">", "exec"), ns2)

    def _dl_one(url, dest, size):       # "download" = create at full size
        ns2["DLS"].append((os.path.basename(dest), url, size))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        io.open(dest, "wb").write(b"x")
        SIZES[os.path.basename(dest)] = size
        return True
    ns2["_dl_one"] = _dl_one
    return ns2


def wshelf(*names):
    for f in os.listdir(WMODELS):
        os.remove(os.path.join(WMODELS, f))
    for n in names:
        io.open(os.path.join(WMODELS, n), "wb").write(b"x")


class _Api:
    pass


api = _Api()
FULL = 13543869408 + 927607488
SIZES.update({QWEN: 13543869408, QMM: 927607488})
fns = build_fetch(SRC, TREE)
shelf(QWEN, QMM)
st = fns["models_status"](api)
by = {x["key"]: x for x in st["sets"]}
check("status: the describer and the thinker both 'have' when the shared "
      "file and the projector are there",
      by["describer"]["have"] and by["thinker"]["have"]
      and by["describer"]["on_disk"] == FULL)
r = fns["models_fetch"](api, ["describer", "thinker"])
check("fetch: nothing to do when both are present",
      r == {"ok": False, "why": "everything asked for is already here"})
shelf(QWEN)
fns["DLS"].clear()
fns["_DL"]["busy"] = None
st = fns["models_status"](api)
by = {x["key"]: x for x in st["sets"]}
check("status: only the projector missing -> the describer is 0.93 GB "
      "short, the thinker still whole",
      not by["describer"]["have"] and by["thinker"]["have"]
      and by["describer"]["bytes"] - by["describer"]["on_disk"] == 927607488)
r = fns["models_fetch"](api, ["describer", "thinker"])
check("fetch: only the projector downloads, once, and the budget is its "
      "size", r["ok"] and r["bytes"] == 927607488
      and [x[0] for x in fns["DLS"]] == [QMM]
      and fns["_DL"]["total"] == 927607488 and fns["_DL"]["state"] == "done")
shelf()
fns["DLS"].clear()
fns["_DL"]["busy"] = None
r = fns["models_fetch"](api, ["describer", "thinker"])
check("fetch: both sets missing -> the 13.5 GB file downloads ONCE, then "
      "the projector", [x[0] for x in fns["DLS"]] == [QWEN, QMM]
      and fns["_DL"]["state"] == "done")
check("...and the budget counts that file ONCE: 14.5 GB asked of the "
      "drive, the bar ends at 100%",
      r["bytes"] == FULL and fns["_DL"]["total"] == FULL
      and r["bytes"] != 2 * 13543869408 + 927607488)
shelf()
fns["DLS"].clear()
fns["_DL"]["busy"] = None
fns["_free_bytes"] = lambda p: FULL + (3 << 30)     # room for 14.5, not 28
r = fns["models_fetch"](api, ["describer", "thinker"])
check("the free-space gate asks for what will land, not for the file "
      "twice", r["ok"] and [x[0] for x in fns["DLS"]] == [QWEN, QMM])
fns["_free_bytes"] = lambda p: 10 ** 12
# the split-home install: models beside the exe (read-only), fetch lands
# in the data folder - what is beside the exe must NOT come down again
sns = build_fetch(SRC, TREE, split_home=True)
shelf(QWEN)
wshelf()
sns["_DL"]["busy"] = None
r = sns["models_fetch"](api, ["describer"])
check("split-home: the thinker's file beside the exe is seen as present - "
      "only the projector comes down, into the writing home",
      r["ok"] and r["bytes"] == 927607488
      and [x[0] for x in sns["DLS"]] == [QMM]
      and os.path.isfile(os.path.join(WMODELS, QMM))
      and not os.path.isfile(os.path.join(WMODELS, QWEN)))
shelf(QWEN)
sns["DLS"].clear()
sns["_DL"]["busy"] = None
r = sns["models_fetch"](api, ["describer"])
check("split-home: what already landed in the writing home is not fetched "
      "twice either", r["ok"] and sns["DLS"] == []
      and sns["_DL"]["state"] == "done")
wshelf()
shelf(QWEN, QMM)
sns["DLS"].clear()
sns["_DL"]["busy"] = None
r = sns["models_fetch"](api, ["describer", "thinker"])
check("split-home: everything beside the exe -> nothing to fetch",
      r == {"ok": False, "why": "everything asked for is already here"})
# the pins: models_status untouched, models_fetch = the base's plus the
# two edits, _model_have untouched
_NEED_OLD = (
    '        need = 0\n'
    '        for kind, it in jobs:\n')
_NEED_NEW = (
    '        need = 0\n'
    '        seen = set()\n'
    '        for kind, it in jobs:\n')
_NEED_OLD2 = (
    '                _ok, got0, tot0 = _model_have(it)\n'
    '                need += max(0, tot0 - got0)\n')
_NEED_NEW2 = (
    '                # ONE FILE, BUDGETED ONCE (3.33 drop G). The describer\n'
    '                # and the thinker name the same 13.5 GB file; summing\n'
    '                # the two sets asked the drive for 28 GB where 14.5\n'
    '                # would land, and the bar would have ended near 52%.\n'
    '                # The download itself was always once - work() below\n'
    '                # finds the file present the second time round.\n'
    '                for rel, _url, size in it["files"]:\n'
    '                    p = _model_file(it["dir"], rel) if it["dir"] \\\n'
    '                        else _model_file(rel)\n'
    '                    if p in seen:\n'
    '                        continue\n'
    '                    seen.add(p)\n'
    '                    try:\n'
    '                        n = os.path.getsize(p)\n'
    '                    except OSError:\n'
    '                        n = 0\n'
    '                    if n != size:\n'
    '                        need += size\n')
_HAVE_OLD = (
    '                        if os.path.isfile(dest) \\\n'
    '                                and os.path.getsize(dest) == size:\n'
    '                            continue          # already here, in full\n')
_HAVE_NEW = (
    '                        # PRESENT WHERE THE READS LOOK, OR WHERE THE\n'
    '                        # WRITES LAND (3.33 drop G). An install that\n'
    '                        # keeps its models beside the exe in Program\n'
    '                        # Files fetches into the data folder; asking\n'
    '                        # only there would have fetched the thinker\'s\n'
    '                        # 13.5 GB file a second time for the describer\n'
    '                        # set, into a folder the describer never reads.\n'
    '                        have0 = (_model_file(it["dir"], rel) if it["dir"]\n'
    '                                 else _model_file(rel))\n'
    '                        if any(os.path.isfile(q)\n'
    '                               and os.path.getsize(q) == size\n'
    '                               for q in (have0, dest)):\n'
    '                            continue          # already here, in full\n')
s_fetch = msrc(SRC, TREE, "_JsApi", "models_fetch")
check("models_fetch carries the two edits, each once",
      s_fetch.count(_NEED_NEW) == 1 and s_fetch.count(_NEED_NEW2) == 1
      and s_fetch.count(_HAVE_NEW) == 1 and _NEED_OLD2 not in s_fetch
      and _HAVE_OLD not in s_fetch)
check("models_fetch is otherwise the parity base's, byte for byte",
      HSRC and msrc(HSRC, HTREE, "_JsApi", "models_fetch")
      == s_fetch.replace(_NEED_NEW, _NEED_OLD)
                .replace(_NEED_NEW2, _NEED_OLD2)
                .replace(_HAVE_NEW, _HAVE_OLD))
check("models_status and _model_have are the parity base's",
      HSRC and msrc(HSRC, HTREE, "_JsApi", "models_status")
      == msrc(SRC, TREE, "_JsApi", "models_status")
      and fsrc(HSRC, HTREE, "_model_have") == fsrc(SRC, TREE, "_model_have"))

# ================================================== T8 his install
print("--- T8: the projector beside the exe - the eye on his install ---")
# His install keeps its models beside the exe (Program Files, read-only
# to him): the real _models_dir / _model_file resolve there, so the eye
# is lit only if the drop-in puts the projector THERE. Mirrored on a
# scratch folder with the real functions and _here pointed at it.
APP = os.path.join(TD, "app")
BESIDE = os.path.join(APP, "ai", "models")
DATA = os.path.join(TD, "data")
os.makedirs(BESIDE)
os.makedirs(DATA)
hns2 = {"os": os, "sys": sys, "SETTINGS": {},
        "_here": lambda: APP, "_data_dir": lambda: DATA,
        "_runtime_dir": lambda name: os.path.join(TD, "runtime", name),
        "log": lambda m: LOGS.append(m)}
for nm in ("_models_dir", "_model_file", "_describer_paths",
           "_desc_mmproj"):
    extract(SRC, TREE, nm, hns2)
exe(True)
for n in (QWEN, GEMMA, GMM):
    io.open(os.path.join(BESIDE, n), "wb").write(b"x")
check("the install as it stands (no Qwen projector beside the exe): the "
      "describer resolves there but the eye is DARK - _desc_mmproj None",
      hns2["_models_dir"]() == BESIDE
      and hns2["_describer_paths"] is not None
      and os.path.basename(hns2["_describer_paths"]()[1]) == QWEN
      and hns2["_desc_mmproj"]() is None)
os.makedirs(os.path.join(DATA, "models"), exist_ok=True)
io.open(os.path.join(DATA, "models", QMM), "wb").write(b"x")
check("a projector in the data folder does not light it (the reads never "
      "look there while the beside-the-exe home holds files) - the "
      "drop-in must carry it", hns2["_desc_mmproj"]() is None)
io.open(os.path.join(BESIDE, QMM), "wb").write(b"x")
check("the projector beside the exe, as the drop-in ships it: the eye is "
      "lit - _desc_mmproj is that very path",
      hns2["_desc_mmproj"]() == os.path.join(BESIDE, QMM))
hns2["SETTINGS"]["describe_model"] = GEMMA
check("...and a describe_model set back to gemma keeps gemma's eye there",
      hns2["_desc_mmproj"]() == os.path.join(BESIDE, GMM))
hns2["SETTINGS"].clear()
# the drop-in itself, when it is staged on this machine
QMM_BYTES = 927607488
staged = os.path.join(os.path.expanduser("~"), "Downloads",
                      "Lore-update-3.33")
if os.path.isdir(staged):
    p = os.path.join(staged, "ai", "models", QMM)
    check("the staged drop-in carries the Qwen projector at its true size "
          "(927,607,488 B) under ai\\models - robocopy /E lands it beside "
          "the exe", os.path.isfile(p) and os.path.getsize(p) == QMM_BYTES)
else:
    print("   NOTE: no staged drop-in at " + staged + " - not checked here")
installed = os.path.join("C:\\", "Program Files", "Lore", "ai", "models", QMM)
try:
    lit = os.path.isfile(installed) and os.path.getsize(installed) == QMM_BYTES
except OSError:
    lit = False
print("   NOTE: the installed projector " + ("is there - the eye is lit"
      if lit else "is NOT there yet - it lands with the 3.33 install"))

print("\n%d ok, %d failed" % (OK, FAIL))
sys.exit(1 if FAIL else 0)

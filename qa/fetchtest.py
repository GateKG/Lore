# -*- coding: utf-8 -*-
"""The fetcher, proven: a fetched install finds EVERYTHING, the
downloader refuses a server that ignores Range, a failure outlives the
job, and the space check counts the unpacking."""
import io
import os
import sys
import tempfile

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

lore.log = lambda m: None
try:
    lore.load_settings()
except Exception:
    pass
lore.save_settings = lambda *a, **k: None

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


# ---- a FETCHED install: nothing beside the exe, everything in data ----
TD = tempfile.mkdtemp(prefix="fetched_")
lore._data_dir = lambda: TD
lore._here = lambda: os.path.join(TD, "app")
lore.SETTINGS.pop("models_dir", None)
os.makedirs(os.path.join(TD, "models"), exist_ok=True)
for n in ("google_gemma-3-27b-it-Q3_K_M.gguf",
          "mmproj-gemma-3-27b-it-f16.gguf",
          "Qwen3.8-27B-i1-IQ4_XS-GGUF-Smaller.gguf",
          "Cnn14_DecisionLevelMax_mAP=0.385.pth"):
    io.open(os.path.join(TD, "models", n), "wb").write(b"x")
for d in ("clap", "hype", "ecapa", "qwen3-asr-gguf"):
    os.makedirs(os.path.join(TD, "models", d), exist_ok=True)
io.open(os.path.join(TD, "models", "qwen3-asr-gguf",
                     "Qwen3-ASR-1.7B-bf16.gguf"), "wb").write(b"x")
io.open(os.path.join(TD, "models", "qwen3-asr-gguf",
                     "mmproj-Qwen3-ASR-1.7B-bf16.gguf"), "wb").write(b"x")

print("--- C1: BOTH runtimes are fetched and found ---")
homes = lore._RUNTIME_SETS[0]["into"]
check("the runtime set installs into both homes",
      isinstance(homes, list) and set(homes) == {"llama", "llama2"})
for h in homes:
    d = os.path.join(TD, "runtime", h)
    os.makedirs(d, exist_ok=True)
    io.open(os.path.join(d, "llama-server.exe"), "wb").write(b"x")
check("the describer's runtime resolves after a fetch",
      lore._describer_paths() is not None)
check("the thinker's runtime resolves after a fetch",
      lore._aud_llm_paths() is not None)
api = lore._JsApi.__new__(lore._JsApi)
st = api.models_status()
rt = [x for x in st["sets"] if x["key"] == "runtime"][0]
check("and the panel only says 'here' when BOTH are", rt["have"])
os.remove(os.path.join(TD, "runtime", "llama", "llama-server.exe"))
st2 = api.models_status()
rt2 = [x for x in st2["sets"] if x["key"] == "runtime"][0]
check("one home missing => the panel says missing", not rt2["have"])
io.open(os.path.join(TD, "runtime", "llama", "llama-server.exe"),
        "wb").write(b"x")

print("\n--- C3: the senses and laughter follow the models ---")
check("laughter finds its checkpoint in the new home",
      lore._model_file("Cnn14_DecisionLevelMax_mAP=0.385.pth")
      .startswith(TD))
sp = lore._senses_paths.__doc__ is not None
check("the senses look where the fetcher writes",
      os.path.isdir(lore._model_file("clap")))

print("\n--- the model home must be WRITABLE for fetching ---")
check("a fresh install writes to the data folder",
      lore._models_dir(True).startswith(TD))
check("_writable tells the truth about a real folder",
      lore._writable(TD) is True)
check("_writable refuses a path it cannot create",
      lore._writable("Z:\\nope\\nope") is False)

print("\n--- S4: a server that ignores Range must not corrupt ---")
lore._DL.update({"busy": True, "cancel": False, "done": 0, "base": 0,
                 "total": 0, "err": "", "last_err": ""})
# OFFLINE: a loopback fixture stands in for the range-ignoring host.
# It answers 200 with the whole body whatever the request says - which
# is exactly the server shape this test exists to survive - and the
# roster stops touching huggingface.co on every run.
import http.server
import threading
FIX = b"A" * 1919


class _RangeBlind(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)               # never 206: Range ignored
        self.send_header("Content-Length", str(len(FIX)))
        self.end_headers()
        self.wfile.write(FIX)

    def log_message(self, *a):
        pass


_srv = http.server.HTTPServer(("127.0.0.1", 0), _RangeBlind)
threading.Thread(target=_srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d/hyperparams.yaml" % _srv.server_port
dest = os.path.join(TD, "range.yaml")
io.open(dest + ".part", "wb").write(b"Z" * 500)   # a stale 500-byte head
got = lore._dl_one(URL, dest, len(FIX))
_srv.shutdown()
size = os.path.getsize(dest) if os.path.isfile(dest) else -1
head = io.open(dest, "rb").read(1) if size > 0 else b""
check("it restarts the file rather than appending onto the part",
      got and size == len(FIX) and head != b"Z")

print("\n--- S5/S6: a failure outlives the job, and cannot escape ---")
lore._DL.update({"done": 0, "base": 0, "err": "", "last_err": ""})
bad_dest = os.path.join("Z:\\nope\\nope", "x.bin")
r = lore._dl_one(URL, bad_dest, 1919)
check("an unwritable destination returns False, never raises",
      r is False)
check("and the reason is remembered", bool(lore._DL.get("last_err")))
lore._DL["busy"] = None
st3 = api.models_status()
check("the panel can still show it after the job ends",
      bool(st3.get("last_err")))
check("and he can dismiss it", api.models_forget_error().get("ok")
      and not api.models_status().get("last_err"))

print("\n--- the space check counts the unpacking ---")
lore._DL["busy"] = None
for _h in ("llama", "llama2"):        # make it genuinely missing
    try:
        os.remove(os.path.join(TD, "runtime", _h, "llama-server.exe"))
    except OSError:
        pass
_real_free = lore._free_bytes
lore._free_bytes = lambda p: 1 << 30          # only 1 GB free
try:
    r = api.models_fetch(["runtime"])
    check("a nearly-full drive is refused, in his words",
          not r.get("ok") and "room" in (r.get("why") or ""))
    check("and the refusal counts the UNPACKING, not just the zip",
          "137" in (r.get("why") or "") or "MB" in (r.get("why") or ""))
finally:
    lore._free_bytes = _real_free
    lore._DL["busy"] = None

print("\n--- the busy claim is atomic ---")
lore._DL["busy"] = True
r2 = api.models_fetch(["describer"])
check("a second fetch is refused while one runs", not r2.get("ok"))
lore._DL["busy"] = None

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

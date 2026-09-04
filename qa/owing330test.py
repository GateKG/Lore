# -*- coding: utf-8 -*-
"""3.30: the empty review that owed itself forever.

Drives the REAL _ins_owing_raw out of lore.py (AST-extracted, its
disk helpers stubbed to a scratch shelf) and proves the loop the
production log showed: an EMPTY review on a night whose transcript
carries a reader generation was re-owed on every beat, because the
empty writer never stamped src_stt and the reader clause read the
missing stamp as "built on reader zero". Then proves the fix settles
it in exactly one pass and that a real re-read still re-owes.
"""
import ast
import io
import json
import os
import re
import sys
import tempfile
import textwrap
import time

SRC_P = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lore.py")
SRC = io.open(SRC_P, encoding="utf-8").read()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def extract(name, ns):
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<x>", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


# ---- a scratch shelf: one video, its sidecars beside it ----------------
tmp = tempfile.mkdtemp(prefix="lore_owing_")
VID = os.path.join(tmp, "grunn_20260824_223109.mp4")
io.open(VID, "wb").write(b"\0" * 200000)
os.utime(VID, (1000000.0, 1000000.0))


def side(kind):
    return os.path.join(tmp, "grunn_20260824_223109." + kind + ".json")


def put(kind, doc, mt=None):
    io.open(side(kind), "w", encoding="utf-8").write(
        json.dumps(doc, ensure_ascii=False))
    if mt is not None:
        os.utime(side(kind), (mt, mt))


_INS_GENERATION = int(re.search(r"^_INS_GENERATION\s*=\s*(\d+)", SRC,
                                re.M).group(1))
_STT_READER = int(re.search(r"^_STT_READER\s*=\s*(\d+)", SRC,
                            re.M).group(1))
_STT_V = int(re.search(r"^_STT_V\s*=\s*(\d+)", SRC, re.M).group(1))
_STT_ENGINE = re.search(r'^_STT_ENGINE\s*=\s*"([^"]+)"', SRC,
                        re.M).group(1)

ns = {"os": os, "json": json, "re": re, "time": time,
      "_ai_sidecar": lambda p, k: side(k),
      "_desc_mmproj": lambda: "mmproj",
      "_INS_GENERATION": _INS_GENERATION,
      "_STT_READER": _STT_READER, "_STT_V": _STT_V,
      "_TITLE_GEN": int(re.search(r"^_TITLE_GEN\s*=\s*(\d+)", SRC,
                                     re.M).group(1)),
      "_STT_ENGINE": _STT_ENGINE, "_STT_RD_CACHE": {},
      "log": lambda *a, **k: None}
_stt_reader_of = extract("_stt_reader_of", ns)
_ins_owing_raw = extract("_ins_owing_raw", ns)

# the transcript: reader 2, four lines - exactly grunn's shape
put("stt", {"v": _STT_V, "engine": _STT_ENGINE, "reader": 2,
            "segments": [{"a": 1000, "b": 2000, "t": "yalla"},
                         {"a": 3000, "b": 4000, "t": "okay"},
                         {"a": 5000, "b": 6000, "t": "no"},
                         {"a": 7000, "b": 8000, "t": "wait"}]},
    mt=1000100.0)
check("the scratch transcript reads back as reader 2",
      _stt_reader_of(VID) == 2)

print("--- the loop, as the shelf had it ---")
put("ins", {"v": 3, "empty": True, "complete": True}, mt=1000200.0)
check("an EMPTY review with no src_stt stamp is owed (the bug)",
      _ins_owing_raw(VID) is True)
# ...and describing it again writes the SAME stampless document, so it
# is owed again - that is the whole loop, in two lines
put("ins", {"v": 3, "empty": True, "complete": True}, mt=1000300.0)
check("...and stays owed after being described again (the loop)",
      _ins_owing_raw(VID) is True)

print("\n--- what the empty writer must stamp ---")
# the 3.30 empty document carries the ear it was built on
put("ins", {"v": 3, "empty": True, "complete": True,
            "src_stt": {"mt": 1000100.0, "reader": 2}}, mt=1000400.0)
check("a stamped empty review on the same reader owes nothing",
      _ins_owing_raw(VID) is False)

print("\n--- and a genuine re-read still re-owes it ---")
put("stt", {"v": _STT_V, "engine": _STT_ENGINE, "reader": 4,
            "segments": [{"a": 1000, "b": 2000, "t": "yalla shabab"}]},
    mt=1000500.0)
ns["_STT_RD_CACHE"].clear()
check("a newer reader re-owes the stamped empty review once",
      _ins_owing_raw(VID) is True)
put("ins", {"v": 3, "empty": True, "complete": True,
            "src_stt": {"mt": 1000500.0, "reader": 4}}, mt=1000600.0)
check("...and the re-described empty settles again",
      _ins_owing_raw(VID) is False)

print("\n--- the legacy shape is untouched ---")
put("stt", {"v": _STT_V, "engine": _STT_ENGINE,
            "segments": [{"a": 1000, "b": 2000, "t": "yalla"}]},
    mt=1000700.0)                                  # no reader = zero
ns["_STT_RD_CACHE"].clear()
put("ins", {"v": 3, "empty": True, "complete": True}, mt=1000800.0)
check("a stampless empty over a reader-zero transcript never owed and "
      "still does not", _ins_owing_raw(VID) is False)

print("\n--- the writer itself (source read) ---")
src_empty = re.search(
    r'_atomic_write_json\(_ai_sidecar\(video_path, "ins"\),\s*\n\s*'
    r'\{"v": 3, "empty": True, "complete": True(?P<rest>[^}]*)\}\)', SRC)
check("the empty-review write in _insights_one exists",
      src_empty is not None)
check("...and it stamps src_stt",
      src_empty is not None and "src_stt" in src_empty.group("rest"))

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

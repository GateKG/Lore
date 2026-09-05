# -*- coding: utf-8 -*-
"""3.31 SOURCES - the process-tree walkers against the LIVE machine.

Read-only and CPU-light: lifts the REAL _root_pids (Toolhelp32 through
ctypes), _climb_to_root and _pid_wears out of lore.py and proves, on
whatever is running right now:

  - the walk returns the same roots as a psutil ppid walk for every
    name it is asked about (discord.exe, steam.exe, explorer.exe, this
    python), in under 50 ms;
  - _climb_to_root(own pid, this exe) returns the root of the own
    same-name chain (the own pid, unless a python spawned this python);
  - _pid_wears(own pid, this exe) is True, False for a dead pid and False
    for a live pid wearing another name.
Nothing is started, killed or written."""
import ast
import io
import os
import sys
import time

import psutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def extract(name, ns):
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


ns = {"os": os, "psutil": psutil, "log": lambda m: None}
root_pids = extract("_root_pids", ns)
climb = extract("_climb_to_root", ns)
wears = extract("_pid_wears", ns)

ME = os.path.basename(sys.executable).lower()
NAMES = ("discord.exe", "steam.exe", "explorer.exe", ME)


def psutil_roots(names):
    procs = {p.pid: p for p in psutil.process_iter(["name", "ppid"])}
    out = {}
    for pid, p in procs.items():
        nm = (p.info.get("name") or "").lower()
        if nm not in names:
            continue
        pp = procs.get(p.info.get("ppid"))
        pnm = ((pp.info.get("name") if pp else "") or "").lower()
        if pnm != nm and nm not in out:
            out[nm] = pid
    return out


print("--- the Toolhelp32 walk vs the psutil ppid walk ---")
t = time.perf_counter()
got = root_pids(NAMES)
ms = (time.perf_counter() - t) * 1000
want = psutil_roots(set(NAMES))
print("  walk: %.1f ms, roots %r" % (ms, got))
check("the same names are found", set(got) == set(want))
# 'first root seen' can differ between the two walks when a name has
# SEVERAL roots (two separate Discord installs); each answer must be A
# root by the other walk's rule, so compare root-ness, not the pick
procs = {p.pid: (p.info.get("name") or "").lower() for p in
         psutil.process_iter(["name"])}


def is_root(pid, nm):
    try:
        pp = psutil.Process(pid).parent()
        return pp is None or (pp.name() or "").lower() != nm
    except Exception:
        return False


check("every root the walk names is alive, wears the name and has no same-name parent",
      all(procs.get(pid) == nm and is_root(pid, nm) for nm, pid in got.items()))
check("this python's root is what psutil says it is",
      got.get(ME) is not None and (got[ME] == want.get(ME)
                                   or is_root(got[ME], ME)))
check("under 50 ms (%.1f ms)" % ms, ms < 50)
check("an unknown name and an empty ask give {}",
      root_pids(("no_such_thing_331.exe",)) == {} and root_pids(()) == {})
check("names are matched case-insensitively", root_pids((ME.upper(),)).get(ME) == got.get(ME))

print("\n--- _climb_to_root ---")
own = os.getpid()
expect = own
try:
    cur = psutil.Process(own)
    while cur.parent() is not None and (cur.parent().name() or "").lower() == ME:
        cur = cur.parent()
    expect = cur.pid
except Exception:
    pass
check("own pid climbs to the root of its own same-name chain (%d -> %d)" % (own, expect),
      climb(own, ME) == expect)
check("a pid whose parent wears ANOTHER name is its own root",
      climb(own, "no_such_thing_331.exe") == own)
check("None / 0 come back as given", climb(None, ME) is None and climb(0, ME) == 0)
check("a dead pid comes back as given", climb(2 ** 22 + 1, ME) == 2 ** 22 + 1)

print("\n--- _pid_wears ---")
check("own pid wears this python", wears(own, ME) is True)
check("...and not another name", wears(own, "explorer.exe") is False)
check("a dead pid wears nothing", wears(2 ** 22 + 1, ME) is False)
check("None / 0 wear nothing", wears(None, ME) is False and wears(0, ME) is False)
t = time.perf_counter()
for _ in range(50):
    wears(own, ME)
us = (time.perf_counter() - t) * 1e6 / 50
check("cheap enough for a 4 s beat (%.0f us per check)" % us, us < 5000)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

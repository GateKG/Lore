# -*- coding: utf-8 -*-
"""3.31 SOURCES - the settings keys, sanitised; the prewarm at boot.

Lifts DEFAULTS and _sanitize_settings out of lore.py by name and proves:
the three new keys and their defaults; a hand-edited voice_apps list is
lower-cased, given its .exe, capped at 20, and a string collapses to
the default list; the two bools are bools; game_audio_only is left
exactly as given (no migration, no rename). Then _prewarm_proctap on
a fake and a missing proctap, and the wiring read from the source:
_PROCTAP beside _MICWATCH, the boot thread right after load_settings,
the ui.html mock and the Audio page rows."""
import ast
import io
import os
import re
import sys
import textwrap
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = io.open(os.path.join(ROOT, "lore.py"), encoding="utf-8").read()
USRC = io.open(os.path.join(ROOT, "ui.html"), encoding="utf-8").read()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


TREE = ast.parse(SRC)


def extract(name, ns):
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


def lift_assign(name, ns):
    for node in TREE.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            code = "\n".join(SRC.splitlines()[node.lineno - 1:node.end_lineno])
            exec(compile(code, "<" + name + ">", "exec"), ns)
            return ns[name]
    raise AssertionError(name)


SAID = []
ns = {"os": os, "log": SAID.append, "time": time,
      "_default_output_dir": lambda: r"C:\mock\Records"}
DEFAULTS = lift_assign("DEFAULTS", ns)
sanitize = extract("_sanitize_settings", ns)

print("--- DEFAULTS ---")
check("capture_by_source defaults True", DEFAULTS.get("capture_by_source") is True)
check("voice_apps defaults to the three Discord builds",
      DEFAULTS.get("voice_apps") == ["discord.exe", "discordptb.exe",
                                     "discordcanary.exe"])
check("read_game_lines defaults True (hidden: no settings row)",
      DEFAULTS.get("read_game_lines") is True)
check("game_audio_only is kept, default False",
      DEFAULTS.get("game_audio_only") is False)
keys = list(DEFAULTS.keys())
check("the three new keys sit right after game_audio_only",
      keys[keys.index("game_audio_only") + 1:keys.index("game_audio_only") + 4]
      == ["capture_by_source", "voice_apps", "read_game_lines"])
m = re.search(r'\n((?:    #[^\n]*\n)+)    "game_audio_only":', SRC)
check("game_audio_only's comment was rewritten (keep only the game; no media layer)",
      m is not None and "no device loopback" in m.group(1)
      and "EXPERIMENTAL" not in m.group(1))


def san(**kw):
    d = dict(DEFAULTS)
    d.update(kw)
    sanitize(d)
    return d


print("\n--- _sanitize_settings ---")
d = san(voice_apps=["Discord", "STEAM.EXE", 3, ""])
check("names are lower-cased, given .exe, blanks dropped",
      d["voice_apps"] == ["discord.exe", "steam.exe", "3.exe"])
d = san(voice_apps=["a%d" % i for i in range(30)])
check("capped at 20", len(d["voice_apps"]) == 20 and d["voice_apps"][0] == "a0.exe")
d = san(voice_apps="discord.exe")
check("a string is not a list: the default list", d["voice_apps"] == DEFAULTS["voice_apps"])
d = san(voice_apps=None)
check("None: the default list", d["voice_apps"] == DEFAULTS["voice_apps"])
d = san(voice_apps=[])
check("an empty list stays empty (he may want no voice tap)", d["voice_apps"] == [])
d = san(capture_by_source="yes")
check("capture_by_source 'yes' -> True", d["capture_by_source"] is True)
d = san(capture_by_source=0)
check("capture_by_source 0 -> False", d["capture_by_source"] is False)
d = dict(DEFAULTS)
del d["capture_by_source"]
del d["read_game_lines"]
sanitize(d)
check("missing bools take their defaults",
      d["capture_by_source"] is True and d["read_game_lines"] is True)
d = san(read_game_lines=0)
check("read_game_lines 0 -> False", d["read_game_lines"] is False)
d = san(game_audio_only=True)
check("game_audio_only is untouched by the sanitiser", d["game_audio_only"] is True)
d = san(game_audio_only="junk")
check("...whatever it holds (no migration, no enum)", d["game_audio_only"] == "junk")
src_mig = SRC[SRC.find("def _migrate_settings_shape"):SRC.find("def _sanitize_settings")]
check("_migrate_settings_shape never mentions game_audio_only or capture_sources",
      "game_audio_only" not in src_mig and "capture_sources" not in src_mig)
check("there is no 'capture_sources' enum and no 'audio_sources' key anywhere",
      "capture_sources" not in SRC and "audio_sources" not in SRC)

print("\n--- _prewarm_proctap ---")
ns2 = {"time": time, "log": SAID.append, "_PROCTAP": {"ok": None, "err": "", "ms": 0}}
prewarm = extract("_prewarm_proctap", ns2)
saved = {k: sys.modules.get(k) for k in ("proctap", "proctap.backends",
                                         "proctap.backends.windows")}
try:
    sys.modules["proctap"] = None          # ImportError on import
    del SAID[:]
    prewarm()
    check("a missing proctap is remembered, said once, never raises",
          ns2["_PROCTAP"]["ok"] is False and ns2["_PROCTAP"]["err"]
          and len(SAID) == 1
          and "per-app capture unavailable" in SAID[0]
          and "Mix and Mic only, as before" in SAID[0])
    fake = types.ModuleType("proctap")
    fakeb = types.ModuleType("proctap.backends")
    fakew = types.ModuleType("proctap.backends.windows")
    fakew.WindowsBackend = type("WindowsBackend", (), {})
    fake.backends = fakeb
    fakeb.windows = fakew
    sys.modules["proctap"] = fake
    sys.modules["proctap.backends"] = fakeb
    sys.modules["proctap.backends.windows"] = fakew
    ns2["_PROCTAP"] = {"ok": None, "err": "", "ms": 0}
    del SAID[:]
    prewarm()
    check("an importable proctap: ok True, ms measured, nothing said",
          ns2["_PROCTAP"]["ok"] is True and ns2["_PROCTAP"]["err"] == ""
          and ns2["_PROCTAP"]["ms"] >= 0 and SAID == [])
finally:
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v

print("\n--- the wiring, read from the source ---")
i = SRC.find("_MICWATCH = {")
check("_PROCTAP lives beside _MICWATCH",
      i > 0 and "_PROCTAP = {\"ok\": None, \"err\": \"\", \"ms\": 0}" in SRC[i:i + 600])
wc = SRC[SRC.find("def _watch_core(ctl):"):SRC.find("def _watch_core(ctl):") + 1200]
check("the boot thread starts right after load_settings, gated on both keys",
      re.search(r'load_settings\(\)\n(?:    #[^\n]*\n)*    if SETTINGS\.get\("capture_by_source"\) and SETTINGS\.get\("capture_system"\):\n'
                r'        threading\.Thread\(target=_prewarm_proctap, daemon=True\)\.start\(\)', wc) is not None)
check("_prewarm_proctap is defined after _pa_close",
      0 < SRC.find("def _pa_close(") < SRC.find("def _prewarm_proctap(") < SRC.find("class AudioRecorder"))
check("nothing else imports proctap at module level",
      not re.search(r"^(?:import proctap|from proctap)", SRC, re.M))

print("\n--- _sources_note with 'by source' off (stage C) ---")
note = extract("_sources_note", ns)
check("both switches on: the old sentence",
      note({"on": False, "system": True, "mic": True}).startswith(
          "everything, as one \u2014 one stream of whatever the speakers played, plus your mic."))
check("the loopback off: 'your mic only'",
      note({"on": False, "system": False, "mic": True}).startswith("your mic only \u2014 "))
check("the mic off: the speakers, and 'your mic is off'",
      note({"on": False, "system": True, "mic": False}).startswith("everything, as one")
      and "your mic is off" in note({"on": False, "system": True, "mic": False}))
check("both off: 'no sound'",
      note({"on": False, "system": False, "mic": False}).startswith("no sound \u2014 "))
check("a state without the switches reads as before",
      note({"on": False}).startswith("everything, as one"))
check("_sources_state carries the two switches for it",
      'out["system"] = bool(SETTINGS.get("capture_system", True))' in SRC
      and 'out["mic"] = bool(SETTINGS.get("capture_mic", True))' in SRC)

print("\n--- ui.html ---")
m = re.search(r"get_settings:async\(\)=>\(\{settings:\{(.*?)\}\}\)", USRC, re.S)
mock = m.group(1) if m else ""
check("the mock carries capture_by_source:true",
      "capture_by_source:true" in mock)
check("the mock carries voice_apps",
      "voice_apps:['discord.exe','discordptb.exe','discordcanary.exe']" in mock)
check("the mock carries read_game_lines:true", "read_game_lines:true" in mock)
check("the mock still carries game_audio_only:false", "game_audio_only:false" in mock)
aud = USRC[USRC.find("if(app.key==='audio'){"):USRC.find("if(app.key==='audio'){") + 4000]
r1 = aud.find("row(L,'Tell the sources apart',ctlToggle('capture_by_source'))")
r2 = aud.find("row(L,'Keep only the game in the video',ctlToggle('game_audio_only'))")
check("the Audio page: 'Tell the sources apart' then 'Keep only the game in the video'",
      0 < r1 < r2)
between = aud[r1:r2]
check("three hint paragraphs between them, in the tome's voice",
      between.count("hint(L,") == 3
      and "you and your friends are the room" in between
      and "the room is your mic alone that night" in between
      and "Switch this off for the old way" in between)
after = aud[r2:r2 + 700]
check("the relabelled row's hint says a background video cannot be found",
      "hint(L," in after and "cannot be found" in after
      and "falls back to normal system sound" in after)
check("no read_game_lines row (hidden setting)", "read_game_lines" not in aud)
check("the old EXPERIMENTAL row is gone", "Game audio only" not in USRC
      and "EXPERIMENTAL: record only" not in USRC)
check("the hints are prose (no markup)", "<" not in between.replace("<=", ""))

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

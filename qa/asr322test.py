# -*- coding: utf-8 -*-
"""3.22: the transcript audit's ship-tonight set, proven.

The guards are nested inside main(), so they are AST-extracted from the
real source and driven as written - not re-implemented (a re-implementation
tests the tester)."""
import ast
import io
import re
import sys
import textwrap

SRC = io.open(r"D:\Gate LLC\ai\asr_worker.py", encoding="utf-8").read()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


def extract(name):
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            code = textwrap.dedent("\n".join(
                SRC.splitlines()[node.lineno - 1:node.end_lineno]))
            ns = {"re": re,
                  "_CTX_STOP": frozenset(
                      "the a an and or of in on with they we our your his "
                      "her its it he she you i to for at by is are was were "
                      "be this that".split())}
            exec(compile(code, "<x>", "exec"), ns)
            return ns[name]
    raise AssertionError(name + " not found")


_impossible = extract("_impossible")
_ctx_echo = extract("_ctx_echo")

CTX = ("Gaming session of Bloodthief. Friends on Discord playing "
       "together; casual gaming chat, callouts, jokes. They speak "
       "Emirati Gulf Arabic and English, often switching within one "
       "sentence.")

print("--- T1: the physics gate ---")
attractor = ("Oh yeah! Oh yeah! " + "Yeah! " * 27).strip()
check("the 251-cps attractor on a 688ms span is impossible",
      _impossible(attractor, 0.688) is True)
canned = ("Hearthstone game play with friends in the discord server "
          "talking about their favorite cards and having a good time")
check("the prompt paraphrase at ~110 cps is impossible",
      _impossible(canned, 1.0) is True)
check("the same sentence over honest seconds is fine",
      _impossible(canned, 9.0) is False)
check("real speech at ~9 cps is untouched",
      _impossible("Get the sniper", 1.5) is False)
check("genuine game VO at 16 cps is untouched",
      _impossible("The mighty warband trusted their leader", 2.1) is False)
# thresholds: >40 Latin, >30 Arabic, counted on speech chars only
check("40.0 cps Latin exactly is NOT flagged (strictly greater)",
      _impossible("a" * 40, 1.0) is False)
check("41 cps Latin is flagged", _impossible("a" * 41, 1.0) is True)
check("31 Arabic chars/sec is flagged",
      _impossible("\u0645" * 31, 1.0) is True)
check("29 Arabic chars/sec is not",
      _impossible("\u0645" * 29, 1.0) is False)
# tashkeel must not count: 25 letters + 25 diacritics = 25 real cps
tash = ("\u0645\u064E" * 25)
check("full tashkeel does not inflate the count",
      _impossible(tash, 1.0) is False)
check("punctuation and spaces do not count",
      _impossible("a! " * 30, 1.0) is False)   # 30 letters, 90 raw chars
check("empty and zero-length are safe",
      _impossible("", 1.0) is False and _impossible("hi", 0) is False)

print("\n--- T2: the short arm of the echo test ---")
check("'Bloodthief.' alone IS an echo", _ctx_echo("Bloodthief.", CTX))
check("'Bloodthief me?' is too", _ctx_echo("Bloodthief me?", CTX))
check("'BLOODTHIEF!' shouted is (and the retry decides)",
      _ctx_echo("BLOODTHIEF!", CTX))
CTX_BW = CTX.replace("Bloodthief", "Big Walk")
check("'Big walk.' collapses onto a two-word title",
      _ctx_echo("Big walk.", CTX_BW))
check("a real sentence MENTIONING the game is not an echo",
      not _ctx_echo("I love playing Bloodthief with you guys", CTX))
check("boilerplate words alone never trigger the short arm",
      not _ctx_echo("Can you hear me?", CTX)
      and not _ctx_echo("Discord chat.", CTX)
      and not _ctx_echo("Nice one, friend.", CTX))
check("a short real line is not an echo", not _ctx_echo("Yeah!", CTX))
CTX_NOG = ("Friends on Discord playing together; casual gaming chat, "
           "callouts, jokes.")
check("a context with no game clause never fires the short arm",
      not _ctx_echo("Bloodthief.", CTX_NOG))
long_echo = ("Gaming session with friends on Discord playing together "
             "casual chat callouts jokes speaking Arabic and English")
check("the LONG form still catches a 7+ word paraphrase",
      _ctx_echo(long_echo, CTX))
check("ordinary long speech still passes",
      not _ctx_echo("We pushed the tower and then the whole team came "
                    "around the corner so we backed off", CTX))

print("\n--- the review fleet's four, locked ---")
CTX_REPO = CTX.replace("Bloodthief", "R.E.P.O")
check("a title with its own periods still parses (R.E.P.O)",
      _ctx_echo("R.E.P.O.", CTX_REPO))
CTX_DS = CTX.replace("Bloodthief", "Ds")
check("a two-letter shelf fires on an EXACT bare title",
      _ctx_echo("Ds.", CTX_DS))
check("...but never inside real words on that night",
      not _ctx_echo("hands up", CTX_DS)
      and not _ctx_echo("What is this?", CTX_DS))
CTX_PEAK = CTX.replace("Bloodthief", "PEAK")
check("'peak' cannot hide inside \"don't speak\"",
      not _ctx_echo("Don't speak.", CTX_PEAK))
check("a standalone 'peak' still fires (the retry decides it)",
      _ctx_echo("That's peak.", CTX_PEAK))
check("the split/fuse case still matches",
      _ctx_echo("Blood thief.", CTX))
check("a blanked line teaches `last` nothing",
      "if txt and lang in KEEP:" in SRC)
check("the guard summary counts the physics wall",
      "impossible-speed re-ask(s)" in
      io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read())

print("\n--- T3: the tag yields to the script ---")
i_gate = SRC.index('stats["physics"] += 1')
i_lang = SRC.index("THE TAG IS THE MODEL'S GUESS")
i_last = SRC.index("if txt and lang in KEEP:\n            last = lang")
check("the physics gate runs before the accept", i_gate < i_last)
check("...and the script-derivation sits between it and `last`",
      i_gate < i_lang < i_last)
LSRC = io.open(r"D:\Gate LLC\lore.py", encoding="utf-8").read()
check("the dossier derives [ar]/[en] from the characters",
      "THE TAG IS THE MODEL'S GUESS" in LSRC
      and LSRC.index("_da / float(len(_dl)) > 0.5")
          < LSRC.index('outl.append(mark + lang + " " + txt[:110])'))

print("\n--- T4: the reader generation ---")
check("worker stamps READER = 3", "READER = 3" in SRC)
check("the app expects the same", "_STT_READER = 3" in LSRC)
check("the physics counter ships in stats", '"physics": 0' in SRC)
check("the boot note still never re-reads behind his back",
      "never read again on its own" in LSRC)

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

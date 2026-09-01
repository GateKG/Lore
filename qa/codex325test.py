# -*- coding: utf-8 -*-
"""3.25: Codex round three's acceptance bar, proven on the real
functions. A stopword alone never authorizes a mutation; an ear that
repeats the line itself always preserves it; everything that worked
before still works."""
import io
import sys

sys.path.insert(0, r"D:\Gate LLC")
import lore  # noqa: E402

SAID = []
lore.log = lambda m: SAID.append(m)
lore.load_settings()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


# a vocabulary where "the" towers over everything (top-2% filler) and
# the content words are established but ordinary
lore._AUD_VOCAB.clear()
lore._AUD_VOCAB["freq"] = dict(
    {w: 10 for w in ("door", "sniper", "boss", "behind", "going",
                     "yalla", "shabab", "now", "get",
                     "يا", "الله")},
    the=50)

print("--- P0-1: a stopword alone never authorizes a mutation ---")


def parse(garble, fixes, checked=None):
    SAID[:] = []
    return lore._aud_parse({"checked": checked or [], "fixes": fixes},
                           garble)


g = [{"t": 10.0, "text": "gibber jabber xx",
      "ear": "get behind the door now"}]
_, _, _, _, _, fx = parse(g, [{"n": 0, "heard": "The sniper boss",
                               "why": "sounds right"}])
check("REJECT: overlap of 'the' alone is refused", len(fx) == 0)
check("...and the refusal leaves the trace",
      g[0].get("verdict") == "unclear" and "refused" in
      (g[0].get("vwhy") or ""))

g2 = [{"t": 10.0, "text": "gibber jabber xx",
       "ear": "get behind the door now"}]
_, _, _, _, _, fx2 = parse(g2, [{"n": 0, "heard": "get behind door",
                                 "why": "clearer"}])
check("ACCEPT: content anchors still pass", len(fx2) == 1)

g3 = [{"t": 10.0, "text": "vyalla.",
       "ear": "\u064a\u0627 \u0627\u0644\u0644\u0647"}]
_, _, _, _, _, fx3 = parse(g3, [
    {"n": 0, "heard": "\u064a\u0627 \u0627\u0644\u0644\u0647",
     "why": "the ear's own words"}])
check("ACCEPT: identity - a fix adopting the ear's words passes even "
      "when every word is filler", len(fx3) == 1)

g4 = [{"t": 10.0, "text": "gibber",
       "ear": "\u0631\u0627\u0633\u062a\u0646"}]
_, _, _, _, _, fx4 = parse(g4, [{"n": 0, "heard": "Rastin.",
                                 "why": "the name"}])
check("ACCEPT: cross-script skeleton agreement still passes",
      len(fx4) == 1)

check("the filler set knows 'the' and not 'door'",
      "the" in lore._aud_filler()
      and "door" not in lore._aud_filler())

print("\n--- P0-2: an ear that repeats the line preserves it ---")


def verdict_of(row):
    garble = [row]
    lore._aud_parse({"checked": [{"n": 0, "verdict": "noise",
                                  "why": "x"}], "fixes": []}, garble)
    return garble[0].get("verdict"), garble[0].get("ear_kept")


v, kept = verdict_of({"t": 5.0, "text": "Vontrelle",
                      "ear": "Vontrelle"})
check("KEEP: a one-word ear matching the line vetoes the strike",
      v == "unclear" and kept is True)
v, kept = verdict_of({"t": 5.0, "text": "Rastin",
                      "ear": "\u0631\u0627\u0633\u062a\u0646"})
check("KEEP: cross-script name agreement vetoes too",
      v == "unclear" and kept is True)
v, _ = verdict_of({"t": 5.0, "text": "Vontrelle", "ear": "door"})
check("STRIKE: an unrelated one-word ear still strikes", v == "noise")
v, _ = verdict_of({"t": 5.0, "text": "Vontrelle", "ear": "Vontrelle",
                   "ear_junk": True})
check("STRIKE: a junk ear never vetoes, matching or not",
      v == "noise")
v, kept = verdict_of({"t": 5.0, "text": "abc",
                      "ear": "get behind the door"})
check("KEEP: the multi-word readable veto still works",
      v == "unclear" and kept is True)
v, _ = verdict_of({"t": 5.0, "text": "abc",
                   "ear": "\u0623\u0633\u062a\u0627 \u3061\u306f"})
check("STRIKE: CJK static still strikes", v == "noise")

print("\n--- the agreement veto skips the vocabulary test ---")
# Vontrelle is NOT in the vocab - that is the whole point: a name the
# library never heard, re-heard verbatim, is evidence, not noise.
check("'vontrelle' is genuinely unknown to the test vocabulary",
      "vontrelle" not in lore._AUD_VOCAB["freq"])

print("\n--- the round-2 fleet: fabrication shapes stay dead ---")
lore._AUD_VOCAB["freq"].update(killed=10, again=10, boss=10)
lore._AUD_VOCAB["at"] = 2.0          # bust the filler cache
g5 = [{"t": 10.0, "text": "gibber",
       "ear": "yeah okay now"}]
_, _, _, _, _, fx5 = parse(g5, [
    {"n": 0, "heard": "Yeah okay now you killed the boss again.",
     "why": "clear"}])
check("REJECT: echoing the ear then fabricating a tail is not "
      "identity", len(fx5) == 0)
g6 = [{"t": 10.0, "text": "gibber",
       "ear": "get behind the door now"}]
_, _, _, _, _, fx6 = parse(g6, [{"n": 0, "heard": "The, the!",
                                 "why": "hm"}])
check("REJECT: a doubled stopword is not substance", len(fx6) == 0)

v, kept = verdict_of({"t": 5.0, "text": "Ateka?",
                      "ear": "أتيكا؟"})
check("KEEP: a two-consonant name re-heard across scripts vetoes "
      "(two-consonant class)", v == "unclear" and kept is True)

g7 = [{"t": 10.0, "text": "gibber",
       "ear": "Marwol Dast"}]
_, _, _, _, _, fx7 = parse(g7, [{"n": 0, "heard": "Marwol Dast.",
                                 "why": "both listeners heard it"}])
check("ACCEPT: a verbatim ear adoption passes even when every word "
      "is library-new (the sense gate honours convergence)",
      len(fx7) == 1)

print("\n--- the filler set cannot eat a name ---")
big = {("w%d" % i): 1 for i in range(1000)}
big.update(zarel=500, the=800)
lore._AUD_VOCAB.clear()
lore._AUD_VOCAB["freq"] = big
lore._AUD_VOCAB["low"] = {"zarel": 5, "the": 800}
lore._AUD_VOCAB["at"] = 3.0
f = lore._aud_filler()
check("a mostly-capitalised frequent name is never filler",
      "zarel" not in f and "the" in f)
lore._AUD_VOCAB["freq"] = {"door": 50, "open": 30, "yes": 20}
lore._AUD_VOCAB["low"] = {"door": 50, "open": 30, "yes": 20}
lore._AUD_VOCAB["at"] = 4.0
check("a tiny vocabulary gets the hand list only - 'door' is safe",
      "door" not in lore._aud_filler())

print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

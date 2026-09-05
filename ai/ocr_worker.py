# -*- coding: utf-8 -*-
"""LORE's HUD reader: what the game itself printed on screen.

    ocr_worker.py <video.mp4> <ffmpeg.exe> <out.json> <t1,t2,...> [game]
                  [grid_step_seconds] [video_duration_seconds]
                  [dense_windows "a-b[:step],..."] [dense_frame_cap]

Samples one frame at each requested second (the seconds are chosen by the
app: around gold moments and chapter starts), reads the text with RapidOCR
(Apache-2.0, vendored beside this file, fully offline), and turns matches
of the event patterns into events: a triple kill marks gold even if nobody
screamed.

THE GRID (3.30). Banners last four seconds and forty targeted frames on a
two-hour night found one; but a boss's health bar, a mode, a menu STAND on
screen for minutes. So when a grid step is given, one centre 16:9 frame
every `step` seconds is read as well and every string it printed is kept
(`hud.rows`, [t, [strings]]). The app turns those rows into what the
screen NAMED and for how long - the words that were always there (his own
tag, the flask slot) are the chrome and fall away. Measured on a 132-minute
night: 264 frames in 8 CPU minutes, the boss's name on 17 of them. The
centre crop is what the eye reads too: on a 32:9 recording the edges hold
the minimap and the chat, the middle holds the fight.

Per-game packs (ai/packs/<game>.ocr.txt: one regex per line) extend the
built-in patterns. Fails open: a bad frame or an unreadable HUD is skipped.

OUTCOMES (3.32). The grid caught WINNER on none of five Rocket League
ends (a 16-30 s banner against a 60 s step) and its clock row predicted
every one of them; Battlegrounds prints "5th Place" for six seconds. So
a pack line may wear a typed head - `outcome.<kind>: <regex with named
groups>` (win, loss, death, placement, score, clock, rating; a pack may
add its own trigger words: overtime, podium, spectator, lobby) - and the
app hands back DENSE WINDOWS (argv[8], "a-b[:step],..." in seconds, at
most argv[9] frames, 300 by default) around the ends it predicted. Each
dense frame is read through the same centre crop and, only when an
outcome regex hit, read a second time at full width (scale=1920) for
the score line the centre crop misreads; every frame's hits are kept
(`dense`, [t, [strings], [{kind, text, groups}]]) - never deduped, so
the app can measure how long the verdict stood. Outcome kinds never
become events: the plain `kind: regex` lines are the senses, the typed
ones are the verdict, and the two are read by different hands. The
doc is stamped `v` 3 for it: an older reader on disk takes argv[8]
in silence and writes no `dense` key, and the app tells the two
apart by the stamp rather than writing that night down as read.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "vendor_ocr"))

PATTERNS = [
    # 3.32: "S5 TOURNAMENT WINNER" is a player title worn on every goal
    # replay, and "#\s*1" fired on a Discord channel read off an alt-tab
    ("victory", r"\bVICTORY\b|\bYOU WIN\b|(?<!TOURNAMENT )\bWINNER\b|"
                r"\bCHAMPION\b"),
    ("defeat", r"\bDEFEAT\b|\bYOU DIED\b|\bGAME OVER\b|\bWASTED\b|\bYOU LOSE\b"),
    ("kill", r"\bDOUBLE KILL\b|\bTRIPLE KILL\b|\bQUAD(?:RA)? KILL\b|"
             r"\bPENTA ?KILL\b|\bKILLING SPREE\b|\bELIMINATED\b|\bHEADSHOT\b"),
    ("level", r"\bLEVEL UP\b|\bRANK UP\b|\bPROMOTED\b|\bNEW RECORD\b"),
    ("boss", r"\bBOSS\b.{0,20}\bDEFEATED\b|\bFELLED\b|\bGREAT ENEMY\b|"
             r"\bENEMY FELLED\b|\bHEIR OF THE CURSE\b"),
]


# the outcome kinds the app knows how to fold; a pack may add trigger
# words of its own under the same head (they never become events)
OUTCOME_KINDS = ("win", "loss", "death", "placement", "score", "clock",
                 "rating")


def pack_line(ln):
    """One pack line -> (kind, regex, is_outcome) or None. The typed head
    `outcome.<kind>:` is split off BEFORE the twelve-character cut a
    plain kind gets, or "outcome.placement" would have come back as
    "outcome.plac" and gone through the event dedupe like a banner."""
    ln = (ln or "").strip()
    if not ln or ln.startswith("#") or ":" not in ln:
        return None
    k, _, p = ln.partition(":")
    head = k.strip().lower()
    outc = head.startswith("outcome.")
    kind = (head[8:].strip() if outc else head)[:12]
    if not kind:
        return None
    try:
        return kind, re.compile(p.strip(), re.I), outc
    except re.error:
        return None


def load_pack(game):
    """The built-in patterns plus the game's pack: [(kind, regex,
    is_outcome)]. Only the plain kinds mark events."""
    out = [(k, re.compile(p, re.I), False) for k, p in PATTERNS]
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        pf = os.path.join(base, "packs",
                          (game or "").strip().lower().replace(" ", "")
                          + ".ocr.txt")
        if os.path.isfile(pf):
            with open(pf, encoding="utf-8") as fh:
                for ln in fh:
                    got = pack_line(ln)
                    if got is not None:
                        out.append(got)
    except Exception:
        pass
    return out


def outcome_hits(pats, text, per_kind=6):
    """Every outcome match in one frame's text: [{kind, text, groups}].
    finditer, not search - a podium prints four tags on one frame and
    the app needs all of them to tell whose win it was."""
    hits = []
    if not text:
        return hits
    for kind, rx, outc in pats:
        if not outc:
            continue
        n = 0
        for m in rx.finditer(text):
            hits.append({"kind": kind, "text": m.group(0)[:40].strip(),
                         "groups": {k2: v2 for k2, v2 in
                                    m.groupdict().items() if v2}})
            n += 1
            if n >= per_kind:
                break
    return hits


def parse_dense(spec):
    """The app's dense windows, "a-b[:step],..." -> [(a, b, step)].
    Junk is skipped, a step under half a second is a typo."""
    out = []
    for part in str(spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        rng, _, st = part.partition(":")
        a, _, b = rng.partition("-")
        try:
            a, b = float(a), float(b)
            st = float(st) if st.strip() else 2.0
        except ValueError:
            continue
        if b <= a or st < 0.5:
            continue
        out.append((max(0.0, a), b, st))
    return out


def dense_seconds(windows, cap=300):
    """The seconds the dense windows ask for, in order, each once,
    never more than `cap` of them (six minutes of RapidOCR on a
    5120x1440 night is the whole budget)."""
    out, seen = [], set()
    try:
        cap = max(1, int(cap or 300))
    except (TypeError, ValueError):
        cap = 300
    for a, b, st in windows or []:
        t = a
        while t <= b + 1e-6:
            k = round(t, 1)
            if k not in seen:
                seen.add(k)
                out.append(k)
                if len(out) >= cap:
                    return out
            t += st
    return out


def frame_strings(got, cap=24):
    """A frame's readable strings: three letters or more, read with
    some confidence, each once, `cap` at most."""
    strs = []
    for x in got or []:
        try:
            txt = " ".join(str(x[1]).split())
            sc = float(x[2]) if len(x) > 2 else 1.0
        except Exception:
            continue
        if len(txt) >= 3 and sc >= 0.55 and txt not in strs:
            strs.append(txt[:60])
        if len(strs) >= cap:
            break
    return strs


# the middle 16:9 of the picture, scaled to what RapidOCR reads best
_MID = (r"crop=min(iw\,ih*16/9):ih:(iw-min(iw\,ih*16/9))/2:0,"
        r"scale=1280:-2")


def grid_seconds(step, dur):
    """The grid's seconds: from five seconds in to five seconds before the
    end, every `step`. Empty when either number is missing."""
    out = []
    try:
        step, dur = float(step or 0), float(dur or 0)
    except (TypeError, ValueError):
        return out
    if step <= 0 or dur <= 10:
        return out
    t = 5.0
    while t < dur - 5:
        out.append(round(t, 1))
        t += step
    return out


def main(video, ffmpeg, dst, seconds, game="", step=0.0, dur=0.0,
         dense=None, cap=300):
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    pats = load_pack(game)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    events, seen = [], set()
    rows, dense_rows = [], []
    tdir = tempfile.mkdtemp(prefix="lore_ocr_")

    def mark(t, text):
        for kind, rx, outc in pats:
            if outc:
                continue          # a verdict is not a banner
            m = rx.search(text)
            if m:
                key = (kind, int(t // 20))   # one per kind per ~20s
                if key in seen:
                    continue
                seen.add(key)
                events.append({"t": round(t, 1), "kind": kind,
                               "text": m.group(0)[:40].strip()})

    def read(t, vf, tag):
        jp = os.path.join(tdir, f"{tag}_{int(t * 10)}.jpg")
        try:
            r = subprocess.run(
                [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{t:.2f}",
                 "-i", video, "-frames:v", "1", "-vf", vf, "-q:v", "4",
                 jp],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=flags, timeout=30)
            if r.returncode != 0 or not os.path.isfile(jp):
                return None
            got, _ = ocr(jp)
            return got or []
        except Exception:
            return None
        finally:
            try:
                if os.path.isfile(jp):
                    os.remove(jp)
            except OSError:
                pass

    try:
        for t in seconds:
            got = read(t, "scale=1280:-2", "f")
            if not got:
                continue
            text = " ".join(x[1] for x in got)
            if text:
                mark(t, text)
        for t in grid_seconds(step, dur):
            got = read(t, _MID, "g")
            if got is None:
                continue
            strs = frame_strings(got)
            rows.append([round(t, 1), strs])
            if strs:
                mark(t, " ".join(strs))
        # THE DENSE WINDOWS. The app predicted where a match ended and
        # asks for two-second frames there; a frame that hit an outcome
        # regex is read once more at full width for the score line
        # the centre crop misread ("O BLUE", "DORANGE"). Every frame's
        # hits are kept, never deduped - the span is the evidence.
        for t in dense_seconds(parse_dense(dense), cap):
            got = read(t, _MID, "d")
            if got is None:
                continue
            strs = frame_strings(got, 40)
            hits = outcome_hits(pats, " ".join(strs))
            if hits:
                got2 = read(t, "scale=1920:-2", "w")
                if got2:
                    for s2 in frame_strings(got2, 40):
                        if s2 not in strs:
                            strs.append(s2)
                    hits = outcome_hits(pats, " ".join(strs))
            dense_rows.append([round(t, 1), strs, hits])
    finally:
        try:
            os.rmdir(tdir)
        except OSError:
            pass
    # v 3: this reader understands dense windows (argv[8]) - the app
    # reads the stamp to tell an older drop-in from a night with no
    # verdict on it
    doc = {"v": 3, "events": events}
    if rows:
        doc["hud"] = {"step": float(step), "rows": rows}
    if dense:
        # asked and answered - an empty list is "looked, found nothing"
        doc["dense"] = dense_rows
    with open(dst + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    os.replace(dst + ".tmp", dst)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("usage: ocr_worker.py <video> <ffmpeg> <out.json> <t1,t2,..> "
              "[game] [grid_step] [duration] [dense a-b[:step],...] "
              "[dense_cap]", file=sys.stderr)
        sys.exit(2)
    try:
        secs = [float(x) for x in sys.argv[4].split(",") if x.strip()]
        sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], secs,
                      sys.argv[5] if len(sys.argv) > 5 else "",
                      float(sys.argv[6]) if len(sys.argv) > 6 else 0.0,
                      float(sys.argv[7]) if len(sys.argv) > 7 else 0.0,
                      sys.argv[8] if len(sys.argv) > 8 else None,
                      int(sys.argv[9]) if len(sys.argv) > 9 else 300))
    except Exception as e:
        print(f"OCR_WORKER_FAILED {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

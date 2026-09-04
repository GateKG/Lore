# -*- coding: utf-8 -*-
"""LORE's HUD reader: what the game itself printed on screen.

    ocr_worker.py <video.mp4> <ffmpeg.exe> <out.json> <t1,t2,...> [game]
                  [grid_step_seconds] [video_duration_seconds]

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
    ("victory", r"\bVICTORY\b|\bYOU WIN\b|\bWINNER\b|\bCHAMPION\b|#\s*1\b"),
    ("defeat", r"\bDEFEAT\b|\bYOU DIED\b|\bGAME OVER\b|\bWASTED\b|\bYOU LOSE\b"),
    ("kill", r"\bDOUBLE KILL\b|\bTRIPLE KILL\b|\bQUAD(?:RA)? KILL\b|"
             r"\bPENTA ?KILL\b|\bKILLING SPREE\b|\bELIMINATED\b|\bHEADSHOT\b"),
    ("level", r"\bLEVEL UP\b|\bRANK UP\b|\bPROMOTED\b|\bNEW RECORD\b"),
    ("boss", r"\bBOSS\b.{0,20}\bDEFEATED\b|\bFELLED\b|\bGREAT ENEMY\b|"
             r"\bENEMY FELLED\b|\bHEIR OF THE CURSE\b"),
]


def load_pack(game):
    out = [(k, re.compile(p, re.I)) for k, p in PATTERNS]
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        pf = os.path.join(base, "packs",
                          (game or "").strip().lower().replace(" ", "")
                          + ".ocr.txt")
        if os.path.isfile(pf):
            with open(pf, encoding="utf-8") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln or ln.startswith("#") or ":" not in ln:
                        continue
                    k, _, p = ln.partition(":")
                    try:
                        out.append((k.strip().lower()[:12],
                                    re.compile(p.strip(), re.I)))
                    except re.error:
                        pass
    except Exception:
        pass
    return out


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


def main(video, ffmpeg, dst, seconds, game="", step=0.0, dur=0.0):
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    pats = load_pack(game)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    events, seen = [], set()
    rows = []
    tdir = tempfile.mkdtemp(prefix="lore_ocr_")

    def mark(t, text):
        for kind, rx in pats:
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
            strs = []
            for x in got:
                try:
                    txt = " ".join(str(x[1]).split())
                    sc = float(x[2]) if len(x) > 2 else 1.0
                except Exception:
                    continue
                if len(txt) >= 3 and sc >= 0.55 and txt not in strs:
                    strs.append(txt[:60])
                if len(strs) >= 24:
                    break
            rows.append([round(t, 1), strs])
            if strs:
                mark(t, " ".join(strs))
    finally:
        try:
            os.rmdir(tdir)
        except OSError:
            pass
    doc = {"v": 2, "events": events}
    if rows:
        doc["hud"] = {"step": float(step), "rows": rows}
    with open(dst + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    os.replace(dst + ".tmp", dst)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("usage: ocr_worker.py <video> <ffmpeg> <out.json> <t1,t2,..> "
              "[game]", file=sys.stderr)
        sys.exit(2)
    try:
        secs = [float(x) for x in sys.argv[4].split(",") if x.strip()]
        sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], secs,
                      sys.argv[5] if len(sys.argv) > 5 else "",
                      float(sys.argv[6]) if len(sys.argv) > 6 else 0.0,
                      float(sys.argv[7]) if len(sys.argv) > 7 else 0.0))
    except Exception as e:
        print(f"OCR_WORKER_FAILED {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

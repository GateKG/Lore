# -*- coding: utf-8 -*-
"""LORE's HUD reader: what the game itself printed on screen.

    ocr_worker.py <video.mp4> <ffmpeg.exe> <out.json> <t1,t2,...> [game]

Samples one frame at each requested second (the seconds are chosen by the
app: around gold moments and chapter starts - a full-video OCR pass would
cost more CPU than it returns), reads the text with RapidOCR (Apache-2.0,
vendored beside this file, fully offline), and turns matches of the event
patterns into events: a triple kill marks gold even if nobody screamed.

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


def main(video, ffmpeg, dst, seconds, game=""):
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    pats = load_pack(game)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    events, seen = [], set()
    tdir = tempfile.mkdtemp(prefix="lore_ocr_")
    try:
        for t in seconds:
            jp = os.path.join(tdir, f"f_{int(t * 10)}.jpg")
            try:
                r = subprocess.run(
                    [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{t:.2f}",
                     "-i", video, "-frames:v", "1", "-vf", "scale=1280:-2",
                     "-q:v", "4", jp],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=flags, timeout=30)
                if r.returncode != 0 or not os.path.isfile(jp):
                    continue
                got, _ = ocr(jp)
                text = " ".join(x[1] for x in (got or []))
                if not text:
                    continue
                for kind, rx in pats:
                    m = rx.search(text)
                    if m:
                        key = (kind, int(t // 20))   # one per kind per ~20s
                        if key in seen:
                            continue
                        seen.add(key)
                        events.append({"t": round(t, 1), "kind": kind,
                                       "text": m.group(0)[:40].strip()})
            except Exception:
                continue
            finally:
                try:
                    if os.path.isfile(jp):
                        os.remove(jp)
                except OSError:
                    pass
    finally:
        try:
            os.rmdir(tdir)
        except OSError:
            pass
    with open(dst + ".tmp", "w", encoding="utf-8") as fh:
        json.dump({"v": 1, "events": events}, fh, ensure_ascii=False)
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
                      sys.argv[5] if len(sys.argv) > 5 else ""))
    except Exception as e:
        print(f"OCR_WORKER_FAILED {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

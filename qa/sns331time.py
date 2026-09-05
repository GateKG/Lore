# -*- coding: utf-8 -*-
"""3.31 STAGE D - MEASURE THE REMEDY BEFORE SETTING THE NUMBERS.

Read-only over the shelf's sidecars (D:\\Records\\.lore_thumbs by default;
pass another folder as argv[1]). Nothing is written, no model runs, no
audio is decoded: the sound curves (.lvl), the words (.stt), the hype
curves (.sns), the gold marks (.hl) and the reviews (.ins) already on
disk are the whole evidence. CPU-light: JSON reads and numpy over
1,300 curves, well under a minute.

What it settles, and how (every number the code carries came from here):

  HL_VOICE_GATE_DB  the room's 'somebody is talking' floor for the shout
                    picker and the hype gate. Bounded from ABOVE by the
                    quietest talking the shelf has ever carried: the 5th
                    percentile of the Mix level at seconds a room line
                    covers, per night, and the lowest nights of that.
                    The Mix is the room PLUS the game bed, so the room's
                    own talking is never louder than this - a gate that
                    sits under the shelf's quietest spoken second on the
                    Mix sits under it on the room too. Bounded from BELOW
                    by what a voice app's gate writes between lines: true
                    zeros, which the envelope reads as -100 dB (1e-10
                    floor) - nowhere near.
  HL_SHOUT_RISE_DB  how far above its own talking level the room must
                    rise for a 'shout'. The rise is computed exactly as
                    _pick_shouts computes it (a +-60 s rolling median
                    over SPOKEN seconds only), over the Mix curve at the
                    words' seconds. On the Mix a shout rises LESS than on
                    the room alone (the game bed under the talk lifts the
                    reference and not the peak), so a threshold the Mix
                    clears the room clears too. Two populations: the p99
                    rise of nights where somebody laughed (the ear's marks
                    on the .hl) against nights with no laugh at all; and
                    the rise at the existing loud marks that sit on a hot
                    line (the shouts the words already vouch for).
  HYPE_MIN_RISE     the smallest spread of the arousal curve that counts
                    as a night that ROSE. Over spoken windows (a window
                    overlapping a room line) per night: p90 - median and
                    3 MADs. Calm nights (no laugh, no scream marks) give
                    the noise the model reports when nothing happened;
                    lively nights (five laughs or more) give what a real
                    rise looks like. The floor sits above the calm p75.
  the p85 retone    what _ins_retone did to the shelf's reviews: kind0
                    is the describer's word, kind the retone's - how many
                    'excited' were p85 promotions and how many tones were
                    blanked. That is the cost of the rule the room curve
                    replaces (and the reason the mix path keeps it as
                    audited, rather than re-judging 400 nights).

Run by hand while the box is idle; not in run_all.bat (it reads the real
shelf)."""
import glob
import io
import json
import math
import os
import sys
from collections import Counter

import numpy as np

TH = sys.argv[1] if len(sys.argv) > 1 else r"D:\Records\.lore_thumbs"


def load(base, kind):
    try:
        with io.open(os.path.join(TH, "%s.%s.json" % (base, kind)),
                     encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def q(xs, p):
    xs = [x for x in xs if x is not None and not (isinstance(x, float)
                                                  and math.isnan(x))]
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[min(len(s) - 1, int(len(s) * p))]


def room_lines(stt):
    """(a, b) seconds of the lines the ROOM said - src absent or 'you'."""
    out = []
    for sg in (stt or {}).get("segments") or []:
        if str(sg.get("src") or "") in ("media", "game"):
            continue
        try:
            a, b = float(sg.get("a") or 0) / 1000.0, \
                float(sg.get("b") or 0) / 1000.0
        except (TypeError, ValueError):
            continue
        if b > a:
            out.append((a, b))
    return out


def rise_like_pick_shouts(sm, hop_s, live):
    """The rise _pick_shouts measures: the smoothed level minus a +-60 s
    rolling median over spoken seconds (>= 5 of them or no opinion)."""
    n = len(sm)
    per = max(1, int(round(1.0 / hop_s)))
    secs = n // per
    if secs < 20:
        return None
    m = np.nanmedian(np.where(live, sm, np.nan)[:secs * per]
                     .reshape(secs, per), axis=1)
    padm = np.concatenate([np.full(60, np.nan), m, np.full(60, np.nan)])
    win = np.lib.stride_tricks.sliding_window_view(padm, 121)
    cnt = np.sum(~np.isnan(win), axis=1)
    with np.errstate(all="ignore"):
        ref = np.where(cnt >= 5, np.nanmedian(win, axis=1), np.nan)
    reff = np.repeat(ref, per)
    reff = np.concatenate([reff, np.full(n - len(reff),
                                         reff[-1] if len(reff) else np.nan)])
    return np.where(live & ~np.isnan(reff), sm - reff, -np.inf), reff


bases = sorted(os.path.basename(p)[:-9]
               for p in glob.glob(os.path.join(TH, "*.lvl.json")))
print("shelf: %s - %d sound curves" % (TH, len(bases)))

# ---------------------------------------------------------------- gate
spoken_p5, spoken_p1, floors, spoken_p50 = [], [], [], []
GATES = (-45.0, -50.0, -55.0, -60.0, -65.0)
under = {g0: [] for g0 in GATES}      # share of spoken seconds under it
# ---------------------------------------------------------------- rise
p99_laugh, p99_calm, p99_all = [], [], []
shout_rise = []            # the rise at loud marks on a hot line
talk_rise_p99_by_night = {}
nights_used = 0
for b in bases:
    L = load(b, "lvl")
    S = load(b, "stt")
    if not isinstance(L, dict) or not isinstance(S, dict):
        continue
    db = L.get("db") or []
    dur = float(L.get("dur") or 0)
    if len(db) < 200 or dur < 120:
        continue
    lines = room_lines(S)
    if sum(bb - aa for aa, bb in lines) < 60:
        continue                       # under a minute of talk: no opinion
    es = np.asarray(db, dtype=np.float32)
    n = len(es)
    hop_s = dur / float(n)
    live = np.zeros(n, dtype=bool)
    for aa, bb in lines:
        i0, i1 = max(0, int(aa / hop_s)), min(n, int(bb / hop_s) + 1)
        live[i0:i1] = True
    if live.sum() < 50:
        continue
    nights_used += 1
    # THE GATE TESTS A SECOND, NOT A FRAME: the level of one second is
    # the RMS over it (energy mean -> dB), which is what _pick_shouts
    # smooths to and what the worker's 6 s window RMS is. The p5 of the
    # frames would read the gaps between words instead.
    per = max(1, int(round(1.0 / hop_s)))
    secs = n // per
    pw = (10.0 ** (es[:secs * per] / 10.0)).reshape(secs, per).mean(axis=1)
    sec_db = 10.0 * np.log10(pw + 1e-10)
    sec_live = live[:secs * per].reshape(secs, per).any(axis=1)
    sp = sec_db[sec_live]
    spoken_p5.append(float(np.percentile(sp, 5)))
    spoken_p1.append(float(np.percentile(sp, 1)))
    spoken_p50.append(float(np.percentile(sp, 50)))
    for g0 in GATES:
        under[g0].append(float((sp < g0).mean()))
    floors.append(float(L.get("floor") if L.get("floor") is not None
                        else np.percentile(es, 5)))
    w = max(3, int(round(1.0 / hop_s)))
    # the picker smooths ENERGY over a second, not dB (a second half
    # filled with a voice app's gated zeros would otherwise read -65)
    sm = 10.0 * np.log10(np.convolve(10.0 ** (es / 10.0),
                                     np.ones(w, np.float32) / w,
                                     mode="same") + 1e-10)
    got = rise_like_pick_shouts(sm, hop_s, live)
    if got is None:
        continue
    rise, reff = got
    lr = rise[np.isfinite(rise)]
    if not len(lr):
        continue
    p99 = float(np.percentile(lr, 99))
    p99_all.append(p99)
    talk_rise_p99_by_night[b] = p99
    H = load(b, "hl")
    evs = (H or {}).get("events") if isinstance(H, dict) else H
    evs = [e for e in (evs or []) if isinstance(e, dict)]
    laughs = [e for e in evs if e.get("kind") in ("laugh", "scream")]
    (p99_laugh if laughs else p99_calm).append(p99)
    # the shouts the words vouch for: a plain loud mark on a hot line
    hot = []
    for sg in S.get("segments") or []:
        if str(sg.get("src") or "") in ("media", "game"):
            continue
        t = str(sg.get("t") or "")
        if "!" in t or t.isupper():
            hot.append(float(sg.get("a") or 0) / 1000.0)
    for e in evs:
        if e.get("kind"):
            continue
        try:
            t = float(e.get("t") or 0)
        except (TypeError, ValueError):
            continue
        if not any(abs(t - x) <= 4.0 for x in hot):
            continue
        i = min(n - 1, int((t + 0.4) / hop_s))
        j0, j1 = max(0, i - int(2.0 / hop_s)), min(n, i + int(2.0 / hop_s))
        r = rise[j0:j1]
        r = r[np.isfinite(r)]
        if len(r):
            shout_rise.append(float(r.max()))

print("\n=== HL_VOICE_GATE_DB - the quietest talking on the shelf (Mix "
      "level at room seconds) ===")
print("  nights with >= 1 min of room lines: %d" % nights_used)
print("  per-night p5 of the spoken SECOND level (RMS over the second): "
      "median %.1f dB, p10 %.1f, p5 %.1f, p1 %.1f, min %.1f"
      % (q(spoken_p5, .5), q(spoken_p5, .1),
                                    q(spoken_p5, .05), q(spoken_p5, .01),
                                    min(spoken_p5)))
print("  per-night p1 of the spoken level: median %.1f dB, p5 %.1f, min "
      "%.1f" % (q(spoken_p1, .5), q(spoken_p1, .05), min(spoken_p1)))
print("  per-night median spoken level: median %.1f dB" % q(spoken_p50, .5))
print("  the nights' own floors (p5 of everything): median %.1f, p5 %.1f, "
      "min %.1f" % (q(floors, .5), q(floors, .05), min(floors)))
print("  the nights' own floors, upper tail (a loud game bed): p75 %.1f, "
      "p90 %.1f" % (q(floors, .75), q(floors, .9)))
# TWO WALLS. Above: the talk itself - a spoken second on the Mix is at
# least as loud as on the room (the room is the Mix minus the game), so
# the share of spoken seconds under a gate on the Mix is a LOWER bound
# on what that gate would lose on the room. Below: the mic's own floor,
# which the Mix's p5-of-everything bounds from above (the mic rides in
# the Mix at parity). The gate is the lowest whole five dB that still
# clears the median night's floor by 8 dB - the room's quiet is the mic
# alone, with no game bed to lift it - and the loss it costs is printed.
for g0 in GATES:
    print("  gate %.0f dB: loses %4.1f%% of spoken seconds on the median "
          "night, %4.1f%% on the p90 night; %3d%% of nights lose > 10%%"
          % (g0, 100 * q(under[g0], .5), 100 * q(under[g0], .9),
             100 * sum(1 for x in under[g0] if x > 0.10)
             / max(1, len(under[g0]))))
floor_med = q(floors, .5)
over = [g0 for g0 in GATES if g0 >= floor_med + 8.0]
gate = min(over) if over else -50.0
print("  -> HL_VOICE_GATE_DB = %.0f (the lowest five-dB step >= the "
      "median night's floor %.1f + 8 dB; loses %.1f%% of the median "
      "night's spoken seconds on the Mix, fewer on the room)"
      % (gate, floor_med, 100 * q(under[gate], .5)))

print("\n=== HL_SHOUT_RISE_DB - how far talk rises above its own level ===")
print("  p99 rise over spoken seconds, nights WITH a laugh/scream mark "
      "(n=%d): median %.1f dB, p25 %.1f, p10 %.1f"
      % (len(p99_laugh), q(p99_laugh, .5), q(p99_laugh, .25),
         q(p99_laugh, .1)))
print("  p99 rise over spoken seconds, nights with NONE (n=%d): median "
      "%.1f dB, p75 %.1f, p90 %.1f"
      % (len(p99_calm), q(p99_calm, .5), q(p99_calm, .75),
         q(p99_calm, .9)))
print("  the rise at loud marks on a hot line (the words' own shouts, "
      "n=%d): median %.1f dB, p25 %.1f, p10 %.1f, p5 %.1f"
      % (len(shout_rise), q(shout_rise, .5), q(shout_rise, .25),
         q(shout_rise, .1), q(shout_rise, .05)))
for thr in (4.0, 5.0, 6.0, 7.0, 8.0):
    print("  at %.0f dB: %3d%% of laugh nights clear it, %3d%% of calm "
          "nights do, %3d%% of the words' shouts do"
          % (thr,
             100 * sum(1 for x in p99_laugh if x >= thr) / max(1, len(p99_laugh)),
             100 * sum(1 for x in p99_calm if x >= thr) / max(1, len(p99_calm)),
             100 * sum(1 for x in shout_rise if x >= thr)
             / max(1, len(shout_rise))))
# the threshold: the words' own shouts must mostly clear it (>= 90 %)
# and it must be a whole dB the laugh nights' p10 clears - on the Mix,
# which under-reads the room's rise (the bed lifts the reference)
cands = [thr for thr in (8.0, 7.0, 6.0, 5.0, 4.0)
         if sum(1 for x in shout_rise if x >= thr) / max(1, len(shout_rise))
         >= 0.9 and q(p99_laugh, .1) >= thr]
rise_thr = cands[0] if cands else 6.0
print("  -> HL_SHOUT_RISE_DB = %.0f (the highest whole dB that 90%% of the "
      "words' shouts and the laugh nights' p10 still clear on the Mix; "
      "the room clears more)" % rise_thr)

print("\n=== HYPE_MIN_RISE - the arousal spread that counts as a rise ===")
calm_rise, live_rise, calm_mad3, live_mad3, calm_max, live_max = \
    [], [], [], [], [], []
nsns = 0
for b in bases:
    D = load(b, "sns")
    if not isinstance(D, dict):
        continue
    h = D.get("hype") or {}
    v = [float(x) for x in (h.get("v") or [])]
    hop = float(h.get("hop") or 3.0)
    if len(v) < 60:
        continue
    S = load(b, "stt")
    lines = room_lines(S)
    if not lines:
        continue
    n = len(v)
    spoken = np.zeros(n, dtype=bool)
    for aa, bb in lines:
        i0, i1 = max(0, int(aa / hop)), min(n, int(bb / hop) + 1)
        spoken[i0:i1] = True
    sv = sorted(x for x, s in zip(v, spoken) if s)
    if len(sv) < 40:
        continue
    nsns += 1
    med = sv[len(sv) // 2]
    p90 = sv[int(len(sv) * 0.9)]
    mad = sorted(abs(x - med) for x in sv)[len(sv) // 2]
    H = load(b, "hl")
    evs = (H or {}).get("events") if isinstance(H, dict) else H
    laughs = sum(1 for e in (evs or []) if isinstance(e, dict)
                 and e.get("kind") in ("laugh", "scream"))
    if laughs == 0:
        calm_rise.append(p90 - med)
        calm_mad3.append(3 * mad)
        calm_max.append(sv[-1] - med)
    elif laughs >= 5:
        live_rise.append(p90 - med)
        live_mad3.append(3 * mad)
        live_max.append(sv[-1] - med)
print("  nights with a hype curve and room lines: %d (calm = no laugh "
      "mark: %d; lively = 5+ laughs: %d)" % (nsns, len(calm_rise),
                                              len(live_rise)))
print("  calm nights,   p90 - median over spoken windows: median %.3f, "
      "p75 %.3f, p90 %.3f; 3 MADs median %.3f; max - median median %.3f"
      % (q(calm_rise, .5), q(calm_rise, .75), q(calm_rise, .9),
         q(calm_mad3, .5), q(calm_max, .5)))
print("  lively nights, p90 - median over spoken windows: median %.3f, "
      "p25 %.3f, p10 %.3f; 3 MADs median %.3f; max - median median %.3f"
      % (q(live_rise, .5), q(live_rise, .25), q(live_rise, .1),
         q(live_mad3, .5), q(live_max, .5)))
# these are MIX curves (the game in them), so a calm night's spread is
# wider than the room's own would be: a floor over the calm p75 is a
# floor the room's noise never reaches
floor_c = q(calm_rise, .75)
hype_min = math.ceil(floor_c * 100.0) / 100.0 if not math.isnan(floor_c) \
    else 0.06
hype_min = max(0.03, hype_min)
print("  -> HYPE_MIN_RISE = %.2f (the calm nights' p75 of p90 - median, "
      "rounded up to a hundredth; %d%% of lively nights' max - median "
      "clear it)" % (hype_min,
                     100 * sum(1 for x in live_max if x >= hype_min)
                     / max(1, len(live_max))))

print("\n=== the p85 retone on the shelf's reviews (_ins_retone's cost) ===")
promo = blank = kept = total_ex = 0
by_kind0 = Counter()
for p in glob.glob(os.path.join(TH, "*.ins.json")):
    try:
        with io.open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        continue
    if not isinstance(d, dict):
        continue
    for m in d.get("moments") or []:
        if not isinstance(m, dict):
            continue
        k, k0 = str(m.get("kind") or ""), m.get("kind0")
        if k == "excited":
            total_ex += 1
        if k0 is None:
            continue
        by_kind0[str(k0)] += 1
        if k == "excited":
            promo += 1
        elif k == "":
            blank += 1
        else:
            kept += 1
print("  'excited' moments on the shelf: %d, of which %d were p85 "
      "promotions of a describer's funny/scary; %d describer tones were "
      "blanked to '' by the rule (kind0 %s)"
      % (total_ex, promo, blank, dict(by_kind0)))
print("  -> DECISION: the rule stays verbatim for a MIX-fed curve (those "
      "reviews were audited under it; re-judging them re-owes the shelf) "
      "and is re-based on the room's own bar for a room-fed one: a moment "
      "is 'excited' only when the room rose (x >= bar, never on a flat "
      "night, never in a window nobody spoke).")

print("\n=== summary ===")
print("  HL_VOICE_GATE_DB = %.0f\n  HL_SHOUT_RISE_DB = %.0f\n  "
      "HYPE_MIN_RISE = %.2f\n  HYPE_GATE_DB (worker) = HL_VOICE_GATE_DB"
      % (gate, rise_thr, hype_min))

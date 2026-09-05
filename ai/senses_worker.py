# -*- coding: utf-8 -*-
"""LORE's new senses: a sound vocabulary, a hype curve, and voices told apart.

Called as a subprocess, exactly like the reader and the laughter ear:

    senses_worker.py <input.wav (48kHz mono)> <output.json> [game-name] [mic]

3.31 BY SOURCE: a control file beside the wav, <input.wav>.ctl =
{src: 'room'|'mix', game_wav, game_src, mic, threads}, says WHICH layer
the wav is. On 'room' (the voice app's tap + the mic, or the mic alone)
the hype curve and the voices are read off the room, windows nobody
spoke in skip the model, and the sound vocabulary listens to game_wav
(the Game tap, or the mix when there was none). No .ctl, or src 'mix':
today's worker to the bit - one wav, every pass over it, un-gated.

Three passes over one decode, all CPU (torch is CPU-only on this machine and
the GPU belongs to games):

  CLAP  (laion/larger_clap_general, Apache-2.0) - zero-shot sound tagging
        against a prompt list: cheering, groans, victory fanfares, whatever
        the packs file says for this game. RELATIVE scoring, the laughter
        ear's hard-won lesson: absolute scores are meaningless under game
        audio, so an event must stand clear of THIS session's own background.
  HYPE  (audeering wav2vec2 dimensional emotion, research license, personal
        use) - an arousal curve: excited-vs-flat, which is not the same as
        loud-vs-quiet. Tense whispered clutches finally have a signal.
  WHO   (speechbrain ECAPA-VoxCeleb embeddings, Apache-2.0) - utterances
        clustered by voice. Names are given later by the user; this pass
        only tells Speaker 1 from Speaker 2.

The output is one JSON: {events, hype:{hop,v}, speakers, emb:{t,v}, counters}.
Every pass fails OPEN and independently - a missing model or a crashed pass
drops that sense alone, never the whole job.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SR = 48000                 # the wav arrives at 48k (CLAP's native rate)
CHUNK_S = 10               # CLAP window
HOP_S = 5                  # CLAP hop
HYPE_WIN = 6.0             # arousal window
HYPE_HOP = 3.0
# 3.31 a hype window under this RMS (dBFS) on the ROOM is nobody
# talking: no model call, a 0 in the curve. The same number as lore.py's
# HL_VOICE_GATE_DB, measured in qa/sns331time.py (the lowest five-dB
# step eight dB over the median night's floor; loses 1.4 % of the
# median night's spoken seconds on the Mix, fewer on the room).
HYPE_GATE_DB = -60.0

# the default sound vocabulary; a per-game pack (ai/packs/<game>.txt, one
# prompt per line as  kind: prompt text) replaces or extends it
DEFAULT_PROMPTS = [
    ("cheer", "people cheering and celebrating loudly"),
    ("cheer", "a group of friends shouting with excitement and joy"),
    ("groan", "a frustrated groan of disappointment"),
    ("music", "epic orchestral boss battle music"),
    ("scare", "a sudden jump scare with screaming in a horror game"),
]
NEG_PROMPTS = [
    "people talking calmly over video game background sounds",
    "quiet video game ambience with soft background noise",
]
# THE ROOM PANEL. CLAP always answers with the nearest label on the list,
# so with only game moments on it the fluorescent hum of his backrooms
# night landed on "epic orchestral boss battle music" and the tome
# reported three music moments over a soundtrack that never existed.
# These are not events and they are not competitors to be out-run one at
# a time - that version ate 22 of hearthstone's 40 real music windows.
# They are a panel that says what the room sounds like when nothing is
# happening. Footsteps and wind were on this list and came straight off:
# those are things that HAPPEN in his games, not room tone.
ROOM_PROMPTS = [
    "room tone in an empty room",
    "a quiet hum",
    "an air conditioner running",
    "an electrical buzz from fluorescent lights",
    "silence",
    "static noise",
]
# How far over the room a label has to stand, in that label's own MADs.
# Measured on two of his nights: on hearthstone (real music) the weakest
# music mark stands 4.18 over the room and the weakest music stretch
# 3.67; on the backrooms hum night the strongest invented mark reaches
# 2.91 and the strongest invented stretch 2.13. 3.0 sits in that gap.
ROOM_MARGIN = 3.0
MUSIC_MIN_S = 20.0     # a music STRETCH has to really cover this long
VOICE_MARGIN = 0.10    # ECAPA cosine: the best voice over the runner-up
VOICE_FLOOR = 0.30     # under this it resembles no kept voice at all
SOLO_FLOOR = 0.45      # ...and with one voice kept there is no runner-up


def score_room(np, arr, npos):
    """What each label did OVER the room, window by window.

    Two steps, and the second is the one that matters. First every column
    against its own session median in its own MADs - raw CLAP scores are
    not comparable between prompts ("silence" reads 0.25 on his
    hearthstone night where "wind" reads 0.02), so no honest comparison
    starts from raw. Then the window's own median z, taken over the
    negatives and the room prompts only, is subtracted: a window where
    EVERY label rises is a window where nothing in particular happened,
    which is exactly what a hum does to a zero-shot tagger."""
    med = np.median(arr, axis=0)
    mad = np.median(np.abs(arr - med), axis=0)
    mad[mad <= 0] = 0.01
    z = (arr - med) / mad
    if arr.shape[1] <= npos:
        return z                      # no panel: nothing to subtract
    return z - np.median(z[:, npos:], axis=1)[:, None]


def sound_events(np, arr, over, prompts, hops):
    """Where a kind fires. RELATIVE, always: a kind fires where its sim
    stands clear of this session's own median for that kind, beats the
    negatives, and stands clear of the room. Returns (events, dropped) -
    the count matters, it is how many marks the room explained away and
    the log says so."""
    npos = len(prompts)
    # the negatives are the panel's FIRST columns only. The room prompts
    # sit past them now, and letting those in here would be a second,
    # silent gate on top of the one below.
    neg = arr[:, npos:npos + len(NEG_PROMPTS)].max(axis=1)
    ev, dropped = [], 0
    for ki in range(npos):
        col = arr[:, ki]
        med = float(np.median(col))
        mad = float(np.median(np.abs(col - med))) or 0.01
        for i, v in enumerate(col):
            if not (v - med > 4.5 * mad and v > neg[i] + 0.02):
                continue
            if over[i, ki] <= ROOM_MARGIN:
                dropped += 1              # the room won, not the game
                continue
            ev.append({"t": round(hops[i] + CHUNK_S / 2, 1),
                       "kind": prompts[ki][0],
                       "p": round(float(v - med), 3)})
    return ev, dropped


def music_spans(np, mover, hops, hot):
    """Stretches where the game itself is singing - a cutscene, a
    YouTube tab - so the words heard inside them can be flagged.

    The stretch is judged as ONE thing, not window by window: gating each
    window separately broke a real hearthstone stretch in half over a
    single dipped window. And the length test now measures what the span
    actually writes - the old one compared hop STARTS, 5s apart, while
    writing a span 5s longer than it had checked."""
    spans, run, thrown = [], None, 0
    n = len(hot)
    for ix in range(n + 1):
        h = bool(hot[ix]) if ix < n else False
        if h and run is None:
            run = ix
        elif not h and run is not None:
            a0, b0 = float(hops[run]), float(hops[ix - 1]) + CHUNK_S
            if b0 - a0 >= MUSIC_MIN_S:
                if float(np.median(mover[run:ix])) > ROOM_MARGIN:
                    spans.append([round(a0, 1), round(b0, 1)])
                else:
                    thrown += 1
            run = None
    return spans, thrown


def assign_voice(sims):
    """Which kept voice this utterance is, or 0 for "someone spoke and
    the ears cannot tell who".

    Two voices was the right answer for his backrooms night - the fault
    was per utterance. 134 of its 206 utterances fell under the cluster
    floor as singletons and carried no voice at all, so the panel
    borrowed a name from up to three seconds away, and that borrow is the
    swapping he sees. Scoring every utterance against the kept voices
    closes the gap; the margin keeps it honest. With ONE voice kept there
    is no runner-up to beat and the floor is the whole guard, so it has
    to be a real one: on that night 0.45 keeps all 51 of the first man's
    utterances and admits none of the other man's 21, where 0.25 - the
    two-voice floor - admitted 8 of them."""
    if not sims:
        return 0
    best = max(range(len(sims)), key=lambda i: sims[i])
    top = float(sims[best])
    if len(sims) == 1:
        return best + 1 if top >= SOLO_FLOOR else 0
    rest = max(float(v) for i, v in enumerate(sims) if i != best)
    if top < VOICE_FLOOR or top - rest < VOICE_MARGIN:
        return 0
    return best + 1


def _threads():
    return max(2, (os.cpu_count() or 8) - 4)


def load_prompts(game):
    out = list(DEFAULT_PROMPTS)
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        pf = os.path.join(base, "packs",
                          (game or "").strip().lower().replace(" ", "") + ".txt")
        if os.path.isfile(pf):
            got = []
            with io.open(pf, encoding="utf-8") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln or ln.startswith("#") or ":" not in ln:
                        continue
                    k, _, p = ln.partition(":")
                    if k.strip() and p.strip():
                        got.append((k.strip().lower()[:12], p.strip()))
            if got:
                out = got          # a pack REPLACES the defaults deliberately
    except Exception:
        pass
    return out


def say_prog(dst, done_s, total_s):
    try:
        with open(dst + ".prog", "w", encoding="utf-8") as fh:
            json.dump({"done_s": round(min(done_s, total_s), 1),
                       "total_s": round(total_s, 1)}, fh)
    except Exception:
        pass


def decimate(np, x, factor):
    """48k -> 16k with a cheap anti-alias average (speech models shrug at
    the residual; a full FIR is not worth the minutes it costs here)."""
    n = (len(x) // factor) * factor
    return x[:n].reshape(-1, factor).mean(axis=1)


def _read_ctl(src):
    """The beside-the-wav control file (the laughter ear reads the same
    shape): {src, game_wav, game_src, mic, threads}; {} when absent or
    unreadable, which is exactly the pre-3.31 worker."""
    try:
        with open(src + ".ctl", encoding="utf-8") as fh:
            d = json.load(fh) or {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _hype_prep(np, a16, src_name, gate_db=HYPE_GATE_DB):
    """The hype windows, prepared the way the model expects. Pure, so a
    test can lift it without torch. Yields (pos, segment-or-None).

    room: a window under gate_db RMS yields None (no model call - a
    voice app's gate writes true zeros and normalising those is noise
    amplified into a reading); the rest are zero-mean / unit-variance,
    which is exactly Wav2Vec2FeatureExtractor.zero_mean_unit_var_norm
    (models/hype/preprocessor_config.json do_normalize=true).
    mix (old files): every window, untouched - today's numbers."""
    hop, win = int(HYPE_HOP * 16000), int(HYPE_WIN * 16000)
    pos = 0
    while pos + 16000 <= len(a16):
        seg = np.ascontiguousarray(a16[pos:pos + win]).astype(np.float32)
        if src_name == "room":
            rms_db = 20.0 * np.log10(float(np.sqrt(np.mean(seg * seg)))
                                     + 1e-9)
            if rms_db < gate_db:
                yield pos, None
            else:
                yield pos, (seg - seg.mean()) / np.sqrt(seg.var() + 1e-7)
        else:
            yield pos, seg
        pos += hop


def load_mono(sf, np, path):
    """One 48 k mono float32 array off a wav - the room wav and the
    game wav come through the same door."""
    a, sr = sf.read(path, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != SR:
        raise SystemExit(f"expected {SR} Hz, got {sr}")
    return a


def main(src, dst, game="", mic=None):
    import numpy as np
    import soundfile as sf
    import torch
    ctl = _read_ctl(src)
    mic = mic or ctl.get("mic")
    game_wav = ctl.get("game_wav") or None
    src_name = str(ctl.get("src") or "mix")
    try:
        _thr = int(ctl.get("threads") or 0)
    except (TypeError, ValueError):
        _thr = 0
    torch.set_num_threads(max(1, min(_thr, os.cpu_count() or _thr))
                          if _thr > 0 else _threads())

    base = os.path.dirname(os.path.abspath(__file__))
    mdir = os.path.join(base, "models")
    a = load_mono(sf, np, src)
    dur = len(a) / float(SR)
    total_work = dur * 3.0             # three passes, roughly equal footing
    done_work = 0.0
    out = {"v": 1, "events": [], "hype": None, "speakers": [],
           "emb": [], "counters": {},
           # 3.31 whose ears: which layer fed each pass
           "src": {"clap": (str(ctl.get("game_src") or "game")
                            if game_wav else "mix"),
                   "hype": src_name, "who": src_name}}

    def _feat(x):
        # transformers 4.x returned tensors from get_*_features; 5.x wraps
        # them in model outputs - accept both
        if torch.is_tensor(x):
            return x
        for k in ("audio_embeds", "text_embeds", "pooler_output"):
            v = getattr(x, k, None)
            if v is not None and torch.is_tensor(v):
                return v
        v = getattr(x, "last_hidden_state", None)
        if v is not None:
            return v.mean(dim=1)
        raise RuntimeError("no embeddings in model output")

    # ---------------- CLAP: the sound vocabulary -------------------------
    # 3.31: over the GAME wav when the control file names one (boss
    # music lives there, not in the room); a game wav that will not
    # read fails this pass alone - never a fall-back to the room
    ca = a
    try:
        if game_wav:
            try:
                ca = load_mono(sf, np, game_wav)
            except Exception as e4:
                out["src"]["clap"] = None
                raise RuntimeError("game wav unreadable: " + str(e4)[:80])
        cdir = os.path.join(mdir, "clap")
        if not os.path.isdir(cdir):
            raise RuntimeError("clap model missing")
        from transformers import ClapModel, ClapProcessor
        model = ClapModel.from_pretrained(cdir, local_files_only=True).eval()
        proc = ClapProcessor.from_pretrained(cdir, local_files_only=True)
        prompts = load_prompts(game)
        texts = ([p for _, p in prompts] + NEG_PROMPTS
                 + ROOM_PROMPTS)
        with torch.no_grad():
            ti = proc(text=texts, return_tensors="pt", padding=True)
            temb = _feat(model.get_text_features(**ti))
            temb = temb / temb.norm(dim=-1, keepdim=True)
        hops, sims, aembs = [], [], []
        pos = 0
        step, win = int(HOP_S * SR), int(CHUNK_S * SR)
        while pos + SR <= len(ca):
            seg = ca[pos:pos + win]
            with torch.no_grad():
                ai = proc(audio=[seg], sampling_rate=SR, return_tensors="pt")
                em = _feat(model.get_audio_features(**ai))
                em = em / em.norm(dim=-1, keepdim=True)
            s = (em @ temb.T)[0].tolist()
            hops.append(pos / SR)
            sims.append(s)
            aembs.append(em[0])
            pos += step
            done_work = min(dur, pos / SR)
            say_prog(dst, done_work, total_work)
        npos = len(prompts)
        ev = []
        if sims:
            arr = np.asarray(sims)
            over = score_room(np, arr, npos)
            ev, room_drop = sound_events(np, arr, over, prompts, hops)
            out["counters"]["sound_dropped_room"] = room_drop
            # one mark per breath per kind: keep the strongest inside 20s
            ev.sort(key=lambda e: (e["kind"], e["t"]))
            kept = []
            for e in ev:
                if kept and kept[-1]["kind"] == e["kind"] \
                        and e["t"] - kept[-1]["t"] < 20:
                    if e["p"] > kept[-1]["p"]:
                        kept[-1] = e
                else:
                    kept.append(e)
            out["events"] = sorted(kept, key=lambda e: e["t"])[:150]
            # WHERE THE GAME ITSELF IS SINGING: sustained music-lead spans.
            # Words heard inside them are probably the game (a cutscene, a
            # YouTube tab), not the room - the app flags those lines.
            mus_ix = [ix for ix, pr in enumerate(prompts)
                      if pr[0] == "music"]
            if mus_ix:
                mcol = arr[:, mus_ix].max(axis=1)
                mmed = float(np.median(mcol))
                mmad = float(np.median(np.abs(mcol - mmed))) or 0.01
                hot = (mcol - mmed) > 3.0 * mmad
                mover = over[:, mus_ix].max(axis=1)
                spans, thrown = music_spans(np, mover, hops, hot)
                # [] is an ANSWER: the ears listened and heard no music.
                # The app clears its stale game-audio flags on that, and
                # only a missing key means "no opinion".
                out["music"] = spans[:40]
                out["counters"]["music_spans_dropped_room"] = thrown
        # the embeddings ride along (rounded, small) - "more like this"
        # and structured sound search read them later
        out["emb"] = [{"t": round(h, 1),
                       "v": [round(float(x), 4) for x in e[::4]]}   # 128-d
                      for h, e in zip(hops[::2], aembs[::2])]
        out["counters"]["clap_windows"] = len(hops)
        del model, proc
    except Exception as e:
        out["counters"]["clap_failed"] = str(e)[:120]
    del ca                    # the game array goes before the room's 16 k
    done_work = dur
    say_prog(dst, done_work, total_work)

    # ---------------- HYPE: the arousal curve ----------------------------
    try:
        hdir = os.path.join(mdir, "hype")
        if not os.path.isdir(hdir):
            raise RuntimeError("hype model missing")
        import torch.nn as nn
        from transformers import Wav2Vec2Model, Wav2Vec2Config

        class Head(nn.Module):          # audeering's regression head, vendored
            def __init__(self, cfg):
                super().__init__()
                self.dense = nn.Linear(cfg.hidden_size, cfg.hidden_size)
                self.dropout = nn.Dropout(cfg.final_dropout)
                self.out_proj = nn.Linear(cfg.hidden_size, 3)  # a/d/v

            def forward(self, x):
                x = torch.tanh(self.dense(self.dropout(x)))
                return self.out_proj(self.dropout(x))

        cfg = Wav2Vec2Config.from_pretrained(hdir)
        body = Wav2Vec2Model.from_pretrained(hdir, local_files_only=True).eval()
        head = Head(cfg)
        sd = torch.load(os.path.join(hdir, "pytorch_model.bin"),
                        map_location="cpu", weights_only=True)
        head.load_state_dict({k.replace("classifier.", ""): v
                              for k, v in sd.items()
                              if k.startswith("classifier.")}, strict=True)
        head.eval()
        a16 = decimate(np, a, 3)
        vals, quiet = [], 0
        with torch.no_grad():
            for pos, seg in _hype_prep(np, a16, src_name):
                if seg is None:
                    vals.append(0.0)       # nobody spoke: no reading
                    quiet += 1
                else:
                    h = body(torch.from_numpy(seg)[None, :]) \
                        .last_hidden_state.mean(dim=1)
                    ar = float(head(h)[0][0])      # arousal, roughly 0..1
                    vals.append(round(max(0.0, min(1.0, ar)), 3))
                say_prog(dst, dur + min(dur, (pos + int(HYPE_HOP * 16000))
                                        / 16000), total_work)
        if vals:
            out["hype"] = {"hop": HYPE_HOP, "v": vals, "src": src_name,
                           "norm": 1 if src_name == "room" else 0,
                           "gate_db": (HYPE_GATE_DB if src_name == "room"
                                       else None),
                           "quiet": quiet, "windows": len(vals)}
            out["counters"]["hype_windows"] = len(vals)
        del body, head
    except Exception as e:
        out["counters"]["hype_failed"] = str(e)[:120]
    done_work = dur * 2
    say_prog(dst, done_work, total_work)

    # ---------------- WHO: voices clustered ------------------------------
    try:
        edir = os.path.join(mdir, "ecapa")
        if not os.path.isfile(os.path.join(edir, "embedding_model.ckpt")):
            raise RuntimeError("ecapa model missing")
        sys.path.insert(0, os.path.join(base, "vendor_sb"))
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        # the inference wrapper wants to FETCH (symlinks, caches, privileges);
        # the checkpoint is right here - load the bare module instead
        from speechbrain.lobes.models.ECAPA_TDNN import ECAPA_TDNN
        from speechbrain.lobes.features import Fbank
        from speechbrain.processing.features import InputNormalization
        from silero_vad import get_speech_timestamps, load_silero_vad
        net = ECAPA_TDNN(input_size=80, lin_neurons=192,
                         channels=[1024, 1024, 1024, 1024, 3072],
                         kernel_sizes=[5, 3, 3, 3, 1],
                         dilations=[1, 2, 3, 4, 1],
                         attention_channels=128)
        net.load_state_dict(torch.load(
            os.path.join(edir, "embedding_model.ckpt"), map_location="cpu"))
        net.eval()
        fbank = Fbank(n_mels=80)
        inorm = InputNormalization(norm_type="sentence", std_norm=False)

        class _Enc:
            def encode_batch(self, x):
                f = fbank(x)
                f = inorm(f, torch.ones(x.shape[0]))
                return net(f)
        enc = _Enc()
        a16 = decimate(np, a, 3).astype(np.float32)
        spans = get_speech_timestamps(
            torch.from_numpy(np.ascontiguousarray(a16)), load_silero_vad(),
            sampling_rate=16000, min_silence_duration_ms=350,
            speech_pad_ms=60)
        # 0.7s, not 1.1: short callouts ("okay!", "wait-") carried no
        # voice at all, so the panel's chips read as random. ECAPA embeds
        # 0.7s well enough, and the cluster floor still drops strays.
        segs = [(s0["start"], s0["end"]) for s0 in spans
                if s0["end"] - s0["start"] >= int(0.7 * 16000)]
        if segs:
            embs = []
            with torch.no_grad():
                for i, (s0, s1) in enumerate(segs):
                    x = torch.from_numpy(np.ascontiguousarray(
                        a16[s0:min(s1, s0 + 16000 * 12)]))[None, :]
                    e = enc.encode_batch(x).squeeze()
                    embs.append(e / e.norm())
                    if i % 8 == 0:
                        say_prog(dst, dur * 2 + dur * (i / max(1, len(segs))),
                                 total_work)
            E = torch.stack(embs)
            labels = list(range(len(embs)))

            def merge_once():
                best, bi, bj = 0.0, -1, -1
                cents = {}
                for L in set(labels):
                    idx = [i for i, x in enumerate(labels) if x == L]
                    c = E[idx].mean(dim=0)
                    cents[L] = c / c.norm()
                ks = sorted(cents)
                for x in range(len(ks)):
                    for y in range(x + 1, len(ks)):
                        sc = float(cents[ks[x]] @ cents[ks[y]])
                        if sc > best:
                            best, bi, bj = sc, ks[x], ks[y]
                if best > 0.55:            # ECAPA cosine: same voice ~0.6+
                    for i, L in enumerate(labels):
                        if L == bj:
                            labels[i] = bi
                    return True
                return False
            while len(set(labels)) > 1 and merge_once():
                pass
            order = {}
            for L in labels:
                order[L] = order.get(L, 0) + 1
            # THE FLOOR THAT ATE HIS FRIENDS. 2.5% of a seven-hour
            # night is ~50 utterances - a quiet seventh player with
            # thirty lines was culled outright, every one of their
            # lines then reading "a voice". The floor is capped at 15
            # utterances: enough to drop strays, never enough to erase
            # a real person who mostly listens.
            keep = [L for L, n in order.items()
                    if n >= max(2, min(15, len(segs) // 80))]
            name = {L: i + 1 for i, L in enumerate(
                sorted(keep, key=lambda L: -order[L]))}
            # EVERY utterance is scored against the kept voices, not
            # only the ones the merge happened to gather: on his backrooms
            # night 134 of 206 fell under the cluster floor as singletons
            # and carried nothing, so the panel borrowed a name from up to
            # three seconds away. who = 0 means "someone spoke, and the
            # ears cannot tell which of them" - an honest gap the panel
            # can print, and a wall the borrow cannot climb over.
            cents = []
            for L in sorted(keep, key=lambda L: -order[L]):
                idx = [i for i, x in enumerate(labels) if x == L]
                c = E[idx].mean(dim=0)
                cents.append(c / c.norm())
            unknown = 0
            if cents:
                with torch.no_grad():
                    vs = (E @ torch.stack(cents).T).tolist()
                for (s0, s1), row in zip(segs, vs):
                    who = assign_voice(row)
                    if not who:
                        unknown += 1
                    out["speakers"].append({"a": round(s0 / 16000, 2),
                                            "b": round(s1 / 16000, 2),
                                            "who": who})
                # THE PRINTS RIDE ALONG so the names he types survive a
                # re-run. A redo renumbers the clusters by size, so
                # "voice 1" is not the same man twice and carrying a name
                # by number was a coin flip; the app matches these.
                out["voices"] = [{"n": i + 1,
                                  "v": [round(float(x), 4)
                                        for x in c.tolist()]}
                                 for i, c in enumerate(cents)]
            out["counters"]["speaker_clusters"] = len(keep)
            out["counters"]["speaker_utts"] = len(segs)
            out["counters"]["speaker_unknown"] = unknown
            # THE MIC LAYER (2.81+): embed a few utterances from HIS mic
            # track and the nearest cluster is him - named automatically
            if mic and os.path.isfile(mic) and keep:
                try:
                    import soundfile as sf3
                    ma, msr = sf3.read(mic, dtype="float32")
                    if ma.ndim > 1:
                        ma = ma.mean(axis=1)
                    if msr != 16000:
                        ma = decimate(np, ma.astype(np.float32),
                                      max(1, int(msr // 16000)))
                    msp = get_speech_timestamps(
                        torch.from_numpy(np.ascontiguousarray(
                            ma.astype(np.float32))),
                        load_silero_vad(), sampling_rate=16000,
                        min_silence_duration_ms=350, speech_pad_ms=60)
                    msp = [m2 for m2 in msp
                           if m2["end"] - m2["start"] >= int(1.2 * 16000)][:6]
                    if msp:
                        mes = []
                        with torch.no_grad():
                            for m2 in msp:
                                x2 = torch.from_numpy(np.ascontiguousarray(
                                    ma[m2["start"]:m2["start"]
                                       + 16000 * 10]))[None, :]
                                e2 = enc.encode_batch(x2).squeeze()
                                mes.append(e2 / e2.norm())
                        mc = torch.stack(mes).mean(dim=0)
                        mc = mc / mc.norm()
                        best, bl = -1.0, None
                        for L in keep:
                            idx = [i2 for i2, x2 in enumerate(labels)
                                   if x2 == L]
                            c2 = E[idx].mean(dim=0)
                            sc2 = float((c2 / c2.norm()) @ mc)
                            if sc2 > best:
                                best, bl = sc2, L
                        if bl is not None and best > 0.4:
                            out["names"] = {str(name[bl]): "you"}
                except Exception as e3:
                    out["counters"]["mic_anchor_failed"] = str(e3)[:100]
    except Exception as e:
        out["counters"]["who_failed"] = str(e)[:120]

    with open(dst + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    os.replace(dst + ".tmp", dst)
    say_prog(dst, total_work, total_work)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: senses_worker.py <in.wav> <out.json> [game] [mic]",
              file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(main(sys.argv[1], sys.argv[2],
                      sys.argv[3] if len(sys.argv) > 3 else "",
                      sys.argv[4] if len(sys.argv) > 4 else None))
    except Exception as e:
        print(f"SENSES_WORKER_FAILED {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

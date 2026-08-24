# -*- coding: utf-8 -*-
"""LORE's ear for laughter and screams: PANNs CNN14, gated by voice detection.

Called as a subprocess, exactly like the transcriber:

    laugh_worker.py <input.wav (32kHz mono)> <output.json> [checkpoint.pth]

WHY THIS EXISTS. The gold marks come from loudness prominence and the red
chapters from words - but a laugh is neither loud enough to always win a
prominence contest nor a word the transcriber writes down. This model heard
two million YouTube clips and knows what laughter IS, in any language, even
under game audio. Screams too, which in a horror house is half the point.

The model class below is the original Cnn14_DecisionLevelMax from
qiuqiangkong/audioset_tagging_cnn, vendored so nothing here needs librosa or
its numba chain - torchlibrosa does the mel front-end in plain torch. The
checkpoint is the published AudioSet one (mAP 0.385, framewise heads).

Class indices verified against metadata/class_labels_indices.csv:
    16 Laughter, 18 Giggle, 19 Snicker, 20 Belly laugh, 21 Chuckle/chortle
    14 Screaming
"""
import json
import os
import sys
import time

# torchlibrosa ships VENDORED beside this file (11 KB of plain torch code):
# the venv sits in Program Files where pip cannot write without elevation,
# and a worker that needs an installer step is a worker that breaks
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SR = 32000                 # what CNN14 was trained on - the wav must arrive
#                            at 32 kHz mono; ffmpeg makes it, nothing resamples
LAUGH = (16, 18, 19, 20, 21)
SCREAM = (14,)
CHUNK_S = 30               # per model call, bounds memory
PAD_S = 3.0                # laughs sit at the EDGES of speech spans
# MEASURED ON HIS OWN RECORDINGS: a real, transcript-confirmed laugh under
# Discord compression and game audio peaks at ~0.05, not 0.5 - the mix
# buries the class. So detection is RELATIVE: collect every sustained
# blip above a tiny floor, then keep what stands clear of that session's
# own noise. A global threshold would have returned nothing, ever.
FLOOR = 0.008              # candidate collection floor
SUS = {"laugh": 0.6,       # a laugh holds for a while; a click does not
       "scream": 0.30}     # a real shriek is SHORT - the shared 0.6s bar
#                            ate whole Backrooms screams (reported, fixed)
ABS_KEEP = {"laugh": 0.015, "scream": 0.010}
REL_KEEP = {"laugh": 5.0, "scream": 3.5}
_REL_DOC = 5.0             # ...or below ~5x the session's BACKGROUND (the
#                            median per-second score across all speech) -
#                            never relative to the candidates themselves,
#                            which rejects a session whose one candidate
#                            is the real thing
REL_CAP = 0.06             # but a loud night must not drown its best laughs


def build_model(torch, nn):
    from torchlibrosa.stft import Spectrogram, LogmelFilterBank

    class ConvBlock(nn.Module):
        def __init__(self, cin, cout):
            super().__init__()
            self.conv1 = nn.Conv2d(cin, cout, 3, 1, 1, bias=False)
            self.conv2 = nn.Conv2d(cout, cout, 3, 1, 1, bias=False)
            self.bn1 = nn.BatchNorm2d(cout)
            self.bn2 = nn.BatchNorm2d(cout)

        def forward(self, x, pool_size):
            import torch.nn.functional as F
            x = F.relu_(self.bn1(self.conv1(x)))
            x = F.relu_(self.bn2(self.conv2(x)))
            if pool_size != (1, 1):
                x = F.avg_pool2d(x, kernel_size=pool_size)
            return x

    class Cnn14_DecisionLevelMax(nn.Module):
        def __init__(self):
            super().__init__()
            self.interpolate_ratio = 32
            self.spectrogram_extractor = Spectrogram(
                n_fft=1024, hop_length=320, win_length=1024, window="hann",
                center=True, pad_mode="reflect", freeze_parameters=True)
            self.logmel_extractor = LogmelFilterBank(
                sr=SR, n_fft=1024, n_mels=64, fmin=50, fmax=14000,
                ref=1.0, amin=1e-10, top_db=None, freeze_parameters=True)
            self.bn0 = nn.BatchNorm2d(64)
            self.conv_block1 = ConvBlock(1, 64)
            self.conv_block2 = ConvBlock(64, 128)
            self.conv_block3 = ConvBlock(128, 256)
            self.conv_block4 = ConvBlock(256, 512)
            self.conv_block5 = ConvBlock(512, 1024)
            self.conv_block6 = ConvBlock(1024, 2048)
            self.fc1 = nn.Linear(2048, 2048, bias=True)
            self.fc_audioset = nn.Linear(2048, 527, bias=True)

        def forward(self, x):
            import torch.nn.functional as F
            x = self.spectrogram_extractor(x)
            x = self.logmel_extractor(x)
            frames_num = x.shape[2]
            x = x.transpose(1, 3)
            x = self.bn0(x)
            x = x.transpose(1, 3)
            x = self.conv_block1(x, (2, 2))
            x = self.conv_block2(x, (2, 2))
            x = self.conv_block3(x, (2, 2))
            x = self.conv_block4(x, (2, 2))
            x = self.conv_block5(x, (2, 2))
            x = self.conv_block6(x, (1, 2))     # keep the TIME axis - the
            #                                     whole point is when
            x = torch.mean(x, dim=3)
            x1 = F.max_pool1d(x, kernel_size=3, stride=1, padding=1)
            x2 = F.avg_pool1d(x, kernel_size=3, stride=1, padding=1)
            x = x1 + x2
            x = x.transpose(1, 2)
            x = F.relu_(self.fc1(x))
            seg = torch.sigmoid(self.fc_audioset(x))     # (B, T', 527)
            # 10ms frames again: undo the 2^5 time pooling
            fr = seg.repeat_interleave(self.interpolate_ratio, dim=1)
            if fr.shape[1] < frames_num:
                fr = torch.cat(
                    [fr, fr[:, -1:, :].repeat(1, frames_num - fr.shape[1], 1)],
                    dim=1)
            return fr[:, :frames_num, :]

    return Cnn14_DecisionLevelMax()


def main(src, dst, ckpt_path):
    import numpy as np
    import soundfile as sf
    import torch
    import torch.nn as nn
    from silero_vad import get_speech_timestamps, load_silero_vad

    ctl_path = src + ".ctl"
    default_threads = max(2, (os.cpu_count() or 8) - 4)

    def apply_threads():
        n = default_threads
        try:
            with open(ctl_path, encoding="utf-8") as fh:
                m = int(json.load(fh).get("threads") or 0)
            if m > 0:
                n = max(1, min(m, os.cpu_count() or m))
        except Exception:
            pass
        torch.set_num_threads(n)

    apply_threads()

    a, sr = sf.read(src, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != SR:
        raise SystemExit(f"expected {SR} Hz, got {sr}")

    # WHERE PEOPLE ARE. Silero listens at 16k; every second sample of a 32k
    # signal is exactly that. Only speech (padded - laughs OVERHANG speech)
    # is ever scored, which is both the honesty and the speed of this.
    spans = get_speech_timestamps(
        torch.from_numpy(np.ascontiguousarray(a[::2])), load_silero_vad(),
        sampling_rate=16000, min_silence_duration_ms=400, speech_pad_ms=150)
    merged = []
    for s in spans:
        lo = max(0, s["start"] * 2 - int(PAD_S * SR))
        hi = min(len(a), s["end"] * 2 + int(PAD_S * SR))
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])

    events = []
    if merged:
        model = build_model(torch, nn)
        try:
            ck = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        except Exception:
            ck = torch.load(ckpt_path, map_location="cpu",
                            weights_only=False)
        sd = ck.get("model", ck) if isinstance(ck, dict) else ck
        missing, unexpected = model.load_state_dict(sd, strict=False)
        real_missing = [k for k in missing if "spec" not in k]
        if real_missing:
            raise SystemExit(f"checkpoint mismatch: {real_missing[:4]}")
        if unexpected:
            # harmless today, but a swapped checkpoint should say so
            print(f"laugh: {len(unexpected)} unexpected checkpoint key(s) "
                  f"ignored, e.g. {unexpected[:2]}", file=sys.stderr)
        model.eval()

        FPS = SR / 320.0                       # framewise resolution, 10ms
        prog_total = max(0.1, sum(hi - lo for lo, hi in merged) / float(SR))
        prog_done = 0.0
        prog_t = [0.0]

        def say_prog():
            try:
                with open(dst + ".prog", "w", encoding="utf-8") as fh:
                    json.dump({"done_s": round(min(prog_done, prog_total), 1),
                               "total_s": round(prog_total, 1)}, fh)
            except Exception:
                pass
        cands = {"laugh": [], "scream": []}
        bg = {"laugh": [], "scream": []}       # per-second maxes: the noise
        for lo, hi in merged:
            pos = lo
            while pos < hi:
                apply_threads()                # he alt-tabbed; give it back
                end = min(hi, pos + CHUNK_S * SR)
                if end - pos < SR:
                    break
                x = torch.from_numpy(
                    np.ascontiguousarray(a[pos:end]))[None, :]
                with torch.no_grad():
                    fr = model(x)[0].numpy()   # (T, 527)
                base = pos / float(SR)
                for kind, idxs in (("laugh", LAUGH), ("scream", SCREAM)):
                    curve = fr[:, list(idxs)].max(axis=1)
                    bg[kind].extend(
                        float(curve[s:s + 100].max())
                        for s in range(0, len(curve), 100))
                    # sustained runs above the floor -> one candidate at the
                    # run's peak; 3s of separation so a giggle-fit is one
                    # mark, not eleven
                    got = cands[kind]
                    on = curve >= FLOOR
                    i = 0
                    while i < len(on):
                        if not on[i]:
                            i += 1
                            continue
                        j = i
                        while j < len(on) and on[j]:
                            j += 1
                        if (j - i) / FPS >= SUS[kind]:
                            seg = curve[i:j]
                            pk = int(seg.argmax())
                            t = base + (i + pk) / FPS
                            p = float(seg[pk])
                            if got and t - got[-1][0] < 3.0:
                                if p > got[-1][1]:
                                    got[-1] = (t, p)
                            else:
                                got.append((t, p))
                        i = j
                prog_done += (end - pos) / float(SR)
                if time.time() - prog_t[0] > 2.0:
                    prog_t[0] = time.time()
                    say_prog()
                # overlap the next chunk by 2s: a laugh straddling a chunk
                # seam used to reset the sustain test and vanish (the 3s
                # candidate separation absorbs any double-sighting)
                pos = end if end >= hi else max(pos + SR, end - 2 * SR)

        # WHAT STANDS CLEAR OF THIS SESSION'S OWN NOISE. The keep bar is
        # relative to the session's background score, floored and capped,
        # then the best survivors are spread out like the gold marks are.
        dur = len(a) / float(SR)
        for kind, got in cands.items():
            if not got:
                continue
            noise = sorted(bg[kind])[len(bg[kind]) // 2] if bg[kind] else 0.0
            bar = max(ABS_KEEP[kind], min(REL_CAP, REL_KEEP[kind] * noise))
            good = [(t, p) for t, p in got if p >= bar]
            # HIS RULE: every real moment survives - the cap is a sanity
            # rail, not a curator. Presentation handles density.
            cap = int(min(60, max(8, dur / 120.0)))
            chosen = []
            for t, p in sorted(good, key=lambda c: -c[1]):
                if len(chosen) >= cap:
                    break
                if all(abs(t - c[0]) >= 6.0 for c in chosen):
                    chosen.append((t, p))
            events.extend({"t": round(t, 1), "p": round(p, 3), "kind": kind}
                          for t, p in chosen)

    events.sort(key=lambda e: e["t"])
    with open(dst + ".tmp", "w", encoding="utf-8") as fh:
        json.dump({"events": events, "engine": "panns-cnn14"}, fh)
    os.replace(dst + ".tmp", dst)   # never torn JSON under the final name
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: laugh_worker.py <in.wav> <out.json> [ckpt]",
              file=sys.stderr)
        sys.exit(2)
    ck = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "models",
        "Cnn14_DecisionLevelMax_mAP=0.385.pth")
    try:
        sys.exit(main(sys.argv[1], sys.argv[2], ck))
    except Exception as e:
        print(f"LAUGH_WORKER_FAILED {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

# LORE — briefing for the next external review

**Audience:** ChatGPT Codex (or any external reviewer).
**Prepared:** 2026-09-01, alongside LORE v3.23.
**Purpose:** your previous review (`CODEX_LORE_AI_REVIEW.md`, written
against v3.21 / `ffeb213`) was read closely, verified claim-by-claim
against the live code, and acted on. This file tells you what has
changed since, which of your findings were confirmed / already fixed /
rejected, and the product laws you must respect so your next review
spends its effort where it counts.

**Change policy for you:** audit and findings only — no code changes.
Cite live line numbers from the current checkout, not from memory of
this document; the files move fast.

---

## 1. Product laws (owner decisions — do not relitigate)

1. **Hands-off, full AI.** The owner's words: *"the purpose of the
   system is hands off, full AI... getting involved manually is not
   what i want to do."* Your P0 recommendation "auditor proposes, user
   approves" was considered and **rejected**. Do not propose
   approve-first flows, corrections inboxes, or "uncertain" badges
   whose remedy is manual review. The correct direction is always to
   make the *automatic* pipeline more accurate: stronger gates,
   lineage-aware evidence, sense-tests on every mutation, banked
   reversibility, and visible-but-non-blocking change logs.
2. **Automatic-but-banked.** Every automatic mutation must be
   recoverable (`.v1/.v2/.v3` chains, `was=` originals, the attic).
   The owner was burned by silent *drops*, never by repairs. A finding
   that a mutation is unbanked is always valid; a finding that a
   mutation is automatic is not, by itself, a finding.
3. **No build step; two big files are deliberate.** `lore.py` and
   `ui.html` stay monolithic; features are appended as self-contained
   blocks. Do not recommend splitting them or introducing a bundler.
4. **The UI is a hand-crafted tome.** `el(tag, cls, html)`'s third
   argument is innerHTML — every dynamic string must pass `esc()`.
   Unescaped `</script>` inside built strings kills the whole script
   block. These are the two classic UI foot-guns here.
5. **The GPU belongs to games.** Background AI yields to a running
   game; the describer will not load onto a card a game has focus of.
   Scheduling findings must respect that hierarchy.
6. **Bilingual by design.** The owner speaks Emirati Gulf Arabic and
   English, switching mid-sentence. Any text heuristic that only
   handles Latin (capitalisation tests, token regexes) is a bug — this
   exact class produced a fabricated title relationship (see §3).

## 2. Architecture (unchanged since your review)

Your system map remains accurate: recording → loudness/highlights
(`.hl`/`.lvl`) + VAD→ASR (`.stt`) + CLAP/hype/voice/laughter (`.sns`)
+ OCR (`.ins` inputs) + eye (`.vis`) → describer (`.ins`) → auditor
(`.aud`, may rewrite `.stt`/`.ins` — banked). Sidecars live in
`D:\Records\.lore_thumbs\<basename>.<kind>.json`. Workers are in
`ai\`; `asr_worker.py` is the transcriber (Qwen3-ASR-1.7B, Silero VAD,
temperature 0).

## 3. What changed since v3.21 (so you do not re-report it)

### v3.22 — "the transcripts stop lying" (`6ff787e`)
Driven by a 41-agent audit of all 521 transcripts (independent of your
review, convergent with parts of it):

- **Physics gate** (`asr_worker.py`, `_impossible`): any line whose
  speech-characters-per-second exceeds what a mouth can do (>40
  Latin-majority, >30 Arabic-majority, tashkeel stripped, judged by
  script never by the lang tag) triggers one no-context retry; the
  retry faces the same walls. Kills the prompt-*paraphrase*
  fabrication class (~1,022 impossible lines library-wide, canned
  strings at 78–263 cps recurring byte-identically across nights).
  This partially addresses your §7 (no acoustic evidence): the
  timing-impossibility signal is now used.
- **`_ctx_echo` short arm**: your §7 note that the echo guard needs
  ≥7 content words was correct and is now closed — a short line that
  collapses (boundary-aligned, alnum-only) onto the game-title clause
  of the context prompt is treated as an echo and re-asked without
  context. Handles titles with periods (R.E.P.O) and two-letter
  shelves (Ds); a title cannot match inside a longer word.
- **Script-derived language tags**: the stored `lang` was wrong on 44%
  of Arabic lines and the decode loop *learned* the lie (`last`
  pinning). The characters decide now, before `last` learns anything;
  a blanked line teaches nothing; and `_aud_dossier` re-derives
  [ar]/[en] from the characters at read time, healing every existing
  sidecar's dossier without touching the library.
- **READER/_STT_READER = 3**: transcripts now stamp their guard
  generation. Old transcripts are counted once at boot and never
  re-read automatically (owner's recorded decision: bulk re-reads are
  priced on a card, his call).

### v3.24 — the response to your second review
Your v3.23 follow-up (`CODEX_LORE_V3.23_HANDS_OFF_REVIEW.md`) was
verified and acted on the same day:

- **C1 shipped, then hardened by the pre-ship fleet**: a transcript
  fix is refused when the span's audio re-listen (`g["ear"]`) shares
  zero distinctive tokens with the proposal. The first cut compared
  raw `_aud_lat` tokens and was measured refusing 27 of 308
  known-good historical repairs (8.8%) — exact tokens are vowel- and
  spacing-blind across scripts ("Rastin." vs راستن). The shipped gate
  falls back to the consonant-skeleton comparator (`_aud_ear_agrees`:
  skeleton containment + phonetic equivalence) before refusing, and a
  refusal is no longer invisible: it writes `unclear` + the reason on
  the row via setdefault, strikes nothing, and carries. Spans the ear
  never reached keep prior behaviour — a gate that cannot see does
  not guess.
- **C2 shipped, after the fleet killed my first version as a
  tautology**: `g["ear"]` only exists because the re-listen already
  passed `_aud_sense` at write time, so re-asking "is the ear
  readable?" could never say no — it would have vetoed 147 of 316
  historical strikes (46%) and the veto froze via the carry. The
  shipped veto demands strictly more than the write-gate guaranteed:
  ≥2 real word-tokens, no library-unknown words, no CJK static —
  measured 30 of 147 vetoed, each a line that genuinely reads. A
  vetoed row (`ear_kept`) is NOT carried — it is re-litigated at the
  next audit — and a later fix beats the downgrade in dedup.
  Junk/absent ears still strike — the owner's recorded request ("it
  tried and it couldnt... say unintelligible") covers exactly that
  case and only that case.
- **C3 shipped**: ask_video's answer prose is replaced with an
  explicit could-not-verify verdict when every hit fails; with
  survivors it stands, footnoted.
- **C4 shipped**: one-word quote matching is contiguous whole-token
  equality, both scripts ("no" can no longer verify inside "know");
  the fleet then found Arabic punctuation (؟ ، ؛) glues tokens under
  `\w`, so both sides shed it before tokenising.
- **C5 shipped**: ask_library never keeps an invented time — an
  ungrounded hit opens without seeking (t=0 is the file's own no-seek
  convention).
- **C8 shipped**: the quote-recovery prefix strip is script-blind
  (your point interacted with our own 3.23 change that puts Arabic
  voice names on lines).
- **Your QA complaint answered**: the deterministic roster is now
  committed at `qa/` (24 suites + runner + README) so the reported
  numbers can be replayed from the repository. Note for your review:
  every literal that originated in a real recording (names, quoted
  lines, garble samples, timestamps) was rewritten as
  structure-preserving fiction across qa/, lore.py's docstrings and
  few-shot prompts, asr_worker's docstrings, and ui.html's demo data
  before publication. Do not treat those strings as ground truth from
  the library — they are synthetic stand-ins with the same shape.
- **Rejected by measurement**: "the re-listen always primes Arabic" —
  deliberate, not a bug. The shortlist it serves is precisely
  suspected-Arabic-misrendered-as-Latin (the garble detector's shape)
  and 258 of 307 historical fixes are Latin→Arabic rewrites; an
  auto/English pin would defeat the ear on the class it exists for.
- **Open, agreed, queued**: your decode-panel consensus (multi-decode
  agreement before corrections), describer token-bounded chunking,
  claim-level (not just quote-level) validation, lineage-aware auditor
  voting, `ins_validation` retroactive pass, and OCR/vision
  persistence. These are on the ledger with your specs as the design
  reference.

### v3.27 — the rest of your fourth review, judged item by item
Everything below was measured on the real shelf before it was written,
and five of your remedies were rejected with numbers rather than
implemented. Read this section before re-reporting any of it.

- **F07 SHIPPED, but your mechanism was wrong.** Even-row context
  thinning never fired on the flagship file (windows rendered
  2504/2274/2881 tokens against room for 4132). The real cause is the
  head: `"Three to five stretches."` — 69% of 971 historical asks
  returned 3–5 stretches at ~12 lines each, so ONE ask covers a median
  of 48 lines regardless of window size. Shipped: a pending-range loop
  (contiguous runs, ASK_MAX 5, MIN_RUN 6), `want` stretches asked for
  by run length, schema maxItems 8→12, per-ask token cap, `src` row
  ranges per stretch, a `cov` block (rows/told/frac/gaps with
  silence-vs-untold), and `missing` extended by `_win_owes`. A window
  RESUMES from disk (stretches, spent asks, and the range it left), so
  the budget is spent across runs and a night the model cannot finish
  becomes terminal.
  **REJECTED — coverage-gated `complete`** (your F07 exact-change): it
  makes such a night un-finishable and loops the GPU forever, because
  `tries` resets whenever any window lands. `_ins_done_honest` consults
  the cov block instead, which is terminal by construction.
  **REJECTED — fixed-size chunking** (5× the asks, measured) and
  **bumping `_INS_GENERATION`** (58 GPU-hours, automatic, unasked).
  Also fixed in passing: the cross-window "story so far" block read
  `sgm["label"]`, but stored stretches only ever carry `name` — every
  cross-window ask ever made was handed an empty string.
- **F08 SHIPPED NARROWED.** Your salience remedy was measured to
  *promote* the offending subject: "Toilets and Team Play" is the
  SECOND-LONGEST chapter of that night (339.6s of 19), and shelf-wide
  the longest chapter of a night holds 22.9% of its clock but only
  10.7% of its moments — duration is an anti-signal. Shipped: a
  blended ledger (0.45 duration + 0.30 cited rows + 0.25 moments and
  gold) that re-orders the SAME single ask heaviest-first with weights
  inline; no extra model call. The list-clamp fallback prefers the
  clock and uses the ledger only to break ties (left to itself it
  overruled the longest chapter by 0.003 and named noise over
  content). The real fix for that title is F07, not F08 — the boss
  outcome was never in the candidate set.
- **F09 SHIPPED (proximity half).** `_aud_says` now picks the row that
  COVERS the second, not the first within ±4s (45.7% of "agreements"
  had no overlap; 813 skipped a covering row), and says how far away a
  near-miss was. A chapter label no longer votes (86% span 60s+); a
  moment votes only when it names the second; `agrees == ["review"]`
  is dropped. Structured reason codes and carry generations remain
  queued.
- **F12/F13/F16 — SCHEMA MIGRATION REJECTED.** Your mechanism is also
  wrong here: nothing overwrites. `_merge_sns_into_hl` is FIRST WRITER
  WINS (`if "kind" not in near[0]`), `_merge_vis_into_hl`'s collision
  arm is a deliberate `pass`, and laughter only appears to dominate
  because it lands in the gold pass before the folds run. Measured
  18.8% loss (516/2,746). The full `signals[]` array cannot be cashed
  out on the read side — the tome draws one node per event with one
  colour, the picker keys on the second, and the cluster pass folds
  same-second ticks into one — so three ticks for three signals would
  violate your own acceptance criterion. Shipped instead: an additive
  `also` list on the same event (every existing reader, including an
  un-updated exe and the banked attic, ignores an unknown key), UI
  chip/tooltip opt-ins, and a re-fold walk that recovers the lost
  signals from the sidecars with zero model calls.
- **F14 SHIPPED.** Worse than you reported: 1,749 gold marks carry
  `kind == "creature"` — 8.9% of the entire 19,545-mark timeline —
  and at most ~155 are plausibly an enemy. `_eye_worth` gates on
  not-a-creature words, menu/board context (in `place` AND `doing`),
  and then either a hostile-creature word or an actor verb. Measured
  9.4% keep, per-game: Rocket League 1.2%, Hearthstone 1.9%, Lies of P
  50.3%, Supraland 69.1%. `_vis_promote_migration` re-judges the
  existing marks once, banked, and only where a mark can be matched to
  a look today's gate rejects.
- **F15 NOT SHIPPED.** Confirmed and queued; the eye outranked it per
  GPU-second and the sampler needs its own cost budget.
- **F05 SHIPPED NARROWED.** The leash fires on 25.9% of ALL utterances
  (8,291) and 56.1% of the flagship night, and it replaced the first
  decode on a language TAG with no accept test — the only guard in
  that worker without one. It now keeps the first answer when the
  retry is empty, foreign-alphabet, physically impossible, a prompt
  echo, or written in the script the pin was pushing (both directions
  — guarding one direction made Arabic win every argument and latch).
  The loser is persisted as `alt`. Mic-only VAD spans are unioned in
  (subtracted first, fragments dropped, capped by a stop the way
  TRANSLIT_MAX and ENWALL_MAX are). READER 3→4.
  **REJECTED — your content-agreement arbiter**: 893 library lines
  score below the only available dictionary floor and every one read
  is his own Gulf Arabic or an Arabic name.

### v3.26 — the response to your fourth review (the lifecycle audit)
Your `CODEX_LORE_FULL_EVIDENCE_AND_FUNCTIONAL_AUDIT.md` +
implementation brief were verified finding-by-finding on the real
shelf; every checked claim held. Shipped in v3.26 (each measured
before landing):

- **F01/F02**: `_aud_retell` stages a complete review's cut to
  `.ins.json.new` and rides the existing upgrade lane (bank + atomic
  swap on completion; resume clause added to `_ins_owing_raw`). The
  served file is untouched on failure — and the audit's INS source
  stamp becomes honest by construction, with the completed swap
  re-owing the audit via `_aud_covers_now` (your automatic
  revalidation, via machinery that already existed). Mid-build
  reviews keep the in-place cut (nothing complete stands to lose).
  `qa/aud302test.py`'s destructive assertions were replaced with the
  staged contract.
- **F03/F20**: `_stt_current_doc` / `_stt_stale_reader` (reader ≥
  `_STT_READER`, engine family by prefix) + silver display with an
  honest why; `_transcribe_one` refuses a stale installed worker
  up-front (generation parity via the worker's own READER constant).
  Bulk re-read stays behind `reread_old` (owner's recorded pricing
  decision) — the cascade (stt → ins via `src_stt` reader stamp →
  aud via `_aud_covers_now`) is fully wired when he flips it.
- **F10**: `_aud_ear_veto` extracted as the single source of truth
  (live audit + migration share it — an oracle copy drifts);
  `_aud_strike_migration` replays it once per aud sidecar over every
  machine strike: restore from `was`, bank first, aud row →
  unclear+ear_kept (re-litigated fresh, never carried), staged
  retell for the windows, pins untouched, `sg` stamp for
  idempotence. Prompt-echo ears (your relisten prompt reflected
  back) are junked at the writer and veto nothing — 8 of 74 raw
  candidates were this.
- **F11**: ask_video `hits=[]` + non-negative prose → deterministic
  not-found; ask_library requires ≥1 transcript-grounded hit for its
  prose. (Full claim-level grounding + STT root indexing remains
  queued per your phases.)
- **F17/F18/F08/F06/F04**: hype NMS-by-strength top-40; `_ins_retone`
  reads HL laugh/scream (the old code searched `.sns`, where laughter
  has never lived) and judges cold rows (unsupported+cold → plain
  moment); title list-clamp (≥2 commas or >9 words → longest-lived
  chapter name) + word-safe cut replacing `[:120]`; extraction 90%
  duration parity mirroring the sound pass; stt `run` telemetry
  block + worker engine preserved (family-checked everywhere).
- **Deliberately NOT shipped yet** (queued as v3.27 with your
  fixtures): F07 coverage loop + F08 salience ledger (coverage
  first, as you ordered), F09 lineage voting, F12/F13/F16 signals[]
  schema + standing view + montage calibration, F14 vision roles,
  F15 OCR sampling, F05 candidate arbitration + Mic-VAD union.

### v3.25 — the response to your third review
Your v3.24 review (`CODEX_LORE_V3.24_VALUE_REVIEW.md`) was verified
the same day. All four findings CONFIRMED (both P0s functionally, on
the live functions). Your P0-1 *remedy* was measured NET HARMFUL
before it could ship — replayed over all 308 historical repairs, the
content-anchor rule caught zero bad corrections and refused 12–31
good ones, because 80% of real fixes adopt the ear's own words
verbatim and short Gulf colloquial lines are all "stopwords". What
shipped instead (each arm measured at zero historical cost):

- **P0-1 closed**: order of evidence in the correction gate —
  (1) identity: the fix adopts the ear's words (whole latinized
  token-list equality ONLY — subset arms were measured carrying zero
  unique repairs while admitting echo-prefix fabrications, and were
  dropped); (2) a content token: at least one shared non-filler word
  (`_aud_filler`: top-2% latinized vocab by frequency, name-aware via
  the lowercase counts so frequent friend-names can never become
  filler, hand-list-only under 1,000 words, cached on the vocab
  rebuild stamp); (3) the skeleton comparator; else refuse with the
  `unclear` trace. Your synthetic ("The sniper boss" on a shared
  "the") refuses; all 291 historically-accepted repairs still accept.
- **P0-2 closed**: an agreement veto runs BEFORE the readable veto
  and deliberately skips `_aud_sense` — a non-junk ear whose token
  list equals the row's own text, or which agrees by skeleton
  (including whole-string skeleton equality at length ≥2, for the
  two-consonant names), downgrades `noise` to `unclear` + `ear_kept`.
  Replayed: every previously-banked one-word genuine repetition now
  survives; junk/CJK/unrelated ears still strike.
- **Consistency**: the sense gate now honours the same convergence —
  a verbatim ear adoption passes even when every word is
  library-new (two listeners beat the dictionary in both gates).
- **Your QA-1 fixed**: the recorder scenario drives the real
  `_looks_gone()` with the production 3-poll debounce; `finding()`
  now FAILS the suite on a demonstrated defect; stale line citations
  refreshed.
- **Your QA-2 fixed**: `run_all.bat` preflights python imports
  (psutil, PyAudioWPatch) and node with a precise one-shot message;
  the README documents the environment and the two installed-app-
  dependent suites. `codex325test` (19 checks) locks your acceptance
  bar plus the fleet's round-2 fabrication shapes.

### v3.23 — the response to your review
See `CURRENT-BUILD.md` and the v3.23 commit message for the precise
list. In summary, the confirmed subset of your findings was shipped
under the hands-off law (accuracy of the automatic system, not manual
gates). The section below records the verdict on each of your claims.

## 4. Verdicts on your v3.21 findings

Each claim was verified against the live code by an adversarial agent
fleet (35 agents; 22 of 28 verdicts confirmed some form of your claim)
before anything shipped.

**CONFIRMED AND SHIPPED in v3.23:**
- §13 budget semantics (your C2): the three-way contradiction was real
  and 0/invalid meant *unlimited*. Now: one meaning, fails closed,
  finite-only ceilings, bad values fall to the default out loud.
- §13 the `"deep"` model key (C1): confirmed nonexistent — though the
  sole caller is haiku-only, so it was "right by accident"; classified
  by the actual model now.
- §11 ask_video (C7a): quotes verified (normalised, never fuzzy),
  times snapped to the matched segment, paraphrases localised to the
  real line, inventions dropped with an honest note. ask_library (C7b)
  grounds time in the transcript first — note it already half-did
  this (your "validates only row index" was true only of the
  nonzero-t branch).
- §6 speaker join (C6): describer lines now carry the named voice via
  the existing overlap-only attribution; no "speaker N" arm, by
  measurement (29/30 named nights carry only the auto 'you' map).
- §4 quote validation (C3 part 2): describer stretch/moment quotes are
  exact-checked against their cited lines at parse; failures are
  blanked/trimmed and banked, never silently dropped.
- §5 partially (C4): the *summary* now gets the same guard as the
  title, and words vouched **only** by generated chapter names are
  logged as laundering. See REJECTED below for the part that failed
  measurement.
- §16 docs (C8): README's "fully offline" replaced with the exact
  three network modes; CURRENT-BUILD.md regenerates at every ship;
  the build report counts what `build.bat` actually copies.

**ALREADY FIXED IN 3.22** (see §3): impossible-speed transcript lines,
the short-echo hole, wrong language tags, reader-generation stamps.

**REJECTED BY MEASUREMENT** (your remedy, not your finding):
- Removing chapter names from the "heard" corpus: replayed twice
  independently — it newly flags 101–115 of 357 titles (~90%
  legitimate) to catch ~3 genuine launderings. Kept the corpus;
  laundering is logged instead.
- Making `quote` schema-required: llama-server compiles the schema to
  a grammar, so a required string on mandatory segments *mandates
  invention* for stretches with nothing quotable. Optional +
  parse-validation is the correct shape.
- "Drop the hit and answer 'the recording does not establish that'":
  collides with the recorded philosophy (burned by silent drops);
  the shipped discipline is verify → localise-and-substitute → drop
  *that hit only* with an honest note, answer kept.
- Your causal story for the Big Walk title: the corpus was CLEAN (the
  invented words appear in zero sources) — laundering did not cause
  it. The real hole was the Latin-only candidate regex; Arabic lies
  without capitals. Fixed with a narrow kinship-claim arm (replayed:
  1 flag in 357 titles, zero false).

**REJECTED BY PRODUCT LAW:** your P0 "auditor proposes, user
approves" and every approve-first/inbox/badge remedy (see §1, law 1).
The auditor's mechanics you described (temporal co-occurrence as
agreement; the review voting for its own inputs) were CONFIRMED and
remain open items — the fix direction is lineage-aware voting inside
the automatic system, queued behind its A/B.

**CONFIRMED, QUEUED BEHIND A/B:** §3 describer window downsampling
(confirmed live; first step is a counter measuring how often the
even-sampling fires, plus telling the model in-prompt when lines were
sampled); §8–§10 senses/OCR/eye calibration (largely untouched,
your recommendations stand).

## 5. What the next review should focus on

1. **The evidence/lineage work** — the parts of your §2/§5 that
   survive the hands-off law: does the auditor still count derived
   layers as independent witnesses anywhere? Did the corpus/laundering
   fixes hold? Look for NEW laundering paths.
2. **The A/B-gated queue** (see `Downloads\LORE-QUEUE.md`): mic-span
   union, timed repeat gate, legacy cleanse, arabizi span repair. If
   any shipped since, review their false-positive behaviour against
   real speech first.
3. **Anything the fast pace broke.** v3.09→v3.23 in under a month.
   Your instinct about regression risk is right; the mitigations are
   the scratch-pad test roster (~30 suites, 400+ checks, run on every
   ship) and an adversarial multi-agent review before every ship.
   Fresh eyes on *newly added* code (AFK catch-up, queue attic,
   physics gate, short echo arm) are worth more than re-auditing old
   ground.
4. **The eye and OCR** (your §9/§10) — largely untouched so far;
   your persistence/confidence recommendations there remain open and
   unrebutted.
5. **Concrete bugs over architecture.** The most useful findings are
   file:line defects with a demonstrable victim. Architectural essays
   are read but move slower here.

## 6. Practical notes for your run

- Sidecar field names: stt segments are `{a, b, t, lang[, src, micp]}`
  (`a`/`b` in ms; `t` is the text — not `text`).
- The stt `counters` dict tells you which guard generation produced a
  file; `reader: 3` = current.
- `_ai_sidecar_fresh` is mtime-based by design; generation staleness
  is signalled via the version constants (`_STT_V`, `_HL_V`, `_LVL_V`,
  READER) and surfaces as silver marks in the UI, not as auto-rebuilds.
- The library at `D:\Records` is the owner's real footage: read-only,
  always.
- Never send requests to ports 8906–8912 — they are the app's live
  model servers.

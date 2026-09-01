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

// Run the SHIPPED rank chip out of ui.html - the drop-L block whole, so
// the cycle, the "normal means no row" rule and the AI-suite gate are
// PROVEN rather than pinned as strings. Same lift-and-run idea as
// paneltest.js; nothing here touches the shelf.
const fs = require('fs');
const src = fs.readFileSync('D:/Gate LLC/ui.html', 'utf8');

const a = src.indexOf('/* ---- 3.35 L:');
const b = src.indexOf('function renderContents(cL,cR,spreadIdx){');
if (a < 0 || b < 0 || b < a) throw new Error('drop L block not found in ui.html');
const block = src.slice(a, b);

let ok = 0, bad = 0;
const t = (n, v) => { v ? ok++ : bad++; console.log((v ? '  OK   ' : '  FAIL ') + n); };

// the page's own furniture, reduced to what the block actually leans on
let saved = null;
const whispers = [];
const S = { settings: { settings: { ai_highlights: true, game_rank: {} } } };
const el = (tag, cls, html) => ({
  tag: tag, className: cls || '', textContent: html || '', title: '',
  _h: [], addEventListener(n, f) { this._h.push(f); },
  click(ev) { this._h.forEach(f => f(ev)); } });
const esc = x => String(x);
const whisper = m => whispers.push(m);
const queueSave = p => { saved = p; Object.assign(S.settings.settings, p); };

const NS = new Function(
  'S', 'el', 'esc', 'whisper', 'queueSave',
  block + '\nreturn {rankChip, rankOf, rankWord, aiSuiteOn, RANKS, RANKW};'
)(S, el, esc, whisper, queueSave);

const g = { key: 'alpha', display: 'Alpha' };
const ev = { stopPropagation() { ev.stopped = true; } };

// ---- the cycle -------------------------------------------------------
const chip = NS.rankChip(g);
const seen = [chip.textContent];
for (let i = 0; i < 4; i++) { chip.click(ev); seen.push(chip.textContent); }
t('the chip starts "in its turn" and cycles all four back to the start',
  seen.join('|') === 'in its turn|when the rest are done|never on its own|'
                   + 'ahead of the rest|in its turn');
t('a press does not open the chapter underneath it', ev.stopped === true);
t('back at "normal" the dict is empty again - the two-hundred clamp is '
  + 'never filled with defaults',
  JSON.stringify(S.settings.settings.game_rank) === '{}');
t('every press went through the existing settings road',
  saved !== null && 'game_rank' in saved);
t('the class says the state, so the type can', chip.className === 'grank r-normal');
t('and the whisper names the game and the state',
  whispers.length === 4 && whispers[0] === 'Alpha \u2014 when the rest are done');

// ---- what it stores --------------------------------------------------
chip.click(ev); chip.click(ev);                      // later, then never
t('a held-back game is stored by its chapter key',
  S.settings.settings.game_rank.alpha === 'never'
  && NS.rankOf('alpha') === 'never');
t('a game nobody ranked is "normal" without a row',
  NS.rankOf('beta') === 'normal'
  && !('beta' in S.settings.settings.game_rank));
S.settings.settings.game_rank.alpha = 'sideways';
t('a word the settings clamp would have refused still reads "normal"',
  NS.rankOf('alpha') === 'normal');

// ---- the tip ---------------------------------------------------------
S.settings.settings.game_rank = {};
const chip2 = NS.rankChip(g);
const tips = [chip2.title];
for (let i = 0; i < 3; i++) { chip2.click(ev); tips.push(chip2.title); }
t('every one of the four tips promises the direct ask',
  tips.length === 4 && tips.every(x => /asking for a night by name always works/.test(x)));
t('...and each explains its own state',
  /in its turn/.test(tips[0]) && /only when the rest are done/.test(tips[1])
  && /never picks this game on its own/.test(tips[2])
  && /before the rest/.test(tips[3]));

// ---- the quiet word on the Working page ------------------------------
t('rankWord is silent for the default and for nothing at all',
  NS.rankWord('normal') === '' && NS.rankWord(undefined) === ''
  && NS.rankWord('') === '' && NS.rankWord('sideways') === '');
t('...and speaks for the three states worth seeing',
  NS.rankWord('first') === 'ahead of the rest'
  && NS.rankWord('later') === 'when the rest are done'
  && NS.rankWord('never') === 'never on its own');

// ---- the gate --------------------------------------------------------
const st = S.settings.settings;
st.ai_highlights = st.ai_transcribe = st.insights_auto = false;
t('no AI suite, no chip - there is no queue to order',
  NS.aiSuiteOn() === false && NS.rankChip(g) === null);
st.ai_transcribe = true;
t('one lane on is enough', NS.aiSuiteOn() === true && NS.rankChip(g) !== null);
S.settings = null;
t('a page whose settings have not landed yet does not throw',
  NS.aiSuiteOn() === false && NS.rankChip(g) === null);

console.log('\n' + ok + ' ok, ' + bad + ' failed');
process.exit(bad ? 1 : 0);

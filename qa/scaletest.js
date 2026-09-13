// 3.37 drop O, item O1 - THE SCALE SAYS WHAT IT MEANS, on the shelf's
// own paint. His word, 13 Sep: "right now its silver describe and when
// i hover it tells me its silver because its not audited??? that makes
// no sense". Lifted out of ui.html (the lift-and-run idea of
// uiloops336.js), run on fixtures, and shown against the PARITY_BASE
// twin saying the old thing. Nothing here touches the shelf.
//
//   markPaint     level-1 ins tip never says "audit" unless the why does,
//                 and its DO names the lightning menu's own describe item;
//                 the level-2 ins tip says "current version"
//   quick-look    the level-1 text is the backend why's head (before its
//                 first " - "), never "described, audit owed"
//   makeMock      the silver pen carries the new why
const fs = require('fs');
const cp = require('child_process');
const ROOT = 'D:/Gate LLC';
const src = fs.readFileSync(ROOT + '/ui.html', 'utf8');

// THE PARITY BASE IS A COMMIT, NOT HEAD. 01f0a49 is 3.36, the tree his
// 13 Sep word was measured on.
const PARITY_BASE = '01f0a49';
const base = cp.execSync('git show ' + PARITY_BASE + ':ui.html',
  { cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
if (base.indexOf('function markPaint(') < 0) throw new Error('git show of the parity base failed');

let ok = 0, bad = 0;
const t = (n, v, extra) => { v ? ok++ : bad++;
  console.log((v ? '  OK   ' : '  FAIL ') + n + (extra ? '   [' + extra + ']' : '')); };

function sliceBlock(text, start, from) {
  const i = text.indexOf(start, from || 0);
  if (i < 0) throw new Error('not found: ' + start);
  let d = 0, started = false;
  for (let k = i; k < text.length; k++) {
    if (text[k] === '{') { d++; started = true; }
    else if (text[k] === '}') { d--; if (started && d === 0) return text.slice(i, k + 1); }
  }
  throw new Error('unbalanced: ' + start);
}
function liftConst(text, name) {
  const i = text.indexOf('const ' + name + '=');
  if (i < 0) throw new Error('not found: const ' + name);
  const j = text.indexOf('};', i);
  return text.slice(i, j + 2);
}
function markRig(text) {
  return new Function(sliceBlock(text, 'function markPaint(') + '\n'
    + liftConst(text, 'AV_HAS') + '\n' + liftConst(text, 'AV_NOT')
    + '\nreturn {markPaint, AV_NOT, AV_HAS};')();
}
// the quick-look card's per-mark text: the .map(k=>{...}) callback
function qlRig(text) {
  const a = text.indexOf("card.append(el('div','qlmarks'");
  if (a < 0) throw new Error('quick-look marks not found');
  const m = text.indexOf('.map(k=>', a);
  const blk = sliceBlock(text, '{', m);
  const AV = new Function(liftConst(text, 'AV_HAS') + '\n' + liftConst(text, 'AV_NOT')
    + '\nreturn {AV_HAS, AV_NOT};')();
  const fn = new Function('f', 'k', 'AV_HAS', 'AV_NOT', blk.slice(1, -1));
  return (f, k) => fn(f, k, AV.AV_HAS, AV.AV_NOT);
}
const fakeI = () => { const s = new Set(); return { title: '', cls: s,
  classList: { toggle: (c, on) => { on ? s.add(c) : s.delete(c); }, contains: c => s.has(c) } }; };

const WHY_OLD = 'described by an older version (v2; v3 is installed) - it will be told again on its own';
const WHY_ASK = 'described by an older version (v2; v3 is installed) - ask for it by name to bring it up to date';
const WHY_CUT = 'the audit corrected lines inside it - those minutes are being told again';
const WHY_FRESH = 'a fresh telling is owed';
const WHY_REDO = 'it is being described again - asked by name';
const AUD_OLD = 'audited by v6; auditor v7 is installed - it will be audited again';
const AUD_PRE = 'it read an older description - it will be audited again';

// the lightning menu's own describe item, read off the menu itself
const menu = src.slice(src.indexOf("[['sound','Sound & gold moments',null]"), src.indexOf("['all','Everything, from scratch',true]]"));
t('the lightning menu names its describe item "Describe it" (one recording)',
  menu.indexOf("['think','Describe '+(many?'them':'it'),null]") > 0);

console.log('--- markPaint: the silver pen says why, and how to ask ---');
const MP = markRig(src);
const paint = (row, k) => { const b = fakeI(); MP.markPaint(b, row, k || 'ins'); return b; };
for (const why of [WHY_OLD, WHY_ASK, WHY_FRESH, WHY_REDO]) {
  const b = paint({ ins: true, ins_lvl: 1, ins_why: why });
  t('level-1 ins tip carries the why and never the word "audit": ' + why.slice(0, 34) + '...',
    b.cls.has('part') && b.title.indexOf(why) >= 0 && !/audit/i.test(b.title), b.title);
  t('...and its DO names the menu\'s own item (Describe it)',
    /\u26a1 \u2192 Describe it\)/.test(b.title) && !/run the audit again/.test(b.title), b.title);
}
for (const why of [WHY_OLD, WHY_ASK]) {
  const b = paint({ ins: true, ins_lvl: 1, ins_why: why });
  t('a why that opens "described by" is not headed "described \u2014 but" (the word never doubles): ' + why.slice(0, 34) + '...',
    b.title.indexOf(why) === 0 && !/described \u2014 but described/.test(b.title), b.title);
}
for (const why of [WHY_FRESH, WHY_REDO]) {
  const b = paint({ ins: true, ins_lvl: 1, ins_why: why });
  t('...while a why that does not open with the word keeps the HEAD: ' + why.slice(0, 34) + '...',
    b.title.indexOf('described \u2014 but ' + why) === 0, b.title);
}
const bc = paint({ ins: true, ins_lvl: 1, ins_why: WHY_CUT });
t('the corrected-lines why is the one level-1 ins tip allowed to say "audit" (the why says it)',
  bc.title.indexOf(WHY_CUT) >= 0 && !/run the audit again/.test(bc.title), bc.title);
const bg = paint({ ins: true, ins_lvl: 2, ins_why: '' });
t('level-2 ins tip: "described by the current version"',
  bg.cls.has('on') && bg.title === 'described by the current version', bg.title);
const ba = paint({ aud: false, aud_lvl: 1, aud_v: 6, aud_why: AUD_OLD }, 'aud');
t('level-1 aud tip carries the audit\'s own why and its DO',
  ba.title.indexOf(AUD_OLD) >= 0 && /run the audit again/.test(ba.title), ba.title);
const bag = paint({ aud: true, aud_lvl: 2, aud_v: 7, aud_why: '' }, 'aud');
t('level-2 aud tip stays "audited by vN against this description"',
  bag.title === 'audited by v7 against this description', bag.title);
const bd = paint({ ins: false, ins_lvl: 0, ins_why: '' });
t('a dark pen still says "not described yet"', bd.title === MP.AV_NOT.ins);

console.log('--- the quick-look card: the why\'s head ---');
const QL = qlRig(src);
t('level-1 ins text is the why cut at its first " - "',
  QL({ ins_lvl: 1, ins_why: WHY_OLD }, 'ins') === 'described by an older version (v2; v3 is installed)',
  QL({ ins_lvl: 1, ins_why: WHY_OLD }, 'ins'));
t('...the corrected-lines why keeps its head', QL({ ins_lvl: 1, ins_why: WHY_CUT }, 'ins') === 'the audit corrected lines inside it');
t('...a why with no " - " stands whole', QL({ ins_lvl: 1, ins_why: WHY_FRESH }, 'ins') === WHY_FRESH);
t('...the by-name redo keeps its head', QL({ ins_lvl: 1, ins_why: WHY_REDO }, 'ins') === 'it is being described again');
t('level-1 aud text is the audit why\'s head',
  QL({ aud_lvl: 1, aud_why: AUD_OLD }, 'aud') === 'audited by v6; auditor v7 is installed'
  && QL({ aud_lvl: 1, aud_why: AUD_PRE }, 'aud') === 'it read an older description');
t('with no why at all: "described, older" / "audited, older" - never "audit owed"',
  QL({ ins_lvl: 1 }, 'ins') === 'described, older' && QL({ aud_lvl: 1 }, 'aud') === 'audited, older');
t('the other marks: their why\'s head, or the old fallback',
  QL({ stt_lvl: 1, stt_why: 'read by an older reader (gen 6 of 7)' }, 'stt') === 'read by an older reader (gen 6 of 7)'
  && QL({ hl_lvl: 1 }, 'hl') === 'sound pass, older');
t('level 2 and level 0 are untouched',
  QL({ ins_lvl: 2 }, 'ins') === 'has an AI review' && QL({ ins_lvl: 0 }, 'ins') === 'not described yet'
  && QL({ ins_lvl: 0, ins_why: 'gave up after three tries' }, 'ins') === 'gave up after three tries');
t('"described, audit owed" is gone from ui.html', src.indexOf('described, audit owed') < 0);

console.log('--- the mock ---');
t('makeMock\'s silver pen carries the new why',
  src.indexOf("ins_why:'described by an older version (v2; v3 is installed) '") > 0
  && src.indexOf('no audit has read this description yet') < 0);
t('the Everything list\'s chip comment still holds ("not audited" cannot hide a silver scale)',
  src.indexOf('"not audited" cannot hide a silver') > 0);

console.log('--- the witness, ' + PARITY_BASE + ' ---');
const MB = markRig(base);
const ob = fakeI(); MB.markPaint(ob, { ins: true, ins_lvl: 1, ins_why: 'no audit has read this description yet' }, 'ins');
t('before: the silver pen sent him to the audit ("run the audit again")',
  /run the audit again/.test(ob.title) && /Audit only/.test(ob.title), ob.title);
const od = fakeI(); MB.markPaint(od, { ins: true, ins_lvl: 1, ins_why: WHY_OLD }, 'ins');
t('before: the HEAD doubled the word over a "described by" why ("described \u2014 but described by")',
  /described \u2014 but described by/.test(od.title), od.title);
const og = fakeI(); MB.markPaint(og, { ins: true, ins_lvl: 2 }, 'ins');
t('before: the gold pen said "the audit has read this version"', /the audit has read this version/.test(og.title), og.title);
const QB = qlRig(base);
t('before: the quick-look said "described, audit owed"', QB({ ins_lvl: 1, ins_why: WHY_OLD }, 'ins') === 'described, audit owed');

console.log('\n' + ok + ' ok, ' + bad + ' failed');
process.exit(bad ? 1 : 0);

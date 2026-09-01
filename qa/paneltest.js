// Run the SHIPPED thrModel + thrSig out of ui.html against a realistic
// audit payload, so the panel's contract is proven rather than assumed.
const fs = require('fs');
const src = fs.readFileSync('D:/Gate LLC/ui.html', 'utf8');

function lift(name) {
  const i = src.indexOf('function ' + name + '(');
  if (i < 0) throw new Error('not found: ' + name);
  let d = 0, started = false;
  for (let k = i; k < src.length; k++) {
    if (src[k] === '{') { d++; started = true; }
    else if (src[k] === '}') { d--; if (started && d === 0) return src.slice(i, k + 1); }
  }
  throw new Error('unbalanced: ' + name);
}

const code = ['thrArr', 'thrStr', 'thrNum', 'thrWhat', 'thrAgrees',
              'thrModel', 'thrSig'].map(lift).join('\n');
const THR = new Function(
  'let _thrSeq=0;\n' +
  'const THR_LEAD=2, THR_SLACK=1;\n' +
  code + '\n' +
  'return {thrModel:thrModel, thrSig:thrSig};')();

// a payload shaped exactly like _aud_public's output after 2.93
const doc = {
  v: 3, complete: true,
  thread: [
    { t: 612.3, agrees: ['words', 'eye', 'review', 'laugh'],
      say: { words: '"Why would the door open by itself?"',
             eye: 'stone cellar with a low arch - two cloaked statues',
             review: 'A stray question about the map goes unanswered.',
             laugh: 'somebody laughs' } },
    { t: 3377.5, agrees: ['words'], say: { words: '"I got knocked clean off."' } },
  ],
  corrected: [
    { t: 941.2, was: 'Zami hehe.', now: 'قال لي Ho Ho',
      odd: ['Zami'], put_back: false },
    { t: 77.0, was: '', now: 'Vontrelle.', odd: [], put_back: true },
  ],
  names_fixed: [{ from: 'Marid', to: 'مارد',
                  why: 'said, spelt another way' }],
  names: [{ name: 'ZXQs', where: 'summary', verdict: 'unsaid',
            how: 'nobody in this recording says this', said: '' },
          { name: 'Marid', where: 'title', verdict: 'spelt',
            how: 'said, spelt another way', said: 'مارد' }],
  garble: [{ t: 2951.7, text: 'Ostam vekkuri shonaas wat? Yeah.',
             odd: ['vekkuri', 'shonaas'] }],
  fixes: [{ t: 941.2, heard: 'قال لي Ho Ho', applied: true, undone: false }],
  dropped: [{ t: 140.0, what: 'music', why: 'nothing else at that second' }],
  merged: [{ kept: 'shopkeep Sam', folded: ['sam the shopkeep'] }],
  warnings: ['the senses tagged 1 music event on a recording with no music'],
};

let ok = 0, bad = 0;
const check = (n, c) => { c ? ok++ : bad++; console.log((c ? '  OK   ' : '  FAIL ') + n); };

const m = THR.thrModel(doc);
check('evidence rows carry per-layer quotes',
  m.beats.length === 2 && m.beats[0].say.eye.indexOf('cloaked') >= 0);
check('a 4-layer row keeps all four', m.beats[0].ag.length === 4);
// rows arrive in time order, so find them by clock, not by index
const at = (t) => m.fixed.find(r => Math.abs(r.t - t) < 0.05);
check('rows are in time order',
  m.fixed.length === 2 && m.fixed[0].t < m.fixed[1].t);
check('corrections carry before, after and the odd words',
  at(941.2) && at(941.2).was === 'Zami hehe.' &&
  at(941.2).now.indexOf('قال') === 0 && at(941.2).odd[0] === 'Zami');
check('a put-back line is marked as such',
  at(77.0) && at(77.0).put_back === true && at(941.2).put_back === false);
check('respelt names carry their reason',
  m.respelt.length === 1 && m.respelt[0].to === 'مارد' &&
  m.respelt[0].why === 'said, spelt another way');
check('a corrected line is not ALSO listed as still-doubtful',
  m.said.every(g => Math.abs(g.t - 941.2) > 2));
check('a genuinely unread line survives in said',
  m.said.length === 1 && m.said[0].odd[0] === 'vekkuri');
check('names keeps both verdicts for the questioned section',
  m.names.length === 2);
check('drops and folds still travel',
  m.drop.length === 1 && m.fold.length === 1);
check('any is true when there is work to show', m.any === true);

// the signature must move when ANY of the new fields move
const sig0 = THR.thrSig(m);
const d2 = JSON.parse(JSON.stringify(doc));
d2.corrected[0].put_back = true;
check('signature moves when a correction is put back',
  THR.thrSig(THR.thrModel(d2)) !== sig0);
const d3 = JSON.parse(JSON.stringify(doc));
d3.names_fixed = [];
check('signature moves when a respelling disappears',
  THR.thrSig(THR.thrModel(d3)) !== sig0);

// an OLD audit (prose, no quotes, no corrections) must still render
const old = { v: 1, complete: true,
  thread: [{ t: 10, what: 'Pixel was pulled into the pit.',
             agrees: ['words', 'eye'] }],
  dropped: [], merged: [], warnings: [] };
const mo = THR.thrModel(old);
check('an audit written before 2.92 still shows its rows',
  mo.beats.length === 1 && mo.beats[0].what.indexOf('Pixel') === 0 &&
  Object.keys(mo.beats[0].say).length === 0 && mo.any === true);

// junk must not throw
[null, undefined, {}, { thread: 7, corrected: 'x', names_fixed: {} },
 { corrected: [null, 3, { t: 'x' }] }].forEach((j, i) => {
  try { const r = THR.thrModel(j); check('junk payload ' + i + ' renders empty',
    Array.isArray(r.beats) && Array.isArray(r.fixed)); }
  catch (e) { check('junk payload ' + i + ' renders empty', false); }
});

console.log('\n' + ok + ' ok, ' + bad + ' failed');
process.exit(bad ? 1 : 0);

// The 3.36 audit's three ui.html fixes, PROVEN on the shipped code rather
// than pinned as strings - the same lift-and-run idea as paneltest.js /
// ranktest.js. Each section lifts the real function out of ui.html, runs
// it on a fixture, and shows the same fixture on the PARITY_BASE twin
// doing what the audit found. Nothing here touches the shelf.
//
//   UI-W1  flagsWatch re-asks have_flags for the paths that landed, not
//          the whole shelf, when the status carries a done_paths ring
//          (and, without one, treats the one-landing double bump as one)
//   UI-G2  the Working page's whole-shelf tally has its own unclamped
//          node under the job sentence - no figure is silently cut
//   UI-A1  a gave-up night (level 0 WITH a reason) paints a struck pen
//          whose tip says so; the header and the tally line count it
const fs = require('fs');
const cp = require('child_process');
const ROOT = 'D:/Gate LLC';
const src = fs.readFileSync(ROOT + '/ui.html', 'utf8');

// THE PARITY BASE IS A COMMIT, NOT HEAD. e3212c6 is 3.36 drop N, the tree
// the audit measured; HEAD would make every "before" witness vanish the
// moment this drop lands.
const PARITY_BASE = 'e3212c6';
const base = cp.execSync('git show ' + PARITY_BASE + ':ui.html',
  { cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
if (base.indexOf('function flagsWatch(') < 0) throw new Error('git show of the parity base failed');

let ok = 0, bad = 0;
const t = (n, v, extra) => { v ? ok++ : bad++;
  console.log((v ? '  OK   ' : '  FAIL ') + n + (extra ? '   [' + extra + ']' : '')); };

// a balanced-brace slice from the first '{' at or after `from`
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

// ===================================================================
// UI-W1 - flagsWatch and the have_flags storm
// ===================================================================
console.log('--- UI-W1: flagsWatch asks about the paths that landed ---');
const NPATHS = 1366;
function flagsRig(text) {
  const a = text.indexOf('let _doneRev=null;');
  const b = text.indexOf('setInterval(flagsWatch,4000);');
  if (a < 0 || b < 0 || b < a) throw new Error('flagsWatch block not found');
  const fw = text.slice(a, b);
  if (fw.split('async function flagsWatch(').length !== 2) throw new Error('flagsWatch lifted twice');
  const rig = new Function('NPATHS', `
    const document={hidden:false,querySelectorAll:()=>[],addEventListener(){}};
    let _visWake=[]; const _visKick=()=>{}; function _parked(){return false;}
    const _have=new Map();
    const paths=[]; for(let i=0;i<NPATHS;i++){paths.push('D:/R/n'+i+'.mp4'); _have.set(paths[i],{hl:true,ins_lvl:0});}
    let V={cur:{path:paths[7]}}; const AV={sort:'',want:{}}; const avNode=()=>null;
    const avPaint=()=>{}; const avFlagsRefresh=()=>{}; const thrForget=()=>{};
    let loads=0; const loadThread=()=>{loads++;}; const loadSaid=()=>{}; const _viewerReq=0;
    const script=[]; let rpc=0, asked=[];
    const api={
      ai_status:async()=>script.length?script.shift():null,
      have_flags:async ps=>{rpc++; asked=asked.concat(ps); const o={};
        ps.forEach(p=>o[p]={hl:true,ins_lvl:(p===paths[7]&&flip)?2:0}); return o;}
    };
    let flip=false;
    ${fw}
    return {
      paths, _have,
      setFlip:v=>{flip=v;},
      beat:async st=>{ rpc=0; asked=[]; const l0=loads; if(st)script.push(st); await flagsWatch();
        return {rpc, asked:asked.length, set:[...new Set(asked)].sort(), have:_have.size, loads:loads-l0}; }
    };`)(NPATHS);
  return rig;
}

(async () => {
  const R = flagsRig(src);
  const P = R.paths;
  let r;
  r = await R.beat({ done_rev: 101, done_path: P[3] });
  t('W1 first tick adopts done_rev and asks nothing', r.rpc === 0);
  r = await R.beat({ done_rev: 101, done_path: P[3] });
  t('W1 (d) the same done_rev twice is a no-op', r.rpc === 0);
  // (a) one audit landing: _put bumps, the finally bumps - same path twice
  r = await R.beat({ done_rev: 103, done_path: P[3],
    done_paths: [{ rev: 102, path: P[3] }, { rev: 103, path: P[3] }] });
  t('W1 (a) one landing (done_rev +2, ring names one path twice) asks exactly that path, one RPC',
    r.rpc === 1 && r.asked === 1 && r.set.length === 1 && r.set[0] === P[3],
    'rpc=' + r.rpc + ' asked=' + r.asked);
  t('W1 (a) the map is whole afterwards (nothing greyed out)', r.have === NPATHS);
  // (b) two jobs in one tick: two paths in the ring, no blanket
  r = await R.beat({ done_rev: 105, done_path: P[9],
    done_paths: [{ rev: 102, path: P[3] }, { rev: 103, path: P[3] },
                 { rev: 104, path: P[5] }, { rev: 105, path: P[9] }] });
  t('W1 (b) two jobs in one tick ask exactly the two paths that landed',
    r.rpc === 1 && r.set.length === 2 && r.set.includes(P[5]) && r.set.includes(P[9])
    && r.asked === 2, 'asked=' + r.asked);
  // (c) a gap the ring cannot cover: its oldest rev is beyond the rev we last saw
  r = await R.beat({ done_rev: 130, done_path: P[1],
    done_paths: [{ rev: 125, path: P[1] }, { rev: 130, path: P[2] }] });
  t('W1 (c) a gap the ring cannot cover keeps the blanket (safety net)',
    r.asked === NPATHS && r.rpc === Math.ceil(NPATHS / 300), 'asked=' + r.asked);
  t('W1 (c) the map is refilled after the blanket', r.have === NPATHS);
  // (e) a ring that does not reach the rev we are told - some bump site did not ring
  r = await R.beat({ done_rev: 134, done_path: P[1],
    done_paths: [{ rev: 130, path: P[2] }, { rev: 131, path: P[4] }] });
  t('W1 (e) a ring that stops short of done_rev blankets too', r.asked === NPATHS);
  // the viewer: a direct hit on the open recording reloads it, a blanket only when its flags moved
  R.setFlip(false);
  r = await R.beat({ done_rev: 136, done_path: P[7],
    done_paths: [{ rev: 135, path: P[7] }, { rev: 136, path: P[7] }] });
  t('W1 the open recording reloads on its own landing (direct hit)', r.loads === 1 && r.asked === 1);
  r = await R.beat({ done_rev: 138, done_path: P[8],
    done_paths: [{ rev: 137, path: P[8] }, { rev: 138, path: P[8] }] });
  t('W1 another night landing does not yank the open recording', r.loads === 0 && r.asked === 1);
  r = await R.beat({ done_rev: 160, done_path: P[8],
    done_paths: [{ rev: 159, path: P[8] }, { rev: 160, path: P[8] }] });
  t('W1 a blanket with the open recording unchanged does not reload it', r.asked === NPATHS && r.loads === 0);
  R.setFlip(true);
  r = await R.beat({ done_rev: 180, done_path: P[8],
    done_paths: [{ rev: 179, path: P[8] }, { rev: 180, path: P[8] }] });
  t('W1 a blanket that moved the open recording\'s flags reloads it', r.asked === NPATHS && r.loads === 1);
  R.setFlip(false);
  // without a ring (an older backend): +2 with a named path is one landing
  r = await R.beat({ done_rev: 182, done_path: P[11] });
  t('W1 (no ring) done_rev +2 with a named path asks that path only',
    r.rpc === 1 && r.asked === 1 && r.set[0] === P[11], 'asked=' + r.asked);
  r = await R.beat({ done_rev: 185, done_path: P[12] });
  t('W1 (no ring) a bigger jump still blankets', r.asked === NPATHS);
  r = await R.beat({ done_rev: 186, done_path: null });
  t('W1 (no ring) a bump that names nothing asks nothing', r.rpc === 0);
  r = await R.beat({ done_rev: 187, done_paths: [], done_path: null });
  t('W1 an empty ring on a bump blankets rather than going quiet', r.asked === NPATHS);

  // the before: the same one-landing shape on the parity base
  const B = flagsRig(base);
  await B.beat({ done_rev: 101, done_path: B.paths[3] });
  const rb = await B.beat({ done_rev: 103, done_path: B.paths[3],
    done_paths: [{ rev: 102, path: B.paths[3] }, { rev: 103, path: B.paths[3] }] });
  t('W1 [before, ' + PARITY_BASE + '] the same landing re-asked the whole shelf',
    rb.asked === NPATHS, 'asked=' + rb.asked);
  t('W1 the blanket is no longer keyed on the count alone',
    src.indexOf("const stale=jumped>1?[..._have.keys()]:[p];") < 0
    && src.indexOf('a.done_paths') > 0);

  // =================================================================
  // UI-G2 - the tally line has its own unclamped node
  // =================================================================
  console.log('--- UI-G2: the whole-shelf tally is never cut ---');
  const cssTally = (() => { const i = src.indexOf('.lab .ltally{'); return i < 0 ? '' : src.slice(i, src.indexOf('}', i) + 1); })();
  const cssName = (() => { const i = src.indexOf('.lab .lname{'); return src.slice(i, src.indexOf('}', i) + 1); })();
  t('G2 a .lab .ltally rule exists', cssTally.length > 0);
  t('G2 the tally node has no line clamp and no hidden overflow',
    cssTally.indexOf('line-clamp') < 0 && cssTally.indexOf('overflow') < 0
    && cssTally.indexOf('white-space:pre-line') > 0);
  t('G2 the job sentence keeps its two-line clamp', cssName.indexOf('-webkit-line-clamp:2') > 0);
  t('G2 the idle branch always hands the tally to line two',
    src.indexOf("(advice||'')+'\\n'+tally,null,null,!!busyWith);") > 0
    && src.indexOf("(advice?advice+'\\n':'')+tally") < 0);

  // the DOM, reduced to what mk()/set() lean on
  const mkEl = (tag, cls, html) => ({ tag, className: cls || '', textContent: html || '',
    style: {}, kids: [], _cls: new Set(),
    classList: { toggle(c, on) { on ? this._s.add(c) : this._s.delete(c); }, add(c) { this._s.add(c); },
                 contains(c) { return this._s.has(c); }, _s: new Set() },
    append(...k) { this.kids.push(...k); } });
  function plateRig(text) {
    const mk = sliceBlock(text, 'const mk=()=>{');
    const set = sliceBlock(text, 'const set=(o,live,what,name,pct,onStop,queued,stopLabel)=>{');
    return new Function('el', mk + ';\n' + set + ';\nreturn {mk, set};')(mkEl);
  }
  const PR = plateRig(src);
  const o = PR.mk();
  const mid = o.r.kids[1];
  t('G2 mk() builds lwhat, lname, ltally, lbar in that order under lmid',
    mid.className === 'lmid' && mid.kids.map(k => k.className).join(',') === 'lwhat,lname,ltally,lbar');
  t('G2 mk() returns the tally node', o.tally && o.tally.className === 'ltally');
  const TALLY = 'the whole shelf: 1,357 of 1,366 done  \u00b7  9 left  \u00b7  214 never on their own  \u00b7  about 3h 10m for all of them';
  PR.set(o, true, 'AI review', 'night_20260903  \u00b7  3m in  \u00b7  1h 2m long\n' + TALLY, 42, null);
  t('G2 set() keeps the job sentence alone on the clamped line',
    o.name.textContent === 'night_20260903  \u00b7  3m in  \u00b7  1h 2m long' && o.name.textContent.indexOf('\n') < 0);
  t('G2 set() puts the whole tally in the unclamped node, shown',
    o.tally.textContent === TALLY && o.tally.style.display === '');
  t('G2 the bar clamp is still keyed on the first line',
    (PR.set(o, true, 'AI review', 'night_20260903  \u00b7  4m in\n' + TALLY, 30, null),
     o.fill.style.width === '42%'));
  PR.set(o, false, 'AI review \u2014 waiting for you to step away', '\n' + TALLY, null, null);
  t('G2 an idle row with no advice shows the tally and hides the empty sentence',
    o.tally.textContent === TALLY && o.tally.style.display === '' && o.name.style.display === 'none');
  PR.set(o, false, 'AI review \u2014 paused', 'everything is paused for your game', null, null);
  t('G2 a one-line status hides the tally node', o.tally.style.display === 'none' && o.name.textContent === 'everything is paused for your game');
  const staging = '1.2 GB can go \u2014 those recordings are already finished\n0.4 GB exists NOWHERE ELSE';
  PR.set(o, false, 'staging', staging, null, null);
  t('G2 a multi-line status keeps every line visible (line two in the unclamped node)',
    o.name.textContent === staging.split('\n')[0] && o.tally.textContent === staging.split('\n')[1]);
  // the before: on the parity base the tally rode the clamped node
  const PB = plateRig(base);
  const ob = PB.mk();
  PB.set(ob, true, 'AI review', 'night\n' + TALLY, 42, null);
  t('G2 [before, ' + PARITY_BASE + '] the tally rode the clamped .lname',
    ob.name.textContent.indexOf('\n' + TALLY) > 0 && !ob.tally);

  // =================================================================
  // UI-A1 - a gave-up night renders as given up
  // =================================================================
  console.log('--- UI-A1: given up is not "not described yet" ---');
  function markRig(text) {
    return new Function(sliceBlock(text, 'function markPaint(') + '\n'
      + liftConst(text, 'AV_HAS') + '\n' + liftConst(text, 'AV_NOT')
      + '\nreturn {markPaint, AV_NOT, AV_HAS};')();
  }
  const fakeI = () => { const s = new Set(); return { title: '', cls: s,
    classList: { toggle: (c, on) => { on ? s.add(c) : s.delete(c); }, contains: c => s.has(c) } }; };
  const GAVE = "gave up after three tries - Ask again on the Working page's Given up on shelf";
  const rows = {
    never: { ins: false, ins_lvl: 0, ins_why: '' },
    gaveup: { ins: false, ins_lvl: 0, ins_why: GAVE },
    silver: { ins: true, ins_lvl: 1, ins_why: 'no audit has read this description yet' },
    gold: { ins: true, ins_lvl: 2, ins_why: '' },
  };
  const MP = markRig(src);
  const paint = (row, k) => { const b = fakeI(); MP.markPaint(b, row, k || 'ins'); return b; };
  const g = paint(rows.gaveup), n = paint(rows.never), s = paint(rows.silver), d = paint(rows.gold);
  t('A1 a never-tried night still says "not described yet" with a dark pen',
    n.title === MP.AV_NOT.ins && !n.cls.has('gone') && !n.cls.has('on') && !n.cls.has('part'));
  t('A1 a gave-up night does not say "not described yet"', g.title !== MP.AV_NOT.ins, g.title);
  t('A1 its tip says it gave up and where to ask again', /gave up/.test(g.title) && /Ask again/.test(g.title));
  t('A1 its tip does not send him to an audit that cannot run', !/run the audit again/.test(g.title));
  t('A1 the pen wears the struck look (class gone), not gold or silver',
    g.cls.has('gone') && !g.cls.has('on') && !g.cls.has('part'));
  t('A1 silver and gold are untouched', s.cls.has('part') && !s.cls.has('gone') && d.cls.has('on') && !d.cls.has('gone'));
  const b2 = fakeI(); MP.markPaint(b2, rows.gaveup, 'ins'); MP.markPaint(b2, rows.gold, 'ins');
  t('A1 a repaint from given-up to told takes the struck look off', !b2.cls.has('gone') && b2.cls.has('on'));
  const hlGone = paint({ hl_lvl: 0, hl_why: 'gave up after three tries' }, 'hl');
  t('A1 the other layers honour a level-0 reason the same way', hlGone.cls.has('gone') && /gave up/.test(hlGone.title));
  t('A1 the struck pen has a style of its own', src.indexOf('.everylist .amarks i.gone{') > 0);
  // the before
  const MB = markRig(base);
  const gb = fakeI(); MB.markPaint(gb, rows.gaveup, 'ins');
  t('A1 [before, ' + PARITY_BASE + '] the gave-up pen said "not described yet"',
    gb.title === MB.AV_NOT.ins && !gb.cls.has('gone'));

  // the Everything header counts gave-ups apart from "not described"
  const statRig = new Function('_have', 'AV', 'fmtSize', 'avNode',
    sliceBlock(src, 'function avStatLine(') + '\nreturn avStatLine;');
  const have = new Map();
  const list = [];
  Object.keys(rows).forEach((k, i) => { const p = 'D:/R/' + k + '.mp4'; list.push({ path: p, size: 10 });
    have.set(p, Object.assign({ stt_lvl: 2, hl_lvl: 2 }, rows[k])); });
  let statText = '';
  statRig(have, { rows: list }, b => b + ' B', () => ({ set textContent(v) { statText = v; } }))(list);
  t('A1 the Everything header says "1 given up" beside "1 not described"',
    /\b1 given up\b/.test(statText) && /\b1 not described\b/.test(statText), statText);

  // the quick-look card's word for a level-0 mark
  const qi = src.indexOf("card.append(el('div','qlmarks',esc(['hl','stt','ins','aud']");
  t('A1 the quick-look card marks are where they were', qi > 0);
  const qmap = sliceBlock(src, '.map(k=>{', qi);
  const qfn = new Function('f', 'AV_HAS', 'AV_NOT',
    "return ['hl','stt','ins','aud']" + qmap + ');')(
    Object.assign({ hl_lvl: 2, stt_lvl: 2, aud_lvl: 0 }, rows.gaveup), MP.AV_HAS, MP.AV_NOT);
  t('A1 the quick-look card says why instead of "not described yet"',
    qfn[2] === GAVE && qfn[3] === MP.AV_NOT.aud, qfn[2]);

  // the Working page tally line carries the given-up count
  const ti = src.indexOf("const tally=k?('the whole shelf: '+[");
  const tj = src.indexOf("].filter(Boolean).join('  \\u00b7  ')):'';", ti);
  t('A1 the tally line is where it was', ti > 0 && tj > ti);
  const texpr = src.slice(ti + 'const tally='.length, tj + "].filter(Boolean).join('  \\u00b7  '))".length + 3);
  const tallyOf = (k, kind) => new Function('k', 'kind', 'num', 'dur', 'est', 'return ' + texpr + ';')(
    k, kind, n => String(n == null ? 0 : n), s => s + 's', '');
  const k1 = { on: true, done: 1, total: 5, left: 4, held: 2, gaveup: 3, eta_s: null, speed: null, measured: true };
  const line1 = tallyOf(k1, 'thinking');
  t('A1 the tally line says "3 given up" beside "2 never on their own"',
    /3 given up/.test(line1) && /2 never on their own/.test(line1), line1);
  const line0 = tallyOf(Object.assign({}, k1, { gaveup: 0 }), 'thinking');
  t('A1 no gave-ups, no phrase', line0.indexOf('given up') < 0);

  console.log(ok + ' ok, ' + bad + ' failed');
  process.exit(bad ? 1 : 0);
})().catch(e => { console.log('HARNESS ERROR ' + (e && e.stack || e)); console.log(ok + ' ok, ' + (bad + 1) + ' failed'); process.exit(1); });

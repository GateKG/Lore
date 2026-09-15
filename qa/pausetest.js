// 3.38 drop P - the ui.html half, PROVEN on the shipped code the way
// uiloops336.js proves the 3.36 fixes: the real function is lifted out of
// ui.html, run on a fixture, and the same fixture is run on the PARITY_BASE
// twin to show what he saw. Nothing here touches the shelf.
//
//   P1  the developer fps meter has no key. A bare F8 toggled it, and a
//       bare F8 also arrives from game keybinds and some keyboards' media
//       rows (his Discord-clip hotkey is ctrl+alt+F8): "wtf is this weird
//       fps counter??? why do I have an fps counter". Only #fps in the
//       URL shows it now.
//   P3  the Settings row for pause_close_minutes sits beside the AFK rows
//       and the mock carries its default.
//   P4  flagsWatch never empties its map. A blanket used to _have.clear()
//       and refill 1,377 paths in batches of 300; the "audited" chip's
//       avMatch treats a row with no flags yet as not matching, so the
//       list shrank to the refilled part and grew back on every landing:
//       "it keeps changing in front of me from 70 to 120". The refill is
//       in place now, newest first, and with a ring only the landed path
//       is re-asked.
const fs = require('fs');
const cp = require('child_process');
const ROOT = 'D:/Gate LLC';
const src = fs.readFileSync(ROOT + '/ui.html', 'utf8');

// THE PARITY BASE IS A COMMIT, NOT HEAD. 747f76a is 3.37, the tree he was
// running on 15 Sep; HEAD would make every "before" witness vanish the
// moment this drop lands.
const PARITY_BASE = '747f76a';
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

// ===================================================================
// P1 - the fps meter has no key
// ===================================================================
console.log('--- P1: the fps meter has no key ---');
const meter = sliceBlock(src, 'function fpsMeter(){');
const meterBase = sliceBlock(base, 'function fpsMeter(){');
t('P1 no keydown handler in ui.html tests e.key===\'F8\'',
  src.indexOf("e.key==='F8'") < 0 && !/keydown[^\n]{0,120}F8/.test(src));
t('P1 fpsMeter registers no key listener at all', meter.indexOf('addEventListener') < 0);
t('P1 the #fps road still exists', meter.indexOf("set(location.hash.includes('fps'))") > 0);
t('P1 [before, ' + PARITY_BASE + '] a bare F8 toggled it',
  meterBase.indexOf("addEventListener('keydown',e=>{if(e.key==='F8')set(!on);});") > 0);

// ===================================================================
// P3 - the Settings row and the mock
// ===================================================================
console.log('--- P3: the Settings row ---');
const afkRow = src.indexOf("row(L,'\u2026after how many minutes',ctlNum('afk_minutes',1,120));");
const capRow = src.indexOf("ctlNum('pause_close_minutes',0,1440)");
t('P3 the pause-close row sits right after the AFK rows', afkRow > 0 && capRow > afkRow && capRow - afkRow < 900);
t('P3 its hint is prose and says a pause he made himself is never closed',
  /hint\(L,'A recording paused because you were away[^\n]*A pause you made yourself is never closed by this/.test(src));
const mock = (src.match(/get_settings:async\(\)=>\(\{settings:\{([\s\S]*?)\}\}\)/) || [, ''])[1];
t('P3 the mock carries pause_close_minutes:0 (off by default)', mock.indexOf('pause_close_minutes:0,') > 0);
t('P3 [before, ' + PARITY_BASE + '] no such row, no such key',
  base.indexOf('pause_close_minutes') < 0);

// ===================================================================
// P4 - flagsWatch never empties its map
// ===================================================================
console.log('--- P4: the map is never emptied ---');
const NPATHS = 1366;
// the fixture: half the shelf audited (odd rows), the "audited" chip on,
// the REAL avMatch lifted beside the REAL flagsWatch; have_flags measures
// the chip's count at the moment each batch is asked
function flagsRig(text) {
  const a = text.indexOf('let _doneRev=null;');
  const b = text.indexOf('setInterval(flagsWatch,4000);');
  if (a < 0 || b < 0 || b < a) throw new Error('flagsWatch block not found');
  const fw = text.slice(a, b);
  if (fw.split('async function flagsWatch(').length !== 2) throw new Error('flagsWatch lifted twice');
  const am = sliceBlock(text, 'function avMatch(v){');
  const rig = new Function('NPATHS', `
    const document={hidden:false,querySelectorAll:()=>[],addEventListener(){}};
    let _visWake=[]; const _visKick=()=>{}; function _parked(){return false;}
    const _have=new Map();
    const S={meta:{}};
    const AV={game:null,q:'',kind:'any',sort:'',anchor:null,
              want:{hl:0,stt:0,ins:0,aud:1},after:'',before:'',minM:'',maxM:''};
    ${am}
    const paths=[]; const rows=[];
    for(let i=0;i<NPATHS;i++){
      paths.push('D:/R/n'+i+'.mp4');
      rows.push({path:paths[i],kind:'session',gkey:'g',gname:'g',mtime:1000+i});
      _have.set(paths[i],{hl:true,ins_lvl:0,aud_lvl:(i%2)?2:0});
    }
    const avAll=()=>rows.slice();
    const audited=()=>rows.filter(avMatch).length;
    let V={cur:{path:paths[7]}}; const avNode=()=>null;
    const avPaint=()=>{}; const avFlagsRefresh=()=>{}; const thrForget=()=>{};
    let loads=0; const loadThread=()=>{loads++;}; const loadSaid=()=>{}; const _viewerReq=0;
    /* the retry's spacing is not waited for; fail(ps, n) makes the n-th
       have_flags call throw; each answered row is stamped with the beat's
       gen BESIDE the map (never inside the flags - an unchanged night must
       still read unchanged), so a row that kept OLD flags can be told from
       one that landed */
    const setTimeout=(f,ms)=>global.setTimeout(f,0), clearTimeout=global.clearTimeout;
    const script=[]; let rpc=0, asked=[], batches=[], minAud=Infinity, minHave=Infinity, gen=0, fail=null;
    const landed=new Map(), lastObj=new Map();
    const api={
      ai_status:async()=>script.length?script.shift():null,
      have_flags:async ps=>{rpc++; asked=asked.concat(ps); batches.push(ps.slice());
        minAud=Math.min(minAud,audited()); minHave=Math.min(minHave,_have.size);
        if(fail&&fail(ps,rpc))throw new Error('lost');
        const o={};
        ps.forEach(p=>{const i=+p.slice(6,-4);
          o[p]={hl:true,ins_lvl:(p===paths[7]&&flip)?2:0,aud_lvl:(i%2)?2:0};
          landed.set(p,gen); lastObj.set(p,o[p]);});
        return o;}
    };
    let flip=false;
    ${fw}
    const fresh=()=>paths.filter(p=>landed.get(p)===gen&&_have.get(p)===lastObj.get(p)).length;
    return {
      paths, _have, audited,
      stale:()=>(typeof _haveStale==='object'&&_haveStale)?_haveStale.size:-1,
      setFlip:v=>{flip=v;}, setFail:f=>{fail=f;}, left:()=>script.length,
      beat:async st=>{ rpc=0; asked=[]; batches=[]; minAud=Infinity; minHave=Infinity; gen++;
        const l0=loads; if(st)script.push(st); await flagsWatch();
        return {rpc, asked:asked.length, set:[...new Set(asked)].sort(), have:_have.size,
                loads:loads-l0, batches, minAud, minHave, aud:audited(), fresh:fresh()}; },
      /* two ticks at once: the interval firing during a chain */
      beat2:async(s1,s2)=>{ rpc=0; asked=[]; batches=[]; gen++; script.push(s1,s2);
        await Promise.all([flagsWatch(),flagsWatch()]);
        return {rpc, asked:asked.length, left:script.length, fresh:fresh()}; }
    };`)(NPATHS);
  return rig;
}

(async () => {
  const R = flagsRig(src);
  const P = R.paths;
  const PRE = R.audited();
  t('P4 the fixture: 683 of 1,366 rows match the "audited" chip before anything lands',
    PRE === 683, 'pre=' + PRE);
  let r;
  r = await R.beat({ done_rev: 101, done_path: P[3] });
  t('P4 first tick adopts done_rev and asks nothing', r.rpc === 0);
  // a blanket the ring cannot explain: the shape the 3.37 backend (no ring) produced all afternoon
  r = await R.beat({ done_rev: 140, done_path: P[3] });
  t('P4 a blanket still re-asks the whole shelf, in batches of 300',
    r.asked === NPATHS && r.rpc === Math.ceil(NPATHS / 300), 'asked=' + r.asked + ' rpc=' + r.rpc);
  t('P4 ...and the count of rows matching the "audited" chip NEVER drops below its pre-blanket value while the batches land',
    r.minAud >= PRE && r.aud === PRE, 'min=' + r.minAud + ' pre=' + PRE);
  t('P4 ...the map never has a hole: every row keeps its flags until its answer replaces them',
    r.minHave === NPATHS && r.have === NPATHS, 'minHave=' + r.minHave);
  const newest = P.slice().sort((x, y) => (+y.slice(6, -4)) - (+x.slice(6, -4)));
  t('P4 ...the batches go newest-first (the first batch is the 300 newest nights)',
    r.batches.length === 5 && r.batches[0].join() === newest.slice(0, 300).join()
    && r.batches[4].join() === newest.slice(1200).join());
  // the ring, as the backend now writes it: 16 entries of {rev, path}, revs contiguous
  const ring = []; for (let k = 0; k < 16; k++) ring.push({ rev: 125 + k, path: P[(k * 7) % NPATHS] });
  r = await R.beat({ done_rev: 140, done_path: ring[15].path, done_paths: ring });
  t('P4 the same rev with the ring in hand is a no-op (nothing moved)', r.rpc === 0);
  const ring2 = []; for (let k = 0; k < 16; k++) ring2.push({ rev: 127 + k, path: (k < 14) ? P[9] : P[11] });
  r = await R.beat({ done_rev: 142, done_path: P[11], done_paths: ring2 });
  t('P4 with a ring only the landed paths are re-asked (two revs past the one we saw: one night), one RPC',
    r.rpc === 1 && r.asked === 1 && r.set.length === 1 && r.set[0] === P[11], 'asked=' + r.asked);
  t('P4 ...and a direct hit keeps its row too: no hole, the chip\'s count untouched',
    r.minHave === NPATHS && r.minAud === PRE);
  // the viewer rules of 3.36 still hold on the in-place refill
  R.setFlip(false);
  r = await R.beat({ done_rev: 144, done_path: P[7],
    done_paths: [{ rev: 143, path: P[7] }, { rev: 144, path: P[7] }] });
  t('P4 the open recording still reloads on its own landing', r.loads === 1 && r.asked === 1);
  r = await R.beat({ done_rev: 170, done_path: P[8],
    done_paths: [{ rev: 169, path: P[8] }, { rev: 170, path: P[8] }] });
  t('P4 a blanket with the open recording unchanged still does not reload it', r.asked === NPATHS && r.loads === 0);
  R.setFlip(true);
  r = await R.beat({ done_rev: 200, done_path: P[8],
    done_paths: [{ rev: 199, path: P[8] }, { rev: 200, path: P[8] }] });
  t('P4 a blanket that moved the open recording\'s flags still reloads it', r.asked === NPATHS && r.loads === 1);
  t('P4 the source: no _have.clear(), no per-path delete in flagsWatch',
    src.indexOf('_have.clear();') < 0 && src.indexOf('stale.forEach(q=>_have.delete(q))') < 0);

  // --- the review's two lows on the page ---
  console.log('--- P4: a lost batch is retried, then owed; one chain at a time ---');
  const R2 = flagsRig(src);
  await R2.beat({ done_rev: 101, done_path: R2.paths[3] });
  R2.setFail((ps, n) => n === 3);            // the third call is lost once
  r = await R2.beat({ done_rev: 140, done_path: R2.paths[3] });
  t('P4 a batch lost ONCE is retried in place: 6 calls for 5 batches, every row lands fresh, nothing owed',
    r.rpc === 6 && r.fresh === NPATHS && r.have === NPATHS && R2.stale() === 0,
    'rpc=' + r.rpc + ' fresh=' + r.fresh + ' owed=' + R2.stale());
  let lostBatch = null;
  R2.setFail((ps, n) => { if (n === 3) lostBatch = ps.slice(); return n >= 3 && n <= 5; });   // three tries, all lost
  r = await R2.beat({ done_rev: 180, done_path: R2.paths[3] });
  t('P4 a batch lost for GOOD (three tries): its 300 rows keep their OLD flags - no hole - and are owed',
    r.rpc === 7 && r.have === NPATHS && r.fresh === NPATHS - 300 && R2.stale() === 300
    && lostBatch && lostBatch.length === 300 && r.minAud >= PRE,
    'rpc=' + r.rpc + ' have=' + r.have + ' fresh=' + r.fresh + ' owed=' + R2.stale());
  R2.setFail(null);
  r = await R2.beat({ done_rev: 180, done_path: R2.paths[3] });
  t('P4 the next tick, with NO landing, asks exactly the owed 300 first and clears the debt',
    r.rpc === 1 && r.asked === 300 && r.set.join() === lostBatch.slice().sort().join()
    && r.fresh === 300 && R2.stale() === 0, 'rpc=' + r.rpc + ' asked=' + r.asked);
  r = await R2.beat({ done_rev: 180, done_path: R2.paths[3] });
  t('P4 ...and with nothing owed the same rev is a no-op again', r.rpc === 0);
  // owed paths ride ahead of a direct hit, once
  R2.setFail((ps, n) => n >= 1 && n <= 3);
  await R2.beat({ done_rev: 182, done_path: R2.paths[5],
    done_paths: [{ rev: 181, path: R2.paths[5] }, { rev: 182, path: R2.paths[5] }] });
  R2.setFail(null);
  r = await R2.beat({ done_rev: 184, done_path: R2.paths[9],
    done_paths: [{ rev: 183, path: R2.paths[9] }, { rev: 184, path: R2.paths[9] }] });
  t('P4 a direct hit lost for good is owed and rides with the next direct hit, first',
    r.rpc === 1 && r.asked === 2 && r.batches[0].join() === [R2.paths[5], R2.paths[9]].join() && R2.stale() === 0,
    'asked=' + r.asked);

  const R3 = flagsRig(src);
  await R3.beat({ done_rev: 101, done_path: R3.paths[3] });
  r = await R3.beat2({ done_rev: 140, done_path: R3.paths[3] },
                     { done_rev: 141, done_path: R3.paths[5] });
  t('P4 two ticks at once: the second finds a chain running and does not even read ai_status (one blanket, the second status still unread)',
    r.rpc === 5 && r.left === 1, 'rpc=' + r.rpc + ' left=' + r.left);
  r = await R3.beat();
  t('P4 ...the next tick reads it and takes the one-night direct hit', r.rpc === 1 && r.asked === 1 && R3.left() === 0);
  const fwSrc = src.slice(src.indexOf('let _doneRev=null;'), src.indexOf('setInterval(flagsWatch,4000);'));
  t('P4 the source: a reentry guard before done_rev is read, evLoadMarks\' three-try shape per batch, the owed set',
    fwSrc.indexOf('if(_fwRun)return;') > 0 && fwSrc.indexOf('_fwRun=true;') < fwSrc.indexOf('api.ai_status()')
    && fwSrc.indexOf('for(let k=0;k<3;k++){') > 0 && fwSrc.indexOf('setTimeout(z,700*k)') > 0
    && fwSrc.indexOf('const _haveStale=new Set();') > 0 && fwSrc.split('async function _flagsWatchRun(').length === 2);
  t('P4 ...and evLoadMarks asks the owed paths too, and forgets them as they land',
    src.indexOf('all.filter(p=>!_have.has(p)||_haveStale.has(p))') > 0
    && src.indexOf('_have.set(k,r[k]);_haveStale.delete(k);') > 0);

  // the before: the same blanket on the parity base
  const B = flagsRig(base);
  const PREB = B.audited();
  await B.beat({ done_rev: 101, done_path: B.paths[3] });
  const rb = await B.beat({ done_rev: 140, done_path: B.paths[3] });
  t('P4 [before, ' + PARITY_BASE + '] the same blanket emptied the map: the chip\'s count fell to zero and the list grew back batch by batch - 70, then 120',
    PREB === 683 && rb.minAud === 0 && rb.minHave === 0 && rb.asked === NPATHS && rb.aud === PREB,
    'min=' + rb.minAud + ' minHave=' + rb.minHave);
  const B2 = flagsRig(base);
  await B2.beat({ done_rev: 101, done_path: B2.paths[3] });
  B2.setFail((ps, n) => n === 3);
  const rb2 = await B2.beat({ done_rev: 140, done_path: B2.paths[3] });
  t('P4 [before, ' + PARITY_BASE + '] one lost batch STOPPED the chain: 3 calls, 766 holes in the emptied map, no retry, nothing owed',
    rb2.rpc === 3 && rb2.have === 600 && B2.stale() === -1, 'rpc=' + rb2.rpc + ' have=' + rb2.have);
  const B3 = flagsRig(base);
  await B3.beat({ done_rev: 101, done_path: B3.paths[3] });
  const rb3 = await B3.beat2({ done_rev: 140, done_path: B3.paths[3] },
                             { done_rev: 141, done_path: B3.paths[5] });
  t('P4 [before, ' + PARITY_BASE + '] two ticks at once ran two chains (both statuses consumed, 6 calls)',
    rb3.left === 0 && rb3.rpc === 6, 'rpc=' + rb3.rpc + ' left=' + rb3.left);

  console.log('\n' + ok + ' ok, ' + bad + ' failed');
  process.exit(bad ? 1 : 0);
})().catch(e => { console.log('CRASH ' + (e && e.stack || e)); process.exit(1); });

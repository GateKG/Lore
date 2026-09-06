// 3.34 J: THE TIMELINE IS THE CHAPTERS, THE MOMENTS ARE THE RED.
// The SHIPPED placers are lifted out of ui.html and run against a fake bar
// and a fake player, so what the bar draws - and what a press on it does -
// is proven rather than assumed. Same idiom as paneltest.js / cliptest.js.
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

let ok = 0, bad = 0;
function check(name, cond) {
  if (cond) { ok++; console.log('  OK   ' + name); }
  else { bad++; console.log('  FAIL ' + name); }
}

// ---- the smallest DOM that can hold a seek bar -------------------------
const BAR = { left: 100, width: 1000, top: 0 };
function makeNode(tag) {
  const n = { tag: tag || 'div', id: '', children: [], parent: null,
              style: {}, dataset: {}, _ls: {}, _cls: new Set(), _html: '',
              offsetWidth: 120 };
  n.classList = {
    add: (...c) => c.forEach(x => x && n._cls.add(x)),
    remove: (...c) => c.forEach(x => n._cls.delete(x)),
    contains: c => n._cls.has(c),
    toggle: (c, on) => { if (on === undefined) on = !n._cls.has(c);
      if (on) n._cls.add(c); else n._cls.delete(c); return on; },
  };
  Object.defineProperty(n, 'className', {
    get: () => [...n._cls].join(' '),
    set: v => { n._cls = new Set(String(v).split(/\s+/).filter(Boolean)); } });
  Object.defineProperty(n, 'innerHTML', {
    get: () => n._html,
    set: v => { n._html = v == null ? '' : String(v);
      if (!v) { n.children.forEach(c => { c.parent = null; }); n.children = []; } } });
  Object.defineProperty(n, 'firstChild', { get: () => n.children[0] || null });
  n.append = (...ks) => ks.forEach(k => { k.parent = n; n.children.push(k); });
  n.insertBefore = (k, ref) => { const i = ref ? n.children.indexOf(ref) : -1;
    k.parent = n; if (i < 0) n.children.push(k); else n.children.splice(i, 0, k); };
  n.remove = () => { if (n.parent) { const i = n.parent.children.indexOf(n);
    if (i >= 0) n.parent.children.splice(i, 1); } n.parent = null; };
  n.removeAttribute = () => {};
  n.addEventListener = (t, f) => { (n._ls[t] = n._ls[t] || []).push(f); };
  n.fire = (t, ev) => (n._ls[t] || []).forEach(f => f(Object.assign(
    { preventDefault() {}, stopPropagation() {} }, ev || {})));
  n.getBoundingClientRect = () => ({ left: BAR.left, width: BAR.width, top: BAR.top });
  n.querySelectorAll = sel => { const want = sel.replace(/^\./, ''), out = [];
    (function walk(p) { p.children.forEach(c => {
      if (c._cls.has(want)) out.push(c); walk(c); }); })(n);
    return out; };
  return n;
}

// ---- the night: four chapters, five moments, one of them the screen's ----
const DUR = 1200;
const CH = [
  { t: 0,   label: 'warm-up',         what: 'settling in, nothing decided yet' },
  { t: 300, label: 'the good lobby',  what: 'the run finally begins' },
  { t: 600, label: 'the final fight', what: 'the last board, and it is close' },
  { t: 900, label: 'after',           what: 'winding down' },
];
const MOM = [
  { t: 120, why: 'you shouted at a topdeck' },
  { t: 420, why: 'big laugh - he had no idea' },
  { t: 660, why: 'the clutch' },
  { t: 700, why: 'the screen decided', kind: 'outcome' },
  { t: 960, why: 'goodnight' },
];

// ---- the harness -------------------------------------------------------
let wrap, video, seeks, inView, cards, said;
function fresh() {
  wrap = makeNode('div');
  video = { currentTime: 0, duration: DUR };
  seeks = []; inView = []; cards = []; said = [];
}
const ENV = {
  $: sel => sel === '#vseekwrap' ? wrap : (sel === '#vvideo' ? video : null),
  document: { createElement: t => makeNode(t) },
  tlDur: () => (video && video.duration) || 0,
  tlGeom: () => ({ W: Math.max(1, BAR.width - 14), width: BAR.width }),
  tlPaint: () => {},
  chapterInView: t => inView.push(t),
  markCardShow: m => cards.push(m),
  momTogglePick: () => {},
  markTipHide: () => { if (wrap._tip) { wrap._tip.classList.remove('on'); wrap._tip._c = null; } },
  markTipArmHide: () => {},
  whisper: s => said.push(s),
  clamp: (v, a, b) => Math.max(a, Math.min(b, v)),
  esc: s => String(s),
  fmtT: s => { s = Math.max(0, Math.floor(s));
    return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); },
  el: (t, c, h) => { const e = makeNode(t); if (c) e.className = c;
    if (h != null) e.innerHTML = h; return e; },
  MARKS: null, V: null, momPick: null,
};

const CODE = ['chapList', 'chapAt', 'chapSegsPaint', 'chapNotchPlace',
              'momMarksPlace', 'tlWin', 'tlPx', 'tlTimeAt',
              'markTipNode', 'chapTipShow', 'chapTipAtX'].map(lift).join('\n');
const build = new Function('ENV', `
  const {$, document, tlDur, tlGeom, tlPaint, chapterInView, markCardShow,
         momTogglePick, markTipHide, markTipArmHide, whisper, clamp, esc,
         fmtT, el} = ENV;
  let _ins = null, _tlG = null, _viewerReq = 1, _tipHideT = null;
  const MARKS = ENV.MARKS, V = ENV.V, _momPick = ENV.momPick;
  ${CODE}
  return {chapSegsPaint, chapNotchPlace, momMarksPlace, chapAt, chapTipAtX,
          tlPx, tlWin, tlTimeAt,
          setIns: x => { _ins = x; }, setG: g => { _tlG = g; }};
`);

let F;
function boot(ins, marks, v) {
  fresh();
  ENV.MARKS = Object.assign({ gold: true, red: true, loud: true, laugh: true,
    scream: true, told: true, sense: true, game: true, outcome: true }, marks || {});
  ENV.V = Object.assign({ zoom: 0, winA: null, tlPin: false }, v || {});
  ENV.momPick = new Set();
  F = build(ENV);
  F.setIns(ins);
  F.setG({ W: BAR.width - 14, width: BAR.width });
}
const segs = () => wrap.querySelectorAll('.chseg');
const notches = () => wrap.querySelectorAll('.chnotch');
const lit = list => list.filter(n => !n.classList.contains('hid'));
const moms = () => wrap.querySelectorAll('.insmark');
const px = n => parseFloat(n.style.left);

console.log('--- the bar is divided into chapters ---');
boot({ chapters: CH, moments: MOM });
F.chapSegsPaint();
check('one section per chapter', segs().length === 4);
check('the two tints alternate, and only they',
  segs().map(s => s.classList.contains('alt') ? 1 : 0).join('') === '0101');
{
  const s = segs();
  const gaps = [];
  for (let i = 0; i + 1 < s.length; i++)
    gaps.push(Math.round(px(s[i + 1]) - (px(s[i]) + parseFloat(s[i].style.width))));
  check('neighbours are parted by exactly 2px', gaps.every(g => g === 2));
  check('the sections span the whole bar, in order',
    Math.round(px(s[0])) === 8 &&
    Math.round(px(s[3]) + parseFloat(s[3].style.width)) === 992);
  check('each section knows which chapter it is',
    s[2]._c === CH[2] && s[2]._a === 600 && s[2]._b === 900);
}
check('no notch is drawn - the split IS the chapter (his word, 6 Sep)',
  notches().length === 0);
check('chapNotchPlace is a sweeper now, never a builder',
  /function chapNotchPlace\(ch\)\{[\s\S]{0,600}?ch=\[\];/.test(src) &&
  src.indexOf("m.className='chnotch'") < 0);

console.log('\n--- hovering names the section ON THE THUMBNAIL ---');
{
  const t = 700;                                  // inside chapter 3
  const c = F.chapAt(t);
  check('the pointer finds the chapter it is over',
    !!c && c.label === CH[2].label);
  check('the clock line names it, the sentence sits under the frame',
    src.indexOf("$('#vpeekt').textContent=fmtT(Math.max(0,t))+(_cn?'  \\u00b7  '+_cn:'')") > 0 &&
    src.indexOf("_pw.textContent=_cw") > 0);
  check('a chapter whose what repeats its label shows no sentence',
    src.indexOf("_cp.what!==_cp.label") > 0);
  check('the track no longer raises a tip of its own',
    src.indexOf('chapTipAtX(e.clientX)') < 0);
}

console.log('\n--- the moments are the red marks below ---');
boot({ chapters: CH, moments: MOM });
F.momMarksPlace();
check('one red mark per moment, the screen\'s own skipped', moms().length === 4);
check('they stand at the moments\' seconds',
  moms().every((m, i) => {
    const t = [120, 420, 660, 960][i];
    return Math.round(px(m)) === Math.round(F.tlPx(t) - 1);
  }));
check('the moment lives on the node', moms()[1]._m === MOM[1] &&
  moms()[1]._said.why === MOM[1].why && moms()[1]._ev.t === 420);
// a moment with no why falls through to ev.kind in markCardShow, and
// 'a loud moment' is the exact claim this drop took off the red row
check('every red mark says it is a MOMENT, not a loud second',
  moms().every(m => m._ev.kind === 'moment') &&
  src.indexOf("moment:'a described moment'") > 0);
{
  const before = video;
  video = { currentTime: 0, duration: DUR };
  F.momMarksPlace();                       // re-place: same nodes, new player
  moms()[2].fire('pointerdown');
  check('a press lands two seconds before the moment', video.currentTime === 658);
  check('...on the LIVE player, not the one the render closed over',
    before.currentTime === 0);
  check('...and opens the card on that mark', cards.length === 1 && cards[0] === moms()[2]);
}

console.log('\n--- the chips ---');
boot({ chapters: CH, moments: MOM });
F.momMarksPlace(); F.chapSegsPaint();
ENV.MARKS.told = false; F.momMarksPlace();
check('the moments chip puts the red row away',
  moms().length === 4 && lit(moms()).length === 0);
ENV.MARKS.told = true; F.momMarksPlace();
check('...and brings it back', lit(moms()).length === 4);
ENV.MARKS.red = false; F.chapSegsPaint();
check('the chapter chip takes the sections away',
  segs().length === 0);
ENV.MARKS.red = true; F.chapSegsPaint();
check('...and puts them back', segs().length === 4);

console.log('\n--- zoomed to one chapter ---');
boot({ chapters: CH, moments: MOM }, null, { zoom: 250, winA: 300 });
F.chapSegsPaint(); F.momMarksPlace();
check('the window really is 300 -> 550',
  Math.round(F.tlWin().a) === 300 && Math.round(F.tlWin().b) === 550);
check('only the section that is on screen is drawn',
  segs().length === 1 && segs()[0]._c === CH[1]);
check('and only the moments inside it',
  moms().length === 1 && moms()[0]._m === MOM[1]);

console.log('\n--- nothing to draw ---');
boot({ chapters: [], moments: [] });
F.chapSegsPaint(); F.momMarksPlace();
check('a night with no review draws no sections, notches or marks',
  segs().length === 0 && notches().length === 0 && moms().length === 0);
boot(null);
F.chapSegsPaint(); F.momMarksPlace();
check('and a missing review does not throw', true);

console.log('\n--- what an older save may still switch off ---');
// 'told' stopped meaning a tint on some gold marks and started
// meaning the whole red moments row. A Told=off saved against the
// old meaning would open 3.34 with the tome's own moments gone.
{
  const restore = src.slice(src.indexOf("localStorage.getItem('lore."
    + "marks')"), src.indexOf('MARKS.gold=true;'));
  check('the blind restore loop no longer carries told',
    restore.indexOf("'scream','sense'") > 0 &&
    restore.indexOf("'scream','told'") < 0);
  check('told comes back only from a save stamped since the meaning'
    + ' changed',
    restore.indexOf("m.v>=2&&typeof m.told==='boolean'") > 0 &&
    src.indexOf('JSON.stringify(Object.assign({v:2},MARKS))') > 0);
}

console.log('\n--- one event, one mark (his 4:54 gold vs 4:55 red) ---');
{
  check('gold never speaks the describer\'s moment',
    src.indexOf("m._said=null;") > 0 &&
    src.indexOf("'\\u2726 '+m._said.why") < 0 &&
    src.indexOf("esc(said?('\\u2726 '+said.why)") < 0);
  check('a loud second a moment already claims draws once',
    src.indexOf('m._claimed=!!(said&&said.d<=3);') > 0 &&
    /if\(m\._claimed&&MARKS\.told!==false&&\(m\._ev\|\|\{\}\)\.kind!=='outcome'\)/
      .test(src));
  check('...but the screen\'s own verdict never steps aside',
    src.indexOf("kind!=='outcome'") > 0);
  check('...and putting the moments away brings it back',
    src.indexOf('MARKS.told!==false') > 0);
}

console.log('\n' + ok + ' ok, ' + bad + ' failed');
process.exit(bad ? 1 : 0);

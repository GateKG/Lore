// The SHIPPED clipper gestures, lifted out of ui.html and driven against
// a fake bar: taking an edge, sliding the span, and - the whole point of
// 3.29 - a press on your own clip that does not throw it away.
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

// the bar: 1000 px wide at x=100, 7 px of padding each side, showing
// the whole of a 120 s recording
const BAR = { left: 100, width: 1000 };
const DUR = 120;
const env = {
  clamp: (v, a, b) => Math.max(a, Math.min(b, v)),
  tlWin: () => ({ a: 0, len: DUR }),
  tlDur: () => DUR,
  $: () => ({ getBoundingClientRect: () => BAR }),
};

const CODE = [lift('clipEdges'), lift('clipHit'), lift('tlTimeAt')].join('\n');
const api = new Function(
  'clamp', 'tlWin', 'tlDur', '$', 'CLIP', 'CLIP_GRAB_PX',
  CODE + '\nreturn {clipEdges, clipHit, tlTimeAt};');

let ok = 0, bad = 0;
function check(name, cond) {
  if (cond) { ok++; console.log('  OK   ' + name); }
  else { bad++; console.log('  FAIL ' + name); }
}

// x for a time, the inverse of what the band is painted with
const X = t => BAR.left + 7 + (t / DUR) * (BAR.width - 14);

function mk(a, b) {
  const CLIP = { on: true, a: a, b: b, drag: false, mode: 'new', grab: 0 };
  const f = api(env.clamp, env.tlWin, env.tlDur, env.$, CLIP, 12);
  return { CLIP, f };
}

console.log('--- what the pointer is over ---');
{
  const { f } = mk(30, 60);
  check('the left edge answers to its own end', f.clipHit(X(30)) === 'a');
  check('the right edge answers to its own end', f.clipHit(X(60)) === 'b');
  check('the middle answers "slide me"', f.clipHit(X(45)) === 'in');
  check('outside answers nothing - a new span starts there',
        f.clipHit(X(10)) === null && f.clipHit(X(90)) === null);
  check('the grab is a band, not a pixel - 10px off still takes the edge',
        f.clipHit(X(30) + 10) === 'a' && f.clipHit(X(60) - 10) === 'b');
  check('...but 20px off does not', f.clipHit(X(30) - 20) === null);
}
{
  const { f } = mk(null, null);
  check('with nothing marked, everywhere starts a new span',
        f.clipHit(X(50)) === null);
}

// the gestures, exactly as wireClipper runs them
function press(st, clientX) {
  const hit = st.f.clipHit(clientX);
  const C = st.CLIP;
  C.drag = true; C.mode = hit || 'new';
  if (hit === 'in') {
    C.grab = st.f.tlTimeAt(clientX);
    C._a0 = Math.min(C.a, C.b); C._b0 = Math.max(C.a, C.b);
  } else if (hit) {
    const lo = Math.min(C.a, C.b), hi = Math.max(C.a, C.b);
    C.a = (hit === 'a') ? hi : lo;
    C.b = (hit === 'a') ? lo : hi;
    C.mode = 'end';
  } else { C.a = st.f.tlTimeAt(clientX); C.b = C.a; }
}
function move(st, clientX, MAX) {
  const C = st.CLIP, t = st.f.tlTimeAt(clientX);
  if (C.mode === 'in') {
    const len = C._b0 - C._a0, d = DUR;
    let a = C._a0 + (t - C.grab);
    a = Math.max(0, Math.min(a, Math.max(0, d - len)));
    C.a = a; C.b = a + len;
  } else {
    C.b = (t >= C.a) ? Math.min(t, C.a + MAX) : Math.max(t, C.a - MAX);
  }
}
function release(st) {
  const C = st.CLIP;
  C.drag = false;
  if (C.b < C.a) { const t = C.a; C.a = C.b; C.b = t; }
  if (C.mode === 'new' && C.b - C.a < 0.4) C.b = Math.min(C.a + 3, DUR);
  if (C.mode === 'end' && C.b - C.a < 0.15) C.b = C.a + 0.15;
  C.mode = 'new';
}

console.log('\n--- a press on your own clip does not throw it away ---');
{
  const st = mk(30, 42);
  press(st, X(36));            // straight down the middle
  release(st);                 // ...and up again, without moving
  check('a still click inside leaves the span exactly as it was',
        st.CLIP.a === 30 && st.CLIP.b === 42);
}
{
  const st = mk(30, 42);
  press(st, X(80));            // outside
  release(st);
  check('a click OUTSIDE still starts a new one, as before',
        st.CLIP.a !== 30 && Math.abs(st.CLIP.b - st.CLIP.a - 3) < 0.2);
}

console.log('\n--- the edges move, the other end stays put ---');
{
  const st = mk(30, 36);
  press(st, X(36));            // take the right end
  move(st, X(44), 15); release(st);   // 14 s - inside the ceiling
  check('pulling the right edge out lengthens it, left end unmoved',
        Math.abs(st.CLIP.a - 30) < 0.2 && Math.abs(st.CLIP.b - 44) < 0.3);
}
{
  const st = mk(30, 42);
  press(st, X(42));
  move(st, X(35), 15); release(st);
  check('pushing the right edge in shortens it, left end unmoved',
        Math.abs(st.CLIP.a - 30) < 0.2 && Math.abs(st.CLIP.b - 35) < 0.3);
}
{
  const st = mk(30, 36);
  press(st, X(30));            // take the LEFT end
  move(st, X(23), 15); release(st);   // 13 s - inside the ceiling
  check('pulling the left edge out lengthens it, right end unmoved',
        Math.abs(st.CLIP.a - 23) < 0.3 && Math.abs(st.CLIP.b - 36) < 0.2);
}
{
  const st = mk(30, 42);
  press(st, X(30));
  move(st, X(5), 15); release(st);   // past the 15 s ceiling
  check('an edge cannot be pulled past what Discord will take',
        Math.abs(st.CLIP.b - st.CLIP.a) <= 15.05);
}
{
  const st = mk(30, 42);
  press(st, X(42));
  move(st, X(60), 15); release(st);   // 30 s asked for, 15 allowed
  check('...from either end - the anchor holds and the ceiling bites',
        Math.abs(st.CLIP.a - 30) < 0.2
        && Math.abs(st.CLIP.b - 45) < 0.3);
}

console.log('\n--- the whole span slides ---');
{
  const st = mk(30, 42);
  press(st, X(36));
  move(st, X(46), 15); release(st);
  check('sliding moves both ends and keeps the length',
        Math.abs((st.CLIP.b - st.CLIP.a) - 12) < 0.05
        && Math.abs(st.CLIP.a - 40) < 0.3);
}
{
  const st = mk(2, 14);
  press(st, X(8));
  move(st, X(0), 15); release(st);
  check('it stops at the start of the recording instead of squashing',
        st.CLIP.a >= -0.01 && Math.abs((st.CLIP.b - st.CLIP.a) - 12) < 0.05);
}
{
  const st = mk(100, 112);
  press(st, X(106));
  move(st, X(120), 15); release(st);
  check('and at the end of it',
        st.CLIP.b <= DUR + 0.01
        && Math.abs((st.CLIP.b - st.CLIP.a) - 12) < 0.05);
}

console.log('\n' + ok + ' ok, ' + bad + ' failed');
process.exit(bad ? 1 : 0);

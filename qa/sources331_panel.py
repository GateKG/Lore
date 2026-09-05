# -*- coding: utf-8 -*-
"""3.31 THE SAID PANEL BY SOURCE - the video toggle, the rows, the guards.

Two halves:
  1. the SHIPPED saidVisible and voiceText lifted out of ui.html and run
     under node (the paneltest.js lift): folding hides only src==='media'
     and leaves pos -1 for them; showing shows all; the query still
     applies to shown media lines; a transcript with no media lines gives
     the pre-3.31 loop's vis/pos exactly (the old loop is kept here
     verbatim); voiceText's four shapes;
  2. the wiring, read from the source: #vsqm in .vsrch, the CSS beside
     .sline.gml, SAID_MEDIA + localStorage 'lore.said.media' in try/catch,
     saidMediaPaint's count badge and the all-media empty row, media rows
     'media' + 'a video' + the why detail, game rows 'gml gl2' + 'the
     game', no naming chip on either, the copy prefixes and the 'left
     out' whisper, the lull and mark-tooltip filters, the library-search
     labels, voiceBadges/voiceText on the shelf rows, the mock rows - and
     that EVERY new read is guarded so an older lore.py (no src, no
     voices) paints as today. Then checkui over the whole file."""
import io
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(ROOT, "ui.html")
U = io.open(UI, encoding="utf-8").read()

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("  OK   " if cond else "  FAIL ") + name)


print("--- 1. saidVisible / voiceText under node ---")
NODE = r"""
const fs = require('fs');
const src = fs.readFileSync(%r, 'utf8');
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
const F = new Function(lift('saidVisible') + '\n' + lift('voiceText')
  + '\nreturn {saidVisible, voiceText};')();
/* the 3.30 loop, verbatim, for the no-media parity case */
function oldFilter(lines, low, q){
  const t=String(q||'').trim().toLowerCase();
  const n=lines.length;
  const vis=[], pos=new Array(n).fill(-1);
  for(let i=0;i<n;i++){
    if(!t||low[i].indexOf(t)>=0||(lines[i].when||'').indexOf(t)>=0){
      pos[i]=vis.length; vis.push(i);
    }
  }
  return {vis,pos};
}
let ok = 0, bad = 0;
const check = (n, c) => { c ? ok++ : bad++; console.log((c ? '  OK   ' : '  FAIL ') + n); };
const lines = [
  {t:4, when:'0:04', text:'Right, we are going in.', src:''},
  {t:9, when:'0:09', text:'Watch the left side.', src:'you'},
  {t:21, when:'0:21', text:'the Quilboar build is dead', src:'media'},
  {t:26, when:'0:26', text:'The enemy has slain your ally.', src:'game'},
  {t:31, when:'0:31', text:'Okay, last play - go for it.', src:''}];
const low = lines.map(l => l.text.toLowerCase());
let r = F.saidVisible(lines, low, '', false);
check('folded: the media line alone drops out of vis',
  JSON.stringify(r.vis) === '[0,1,3,4]');
check('...and its pos is -1 while the others count on',
  r.pos[2] === -1 && r.pos[3] === 2 && r.pos[4] === 3);
r = F.saidVisible(lines, low, '', true);
check('shown: all five', JSON.stringify(r.vis) === '[0,1,2,3,4]');
r = F.saidVisible(lines, low, 'quilboar', true);
check('a query still applies to a shown media line', JSON.stringify(r.vis) === '[2]');
r = F.saidVisible(lines, low, 'quilboar', false);
check('...and finds nothing when it is folded', r.vis.length === 0);
r = F.saidVisible(lines, low, '0:2', false);
check('the clock matches too (0:26 shown, 0:21 folded)', JSON.stringify(r.vis) === '[3]');
const plain = lines.map(l => Object.assign({}, l, {src: l.src === 'media' ? '' : l.src}));
const lowp = plain.map(l => l.text.toLowerCase());
for (const q of ['', 'the', '0:3', 'zzz']) {
  const a = F.saidVisible(plain, lowp, q, false), b = oldFilter(plain, lowp, q);
  check('no media lines: identical to the 3.30 loop for ' + JSON.stringify(q),
    JSON.stringify(a) === JSON.stringify(b));
}
const noSrc = lines.map(l => ({t: l.t, when: l.when, text: l.text}));
r = F.saidVisible(noSrc, low, '', false);
check('an older lore.py (no src at all): every line shows', r.vis.length === 5);
check('voiceText: nothing for null / absent / nights 0',
  F.voiceText(null) === '' && F.voiceText({}) === '' && F.voiceText({voices:null}) === ''
  && F.voiceText({voices:{chat:2, lines:1, nights:0}}) === '');
check('voiceText: voice chat in 3 of 4 nights',
  F.voiceText({voices:{chat:3, lines:0, nights:4}}) === 'voice chat in 3 of 4 nights');
check('voiceText: the game talks',
  F.voiceText({voices:{chat:0, lines:2, nights:4}}) === 'the game talks');
check('voiceText: both, joined',
  F.voiceText({voices:{chat:1, lines:1, nights:1}}) === 'voice chat in 1 of 1 night · the game talks');
console.log(ok + ' ok, ' + bad + ' failed');
process.exit(bad ? 1 : 0);
""" % UI.replace("\\", "/")
tmp = tempfile.mkdtemp(prefix="lore_panel331_")
js = os.path.join(tmp, "panel331.js")
io.open(js, "w", encoding="utf-8").write(NODE)
r = subprocess.run(["node", js], capture_output=True, text=True,
                   encoding="utf-8")
print(r.stdout.rstrip())
if r.stderr.strip():
    print(r.stderr.strip())
m = re.search(r"(\d+) ok, (\d+) failed", r.stdout or "")
if m:
    ok += int(m.group(1))
    bad += int(m.group(2))
else:
    bad += 1
    print("  FAIL node did not report")

print("\n--- 2. the wiring ---")
check("#vsqm sits in .vsrch after Ask, hidden until a night carries media",
      '<button id="vsqm" title="the video’s lines" style="display:none">'
      in U and U.index('id="vsqa"') < U.index('id="vsqm"') < U.index(
          'class="vsaidbody"'))
check(".sline.media CSS beside .sline.gml, dimmer than the game",
      ".sline.media{opacity:.42}" in U and ".sline.gml{opacity:.5}" in U
      and U.index(".sline.gml span{font-style:italic}")
      < U.index(".sline.media{opacity:.42}") < U.index(".sline .swho{"))
check("...the game row's chip and the toggle's on/count styles",
      ".sline.gl2 .swho{" in U and "#vsaid .vsrch #vsqm.on{" in U
      and "#vsaid .vsrch #vsqm .n{" in U)
check("SAID_MEDIA defaults off and reads localStorage in try/catch",
      "let SAID_MEDIA=false;" in U
      and "try{ SAID_MEDIA=localStorage.getItem('lore.said.media')==='1'; }"
          "catch(e){}" in U)
check("...and the write is guarded too",
      "try{localStorage.setItem('lore.said.media',SAID_MEDIA?'1':'0');}"
      "catch(_){}" in U)
check("saidFilter asks saidVisible with SAID_MEDIA",
      "const {vis,pos}=saidVisible(_said.lines,_said.low||[],q,SAID_MEDIA);"
      in U)
check("loadSaid maps why beside src and counts the media lines",
      "why:s.why||''" in U
      and "_said.nMedia=_said.lines.filter(l=>l.src==='media').length;" in U
      and U.index("_said.nMedia=") < U.index("saidMediaPaint();\n  saidWire(body);"))
i_paint = U.index("function saidMediaPaint(){")
paint = U[i_paint:U.index("function saidFilter(q){")]
check("saidMediaPaint: hidden without media, a count while folded, on when shown",
      "b.style.display=n?'':'none';" in paint
      and "b.classList.toggle('on',SAID_MEDIA);" in paint
      and "'<span class=\"n\">'+n+'</span>'" in paint
      and "n&&!SAID_MEDIA?" in paint)
check("the all-media empty row announces the fold",
      "Nobody in the room spoke here \\u2014 a video was playing. Press "
      "\\u25AD to read what it said." in U
      and "(_said.nMedia||0)===n" in U)
i_r = U.index("function saidRender(center){")
rend = U[i_r:U.index("function saidVisible(")]
check("saidRender: media rows get class media, the why detail, no g dressing",
      "const isMedia=ln.src==='media', isGame=ln.src==='game';" in rend
      and "if(isMedia){ r.classList.add('media');" in rend
      and "(ln.why==='mix>voice'?' (no game tap this night: could also be "
          "the game)':'')" in rend
      and rend.index("if(isMedia)") < rend.index("else if(isGame)")
      < rend.index("else if(ln.g)"))
check("...game rows get 'gml gl2' and the label 'the game'",
      "r.classList.add('gml','gl2');" in rend
      and "const lab=isMedia?'a video':(isGame?'the game':who);" in rend)
check("...neither gets a voice chip, a cluster number or a naming handle",
      "const who=(ln.g||isMedia||isGame)?null:" in rend
      and "const wn=(ln.g||isMedia||isGame)?null:snsWhoNumAt(ln.t);" in rend
      and "(wn&&!isMedia&&!isGame)?'swho':'swho unk'" in rend
      and "if(wn&&!isMedia&&!isGame)w.dataset.t=String(ln.t);" in rend)
check("...and snsWireWho ignores .swho.unk, so a label never opens naming",
      "if(!w||w.classList.contains('unk')||!V.cur)return;" in U)
check("the copy button keeps what is shown, prefixes, owns up",
      "const keep=segs.filter(s=>SAID_MEDIA||s.src!=='media');" in U
      and "(s.src==='media'?'[a video] ':(s.src==='game'?'[the game] ':''))"
          in U
      and "(left?' (the video\\u2019s '+left+' left out)':'')" in U)
check("#vsqm is wired once: toggles, persists, repaints, refilters, whispers",
      U.count("$('#vsqm').addEventListener('click'") == 1
      and "SAID_MEDIA=!SAID_MEDIA;" in U
      and "saidMediaPaint(); saidFilter(($('#vsq')&&$('#vsq').value)||'');"
          in U
      and "'the video\\u2019s lines are folded away'" in U)
check("lullCompute drops media lines after the fetch",
      "segs=segs.filter(s=>s.src!=='media');   /* a lull is" in U)
check("the mark tooltip's transcript drops them too",
      "segs=segs.filter(s=>s.src!=='media');   /* \"what was said here\"" in U)
check("library search labels a video's and the game's hits",
      "' · a video said this, not the room'" in U
      and "' · the game said this'" in U)
check("voiceBadges on the Contents rows, voiceText on both chapter heads",
      "const vb=voiceBadges(g); if(vb)r.append(vb);" in U
      and U.count("const vt=voiceText(g); if(vt)stats.push(esc(vt));") == 2)
check(".grow .gvoice chip CSS beside .gcount",
      ".grow .gvoice{" in U
      and U.index(".grow .gcount{") < U.index(".grow .gvoice{"))
i_b = U.index("function voiceBadges(g){")
badges = U[i_b:U.index("function renderContents(")]
check("voiceBadges: null without voices/nights; 'quiet' only after 2 nights",
      "const v=g&&g.voices; if(!v||!v.nights)return null;" in badges
      and "if(!any&&v.nights>=2)" in badges and "'quiet'" in badges)
check("the mock paints a badge, a no-badge and a never-by-source game",
      "voices:(gi%3===2)?null:{chat:gi%2?3:0,lines:gi%3===0?2:0,nights:3}," in U)
check("the mock transcript carries a media and a game row, in time order",
      "src:'media',why:'mix>voice'}" in U
      and "The enemy has slain your ally.',src:'game'}" in U
      and U.index("src:'media',why:'mix>voice'}") < U.index(
          "src:'game'}") < U.index("Okay, last play"))
# guards: every new read tolerates an older lore.py (no src, no voices,
# no why) - by construction each is a string compare against undefined or
# a null-guarded property walk
check("no new read dereferences src/voices/why without a guard",
      "g.voices." not in U.replace("g&&g.voices", "")
      and ".why===" in U and ".why." not in U)
check("the old 'S.showMedia' / 'lore.showmedia' design never landed (one toggle)",
      "S.showMedia" not in U and "lore.showmedia" not in U
      and "vsaidmed" not in U)

print("\n--- 3.31 stage D: the copy button on an all-video panel, the Game "
      "chip, the marks, the ribbon ---")
i_cp = U.index("$('#vsaidcopy').addEventListener('click'")
cp = U[i_cp:U.index("$('#vsqm').addEventListener('click'")]
check("nothing but a video shown: a whisper, no clipboard write",
      "if(!keep.length){whisper('nothing but a video to copy \\u2014 press "
      "the toggle to include it');return;}" in cp
      and cp.index("if(!keep.length)") < cp.index("const txt=keep.map("))
check("the Game chip sits after Scream, on by default, with a tip",
      '<button data-m="game" class="on" title="Bursts in the game itself' in U
      and U.index('data-m="scream"') < U.index('data-m="game"')
      < U.index('data-m="told"'))
check("MARKS carries game (default true), the save list and gsig know it",
      # 3.32 appends the outcome chip to every one of these lists
      "told:true, sense:true, game:true, outcome:true};" in U
      and "['gold','red','loud','laugh','scream','told','sense','game',"
          "'outcome'].forEach" in U
      and "const gsig=['loud','laugh','scream','told','sense','game',"
          "'outcome']" in U
      and "sense:'sense',game:'game',outcome:'outcome'};" in U)
check("stamp: a game mark hears 'a burst in the game', a room shout "
      "'a shout in the room', an old mark 'a loud moment'",
      ":ev.kind==='game'?'a burst in the game'" in U
      and ":(ev.src==='room'?'a shout in the room':'a loud moment');" in U
      and ":ev.kind==='game'?'game'" in U
      and "k==='game'?'game':k==='outcome'?'outcome':(SNSK[k]?'sense':'loud')"
      in U)
check("the game tick's CSS: short, dull, taller when told",
      '.hlmark[data-fk="game"]{background:#b7a37c;opacity:.5;height:4px;top:0}'
      in U and '.hlmark[data-fk="game"].told' not in U)   # a told mark wears data-fk 'told' - that rule was dead
check("both tip maps name the kind",
      U.count("game:'a burst in the game'") == 2)
i_dh = U.index("const drawHype=()=>{")
dh = U[i_dh:U.index("window.__hypePaint=")]
check("drawHype: a room curve draws its deviation, a flat night a baseline "
      "and a word, an old mix curve exactly as before",
      "const room=(_hype.src==='room');" in dh
      and "const dev=(room&&_hype.dev&&_hype.dev.length===n)?_hype.dev:null;"
      in dh
      and "if(room&&_hype.flat){" in dh
      and "'a calm night \\u2014 the room never rose'" in dh
      and "const lo=_hype.median||0,hi=Math.max(_hype._max||1,lo+0.05);" in dh
      and "Math.pow(Math.max(0,Math.min(1,(x-lo)/(hi-lo))),2.6)" in dh)
check("...peaks may be numbers or {t, why}; the cause is written when sparse",
      "const t=(typeof p==='number')?p:p.t;" in dh
      and "if(label&&p&&p.why){" in dh)
check("the click lands on a peak of either shape and says its cause",
      "const pt=(typeof p==='number')?p:(p&&p.t); if(pt==null)return;" in U
      and "whisper('landed on the flow at '+fmtT(Math.round(t))"
          "+(why?' \\u2014 '+why:''));" in U)
check("the ribbon's title names its source after a load",
      "hypeCv.title=(r.src==='room')" in U
      and "'how alive the ROOM was \\u2014 the voice chat and your mic, "
          "not the game'" in U
      and "'how alive the mix sounded (an older recording \\u2014 the game "
          "is in it)'" in U)
check("drawLevels' teal thread breaks across gated windows on a room curve "
      "only",
      "const gated=(_sns.hype.src==='room');" in U
      and "if(gated&&hv[i]<=0){started=false;continue;}" in U)
check("every new read is guarded (src compared, never dereferenced bare)",
      "_hype.src===" in U and "_sns.hype.src===" in U
      and "r.src===" in U and ".dev.length" in U)

print("\n--- checkui over the patched file ---")
r = subprocess.run(["node", os.path.join(ROOT, "qa", "checkui.js"), UI],
                   capture_output=True, text=True, encoding="utf-8")
print("  " + (r.stdout or "").strip())
check("every script block still parses", r.returncode == 0)

import shutil
shutil.rmtree(tmp, ignore_errors=True)
print("\n%d ok, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)

// every <script> block of the patched ui.html has to still parse
const fs = require('fs');
const p = process.argv[2];
const s = fs.readFileSync(p, 'utf8');
const re = /<script(\s[^>]*)?>([\s\S]*?)<\/script>/gi;
let m, n = 0, bad = 0;
while ((m = re.exec(s)) !== null) {
  const attrs = m[1] || '';
  if (/type\s*=\s*"(?!text\/javascript|module)/i.test(attrs)) continue;
  if (/\ssrc\s*=/i.test(attrs)) continue;
  n++;
  try { new Function(m[2]); }
  catch (e) {
    bad++;
    const upto = s.slice(0, m.index).split('\n').length;
    console.log('BLOCK ' + n + ' at line ' + upto + ': ' + e.message);
  }
}
console.log('script blocks parsed: ' + n + ', failures: ' + bad);
process.exit(bad ? 1 : 0);

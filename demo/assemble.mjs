// Builds the full video, the highlight cut, square and vertical versions, GIFs and the chapter list
// from the raw recordings in raw/ and the cards in cards/ (run make-cards.mjs first).
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { CHAPTERS, SHAPES } from './make-cards.mjs';

const OUT = process.env.MEDIA_OUT ?? '../dist-media';   // large files: not committed
const GIF_OUT = '../docs/assets/gifs';                   // small files: committed
const BG = '0x0e0e22', BEZEL = '0x2b2b4a';
fs.mkdirSync(OUT, { recursive: true }); fs.mkdirSync(GIF_OUT, { recursive: true }); fs.mkdirSync('build', { recursive: true });

const ff = (...args) => execFileSync('ffmpeg', ['-v', 'error', '-y', ...args], { stdio: 'inherit' });
const probe = (f) => {
  const [w, h, d] = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height:format=duration', '-of', 'csv=p=0:s=,', f])
    .toString().trim().split(/[,\n]/).map(Number);
  return { w, h, d };
};
const even = (n) => Math.round(n / 2) * 2;
const ENC = ['-c:v', 'libx264', '-crf', '22', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-r', '30', '-an', '-movflags', '+faststart'];

function fitFilter(clip, shape) {
  const [W, H] = SHAPES[shape];
  const { w, h } = probe(clip);
  if (Math.abs(w / h - W / H) < 0.01) return `fps=30,scale=${W}:${H}:flags=lanczos,format=yuv420p`;
  const m = 40, b = 8;
  const k = Math.min((W - 2 * m - 2 * b) / w, (H - 2 * m - 2 * b) / h);
  const ow = even(w * k), oh = even(h * k);
  return `fps=30,scale=${ow}:${oh}:flags=lanczos,pad=${ow + 2 * b}:${oh + 2 * b}:${b}:${b}:color=${BEZEL},pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=${BG},format=yuv420p`;
}

let n = 0;
function segment(clip, shape, { start = 0, dur, speed = 1 } = {}) {
  const out = `build/seg-${shape}-${n++}.mp4`;
  const ss = start ? ['-ss', String(start)] : [];
  const t = dur ? ['-t', String(dur)] : [];
  ff(...ss, ...t, '-i', clip, '-vf', `${fitFilter(clip, shape)}${speed !== 1 ? `,setpts=PTS/${speed}` : ''}`, ...ENC, out);
  return out;
}
function card(name, shape, secs) {
  const out = `build/card-${name}-${shape}-${n++}.mp4`;
  ff('-loop', '1', '-t', String(secs), '-i', `cards/${name}-${shape}.png`, '-vf', 'fps=30,format=yuv420p', ...ENC, out);
  return out;
}
function concat(parts, out) {
  fs.writeFileSync('build/list.txt', parts.map((p) => `file '${p.replace(/^build\//, '')}'`).join('\n'));
  ff('-f', 'concat', '-safe', '0', '-i', 'build/list.txt', '-c', 'copy', '-movflags', '+faststart', out);
  console.log('wrote', out, `${(fs.statSync(out).size / 1e6).toFixed(1)} MB`);
}
const raw = (id) => `raw/${id}.webm`;

// ---------- full video (chapters) + chapters list
function full(shape) {
  const parts = [card('intro', shape, 3.5)];
  const marks = [{ t: 0, title: 'Intro' }];
  let t = 3.5;
  for (const c of CHAPTERS) {
    parts.push(card(c.id, shape, 2.5)); marks.push({ t, title: c.title }); t += 2.5;
    parts.push(segment(raw(c.id), shape)); t += probe(raw(c.id)).d;
  }
  parts.push(card('outro', shape, 6)); marks.push({ t, title: 'Credits' });
  concat(parts, `${OUT}/ParkWise-full-${shape}.mp4`);
  return marks;
}

// ---------- highlight: [clip, start, duration, speed]
const HIGHLIGHT = JSON.parse(fs.readFileSync('media-plan.json', 'utf8')).highlight;
function highlight(shape) {
  const parts = [card('intro', shape, 2.5)];
  for (const [id, start, dur, speed = 1] of HIGHLIGHT) parts.push(segment(raw(id), shape, { start, dur, speed }));
  parts.push(card('outro', shape, 4));
  concat(parts, `${OUT}/ParkWise-highlight-${shape}.mp4`);
}

// ---------- GIFs: [name, clip, start, duration, width, fps, speed]
function gif([name, id, start, dur, width, fps, speed = 1]) {
  const pal = `build/pal-${name}.png`;
  const vf = `setpts=PTS/${speed},fps=${fps},scale=${width}:-1:flags=lanczos`;
  ff('-ss', String(start), '-t', String(dur), '-i', raw(id), '-vf', `${vf},palettegen=max_colors=96:stats_mode=diff`, pal);
  const out = `${GIF_OUT}/${name}.gif`;
  ff('-ss', String(start), '-t', String(dur), '-i', raw(id), '-i', pal, '-lavfi', `${vf}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4`, out);
  console.log('wrote', out, `${(fs.statSync(out).size / 1e6).toFixed(1)} MB`);
}

const plan = JSON.parse(fs.readFileSync('media-plan.json', 'utf8'));
const what = process.argv[2] ?? 'all';
if (what === 'gifs' || what === 'all') plan.gifs.forEach(gif);
if (what === 'highlight' || what === 'all') for (const s of Object.keys(SHAPES)) highlight(s);
if (what === 'full' || what === 'all') {
  const marks = full('wide');
  const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  fs.writeFileSync(`${OUT}/chapters.txt`, marks.map((m) => `${fmt(m.t)} ${m.title}`).join('\n') + '\n');
  console.log(fs.readFileSync(`${OUT}/chapters.txt`, 'utf8'));
}

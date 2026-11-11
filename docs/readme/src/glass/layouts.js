// bwtidy in Glass: every composition of the README. The windows show real output of the scripts on
// the synthetic vault in examples/ (see scripts/readme_visuals.py). The accent light is teal, the
// colour of "Nothing was changed".
import { lights, term, doc, lift, hero, heroPhone, panel, panelPhone, band, bandPhone, social, replay } from './grammar.js';

const A = { ray: '#b2e8de', pool: '#12907f', deep: '#0f3a35', lift: '#1aa894', top: '#0a0d10', haze: '#17201f', fog: '#0a0d0f',
  mote: '#dcfff6', day: '#f0f4f3', shade: '#eaefee', dayFog: '#f0f4f3' };
const L = lights(A);

export function build(M) {
  const F = M.facts;
  const dk = (n) => (n ? '#0B0E14' : '#F7F7F5');
  const au = M.audit, cut = au.lift.fromurl[1] - 30;
  const top = [0, 0, au.w, au.lift.weak[1] - 40], tail = [0, cut, au.w, au.h - cut];
  const HERO = {
    name: 'bwtidy', h: 600, hp: 640,
    // the loop: the audit is run, its report goes by and stops on the summary the window shows
    replay: replay(au, { frames: 96, view: [cut, au.h - cut], page: 0.5, burst: 2, calm: 12, pause: 0 }),
    line: 'A local audit and cleanup for Bitwarden and Vaultwarden, with an undo for every change.',
    linePhone: 'A local audit and cleanup for Bitwarden<br>and Vaultwarden, with an undo for every change.',
    win: (n, ph) => {
      const P = ph
        ? { s: { x: 84, y: 262, w: 150, z: -420, rot: [4, 28, 0] }, d: { x: 298, y: 262, w: 130, z: -420, rot: [4, -28, 0] }, m: { x: 190.5, y: 396, w: 320, z: 0, rot: [3, 0, 0] } }
        : { s: { x: 172, y: 316, w: 250, z: -420, rot: [4, 28, 0] }, d: { x: 670, y: 326, w: 220, z: -420, rot: [4, -28, 0] }, m: { x: 420, y: 380, w: 420, z: 0, rot: [3, 0, 0] } };
      const far = { fog: n ? 0.42 : 0.30, lod: 0.8, defocus: 1.6, breathe: [14, 0.15] };
      return [
        term(M, 'tidy', P.s, n, A, { ...far }),
        doc(M, 'cleanup', P.d, n, A, { ...far, breathe: [14, 0.7] }),
        term(M, 'audit', P.m, n, A, { play: true, crop: tail, breathe: [10, 0.4], bezel: 10, glow: 0.75 }),
        lift(M, 2, 'audit', 'key', n, A, { lift: ph ? 60 : 96, grow: ph ? 1.0 : 1.06, breathe: [12, 0.85], shift: [0, ph ? 8 : 12] }),
      ];
    },
  };
  const AUDIT = {
    kick: 'Audit', head: 'Know what to fix first',
    body: '<code>bwaudit.py</code> reads the whole vault and ranks what it finds: reused passwords in groups, weak ones, critical accounts without 2FA, logins with no website. It writes nothing and never prints a password.',
    win: (n, ph) => {
      const P = ph ? { a: { x: 160, y: 390, w: 250, z: -90, rot: [2, -12, 0] }, b: { x: 246, y: 470, w: 250, z: 60, rot: [0, -12, 0] } }
        : { a: { x: 552, y: 198, w: 320, z: -100, rot: [2, -18, 0] }, b: { x: 652, y: 328, w: 264, z: 50, rot: [0, -12, 0] } };
      return [
        term(M, 'audit', P.a, n, A, { crop: top, breathe: [8, 0.0] }),
        term(M, 'dupes', P.b, n, A, { breathe: [8, 0.45] }),
        lift(M, 0, 'audit', 'group', n, A, { lift: 170, shift: [ph ? 50 : -22, 4] }),
      ];
    },
  };
  const DEAD = {
    kick: 'Clean-up', head: 'Find the dead weight', hp: 612, dyp: 10,
    body: '<code>bwdead.py</code> writes a ranked checklist with the evidence for every entry: exact duplicates first, then domains that no longer resolve. It deletes nothing; you tick through it in the Bitwarden app.',
    win: (n, ph) => {
      const P = ph ? { a: { x: 156, y: 394, w: 240, z: -90, rot: [2, -12, 0] }, b: { x: 232, y: 486, w: 280, z: 60, rot: [0, -12, 0] } }
        : { a: { x: 548, y: 224, w: 244, z: -110, rot: [2, -18, 0] }, b: { x: 656, y: 332, w: 300, z: 50, rot: [0, -12, 0] } };
      return [
        doc(M, 'cleanup', P.a, n, A, { breathe: [8, 0.0] }),
        term(M, 'dead', P.b, n, A, { breathe: [8, 0.45] }),
        lift(M, 1, 'dead', 'key', n, A, { lift: 80, shift: [ph ? 0 : -24, 0] }),
      ];
    },
  };
  const MERGE = {
    kick: 'Merge', head: 'Merge duplicates without losing a byte', cw: 300,
    body: '<code>bwmerge.py</code> folds entries that are provably one account into one, after an owner-only backup, and trashes rather than purges. <code>bwpolish.py</code> then proves every URL, TOTP seed and note survived.',
    win: (n, ph) => {
      const P = ph ? { a: { x: 164, y: 384, w: 250, z: -90, rot: [2, -12, 0] }, b: { x: 226, y: 484, w: 280, z: 60, rot: [0, -12, 0] } }
        : { a: { x: 552, y: 206, w: 300, z: -110, rot: [2, -18, 0] }, b: { x: 660, y: 330, w: 290, z: 50, rot: [0, -12, 0] } };
      return [
        term(M, 'merge', P.a, n, A, { breathe: [8, 0.0] }),
        term(M, 'polish', P.b, n, A, { breathe: [8, 0.45] }),
        lift(M, 1, 'polish', 'key', n, A, { lift: 80, shift: [ph ? 0 : -30, 0] }),
      ];
    },
  };
  const FOLDERS = {
    kick: 'Local model', head: 'A local model sorts the folders',
    body: '<code>bwtidy.py</code> asks a model in LM Studio on your own machine to file each item in one of 16 folders. It sees four fields and never a secret, its reply must match a JSON schema, and you review the plan first.',
    win: (n, ph) => {
      const P = ph ? { a: { x: 170, y: 384, w: 290, z: -90, rot: [2, -12, 0] }, b: { x: 236, y: 486, w: 240, z: 60, rot: [0, -12, 0] } }
        : { a: { x: 560, y: 196, w: 330, z: -110, rot: [2, -18, 0] }, b: { x: 676, y: 330, w: 250, z: 50, rot: [0, -12, 0] } };
      return [
        doc(M, 'request', P.a, n, A, { breathe: [8, 0.0] }),
        term(M, 'plan', P.b, n, A, { breathe: [8, 0.45] }),
        lift(M, 0, n ? 'request' : 'request-light', 'key', n, A, { lift: 80, pad: 0, radius: 12, key: n ? '#11151D' : '#ECECEA', keyAmt: n ? 0.7 : 0.8, shift: [ph ? 0 : -30, -4] }),
      ];
    },
  };
  const UNDO = {
    kick: 'Undo', head: 'Every change has an undo',
    body: 'Every writing script plans first and applies only when you say so. <code>verify</code> proves each credential is byte-identical, <code>revert</code> puts items back, and a model that is not on loopback is refused.',
    win: (n, ph) => {
      const P = ph ? { a: { x: 194, y: 390, w: 296, z: -80, rot: [2, -12, 0] }, b: { x: 214, y: 482, w: 300, z: 60, rot: [0, -10, 0] } }
        : { a: { x: 572, y: 208, w: 360, z: -100, rot: [2, -18, 0] }, b: { x: 650, y: 326, w: 320, z: 50, rot: [0, -12, 0] } };
      return [
        term(M, 'tidy', P.a, n, A, { breathe: [8, 0.0] }),
        term(M, 'guard', P.b, n, A, { breathe: [8, 0.45] }),
        lift(M, 0, 'tidy', 'key', n, A, { lift: 90, shift: [ph ? 0 : -30, 0] }),
      ];
    },
  };
  const FACTS = { glow: A.deep, hi: '#6fe6d8', hiDay: '#0b7d72', facts: [
    [String(F.scripts), 'scripts, one job each'],
    [String(F.tests), 'end-to-end tests on a synthetic vault'],
    [String(F.deps), 'dependencies: standard library and the bw CLI'],
    ['0', 'secrets ever sent to the model, checked by a test', true],
  ] };
  // social preview: the hero's main window and its lifted line at the right, one page behind it
  const socialWin = (n) => { const w = HERO.win(n, false); return [
    { ...w[1], x: 590, y: 150, w: 128, z: -320, rot: [3, -26, 0] },
    { ...w[2], x: 456, y: 162, w: 236, z: 0, rot: [2, -12, 0] },
    { ...w[3], parent: 1, lift: 70, shift: [-10, 0] }]; };
  return {
    hero: hero(HERO, L), 'hero-phone': heroPhone(HERO, L),
    numbers: band(FACTS, L), 'numbers-phone': bandPhone(FACTS, L),
    audit: panel(AUDIT, L), 'audit-phone': panelPhone(AUDIT, L),
    dead: panel(DEAD, L), 'dead-phone': panelPhone(DEAD, L),
    merge: panel(MERGE, L), 'merge-phone': panelPhone(MERGE, L),
    folders: panel(FOLDERS, L), 'folders-phone': panelPhone(FOLDERS, L),
    undo: panel(UNDO, L), 'undo-phone': panelPhone(UNDO, L),
    social: social({ kick: 'CLI · Python', name: 'bwtidy',
      line: 'A local audit and cleanup for Bitwarden and Vaultwarden, with an undo for every change.', win: socialWin }, L),
  };
}

"""
The README scenes: each image is one moment of the tidy-up, on the key board.

Every vault item is drawn as the same key in every scene. Its look comes from
the real audit output: items in one reused-password group share a bitting and
a stamp, weak passwords are flimsy keys, critical logins without TOTP have a
lock missing its second bolt, logins without a URL carry a blank address tag,
and stale entries collect a cobweb. Names, counts and terminal text are the
captured output of the real scripts on the synthetic vault.
"""

import json
import os
import re

from readme_kit import (Board, bin_can, bolts, box, cabinet, chore_tick, cobweb, dymo, esc, fob, hung,
                        key, page, pencil_arrow, plate, rail, string_path, svg_tag, tag, undo_tag, wobble)

WORKDIR = "~/bwtidy-work"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ==========================================================================
# terminal colouring (unchanged rules, new palette in readme_kit.CSS)
# ==========================================================================

TOKENS = re.compile(r"""
  (?P<crit><<\ includes\ a\ critical\ account)
| (?P<fail>FAIL:|Refusing\ to\ send\ vault\ metadata\ to)
| (?P<pass>PASS:)
| (?P<url>https?://[^\s'",)]+)
| (?P<user>\[[^\]\s]*@[^\]\s]*\])
| (?P<folder>\[(?:No\ Folder|[A-Z][\w&]*(?:\ [\w&]+)*)\])
| (?P<file>\b(?:backup-[\w-]+|plan|fingerprint|merge_plan|cleanup|bwtidy)\.(?:json|md)\b)
| (?P<cmd>python3\ bw\w+\.py(?:\ (?:plan|apply|verify|revert|restore))?)
| (?P<arrow>->|<-)
| (?P<del>trashed:)
| (?P<ok>merged\ into:|absorbs:|every\ (?:URL|TOTP\ seed|note)\ preserved
        |Nothing\ was\ (?:changed|deleted)\.|No\ data\ was\ lost\ in\ the\ merge\.)
| (?P<mode>-rw-------)
""", re.X)

CLASS = {"crit": "w", "fail": "w", "pass": "g b", "url": "u", "user": "us",
         "folder": "f", "file": "k", "cmd": "c", "arrow": "a", "del": "r",
         "ok": "g", "mode": "g"}


def tokens(text):
    out, pos = [], 0
    for m in TOKENS.finditer(text):
        out.append(esc(text[pos:m.start()]))
        out.append(f'<span class="{CLASS[m.lastgroup]}">{esc(m.group())}</span>')
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def color_line(line):
    if re.fullmatch(r"=+", line):
        return f'<span class="rule">{line}</span>'
    if line == "⋮":
        return '<span class="ell">⋮</span>'
    m = re.match(r"^([A-Z][A-Z0-9 +\-/,&]*[A-Z0-9+])(?=\s|$|:)(.*)$", line)
    if m and len(m.group(1)) >= 4 and not line.startswith(("PASS", "FAIL")):
        rest = re.sub(r"(\d+)", r'<span class="n">\1</span>', tokens(m.group(2)))
        return f'<span class="h">{esc(m.group(1))}</span><span class="m">{rest}</span>'
    m = re.match(r"^(  )([A-E])(\s+)(\d+)(\s+)(.*)$", line)
    if m:
        return (f'{m.group(1)}<span class="tier">{m.group(2)}</span>{m.group(3)}'
                f'<span class="b">{m.group(4)}</span>{m.group(5)}<span class="h2">{esc(m.group(6))}</span>')
    m = re.match(r"^(\s+)(\d+ chars, \d class\(es\)|[\d.]+ yrs)(.*)$", line)
    if m:
        return f'{m.group(1)}<span class="w">{m.group(2)}</span>{tokens(m.group(3))}'
    m = re.match(r"^(\d+ item\(s\) flagged\.|\d+ items, \d+ flagged|\d+ -> \d+ items\.|"
                 r"\d+ of \d+ items would move:|\d+ merge\(s\), \d+ item\(s\) in trash\.|"
                 r"Moved \d+ items\.|Reverted \d+ item\(s\)\.|Scanned \d+ items)(.*)$", line)
    if m:
        return f'<span class="b">{tokens(m.group(1))}</span>{tokens(m.group(2))}'
    m = re.match(r"^(\s+Group \d+ - \d+ entries)(.*)$", line)
    if m:
        return f'<span class="h2">{esc(m.group(1))}</span>{tokens(m.group(2))}'
    m = re.match(r"^(\s+)(\d+)(  )(\w.*)$", line)          # bwtidy plan counts
    if m:
        return f'{m.group(1)}<span class="n">{m.group(2)}</span>{m.group(3)}<span class="f">{esc(m.group(4))}</span>'
    if line.startswith(("Fix top-down", "Length matters", "Bitwarden can store",
                        "Add the login URL", "Age alone", "No password is printed",
                        "Highest value first", "  (not merged on purpose", "  classifying",
                        "resolving ", "(no DNS check", "Recreated items")):
        return f'<span class="m">{tokens(line)}</span>'
    return tokens(line)


def prompt(command, first):
    cmd = f' <span class="pc">{esc(command)}</span>' if command else ' <span class="cur"> </span>'
    return (f'<span class="{"pr" if first else "pr gap"}"><span class="pp">{WORKDIR}</span> '
            f'<span class="pd">$</span>{cmd}</span>')


def term(blocks, cursor=False):
    """blocks: list of ("$", command) or ("out", text). Returns the <pre> body."""
    rows = []
    for kind, text in blocks:
        if kind == "$":
            rows.append(prompt(text, not rows))
        else:
            rows += [color_line(ln) for ln in text.split("\n")]
    if cursor:
        rows.append(prompt("", not rows))
    return "\n".join(rows)


# ==========================================================================
# the vault, read back from the captured output
# ==========================================================================

class Vault:
    """What the scenes know about each item, parsed from the real reports."""

    def __init__(self, cap):
        a = cap["audit"]
        self.groups = []                 # reused-password groups, in report order
        cur = None
        for ln in a.splitlines():
            if re.match(r"^\s+Group \d+ - ", ln):
                cur = {"names": [], "critical": "critical account" in ln}
                self.groups.append(cur)
            elif cur is not None and re.match(r"^      \S", ln):
                cur["names"].append(re.match(r"^\s+(.+?)\s+\[", ln).group(1))
            elif ln.startswith("="):
                cur = None
        self.group_of = {n: i + 1 for i, g in enumerate(self.groups) for n in g["names"]}
        self.weak = {m.group(3): (int(m.group(1)), int(m.group(2))) for m in
                     re.finditer(r"^\s+(\d+) chars, (\d) class\(es\)  (.+?)\s+\[", a, re.M)}
        self.no2fa = self._section(a, "NO SECOND FACTOR")
        self.nourl = self._section(a, "NO WEBSITE SET")
        self.stale = {m.group(2): m.group(1) for m in re.finditer(r"^\s+([\d.]+) yrs  (.+?)\s+\[", a, re.M)}
        self.flagged = int(re.search(r"^(\d+) item\(s\) flagged", a, re.M).group(1))
        self.scanned = int(re.search(r"Scanned (\d+) items", a).group(1))
        with open(os.path.join(ROOT, "examples", "sample-vault.json")) as fh:
            items = json.load(fh)["items"]
        self.totp = {i["name"] for i in items if (i.get("login") or {}).get("totp")}

    @staticmethod
    def _section(text, title):
        out, on = [], False
        for ln in text.splitlines():
            if ln.startswith(title):
                on = True
            elif on and ln.startswith("=") and out:
                break
            elif on and re.match(r"^  \S", ln):
                out.append(re.match(r"^  (.+?)\s+\[", ln).group(1))
        return out

    def cuts(self, name):
        seed = f"group{self.group_of[name]}" if name in self.group_of else name
        return tuple(1 + int(wobble(seed + str(i), 0, 3.99)) for i in range(5))

    def key(self, name, **kw):
        stamp = str(self.group_of[name]) if name in self.group_of else ""
        return key(self.cuts(name), stamp=stamp, flimsy=name in self.weak, **kw)


# ==========================================================================
# shared pieces
# ==========================================================================

def headline(x, y, text, size, width, extra=""):
    return f'<div class="abs h1" style="left:{x}px;top:{y}px;font-size:{size}px;width:{width}px;{extra}">{text}</div>'


def lede(x, y, text, size, width, extra=""):
    return f'<div class="abs lede" style="left:{x}px;top:{y}px;font-size:{size}px;width:{width}px;{extra}">{text}</div>'


def note(x, y, text, size=17, rot=0, width=None, extra=""):
    w = f"width:{width}px;" if width else "white-space:nowrap;"
    return (f'<div class="note hand" style="left:{x}px;top:{y}px;font-size:{size}px;{w}'
            f'transform:rotate({rot}deg);transform-origin:0 0;{extra}">{text}</div>')


def brand(x, y, size=24, rot=-2):
    return dymo(x, y, "bwtidy", size, rot=rot, center=False, jitter=True)


def hang(b, v, name, x, y, scale, angle=0.0, label=True, label_size=12, extra_keys=(), spread=0.0):
    """Hang one item's key at (x, y). Returns the string anchor (ring bottom)."""
    keys = [(v.key(name), -spread / 2 if extra_keys else 0)]
    for k in extra_keys:
        keys.append((v.key(k), spread / 2))
    b.mid.append(hung(x, y, scale, keys, angle=angle))
    return x + 2 * scale, y + 20 * scale


def scene(width, height, board, radius=None):
    return cabinet(width, height, board.html(), radius=radius)


# ==========================================================================
# scenes
# ==========================================================================

def headline(x, y, text, size, width, extra=""):
    return f'<div class="abs h1" style="left:{x}px;top:{y}px;font-size:{size}px;width:{width}px;{extra}">{text}</div>'


def lede(x, y, text, size, width, extra=""):
    return f'<div class="abs lede" style="left:{x}px;top:{y}px;font-size:{size}px;width:{width}px;{extra}">{text}</div>'


def note(x, y, text, size=17, rot=0, width=None, extra=""):
    w = f"width:{width}px;" if width else "white-space:nowrap;"
    return (f'<div class="note hand" style="left:{x}px;top:{y}px;font-size:{size}px;{w}'
            f'transform:rotate({rot}deg);transform-origin:0 0;{extra}">{text}</div>')


def mono(text, size=None):
    sz = f"font-size:{size}px;" if size else ""
    return f'<span class="mono" style="font-style:normal;font-weight:600;{sz}">{esc(text)}</span>'


def brand(x, y, size=24, rot=-2):
    return dymo(x, y, "bwtidy", size, rot=rot, center=False, jitter=True)


def hang(b, v, name, x, y, scale, angle=0.0, extra_keys=(), spread=0.0):
    """Hang one item's key (plus any extra keys on the same ring) at (x, y)."""
    keys = [(v.key(name), -spread / 2 if extra_keys else 0)]
    for k in extra_keys:
        keys.append((v.key(k), spread / 2))
    b.mid.append(hung(x, y, scale, keys, angle=angle))
    return x + 2 * scale, y + 20 * scale


def scene(width, height, board, radius=None):
    return cabinet(width, height, board.html(), radius=radius)


def the_pair(v):
    """The hero's story: the critical login that shares a cut with a long-dead one."""
    crit = next(g for g in v.groups if g["critical"])["names"]
    stale = next((n for n in crit if n in v.stale), crit[-1])
    other = next(n for n in crit if n != stale)
    return stale, other


def same_cut_pair(b, v, c1, c2, r, S, label=13, note_size=18, tag_size=15, rail_x=None, rail_w=None, long_tag=True):
    stale, crit = the_pair(v)
    if rail_x is not None:
        b.base.append(rail(rail_x, r - 52, rail_w))
    b.base.append(dymo(c1, r - 46, stale, label, rot=-1.2))
    b.base.append(dymo(c2, r - 46, crit, label))
    sx, sy = hang(b, v, stale, c1, r, S, angle=2)
    px, py = hang(b, v, crit, c2, r, S, angle=-2)
    b.back.append(cobweb(c1 + 3.5 * S, r - 22, 29 * min(S, 2.0)))
    if crit in v.no2fa:
        b.mid.append(bolts(c2 + 37 * S, r + 35 * S, (True, False), .76 * S))
    yrs = v.stale.get(stale)
    if yrs:
        b.back.append(string_path(sx, sy, c1 + 20 * S, r + 82 * S, sag=4))
        b.over.append(tag(c1 + 20 * S, r + 82 * S, f"{yrs} yrs untouched" if long_tag else f"{yrs} yrs", tag_size, rot=-8))
    if crit in v.weak:
        b.back.append(string_path(px, py, c2 + 13 * S, r + 88 * S, sag=4))
        b.over.append(tag(c2 + 13 * S, r + 88 * S, f"{v.weak[crit][0]} chars", tag_size, rot=-10))
    b.front.append(pencil_arrow(c1 + 21 * S, r + 47 * S, c2 - 21 * S, r + 47 * S, bend=-15 * S, both=True, width=1.1 * S ** .5 * 1.4))
    b.top.append(note((c1 + c2) / 2 - note_size * 2.1, r + 52 * S, "same cut", note_size, rot=-3))


def hero(cap, f, v):
    W, H = 1100, 660
    b = Board(W - 28, H - 28)
    c1, c2, r1, r2, S = 712, 942, 104, 392, 1.72
    same_cut_pair(b, v, c1, c2, r1, S, rail_x=590, rail_w=452)
    # row 2: a duplicate on one ring, and a lock missing its second bolt
    m = cap["merge_json"]["merges"][0]
    keep, copy = m["keep_name"], m["drop"][0]["name"]
    stale, crit = the_pair(v)
    lonely = next(n for n in v.no2fa if n != crit)
    b.base.append(rail(590, r2 - 52, 452))
    b.base.append(dymo(c1, r2 - 46, keep, 13))
    b.base.append(dymo(c2, r2 - 46, lonely, 13, rot=.8))
    hang(b, v, keep, c1, r2, S, extra_keys=[copy], spread=18)
    hang(b, v, lonely, c2, r2, S, angle=-2)
    b.mid.append(bolts(c1 + 70, r2 + 60, (True, keep in v.totp), 1.3))
    b.mid.append(bolts(c2 + 64, r2 + 60, (True, lonely in v.totp), 1.3))
    if keep in v.totp:
        b.top.append(note(c1 + 88, r2 + 38, "both bolts:<br>has 2FA", 14.5, rot=-3))
    b.back.append(string_path(c1 + 3, r2 + 34, c1 + 42, r2 + 172, sag=4))
    b.over.append(tag(c1 + 42, r2 + 172, "exact duplicate", 15, rot=-6))
    b.top.append(note(c2 + 40, r2 + 112, "no 2nd<br>bolt", 16, rot=-4))
    b.front.append(pencil_arrow(c2 + 74, r2 + 110, c2 + 72, r2 + 88, bend=6, head=7))
    # the words
    b.top.append(brand(54, 50, 24))
    b.top.append(headline(50, 108, "Every key back<br>on its hook.", 70, 540))
    b.top.append(lede(54, 274, "Audit and tidy a Bitwarden or Vaultwarden vault on your own machine. "
                      "Read every plan before it runs, and undo any change.", 20, 452))
    audit = cap["audit"].split("\n")
    body = term([("$", "python3 bwaudit.py"), ("out", "\n".join(audit[:2] + ["⋮", audit[-2]]))])
    b.top.append(plate(54, 424, 468, "bwaudit.py", body, fs=12.6, tail="read-only"))
    return W, H, scene(W, H, b)


def hero_mobile(cap, f, v):
    W, H = 540, 820
    b = Board(W - 28, H - 28)
    b.top.append(brand(30, 32, 21))
    b.top.append(headline(28, 84, "Every key back<br>on its hook.", 54, 480))
    b.top.append(lede(30, 214, "Audit and tidy a Bitwarden or Vaultwarden vault on your own machine. "
                      "Read every plan first. Undo any change.", 17.5, 450))
    same_cut_pair(b, v, 150, 362, 390, 1.62, label=12.5, note_size=17, tag_size=14.5, rail_x=40, rail_w=432, long_tag=False)
    audit = cap["audit"].split("\n")
    body = term([("$", "python3 bwaudit.py"), ("out", "\n".join(audit[:1] + ["⋮", audit[-2]]))])
    b.top.append(plate(26, 628, 460, "bwaudit.py", body, fs=11.4, tail="read-only", wrap=True))
    return W, H, scene(W, H, b)


# ------------------------------------------------------------- numbers --
def stats(f):
    return [
        (str(f["scripts"]), "SCRIPTS", "one job each", False),
        (str(f["checks"]), "HEALTH CHECKS", "before any change", False),
        (str(f["tests"]), "TESTS PASSING", "end to end, on a synthetic vault", False),
        (str(f["deps"]), "DEPENDENCIES", "standard library only", True),
        ("0", "SECRETS SENT", "to the local model", True),
        ("0", "CALLS OUT", "off the machine, proven by a test", True),
    ]


def numbers(cap, f, v):
    W, H = 1100, 356
    b = Board(W - 28, H - 28)
    b.base.append(rail(40, 30, W - 28 - 80))
    st = stats(f)
    x0, step = 112, 166
    for i, (num, word, cap_, mint) in enumerate(st):
        x = x0 + i * step
        if i == len(st) - 1:
            b.back.append(svg_tag(x + 26, 122, "do not disturb", 12.5, rot=56))
        b.mid.append(fob(x, 80, num, word, mint=mint, rot=wobble(word, -5, 5)))
        b.top.append(f'<div class="abs" style="left:{x - 78:.0f}px;top:264px;width:156px;text-align:center">'
                     f'<div class="note hand" style="position:static;font-size:16px;line-height:1.2">{esc(cap_)}</div></div>')
    return W, H, scene(W, H, b)


def numbers_mobile(cap, f, v):
    W, H = 540, 884
    b = Board(W - 28, H - 28)
    st = stats(f)
    for row in range(3):
        y = 26 + row * 272
        b.base.append(rail(40, y, W - 28 - 80))
        for col in range(2):
            i = row * 2 + col
            num, word, cap_, mint = st[i]
            x = 142 + col * 228
            if i == len(st) - 1:
                b.back.append(svg_tag(x + 26, y + 92, "do not disturb", 12, rot=58))
            b.mid.append(fob(x, y + 50, num, word, mint=mint, rot=wobble(word, -5, 5)))
            b.top.append(f'<div class="abs" style="left:{x - 100:.0f}px;top:{y + 232}px;width:200px;text-align:center">'
                         f'<div class="note hand" style="position:static;font-size:16px;line-height:1.2">{esc(cap_)}</div></div>')
    return W, H, scene(W, H, b)


# --------------------------------------------------------------- audit --
SPECIMENS = [
    # (kind, title in the friend's voice, the report's own section, the report's own hint)
    ("reused", "One key, many doors", "Reused passwords", "Fix top-down. Breaking one of these breaks every entry in its group."),
    ("weak", "Flimsy keys", "Weak passwords", "Length matters more than symbols. Regenerate these at 20+ chars."),
    ("no2fa", "No second bolt", "No 2FA on a critical account", "Bitwarden can store the TOTP seed itself."),
    ("nourl", "A key to no door", "No website, so no autofill", "Add the login URL to each so the browser extension offers to fill it."),
    ("stale", "Cobwebs", "Untouched for 3+ years", "Age alone is not a problem. Worth a look for dead accounts to delete."),
]


def specimen_art(b, kind, v, x, y):
    """Draw one finding as it looks on the board, hook at (x, y)."""
    if kind == "reused":
        pair = v.groups[0]["names"]
        b.mid.append(hung(x - 26, y, 1.0, [(v.key(pair[0]), 0)], angle=3))
        b.mid.append(hung(x + 30, y, 1.0, [(v.key(pair[1]), 0)], angle=-3))
    elif kind == "weak":
        b.mid.append(hung(x, y, 1.12, [(v.key(next(iter(v.weak))), 0)], angle=-2))
    elif kind == "no2fa":
        name = v.no2fa[0]
        b.mid.append(hung(x - 18, y, 1.0, [(v.key(name), 0)], angle=2))
        b.mid.append(bolts(x + 30, y + 50, (True, name in v.totp), 1.4))
    elif kind == "nourl":
        name = v.nourl[-1]
        b.mid.append(hung(x - 22, y, 1.0, [(v.key(name), 0)], angle=2))
        b.back.append(string_path(x - 20, y + 20, x - 6, y + 104, sag=4))
        b.over.append(tag(x - 6, y + 104, "https://&thinsp;<span style='display:inline-block;width:2.2em;"
                          "border-bottom:1.3px solid currentColor;transform:translateY(-.15em)'></span>", 12, rot=4))
    elif kind == "stale":
        b.mid.append(hung(x, y, 1.0, [(v.key(next(iter(v.stale))), 0)], angle=1))
        b.back.append(cobweb(x + 3.5, y - 13, 34))


def specimen_text(x, y, width, title, label, count, hint, size=21):
    return (f'<div class="abs" style="left:{x}px;top:{y:.0f}px;width:{width}px">'
            f'<div class="casual" style="font-weight:820;font-size:{size}px;letter-spacing:-.02em;color:var(--s900)">{title}</div>'
            f'<div style="margin-top:4px;font-weight:600;font-size:14px;color:#24493d"><span style="white-space:nowrap">{label}</span>'
            f' <span class="mono" style="display:inline-block;white-space:nowrap;margin-left:2px;font-weight:700;color:var(--s900);'
            f'background:rgba(255,255,255,.5);border-radius:4px;padding:0 .4em">{count}</span></div>'
            f'<div class="hand" style="margin-top:6px;font-size:14px;line-height:1.32;color:#3b564d">&ldquo;{esc(hint)}&rdquo;</div></div>')


def counts(v):
    return {"reused": f'{len(v.groups)} groups, {sum(len(g["names"]) for g in v.groups)} entries',
            "weak": str(len(v.weak)), "no2fa": str(len(v.no2fa)), "nourl": str(len(v.nourl)),
            "stale": str(len(v.stale))}


def audit(cap, f, v):
    W = 1100
    lines = cap["audit"].split("\n")
    fs, lh = 11.2, 1.5
    H = int(max(32 + 30 + (len(lines) + 4) * fs * lh + 90, 1040))
    b = Board(W - 28, H - 28)
    b.top.append(headline(42, 40, f"{v.flagged} findings.<br>Zero judgement.", 50, 420))
    b.top.append(lede(44, 156, f"{mono('bwaudit.py')} reads the whole vault, writes nothing and never prints a password. "
                      "Here is what each finding looks like on the board.", 16.5, 380))
    c = counts(v)
    y0 = 300
    step = (H - 28 - y0 - 10) / len(SPECIMENS)
    for i, (kind, title, label, hint) in enumerate(SPECIMENS):
        y = y0 + i * step
        specimen_art(b, kind, v, 96, y + 6)
        b.top.append(specimen_text(190, y - 6, 236, title, label, c[kind], hint))
        if i:
            b.top.append(f'<div class="abs" style="left:44px;top:{y - 26:.0f}px;width:382px;border-top:1.5px dashed rgba(31,84,66,.28)"></div>')
    body = term([("$", "python3 bwaudit.py"), ("out", cap["audit"])], cursor=True)
    b.top.append(plate(452, 30, 592, f"bwaudit.py — {WORKDIR}", body, fs=fs, lh=lh, wrap=True, tail="read-only"))
    return W, H, scene(W, H, b)


def audit_mobile(cap, f, v):
    W = 540
    lines = cap["audit"].split("\n")
    no2fa_at = next(i for i, ln in enumerate(lines) if ln.startswith("NO SECOND FACTOR"))
    tail = lines[no2fa_at - 1:]
    H = 1060 + 62 + int((len(tail) + 7) * 10.6 * 1.5) + 50
    b = Board(W - 28, H - 28)
    b.top.append(headline(28, 30, f"{v.flagged} findings.<br>Zero judgement.", 46, 470))
    b.top.append(lede(30, 140, f"{mono('bwaudit.py')} reads the whole vault, writes nothing and never prints a password.", 16.5, 440))
    c = counts(v)
    y0, step = 262, 158
    for i, (kind, title, label, hint) in enumerate(SPECIMENS):
        y = y0 + i * step
        specimen_art(b, kind, v, 88, y + 6)
        b.top.append(specimen_text(176, y - 6, 316, title, label, c[kind], hint))
        if i:
            b.top.append(f'<div class="abs" style="left:30px;top:{y - 24:.0f}px;width:452px;border-top:1.5px dashed rgba(31,84,66,.28)"></div>')
    body = term([("out", "\n".join(["⋮"] + tail))])
    b.top.append(plate(26, 1060, 460, "bwaudit.py", body, fs=10.6, lh=1.5, wrap=True, tail="read-only"))
    return W, H, scene(W, H, b)


# ---------------------------------------------------------------- dead --
def parse_cleanup(md):
    tiers, cur = [], None
    for ln in md.splitlines():
        m = re.match(r"^## ([A-E])\. (.*?)  \((\d+)\)$", ln)
        if m:
            cur = {"tier": m.group(1), "title": m.group(2), "count": int(m.group(3)), "items": []}
            tiers.append(cur)
            continue
        m = re.match(r"^- \[ \] \*\*(.+?)\*\* — (.*?)\s*$", ln)
        if m and cur:
            cur["items"].append({"name": m.group(1), "why": m.group(2).split("; "), "host": ""})
            continue
        m = re.match(r"^\s+`(.+?)` · (.*)$", ln)
        if m and cur and cur["items"]:
            cur["items"][-1]["host"] = m.group(1)
    head = re.search(r"(\d+) items scanned, (\d+) flagged", md)
    rest = re.search(r"^(\d+) entries had no evidence of being dead\.", md, re.M)
    return tiers, int(head.group(1)), int(head.group(2)), int(rest.group(1))


SHORT = {"A": "duplicate", "B": "domain gone", "C": "moved off", "D": "untouched", "E": "local address"}


def checklist_sheet(tiers, scanned, flagged, rest, x, y, width, rot=1.2, fs=13.5):
    out = [f'<div class="sheet" style="left:{x}px;top:{y}px;width:{width}px;padding:22px 24px 18px;transform:rotate({rot}deg)">',
           '<div class="mono" style="font-size:12.5px;font-weight:600;color:#6c6250;letter-spacing:.02em">cleanup.md</div>',
           '<div class="casual" style="margin-top:6px;font-weight:820;font-size:23px;letter-spacing:-.02em;color:var(--s900)">Vault cleanup checklist</div>',
           f'<div style="margin-top:4px;font-size:13.5px;font-weight:500;color:#5b6660">{scanned} items scanned, {flagged} flagged. '
           'Nothing has been deleted. Work top-down - tier A is the most certain.</div>']
    for t in tiers:
        out.append(f'<div style="display:flex;align-items:center;gap:9px;margin-top:15px;padding-bottom:5px;border-bottom:1.5px solid #e2dccd">'
                   f'<span class="dymo" style="position:static;font-size:11px;padding:.3em .5em .24em">{t["tier"]}</span>'
                   f'<span style="flex:1;font-weight:700;font-size:{fs - 1.5}px;letter-spacing:.02em;color:#2b3632">{esc(t["title"].split(" - ")[0])}</span>'
                   f'<span class="mono" style="font-weight:700;font-size:12.5px;color:#7a7060">{t["count"]}</span></div>')
        for it in t["items"]:
            out.append(f'<div style="display:flex;gap:10px;padding:7px 0 6px;border-bottom:1px dashed #e5dfd1">'
                       f'<span style="flex:none;width:14px;height:14px;margin-top:2px;border-radius:3px;box-shadow:inset 0 0 0 1.5px #8c8472"></span>'
                       f'<div style="flex:1;min-width:0"><div style="display:flex;gap:10px;align-items:baseline">'
                       f'<b style="font-weight:700;font-size:{fs}px;color:#1d2622">{esc(it["name"])}</b>'
                       f'<span class="mono" style="margin-left:auto;font-size:11.5px;color:#3f7a65;white-space:nowrap">{esc(it["host"])}</span></div>'
                       f'<div style="margin-top:2px;font-size:{fs - 1.5}px;line-height:1.38;color:#5d6762">{esc("; ".join(it["why"]))}</div></div></div>')
    out.append(f'<div style="margin-top:10px;font-size:12.5px;color:#7b8580">Not flagged: {rest} entries had no evidence of being dead.</div></div>')
    return "".join(out)


def box_contents(tiers):
    return [(t["tier"], SHORT.get(t["tier"], ""), [it["name"] for it in t["items"]]) for t in tiers]


def dead(cap, f, v):
    W, H = 1100, 800
    b = Board(W - 28, H - 28)
    tiers, scanned, flagged, rest = parse_cleanup(cap["cleanup"])
    b.top.append(headline(42, 40, "Lost and found.", 52, 520))
    b.top.append(lede(44, 108, f"{mono('bwdead.py')} sorts what looks dead by how sure it is, with the evidence next "
                      "to each one. It deletes nothing: you tick through the list in the app.", 16.5, 470))
    bx = box(78, 282, 432, 150, box_contents(tiers), v)
    b.back += bx["back"]
    b.mid += bx["mid"]
    b.over += bx["over"]
    body = term([("$", "python3 bwdead.py --dns"), ("out", cap["dead"])])
    b.top.append(plate(40, 516, 492, "bwdead.py", body, fs=10.4, lh=1.5))
    b.top.append(checklist_sheet(tiers, scanned, flagged, rest, 568, 40, 460, rot=1.0))
    return W, H, scene(W, H, b)


def dead_mobile(cap, f, v):
    W, H = 540, 1240
    b = Board(W - 28, H - 28)
    tiers, scanned, flagged, rest = parse_cleanup(cap["cleanup"])
    b.top.append(headline(28, 30, "Lost and found.", 46, 470))
    b.top.append(lede(30, 92, f"{mono('bwdead.py')} sorts what looks dead by how sure it is. It deletes nothing.", 16.5, 440))
    bx = box(62, 238, 392, 140, box_contents(tiers), v)
    b.back += bx["back"]
    b.mid += bx["mid"]
    b.over += bx["over"]
    b.top.append(checklist_sheet(tiers, scanned, flagged, rest, 28, 470, 456, rot=.8, fs=13.5))
    return W, H, scene(W, H, b)


# --------------------------------------------------------------- merge --
def merge_story(b, cap, v, x1, x2, y, label=12, tag_size=11.5):
    """Before: two copies of one key on the hook. After: one key with both address tags."""
    m = cap["merge_json"]["merges"][0]
    keep, drop = m["keep_name"], m["drop"][0]["name"]
    u1, u2 = (u.replace("https://", "") for u in m["uris"][:2])
    b.base.append(dymo(x1, y - 46, keep, label))
    b.base.append(dymo(x2, y - 46, keep, label))
    b.top.append(dymo(x1 - 36, y - 92, "Before", 11, center=False, cls="brass", rot=-2))
    b.top.append(dymo(x2 - 30, y - 92, "After", 11, center=False, cls="mint", rot=-2))
    S = 1.15
    b.mid.append(hung(x1, y, S, [(v.key(keep), -10), (v.key(drop), 10)]))
    b.back.append(string_path(x1 - 2, y + 22, x1 + 26, y + 126, sag=3))
    b.over.append(tag(x1 + 26, y + 126, u1, tag_size, rot=-8))
    b.back.append(string_path(x1 + 6, y + 22, x1 + 34, y + 160, sag=3))
    b.over.append(tag(x1 + 34, y + 160, u2, tag_size, rot=4))
    b.front.append(pencil_arrow(x1 + 40, y + 52, x2 - 36, y + 52, bend=-16))
    b.mid.append(hung(x2, y, S, [(v.key(keep), 0)], angle=-1))
    b.back.append(string_path(x2 - 2, y + 22, x2 + 26, y + 126, sag=3))
    b.over.append(tag(x2 + 26, y + 126, u1, tag_size, rot=-8))
    b.back.append(string_path(x2 + 4, y + 22, x2 + 34, y + 160, sag=3))
    b.over.append(tag(x2 + 34, y + 160, u2, tag_size, rot=4))
    return keep, drop


def merge(cap, f, v):
    W, H = 1100, 840
    b = Board(W - 28, H - 28)
    plan = cap["merge_json"]
    b.top.append(headline(42, 40, "Two keys,<br>one door.", 52, 400))
    b.top.append(lede(44, 166, "Same site, same user, same password: one account. The richer key stays and keeps "
                      "every address. The copy goes to the trash, after a backup.", 16, 392))
    y = 364
    b.base.append(rail(40, y - 52, 400))
    keep, drop = merge_story(b, cap, v, 104, 300, y)
    if keep in v.totp:
        b.top.append(note(254, y + 196, "both addresses kept,<br>TOTP seed too", 14.5, rot=-2))
    # the trash, and the pair it leaves alone
    trashed = [drop] + [d["name"] for d in plan["deletes"]]
    tb = bin_can(50, 664, trashed, v)
    b.back += tb["back"]
    b.mid += tb["mid"]
    b.top.append(note(170, 640, "in the trash, not purged:<br>" + "<br>".join(esc(n) for n in trashed)
                      + f"<br>{mono('bwmerge.py restore', 12.5)} brings them back", 14.5, rot=-1.5, width=196))
    if "Amazon (old)" in cap["dupes"]:
        ax = 398
        b.base.append(dymo(ax, 604, "amazon.com", 11))
        b.mid.append(hung(ax, 646, .92, [(v.key("Amazon (old)"), 24), (v.key("Amazon"), -22)]))
        b.top.append(note(ax - 64, 764, "different cuts:<br>left alone", 14.5, rot=-3))
    body = term([("$", "python3 bwmerge.py plan"), ("out", cap["merge_plan"]),
                 ("$", "python3 bwmerge.py apply"), ("out", cap["merge_apply"]),
                 ("$", "python3 bwpolish.py | head -8"), ("out", cap["polish_head"])])
    b.top.append(plate(456, 30, 588, f"bwmerge.py — {WORKDIR}", body, fs=10.8, lh=1.5))
    b.top.append(plate(456, 700, 588, "file modes", term([("out", cap["merge_modes"])]), fs=10.8, lh=1.5,
                       tail="backup first, owner-only"))
    return W, H, scene(W, H, b)


def merge_mobile(cap, f, v):
    W, H = 540, 1210
    b = Board(W - 28, H - 28)
    plan = cap["merge_json"]
    b.top.append(headline(28, 30, "Two keys, one door.", 44, 470))
    b.top.append(lede(30, 92, "The richer key stays and keeps every address. The copy goes to the trash, after a backup.", 16.5, 440))
    y = 290
    b.base.append(rail(40, y - 52, 432))
    keep, drop = merge_story(b, cap, v, 128, 352, y)
    trashed = [drop] + [d["name"] for d in plan["deletes"]]
    tb = bin_can(60, 590, trashed, v)
    b.back += tb["back"]
    b.mid += tb["mid"]
    b.top.append(note(186, 560, "in the trash, not purged:<br>" + "<br>".join(esc(n) for n in trashed)
                      + f"<br>{mono('bwmerge.py restore', 12.5)} brings them back", 15, rot=-1.5, width=280))
    body = term([("$", "python3 bwmerge.py apply"), ("out", cap["merge_apply"])])
    b.top.append(plate(26, 768, 460, "bwmerge.py", body, fs=10.6, lh=1.5, wrap=True))
    b.top.append(plate(26, 1012, 460, "bwpolish.py | head -8", term([("out", "\n".join(cap["polish_head"].split("\n")[-3:]))]), fs=10.6, lh=1.5))
    return W, H, scene(W, H, b)


# ------------------------------------------------------------- folders --
def order_tree(tree):
    return sorted(tree, key=lambda k: (k == "Misc", -len(tree[k]), k))


NUM_WORDS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen".split()


def num_word(n):
    return NUM_WORDS[n].capitalize() if n < len(NUM_WORDS) else str(n)


def before_board(b, v, before, x, y, width, scale=.84):
    b.base.append(rail(x, y - 50, width))
    names = order_tree(before)
    singles = [n for n in names if n != "No Folder"]
    step = (width - 120) / max(1, len(singles))
    for i, n in enumerate(singles + ["No Folder"]):
        hx = x + 40 + i * step if n != "No Folder" else x + width - 58
        items = before[n]
        b.base.append(dymo(hx, y - 44, n, 10.5, rot=wobble(n, -1.5, 1.5)))
        if n == "No Folder":
            ks = [(v.key(it), -42 + 84 * j / max(1, len(items) - 1)) for j, it in enumerate(items)]
            b.mid.append(hung(hx, y, scale * 1.06, ks, angle=7, ring_r=15))
        elif items:
            b.mid.append(hung(hx, y, scale, [(v.key(items[0]), 0)], angle=wobble(n, -3, 3)))
        else:
            b.mid.append(hung(hx, y, scale, [], empty=True))


def after_cell(b, v, name, items, cx, cy, cw, scale=.58, names_size=10.5):
    b.base.append(rail(cx, cy, cw - 14, height=26, screws=False))
    small = cw < 180 and len(name) > 11
    b.base.append(dymo(cx + 7, cy + (6 if small else 4.5), name, 8.4 if small else 10, center=False))
    b.base.append(f'<span class="abs mono" style="left:{cx + cw - 32}px;top:{cy + 6}px;font-size:11.5px;font-weight:700;color:#3a4a50">{len(items)}</span>')
    if not items:
        b.mid.append(hung(cx + 34, cy + 42, scale, [], empty=True))
        return False
    span = (cw - 30) / max(1, len(items))
    for j, it in enumerate(items):
        kx = cx + 14 + span * (j + .5)
        b.mid.append(hung(kx, cy + 42, scale, [(v.key(it), 0)], angle=wobble(it, -3, 3)))
    pills = "".join(f'<span style="display:inline-block;margin:0 4px 4px 0;padding:1px 6px;border-radius:3px;'
                    f'background:rgba(255,255,255,.55);white-space:nowrap">{esc(it)}</span>' for it in items)
    b.over.append(f'<div class="abs" style="left:{cx}px;top:{cy + 42 + 122 * scale:.0f}px;width:{cw - 12}px;'
                  f'font-size:{names_size}px;line-height:1.35;font-weight:650;color:#1f3a31">{pills}</div>')
    return True


def model_plate(cap, x, y, width, fs=11):
    line = next(ln for ln in cap["llm_lines"] if "'Steam'" in ln)
    iid = re.search(r"id=(\S+)", line).group(1)
    ans = next(a for a in cap["llm_answer"] if a["id"] == iid)
    sent = esc(line).replace(" | ", ' <span class="d">|</span> ')
    got = esc('{"id": %s, "folder": %s}' % (json.dumps(ans["id"]), json.dumps(ans["folder"])))
    body = (f'<span class="m">sent to 127.0.0.1, one line per item</span>\n{sent}\n\n'
            f'<span class="m">returned, folder must be one of {len(cap["llm_enum"])} names (JSON schema)</span>\n<span class="g">{got}</span>\n\n'
            f'<span class="w">never sent</span>  password · TOTP seed · notes · custom fields · attachments')
    return plate(x, y, width, "what the model sees", body, fs=fs, lh=1.5, wrap=True)


def folders(cap, f, v):
    W, H = 1100, 856
    b = Board(W - 28, H - 28)
    before, after = cap["tree_before"], cap["tree_after"]
    nf = len(before.get("No Folder", []))
    b.top.append(headline(42, 40, f"{num_word(nf)} keys<br>on one hook?", 50, 390))
    b.top.append(lede(44, 160, f"{mono('bwtidy.py')} asks a model on your own machine to hang every item on one of "
                      f"{len(cap['llm_enum'])} labelled rows. You read the plan before anything moves.", 16, 360))
    b.top.append(dymo(40, 296, "Before", 11, center=False, cls="brass", rot=-2))
    before_board(b, v, before, 40, 380, 364)
    b.top.append(note(64, 540, f"{nf} keys on one hook.<br>The hook would like a word.", 16, rot=-3))
    b.top.append(dymo(446, 34, "After", 11, center=False, cls="mint", rot=-2))
    gx, gy, cw, ch = 446, 74, 202, 172
    for i, n in enumerate(order_tree(after)):
        cx, cy = gx + (i % 3) * cw, gy + (i // 3) * ch
        if not after_cell(b, v, n, after[n], cx, cy, cw):
            b.top.append(note(cx + 54, cy + 50, "empty for now.<br>" + mono("bwfinal.py", 12) + " drops it", 13.5, rot=-3))
    b.top.append(model_plate(cap, 40, 614, 548))
    vbody = term([("$", "python3 bwtidy.py apply | tail -1"), ("out", cap["tidy_apply_tail"]),
                  ("$", "python3 bwtidy.py verify"), ("out", cap["tidy_verify"])])
    b.top.append(plate(602, 614, 442, "bwtidy.py", vbody, fs=11, lh=1.5, wrap=True, tail=f"{len(cap['plan_names'])} moved"))
    return W, H, scene(W, H, b)


def folders_mobile(cap, f, v):
    W, H = 540, 1360
    b = Board(W - 28, H - 28)
    before, after = cap["tree_before"], cap["tree_after"]
    nf = len(before.get("No Folder", []))
    b.top.append(headline(28, 30, f"{num_word(nf)} keys<br>on one hook?", 46, 470))
    b.top.append(lede(30, 148, f"A model on your own machine hangs every item on one of {len(cap['llm_enum'])} "
                      "labelled rows. You read the plan first.", 16.5, 440))
    b.top.append(dymo(40, 252, "Before", 11, center=False, cls="brass", rot=-2))
    before_board(b, v, before, 40, 338, 432, scale=.86)
    b.top.append(note(60, 468, f"{nf} keys on one hook.", 16, rot=-2))
    b.top.append(dymo(40, 520, "After", 11, center=False, cls="mint", rot=-2))
    gx, gy, cw, ch = 28, 560, 160, 172
    for i, n in enumerate(order_tree(after)):
        cx, cy = gx + (i % 3) * cw, gy + (i // 3) * ch
        if not after_cell(b, v, n, after[n], cx, cy, cw, scale=.5, names_size=10):
            b.top.append(note(cx + 48, cy + 50, "empty", 13.5, rot=-3))
    b.top.append(model_plate(cap, 26, 1088, 460, fs=10.4))
    return W, H, scene(W, H, b)


# ---------------------------------------------------------------- flow --
def flow_steps(cap):
    return [
        ("Plan", "bwtidy.py plan", "Reads the vault, writes plan.json. Changes nothing.", cap["modes"].split("\n")[0]),
        ("Review", "plan.json", "Plain JSON. Read it, edit it, delete any line.", cap["tidy_plan"].split("\n")[-1]),
        ("Apply", "bwtidy.py apply", "Re-reads the live vault first and skips anything changed since the plan.", cap["tidy_apply_tail"]),
        ("Verify", "bwtidy.py verify", "SHA-256 of every secret field, before and after.", cap["tidy_verify"]),
    ]


def chore_card(cap, x, y, width, rot=-.8, fs=14):
    rows = []
    for i, (title, cmd, desc, proof) in enumerate(flow_steps(cap)):
        rows.append(f'<div style="display:grid;grid-template-columns:34px 1fr;column-gap:12px;padding:13px 0 12px;'
                    f'{"border-top:1.5px dashed #e0d9c8;" if i else ""}">'
                    f'<div style="grid-row:span 3">{chore_tick(i)}</div>'
                    f'<div style="display:flex;align-items:baseline;gap:12px"><span class="casual" style="font-weight:850;font-size:{fs + 7}px;letter-spacing:-.02em;color:var(--s900)">{i + 1}. {title}</span>'
                    f'<span class="mono" style="font-size:{fs - 1.5}px;font-weight:600;color:#3f7a65">{esc(cmd)}</span></div>'
                    f'<div style="margin-top:2px;font-size:{fs}px;font-weight:500;color:#4c5853;line-height:1.38">{esc(desc)}</div>'
                    f'<div class="mono" style="margin-top:7px;font-size:{fs - 2.5}px;line-height:1.45;color:#c3cfd4;background:#172125;'
                    f'border-radius:6px;padding:6px 10px;white-space:pre-wrap">{color_line(proof)}</div></div>')
    return (f'<div class="sheet" style="left:{x}px;top:{y}px;width:{width}px;padding:16px 26px 10px;transform:rotate({rot}deg)">'
            f'<div class="hand" style="font-size:17px;color:#6c6250">the routine, every time</div>'
            f'{"".join(rows)}</div>')


def guarantee(x, y, title, text, width=300):
    return (f'<div class="abs" style="left:{x}px;top:{y}px;width:{width}px">'
            f'<div class="casual" style="font-weight:820;font-size:19px;letter-spacing:-.015em">{title}</div>'
            f'<div style="margin-top:3px;font-size:14px;color:#24493d;line-height:1.4">{text}</div></div>')


def undo_corner(b, cap, x, y, note_w=200, plate_w=196):
    b.base.append(rail(x - 90, y - 42, 180))
    ut = undo_tag(x, y)
    b.mid += ut["mid"]
    b.top.append(note(x - 84, y + 300, f"on every kind of change:<br>{mono('revert', 12.5)} for moves<br>and renames, "
                      f"{mono('restore', 12.5)}<br>for merges", 15, rot=-2, width=note_w))
    b.top.append(plate(x - 90, y + 420, plate_w, "bwtidy.py revert", term([("out", cap["tidy_revert"])]), fs=11, lh=1.5, wrap=True))


def flow(cap, f, v):
    W, H = 1100, 784
    b = Board(W - 28, H - 28)
    b.top.append(headline(42, 40, "Tidy first.<br>Then prove<br>nothing broke.", 46, 340))
    b.top.append(lede(44, 200, "Every writing script plans first, waits for you, and re-reads the vault before it "
                      "writes. Every change can be walked back.", 16, 300))
    b.top.append(guarantee(44, 330, "Loopback only", "A model address that is not this machine is refused before a byte is sent."))
    b.top.append(plate(40, 412, 304, "bwtidy.py plan", term([("out", cap["refuse"].split(". Set ")[0] + ".")]), fs=10.8, lh=1.5, wrap=True))
    b.top.append(guarantee(44, 548, "Owner-only files", "Plans, fingerprints and backups are created with mode 600."))
    b.top.append(plate(40, 628, 304, "file modes", term([("out", cap["modes"] + "\n" + cap["merge_modes"].split("\n")[1])]),
                       fs=10.8, lh=1.5, wrap=True))
    b.top.append(chore_card(cap, 372, 40, 462))
    undo_corner(b, cap, 950, 128, note_w=214)
    return W, H, scene(W, H, b)


def flow_mobile(cap, f, v):
    W, H = 540, 1296
    b = Board(W - 28, H - 28)
    b.top.append(headline(28, 30, "Tidy first. Then prove nothing broke.", 44, 470))
    b.top.append(lede(30, 148, "Every writing script plans first, waits for you, and can be walked back.", 16.5, 440))
    b.top.append(chore_card(cap, 30, 226, 452, rot=-.6, fs=14))
    b.base.append(rail(40, 940, 180))
    ut = undo_tag(130, 982, scale=.9)
    b.mid += ut["mid"]
    b.top.append(note(252, 960, f"on every kind of change:<br>{mono('revert', 12.5)} for moves<br>and renames, "
                      f"{mono('restore', 12.5)}<br>for merges", 15.5, rot=-2, width=230))
    b.top.append(plate(252, 1104, 232, "bwtidy.py revert", term([("out", cap["tidy_revert"])]), fs=11, lh=1.5, wrap=True))
    return W, H, scene(W, H, b)


# -------------------------------------------------------------- social --
def social(cap, f, v):
    W, H = 1280, 640
    b = Board(W - 28, H - 28)
    b.top.append(brand(70, 66, 34))
    b.top.append(headline(64, 146, "Every key back<br>on its hook.", 92, 700))
    b.top.append(lede(70, 366, "Audit and tidy a Bitwarden or Vaultwarden vault on your own machine. Nothing leaves it.", 27, 600))
    b.top.append(note(72, 506, f"{v.flagged} findings across {v.scanned} items. 0 passwords printed.", 21, rot=-1.2))
    same_cut_pair(b, v, 872, 1090, 168, 2.85, label=15, note_size=25, tag_size=19, rail_x=746, rail_w=480, long_tag=False)
    return W, H, scene(W, H, b, radius=0)


# ------------------------------------------------- GitHub profile cards --
def card(cap, f, v):
    """The profile card: a poster, not a mini README. 880x500 CSS, rendered at 1.5x."""
    W, H = 880, 500
    b = Board(W - 28, H - 28)
    b.top.append(brand(40, 40, 24))
    b.top.append(headline(36, 98, "Every key back<br>on its hook.", 60, 470))
    b.top.append(lede(40, 262, "Audit and tidy a Bitwarden or Vaultwarden vault on your own machine. "
                      "Nothing leaves it.", 20.5, 400))
    b.top.append(note(42, 392, f"{v.flagged} findings, 0 passwords printed", 17, rot=-1.5))
    same_cut_pair(b, v, 566, 728, 132, 2.1, label=13, note_size=19, tag_size=16, rail_x=482, rail_w=346, long_tag=False)
    return W, H, scene(W, H, b, radius=22)


def card_mobile(cap, f, v):
    W, H = 400, 400
    b = Board(W - 24, H - 24)
    b.top.append(brand(26, 26, 18))
    b.top.append(headline(24, 68, "Every key back<br>on its hook.", 40, 350))
    same_cut_pair(b, v, 108, 266, 230, 1.12, label=10.5, note_size=14, tag_size=11.5, rail_x=26, rail_w=324, long_tag=False)
    return W, H, cabinet(W, H, b.html(), radius=18, pad=12)


def cards(cap, f):
    v = Vault(cap)
    out = {}
    for name, fn in (("bwtidy", card), ("bwtidy-mobile", card_mobile)):
        w, h, inner = fn(cap, f, v)
        out[name] = (w, h, page(f"bwtidy card {name}", w, inner, height=h))
    return out


def scenes(cap, f):
    v = Vault(cap)
    out = {}
    for name, fn in (("hero", hero), ("hero-mobile", hero_mobile), ("numbers", numbers),
                     ("numbers-mobile", numbers_mobile), ("audit", audit), ("audit-mobile", audit_mobile),
                     ("merge", merge), ("merge-mobile", merge_mobile), ("folders", folders),
                     ("folders-mobile", folders_mobile), ("flow", flow), ("flow-mobile", flow_mobile),
                     ("dead", dead), ("dead-mobile", dead_mobile), ("social", social)):
        w, h, inner = fn(cap, f, v)
        out[name] = (w, h, page(f"bwtidy {name}", w, inner, height=h))
    return out

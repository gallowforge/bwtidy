#!/usr/bin/env python3
"""
Regenerates the README images in docs/readme/.

1. Capture: runs the real scripts against the synthetic vault in examples/,
   through the fake `bw` (tests/bin/bw) and the stand-in LM Studio
   (tests/fake_lmstudio.py). It refuses to run if `bw` on PATH is anything
   but the fake, so it can never touch a real vault. The one network use is
   `bwdead.py --dns`, which resolves the synthetic vault's public domains.
2. Compose: turns the captured output into one HTML page per scene in
   docs/readme/src/, kept in the repo so every image can be inspected.
3. Render: headless Chrome screenshots each page at 2x and ImageMagick writes
   the WebP. Every scene has a wide and a portrait (phone) version, and
   social.png is the 1280x640 preview for the repository settings.

    python3 scripts/readme_visuals.py            # capture, compose, render
    python3 scripts/readme_visuals.py --html     # capture and compose only
    python3 scripts/readme_visuals.py --only hero,numbers

Needs google-chrome-stable (or $CHROME) and ImageMagick's `magick`.
"""

import ast
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
FAKE_BW = os.path.join(TESTS, "bin", "bw")
OUT = os.path.join(ROOT, "docs", "readme")
SRC = os.path.join(OUT, "src")
CHROME = os.environ.get("CHROME", "google-chrome-stable")
sys.path.insert(0, TESTS)
import fake_lmstudio  # noqa: E402

WORKDIR = "~/bwtidy-work"


# ==========================================================================
# 1. capture
# ==========================================================================

class Demo:
    """A fresh working directory holding a copy of the synthetic vault."""

    def __init__(self, llm_url):
        self.dir = tempfile.mkdtemp(prefix="bwtidy-demo-")
        shutil.copy(os.path.join(ROOT, "examples", "sample-vault.json"),
                    os.path.join(self.dir, "vault.json"))
        shutil.copy(os.path.join(ROOT, "examples", "bwtidy.example.json"),
                    os.path.join(self.dir, "bwtidy.json"))
        path = os.path.dirname(FAKE_BW) + os.pathsep + os.environ["PATH"]
        if shutil.which("bw", path=path) != FAKE_BW:
            sys.exit("refusing to run: `bw` does not resolve to tests/bin/bw")
        self.env = dict(os.environ, PATH=path, BW_SESSION="demo",
                        BW_FAKE_VAULT=os.path.join(self.dir, "vault.json"),
                        LMSTUDIO_URL=llm_url)
        for k in ("BWTIDY_CONFIG", "BWTIDY_ALLOW_REMOTE_LLM", "LMSTUDIO_MODEL"):
            self.env.pop(k, None)

    def _clean(self, text):
        return text.replace(self.dir, WORKDIR).strip("\n")

    def run(self, script, *args, env=None, ok=True):
        p = subprocess.run([sys.executable, os.path.join(ROOT, script), *args],
                           cwd=self.dir, env=env or self.env,
                           capture_output=True, text=True, timeout=120)
        if ok and p.returncode != 0:
            sys.exit(f"{script} {args} failed:\n{p.stdout}\n{p.stderr}")
        return self._clean(p.stdout + p.stderr)

    def sh(self, command):
        """Run a shell pipeline exactly as it is shown in the image."""
        command = command.replace("python3 bw", f"{sys.executable} {ROOT}/bw")
        p = subprocess.run(["sh", "-c", command], cwd=self.dir, env=self.env,
                           capture_output=True, text=True, check=True)
        return self._clean(p.stdout)

    def json(self, name):
        with open(os.path.join(self.dir, name)) as f:
            return json.load(f)

    def read(self, name):
        with open(os.path.join(self.dir, name)) as f:
            return f.read()

    def close(self):
        shutil.rmtree(self.dir)


def folder_tree(state):
    names = {f["id"]: f["name"] for f in state["folders"]}
    tree = {f["name"]: [] for f in state["folders"]}
    for it in state["items"]:
        if not it.get("deletedDate"):
            tree.setdefault(names.get(it.get("folderId"), "No Folder"), []).append(it["name"])
    return tree


def capture():
    server, llm_url = fake_lmstudio.start()
    cap = {}
    try:
        d = Demo(llm_url)
        cap["audit"] = d.run("bwaudit.py")
        cap["dupes"] = d.run("bwdupes.py")
        d.close()

        d = Demo(llm_url)
        cap["dead"] = d.run("bwdead.py", "--dns")
        cap["cleanup"] = d.read("cleanup.md")
        d.close()

        d = Demo(llm_url)
        cap["tree_before"] = folder_tree(d.json("vault.json"))
        fake_lmstudio.REQUESTS.clear()
        cap["tidy_plan"] = d.run("bwtidy.py", "plan")
        cap["plan_names"] = [p["name"] for p in d.json("plan.json")]
        req = fake_lmstudio.REQUESTS[0]
        cap["llm_lines"] = [ln for ln in req["messages"][-1]["content"].splitlines()
                            if re.match(r"\d+\. id=", ln)]
        cap["llm_answer"] = fake_lmstudio.answer(req)["assignments"]
        cap["llm_enum"] = req["response_format"]["json_schema"]["schema"][
            "properties"]["assignments"]["items"]["properties"]["folder"]["enum"]
        cap["tidy_apply_tail"] = d.sh("python3 bwtidy.py apply | tail -1")
        cap["tree_after"] = folder_tree(d.json("vault.json"))
        cap["tidy_verify"] = d.run("bwtidy.py", "verify")
        cap["modes"] = d.sh("stat -c '%A  %n' plan.json fingerprint.json")
        cap["tidy_revert"] = d.run("bwtidy.py", "revert")
        remote = dict(d.env, LMSTUDIO_URL="http://203.0.113.10:1234/v1")
        cap["refuse"] = d.run("bwtidy.py", "plan", env=remote, ok=False)
        d.close()

        d = Demo(llm_url)
        cap["items"] = len(d.json("vault.json")["items"])
        cap["merge_plan"] = d.run("bwmerge.py", "plan")
        cap["merge_json"] = d.json("merge_plan.json")
        cap["merge_apply"] = d.run("bwmerge.py", "apply")
        cap["polish_head"] = d.sh("python3 bwpolish.py | head -8")
        cap["merge_modes"] = d.sh("stat -c '%A  %n' merge_plan.json backup-*.json")
        cap["merge_restore"] = d.run("bwmerge.py", "restore")
        d.close()
    finally:
        server.shutdown()
    return cap


def facts(cap):
    """Every number shown in the images, read from the code, tests and output."""
    a = cap["audit"]

    def grab(pattern):
        return int(re.search(pattern, a, re.M).group(1))

    scripts = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "bw*.py")))
    tests = sum(open(p).read().count("\n    def test_")
                for p in glob.glob(os.path.join(TESTS, "test_*.py")))
    with open(os.path.join(TESTS, "test_e2e.py")) as f:
        suite = f.read()
    for proof in ("test_no_network_egress", "test_model_never_receives_secrets"):
        assert proof in suite, f"{proof} is missing; the numbers banner relies on it"
    third_party = set()
    for p in scripts:
        for node in ast.walk(ast.parse(open(os.path.join(ROOT, p)).read())):
            mods = ([n.name for n in node.names] if isinstance(node, ast.Import) else
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            third_party |= {m.split(".")[0] for m in mods
                            if m.split(".")[0] not in sys.stdlib_module_names
                            and not m.startswith("bw")}
    with open(os.path.join(ROOT, "bwaudit.py")) as f:
        checks = 1 + f.read().count("total += section(")   # reused + the sections
    return {
        "scripts": len(scripts) - 1,                       # bwconfig is shared code
        "tests": tests,
        "checks": checks,
        "deps": len(third_party),
        "scanned": grab(r"Scanned (\d+) items"),
        "reused_groups": grab(r"REUSED PASSWORDS  \((\d+) password"),
        "reused_entries": grab(r"shared across (\d+) entries"),
        "weak": grab(r"^WEAK PASSWORDS .*\((\d+)\)$"),
        "no2fa": grab(r"^NO SECOND FACTOR ON A CRITICAL ACCOUNT  \((\d+)\)"),
        "nourl": grab(r"^NO WEBSITE SET - AUTOFILL CANNOT WORK  \((\d+)\)"),
        "stale": grab(r"^NOT TOUCHED IN \d\+ YEARS  \((\d+)\)"),
        "flagged": grab(r"^(\d+) item\(s\) flagged"),
    }


# ==========================================================================
# 2. compose
# ==========================================================================

def esc(s):
    return html.escape(s, quote=False)


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

CLASS = {"crit": "w", "fail": "r", "pass": "g b", "url": "u", "user": "us",
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
                 r"Moved \d+ items\.|Scanned \d+ items)(.*)$", line)
    if m:
        return f'<span class="b">{tokens(m.group(1))}</span>{tokens(m.group(2))}'
    m = re.match(r"^(\s+Group \d+ - \d+ entries)(.*)$", line)
    if m:
        return f'<span class="h2">{esc(m.group(1))}</span>{tokens(m.group(2))}'
    m = re.match(r"^(\s+)(\d+)(  )(\w.*)$", line)          # bwtidy plan counts
    if m:
        return f'{m.group(1)}<span class="n">{m.group(2)}</span>{m.group(3)}<span class="f">{esc(m.group(4))}</span>'
    m = re.match(r"^(\s{2}\[\d+/\d+\] )(.*?)( -> )(.*)$", line)
    if m:
        return (f'<span class="d">{esc(m.group(1))}</span>{esc(m.group(2))}'
                f'<span class="a">{m.group(3)}</span><span class="f">{esc(m.group(4))}</span>')
    m = re.match(r"^(\s+- )(.*?)(\s+)(https?://\S+)$", line)   # bwdupes rows
    if m:
        return f'<span class="d">{m.group(1)}</span>{esc(m.group(2))}{m.group(3)}<span class="u">{esc(m.group(4))}</span>'
    m = re.match(r"^(\s{2})([a-z0-9.-]+\.[a-z]+)(\s+.*)$", line)  # bwdupes group head
    if m and "@" in line:
        return f'{m.group(1)}<span class="u b">{m.group(2)}</span>{tokens(m.group(3))}'
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


def terminal(blocks, *, title, width, fs=12.5, lh=1.56, cursor=True, wrap=False,
             fade=None, top_fade=None, style=""):
    """blocks: list of ("$", command) or ("out", text)."""
    rows = []
    for kind, text in blocks:
        if kind == "$":
            rows.append(prompt(text, not rows))
        else:
            rows += [color_line(ln) for ln in text.split("\n")]
    if cursor:
        rows.append(prompt("", not rows))
    body = "\n".join(rows)
    cls = "term wrap" if wrap else "term"
    fade_html = f'<div class="fade" style="height:{fade}px"></div>' if fade else ""
    if top_fade:
        fade_html += f'<div class="tfade" style="height:{top_fade}px"></div>'
    return (f'<div class="win" style="width:{width}px;{style}">'
            f'<div class="bar"><i></i><i></i><i></i><span class="t">{esc(title)}</span></div>'
            f'<pre class="{cls}" style="--fs:{fs}px;--lh:{lh}">{body}</pre>{fade_html}</div>')


ICON = """<svg viewBox="0 0 64 64" width="{s}" height="{s}" aria-hidden="true">
<defs><linearGradient id="ig{u}" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#5eead4"/><stop offset="1" stop-color="#0d9488"/></linearGradient></defs>
<rect width="64" height="64" rx="17" fill="url(#ig{u})"/>
<circle cx="32" cy="27.5" r="9.5" fill="#032b26"/>
<path d="M27.2 33.5h9.6l3.2 15.5H24z" fill="#032b26"/>
<path d="M49 11.5l1.6 4.4 4.4 1.6-4.4 1.6L49 23.5l-1.6-4.4-4.4-1.6 4.4-1.6z" fill="#032b26" opacity=".85"/>
</svg>"""


UNDO = ('<svg class="undo" viewBox="0 0 24 24" width="{s}" height="{s}" fill="none" stroke="currentColor" '
        'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4.5V9h4.5"/></svg>')


def undo(size=15):
    return UNDO.format(s=size)


def icon(size, uid="a"):
    return ICON.format(s=size, u=uid)


def brand(size, uid="a"):
    return (f'<div class="brand" style="font-size:{size}px;gap:{size * .5:.0f}px">'
            f'<span class="logo">{icon(round(size * 1.5), uid)}</span>bwtidy</div>')


CSS = """
:root { --accent:#2dd4bf; --accent-2:#14b8a6; --ink:#f3f5f8; --muted:#97a1ad; --dim:#5f6a77;
  --amber:#fbbf24; --red:#f87171; --sky:#7dd3fc; --violet:#c4b5fd; --sand:#e8d5a8; }
* { box-sizing:border-box; margin:0; padding:0; }
html, body { background:transparent; }
body { font-family:Inter, sans-serif; color:var(--ink); -webkit-font-smoothing:antialiased;
  font-feature-settings:'cv11','ss01'; }
.card { position:relative; overflow:hidden; border-radius:32px; isolation:isolate;
  background:
    radial-gradient(var(--gw,1100px) var(--gh,620px) at var(--gx,50%) var(--gy,-8%), rgba(45,212,191,.19), transparent 70%),
    radial-gradient(760px 520px at var(--ax,100%) var(--ay,110%), rgba(45,212,191,.06), transparent 70%),
    linear-gradient(180deg, #0b0f12, #07090b); }
.card::before { content:''; position:absolute; inset:0; z-index:-1;
  background-image:radial-gradient(rgba(255,255,255,.07) 1.2px, transparent 1.6px); background-size:30px 30px;
  -webkit-mask-image:radial-gradient(var(--gw,1100px) var(--gh,620px) at var(--gx,50%) var(--gy,-8%), #000, transparent 75%); }
.rim { position:absolute; inset:0; border-radius:32px; z-index:20; pointer-events:none;
  box-shadow:inset 0 0 0 1.5px rgba(255,255,255,.085), inset 0 1.5px 0 rgba(255,255,255,.06); }
.abs { position:absolute; }
.row { display:flex; } .col { display:flex; flex-direction:column; }
.stack { display:grid; } .stack > * { grid-area:1/1; align-self:start; justify-self:start; }
.lede, .cdesc, .nd, .lr, .dwhy, .sub, .nl { text-wrap:pretty; }
.undo { display:inline-block; vertical-align:-2px; }

/* terminal */
.win { position:relative; border-radius:14px; overflow:hidden; background:#090c10;
  box-shadow:0 0 0 1px rgba(255,255,255,.11), 0 50px 90px -30px rgba(0,0,0,.85), 0 20px 40px -20px rgba(0,0,0,.6); }
.win .bar { position:relative; height:36px; display:flex; align-items:center; gap:8px; padding:0 15px;
  background:#12151a; border-bottom:1px solid rgba(255,255,255,.06); }
.win .bar i { width:11.5px; height:11.5px; border-radius:50%; }
.win .bar i:nth-child(1) { background:#f0605a; } .win .bar i:nth-child(2) { background:#e9b443; }
.win .bar i:nth-child(3) { background:#3cc35a; }
.win .bar .t { position:absolute; left:0; right:0; text-align:center; font:500 12.5px Inter; color:#77818d; letter-spacing:-.005em; }
.term { font-family:'JetBrains Mono', monospace; font-size:var(--fs); line-height:var(--lh); color:#c3cbd5;
  padding:16px 22px 20px; white-space:pre; overflow:hidden; font-variant-ligatures:none; }
.term.wrap { white-space:pre-wrap; overflow-wrap:anywhere; }
.term.wrap .rule { display:inline-block; max-width:100%; overflow:hidden; vertical-align:top; white-space:pre; }
.fade { position:absolute; left:0; right:0; bottom:0; background:linear-gradient(180deg, rgba(9,12,16,0), #090c10 85%); }
.tfade { position:absolute; left:0; right:0; top:37px; background:linear-gradient(0deg, rgba(9,12,16,0), #090c10 85%); }
.pr.gap { display:inline-block; margin-top:9px; }
.pp { color:var(--accent); } .pd { color:#5f6a77; } .pc { color:#f6f8fa; font-weight:700; }
.cur { background:var(--accent); opacity:.85; }
.rule { color:#2e3640; } .h { color:#f6f8fa; font-weight:700; } .h2 { color:#e6ebf0; }
.m { color:#7d8794; } .d { color:#566170; } .b { color:#f6f8fa; font-weight:700; }
.n { color:var(--accent); font-weight:700; } .w { color:var(--amber); } .r { color:var(--red); }
.g { color:var(--accent); } .u { color:var(--sky); } .us { color:#a7b0bc; } .f { color:var(--violet); }
.k { color:var(--sand); } .c { color:#f6f8fa; } .a { color:var(--accent); }
.tier { color:#04201c; background:var(--accent); font-weight:700; border-radius:3px; padding:0 .32em; margin:0 -.32em; }

/* type */
.brand { display:flex; align-items:center; font-weight:800; letter-spacing:-.035em; color:#f6f8fa; }
.logo { display:flex; filter:drop-shadow(0 10px 24px rgba(45,212,191,.45)); }
h1 { font-weight:800; letter-spacing:-.047em; line-height:1.0; color:#f6f8fa; }
.grad { background:linear-gradient(92deg, #7af0dc, #2dd4bf 45%, #14b8a6); -webkit-background-clip:text; background-clip:text; color:transparent; }
.lede { color:var(--muted); font-weight:500; line-height:1.45; letter-spacing:-.012em; }
.center { position:absolute; left:0; right:0; display:flex; flex-direction:column; align-items:center; text-align:center; }
.pills { display:flex; gap:14px; justify-content:center; }
.pill { display:inline-flex; align-items:center; gap:10px; height:48px; padding:0 22px; border-radius:999px; font-weight:700; font-size:17px; letter-spacing:-.01em; }
.pill.go { background:var(--accent); color:#03201c; box-shadow:0 12px 40px -10px rgba(45,212,191,.65); font-family:'JetBrains Mono', monospace; font-size:16px; }
.pill.ghost { color:#d4dae2; box-shadow:inset 0 0 0 1.5px rgba(255,255,255,.14); background:rgba(255,255,255,.03); }

/* panels */
.panel { position:relative; border-radius:20px; background:linear-gradient(180deg, #13171d, #0e1116);
  box-shadow:0 0 0 1px rgba(255,255,255,.10), 0 40px 80px -30px rgba(0,0,0,.9), 0 16px 32px -16px rgba(0,0,0,.6); overflow:hidden; }
.panel::before { content:''; position:absolute; inset:0; border-radius:20px; pointer-events:none;
  background:radial-gradient(480px 220px at 50% -40px, rgba(45,212,191,.10), transparent 70%); }
.eyebrow { font:700 11.5px Inter; letter-spacing:.14em; text-transform:uppercase; color:#7d8794; }
.mono { font-family:'JetBrains Mono', monospace; font-variant-ligatures:none; }
.chip { display:inline-flex; align-items:center; gap:7px; height:28px; padding:0 11px; border-radius:999px;
  font:600 12.5px Inter; color:#cdd4dc; background:rgba(255,255,255,.04); box-shadow:inset 0 0 0 1px rgba(255,255,255,.09); }
.chip.on { color:#5eead4; background:rgba(45,212,191,.08); box-shadow:inset 0 0 0 1px rgba(45,212,191,.28); }
.dot { width:8px; height:8px; border-radius:50%; flex:none; }

/* stats */
.stat { padding-inline-start:28px; border-inline-start:1.5px solid rgba(255,255,255,.07); }
.stat:first-child, .stack .stat { padding-inline-start:0; border:0; }
.stat .num { font-weight:800; letter-spacing:-.05em; line-height:1; color:#f6f8fa; font-variant-numeric:tabular-nums; }
.stat .lab { margin-top:12px; font-weight:700; color:#e2e7ed; letter-spacing:-.01em; }
.stat .sub { margin-top:5px; font-weight:500; color:#7d8693; letter-spacing:-.005em; }
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800'
         '&family=JetBrains+Mono:wght@400;500;700&display=block" rel="stylesheet">')


def page(title, width, inner, extra_css=""):
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<title>{esc(title)}</title>{FONTS}<style>{CSS}{extra_css}</style></head>'
            f'<body style="width:{width}px">\n{inner}\n</body></html>\n')


def card(width, glow, inner):
    return (f'<div class="card" style="width:{width}px;{glow}">'
            f'{inner}<div class="rim"></div></div>')


# ---------------------------------------------------------------- pieces --

def summary_panel(f, width, big=58):
    rows = [
        ("#f87171", "Reused passwords", f'{f["reused_groups"]} groups · {f["reused_entries"]} entries'),
        ("#fbbf24", "Weak passwords", str(f["weak"])),
        ("#fb923c", "No 2FA on a critical account", str(f["no2fa"])),
        ("#7dd3fc", "No website, so no autofill", str(f["nourl"])),
        ("#a7b0bc", "Untouched for 3+ years", str(f["stale"])),
    ]
    items = "".join(
        f'<div class="srow"><span class="dot" style="background:{c};box-shadow:0 0 12px {c}66"></span>'
        f'<span class="sl">{esc(label)}</span><span class="sv">{esc(v)}</span></div>' for c, label, v in rows)
    return f"""
<div class="panel summary" style="width:{width}px">
  <div class="shead"><span class="eyebrow">Audit summary</span><span class="chip on">read-only</span></div>
  <div class="sbig"><span class="grad" style="font-size:{big}px">{f["flagged"]}</span>
    <span class="sbt">findings across<br>{f["scanned"]} vault items</span></div>
  <div class="srows">{items}</div>
  <div class="sfoot"><span class="tick">✓</span> Nothing changed&nbsp;&nbsp;<span class="sep">·</span>&nbsp;&nbsp;0 passwords printed</div>
</div>"""


SUMMARY_CSS = """
.summary { padding:22px 24px 20px; }
.shead { display:flex; align-items:center; justify-content:space-between; }
.sbig { display:flex; align-items:center; gap:16px; margin:16px 0 14px; }
.sbig .grad { font-weight:800; letter-spacing:-.05em; line-height:.95; }
.sbt { font:600 15px/1.3 Inter; color:#c9d0d8; letter-spacing:-.01em; }
.srows { border-top:1px solid rgba(255,255,255,.07); }
.srow { display:flex; align-items:center; gap:12px; padding:11px 0; border-bottom:1px solid rgba(255,255,255,.06); font-size:15px; }
.sl { flex:1; color:#dfe4ea; font-weight:500; letter-spacing:-.01em; }
.sv { color:#f6f8fa; font-weight:700; font-variant-numeric:tabular-nums; }
.sfoot { margin-top:14px; font:600 13.5px Inter; color:#8d97a3; display:flex; align-items:center; }
.sfoot .tick { color:var(--accent); margin-right:8px; font-weight:800; }
.sfoot .sep { color:#4a535e; }
"""


def checks_panel(f, width):
    rows = [
        ("Reused passwords", f'{f["reused_groups"]} groups',
         "SHA-256 of each password, compared in memory. Never printed."),
        ("Weak passwords", str(f["weak"]),
         "Under 12 characters, or two character classes or fewer."),
        ("Missing 2FA", str(f["no2fa"]),
         "No TOTP seed on a login in Financial, Email, Infrastructure or Government &amp; Utilities."),
        ("No website", str(f["nourl"]),
         "No usable URL, so the browser extension can never offer it."),
        ("Untouched", str(f["stale"]),
         "Not edited in three years or more. A hint, never a verdict."),
    ]
    items = "".join(
        f'<div class="crow"><div class="cnum">{i}</div><div class="cbody">'
        f'<div class="ctitle"><span>{t}</span><span class="cval">{v}</span></div>'
        f'<div class="cdesc">{d}</div></div></div>' for i, (t, v, d) in enumerate(rows, 1))
    return f"""
<div class="panel checks" style="width:{width}px">
  <div class="eyebrow">{f["checks"]} checks · no model · no network</div>
  <div class="ctitle0">What <span class="mono g">bwaudit.py</span> looks for</div>
  {items}
</div>"""


CHECKS_CSS = """
.checks { padding:26px 26px 12px; }
.ctitle0 { margin:10px 0 10px; font:700 21px/1.25 Inter; letter-spacing:-.02em; color:#f6f8fa; }
.ctitle0 .mono { font-size:18px; font-weight:600; }
.crow { display:flex; gap:14px; padding:15px 0; border-top:1px solid rgba(255,255,255,.07); }
.cnum { flex:none; width:26px; height:26px; border-radius:8px; display:grid; place-items:center;
  font:700 13px Inter; color:#04201c; background:linear-gradient(135deg,#5eead4,#14b8a6); }
.cbody { flex:1; }
.ctitle { display:flex; justify-content:space-between; font:700 16px Inter; letter-spacing:-.01em; color:#eef2f5; }
.cval { color:var(--accent); font-variant-numeric:tabular-nums; }
.cdesc { margin-top:5px; font:500 14px/1.45 Inter; color:#8e98a4; letter-spacing:-.005em; }
"""


def diff_panel(cap, width):
    plan = cap["merge_json"]
    rows = []
    for m in plan["merges"]:
        keep, drops = m["keep_name"], [d["name"] for d in m["drop"]]
        rows.append(f'<div class="dsec">Merge <span class="dmeta">same site, same user, same password</span></div>')
        rows.append(f'<div class="dl keep"><span class="sg"> </span><span class="dn">{esc(keep)}</span>'
                    f'<span class="dtag">kept · has the TOTP seed</span></div>')
        original = set()
        for u in m["uris"]:
            src = "" if not original else f'<span class="dfrom">from {esc(", ".join(drops))}</span>'
            sign, cls = (" ", "ctx") if not original else ("+", "add")
            rows.append(f'<div class="dl {cls} sub"><span class="sg">{sign}</span>'
                        f'<span class="du">{esc(u)}</span>{src}</div>')
            original.add(u)
        for dname in drops:
            rows.append(f'<div class="dl del"><span class="sg">−</span><span class="dn">{esc(dname)}</span>'
                        f'<span class="dtag r">to trash</span></div>')
    rows.append('<div class="dsec">Delete <span class="dmeta">only what bwtidy.json names</span></div>')
    for d in plan["deletes"]:
        rows.append(f'<div class="dl del two"><span class="sg">−</span><div><span class="dn">{esc(d["name"])}</span>'
                    f'<div class="dwhy">{esc(d["reason"])}</div></div></div>')
    rows.append('<div class="dsec">Left alone <span class="dmeta">could be two accounts</span></div>')
    rows.append('<div class="dl ctx two"><span class="sg">=</span><div><span class="dn">Amazon · Amazon (old)</span>'
                '<div class="dwhy">same site and user, different password</div></div></div>')
    before = cap["items"]
    after = before - sum(len(m["drop"]) for m in plan["merges"]) - len(plan["deletes"])
    return f"""
<div class="panel diff" style="width:{width}px">
  <div class="dhead"><span class="mono k">merge_plan.json</span><span class="chip on">{before} → {after} items</span></div>
  {''.join(rows)}
  <div class="dfoot"><span><b>✓</b> Backup written first, owner-only</span><span><b>✓</b> Trash, never purge</span><span><b>{undo(14)}</b> <span class="mono">bwmerge.py restore</span></span></div>
</div>"""


DIFF_CSS = """
.diff { padding:20px 0 0; }
.dhead { display:flex; justify-content:space-between; align-items:center; padding:0 22px 14px; border-bottom:1px solid rgba(255,255,255,.07); }
.dhead .mono { font-size:14px; }
.dsec { padding:14px 22px 6px; font:700 11.5px Inter; letter-spacing:.12em; text-transform:uppercase; color:#7d8794; }
.dmeta { margin-left:8px; font-weight:500; letter-spacing:0; text-transform:none; color:#5f6a77; font-size:12.5px; }
.dl { display:flex; align-items:baseline; gap:12px; padding:6px 22px; font:500 15px Inter; color:#e3e8ed; }
.dl .sg { flex:none; width:14px; font:700 15px 'JetBrains Mono', monospace; color:#5f6a77; text-align:center; }
.dl.add { background:rgba(45,212,191,.08); box-shadow:inset 3px 0 0 var(--accent); }
.dl.add .sg { color:var(--accent); }
.dl.del { background:rgba(248,113,113,.07); box-shadow:inset 3px 0 0 #f87171; }
.dl.del .sg { color:#f87171; } .dl.del .dn { color:#f3c5c5; text-decoration:line-through; text-decoration-color:rgba(248,113,113,.55); }
.dl.sub { padding-left:48px; }
.dn { font-weight:600; letter-spacing:-.01em; }
.du { font:500 13.5px 'JetBrains Mono', monospace; color:#7dd3fc; }
.dfrom { margin-left:auto; font-size:12.5px; color:#5eead4; white-space:nowrap; }
.dtag { margin-left:auto; font-size:12.5px; color:#8e98a4; white-space:nowrap; }
.dtag.r { color:#f87171; }
.dl.two { align-items:flex-start; }
.dwhy { margin-top:2px; font:500 13px Inter; color:#8e98a4; }
.dfoot { display:flex; flex-wrap:wrap; gap:8px 18px; margin-top:14px; padding:14px 22px 16px; border-top:1px solid rgba(255,255,255,.07);
  background:rgba(0,0,0,.18); font:600 12.5px Inter; color:#a7b0bc; }
.dfoot b { color:var(--accent); margin-right:4px; }
.dfoot .mono { font-weight:500; color:#d6dce3; }
"""


def tree_panel(cap, width):
    before, after = cap["tree_before"], cap["tree_after"]
    moved = set(cap["plan_names"])

    def column(tree, label, side):
        order = sorted(tree, key=lambda k: (k == "Misc", -len(tree[k]), k))
        out = [f'<div class="tcol"><div class="tlab">{label}<span>{len(tree)} folders</span></div>']
        for folder in order:
            names = tree[folder]
            empty = " empty" if not names else ""
            new = " new" if side == "after" and folder not in before else ""
            out.append(f'<div class="tf{empty}{new}"><span class="fi"></span><span class="fn">{esc(folder)}</span>'
                       f'<span class="fc">{len(names)}</span></div>')
            for n in names:
                mv = " mv" if side == "after" and n in moved else ""
                out.append(f'<div class="ti{mv}">{esc(n)}</div>')
        out.append("</div>")
        return "".join(out)

    return f"""
<div class="panel tree" style="width:{width}px">
  <div class="thead"><span class="eyebrow">Folders, before and after</span><span class="chip on">{len(moved)} of {sum(map(len, before.values()))} moved</span></div>
  <div class="tcols">{column(before, "Before", "before")}<div class="tarrow">→</div>{column(after, "After", "after")}</div>
</div>"""


TREE_CSS = """
.tree { padding:20px 22px 18px; }
.thead { display:flex; justify-content:space-between; align-items:center; padding-bottom:14px; border-bottom:1px solid rgba(255,255,255,.07); }
.tcols { display:grid; grid-template-columns:1fr 26px 1fr; gap:0 16px; margin-top:12px; }
.tarrow { align-self:start; margin-top:0; width:26px; height:26px; border-radius:50%; display:grid; place-items:center;
  color:#04201c; background:linear-gradient(135deg,#5eead4,#14b8a6); font:800 14px Inter; box-shadow:0 6px 16px -4px rgba(45,212,191,.6); }
.tlab { display:flex; align-items:baseline; justify-content:space-between; font:700 15px Inter; color:#f6f8fa; margin:2px 0 8px; letter-spacing:-.01em; }
.tlab span { font:500 12.5px Inter; color:#6b7581; }
.tf { display:flex; align-items:center; gap:8px; margin-top:7px; padding:4px 8px; border-radius:8px; background:rgba(255,255,255,.035);
  font:600 13.5px Inter; color:#e6ebf0; letter-spacing:-.01em; }
.tf .fi { width:13px; height:10px; border-radius:2px; background:#c4b5fd; opacity:.9; position:relative; flex:none; }
.tf .fi::before { content:''; position:absolute; left:0; top:-2.5px; width:6px; height:3px; border-radius:1.5px 1.5px 0 0; background:#c4b5fd; }
.tf.new .fi, .tf.new .fi::before { background:var(--accent); }
.tf.new { background:rgba(45,212,191,.07); }
.tf .fn { flex:1; } .tf .fc { font-variant-numeric:tabular-nums; color:#8e98a4; font-weight:600; }
.tf.empty { opacity:.5; }
.ti { padding:2.5px 0 2.5px 29px; font:500 13px Inter; color:#9aa4b0; letter-spacing:-.005em; position:relative; }
.ti.mv { color:#e6ebf0; }
.ti.mv::before { content:''; position:absolute; left:14px; top:50%; width:6px; height:6px; margin-top:-3px; border-radius:50%; background:var(--accent); box-shadow:0 0 8px rgba(45,212,191,.6); }
"""


def model_panel(cap, width):
    line = next(ln for ln in cap["llm_lines"] if "'Steam'" in ln)
    iid = re.search(r"id=(\S+)", line).group(1)
    ans = next(a for a in cap["llm_answer"] if a["id"] == iid)
    sent = esc(line).replace(" | ", ' <span class="d">|</span> ')
    got = esc('{"id": %s,\n "folder": %s}' % (json.dumps(ans["id"]), json.dumps(ans["folder"])))
    return f"""
<div class="panel model" style="width:{width}px">
  <div class="mrow"><span class="eyebrow">Sent to 127.0.0.1</span><span class="mtag">one line per item</span></div>
  <div class="mono mcode">{sent}</div>
  <div class="mrow"><span class="eyebrow">Returned</span><span class="mtag">JSON schema · folder is one of {len(cap["llm_enum"])} names</span></div>
  <div class="mono mcode">{got}</div>
  <div class="mnever"><span>Never sent</span>password · TOTP seed · notes · custom fields · attachments</div>
</div>"""


MODEL_CSS = """
.model { padding:18px 22px 16px; }
.mrow { display:flex; justify-content:space-between; align-items:baseline; margin-top:2px; }
.mrow + .mcode { margin-top:8px; }
.mtag { font:500 12.5px Inter; color:#6b7581; }
.mcode { font-size:12.5px; line-height:1.55; color:#d6dce3; background:#0a0d11; border-radius:10px; padding:10px 12px;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.06); margin-bottom:14px; white-space:pre-wrap; overflow-wrap:anywhere; }
.mcode .d { color:#4a535e; }
.mnever { display:flex; gap:10px; align-items:baseline; padding-top:12px; border-top:1px solid rgba(255,255,255,.07);
  font:500 13.5px Inter; color:#c9d0d8; }
.mnever span { flex:none; font:700 11.5px Inter; letter-spacing:.12em; text-transform:uppercase; color:#f87171; }
"""


def checklist_panel(cap, width):
    md = cap["cleanup"]
    out = []
    for ln in md.splitlines():
        m = re.match(r"^## ([A-E])\. (.*?)  \((\d+)\)$", ln)
        if m:
            out.append(f'<div class="ltier"><span class="tier-b">{m.group(1)}</span>'
                       f'<span class="lt">{esc(m.group(2))}</span><span class="lc">{m.group(3)}</span></div>')
            continue
        m = re.match(r"^- \[ \] \*\*(.+?)\*\* — (.*?)\s*$", ln)
        if m:
            reasons = "".join(f'<div class="lr">{esc(r)}</div>' for r in m.group(2).split("; "))
            out.append(f'<div class="litem"><span class="box"></span><div class="lb">'
                       f'<div class="ln">{esc(m.group(1))}<span class="mono lh">HOST</span></div>{reasons}</div></div>')
            continue
        m = re.match(r"^\s+`(.+?)` · (.*)$", ln)
        if m and out:
            out[-1] = out[-1].replace("HOST", esc(m.group(1)), 1)
    head = re.search(r"(\d+) items scanned, (\d+) flagged", md)
    rest = re.search(r"^(\d+ entries had no evidence of being dead\.)", md, re.M).group(1)
    return f"""
<div class="panel check" style="width:{width}px">
  <div class="lhead"><span class="mono k">cleanup.md</span><span class="chip">{head.group(1)} scanned · {head.group(2)} flagged</span></div>
  <div class="lnote">Nothing has been deleted. Work top-down - tier A is the most certain.</div>
  {''.join(out)}
  <div class="lfoot">Not flagged: {esc(rest)}</div>
</div>"""


def dns_note(width):
    rows = [
        ("Opt-in", "Off unless you pass <span class=\"mono\">--dns</span>. Without it, nothing is looked up."),
        ("One lookup per domain", "Through your system resolver, 20 at a time. No HTTP request is made."),
        ("Local addresses skipped", "<span class=\"mono\">10.x</span>, <span class=\"mono\">192.168.x</span> and <span class=\"mono\">localhost</span> are never resolved."),
    ]
    items = "".join(f'<div class="nrow"><span class="ntick">✓</span><div><div class="nt2">{t}</div>'
                    f'<div class="nl">{d}</div></div></div>' for t, d in rows)
    return f'<div class="panel note" style="width:{width}px"><div class="eyebrow">About the DNS check</div>{items}</div>'


NOTE_CSS = """
.note { padding:20px 22px 8px; }
.nrow { display:flex; gap:12px; padding:13px 0; border-top:1px solid rgba(255,255,255,.07); }
.eyebrow + .nrow { margin-top:12px; }
.ntick { flex:none; width:20px; height:20px; border-radius:6px; display:grid; place-items:center; font:800 11px Inter;
  color:#04201c; background:var(--accent); margin-top:1px; }
.nt2 { font:700 15px Inter; color:#eef2f5; letter-spacing:-.01em; }
.nl { margin-top:3px; font:500 13.5px/1.45 Inter; color:#8e98a4; }
.nl .mono { font-size:12.5px; color:#d6dce3; }
"""


CHECK_CSS = """
.check { padding:20px 22px 16px; }
.lhead { display:flex; justify-content:space-between; align-items:center; }
.lhead .mono { font-size:14px; }
.lnote { margin:10px 0 2px; font:500 13.5px Inter; color:#8e98a4; padding-bottom:12px; border-bottom:1px solid rgba(255,255,255,.07); }
.ltier { display:flex; align-items:center; gap:10px; margin:14px 0 2px; font:700 13px Inter; color:#e6ebf0; letter-spacing:.01em; }
.tier-b { flex:none; width:21px; height:21px; border-radius:6px; display:grid; place-items:center; font:800 12px Inter; color:#04201c; background:var(--accent); }
.lt { flex:1; } .lc { color:#8e98a4; font-weight:600; }
.litem { display:flex; gap:11px; padding:8px 0 8px 2px; border-bottom:1px solid rgba(255,255,255,.045); }
.litem:last-of-type { border-bottom:0; }
.box { flex:none; width:15px; height:15px; margin-top:2px; border-radius:4px; box-shadow:inset 0 0 0 1.5px #4a535e; }
.lb { flex:1; min-width:0; }
.ln { display:flex; align-items:baseline; gap:10px; font:600 14.5px Inter; color:#eef2f5; letter-spacing:-.01em; }
.lh { margin-left:auto; font-size:12px; font-weight:400; color:#7dd3fc; white-space:nowrap; }
.lr { margin-top:2px; font:500 13px/1.4 Inter; color:#9aa4b0; }
.lfoot { margin-top:8px; padding-top:12px; border-top:1px solid rgba(255,255,255,.07); font:500 13px Inter; color:#7d8794; }
"""


def flow_panel(cap, vertical=False):
    steps = [
        ("1", "Plan", "bwtidy.py plan", "Reads the vault, writes plan.json. Changes nothing."),
        ("2", "Review", "plan.json", "Plain JSON. Read it, edit it, delete any line."),
        ("3", "Apply", "bwtidy.py apply", "Re-reads the live vault first and skips anything changed since the plan."),
        ("4", "Verify", "bwtidy.py verify", "SHA-256 of every secret field, before and after."),
        ("undo", "Undo", "revert · restore", "Moves and renames revert. Merges restore from the backup."),
    ]
    nodes = []
    for i, (n, t, cmd, d) in enumerate(steps):
        last = " last" if n == "undo" else ""
        badge = undo(17) if n == "undo" else n
        nodes.append(f'<div class="node{last}"><div class="nbadge">{badge}</div><div class="nt">{t}</div>'
                     f'<div class="mono ncmd">{esc(cmd)}</div><div class="nd">{d}</div></div>')
        if i < len(steps) - 1:
            nodes.append('<div class="link"><span></span></div>')
    verify = cap["tidy_verify"]
    refuse = cap["refuse"].split(". Set ")[0] + "."
    modes = cap["modes"].split("\n")[0]
    bmode = cap["merge_modes"].split("\n")[1]
    tiles = [
        ("Proof, not trust", "verify hashes every secret field and compares it with the plan.", verify),
        ("Loopback-only model", "Any other LM Studio address is refused before a byte is sent.", refuse),
        ("Owner-only files", "Plans, fingerprints and backups are created with mode 600.", modes + "\n" + bmode),
        ("Soft delete", "Deletes go to the Bitwarden trash. Nothing is purged.",
         cap["merge_apply"].split("\n")[-2]),
    ]
    tiles_html = "".join(
        f'<div class="tile"><div class="tt">{t}</div><div class="tp">{prose}</div><pre class="mono tc">'
        + "\n".join(color_line(x) for x in body.split("\n")) + '</pre></div>'
        for t, prose, body in tiles)
    return (f'<div class="flow{" vert" if vertical else ""}">{"".join(nodes)}</div>'
            f'<div class="tiles{" vert" if vertical else ""}">{tiles_html}</div>')


FLOW_CSS = """
.flow { display:flex; align-items:stretch; }
.node { flex:1; position:relative; border-radius:18px; padding:18px 16px 16px; background:linear-gradient(180deg,#13171d,#0e1116);
  box-shadow:0 0 0 1px rgba(255,255,255,.10), 0 30px 60px -30px rgba(0,0,0,.9); }
.node.last { box-shadow:0 0 0 1px rgba(45,212,191,.35), 0 30px 60px -30px rgba(0,0,0,.9); background:linear-gradient(180deg,#10201f,#0c1314); }
.nbadge { width:30px; height:30px; border-radius:9px; display:grid; place-items:center; font:800 15px Inter; color:#04201c;
  background:linear-gradient(135deg,#5eead4,#14b8a6); box-shadow:0 8px 20px -6px rgba(45,212,191,.6); }
.nt { margin-top:14px; font:700 19px Inter; letter-spacing:-.02em; color:#f6f8fa; }
.ncmd { margin-top:6px; font-size:12.5px; color:var(--accent); }
.nd { margin-top:9px; font:500 13.5px/1.45 Inter; color:#8e98a4; letter-spacing:-.005em; }
.link { flex:none; width:26px; display:flex; align-items:center; }
.link span { display:block; width:100%; height:2px; background:linear-gradient(90deg, rgba(45,212,191,.2), rgba(45,212,191,.8)); position:relative; }
.link span::after { content:''; position:absolute; right:-1px; top:-4px; border:5px solid transparent; border-left:7px solid rgba(45,212,191,.9); border-right:0; }
.tiles { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:22px; }
.tile { border-radius:16px; padding:15px 18px 14px; background:#0a0d11; box-shadow:inset 0 0 0 1px rgba(255,255,255,.08); }
.tt { font:700 11.5px Inter; letter-spacing:.12em; text-transform:uppercase; color:#7d8794; }
.tp { margin-top:7px; font:500 14px/1.45 Inter; color:#c9d0d8; letter-spacing:-.005em; text-wrap:pretty; }
.tc { margin-top:10px; padding-top:10px; border-top:1px dashed rgba(255,255,255,.08); font-size:12.5px; line-height:1.6; color:#c3cbd5; white-space:pre-wrap; overflow-wrap:anywhere; }
.flow.vert { flex-direction:column; }
.flow.vert .link { width:auto; height:18px; justify-content:center; }
.flow.vert .link span { width:2px; height:100%; background:linear-gradient(180deg, rgba(45,212,191,.2), rgba(45,212,191,.8)); }
.flow.vert .link span::after { right:-4px; top:auto; bottom:-1px; border:5px solid transparent; border-top:7px solid rgba(45,212,191,.9); border-bottom:0; }
.flow.vert .node { display:grid; grid-template-columns:30px 1fr; column-gap:14px; padding:14px 16px; }
.flow.vert .nbadge { grid-row:span 3; }
.flow.vert .nt { margin-top:2px; font-size:17px; }
.flow.vert .ncmd { margin-top:3px; } .flow.vert .nd { margin-top:5px; }
.tiles.vert { grid-template-columns:1fr; }
"""


def stats(f):
    return [
        (str(f["scripts"]), "Scripts", "one job each"),
        (str(f["checks"]), "Health checks", "before any change"),
        (str(f["tests"]), "End-to-end tests", "on a synthetic vault"),
        (str(f["deps"]), "Dependencies", "Python stdlib only"),
        ("0", "Secrets sent", "to the local model"),
        ("0", "Calls off-machine", "proven by a test"),
    ]


def stat_html(s, n, l, sub, accent=False):
    num, lab, cap = s
    return (f'<div class="stat"><div class="num{" grad" if accent else ""}" style="font-size:{n}px">{num}</div>'
            f'<div class="lab" style="font-size:{l}px">{lab}</div><div class="sub" style="font-size:{sub}px">{cap}</div></div>')


# ---------------------------------------------------------------- scenes --

EXTRA = (SUMMARY_CSS + CHECKS_CSS + DIFF_CSS + TREE_CSS + MODEL_CSS + CHECK_CSS
         + FLOW_CSS + NOTE_CSS)
GLOW_L = "--gx:28%;--gy:-2%;--ax:100%"
GLOW_R = "--gx:72%;--gy:-2%;--ax:0%"
GLOW_M = "--gx:50%;--gy:-3%;--gw:640px;--gh:520px"


def wide(title, glow, inner, pad="48px"):
    return 1200, page(title, 1200, card(1200, glow, f'<div style="padding:{pad}">{inner}</div>'), EXTRA)


def narrow(title, inner, glow=GLOW_M):
    return 540, page(title, 540, card(540, glow,
                     f'<div class="col" style="padding:28px;gap:20px">{inner}</div>'), EXTRA)


def scenes(cap, f):
    S = {}
    audit = cap["audit"].split("\n")
    weak_at = next(i for i, ln in enumerate(audit) if ln.startswith("WEAK PASSWORDS"))
    no2fa_at = next(i for i, ln in enumerate(audit) if ln.startswith("NO SECOND FACTOR"))

    # ---- hero
    hero_term = terminal([("$", "python3 bwaudit.py"), ("out", "\n".join(audit[:weak_at + 4]))],
                         title="bwaudit.py — " + WORKDIR, width=640, fs=13, lh=1.6,
                         cursor=False, fade=170)
    S["hero"] = 1200, page("bwtidy hero", 1200, card(1200, "--gx:50%;--gy:-14%;--gw:1300px;--gh:760px", f"""
<div class="col" style="align-items:center;text-align:center;padding:64px 0 0">{brand(28)}
  <h1 style="margin-top:38px;font-size:70px">Audit and tidy your vault.<br><span class="grad">Nothing leaves your machine.</span></h1>
  <p class="lede" style="margin-top:24px;font-size:20.5px;max-width:860px">Reused and weak passwords, missing 2FA, duplicates and dead entries in Bitwarden or Vaultwarden. Every change is planned, applied and reversible.</p>
  <div class="pills" style="margin-top:30px"><span class="pill go">$ python3 bwaudit.py</span><span class="pill ghost">Local model · standard library · no cloud</span></div>
</div>
<div class="stack" style="margin:48px 0 0 107px;padding-bottom:64px">
  {hero_term}
  <div style="margin:104px 0 0 600px">{summary_panel(f, 386)}</div>
</div>"""), EXTRA)

    S["hero-mobile"] = narrow("bwtidy hero mobile", f"""
<div class="col" style="align-items:center;text-align:center;padding:18px 0 8px">{brand(24, "m")}
  <h1 style="margin-top:28px;font-size:43px">Audit and tidy<br>your vault.<br><span class="grad">Nothing leaves<br>your machine.</span></h1>
  <p class="lede" style="margin-top:18px;font-size:16.5px;max-width:440px">Reused and weak passwords, missing 2FA, duplicates and dead entries in Bitwarden or Vaultwarden. Planned, applied, reversible.</p>
</div>
{summary_panel(f, 484, big=52)}
{terminal([("$", "python3 bwaudit.py"), ("out", chr(10).join(audit[:weak_at - 2]))],
          title="bwaudit.py", width=484, fs=10.6, lh=1.58, cursor=False, fade=90)}""",
        glow="--gx:50%;--gy:-6%;--gw:700px;--gh:620px")

    # ---- numbers
    st = stats(f)
    S["numbers"] = 1200, page("bwtidy numbers", 1200, card(1200, "--gx:50%;--gy:-40%;--gw:1100px;--gh:340px", f"""
<div style="padding:60px 56px 50px;display:grid;grid-template-columns:.8fr 1.05fr 1.15fr 1.05fr 1.05fr 1.15fr;column-gap:26px;align-items:start">
{''.join(stat_html(s, 58, 16.5, 13.5, accent=(i == len(st) - 1)) for i, s in enumerate(st))}</div>"""), EXTRA)
    S["numbers-mobile"] = 540, page("bwtidy numbers mobile", 540, card(540, "--gx:50%;--gy:-12%;--gw:620px;--gh:420px", f"""
<div class="stack-grid" style="padding:46px 44px;display:grid;grid-template-columns:1fr 1fr;row-gap:40px;column-gap:24px">
{''.join(stat_html(s, 58, 17, 13.5, accent=(i == len(st) - 1)) for i, s in enumerate(st))}</div>"""), EXTRA)

    # ---- audit
    S["audit"] = wide("bwtidy audit", GLOW_L, f"""
<div class="row" style="gap:24px;align-items:center">
  {terminal([("$", "python3 bwaudit.py"), ("out", cap["audit"])], title="bwaudit.py — " + WORKDIR, width=680, fs=12, lh=1.5)}
  {checks_panel(f, 400)}
</div>""")
    S["audit-mobile"] = narrow("bwtidy audit mobile", f"""
{checks_panel(f, 484)}
{terminal([("out", chr(10).join(audit[no2fa_at - 1:]))], title="bwaudit.py", width=484,
          fs=10.6, lh=1.55, wrap=True, top_fade=30)}""")

    # ---- merge
    m_blocks = [("$", "python3 bwmerge.py plan"), ("out", cap["merge_plan"]),
                ("$", "python3 bwmerge.py apply"), ("out", cap["merge_apply"]),
                ("$", "python3 bwpolish.py | head -8"), ("out", cap["polish_head"])]
    S["merge"] = wide("bwtidy merge", GLOW_R, f"""
<div class="stack">
  {terminal(m_blocks, title="bwmerge.py — " + WORKDIR, width=720, fs=12.5, lh=1.55)}
  <div style="margin:352px 0 0 612px">{diff_panel(cap, 492)}</div>
</div>""")
    S["merge-mobile"] = narrow("bwtidy merge mobile", f"""
{diff_panel(cap, 484)}
{terminal([("$", "python3 bwmerge.py apply"), ("out", cap["merge_apply"])],
          title="bwmerge.py", width=484, fs=10.6, lh=1.55, wrap=True)}""")

    # ---- folders
    t_blocks = [("$", "python3 bwtidy.py plan"), ("out", cap["tidy_plan"]),
                ("$", "python3 bwtidy.py apply | tail -1"), ("out", cap["tidy_apply_tail"]),
                ("$", "python3 bwtidy.py verify"), ("out", cap["tidy_verify"])]
    S["folders"] = wide("bwtidy folders", GLOW_L, f"""
<div class="row" style="gap:24px;align-items:stretch">
  <div class="col" style="gap:24px">
    {terminal(t_blocks, title="bwtidy.py — " + WORKDIR, width=540, fs=12.2, lh=1.55)}
    {model_panel(cap, 540)}
  </div>
  {tree_panel(cap, 540)}
</div>""")
    S["folders-mobile"] = narrow("bwtidy folders mobile", f"""
{tree_panel(cap, 484)}
{model_panel(cap, 484)}""")

    # ---- flow
    S["flow"] = wide("bwtidy flow", "--gx:50%;--gy:-20%;--gw:1200px;--gh:520px", flow_panel(cap))
    S["flow-mobile"] = narrow("bwtidy flow mobile", flow_panel(cap, vertical=True))

    # ---- dead
    d_blocks = [("$", "python3 bwdead.py --dns"), ("out", cap["dead"])]
    S["dead"] = wide("bwtidy dead", GLOW_R, f"""
<div class="row" style="gap:24px;align-items:flex-start">
  {checklist_panel(cap, 540)}
  <div class="col" style="gap:24px;margin-top:56px">
    {terminal(d_blocks, title="bwdead.py — " + WORKDIR, width=540, fs=12, lh=1.6)}
    {dns_note(540)}
  </div>
</div>""")
    S["dead-mobile"] = narrow("bwtidy dead mobile", f"""
{terminal(d_blocks, title="bwdead.py", width=484, fs=10.6, lh=1.55, wrap=True)}
{checklist_panel(cap, 484)}""")

    # ---- social preview (1280x640, full bleed)
    S["social"] = 1280, page("bwtidy social", 1280, f"""
<div class="card" style="width:1280px;height:640px;border-radius:0;--gx:28%;--gy:-30%;--gw:1100px;--gh:700px">
  <div class="abs" style="left:84px;top:70px;width:660px">{brand(44, "s")}
    <h1 style="margin-top:34px;font-size:58px;line-height:1.02">Audit and tidy<br>your vault.<br><span class="grad">Nothing leaves<br>your machine.</span></h1>
    <p class="lede" style="margin-top:24px;font-size:24px;max-width:600px">Reused and weak passwords, missing 2FA, duplicates and dead entries in Bitwarden or Vaultwarden.</p>
  </div>
  <div class="abs" style="left:790px;top:118px">{summary_panel(f, 410, big=62)}</div>
</div>""", EXTRA)
    return S



# ==========================================================================
# 3. render
# ==========================================================================

def render(name, width, html_path):
    tmp = tempfile.mkdtemp(prefix="bwtidy-shot-")
    png = os.path.join(tmp, "shot.png")
    height = 640 if name == "social" else 2400
    subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=2",
                    "--virtual-time-budget=8000", "--default-background-color=00000000",
                    f"--window-size={width},{height}", f"--screenshot={png}",
                    "file://" + html_path], check=True, capture_output=True)
    if name == "social":
        subprocess.run(["magick", png, "-resize", "1280x640", "-strip",
                        os.path.join(OUT, "social.png")], check=True)
    else:
        subprocess.run(["magick", png, "-trim", "+repage", "-strip", "-quality", "86",
                        "-define", "webp:method=6", os.path.join(OUT, f"{name}.webp")], check=True)
    shutil.rmtree(tmp)


def main():
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    cap = capture()
    f = facts(cap)
    print("facts:", json.dumps(f))
    os.makedirs(SRC, exist_ok=True)
    for name, (width, doc) in scenes(cap, f).items():
        if only and name not in only:
            continue
        path = os.path.join(SRC, f"{name}.html")
        with open(path, "w") as fh:
            fh.write(doc)
        if "--html" not in sys.argv:
            render(name, width, path)
            print("rendered", name)


if __name__ == "__main__":
    main()

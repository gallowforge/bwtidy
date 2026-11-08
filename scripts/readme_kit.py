"""
The drawing kit for the README images: one key board, drawn in code.

Identity (docs/readme/IDENTITY.md): a vault is a key board, and bwtidy is the
tidy friend who puts every key back on its own labelled hook. The board is
painted mint inside a brushed steel cabinet, keys are brass, real output sits
on dark vault-steel plates, and the friend's notes are pencil on kraft tags.
One type family, Recursive: Casual for the friend, Linear for the facts, Mono
for real output.

Everything here is presentation. Every name, number and line of output that a
scene shows comes from the capture in readme_visuals.py.
"""

import hashlib
import html
import math

# --------------------------------------------------------------- palette --
MINT = "#b6e2cd"
MINT_HI = "#d3efe1"
MINT_LO = "#86c6ab"
MINT_INK = "#1f5442"
STEEL_950 = "#0f1619"
STEEL_900 = "#162024"
STEEL_800 = "#1e2a2f"
STEEL_600 = "#465860"
STEEL_400 = "#7f929a"
STEEL_200 = "#c8d2d7"
BRASS_HI = "#f7df9e"
BRASS = "#d6a64a"
BRASS_LO = "#6e4f17"
KRAFT = "#e9d8b4"
PENCIL = "#2c3a35"
CORAL = "#e9846b"


def esc(s):
    return html.escape(str(s), quote=False)


def wobble(seed, lo=-1.0, hi=1.0):
    """A stable pseudo-random number for a string, so renders never jitter."""
    h = int(hashlib.sha256(str(seed).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return lo + (hi - lo) * h


# ------------------------------------------------------------------ fonts --
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Recursive:slnt,wght,CASL,CRSV,MONO'
         '@-15..0,300..1000,0..1,0..1,0..1&display=block" rel="stylesheet">')

NOISE_PAINT = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='260' height='260'%3E"
               "%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E"
               "%3CfeColorMatrix values='0 0 0 0 .05  0 0 0 0 .25  0 0 0 0 .18  0 0 0 .075 0'/%3E%3C/filter%3E"
               "%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")")
NOISE_BRUSH = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='300'%3E"
               "%3Cfilter id='b'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.002 .75' numOctaves='3' stitchTiles='stitch'/%3E"
               "%3CfeColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .55 -.2'/%3E%3C/filter%3E"
               "%3Crect width='100%25' height='100%25' filter='url(%23b)'/%3E%3C/svg%3E\")")
NOISE_PAPER = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E"
               "%3Cfilter id='p'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.6' numOctaves='3' stitchTiles='stitch'/%3E"
               "%3CfeColorMatrix values='0 0 0 0 .35  0 0 0 0 .25  0 0 0 0 .1  0 0 0 .16 0'/%3E%3C/filter%3E"
               "%3Crect width='100%25' height='100%25' filter='url(%23p)'/%3E%3C/svg%3E\")")

CSS = """
:root { --mint:%(MINT)s; --mint-hi:%(MINT_HI)s; --mint-lo:%(MINT_LO)s; --mint-ink:%(MINT_INK)s;
  --s950:%(STEEL_950)s; --s900:%(STEEL_900)s; --s800:%(STEEL_800)s; --s600:%(STEEL_600)s; --s400:%(STEEL_400)s; --s200:%(STEEL_200)s;
  --brass-hi:%(BRASS_HI)s; --brass:%(BRASS)s; --brass-lo:%(BRASS_LO)s; --kraft:%(KRAFT)s; --pencil:%(PENCIL)s; --coral:%(CORAL)s; }
* { box-sizing:border-box; margin:0; padding:0; }
html, body { background:transparent; }
body { font-family:Recursive, sans-serif; color:var(--s900); -webkit-font-smoothing:antialiased;
  font-variation-settings:"CASL" 0, "MONO" 0; }
.abs { position:absolute; }
.casual { font-variation-settings:"CASL" 1, "MONO" 0; }
.mono { font-variation-settings:"MONO" 1, "CASL" 0; font-variant-ligatures:none; }
.hand { font-variation-settings:"CASL" 1, "MONO" 0, "slnt" -11, "CRSV" 1; }
svg { overflow:visible; }

/* the cabinet: brushed steel frame, painted mint panel */
.cab { position:relative; border-radius:18px; padding:14px; isolation:isolate;
  background:%(NOISE_BRUSH)s, linear-gradient(170deg, #e3e9ec 0%%, #bcc7cc 38%%, #d2dade 58%%, #a6b2b8 100%%);
  box-shadow:inset 0 1.5px 0 rgba(255,255,255,.85), inset 0 -1.5px 0 rgba(0,0,0,.22), inset 0 0 0 1px rgba(60,75,82,.55); }
.panel { position:relative; height:100%%; border-radius:7px; overflow:hidden;
  background:%(NOISE_PAINT)s, linear-gradient(118deg, rgba(255,255,255,.20) 0%%, rgba(255,255,255,0) 38%%, rgba(0,50,35,.05) 100%%),
    linear-gradient(178deg, #c3e8d6 0%%, var(--mint) 45%%, #acdcc5 100%%);
  box-shadow:inset 0 3px 7px rgba(10,40,30,.32), inset 0 0 0 1px rgba(10,40,30,.30), inset 0 -1px 0 rgba(255,255,255,.4); }
.screw { position:absolute; width:9px; height:9px; border-radius:50%%;
  background:radial-gradient(circle at 35%% 30%%, #f6f8f9, #9eabb1 60%%, #63737a);
  box-shadow:0 .5px 0 rgba(255,255,255,.7), inset 0 0 0 .5px rgba(40,50,55,.6); }
.screw::after { content:''; position:absolute; left:1.5px; right:1.5px; top:4px; height:1px; background:rgba(40,50,55,.7);
  transform:rotate(var(--sr, 35deg)); }

/* type */
.h1 { font-variation-settings:"CASL" 1, "MONO" 0; font-weight:880; letter-spacing:-.035em; line-height:.96; color:var(--s900); }
.lede { font-weight:500; line-height:1.42; color:#24493d; letter-spacing:-.006em; text-wrap:pretty; }
.kicker { font-variation-settings:"MONO" 1, "CASL" 0; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--mint-ink); }

/* steel rails */
.rail { position:absolute; border-radius:5px;
  background:%(NOISE_BRUSH)s, linear-gradient(180deg, #eef2f4 0%%, #c7d1d6 30%%, #aab6bc 70%%, #8c9aa1 100%%);
  box-shadow:0 0 0 .8px rgba(50,64,70,.65), inset 0 1px 0 rgba(255,255,255,.9), 0 3px 5px rgba(8,45,34,.32), 0 9px 16px -8px rgba(8,45,34,.35); }

/* label-maker tape */
.dymo { position:absolute; white-space:nowrap; border-radius:2.5px; padding:.32em .62em .26em;
  font-weight:780; letter-spacing:.11em; text-transform:uppercase; line-height:1; color:#f2f1ea;
  background:linear-gradient(180deg, #343b3f 0%%, #1a1f22 46%%, #111517 100%%);
  text-shadow:0 -.6px 0 rgba(0,0,0,.9), 0 .9px 0 rgba(255,255,255,.16);
  box-shadow:0 1.5px 2.5px rgba(8,45,34,.38), 0 0 0 .5px rgba(0,0,0,.7), inset 0 .5px 0 rgba(255,255,255,.18); }
.dymo.c { transform:translateX(-50%%) rotate(var(--r, 0deg)); }
.dymo.mint { color:#0f3a2d; text-shadow:0 .9px 0 rgba(255,255,255,.35);
  background:linear-gradient(180deg, #8fe0bd, #5ec79c 50%%, #4fb68d); }
.dymo.brass { color:#3b2a0c; text-shadow:0 .9px 0 rgba(255,240,200,.5);
  background:linear-gradient(180deg, #f3d891, #d6a64a 55%%, #b98a32); }

/* kraft tags and pencil notes */
.tagw { position:absolute; transform-origin:0 50%%; filter:drop-shadow(1px 2.5px 1.5px rgba(8,45,34,.30)); }
.tag { position:relative; display:inline-block; white-space:nowrap; padding:0 .8em 0 1.9em;
  background:%(NOISE_PAPER)s, linear-gradient(180deg, #f1e3c4, #e4d0a8);
  clip-path:polygon(.7em 0, 100%% 0, 100%% 100%%, .7em 100%%, 0 72%%, 0 28%%);
  color:var(--pencil); font-weight:640; letter-spacing:-.005em; }
.tag::before { content:''; position:absolute; left:.55em; top:50%%; width:.62em; height:.62em; margin-top:-.31em; border-radius:50%%;
  background:var(--mint); box-shadow:0 0 0 .16em #cdb98f, inset 0 1px 1px rgba(0,0,0,.25); }
.note { position:absolute; color:var(--pencil); font-weight:620; line-height:1.15; }

/* vault-steel plates for real output */
.plate { position:absolute; border-radius:12px; overflow:hidden;
  background:repeating-linear-gradient(0deg, rgba(255,255,255,.014) 0 1px, transparent 1px 3px),
             linear-gradient(180deg, #1f2b30, #141c20 70%%);
  box-shadow:0 0 0 1px #0a1012, inset 0 1px 0 rgba(255,255,255,.09), 0 26px 44px -20px rgba(6,45,33,.6), 0 9px 16px -9px rgba(6,45,33,.45); }
.plate .ph { position:relative; height:32px; display:flex; align-items:center; gap:10px; padding:0 30px;
  border-bottom:1px solid rgba(255,255,255,.055); background:linear-gradient(180deg, rgba(255,255,255,.035), transparent);
  font-variation-settings:"MONO" 1, "CASL" 0; font-size:11.5px; font-weight:500; letter-spacing:.02em; color:#71848c; }
.plate .ph .screw { top:11.5px; width:9px; height:9px; background:radial-gradient(circle at 35%% 30%%, #9fb0b7, #50636b 60%%, #2b3a40);
  box-shadow:inset 0 0 0 .5px rgba(0,0,0,.6); }
.plate .ph .screw.l { left:11px; } .plate .ph .screw.r { right:11px; }
.plate .ph b { color:#a7b8bf; font-weight:600; }
.plate .ph .tail { margin-left:auto; }
.term { font-variation-settings:"MONO" 1, "CASL" 0; font-variant-ligatures:none; font-size:var(--fs); line-height:var(--lh);
  color:#c3cfd4; padding:14px 20px 16px; white-space:pre; overflow:hidden; }
.term.wrap { white-space:pre-wrap; overflow-wrap:anywhere; }
.term.wrap .rule { display:inline-block; max-width:100%%; overflow:hidden; vertical-align:top; white-space:pre; }
.pr.gap { display:inline-block; margin-top:8px; }
.pp { color:#8fe3bf; } .pd { color:#56676e; } .pc { color:#ffffff; font-weight:700; }
.cur { background:#8fe3bf; opacity:.85; }
.rule { color:#33434a; } .h { color:#ffffff; font-weight:700; } .h2 { color:#e3eaed; }
.m { color:#7a8c94; } .d { color:#53646b; } .b { color:#ffffff; font-weight:700; }
.n { color:#f3cf7a; font-weight:700; } .w { color:#e8b85c; } .r { color:var(--coral); }
.g { color:#8fe3bf; } .u { color:#a9cbdb; } .us { color:#a3b3ba; } .f { color:#bfe9d6; }
.k { color:#f3d896; } .c { color:#ffffff; } .a { color:#8fe3bf; }
.tier { color:#0f3a2d; background:#8fe3bf; font-weight:700; border-radius:3px; padding:0 .32em; margin:0 -.32em; }
.ell { color:#53646b; }

/* paper sheets */
.sheet { position:absolute; background:%(NOISE_PAPER)s, linear-gradient(180deg, #fbf8f0, #f1ece0);
  box-shadow:0 1px 0 rgba(255,255,255,.6) inset, 0 22px 34px -18px rgba(6,45,33,.55), 0 4px 8px -4px rgba(6,45,33,.35); }
""" % dict(globals())


def page(title, width, inner, height=None, extra_css=""):
    h = f"height:{height}px;" if height else ""
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<title>{esc(title)}</title>{FONTS}<style>{CSS}{extra_css}</style></head>'
            f'<body style="width:{width}px;{h}">\n{SVG_DEFS}\n{inner}\n</body></html>\n')


def cabinet(width, height, inner, screws=True, radius=None, pad=14):
    """The steel cabinet with its mint panel. `inner` is positioned in panel px."""
    sc = ""
    if screws:
        e = pad / 2 - 2
        for i, (x, y) in enumerate(((e, e), (width - 9 - e, e), (e, height - 9 - e), (width - 9 - e, height - 9 - e))):
            sc += f'<i class="screw" style="left:{x}px;top:{y}px;--sr:{[35, -20, 70, 10][i]}deg"></i>'
    r = f"border-radius:{radius}px;" if radius is not None else ""
    r += f"padding:{pad}px;" if pad != 14 else ""
    return (f'<div class="cab" style="width:{width}px;height:{height}px;{r}">{sc}'
            f'<div class="panel">{inner}</div></div>')


# --------------------------------------------------------------- svg defs --
SVG_DEFS = """<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
<linearGradient id="brass" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#fbe8b0"/><stop offset=".22" stop-color="#efc76c"/>
  <stop offset=".58" stop-color="#d5a246"/><stop offset=".86" stop-color="#b3832f"/><stop offset="1" stop-color="#8c6220"/></linearGradient>
<linearGradient id="brassDull" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#ece0bd"/><stop offset=".4" stop-color="#cdb47a"/><stop offset="1" stop-color="#8f7a4a"/></linearGradient>
<linearGradient id="steelRod" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#5f6f77"/><stop offset=".35" stop-color="#eef3f5"/><stop offset=".7" stop-color="#a5b3b9"/><stop offset="1" stop-color="#52626a"/></linearGradient>
<radialGradient id="rosette" cx=".36" cy=".3" r=".85">
  <stop offset="0" stop-color="#ffffff"/><stop offset=".45" stop-color="#c3ced3"/><stop offset="1" stop-color="#5d6d75"/></radialGradient>
<linearGradient id="fob" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#2d3b41"/><stop offset=".5" stop-color="#1b252a"/><stop offset="1" stop-color="#10171a"/></linearGradient>
<linearGradient id="fobMint" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#9fe6c6"/><stop offset=".5" stop-color="#63c89f"/><stop offset="1" stop-color="#3f9f7a"/></linearGradient>
<linearGradient id="card" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#d9b47a"/><stop offset="1" stop-color="#b98f55"/></linearGradient>
<linearGradient id="cardSide" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#a87f47"/><stop offset="1" stop-color="#c49a5e"/></linearGradient>
<linearGradient id="bin" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#6d7d85"/><stop offset=".3" stop-color="#e3e9ec"/><stop offset=".55" stop-color="#b4c0c6"/><stop offset="1" stop-color="#5a6970"/></linearGradient>
<filter id="sh" x="-40%" y="-40%" width="180%" height="180%">
  <feDropShadow dx="2.6" dy="5.5" stdDeviation="2.8" flood-color="#08392a" flood-opacity=".30"/></filter>
<filter id="shs" x="-60%" y="-60%" width="220%" height="220%">
  <feDropShadow dx="1.2" dy="2.2" stdDeviation="1.2" flood-color="#08392a" flood-opacity=".38"/></filter>
<filter id="shl" x="-30%" y="-30%" width="160%" height="160%">
  <feDropShadow dx="4" dy="12" stdDeviation="9" flood-color="#08392a" flood-opacity=".32"/></filter>
</defs></svg>"""


# ------------------------------------------------------------------- keys --
PIN_Y = (39, 48, 57, 66, 75)


def key_path(cuts=(2, 4, 1, 3, 2), half=7.0, tip=84.0, bow=18.0):
    """Outline of a pin-tumbler key hanging bow-up, hole centred on (0, 0)."""
    pts = [f"M 0 -10 C {bow * .67:.1f} -10 {bow} -6 {bow} 4 L {bow} 15",
           f"C {bow} 22 {bow * .78:.1f} 26 {half + 1} 26.5 L {half} 27 L {half + 3} 29.5 L {half + 3} 33 L {half} 33"]
    ys = PIN_Y[:len(cuts)] if tip > 80 else [39 + i * 9 for i in range(len(cuts))]
    for y, d in zip(ys, cuts):
        depth = 1.15 * d
        if y + 4.6 > tip:
            break
        pts.append(f"L {half} {y - 4.4} L {half - depth:.1f} {y - .8} L {half - depth:.1f} {y + .8} L {half} {y + 4.4}")
    pts.append(f"L {half} {tip} L {half - 6} {tip + 9.5} L {-half + 4} {tip + 9.5} L {-half} {tip + 5} L {-half} 27 L {-half - 1} 26.5")
    pts.append(f"C {-bow * .78:.1f} 26 {-bow} 22 {-bow} 15 L {-bow} 4 C {-bow} -6 {-bow * .67:.1f} -10 0 -10 Z")
    pts.append("M 4.4 0 A 4.4 4.4 0 1 0 -4.4 0 A 4.4 4.4 0 1 0 4.4 0 Z")
    return " ".join(pts)


def key(cuts=(2, 4, 1, 3, 2), stamp="", flimsy=False, fill="url(#brass)", extra=""):
    """A key in its own coordinates (hole at 0,0). Wrap it in a transform."""
    st = ""
    if stamp:
        sy = 16.4 if flimsy else 18
        st = (f'<text x=".5" y="{sy + .6}" text-anchor="middle" font-size="{7.6 if flimsy else 8.4}" font-weight="800" fill="#fff2c4" opacity=".55" '
              f'style="font-variation-settings:\'MONO\' 1">{esc(stamp)}</text>'
              f'<text x="0" y="{sy}" text-anchor="middle" font-size="{7.6 if flimsy else 8.4}" font-weight="800" fill="{"#6f5b2a" if flimsy else "#7d5716"}" opacity=".85" '
              f'style="font-variation-settings:\'MONO\' 1">{esc(stamp)}</text>')
    if flimsy:
        # a thin, short, bent blank: the weak password
        blade = key_path(cuts[:2], half=4.3, tip=62, bow=15)
        body = (f'<g transform="rotate(9 0 30)"><path d="{blade}" fill="url(#brassDull)" fill-rule="evenodd" '
                f'stroke="#7a6633" stroke-width=".9" stroke-linejoin="round"/>'
                f'<path d="M -1.2 31 L -1.2 64" stroke="#8a7440" stroke-width=".9" opacity=".6"/>'
                f'<path d="M 4.3 47 L 1.6 48.6" stroke="#7a6633" stroke-width=".8" opacity=".7"/>'
                f'<ellipse cx="-5" cy="3" rx="6" ry="3.6" fill="#fff" opacity=".22" transform="rotate(-22 -5 3)"/>{st}</g>')
        return f'<g class="key">{body}{extra}</g>'
    d = key_path(cuts)
    return (f'<g class="key"><path d="{d}" fill="{fill}" fill-rule="evenodd" stroke="{BRASS_LO}" stroke-width="1" stroke-linejoin="round"/>'
            f'<path d="M -2.3 31 L -2.3 {88}" stroke="#7d5716" stroke-width="1.3" opacity=".5"/>'
            f'<path d="M -3.6 31 L -3.6 {88}" stroke="#fff3c8" stroke-width=".7" opacity=".55"/>'
            f'<ellipse cx="-6.5" cy="3.5" rx="7.5" ry="4.4" fill="#fff" opacity=".26" transform="rotate(-24 -6.5 3.5)"/>'
            f'{st}{extra}</g>')


def ring(r=8.0):
    """Split ring hanging from a peg at (0,0); returns (back, front, key_hole_y)."""
    cy = 4.5 + r
    back = (f'<circle cx="0" cy="{cy}" r="{r}" fill="none" stroke="#6f8088" stroke-width="2.3"/>'
            f'<circle cx="0" cy="{cy}" r="{r}" fill="none" stroke="#e6edf0" stroke-width=".7" stroke-dasharray="{r * 2.2:.1f} {r * 5:.1f}" stroke-dashoffset="{r * 4.2:.1f}"/>')
    hole_y = cy + r + 3.4
    a0 = math.asin(min(.99, (hole_y - 10 - cy) / r))
    x0 = r * math.cos(a0)
    front = (f'<path d="M {x0:.2f} {hole_y - 10:.2f} A {r} {r} 0 0 1 0 {cy + r:.2f}" fill="none" stroke="#7d8e96" stroke-width="2.3" stroke-linecap="round"/>'
             f'<path d="M {x0 - .5:.2f} {hole_y - 10.3:.2f} A {r} {r} 0 0 1 0 {cy + r - .7:.2f}" fill="none" stroke="#eef3f5" stroke-width=".6" opacity=".9"/>')
    return back, front, hole_y


def hook_back(size=1.0):
    return (f'<g filter="url(#shs)"><circle r="{6.2 * size:.1f}" fill="url(#rosette)" stroke="#55656d" stroke-width=".8"/>'
            f'<path d="M {-3.4 * size:.1f} {-1.2 * size:.1f} L {3.4 * size:.1f} {1.2 * size:.1f}" stroke="#4d5c63" stroke-width="1.1" stroke-linecap="round"/></g>')


def hook_peg():
    return ('<path d="M 0 0 L 0 6.8" stroke="url(#steelRod)" stroke-width="3.6" stroke-linecap="round"/>'
            '<path d="M 0 6.6 Q 0 8.6 1.8 7.6" stroke="#7d8e96" stroke-width="2" fill="none" stroke-linecap="round"/>')


def hung(x, y, scale=1.0, keys=(), angle=0.0, empty=False, ring_r=8.0, under=""):
    """A hook at (x, y) with keys on a ring. keys: list of (svg_key, rotation)."""
    back, front, hole_y = ring(ring_r)
    out = [f'<g transform="translate({x:.1f} {y:.1f}) scale({scale})">', hook_back()]
    if not empty and keys:
        out.append(f'<g transform="rotate({angle:.1f})" filter="url(#sh)">{back}')
        for k, rot in keys:
            out.append(f'<g transform="rotate({rot:.1f} 0 {hole_y - 6:.1f}) translate(0 {hole_y:.1f})">{k}</g>')
        out.append(f'{front}{under}</g>')
    out.append(hook_peg())
    out.append('</g>')
    return "".join(out)


def string_path(x1, y1, x2, y2, sag=10):
    mx, my = (x1 + x2) / 2, max(y1, y2) + sag
    return (f'<path d="M {x1:.1f} {y1:.1f} Q {mx:.1f} {my:.1f} {x2:.1f} {y2:.1f}" fill="none" '
            f'stroke="#a3876a" stroke-width="1.1" stroke-linecap="round"/>')


def tag(x, y, text, size=14, rot=6, height=None, cls=""):
    """Kraft tag whose hole sits on (x, y)."""
    h = height or round(size * 1.85)
    return (f'<div class="tagw" style="left:{x - size * .86:.1f}px;top:{y - h / 2:.1f}px;transform:rotate({rot}deg);'
            f'transform-origin:{size * .86:.1f}px 50%"><span class="tag hand {cls}" '
            f'style="font-size:{size}px;height:{h}px;line-height:{h}px">{text}</span></div>')


def dymo(x, y, text, size=12, rot=0.0, cls="", center=True, jitter=False):
    """Embossed label-maker tape. jitter nudges each letter like a real hand-cranked label."""
    c = " c" if center else ""
    if jitter:
        body = "".join(f'<i style="display:inline-block;font-style:normal;transform:translateY({wobble(text + str(i), -.045, .045):.3f}em)">'
                       f'{esc(ch) if ch != " " else "&nbsp;"}</i>' for i, ch in enumerate(text))
    else:
        body = esc(text)
    return (f'<span class="dymo{c} {cls}" style="left:{x:.1f}px;top:{y:.1f}px;font-size:{size}px;--r:{rot}deg">'
            f'{body}</span>')


def rail(x, y, width, height=30, screws=True):
    """A brushed steel rail screwed to the board; hooks hang from its lower edge."""
    sc = ""
    if screws:
        sc = (f'<i class="screw" style="left:8px;top:{height / 2 - 4.5:.1f}px;--sr:20deg"></i>'
              f'<i class="screw" style="right:8px;top:{height / 2 - 4.5:.1f}px;--sr:-40deg"></i>')
    return (f'<div class="rail" style="left:{x:.1f}px;top:{y:.1f}px;width:{width:.1f}px;height:{height}px">{sc}</div>')


def bolts(x, y, filled=(True, False), scale=1.0, label=True):
    """The second-bolt plate: a strike plate with two bolts. A missing bolt is 2FA missing."""
    out = [f'<g transform="translate({x:.1f} {y:.1f}) scale({scale})" filter="url(#shs)">',
           '<rect x="-9" y="-19" width="18" height="38" rx="3.5" fill="url(#rosette)" stroke="#55656d" stroke-width=".8"/>']
    for i, on in enumerate(filled):
        cy = -9 + i * 18
        if on:
            out.append(f'<rect x="-5.2" y="{cy - 4.6}" width="10.4" height="9.2" rx="2" fill="url(#brass)" stroke="{BRASS_LO}" stroke-width=".8"/>'
                       f'<rect x="-3.6" y="{cy - 3.2}" width="3" height="6.4" rx="1" fill="#fff" opacity=".35"/>')
        else:
            out.append(f'<rect x="-5.2" y="{cy - 4.6}" width="10.4" height="9.2" rx="2" fill="#1b2529" stroke="#0d1416" stroke-width=".8"/>'
                       f'<rect x="-7.4" y="{cy - 6.8}" width="14.8" height="13.6" rx="3" fill="none" stroke="{CORAL}" stroke-width="1.3" stroke-dasharray="2.4 2"/>')
    for sy in (-16, 16):
        out.append(f'<circle cx="0" cy="{sy}" r="1.3" fill="#7b8a91"/>')
    out.append('</g>')
    return "".join(out)


def cobweb(x, y, r=34, flip=False, spider=True):
    """A corner cobweb anchored at (x, y), opening down-right (or down-left)."""
    sx = -1 if flip else 1
    spokes, rings = [], []
    angles = [0, 22, 45, 68, 90]
    for a in angles:
        t = math.radians(a)
        spokes.append(f'M 0 0 L {sx * r * math.cos(t):.1f} {r * math.sin(t):.1f}')
    for f in (.32, .55, .78, 1.0):
        p = []
        for i, a in enumerate(angles):
            t = math.radians(a)
            px, py = sx * r * f * math.cos(t), r * f * math.sin(t)
            if i == 0:
                p.append(f"M {px:.1f} {py:.1f}")
            else:
                tm = math.radians((a + angles[i - 1]) / 2)
                qx, qy = sx * r * f * .86 * math.cos(tm), r * f * .86 * math.sin(tm)
                p.append(f"Q {qx:.1f} {qy:.1f} {px:.1f} {py:.1f}")
        rings.append(" ".join(p))
    sp = ""
    if spider:
        tx, ty = sx * r * .62, r * .62 + 26
        sp = (f'<path d="M {sx * r * .62:.1f} {r * .62:.1f} L {tx:.1f} {ty - 3:.1f}" stroke="#ffffff" stroke-width=".6" opacity=".8"/>'
              f'<g transform="translate({tx:.1f} {ty:.1f})" stroke="#1d2a2e" stroke-width=".9" stroke-linecap="round" fill="none">'
              f'<path d="M -2 -1 L -5.5 -4 L -7 -1 M -2 0 L -6 0 L -7.5 2.5 M -2 1 L -5 3.5 L -5.5 6 M 2 -1 L 5.5 -4 L 7 -1 '
              f'M 2 0 L 6 0 L 7.5 2.5 M 2 1 L 5 3.5 L 5.5 6"/><ellipse rx="2.6" ry="3.1" fill="#1d2a2e" stroke="none"/>'
              f'<circle cy="-3.4" r="1.6" fill="#1d2a2e" stroke="none"/></g>')
    return (f'<g transform="translate({x:.1f} {y:.1f})" fill="none" stroke="#ffffff" stroke-linecap="round" opacity=".85">'
            f'<path d="{" ".join(spokes)}" stroke-width=".8"/><path d="{" ".join(rings)}" stroke-width=".65"/></g>'
            f'<g transform="translate({x:.1f} {y:.1f})">{sp}</g>')


def pencil_loop(x1, y1, x2, y2, lift=40, arrow=True, color=PENCIL, width=1.6):
    """A hand-drawn arc between two points, a pencil note's arrow."""
    mx = (x1 + x2) / 2
    my = min(y1, y2) - lift
    d = f"M {x1:.1f} {y1:.1f} Q {mx:.1f} {my:.1f} {x2:.1f} {y2:.1f}"
    out = f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-dasharray="0.1 0" opacity=".9"/>'
    if arrow:
        ang = math.atan2(y2 - my, x2 - mx)
        a1, a2 = ang + math.radians(150), ang - math.radians(150)
        out += (f'<path d="M {x2 + 9 * math.cos(a1):.1f} {y2 + 9 * math.sin(a1):.1f} L {x2:.1f} {y2:.1f} '
                f'L {x2 + 9 * math.cos(a2):.1f} {y2 + 9 * math.sin(a2):.1f}" fill="none" stroke="{color}" '
                f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')
    return out


def svg_layer(width, height, body, z=1):
    return (f'<svg class="abs" style="left:0;top:0;z-index:{z}" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" aria-hidden="true">{body}</svg>')


# ------------------------------------------------------------ steel plate --
def plate(x, y, width, title, body_html, fs=12.5, lh=1.55, tail="", wrap=False, z=5, height=None, extra_style=""):
    cls = "term wrap" if wrap else "term"
    h = f"height:{height}px;" if height else ""
    t = f'<span class="tail">{tail}</span>' if tail else ""
    return (f'<div class="plate" style="left:{x}px;top:{y}px;width:{width}px;{h}z-index:{z};{extra_style}">'
            f'<div class="ph"><i class="screw l"></i><b>{esc(title)}</b>{t}<i class="screw r"></i></div>'
            f'<pre class="{cls}" style="--fs:{fs}px;--lh:{lh}">{body_html}</pre></div>')


# ------------------------------------------------------------------ board --
class Board:
    """Layers of one scene, back to front, all in panel pixels."""

    def __init__(self, width, height):
        self.w, self.h = width, height
        self.base = []    # html: rails, labels on rails
        self.back = []    # svg: strings, cobwebs, things behind keys
        self.mid = []     # svg: hooks, keys, objects
        self.over = []    # html: kraft tags
        self.front = []   # svg: pencil marks
        self.top = []     # html: words, plates, sheets

    def html(self):
        return ("".join(self.base)
                + svg_layer(self.w, self.h, "".join(self.back), 1)
                + svg_layer(self.w, self.h, "".join(self.mid), 2)
                + f'<div class="abs" style="left:0;top:0;right:0;bottom:0;z-index:3">{"".join(self.over)}</div>'
                + svg_layer(self.w, self.h, "".join(self.front), 4)
                + f'<div class="abs" style="left:0;top:0;right:0;bottom:0;z-index:5">{"".join(self.top)}</div>')


def pencil_arrow(x1, y1, x2, y2, bend=-20, both=False, width=1.7, color=PENCIL, head=9):
    """A pencil arc from (x1, y1) to (x2, y2); bend pushes the middle sideways."""
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    ln = math.hypot(dx, dy) or 1
    cx, cy = mx - dy / ln * bend, my + dx / ln * bend

    def headat(px, py, fx, fy):
        ang = math.atan2(py - fy, px - fx)
        a1, a2 = ang + math.radians(152), ang - math.radians(152)
        return (f'<path d="M {px + head * math.cos(a1):.1f} {py + head * math.sin(a1):.1f} L {px:.1f} {py:.1f} '
                f'L {px + head * math.cos(a2):.1f} {py + head * math.sin(a2):.1f}" fill="none" stroke="{color}" '
                f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')
    out = (f'<path d="M {x1:.1f} {y1:.1f} Q {cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}" fill="none" stroke="{color}" '
           f'stroke-width="{width}" stroke-linecap="round" opacity=".92"/>')
    out += headat(x2, y2, cx, cy)
    if both:
        out += headat(x1, y1, cx, cy)
    return out


# ------------------------------------------------------------------- fobs --
def fob(x, y, number, word, mint=False, scale=1.0, rot=0.0):
    """A hotel key fob on a hook: the number is the room."""
    back, front, hole_y = ring(7.0)
    fill = "url(#fobMint)" if mint else "url(#fob)"
    ink = "#0d3a2b" if mint else "#f3ead2"
    shade = "rgba(255,255,255,.45)" if mint else "rgba(0,0,0,.55)"
    small = "#1a5541" if mint else "#b9c6cb"
    big = 50 if len(number) < 2 else 44
    body = (f'<path d="M 0 -8 C 20 -8 29 8 33 34 L 44 104 C 48 132 28 150 0 150 C -28 150 -48 132 -44 104 '
            f'L -33 34 C -29 8 -20 -8 0 -8 Z M 4.3 6 A 4.3 4.3 0 1 0 -4.3 6 A 4.3 4.3 0 1 0 4.3 6 Z" fill-rule="evenodd" fill="{fill}" stroke="{"#2f7d5f" if mint else "#0a1114"}" stroke-width="1"/>'
            f'<path d="M -27 30 C -24 12 -16 -2 -4 -4" fill="none" stroke="#fff" stroke-width="2.2" opacity="{.5 if mint else .16}" stroke-linecap="round"/>'
            f'<circle cy="6" r="6" fill="none" stroke="url(#brass)" stroke-width="3.4"/>'
            f'<circle cy="6" r="7.7" fill="none" stroke="{BRASS_LO}" stroke-width=".7"/>'
            f'<circle cy="6" r="4.3" fill="none" stroke="#5b4214" stroke-width=".7"/>'
            f'<text x="0" y="{96 + 1.2:.1f}" text-anchor="middle" font-size="{big}" font-weight="900" fill="{shade}" '
            f'style="font-variation-settings:\'CASL\' 1">{esc(number)}</text>'
            f'<text x="0" y="96" text-anchor="middle" font-size="{big}" font-weight="900" fill="{ink}" '
            f'style="font-variation-settings:\'CASL\' 1">{esc(number)}</text>'
            f'<text x="0" y="122" text-anchor="middle" font-size="{7.6 if len(word) < 13 else 6.6}" font-weight="700" letter-spacing="1.3" fill="{small}" '
            f'style="font-variation-settings:\'MONO\' 1">{esc(word)}</text>')
    return (f'<g transform="translate({x:.1f} {y:.1f}) scale({scale})">{hook_back()}'
            f'<g transform="rotate({rot:.1f})" filter="url(#sh)">{back}'
            f'<g transform="translate(0 {hole_y - 6:.1f})">{body}</g>{front}</g>{hook_peg()}</g>')


# ------------------------------------------------------- lost-and-found box --
def sock(x, y):
    """A striped sock draped over an edge at (x, y): every lost-and-found has one."""
    return (f'<g transform="translate({x:.1f} {y:.1f})" filter="url(#shs)">'
            f'<path d="M 0 -7 L 23 -7 L 23 40 Q 23 46 29 47 L 41 48 Q 51 49 51 57.5 Q 51 66 41 66 L 11 65 Q 0 64 0 52 Z" '
            f'fill="#f6f3ea" stroke="#9aa59f" stroke-width=".9"/>'
            f'<path d="M 0 -7 L 23 -7 L 23 0 L 0 0 Z" fill="#000" opacity=".12"/>'
            f'<path d="M .5 5 L 22.5 5 M .5 12 L 22.5 12" stroke="{CORAL}" stroke-width="3.2"/>'
            f'<path d="M 41 48.2 Q 51 49 51 57.5 Q 51 66 41 66 Q 44 57 41 48.2 Z" fill="{CORAL}" opacity=".9"/>'
            f'<path d="M 0 52 Q 0 64 11 65 Q 8 58 12 50 Q 4 50 0 46 Z" fill="{CORAL}" opacity=".9"/></g>')


def box(x, y, w, h, contents, v, depth=40):
    """A cardboard box, top open, one compartment per cleanup tier.

    contents: [(tier letter, short label, [item names])]. y is the back edge of
    the opening; the front face runs from y + depth to y + depth + h.
    """
    back, mid, over = [], [], []
    yt, yf = y, y + depth
    back.append(f'<g filter="url(#shl)"><path d="M {x + 14} {yt} L {x + w - 14} {yt} L {x + w - 30} {yt - 40} L {x + 28} {yt - 44} Z" '
                f'fill="url(#card)" stroke="#8d6a3a" stroke-width="1"/>'
                f'<path d="M {x} {yf} L {x} {yt} L {x - 34} {yt - 10} L {x - 40} {yf + 6} Z" fill="url(#cardSide)" stroke="#8d6a3a" stroke-width="1"/>'
                f'<path d="M {x + w} {yf} L {x + w} {yt} L {x + w + 34} {yt - 8} L {x + w + 42} {yf + 8} Z" fill="url(#cardSide)" stroke="#8d6a3a" stroke-width="1"/>'
                f'<rect x="{x}" y="{yt}" width="{w}" height="{depth + 4}" fill="#7d5a2e"/>'
                f'<rect x="{x}" y="{yt}" width="{w}" height="{depth * .45:.0f}" fill="#5f4220" opacity=".6"/></g>')
    weights = [max(1.9, len(n)) for _, _, n in contents]
    acc, slots = x, []
    for (tier, short, names), wt in zip(contents, weights):
        cw = w * wt / sum(weights)
        slots.append((acc, cw, tier, short, names))
        acc += cw
    last = len(slots) - 1
    for i, (sx, cw, tier, short, names) in enumerate(slots):
        tw = 34 + len(short) * 6.9
        tx = sx + 6 if i == 0 else (sx + cw - tw - 6 if i == last else sx + (cw - tw) / 2)
        back.append(f'<g filter="url(#shs)"><path d="M {tx:.1f} {yt + 8} L {tx:.1f} {yt - 22} Q {tx:.1f} {yt - 28} {tx + 6:.1f} {yt - 28} '
                    f'L {tx + tw - 6:.1f} {yt - 28} Q {tx + tw:.1f} {yt - 28} {tx + tw:.1f} {yt - 22} L {tx + tw:.1f} {yt + 8} Z" '
                    f'fill="#efe2c2" stroke="#b39869" stroke-width=".9"/>'
                    f'<rect x="{tx + 6:.1f}" y="{yt - 23}" width="15" height="15" rx="2" fill="#161b1e"/>'
                    f'<text x="{tx + 13.5:.1f}" y="{yt - 11.6}" text-anchor="middle" font-size="11" font-weight="800" fill="#f2f1ea">{tier}</text>'
                    f'<text x="{tx + 27:.1f}" y="{yt - 11.2}" font-size="12.5" font-weight="650" fill="{PENCIL}" '
                    f'style="font-variation-settings:\'CASL\' 1,\'slnt\' -11,\'CRSV\' 1">{esc(short)}</text></g>')
        if i:
            mid.append(f'<path d="M {sx:.1f} {yt + 3} L {sx:.1f} {yf}" stroke="#4f361a" stroke-width="2.4"/>')
    keyxy = []
    for sx, cw, tier, short, names in slots:
        n = len(names)
        for j, name in enumerate(names):
            kx = sx + cw * (j + .5) / n
            rot = wobble(name, -14, 14)
            ky = yf - 40 + wobble(name + "y", -5, 4)
            mid.append(f'<g transform="translate({kx:.1f} {ky:.1f}) rotate({rot:.1f}) scale(1.02)" filter="url(#sh)">{v.key(name)}</g>')
            keyxy.append((name, kx, ky, len(keyxy)))
    # the front face over the blades
    mid.append(f'<g filter="url(#shl)"><rect x="{x}" y="{yf}" width="{w}" height="{h}" rx="1.5" fill="url(#card)" stroke="#8d6a3a" stroke-width="1"/></g>'
               f'<rect x="{x}" y="{yf}" width="{w}" height="2.5" fill="#f3d9a8" opacity=".75"/>'
               f'<path d="M {x + w * .5 - 22:.0f} {yf - 2} L {x + w * .5 + 22:.0f} {yf - 2} L {x + w * .5 + 21:.0f} {yf + 40} '
               f'L {x + w * .5 - 23:.0f} {yf + 38} Z" fill="#c9a874" opacity=".55"/>'
               f'<text x="{x + w / 2}" y="{yf + h - 20}" text-anchor="middle" font-size="27" font-weight="900" letter-spacing="7" '
               f'fill="#2a2116" opacity=".8" style="font-variation-settings:\'MONO\' 1">LOST &amp; FOUND</text>')
    mid.append(sock(x + 8, yf))
    # name tags on strings, hanging over the front face in two rows
    for name, kx, ky, j in keyxy:
        tx, ty = kx - 6, yf + 26 + (j % 2) * 32
        mid.append(f'<path d="M {kx:.1f} {ky:.1f} Q {kx - 2:.1f} {(ky + ty) / 2:.1f} {tx:.1f} {ty:.1f}" fill="none" stroke="#a3876a" stroke-width="1.1"/>')
        over.append(tag(tx, ty, esc(name), 11.5, rot=wobble(name + "t", 3, 9)))
    return {"back": back, "mid": mid, "over": over}


# ------------------------------------------------------------------- bin --
def bin_can(x, y, names, v=None, w=100, h=128):
    """A pedal bin, lid up, with the trashed entries' keys poking out."""
    back, mid, over = [], [], []
    back.append(f'<g transform="rotate(34 {x + w + 2} {y - 4})" filter="url(#shs)">'
                f'<path d="M {x - 2} {y - 4} Q {x + w / 2} {y - 34} {x + w + 2} {y - 4} Z" fill="url(#bin)" stroke="#4f5e65" stroke-width="1"/>'
                f'<rect x="{x - 3}" y="{y - 7}" width="{w + 6}" height="6" rx="3" fill="#8796a0" stroke="#4f5e65" stroke-width=".8"/></g>')
    for i, name in enumerate(names):
        kx = x + 22 + i * (w - 44) / max(1, len(names) - 1)
        rot = [-26, 3, 28, -8][i % 4]
        k = v.key(name) if v else key()
        mid.append(f'<g transform="translate({kx:.1f} {y - 40 + abs(rot) * .5:.1f}) rotate({rot}) scale(.86)" filter="url(#sh)">{k}</g>')
    mid.append(f'<g filter="url(#shl)"><path d="M {x + 4} {y} L {x + w - 4} {y} L {x + w - 12} {y + h - 6} Q {x + w - 13} {y + h} {x + w - 19} {y + h} '
               f'L {x + 19} {y + h} Q {x + 13} {y + h} {x + 12} {y + h - 6} Z" fill="url(#bin)" stroke="#4f5e65" stroke-width="1"/></g>'
               f'<path d="M {x + 30} {y + 8} L {x + 33} {y + h - 10}" stroke="#fff" stroke-width="3" opacity=".25" stroke-linecap="round"/>'
               f'<rect x="{x}" y="{y - 4}" width="{w}" height="9" rx="3.5" fill="url(#bin)" stroke="#4f5e65" stroke-width="1"/>'
               f'<rect x="{x + w / 2 - 14}" y="{y + h - 4}" width="28" height="9" rx="3" fill="#2a3539" stroke="#11181b" stroke-width=".8"/>'
               f'<g transform="translate({x + w / 2} {y + 52}) rotate(-2)"><rect x="-27" y="-10" width="54" height="19" rx="2.4" fill="#191e21"/>'
               f'<rect x="-27" y="-10" width="54" height="6" rx="2.4" fill="#fff" opacity=".08"/>'
               f'<text x="0" y="4" text-anchor="middle" font-size="10.5" font-weight="780" letter-spacing="1.6" fill="#f2f1ea">TRASH</text></g>')
    return {"back": back, "mid": mid, "over": over}


# --------------------------------------------------------------- undo tag --
def undo_tag(x, y, scale=1.0):
    """A big brass luggage tag on a hook, stamped UNDO."""
    back, mid = [], []
    rb, rf, hole_y = ring(8.0)
    s = scale
    ty = hole_y + 34
    arrow = ('<path d="M -16 -4 A 16 16 0 1 1 -10 12" fill="none" stroke="#6e4f17" stroke-width="5" stroke-linecap="round"/>'
             '<path d="M -26 -10 L -16 -4 L -10 -15" fill="none" stroke="#6e4f17" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')
    tagsvg = (f'<path d="M -62 24 L -40 0 L 40 0 L 62 24 L 62 214 Q 62 226 50 226 L -50 226 Q -62 226 -62 214 Z" '
              f'fill="url(#brass)" stroke="{BRASS_LO}" stroke-width="1.2"/>'
              f'<path d="M -54 28 L -36 8 L 36 8 L 54 28 L 54 210 Q 54 218 46 218 L -46 218 Q -54 218 -54 210 Z" '
              f'fill="none" stroke="#fff3c8" stroke-width=".8" opacity=".6"/>'
              f'<circle cy="22" r="9" fill="url(#rosette)" stroke="#55656d" stroke-width="1"/>'
              f'<circle cy="22" r="5" fill="{MINT}" stroke="#55656d" stroke-width=".8"/>'
              f'<g transform="translate(0 78)">{arrow}</g>'
              f'<text x="1" y="157" text-anchor="middle" font-size="44" font-weight="900" fill="#fff2c4" opacity=".55" '
              f'style="font-variation-settings:\'CASL\' 1">UNDO</text>'
              f'<text x="0" y="156" text-anchor="middle" font-size="44" font-weight="900" fill="#6e4f17" '
              f'style="font-variation-settings:\'CASL\' 1">UNDO</text>'
              f'<text x="0" y="190" text-anchor="middle" font-size="10" font-weight="700" letter-spacing=".6" fill="#6e4f17" '
              f'style="font-variation-settings:\'MONO\' 1">REVERT · RESTORE</text>')
    mid.append(f'<g transform="translate({x:.1f} {y:.1f}) scale({s})">{hook_back()}<g filter="url(#sh)">{rb}'
               f'<path d="M -3 {hole_y - 8:.1f} L -2 {ty + 22:.1f} M 3 {hole_y - 8:.1f} L 2 {ty + 22:.1f}" stroke="#a3876a" stroke-width="1.6" fill="none"/>'
               f'<g transform="translate(0 {ty:.1f}) rotate(-4 0 22)">{tagsvg}</g>{rf}</g>{hook_peg()}</g>')
    return {"back": back, "mid": mid}


def chore_tick(i):
    """A hand-drawn checkbox with a pencil tick, slightly different each time."""
    j = [(0, 0), (1.2, -.8), (-.8, .6), (.6, 1)][i % 4]
    return (f'<svg width="30" height="30" viewBox="0 0 30 30" style="margin-top:2px">'
            f'<path d="M 4 5.5 Q 15 {4 + j[0]} 25.5 4.5 Q {26 + j[1]} 15 25 25.5 Q 15 {26 + j[1]} 4.5 25 Q {3.5 + j[0]} 15 4 5.5 Z" '
            f'fill="none" stroke="#5f675f" stroke-width="1.6" stroke-linejoin="round"/>'
            f'<path d="M 8 {15 + j[1]} L {13 + j[0]} 21 L {27 + j[1]} {3 + j[0]}" fill="none" stroke="#2c7a5c" stroke-width="2.8" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def svg_tag(x, y, text, size=12, rot=0.0):
    """A kraft tag drawn in SVG (for tags that must sit behind something)."""
    w = len(text) * size * .56 + size * 2.4
    h = size * 1.85
    return (f'<g transform="translate({x:.1f} {y:.1f}) rotate({rot:.1f})" filter="url(#shs)">'
            f'<path d="M 0 {-h * .22:.1f} L {size * .7:.1f} {-h / 2:.1f} L {w:.1f} {-h / 2:.1f} L {w:.1f} {h / 2:.1f} '
            f'L {size * .7:.1f} {h / 2:.1f} L 0 {h * .22:.1f} Z" fill="#ead8b2" stroke="#c7b083" stroke-width=".6"/>'
            f'<circle cx="{size * .86:.1f}" cy="0" r="{size * .31:.1f}" fill="{MINT}" stroke="#cdb98f" stroke-width="{size * .16:.1f}"/>'
            f'<text x="{size * 1.9:.1f}" y="{size * .36:.1f}" font-size="{size}" font-weight="640" fill="{PENCIL}" '
            f'style="font-variation-settings:\'CASL\' 1,\'slnt\' -11,\'CRSV\' 1">{esc(text)}</text></g>')

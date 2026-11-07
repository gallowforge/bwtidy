#!/usr/bin/env python3
"""
bwfix.py - repair rename_plan.json deterministically. No model, no waiting.

Undoes the bad disambiguation:
  - strips suffixes that duplicate what is already in the name
  - strips truncated tails ("... (alex", "(sup.")
  - strips meaningless "(2)" numbering
  - rewrites long emails inside names down to their local part
then re-disambiguates each brand group using ONLY the attributes that actually
differ inside that group, and never cuts a name mid-token.

    python3 bwfix.py            # rewrites rename_plan.json, shows before/after
    python3 bwfix.py --dry      # show what it would do, change nothing
"""

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from urllib.parse import urlparse

import bwconfig  # noqa: F401  (sets an owner-only umask for the plan file)

PLAN = "rename_plan.json"
MAXLEN = 40

MULTI_SUFFIX = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.kw", "net.kw", "org.kw",
    "edu.kw", "gov.kw", "com.sa", "com.au", "com.br", "com.mx", "com.tr",
    "com.cn", "com.hk", "com.sg", "com.eg", "com.qa", "com.bh", "com.om",
    "com.jo", "com.lb", "com.my", "com.ph", "com.vn", "com.pk", "co.jp",
    "co.in", "co.nz", "co.za", "co.kr", "co.il", "co.th", "co.id",
    "org.nz", "org.il",
}
KEEP_SUB = {"ts.net", "duckdns.org", "myshopify.com", "github.io",
            "herokuapp.com", "netlify.app", "vercel.app", "pages.dev",
            "workers.dev", "nabu.casa", "ui.nabu.casa"}


def bw(*args):
    s = os.environ.get("BW_SESSION")
    if not s:
        sys.exit('BW_SESSION is not set. Run: export BW_SESSION="$(bw unlock --raw)"')
    p = subprocess.run(["bw", *args, "--session", s, "--nointeraction"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"bw {' '.join(args)} failed:\n{p.stderr.strip()}")
    return p.stdout


def parsed(item):
    for u in ((item.get("login") or {}).get("uris") or []):
        raw = (u.get("uri") or "").strip()
        if not raw or raw.startswith(("android://", "iosapp://")):
            continue
        r = raw if "://" in raw else "https://" + raw
        p = urlparse(r)
        if p.hostname:
            return p.hostname.lower(), p.port, (p.path or "").strip("/")
    return "", None, ""


def registrable(h):
    h = h.strip(".")
    if not h or re.match(r"^\d{1,3}(\.\d{1,3}){3}$", h):
        return h
    parts = h.split(".")
    if len(parts) < 2:
        return h
    for k in KEEP_SUB:
        if h.endswith("." + k):
            return ".".join(parts[-(k.count(".") + 2):])
    if ".".join(parts[-2:]) in MULTI_SUFFIX and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def local(u):
    return (u or "").split("@")[0].strip()


def attrs(item, brand):
    h, port, path = parsed(item)
    sub = h[:-(len(brand) + 1)] if h.endswith(brand) and len(h) > len(brand) else ""
    if sub == "www":
        sub = ""
    return {"sub": sub, "user": local((item.get("login") or {}).get("username")),
            "port": str(port) if port else "", "host": h, "path": path[:15]}


def strip_mine(name, a):
    """Remove trailing parentheticals that are just echoes of the item's own data,
    plus any truncated tail. Keeps model-written ones like '(UK)'."""
    mine = {v.lower() for v in a.values() if v}
    mine |= {f"port {a['port']}".lower()} if a["port"] else set()
    mine |= {(a["user"] or "").lower()}
    changed = True
    while changed:
        changed = False
        # truncated tail: an unclosed "(" near the end
        if "(" in name and name.count("(") > name.count(")"):
            name = name[:name.rindex("(")].strip()
            changed = True
            continue
        m = re.search(r"\s*\(([^()]*)\)\s*$", name)
        if not m:
            break
        inner = m.group(1).strip()
        low = inner.lower()
        is_mine = (
            low in mine
            or re.fullmatch(r"\d+", inner)                       # "(2)"
            or re.fullmatch(r"port \d+", low)
            or ("@" in inner and local(inner).lower() in mine)   # full email
        )
        if is_mine and name[:m.start()].strip():
            name = name[:m.start()].strip()
            changed = True
    return re.sub(r"\s+", " ", name).strip()


def shorten_email(name):
    return re.sub(r"\(([^()@\s]+)@[^()\s]+\)", r"(\1)", name)


def main():
    dry = "--dry" in sys.argv
    if not os.path.exists(PLAN):
        sys.exit(f"No {PLAN} here. cd to the folder that has it.")
    plan = json.load(open(PLAN))
    items = json.loads(bw("list", "items"))
    byid = {it["id"]: it for it in items}

    groups = defaultdict(list)
    for it in items:
        h, _, _ = parsed(it)
        groups[registrable(h) if h else f"~{it['name'].strip().lower()[:20]}"].append(it)

    proposed = {p["id"]: p["to"] for p in plan}
    original = {p["id"]: p["from"] for p in plan}

    final, repaired = {}, 0
    for brand, members in groups.items():
        # Which attributes actually vary inside this group?
        info = {it["id"]: attrs(it, brand) for it in members}
        varying = [k for k in ("sub", "user", "port")
                   if len({info[i["id"]][k] for i in members}) > 1]

        bases = {}
        for it in members:
            raw = proposed.get(it["id"], it["name"])
            a = info[it["id"]]
            malformed = (len(raw) >= MAXLEN
                         or raw.count("(") != raw.count(")")
                         or raw.count("(") > 1
                         or re.search(r"\(\d+\)$", raw)
                         or "@" in raw)
            bases[it["id"]] = ((shorten_email(strip_mine(raw, a)) or it["name"])
                               if malformed else raw)

        counts = defaultdict(int)
        for it in members:
            counts[bases[it["id"]].lower()] += 1

        used = set()
        for it in members:
            base = bases[it["id"]]
            name = base
            if counts[base.lower()] > 1:
                a = info[it["id"]]
                parts = [a[k] if k != "port" else f"port {a[k]}"
                         for k in varying if a[k]]
                # drop trailing parts until it fits - never cut mid-token
                while parts and len(f"{base} ({', '.join(parts)})") > MAXLEN:
                    parts.pop()
                cand = f"{base} ({', '.join(parts)})" if parts else base
                if not parts or cand.lower() in used:
                    for extra in (a["host"], a["path"]):
                        alt = f"{base} ({extra})"
                        if extra and len(alt) <= MAXLEN and alt.lower() not in used:
                            cand = alt
                            break
                name = cand
            if name.lower() in used:
                i = 2
                while f"{base} ({i})".lower() in used:
                    i += 1
                name = f"{base} ({i})"
            used.add(name.lower())
            final[it["id"]] = name
            if name != proposed.get(it["id"], it["name"]):
                repaired += 1

    newplan = [{"id": i, "from": byid[i]["name"], "to": n, "brand": b}
               for b, ms in groups.items() for i, n in
               ((x["id"], final[x["id"]]) for x in ms)
               if n != byid[i]["name"]]

    bad_before = [p for p in plan if len(p["to"]) >= MAXLEN
                  or p["to"].count("(") != p["to"].count(")")
                  or re.search(r"\(\d+\)$", p["to"])
                  or re.search(r"\(([^()]+)\).*\(\1\)", p["to"])]
    print(f"{len(plan)} renames in plan, {len(bad_before)} clearly malformed.")
    print(f"Repaired {repaired}. New plan has {len(newplan)} renames.\n")

    shown = 0
    for p in plan:
        was, now = p["to"], final.get(p["id"])
        if now and now != was and shown < 30:
            print(f"  {was[:44]:<44} => {now}")
            shown += 1
    if repaired > shown:
        print(f"  ... {repaired - shown} more")

    over = [n for n in final.values() if len(n) > MAXLEN]
    unb = [n for n in final.values() if n.count("(") != n.count(")")]
    print(f"\nchecks: over {MAXLEN} chars: {len(over)} | unbalanced parens: {len(unb)}")
    for b, ms in groups.items():
        names = [final[x["id"]] for x in ms]
        assert len(names) == len({n.lower() for n in names}), f"collision in {b}"
    print("uniqueness within every brand group: OK")

    if dry:
        print("\n--dry: nothing written.")
        return
    json.dump(newplan, open(PLAN, "w"), indent=2, ensure_ascii=False)
    print(f"\nWrote {PLAN}. Review it, then: python3 bwrename.py apply")


if __name__ == "__main__":
    main()

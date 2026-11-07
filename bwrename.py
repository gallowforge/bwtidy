#!/usr/bin/env python3
"""
bwrename.py - full rename pass over the whole vault.

Every entry gets a clean human name. Entries that share a brand are named
together so they can be told apart: uniqueness inside a brand is enforced by
this script, NOT trusted to the model - if two entries in one brand come back
with the same name, a distinguishing detail (subdomain, username, port) is
appended deterministically.

Only the `name` field is ever written. `revert` restores every previous name.

    export BW_SESSION="$(bw unlock --raw)"
    python3 bwrename.py plan
    python3 bwrename.py apply
    python3 bwrename.py revert
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from urllib.parse import urlparse

from bwconfig import MODEL, lmstudio_url

LMSTUDIO = lmstudio_url()
TARGET = 30
PLAN = "rename_plan.json"

MULTI_SUFFIX = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk",
    "com.kw", "net.kw", "org.kw", "edu.kw", "gov.kw",
    "com.sa", "com.au", "com.br", "com.mx", "com.tr", "com.cn", "com.hk",
    "com.sg", "com.eg", "com.qa", "com.bh", "com.om", "com.jo", "com.lb",
    "com.my", "com.ph", "com.vn", "com.pk", "co.jp", "co.in", "co.nz",
    "co.za", "co.kr", "co.il", "co.th", "co.id", "org.nz", "org.il",
}
KEEP_SUB = {"ts.net", "duckdns.org", "myshopify.com", "github.io",
            "herokuapp.com", "netlify.app", "vercel.app", "pages.dev",
            "workers.dev", "nabu.casa", "ui.nabu.casa"}

SYSTEM_PROMPT = """You rename password-manager entries. Every entry belongs to a
GROUP - all entries in a group are the same company or service.

For each entry return a clean, human-readable name.

RULES - follow exactly:
1. Return the exact `id` you were given, character for character.
2. Use the service's common name as a person would say it. "uk.accounts.contoso.com"
   -> "Contoso". "login.microsoftonline.com" -> "Microsoft". "github.com" -> "GitHub".
3. Correct capitalization to the brand's real style: "GitHub", "PayPal", "eBay",
   "YouTube", "TP-Link", "LinkedIn".
4. Strip junk: "(copy)", "(2)", "- old", "new", trailing numbers, and any URL
   fragments or domain suffixes.
5. When a group has MORE THAN ONE entry, every name in that group must be
   DIFFERENT. Tell them apart using the hint given for each entry - its purpose
   (Store, Account, Login, Support), its region, or its username.
   Example group of three Contoso entries ->
     "Contoso", "Contoso (UK)", "Contoso (Support)"
6. Maximum 40 characters. No URLs, no "http", no "www".
7. NEVER invent a fact you were not given. If you do not recognise a service,
   return a tidied version of its current name rather than a guess.
8. Output JSON only. No prose, no markdown fences.
"""

SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "renames", "strict": True,
        "schema": {"type": "object", "properties": {"renames": {
            "type": "array", "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
                "required": ["id", "name"], "additionalProperties": False}}},
            "required": ["renames"], "additionalProperties": False},
    },
}


def bw(*args):
    s = os.environ.get("BW_SESSION")
    if not s:
        sys.exit('BW_SESSION is not set. Run: export BW_SESSION="$(bw unlock --raw)"')
    p = subprocess.run(["bw", *args, "--session", s, "--nointeraction"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"bw {' '.join(args)} failed:\n{p.stderr.strip()}")
    return p.stdout


def first_uri(item):
    for u in ((item.get("login") or {}).get("uris") or []):
        raw = (u.get("uri") or "").strip()
        if raw and not raw.startswith(("android://", "iosapp://")):
            return raw
    return ""


def parsed(item):
    raw = first_uri(item)
    if not raw:
        return "", None, ""
    r = raw if "://" in raw else "https://" + raw
    p = urlparse(r)
    return (p.hostname or "").lower(), p.port, (p.path or "").strip("/")


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


def subdomain(h, brand):
    return h[:-(len(brand) + 1)] if h.endswith(brand) and len(h) > len(brand) else ""


def hint(item, brand):
    h, port, path = parsed(item)
    bits = []
    sub = subdomain(h, brand)
    if sub and sub != "www":
        bits.append(f"subdomain={sub}")
    if port:
        bits.append(f"port={port}")
    if path:
        bits.append(f"path={path[:25]}")
    u = ((item.get("login") or {}).get("username") or "").strip()
    if u:
        bits.append(f"user={u[:35]}")
    return ", ".join(bits) or "no extra detail"


def disambiguator(item, brand, used, port_first=False):
    """Deterministic tie-breaker. When every entry in a group sits on the same
    host, the port is the only real signal, so it is tried first."""
    h, port, path = parsed(item)
    user = ((item.get("login") or {}).get("username") or "").split("@")[0]
    sub = subdomain(h, brand)
    order = ([f"port {port}" if port else "", sub, user, path[:18], h]
             if port_first else
             [sub, user, f"port {port}" if port else "", path[:18], h])
    for cand in order:
        c = (cand or "").strip()
        if c and c.lower() not in used:
            return c
    return ""


def call_model(entries, groups):
    lines = []
    for gname, members in groups:
        lines.append(f"\nGROUP: {gname}  ({len(members)} entr{'y' if len(members)==1 else 'ies'})")
        for it in members:
            lines.append(f"  id={it['id']} | current={it['name'][:50]!r} | {hint(it, gname)}")
    payload = {"model": MODEL, "temperature": 0, "top_p": 1, "max_tokens": 4096,
               "response_format": SCHEMA,
               "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content":
                             "\n".join(lines) + f"\n\nReturn exactly {len(entries)} renames."}]}
    req = urllib.request.Request(f"{LMSTUDIO}/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        body = json.load(r)
    t = body["choices"][0]["message"]["content"].strip()
    if t.startswith("```"):
        t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)["renames"]


BAD = re.compile(r"^(untitled|new item|unnamed|no name|login|account|n/?a)$", re.I)


def sane(new):
    n = (new or "").strip().strip('"')
    n = re.sub(r"\s+", " ", n)
    if not n or len(n) > 40 or BAD.match(n) or "://" in n:
        return None
    if n.lower().startswith(("http", "www.")):
        return None
    return n


def tidy(name):
    n = re.sub(r"\s*[\(\[]?(copy|old|new|backup|dup|duplicate|\d+)[\)\]]?\s*$",
               "", name, flags=re.I)
    return re.sub(r"\s+", " ", n).strip() or name


def build_plan(items, proposed):
    """Pure function: items + model proposals -> plan, with uniqueness enforced."""
    groups = defaultdict(list)
    for it in items:
        h, _, _ = parsed(it)
        groups[registrable(h) if h else f"~{it['name'].strip().lower()[:20]}"].append(it)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    plan = []
    for brand, members in ordered:
        used = set()
        hosts = {parsed(i)[0] for i in members}
        ports = {parsed(i)[1] for i in members}
        port_first = len(hosts) == 1 and len(ports) > 1
        for it in members:
            new = sane(proposed.get(it["id"])) or tidy(it["name"])
            base = new
            if new.lower() in used:
                d = disambiguator(it, brand, used, port_first)
                new = (f"{base} ({d})" if d else f"{base} ({len(used)+1})")[:40]
            if new.lower() in used:
                i = 2
                while f"{base} ({i})".lower() in used:
                    i += 1
                new = f"{base} ({i})"[:40]
            used.add(new.lower())
            if new != it["name"]:
                plan.append({"id": it["id"], "from": it["name"], "to": new,
                             "brand": brand})
    return ordered, plan


def cmd_plan(_):
    items = json.loads(bw("list", "items"))
    groups = defaultdict(list)
    for it in items:
        h, _, _ = parsed(it)
        groups[registrable(h) if h else f"~{it['name'].strip().lower()[:20]}"].append(it)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    print(f"{len(items)} items in {len(ordered)} brand group(s). "
          f"Largest: {', '.join(f'{k}({len(v)})' for k, v in ordered[:5])}")

    batches, cur, n = [], [], 0
    for g in ordered:
        if n and n + len(g[1]) > TARGET:
            batches.append(cur)
            cur, n = [], 0
        cur.append(g)
        n += len(g[1])
    if cur:
        batches.append(cur)

    proposed = {}
    for bi, batch in enumerate(batches, 1):
        members = [it for _, ms in batch for it in ms]
        print(f"  batch {bi}/{len(batches)} - {len(members)} entries")
        try:
            for r in call_model(members, batch):
                proposed[r["id"]] = r.get("name")
        except Exception as e:
            print(f"    failed ({e}), keeping current names for this batch",
                  file=sys.stderr)

    ordered, plan = build_plan(items, proposed)
    with open(PLAN, "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    print(f"\n{len(plan)} rename(s) of {len(items)} items -> {PLAN}\n")
    shown = 0
    for brand, _ in ordered:
        rows = [p for p in plan if p["brand"] == brand]
        if not rows or shown > 45:
            continue
        print(f"  [{brand}]")
        for p in rows:
            print(f"    {p['from'][:38]:<38} -> {p['to']}")
            shown += 1
    if len(plan) > shown:
        print(f"  ... {len(plan)-shown} more in {PLAN}")
    print(f"\nEdit {PLAN} if you disagree, then: python3 bwrename.py apply")


def cmd_apply(_):
    if not os.path.exists(PLAN):
        sys.exit(f"No {PLAN}. Run: python3 bwrename.py plan")
    plan = json.load(open(PLAN))
    if not plan:
        return print("Nothing to rename.")
    items = {it["id"]: it for it in json.loads(bw("list", "items"))}
    ok = skip = 0
    for p in plan:
        it = items.get(p["id"])
        if not it or it["name"] != p["from"]:
            skip += 1
            continue
        it["name"] = p["to"]
        bw("edit", "item", p["id"],
           base64.b64encode(json.dumps(it).encode()).decode())
        ok += 1
        print(f"  [{ok}/{len(plan)}] {p['from'][:38]} -> {p['to']}")
    bw("sync")
    print(f"\nRenamed {ok}." + (f" Skipped {skip} (changed since plan)." if skip else ""))
    print("Undo everything with: python3 bwrename.py revert")


def cmd_revert(_):
    plan = json.load(open(PLAN))
    items = {it["id"]: it for it in json.loads(bw("list", "items"))}
    ok = 0
    for p in plan:
        it = items.get(p["id"])
        if not it or it["name"] != p["to"]:
            continue
        it["name"] = p["from"]
        bw("edit", "item", p["id"],
           base64.b64encode(json.dumps(it).encode()).decode())
        ok += 1
    bw("sync")
    print(f"Reverted {ok} name(s).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(fn=cmd_plan)
    sub.add_parser("apply").set_defaults(fn=cmd_apply)
    sub.add_parser("revert").set_defaults(fn=cmd_revert)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)

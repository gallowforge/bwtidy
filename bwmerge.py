#!/usr/bin/env python3
"""
bwmerge.py - merge duplicate entries and remove confirmed-dead ones. Reversible.

MERGE: when several entries are the same brand AND the same username AND the
same password, they are one account recorded several times. The richest entry
keeps everything, absorbs the others' URLs, and the redundant copies are
trashed. Autofill still works on every URL afterwards.

DELETE: only entries whose domain is verifiably gone, or services you have
confirmed you moved off.

SAFETY
  - every affected item is written to backup-<timestamp>.json BEFORE any change
  - deletes are SOFT (Bitwarden trash), not permanent
  - `restore` undoes an apply completely
  - entries differing by PORT are never merged - those are separate services

    export BW_SESSION="$(bw unlock --raw)"
    python3 bwmerge.py plan
    python3 bwmerge.py apply
    python3 bwmerge.py restore [backup-<stamp>.json]   # default: newest backup
"""

import argparse
import base64
import datetime as dt
import glob
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from bwconfig import CONFIG

PLAN = "merge_plan.json"

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

# Domains you have confirmed dead. The only domains this script will trash.
# With `plan --dns` they are trashed only if they also fail to resolve now.
# Set in bwtidy.json: {"dead_domains": ["example.com", ...]}
DEAD_DOMAINS = set(CONFIG["dead_domains"])

# Never treat these as dead even though a plain lookup fails
# (an apex with no A record, a router-only name, an app identifier).
DNS_FALSE_POSITIVES = set(CONFIG["dns_false_positives"])

# Services you have moved off: {"<substring of name or URL>": "<reason>"}
DECOMMISSIONED = dict(CONFIG["decommissioned"])


def bw(*args):
    s = os.environ.get("BW_SESSION")
    if not s:
        sys.exit('BW_SESSION is not set. Run: export BW_SESSION="$(bw unlock --raw)"')
    p = subprocess.run(["bw", *args, "--session", s, "--nointeraction"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"bw {' '.join(args[:3])} failed: {p.stderr.strip()}")
    return p.stdout


def uris(item):
    return [(u.get("uri") or "").strip()
            for u in ((item.get("login") or {}).get("uris") or [])
            if (u.get("uri") or "").strip()]


def hostport(u):
    if not u or u.startswith(("android://", "iosapp://")):
        return "", None
    r = u if "://" in u else "https://" + u
    p = urlparse(r)
    return (p.hostname or "").lower(), p.port


def registrable(h):
    h = h.strip(".")
    if not h or re.match(r"^\d{1,3}(\.\d{1,3}){3}$", h) or "." not in h:
        return h
    parts = h.split(".")
    for k in KEEP_SUB:
        if h.endswith("." + k):
            return ".".join(parts[-(k.count(".") + 2):])
    if ".".join(parts[-2:]) in MULTI_SUFFIX and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def brand(item):
    hs = {registrable(hostport(u)[0]) for u in uris(item) if hostport(u)[0]}
    return next(iter(hs)) if len(hs) == 1 else (sorted(hs)[0] if hs else "")


def richness(item):
    """How much information an entry carries. The richest one survives a merge."""
    lg = item.get("login") or {}
    return (len(uris(item)),
            1 if lg.get("totp") else 0,
            1 if (item.get("notes") or "").strip() else 0,
            len(item.get("fields") or []),
            1 if item.get("folderId") else 0,
            item.get("revisionDate") or "")


def mergeable(items):
    """Groups that are provably one account: same brand, username, password,
    and NO differing ports (a different port means a different service)."""
    buckets = defaultdict(list)
    for it in items:
        lg = it.get("login") or {}
        user, pw = (lg.get("username") or "").strip(), lg.get("password")
        if not user or not pw or it.get("type") != 1:
            continue
        b = brand(it)
        if not b or re.match(r"^\d{1,3}(\.\d{1,3}){3}$", b) or b == "localhost":
            continue
        key = (b, user.lower(), hashlib.sha256(pw.encode()).hexdigest())
        buckets[key].append(it)

    out = []
    for (b, _, _), group in buckets.items():
        if len(group) < 2:
            continue
        ports = {hostport(u)[1] for it in group for u in uris(it)}
        if len({p for p in ports if p}) > 0 and len(ports) > 1:
            continue                      # differing ports -> distinct services
        group.sort(key=richness, reverse=True)
        out.append((b, group[0], group[1:]))
    return out


def dead(items, do_dns):
    flagged = {}
    for it in items:
        hay = f"{it['name']} {' '.join(uris(it))}".lower()
        for k, why in DECOMMISSIONED.items():
            if k in hay:
                flagged[it["id"]] = why
                break
    hosts = {hostport(u)[0] for it in items for u in uris(it)}
    hosts = {h for h in hosts if h and h not in DNS_FALSE_POSITIVES
             and not re.match(r"^(localhost|127\.|10\.|192\.168\.|172\.)", h)}
    alive = {}
    if do_dns:
        def chk(h):
            try:
                socket.getaddrinfo(h, None)
                return h, True
            except Exception:
                return h, False
        with ThreadPoolExecutor(max_workers=20) as ex:
            alive = dict(ex.map(chk, sorted(hosts)))
    for it in items:
        for u in uris(it):
            h = hostport(u)[0]
            if h in DNS_FALSE_POSITIVES:
                continue
            if h in DEAD_DOMAINS and (not do_dns or alive.get(h) is False):
                flagged.setdefault(it["id"], f"{h} no longer resolves")
    return flagged


def cmd_plan(args):
    items = json.loads(bw("list", "items"))
    folders = {f["id"]: f["name"] for f in json.loads(bw("list", "folders"))}
    merges = mergeable(items)
    kills = dead(items, args.dns)

    merge_rows, absorbed = [], set()
    for b, keep, drop in merges:
        all_uris, seen = [], set()
        for it in [keep] + drop:
            for u in uris(it):
                if u.lower() not in seen:
                    seen.add(u.lower())
                    all_uris.append(u)
        merge_rows.append({
            "brand": b, "keep_id": keep["id"], "keep_name": keep["name"],
            "uris": all_uris,
            "drop": [{"id": d["id"], "name": d["name"]} for d in drop],
        })
        absorbed |= {d["id"] for d in drop}

    kill_rows = [{"id": i, "name": next(x["name"] for x in items if x["id"] == i),
                  "reason": why}
                 for i, why in kills.items() if i not in absorbed]

    plan = {"created": dt.datetime.now(dt.timezone.utc).isoformat(),
            "merges": merge_rows, "deletes": kill_rows}
    json.dump(plan, open(PLAN, "w"), indent=2, ensure_ascii=False)

    print(f"{len(items)} items.\n")
    if merge_rows:
        print(f"MERGE - {len(merge_rows)} group(s), "
              f"{sum(len(r['drop']) for r in merge_rows)} entries absorbed:\n")
        for r in merge_rows:
            print(f"  {r['keep_name']}   <- keeps {len(r['uris'])} URL(s)")
            for d in r["drop"]:
                print(f"      absorbs: {d['name']}")
    if kill_rows:
        print(f"\nDELETE - {len(kill_rows)} entr(y/ies) to trash:\n")
        for r in kill_rows:
            print(f"  {r['name'][:40]:<40} {r['reason']}")
    net = sum(len(r["drop"]) for r in merge_rows) + len(kill_rows)
    print(f"\n{len(items)} -> {len(items) - net} items.")
    print(f"Review {PLAN}, then: python3 bwmerge.py apply")


def cmd_apply(_):
    if not os.path.exists(PLAN):
        sys.exit(f"No {PLAN}. Run: python3 bwmerge.py plan")
    plan = json.load(open(PLAN))
    items = {it["id"]: it for it in json.loads(bw("list", "items"))}

    touched = ([r["keep_id"] for r in plan["merges"]]
               + [d["id"] for r in plan["merges"] for d in r["drop"]]
               + [r["id"] for r in plan["deletes"]])
    missing = [i for i in touched if i not in items]
    if missing:
        sys.exit(f"{len(missing)} item(s) in the plan no longer exist. Re-run plan.")

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"backup-{stamp}.json"
    json.dump({i: items[i] for i in touched}, open(backup, "w"),
              indent=2, ensure_ascii=False)
    print(f"backed up {len(touched)} item(s) -> {backup}\n")

    done_m = done_d = 0
    for r in plan["merges"]:
        keep = items[r["keep_id"]]
        keep.setdefault("login", {})["uris"] = [
            {"uri": u, "match": None} for u in r["uris"]]
        bw("edit", "item", keep["id"],
           base64.b64encode(json.dumps(keep).encode()).decode())
        print(f"  merged into: {keep['name']}  ({len(r['uris'])} URLs)")
        for d in r["drop"]:
            bw("delete", "item", d["id"])       # soft delete -> trash
            done_d += 1
            print(f"      trashed: {d['name']}")
        done_m += 1

    for r in plan["deletes"]:
        bw("delete", "item", r["id"])
        done_d += 1
        print(f"  trashed: {r['name']}")

    bw("sync")
    print(f"\n{done_m} merge(s), {done_d} item(s) in trash.")
    print(f"Undo: python3 bwmerge.py restore   (backup: {backup})")


def cmd_restore(args):
    if args.backup:
        backup = args.backup
    else:
        backups = sorted(glob.glob("backup-*.json"), key=os.path.getmtime)
        if not backups:
            sys.exit("No backup-*.json here.")
        backup = backups[-1]
    saved = json.load(open(backup))
    print(f"restoring from {backup} ({len(saved)} item(s))")

    ok = recreated = 0
    for iid, item in saved.items():
        try:
            bw("restore", "item", iid)          # un-trash
        except RuntimeError:
            pass                                # was never trashed
        try:
            bw("edit", "item", iid,
               base64.b64encode(json.dumps(item).encode()).decode())
            ok += 1
        except RuntimeError:
            payload = {k: v for k, v in item.items()
                       if k not in ("id", "revisionDate", "creationDate", "object")}
            try:
                bw("create", "item",
                   base64.b64encode(json.dumps(payload).encode()).decode())
                recreated += 1
            except RuntimeError as e:
                print(f"  could not restore {item.get('name')}: {e}")
    bw("sync")
    print(f"\nrestored {ok} in place, recreated {recreated}.")
    print("Recreated items get new IDs but identical contents.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--dns", action="store_true")
    p.set_defaults(fn=cmd_plan)
    sub.add_parser("apply").set_defaults(fn=cmd_apply)
    p = sub.add_parser("restore"); p.add_argument("backup", nargs="?")
    p.set_defaults(fn=cmd_restore)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)

#!/usr/bin/env python3
"""
bwdead.py - build a deletion checklist. Deletes NOTHING, ever.

Ranks candidates by how strong the evidence is that an entry is dead, and
writes cleanup.md with the reason next to each one. You tick through it in the
Bitwarden app.

    export BW_SESSION="$(bw unlock --raw)"
    python3 bwdead.py              # offline evidence only
    python3 bwdead.py --dns        # also test whether each domain still resolves

--dns does one DNS lookup per unique domain in your vault. Those queries leave
the machine through your resolver. Skip it if you would rather not emit that list.
"""

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import datetime as dt
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from bwconfig import CONFIG

STALE_YEARS = 3
OUT = "cleanup.md"

# Services you have moved off, matched against name + hostname.
# Set in bwtidy.json: {"decommissioned": {"<substring>": "<reason>"}}
DECOMMISSIONED = dict(CONFIG["decommissioned"])

# A private host suffix (e.g. your tailnet or home.arpa) and the ports still
# served under it. Entries on that suffix with any other port are flagged.
PRIVATE_SUFFIX = (CONFIG["private_host"].get("suffix") or "").lower().lstrip(".")
LIVE_PORTS = set(CONFIG["private_host"].get("live_ports") or [])


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
            return p.hostname.lower(), p.port
    return "", None


PRIVATE = re.compile(r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dns", action="store_true",
                    help="test whether each domain still resolves")
    args = ap.parse_args()

    items = json.loads(bw("list", "items"))
    folders = {f["id"]: f["name"] for f in json.loads(bw("list", "folders"))}
    now = dt.datetime.now(dt.timezone.utc)

    def fold(it):
        return folders.get(it.get("folderId"), "none")

    reasons = defaultdict(list)   # id -> [reason strings]
    tier = {}                     # id -> tier letter

    def flag(it, t, why):
        reasons[it["id"]].append(why)
        if it["id"] not in tier or t < tier[it["id"]]:
            tier[it["id"]] = t

    # A - exact duplicates: same domain, same user, same password
    seen = defaultdict(list)
    for it in items:
        lg = it.get("login") or {}
        if not lg.get("password"):
            continue
        h, port = parsed(it)
        key = (h, port, (lg.get("username") or "").lower(),
               hashlib.sha256(lg["password"].encode()).hexdigest())
        if key[0] or key[2]:
            seen[key].append(it)
    for group in seen.values():
        if len(group) > 1:
            for extra in group[1:]:
                flag(extra, "A", f"exact duplicate of \"{group[0]['name']}\"")

    # C - services you have decommissioned
    for it in items:
        h, _ = parsed(it)
        hay = f"{it['name']} {h}".lower()
        for key, why in DECOMMISSIONED.items():
            if key in hay:
                flag(it, "C", why)
                break

    # C - private-host entries on ports that are no longer served
    for it in items:
        h, port = parsed(it)
        if (PRIVATE_SUFFIX and (h == PRIVATE_SUFFIX or h.endswith("." + PRIVATE_SUFFIX))
                and port and port not in LIVE_PORTS):
            flag(it, "C", f"port {port} is no longer served on {PRIVATE_SUFFIX}")

    # D - untouched for years
    for it in items:
        rev = it.get("revisionDate")
        if not rev:
            continue
        try:
            d = dt.datetime.fromisoformat(rev.replace("Z", "+00:00"))
        except ValueError:
            continue
        yrs = (now - d).days / 365.25
        if yrs >= STALE_YEARS:
            flag(it, "D", f"not touched in {yrs:.1f} years")

    # E - points at a machine, not a service
    for it in items:
        h, _ = parsed(it)
        if h and PRIVATE.match(h):
            flag(it, "E", "local address - only valid on that machine")

    # B - domain no longer resolves
    if args.dns:
        hosts = sorted({parsed(it)[0] for it in items
                        if parsed(it)[0] and not PRIVATE.match(parsed(it)[0])})
        print(f"resolving {len(hosts)} domains ...")

        def check(h):
            try:
                socket.getaddrinfo(h, None)
                return h, True
            except Exception:
                return h, False

        with ThreadPoolExecutor(max_workers=20) as ex:
            alive = dict(ex.map(check, hosts))
        for it in items:
            h, _ = parsed(it)
            if h and h in alive and not alive[h]:
                flag(it, "B", f"{h} does not resolve - service likely gone")

    names = {
        "A": "EXACT DUPLICATES - same site, same login, same password",
        "B": "DOMAIN NO LONGER RESOLVES",
        "C": "SERVICES YOU HAVE MOVED OFF",
        "D": f"UNTOUCHED FOR {STALE_YEARS}+ YEARS",
        "E": "LOCAL ADDRESSES - check these are still real machines",
    }
    advice = {
        "A": "Safe to delete the listed copy. The original stays.",
        "B": "Strong signal, but verify - a domain can fail to resolve for other reasons.",
        "C": "Matched your decommissioned list or private-host ports in bwtidy.json. Reject anything still in use.",
        "D": "Age alone proves nothing. Skim for accounts you have genuinely abandoned.",
        "E": "Not necessarily dead - just unreachable from anywhere else.",
    }

    byid = {it["id"]: it for it in items}
    grouped = defaultdict(list)
    for i, t in tier.items():
        grouped[t].append(i)

    lines = [f"# Vault cleanup checklist",
             f"",
             f"{len(items)} items scanned, {len(tier)} flagged. "
             f"Generated {now:%Y-%m-%d %H:%M} UTC.",
             f"",
             f"Nothing has been deleted. Work top-down - tier A is the most certain.",
             f""]
    for t in "ABCDE":
        ids = grouped.get(t)
        if not ids:
            continue
        lines += [f"## {t}. {names[t]}  ({len(ids)})", "", f"*{advice[t]}*", ""]
        for i in sorted(ids, key=lambda x: byid[x]["name"].lower()):
            it = byid[i]
            h, port = parsed(it)
            where = h + (f":{port}" if port else "")
            lines.append(f"- [ ] **{it['name']}** — {'; '.join(reasons[i])}  ")
            lines.append(f"      `{where or 'no url'}` · {fold(it)}")
        lines.append("")

    lines += ["## Not flagged", "",
              f"{len(items) - len(tier)} entries had no evidence of being dead. "
              "That does not mean you want them - it means no tool can tell. "
              "Skim them yourself when you have the patience.", ""]

    open(OUT, "w").write("\n".join(lines))

    print(f"\n{len(items)} items, {len(tier)} flagged -> {OUT}\n")
    for t in "ABCDE":
        if grouped.get(t):
            print(f"  {t}  {len(grouped[t]):>3}  {names[t]}")
    if not args.dns:
        print("\n(no DNS check - re-run with --dns to also test dead domains)")
    print(f"\nNothing was deleted. Open {OUT} and work through it in the app.")


if __name__ == "__main__":
    main()

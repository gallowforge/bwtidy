#!/usr/bin/env python3
"""
bwdupes.py - read-only duplicate report for a Bitwarden/Vaultwarden vault.

Never writes, never deletes, never calls a model. Groups by registrable domain
(so login.chase.com == chase.com) and normalized username (so user+shop@x.com
== user@x.com), then tiers each group by how confident the match is.

    export BW_SESSION="$(bw unlock --raw)"
    python3 bwdupes.py
"""

import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

# Second-level suffixes where the registrable domain is the third label.
MULTI_SUFFIX = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "net.uk", "sch.uk",
    "com.kw", "net.kw", "org.kw", "edu.kw", "gov.kw",
    "com.sa", "net.sa", "org.sa", "edu.sa", "gov.sa",
    "com.au", "net.au", "org.au", "edu.au", "gov.au",
    "co.jp", "or.jp", "ne.jp", "ac.jp", "go.jp",
    "com.br", "com.mx", "com.ar", "com.tr", "com.cn", "com.hk", "com.sg",
    "com.eg", "com.qa", "com.bh", "com.om", "com.jo", "com.lb",
    "co.in", "co.nz", "co.za", "co.kr", "co.il", "co.th", "co.id",
    "com.my", "com.ph", "com.vn", "com.pk", "com.bd",
    "org.il", "net.il", "gov.il",
}

# Services whose subdomains really are separate accounts - don't collapse them.
KEEP_SUBDOMAIN = {"myshopify.com", "github.io", "herokuapp.com", "netlify.app",
                  "vercel.app", "web.app", "firebaseapp.com", "pages.dev",
                  "workers.dev", "ts.net", "duckdns.org", "sharepoint.com"}


def bw(*args):
    session = os.environ.get("BW_SESSION")
    if not session:
        sys.exit('BW_SESSION is not set. Run: export BW_SESSION="$(bw unlock --raw)"')
    p = subprocess.run(["bw", *args, "--session", session, "--nointeraction"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"bw {' '.join(args)} failed:\n{p.stderr.strip()}")
    return p.stdout


def registrable(host):
    """chase.com, login.chase.com, www.chase.com -> chase.com"""
    host = host.lower().strip(".")
    parts = host.split(".")
    if len(parts) < 2:
        return host
    for keep in KEEP_SUBDOMAIN:
        if host.endswith("." + keep):
            return ".".join(parts[-(keep.count(".") + 2):])
    if ".".join(parts[-2:]) in MULTI_SUFFIX and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def domains(item):
    out = []
    for u in ((item.get("login") or {}).get("uris") or []):
        raw = (u.get("uri") or "").strip()
        if not raw or raw.startswith(("android://", "iosapp://")):
            continue
        if "://" not in raw:
            raw = "https://" + raw
        h = urlparse(raw).hostname
        if h:
            d = registrable(h)
            if d and d not in out:
                out.append(d)
    return out


def norm_user(u):
    """user+shop@x.com -> user@x.com ; User@X.com -> user@x.com"""
    u = (u or "").strip().lower()
    if "@" in u:
        local, _, dom = u.partition("@")
        local = local.split("+")[0]
        if dom in ("gmail.com", "googlemail.com"):
            local = local.replace(".", "")
        return f"{local}@{dom}"
    return u


def norm_name(n):
    n = (n or "").lower()
    n = re.sub(r"\((?:copy|old|new|\d+)\)|\b(?:copy|old|new|backup|dup|duplicate)\b", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return " ".join(n.split())


def main():
    items = json.loads(bw("list", "items"))
    logins = [i for i in items if i.get("login")]

    by_key = {}
    for it in logins:
        user = norm_user((it["login"] or {}).get("username"))
        for d in domains(it) or [""]:
            if not d and not user:
                continue
            by_key.setdefault((d, user), []).append(it)

    seen_pairs = set()
    tiers = {"exact": [], "same_site": [], "same_name": []}

    for (dom, user), group in by_key.items():
        if len(group) < 2:
            continue
        ids = frozenset(i["id"] for i in group)
        if ids in seen_pairs:
            continue
        seen_pairs.add(ids)
        pw = {(i["login"] or {}).get("password") for i in group}
        tier = "exact" if (user and len(pw) == 1) else "same_site"
        tiers[tier].append((dom or "(no url)", user or "(no username)", group))

    # Same-name groups that the domain pass missed entirely.
    by_name = {}
    for it in logins:
        by_name.setdefault(norm_name(it.get("name")), []).append(it)
    for name, group in by_name.items():
        if len(group) < 2 or not name:
            continue
        ids = frozenset(i["id"] for i in group)
        if ids in seen_pairs:
            continue
        seen_pairs.add(ids)
        tiers["same_name"].append((name, "", group))

    labels = {
        "exact": "SAME SITE + SAME USER + SAME PASSWORD  (safe to collapse)",
        "same_site": "SAME SITE + SAME USER, different password  (check before touching)",
        "same_name": "SAME NAME, different or missing site  (probably related)",
    }

    total = 0
    for tier in ("exact", "same_site", "same_name"):
        groups = tiers[tier]
        if not groups:
            continue
        print(f"\n{'=' * 70}\n{labels[tier]}  -  {len(groups)} group(s)\n{'=' * 70}")
        for dom, user, group in sorted(groups, key=lambda g: -len(g[2])):
            total += len(group) - 1
            head = f"{dom}" + (f"  [{user}]" if user else "")
            print(f"\n  {head}")
            for i in group:
                uris = ", ".join(
                    (u.get("uri") or "")[:60]
                    for u in ((i["login"] or {}).get("uris") or [])[:2]) or "(no uri)"
                print(f"    - {i['name'][:45]:<45} {uris}")

    print(f"\n{'=' * 70}")
    print(f"{len(logins)} logins scanned. ~{total} redundant entr{'y' if total == 1 else 'ies'} "
          f"if every group were collapsed.")
    print("Nothing was changed. Delete in the Bitwarden app, top tier first.")


if __name__ == "__main__":
    main()

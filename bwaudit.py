#!/usr/bin/env python3
"""
bwaudit.py - read-only health report for a Bitwarden/Vaultwarden vault.

No model, no network beyond the vault, no writes. Passwords are hashed for
comparison and NEVER printed, logged, or sent anywhere.

    export BW_SESSION="$(bw unlock --raw)"
    python3 bwaudit.py
"""

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from urllib.parse import urlparse

WEAK_LEN = 12
STALE_YEARS = 3

# Folders where a missing second factor actually matters.
CRITICAL_FOLDERS = {"Financial", "Email", "Infrastructure", "Government & Utilities"}


def bw(*args):
    session = os.environ.get("BW_SESSION")
    if not session:
        sys.exit('BW_SESSION is not set. Run: export BW_SESSION="$(bw unlock --raw)"')
    p = subprocess.run(["bw", *args, "--session", session, "--nointeraction"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"bw {' '.join(args)} failed:\n{p.stderr.strip()}")
    return p.stdout


def h(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def strength(pw):
    """Rough classes present + length. Not a real entropy estimate, just triage."""
    classes = sum(bool(re.search(p, pw)) for p in
                  (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^a-zA-Z0-9]"))
    return len(pw), classes


def host(item):
    for u in ((item.get("login") or {}).get("uris") or []):
        raw = (u.get("uri") or "").strip()
        if not raw or raw.startswith(("android://", "iosapp://")):
            continue
        if "://" not in raw:
            raw = "https://" + raw
        hn = urlparse(raw).hostname
        if hn:
            return hn.lower()
    return ""


def section(title, rows, note=""):
    if not rows:
        return 0
    print(f"\n{'=' * 72}\n{title}  ({len(rows)})\n{'=' * 72}")
    if note:
        print(f"{note}\n")
    for r in rows:
        print(f"  {r}")
    return len(rows)


def main():
    items = json.loads(bw("list", "items"))
    folders = {f["id"]: f["name"] for f in json.loads(bw("list", "folders"))}
    logins = [i for i in items if (i.get("login") or {}).get("password")]
    now = dt.datetime.now(dt.timezone.utc)

    def fname(it):
        return folders.get(it.get("folderId"), "(none)")

    def label(it):
        return f"{it['name'][:40]:<40} [{fname(it)}]"

    # --- reused ---
    by_pw = defaultdict(list)
    for it in logins:
        by_pw[h(it["login"]["password"])].append(it)
    reused = sorted((g for g in by_pw.values() if len(g) > 1),
                    key=lambda g: -len(g))

    # --- weak ---
    weak = []
    for it in logins:
        n, c = strength(it["login"]["password"])
        if n < WEAK_LEN or c <= 2:
            weak.append((n, c, it))
    weak.sort(key=lambda x: (x[0], x[1]))

    # --- no 2FA in critical folders ---
    no2fa = [it for it in logins
             if fname(it) in CRITICAL_FOLDERS and not (it["login"] or {}).get("totp")]

    # --- autofill broken: no usable URI ---
    nouri = [it for it in logins if not host(it)]

    # --- stale ---
    stale = []
    for it in logins:
        rev = it.get("revisionDate")
        if not rev:
            continue
        try:
            d = dt.datetime.fromisoformat(rev.replace("Z", "+00:00"))
        except ValueError:
            continue
        yrs = (now - d).days / 365.25
        if yrs >= STALE_YEARS:
            stale.append((yrs, it))
    stale.sort(key=lambda x: -x[0])

    print(f"\nScanned {len(items)} items ({len(logins)} with passwords) "
          f"across {len(folders)} folders.")
    print("No password is printed anywhere in this report.")

    total = 0
    if reused:
        print(f"\n{'=' * 72}\nREUSED PASSWORDS  ({len(reused)} password(s) shared across "
              f"{sum(len(g) for g in reused)} entries)\n{'=' * 72}")
        print("Fix top-down. Breaking one of these breaks every entry in its group.\n")
        for n, group in enumerate(reused, 1):
            crit = any(fname(i) in CRITICAL_FOLDERS for i in group)
            print(f"  Group {n} - {len(group)} entries" + ("   << includes a critical account" if crit else ""))
            for i in group:
                print(f"      {label(i)}")
            total += len(group) - 1
            print()

    total += section(
        f"WEAK PASSWORDS (under {WEAK_LEN} chars or 2 character classes or fewer)",
        [f"{n:>3} chars, {c} class(es)  {label(it)}" for n, c, it in weak],
        "Length matters more than symbols. Regenerate these at 20+ chars.")

    total += section(
        "NO SECOND FACTOR ON A CRITICAL ACCOUNT",
        [label(it) for it in sorted(no2fa, key=lambda i: fname(i))],
        "Bitwarden can store the TOTP seed itself - add it on the site, then paste the seed here.")

    total += section(
        "NO WEBSITE SET - AUTOFILL CANNOT WORK",
        [label(it) for it in nouri],
        "Add the login URL to each so the browser extension offers to fill it.")

    total += section(
        f"NOT TOUCHED IN {STALE_YEARS}+ YEARS",
        [f"{y:>4.1f} yrs  {label(it)}" for y, it in stale[:40]],
        "Age alone is not a problem. Worth a look for dead accounts to delete.")

    print(f"\n{'=' * 72}")
    if total:
        print(f"{total} item(s) flagged. Nothing was changed.")
        print("Highest value first: reused passwords, then no-2FA on critical accounts.")
    else:
        print("Nothing flagged. Vault is in good shape.")


if __name__ == "__main__":
    main()

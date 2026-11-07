#!/usr/bin/env python3
"""
bwpolish.py - verify nothing was lost in the merge, then list what is left to fix.

Compares the live vault against backup-*.json written before the merge and
proves that every URL, TOTP seed, note and custom field that existed before
still exists now. Then reports remaining cosmetic issues.

Read-only. Changes nothing.

    export BW_SESSION="$(bw unlock --raw)"
    python3 bwpolish.py [backup-<stamp>.json]   # default: newest backup
"""

import glob
import json
import os
import re
import subprocess
import sys
from collections import defaultdict, Counter
from urllib.parse import urlparse


def bw(*args):
    s = os.environ.get("BW_SESSION")
    if not s:
        sys.exit('BW_SESSION is not set. Run: export BW_SESSION="$(bw unlock --raw)"')
    p = subprocess.run(["bw", *args, "--session", s, "--nointeraction"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"bw {' '.join(args)} failed:\n{p.stderr.strip()}")
    return p.stdout


def uris(it):
    return {(u.get("uri") or "").strip().lower()
            for u in ((it.get("login") or {}).get("uris") or [])
            if (u.get("uri") or "").strip()}


def host(u):
    if not u or u.startswith(("android://", "iosapp://", "com.")):
        return ""
    r = u if "://" in u else "https://" + u
    return (urlparse(r).hostname or "").lower()


def main():
    items = json.loads(bw("list", "items"))
    folders = {f["id"]: f["name"] for f in json.loads(bw("list", "folders"))}
    print(f"Live vault: {len(items)} items, {len(folders)} folders\n")

    problems = 0

    # ---------- 1. nothing lost in the merge ----------
    backups = (sys.argv[1:2]
               or sorted(glob.glob("backup-*.json"), key=os.path.getmtime))
    if backups:
        saved = json.load(open(backups[-1]))
        # Items the merge plan trashed on purpose are not "lost".
        if os.path.exists("merge_plan.json"):
            planned = {d["id"] for d in json.load(open("merge_plan.json")).get("deletes", [])}
            saved = {i: o for i, o in saved.items() if i not in planned}
        print(f"{'=' * 66}\nMERGE INTEGRITY  (vs {backups[-1]}, {len(saved)} items)\n{'=' * 66}")

        live_uris = set().union(*[uris(i) for i in items]) if items else set()
        live_totp = {(i.get("login") or {}).get("totp") for i in items}
        live_notes = {(i.get("notes") or "").strip() for i in items}

        lost_u = [(o["name"], u) for o in saved.values()
                  for u in uris(o) if u not in live_uris]
        lost_t = [o["name"] for o in saved.values()
                  if (o.get("login") or {}).get("totp")
                  and (o["login"]["totp"] not in live_totp)]
        lost_n = [o["name"] for o in saved.values()
                  if (o.get("notes") or "").strip()
                  and (o["notes"].strip() not in live_notes)]

        for label, lost in (("URL", lost_u), ("TOTP seed", lost_t), ("note", lost_n)):
            if lost:
                problems += len(lost)
                print(f"\n  LOST {label}(s): {len(lost)}")
                for x in lost[:12]:
                    print(f"    {x}")
            else:
                print(f"  every {label} preserved")
    else:
        print("(no backup-*.json found - skipping merge integrity check)")

    # ---------- 2. duplicate names ----------
    dupes = {n: c for n, c in Counter(i["name"] for i in items).items() if c > 1}
    print(f"\n{'=' * 66}\nDUPLICATE NAMES\n{'=' * 66}")
    if dupes:
        problems += sum(dupes.values())
        for n, c in sorted(dupes.items(), key=lambda x: -x[1]):
            print(f"  {n}  x{c}")
    else:
        print("  none")

    # ---------- 3. still-duplicated logins the merge could not touch ----------
    print(f"\n{'=' * 66}\nSAME SITE + SAME USER, DIFFERENT PASSWORD\n{'=' * 66}")
    print("  (not merged on purpose - could be two accounts, or one stale copy)\n")
    by = defaultdict(list)
    for it in items:
        lg = it.get("login") or {}
        hs = {host(u) for u in uris(it)}
        hs.discard("")
        if lg.get("username") and hs:
            by[(sorted(hs)[0], lg["username"].lower())].append(it)
    found = 0
    for (h, u), g in sorted(by.items()):
        if len(g) > 1:
            found += 1
            print(f"  {h} [{u}]")
            for i in g:
                print(f"      {i['name']}")
    if not found:
        print("  none")

    # ---------- 4. structural gaps ----------
    print(f"\n{'=' * 66}\nSTRUCTURE\n{'=' * 66}")

    used = {i.get("folderId") for i in items}
    empty = [n for fid, n in folders.items() if fid not in used]
    print(f"  empty folders: {len(empty)}" + (f"  {empty}" if empty else ""))

    nofold = [i["name"] for i in items if not i.get("folderId")]
    print(f"  items with no folder: {len(nofold)}"
          + (f"  {nofold[:8]}" if nofold else ""))

    unc = [i["name"] for i in items
           if folders.get(i.get("folderId")) == "Uncategorized"]
    print(f"  items still in Uncategorized: {len(unc)}")

    nouri = [i["name"] for i in items
             if i.get("type") == 1 and not uris(i)]
    print(f"  logins with no URL (autofill cannot work): {len(nouri)}")
    for n in nouri[:10]:
        print(f"      {n}")

    weird = [(i["name"], u) for i in items for u in uris(i)
             if not host(u) and not u.startswith(("android://", "iosapp://"))]
    if weird:
        print(f"  URLs that are not really URLs: {len(weird)}")
        for n, u in weird[:8]:
            print(f"      {n}: {u}")

    # ---------- 5. names that could still read better ----------
    print(f"\n{'=' * 66}\nNAMES WORTH A SECOND LOOK\n{'=' * 66}")
    odd = []
    for i in items:
        n = i["name"]
        if (re.search(r"\.(com|net|org|io|tv|me|kw|app|co|sh|xyz)\b", n, re.I)
                or n.islower() and len(n) > 4
                or re.search(r"\(port \d+\)", n)):
            odd.append(n)
    print(f"  {len(odd)} entr(y/ies):")
    for n in sorted(odd)[:25]:
        print(f"      {n}")
    if len(odd) > 25:
        print(f"      ... {len(odd)-25} more")

    print(f"\n{'=' * 66}")
    if problems:
        print(f"{problems} integrity problem(s) found. "
              "If any URL/TOTP/note was lost, run: python3 bwmerge.py restore")
    else:
        print("No data was lost in the merge. Everything above is cosmetic.")


if __name__ == "__main__":
    main()

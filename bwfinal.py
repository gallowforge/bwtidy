#!/usr/bin/env python3
"""
bwfinal.py - the last pass. Everything that can be determined, determined.

  1. Re-classifies everything still in Uncategorized. Worth redoing now that
     entries have real names instead of raw hostnames.
  2. Adds the missing URL to logins that have none, where the service is
     unambiguous, so autofill starts working.
  3. Converts entries that are not logins (a device, a recovery key) into
     Secure Notes, where they belong.
  4. Deletes empty folders.
  5. Reports the duplicate pairs it will NOT guess at, with the age of each
     password so you can tell which is stale in one glance.

Backs up every affected item first. Soft-deletes only. Undo the item changes
with `python3 bwmerge.py restore backup-final-<stamp>.json`.

    export BW_SESSION="$(bw unlock --raw)"
    python3 bwfinal.py plan
    python3 bwfinal.py apply
"""

import argparse
import base64
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from urllib.parse import urlparse

from bwconfig import CONFIG, MODEL, lmstudio_url

LMSTUDIO = lmstudio_url()
PLAN = "final_plan.json"

FOLDERS = ["Financial", "Email", "Social", "Shopping", "Work", "Development",
           "Infrastructure", "Entertainment", "Government & Utilities", "Health",
           "Education", "Travel", "Gaming", "AI & SaaS Tools", "Archive",
           "Uncategorized"]

# URLs for logins that have none. Only services identifiable beyond doubt.
# Set in bwtidy.json: {"add_url": {"<exact item name>": "<url>"}}
ADD_URL = dict(CONFIG["add_url"])

# Entries that are not website logins at all (a device, a recovery key).
# Set in bwtidy.json: {"to_note": ["<exact item name>", ...]}
TO_NOTE = set(CONFIG["to_note"])

SYSTEM_PROMPT = """You are a precise data classifier. You assign vault entries to folders.

RULES:
1. Assign every entry. Never skip one.
2. Return the exact `id` given, character for character.
3. `folder` MUST be copied verbatim from the ALLOWED FOLDERS list.
4. Judge from the entry's name, username and website.
5. Only use "Uncategorized" if the entry is genuinely unclassifiable. You are
   seeing these because a first pass gave up on them - try harder this time,
   the names are now clean and readable.
6. Banks, cards, payment, crypto, insurance -> "Financial".
7. Servers, routers, DNS, registrars, NAS, self-hosted services -> "Infrastructure".
8. Newspapers, magazines, news sites, streaming, music, video, film -> "Entertainment".
9. Online stores and marketplaces of any kind -> "Shopping".
10. Output JSON only. No prose, no markdown fences.
"""

SCHEMA = {"type": "json_schema", "json_schema": {
    "name": "assignments", "strict": True,
    "schema": {"type": "object", "properties": {"assignments": {
        "type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"},
            "folder": {"type": "string", "enum": FOLDERS}},
            "required": ["id", "folder"], "additionalProperties": False}}},
        "required": ["assignments"], "additionalProperties": False}}}


def bw(*args):
    s = os.environ.get("BW_SESSION")
    if not s:
        sys.exit('BW_SESSION is not set. Run: export BW_SESSION="$(bw unlock --raw)"')
    p = subprocess.run(["bw", *args, "--session", s, "--nointeraction"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"bw {' '.join(args[:3])}: {p.stderr.strip()}")
    return p.stdout


def uris(it):
    return [(u.get("uri") or "").strip()
            for u in ((it.get("login") or {}).get("uris") or [])
            if (u.get("uri") or "").strip()]


def host(it):
    for u in uris(it):
        if u.startswith(("android://", "iosapp://", "com.")):
            continue
        r = u if "://" in u else "https://" + u
        h = urlparse(r).hostname
        if h:
            return h.lower()
    return ""


def classify(batch):
    lines = "\n".join(
        f'{i+1}. id={it["id"]} | name={it["name"]!r} | site={host(it)!r} '
        f'| user={((it.get("login") or {}).get("username") or "")[:35]!r}'
        for i, it in enumerate(batch))
    payload = {"model": MODEL, "temperature": 0, "max_tokens": 3000,
               "response_format": SCHEMA,
               "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content":
                             "ALLOWED FOLDERS:\n" + "\n".join(f"- {f}" for f in FOLDERS)
                             + f"\n\nENTRIES:\n{lines}\n\nReturn exactly {len(batch)}."}]}
    req = urllib.request.Request(f"{LMSTUDIO}/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        body = json.load(r)
    t = body["choices"][0]["message"]["content"].strip()
    if t.startswith("```"):
        t = t.split("```")[1].lstrip("json").strip()
    return {a["id"]: a["folder"] for a in json.loads(t)["assignments"]
            if a["folder"] in FOLDERS}


def pw_age(it):
    d = ((it.get("login") or {}).get("passwordRevisionDate")
         or it.get("creationDate"))
    if not d:
        return "unknown"
    try:
        t = dt.datetime.fromisoformat(d.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    days = (dt.datetime.now(dt.timezone.utc) - t).days
    return f"{days}d ago"


def cmd_plan(_):
    items = json.loads(bw("list", "items"))
    folders = {f["id"]: f["name"] for f in json.loads(bw("list", "folders"))}
    name2fid = {n: i for i, n in folders.items()}

    unc = [it for it in items
           if folders.get(it.get("folderId")) == "Uncategorized"]
    print(f"{len(items)} items. {len(unc)} in Uncategorized.\n")

    moves = {}
    if unc:
        for i in range(0, len(unc), 30):
            chunk = unc[i:i + 30]
            print(f"  reclassifying {i+1}-{i+len(chunk)} of {len(unc)}")
            try:
                for iid, f in classify(chunk).items():
                    if f != "Uncategorized":
                        moves[iid] = f
            except Exception as e:
                print(f"    failed ({e})", file=sys.stderr)

    add_url = [{"id": it["id"], "name": it["name"], "url": ADD_URL[it["name"]]}
               for it in items if it["name"] in ADD_URL and not uris(it)]
    to_note = [{"id": it["id"], "name": it["name"]}
               for it in items if it["name"] in TO_NOTE and it.get("type") == 1]

    used = {it.get("folderId") for it in items}
    # a folder is only droppable if nothing lands in it after the moves
    landing = {name2fid.get(f) for f in moves.values()}
    empty = [{"id": fid, "name": n} for fid, n in folders.items()
             if fid not in used and fid not in landing]

    # ambiguous pairs - reported, never guessed
    by = defaultdict(list)
    for it in items:
        lg = it.get("login") or {}
        if lg.get("username") and host(it):
            by[(host(it), lg["username"].lower())].append(it)
    pairs = [(k, g) for k, g in by.items()
             if len({(i.get("login") or {}).get("password") for i in g}) > 1]

    plan = {"moves": moves, "add_url": add_url, "to_note": to_note,
            "drop_folders": empty}
    json.dump(plan, open(PLAN, "w"), indent=2, ensure_ascii=False)

    if moves:
        c = defaultdict(int)
        for f in moves.values():
            c[f] += 1
        print(f"\nRECLASSIFY {len(moves)} of {len(unc)} out of Uncategorized:")
        for f in sorted(c, key=lambda x: -c[x]):
            print(f"  {c[f]:>3}  {f}")
        print(f"  {len(unc)-len(moves)} genuinely stay Uncategorized")
    for label, rows in (("ADD URL", add_url), ("CONVERT TO SECURE NOTE", to_note),
                        ("DROP EMPTY FOLDER", empty)):
        if rows:
            print(f"\n{label}:")
            for r in rows:
                print(f"  {r['name']}" + (f"  -> {r.get('url')}" if r.get("url") else ""))
    if pairs:
        print(f"\nNOT TOUCHING - same site + user, different password ({len(pairs)}):")
        print("  password age tells you which is stale\n")
        for (h, u), g in pairs:
            print(f"  {h} [{u}]")
            for it in g:
                print(f"      {it['name'][:38]:<38} password set {pw_age(it)}")
    print(f"\nReview {PLAN}, then: python3 bwfinal.py apply")


def cmd_apply(_):
    if not os.path.exists(PLAN):
        sys.exit(f"No {PLAN}. Run: python3 bwfinal.py plan")
    plan = json.load(open(PLAN))
    items = {it["id"]: it for it in json.loads(bw("list", "items"))}
    folders = {f["name"]: f["id"] for f in json.loads(bw("list", "folders"))}

    touched = (list(plan["moves"]) + [r["id"] for r in plan["add_url"]]
               + [r["id"] for r in plan["to_note"]])
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bkp = f"backup-final-{stamp}.json"
    json.dump({i: items[i] for i in touched if i in items}, open(bkp, "w"),
              indent=2, ensure_ascii=False)
    print(f"backed up {len(touched)} item(s) -> {bkp}\n")

    n = 0
    for iid, fname in plan["moves"].items():
        it = items.get(iid)
        if not it or fname not in folders:
            continue
        it["folderId"] = folders[fname]
        bw("edit", "item", iid, base64.b64encode(json.dumps(it).encode()).decode())
        n += 1
        print(f"  {it['name'][:38]:<38} -> {fname}")

    for r in plan["add_url"]:
        it = items.get(r["id"])
        if not it:
            continue
        it.setdefault("login", {})["uris"] = [{"uri": r["url"], "match": None}]
        bw("edit", "item", it["id"], base64.b64encode(json.dumps(it).encode()).decode())
        print(f"  URL added: {it['name']} -> {r['url']}")

    for r in plan["to_note"]:
        it = items.get(r["id"])
        if not it:
            continue
        lg = it.get("login") or {}
        keep = []
        if lg.get("username"):
            keep.append(f"username: {lg['username']}")
        if lg.get("password"):
            keep.append(f"value: {lg['password']}")
        it["notes"] = ((it.get("notes") or "") + "\n" + "\n".join(keep)).strip()
        it["type"] = 2
        it["login"] = None
        it["secureNote"] = {"type": 0}
        bw("edit", "item", it["id"], base64.b64encode(json.dumps(it).encode()).decode())
        print(f"  converted to Secure Note: {it['name']}")

    for f in plan["drop_folders"]:
        try:
            bw("delete", "folder", f["id"])
            print(f"  folder deleted: {f['name']}")
        except RuntimeError as e:
            print(f"  could not delete folder {f['name']}: {e}")

    bw("sync")
    print(f"\n{n} reclassified, {len(plan['add_url'])} URLs added, "
          f"{len(plan['to_note'])} converted, {len(plan['drop_folders'])} folders dropped.")
    print(f"Backup: {bkp}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(fn=cmd_plan)
    sub.add_parser("apply").set_defaults(fn=cmd_apply)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)

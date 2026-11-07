#!/usr/bin/env python3
"""
bwtidy.py - organize a Bitwarden vault into folders using a local LM Studio model.

Only each item's id, name, username and hostname are sent to the model, and
only to a loopback LM Studio server. Passwords, TOTP seeds, notes and custom
fields never leave the `bw` process output.

    export BW_SESSION="$(bw unlock --raw)"
    python3 bwtidy.py plan      # classify, write plan.json + fingerprint.json
    python3 bwtidy.py apply     # move items as planned
    python3 bwtidy.py verify    # prove every credential is byte-identical
    python3 bwtidy.py revert    # move every planned item back
"""

import argparse, base64, hashlib, json, os, subprocess, sys
import urllib.error, urllib.request
from urllib.parse import urlparse

from bwconfig import MODEL, lmstudio_url

LMSTUDIO = lmstudio_url()
BATCH = 35
PLAN = "plan.json"
FINGERPRINT = "fingerprint.json"

FOLDERS = [
    "Financial", "Email", "Social", "Shopping", "Work", "Development",
    "Infrastructure", "Entertainment", "Government & Utilities", "Health",
    "Education", "Travel", "Gaming", "AI & SaaS Tools", "Archive", "Uncategorized",
]

SYSTEM_PROMPT = """You are a precise data classifier. You assign vault entries to folders.

RULES - follow exactly:
1. You MUST assign every entry you are given. Never skip one.
2. You MUST return the exact `id` string you were given, character for character.
3. The `folder` value MUST be copied verbatim from the ALLOWED FOLDERS list.
4. Judge from the entry's name, username, and hostname. The hostname is the strongest signal.
5. If an entry does not clearly belong anywhere, assign "Uncategorized". Guessing wrongly is worse.
6. Banks, cards, payment processors, brokerages, crypto exchanges, insurance -> "Financial".
7. Servers, VPS, routers, DNS, registrars, NAS, hypervisors, self-hosted services -> "Infrastructure".
8. Code hosting, package registries, CI, developer APIs -> "Development".
9. Output JSON only. No prose, no explanation, no markdown fences.
"""

USER_TEMPLATE = """ALLOWED FOLDERS (choose one, verbatim):
{folders}

ENTRIES:
{entries}

Return a JSON object: {{"assignments": [{{"id": "<exact id>", "folder": "<exact folder>"}}, ...]}}
Return exactly {n} assignments - one per entry, in the same order."""

SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "assignments", "strict": True,
        "schema": {
            "type": "object",
            "properties": {"assignments": {"type": "array", "items": {
                "type": "object",
                "properties": {"id": {"type": "string"},
                               "folder": {"type": "string", "enum": FOLDERS}},
                "required": ["id", "folder"], "additionalProperties": False}}},
            "required": ["assignments"], "additionalProperties": False,
        },
    },
}

def bw(*args, stdin=None):
    session = os.environ.get("BW_SESSION")
    if not session:
        sys.exit('BW_SESSION is not set. Run: export BW_SESSION="$(bw unlock --raw)"')
    p = subprocess.run(["bw", *args, "--session", session, "--nointeraction"],
                       input=stdin, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"bw {' '.join(args)} failed:\n{p.stderr.strip()}")
    return p.stdout

def load_items():
    return json.loads(bw("list", "items"))

def load_folders():
    return json.loads(bw("list", "folders"))

SENSITIVE_KEYS = {"password", "totp", "notes", "fields", "card", "identity",
                  "passwordHistory", "attachments", "sshKey"}

def hostname(item):
    uris = (item.get("login") or {}).get("uris") or []
    hosts = []
    for u in uris:
        raw = (u.get("uri") or "").strip()
        if not raw:
            continue
        if "://" not in raw:
            raw = "https://" + raw
        h = (urlparse(raw).hostname or "").lower()
        if h.startswith("www."):
            h = h[4:]
        if h and h not in hosts:
            hosts.append(h)
    return ", ".join(hosts[:3])

def slim(item):
    return {"id": item["id"],
            "name": (item.get("name") or "").strip()[:80],
            "username": ((item.get("login") or {}).get("username") or "").strip()[:60],
            "hostname": hostname(item)}

def secret_fingerprint(items):
    out = {}
    for it in items:
        blob = json.dumps({k: v for k, v in it.items()
                           if k in SENSITIVE_KEYS or k == "login"},
                          sort_keys=True, ensure_ascii=False)
        out[it["id"]] = hashlib.sha256(blob.encode()).hexdigest()
    return out

def model_name():
    try:
        with urllib.request.urlopen(f"{LMSTUDIO}/models", timeout=10) as r:
            ids = [m["id"] for m in json.load(r)["data"]]
    except Exception as e:
        sys.exit(f"Cannot reach LM Studio at {LMSTUDIO}. Start the server. {e}")
    if MODEL not in ids:
        sys.exit(f"Model not loaded in LM Studio. Found: {ids}")
    return MODEL

def classify(batch, model):
    entries = "\n".join(
        f'{i+1}. id={e["id"]} | name={e["name"]!r} | user={e["username"]!r} | host={e["hostname"]!r}'
        for i, e in enumerate(batch))
    payload = {"model": model, "temperature": 0, "top_p": 1, "max_tokens": 4096,
               "response_format": SCHEMA,
               "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": USER_TEMPLATE.format(
                                folders="\n".join(f"- {f}" for f in FOLDERS),
                                entries=entries, n=len(batch))}]}
    req = urllib.request.Request(f"{LMSTUDIO}/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        body = json.load(r)
    text = body["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    return json.loads(text)["assignments"]

def classify_validated(batch, model, retries=3):
    want = {e["id"] for e in batch}
    for attempt in range(1, retries + 1):
        try:
            got = classify(batch, model)
        except Exception as e:
            print(f"    batch error ({e}), retry {attempt}/{retries}", file=sys.stderr)
            continue
        mapping = {a["id"]: a["folder"] for a in got
                   if a["id"] in want and a["folder"] in FOLDERS}
        if set(mapping) == want:
            return mapping
        print(f"    batch incomplete ({len(mapping)}/{len(want)}), retry {attempt}/{retries}",
              file=sys.stderr)
    if len(batch) > 1:
        mid = len(batch) // 2
        out = classify_validated(batch[:mid], model, retries)
        out.update(classify_validated(batch[mid:], model, retries))
        return out
    return {batch[0]["id"]: "Uncategorized"}

def dupes(items):
    seen = {}
    for it in items:
        login = it.get("login") or {}
        key = (hostname(it), (login.get("username") or "").lower())
        if not key[0] and not key[1]:
            continue
        seen.setdefault(key, []).append(it["name"])
    hits = {k: v for k, v in seen.items() if len(v) > 1}
    if hits:
        print(f"\n{len(hits)} likely duplicate group(s) - review manually, nothing is deleted:")
        for (h, u), names in list(hits.items())[:20]:
            print(f"  {h} / {u}: {', '.join(names)}")

def cmd_plan(_):
    items = load_items()
    current = {f["id"]: f["name"] for f in load_folders()}
    model = model_name()
    print(f"model: {model}\nitems: {len(items)}")
    slims = [slim(i) for i in items]
    assignments = {}
    for i in range(0, len(slims), BATCH):
        chunk = slims[i:i + BATCH]
        print(f"  classifying {i+1}-{i+len(chunk)} of {len(slims)}")
        assignments.update(classify_validated(chunk, model))
    assert set(assignments) == {i["id"] for i in items}, "id set mismatch - aborting"
    plan = []
    for it in items:
        target = assignments[it["id"]]
        now = current.get(it.get("folderId"), "(none)")
        if now != target:
            plan.append({"id": it["id"], "name": it["name"], "from": now, "to": target})
    with open(PLAN, "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    with open(FINGERPRINT, "w") as f:
        json.dump(secret_fingerprint(items), f, indent=2)
    counts = {}
    for p in plan:
        counts[p["to"]] = counts.get(p["to"], 0) + 1
    print(f"\n{len(plan)} of {len(items)} items would move:")
    for k in sorted(counts, key=lambda x: -counts[x]):
        print(f"  {counts[k]:>4}  {k}")
    dupes(items)
    print(f"\nReview {PLAN}, then: python3 bwtidy.py apply")

def cmd_apply(_):
    if not os.path.exists(PLAN):
        sys.exit("No plan.json. Run: python3 bwtidy.py plan")
    plan = json.load(open(PLAN))
    if not plan:
        return print("Nothing to do.")
    existing = {f["name"]: f["id"] for f in load_folders()}
    for name in sorted({p["to"] for p in plan} - set(existing)):
        enc = base64.b64encode(json.dumps({"name": name}).encode()).decode()
        existing[name] = json.loads(bw("create", "folder", enc))["id"]
        print(f"created folder: {name}")
    items = {it["id"]: it for it in load_items()}
    ok = 0
    for p in plan:
        item = items.get(p["id"])
        if not item:
            print(f"  skipped (no longer in vault): {p['name']}")
            continue
        item["folderId"] = existing[p["to"]]
        enc = base64.b64encode(json.dumps(item).encode()).decode()
        bw("edit", "item", p["id"], enc)
        ok += 1
        print(f"  [{ok}/{len(plan)}] {p['name']} -> {p['to']}")
    bw("sync")
    print(f"\nMoved {ok} items. Now run: python3 bwtidy.py verify")

def cmd_revert(_):
    if not os.path.exists(PLAN):
        sys.exit("No plan.json - nothing to revert.")
    plan = json.load(open(PLAN))
    existing = {f["name"]: f["id"] for f in load_folders()}
    items = {it["id"]: it for it in load_items()}
    ok = skip = 0
    for p in plan:
        item = items.get(p["id"])
        if not item or item.get("folderId") != existing.get(p["to"]):
            skip += 1           # gone, or moved again since apply
            continue
        if p["from"] == "(none)":
            item["folderId"] = None
        else:
            if p["from"] not in existing:
                enc = base64.b64encode(json.dumps({"name": p["from"]}).encode()).decode()
                existing[p["from"]] = json.loads(bw("create", "folder", enc))["id"]
            item["folderId"] = existing[p["from"]]
        enc = base64.b64encode(json.dumps(item).encode()).decode()
        bw("edit", "item", p["id"], enc)
        ok += 1
    bw("sync")
    print(f"Reverted {ok} item(s)." + (f" Skipped {skip} (changed since apply)." if skip else ""))

def cmd_verify(_):
    if not os.path.exists(FINGERPRINT):
        sys.exit("No fingerprint.json. Run plan first.")
    before = json.load(open(FINGERPRINT))
    after = secret_fingerprint(load_items())
    missing = set(before) - set(after)
    changed = [i for i in before if i in after and before[i] != after[i]]
    if missing:
        print(f"FAIL: {len(missing)} item(s) missing from vault")
    if changed:
        print(f"FAIL: {len(changed)} item(s) have altered credentials")
    if not missing and not changed:
        print(f"PASS: all {len(before)} items present, every credential byte-identical.")
    return 1 if (missing or changed) else 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(fn=cmd_plan)
    sub.add_parser("apply").set_defaults(fn=cmd_apply)
    sub.add_parser("verify").set_defaults(fn=cmd_verify)
    sub.add_parser("revert").set_defaults(fn=cmd_revert)
    args = ap.parse_args()
    sys.exit(args.fn(args) or 0)

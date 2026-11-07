"""
bwconfig.py - settings shared by the bwtidy scripts.

Vault-specific knowledge (services you have moved off, domains you have
confirmed dead, items to convert) lives in a local JSON file, not in the code.
Copy examples/bwtidy.example.json to ./bwtidy.json and edit it, or point
BWTIDY_CONFIG at another path. Every key is optional.

Importing this module also sets a 077 umask: plans, fingerprints and backups
contain vault data (backups contain full plaintext items), so every file the
scripts write is readable by the owner only.
"""

import ipaddress
import json
import os
import sys
from urllib.parse import urlparse

os.umask(0o077)

DEFAULTS = {
    # substring of an item's name or host -> why it is considered gone
    "decommissioned": {},
    # domains confirmed dead; the only domains bwmerge will ever trash
    "dead_domains": [],
    # hosts whose plain DNS lookup fails although the service is alive
    "dns_false_positives": ["microsoftonline.com"],
    # private host suffix and the ports still served under it; entries on
    # other ports are flagged by bwdead
    "private_host": {"suffix": "", "live_ports": []},
    # exact item name -> URL to add when the login has none (bwfinal)
    "add_url": {},
    # exact item names that are not website logins; converted to Secure Notes
    "to_note": [],
}


def load():
    path = os.environ.get("BWTIDY_CONFIG", "bwtidy.json")
    cfg = {k: (v.copy() if isinstance(v, (dict, list)) else v)
           for k, v in DEFAULTS.items()}
    if os.path.exists(path):
        try:
            with open(path) as f:
                user = json.load(f)
        except (OSError, ValueError) as e:
            sys.exit(f"Cannot read {path}: {e}")
        unknown = set(user) - set(DEFAULTS) - {"_comment"}
        if unknown:
            sys.exit(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
        cfg.update({k: v for k, v in user.items() if k in DEFAULTS})
    return cfg


CONFIG = load()

MODEL = os.environ.get("LMSTUDIO_MODEL",
                       "mistralai_mistral-small-3.2-24b-instruct-2506")


def lmstudio_url():
    """The LM Studio endpoint. Item names, usernames and hostnames are sent to
    it, so anything other than a loopback address is refused unless
    BWTIDY_ALLOW_REMOTE_LLM=1 is set explicitly."""
    url = os.environ.get("LMSTUDIO_URL", "http://localhost:1234/v1").rstrip("/")
    host = (urlparse(url).hostname or "").lower()
    loopback = host == "localhost"
    if not loopback:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
    if not loopback and os.environ.get("BWTIDY_ALLOW_REMOTE_LLM") != "1":
        sys.exit(f"Refusing to send vault metadata to {url}: not a loopback "
                 "address. Set BWTIDY_ALLOW_REMOTE_LLM=1 if that host is yours.")
    return url

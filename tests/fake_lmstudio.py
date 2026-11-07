"""
Deterministic stand-in for LM Studio's OpenAI-compatible API, for tests and
demos. Answers the two structured-output requests the scripts make:
"assignments" (folder classification) and "renames" (clean names), using
keyword rules instead of a model.

    python3 tests/fake_lmstudio.py          # serves on 127.0.0.1:1234
"""
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "mistralai_mistral-small-3.2-24b-instruct-2506"

RULES = [
    (r"github|gitlab|npm", "Development"),
    (r"paypal|bank|card", "Financial"),
    (r"steam", "Gaming"),
    (r"amazon|shop|store", "Shopping"),
    (r"reddit|forum", "Social"),
    (r"router|nas|webhost|10\.0\.|home\.arpa", "Infrastructure"),
    (r"mail", "Email"),
]

# Every chat request body received, so tests can prove what reaches the model.
REQUESTS = []

BRANDS = {"github": "GitHub", "paypal": "PayPal", "amazon": "Amazon",
          "reddit": "Reddit", "steam": "Steam"}


def classify(line):
    low = line.lower()
    for pattern, folder in RULES:
        if re.search(pattern, low):
            return folder
    return "Uncategorized"


def rename(current):
    name = re.sub(r"\s*\((copy|old|new|\d+)\)\s*$", "", current, flags=re.I)
    name = re.sub(r"^(https?://)?(www\.)?", "", name)
    name = re.sub(r"\.(com|org|net)$", "", name)
    return BRANDS.get(name.lower(), name[:1].upper() + name[1:])


def answer(payload):
    kind = payload["response_format"]["json_schema"]["name"]
    text = payload["messages"][-1]["content"]
    if kind == "assignments":
        rows = [{"id": m.group(1), "folder": classify(line)}
                for line in text.splitlines()
                if (m := re.search(r"\bid=(\S+)", line))]
        return {"assignments": rows}
    if kind == "renames":
        rows = [{"id": m.group(1), "name": rename(m.group(2))}
                for m in re.finditer(r"id=(\S+) \| current='([^']*)'", text)]
        return {"renames": rows}
    raise ValueError(f"unknown schema {kind}")


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith("/models"):
            return self._send({"data": [{"id": MODEL}]})
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        REQUESTS.append(payload)
        content = json.dumps(answer(payload))
        self._send({"choices": [{"message": {"role": "assistant", "content": content}}]})

    def log_message(self, *_):
        pass


def start(port=0):
    """Start in a background thread. Returns (server, base_url)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 1234
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"fake LM Studio on http://127.0.0.1:{port}/v1", file=sys.stderr)
    server.serve_forever()

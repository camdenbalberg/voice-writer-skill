# -*- coding: utf-8 -*-
"""Voice Writer server: serves *-voice.html worksheets over http://127.0.0.1 so browser
extensions (Grammarly) run on them, and keeps answers on disk next to each worksheet.

Usage:
    python server.py [--port 8795] [--root DIR ...] [--host ADDR ...]

    --root  folder to find worksheets in (repeatable; default ~/Documents). Subfolders count.
    --host  address to listen on (repeatable; default 127.0.0.1). Add a second --host (e.g. a
            Tailscale IP) to open worksheets from your other devices; if that address isn't up
            yet, it is retried every 30 s while 127.0.0.1 keeps serving.

Routes:
    GET  /                      list of worksheets under the roots
    GET  /w/<path>              a worksheet (<path> relative to its root)
    GET  /api/answers?w=<path>  {"answers": {...}, "url": "/w/<path>"}   (or ?file=<absolute path>)
    POST /api/answers           {"w"|"file": ..., "answers": {id: text}, "times": {id: ms}}
                                per key, the newer edit wins; "" deletes (kept as a timed tombstone)
    GET  /api/ping              {"app": "voice-writer"}

Answers for x-voice.html live in x.answers.json in the same folder (UTF-8, no BOM).
Only *-voice.html files under a root are served, and only their .answers.json are written.
"""
import argparse, html, json, os, threading, time, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

SUFFIX = "-voice.html"
LOCK = threading.Lock()
ROOTS = []


def resolve(w=None, file=None):
    """Map a root-relative path or an absolute path to (root, abs path) of a real worksheet."""
    if file:
        p = os.path.normcase(os.path.realpath(file))
        for r in ROOTS:
            if p.startswith(os.path.normcase(r) + os.sep):
                break
        else:
            return None
        cands = [(r, os.path.realpath(file))]
    elif w:
        cands = [(r, os.path.realpath(os.path.join(r, w))) for r in ROOTS]
    else:
        return None
    for r, p in cands:
        inside = os.path.normcase(p).startswith(os.path.normcase(r) + os.sep)
        if inside and p.lower().endswith(SUFFIX) and os.path.isfile(p):
            return r, p
    return None


def url_for(root, path):
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    return "/w/" + urllib.parse.quote(rel)


def answers_path(path):
    return path[: -len(SUFFIX)] + ".answers.json"


def load_answers(path):
    try:
        with open(answers_path(path), encoding="utf-8") as f:
            d = json.load(f)
        return d.get("answers", {}), d.get("times", {})
    except (OSError, ValueError):
        return {}, {}


def save_answers(path, answers, times):
    out = answers_path(path)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"worksheet": os.path.basename(path), "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "answers": answers, "times": times}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, out)


def worksheets():
    found = []
    for r in ROOTS:
        for d, dirs, files in os.walk(r):
            dirs[:] = [x for x in dirs if not x.startswith(".") and x != "node_modules"]
            for fn in files:
                if fn.lower().endswith(SUFFIX):
                    p = os.path.join(d, fn)
                    found.append((os.path.getmtime(p), r, p))
    return sorted(found, reverse=True)


INDEX = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Voice Writer</title><style>
:root{--bg:#f6f7f9;--panel:#fff;--ink:#1c2024;--muted:#5b636c;--line:#e2e5ea;--accent:#2f6df6}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#14171b;--panel:#1b1f25;--ink:#e7eaee;--muted:#9aa3ad;--line:#2b313a;--accent:#5c8dff}}
:root[data-theme="dark"]{--bg:#14171b;--panel:#1b1f25;--ink:#e7eaee;--muted:#9aa3ad;--line:#2b313a;--accent:#5c8dff}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);font-size:14px;margin:0 0 18px}
a.ws{display:block;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:11px 14px;margin:8px 0;
color:var(--ink);text-decoration:none}a.ws:hover{border-color:var(--accent)}
.name{font-weight:650}.meta{font-size:12.5px;color:var(--muted)}
</style></head><body><main><h1>Voice Writer</h1><p class="sub">Worksheets under %s, newest first.</p>%s</main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = (json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/api/ping":
            return self.send(200, {"app": "voice-writer"})
        if u.path == "/api/answers":
            hit = resolve(q.get("w"), q.get("file"))
            if not hit:
                return self.send(404, {"error": "no such worksheet under " + " / ".join(ROOTS)})
            with LOCK:
                answers, times = load_answers(hit[1])
            return self.send(200, {"answers": answers, "times": times, "url": url_for(*hit)})
        if u.path.startswith("/w/"):
            hit = resolve(w=urllib.parse.unquote(u.path[3:]))
            if not hit:
                return self.send(404, "Not found", "text/plain; charset=utf-8")
            with open(hit[1], "rb") as f:
                return self.send(200, f.read(), "text/html; charset=utf-8")
        if u.path == "/":
            rows = []
            for mt, r, p in worksheets():
                rel = os.path.relpath(p, r)
                rows.append('<a class="ws" href="%s"><div class="name">%s</div><div class="meta">%s &middot; %s</div></a>' % (
                    url_for(r, p), html.escape(os.path.basename(p)[: -len(SUFFIX)]),
                    html.escape(os.path.dirname(rel) or "."), time.strftime("%b %d %H:%M", time.localtime(mt))))
            body = INDEX % (html.escape(" and ".join(ROOTS)), "".join(rows) or "<p>No worksheets yet.</p>")
            return self.send(200, body, "text/html; charset=utf-8")
        self.send(404, "Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/api/answers":
            return self.send(404, {"error": "not found"})
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self.send(400, {"error": "bad json"})
        hit = resolve(data.get("w"), data.get("file"))
        if not hit or not isinstance(data.get("answers"), dict):
            return self.send(404, {"error": "no such worksheet under " + " / ".join(ROOTS)})
        now = int(time.time() * 1000)
        sent = data.get("times") if isinstance(data.get("times"), dict) else {}
        with LOCK:
            cur, times = load_answers(hit[1])
            for k, v in data["answers"].items():
                t = sent.get(k)
                t = t if isinstance(t, (int, float)) else now
                if not isinstance(v, str) or t < times.get(k, 0):
                    continue
                times[k] = t
                if v.strip():
                    cur[k] = v
                else:
                    cur.pop(k, None)
            save_answers(hit[1], cur, times)
        self.send(200, {"ok": True, "url": url_for(*hit)})


def main():
    ap = argparse.ArgumentParser(description="Voice Writer worksheet server")
    ap.add_argument("--port", type=int, default=8795)
    ap.add_argument("--root", action="append", help="folder to serve worksheets from (repeatable)")
    ap.add_argument("--host", action="append", help="address to listen on (repeatable; default 127.0.0.1)")
    a = ap.parse_args()
    ROOTS.extend(os.path.realpath(r) for r in (a.root or [os.path.expanduser("~/Documents")]))
    hosts = a.host or ["127.0.0.1"]
    print(f"Voice Writer roots: {', '.join(ROOTS)}", flush=True)
    # The first host must bind (a clash means another copy is running); the others are retried,
    # since a Tailscale address may not exist yet when this starts at logon.
    first = ThreadingHTTPServer((hosts[0], a.port), Handler)
    print(f"Voice Writer on http://{hosts[0]}:{a.port}/", flush=True)
    for h in hosts[1:]:
        threading.Thread(target=serve_retry, args=(h, a.port), daemon=True).start()
    first.serve_forever()


def serve_retry(host, port):
    said = False
    while True:
        try:
            srv = ThreadingHTTPServer((host, port), Handler)
        except OSError as e:
            if not said:
                print(f"  {host}:{port} not available yet ({e}); retrying every 30 s", flush=True)
                said = True
            time.sleep(30)
            continue
        print(f"Voice Writer on http://{host}:{port}/", flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()

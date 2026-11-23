# -*- coding: utf-8 -*-
"""Build a Voice Writer worksheet from a questions JSON + the template.

Usage:
    python build.py questions.json output.html [template.html]

questions.json schema:
{
  "title":    "Piece / assignment name",        # shown at top; emitted as # H1 unless emit_title=false
  "subtitle": "optional one-line context",       # shown under the title in the worksheet only
  "emit_title": true,                             # optional; include the title as an H1 in the assembled draft
  "slug":     "download-filename",                # optional; used for the downloaded .md name
  "word_target": 300,                             # optional; top bar shows "n / 300 words", green once reached
  "source":   "paper.md",                         # optional; file(s) the quotes come from (path or list,
                                                  #   relative to this JSON). Every quote must appear in one.
  "readings": [{"title": "Mary's post", "file": "mary.txt"}],   # optional; texts shown in full at the top
                                                  #   with numbered paragraphs ("text" instead of "file" works too).
                                                  #   Also count as quote sources. A look whose quote is in a
                                                  #   reading shows that whole paragraph, quote highlighted; or
                                                  #   point at one with {"reading": "Mary's post", "para": 3}.
  "sections": [
    {
      "heading": "Section name",                  # shown as an organizer in the worksheet
      "emit_heading": false,                       # true -> include as "## heading" in the assembled draft
      "blocks": [
        {"id": "s1b1", "para": "p1", "question": "One open, non-leading question = one sentence block",
         "look":  [{"where": "Introduction, 2nd paragraph", "quote": "exact words from the source"},
                   {"where": "Step 3 screenshot", "img": "shots/03.png"}],   # img: path or list, relative
                                                  #   to this JSON; embedded in the page, click to enlarge
         "facts": ["a number/finding the writer can use, with its citation"],
         "check": ["a thing to look for, phrased as a neutral question"],
         "cautions": ["an easy mistake to avoid"],
         "needs": "what the answer should contain (its shape, never its content)",
         "starters": ["Optional opening ...", "Another ..."]},   # or {"first": [...], "second": [...]}
        ...
      ]
    }
  ]
}

Notes:
- "para" groups blocks into one paragraph in the assembled draft. Omit it and every block in a
  section joins into one paragraph by default.
- "look", "facts", "check", "cautions", "needs", "starters" are optional guidance, each shown as its
  own labeled panel under the question. "look" may be one object, a list, or a plain string (just a
  "where"). Quotes are verified against "source". "starters" (only when the writer asks for them) are
  short openings shown as clickable chips; a dict {"first","second"} gives two rows for a
  two-sentence answer.
- "id" is the localStorage key for that block's saved answer. Keep ids STABLE across regenerations
  so the writer's saved answers survive when you add or reword questions.
"""
import json, sys, os, re

def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:50] or "worksheet"

def norm(s):
    # compare text the way a reader sees it: drop markdown escapes/emphasis, unify quotes, collapse space
    s = s.replace("\\", "")
    s = re.sub(r"[*_]", "", s)
    s = s.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}))
    return re.sub(r"\s+", " ", s).strip().lower()

_img_cache = {}
def embed(path, max_w=1100):
    """An image file -> data URI (screenshots shrunk to max_w px wide, WebP), so the worksheet stays one file."""
    if path in _img_cache:
        return _img_cache[path]
    if not os.path.isfile(path):
        raise SystemExit(f"image not found: {path}")
    import base64, io
    try:
        from PIL import Image
        im = Image.open(path)
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        buf = io.BytesIO(); im.convert("RGB").save(buf, "WEBP", quality=88)
        uri = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        ext = os.path.splitext(path)[1].lower().lstrip(".").replace("jpg", "jpeg")
        uri = f"data:image/{ext};base64," + base64.b64encode(open(path, "rb").read()).decode()
    _img_cache[path] = uri
    return uri

def main():
    if len(sys.argv) < 3:
        print("usage: python build.py questions.json output.html [template.html]"); sys.exit(1)
    qpath, out = sys.argv[1], sys.argv[2]
    tmpl = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")
    data = json.load(open(qpath, encoding="utf-8"))

    data.setdefault("slug", slugify(data.get("title", "draft")))
    data.setdefault("storeKey", "vw:" + data["slug"] + ":")

    srcs = data.pop("source", None)
    srcs = [srcs] if isinstance(srcs, str) else (srcs or [])
    base = os.path.dirname(os.path.abspath(qpath))
    src_text = [norm(open(os.path.join(base, f), encoding="utf-8").read()) for f in srcs]
    bad = []

    # readings: texts shown in full at the top, split into numbered paragraphs (blank-line separated)
    readings = data.get("readings") or []
    for r in readings:
        txt = r.pop("text", None) or open(os.path.join(base, r.pop("file")), encoding="utf-8").read()
        r["paras"] = [re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(r"\n\s*\n", txt) if p.strip()]
        src_text.append(norm(txt))
    rtitles = {r.get("title"): i for i, r in enumerate(readings)}

    def context(l):
        # the reading paragraph a look points at: explicit {"reading", "para"}, else the one holding its quote
        if l.get("reading") in rtitles and l.get("para"):
            ri = rtitles[l["reading"]]
            return {"r": ri, "p": int(l["para"]) - 1}
        q = l.get("quote")
        if not q:
            return None
        pat = re.compile(r"\W+".join(re.escape(w) for w in re.findall(r"\w+", q)), re.I)
        # search the reading the "where" names first (the same quote can sit in two readings)
        order = sorted(range(len(readings)), key=lambda i: not (l.get("where") or "").startswith(readings[i].get("title") or "\0"))
        for ri in order:
            r = readings[ri]
            for pi, p in enumerate(r["paras"]):
                m = pat.search(p)
                if m:
                    return {"r": ri, "p": pi, "hl": [m.start(), m.end()]}
        return None

    n = 0
    seen = set()
    for si, sec in enumerate(data.get("sections", [])):
        for bi, b in enumerate(sec.get("blocks", [])):
            if "id" not in b or not b["id"]:
                b["id"] = f"s{si+1}b{bi+1}"
            if b["id"] in seen:
                raise SystemExit(f"duplicate block id: {b['id']} (ids must be unique and stable)")
            seen.add(b["id"])
            if "question" not in b:
                raise SystemExit(f"block {b['id']} has no 'question'")
            looks = b.get("look") or []
            for l in (looks if isinstance(looks, list) else [looks]):
                if isinstance(l, dict) and l.get("img"):
                    imgs = l.pop("img")
                    l["imgs"] = [embed(os.path.join(base, p)) for p in ([imgs] if isinstance(imgs, str) else imgs)]
                if isinstance(l, dict) and readings:
                    ctx = context(l)
                    if ctx:
                        l["ctx"] = ctx
                q = l.get("quote") if isinstance(l, dict) else None
                if not q:
                    continue
                if not src_text:
                    print(f"WARN {b['id']}: quote not verified (no \"source\" set): {q[:60]}")
                elif not any(norm(q) in t for t in src_text):
                    bad.append(f"  {b['id']}: {q}")
            n += 1
    if bad:
        raise SystemExit("quotes not found word for word in the source:\n" + "\n".join(bad))

    js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = open(tmpl, encoding="utf-8").read().replace("__DATA__", js)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out}  ({n} question blocks, storeKey {data['storeKey']})")

if __name__ == "__main__":
    main()

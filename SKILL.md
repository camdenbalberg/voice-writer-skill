---
name: voice-writer
description: "Own-voice writing scaffold. Use when the user has to write something themselves (essay, report, discussion post, reflection, application, cover letter, short answer, any prose) and wants to write it in their own words rather than edit AI-written prose. It builds an outline-first set of directed, open questions (each pointing at the exact passage, with things to check and what the answer needs, but never the answer), broken into sentence-sized blocks, and generates a local HTML worksheet where the user answers each block in their own voice; a button then stitches the answers into a Markdown draft. It never writes the prose for them. Triggers: 'voice writer', 'voice-writer', 'help me write X in my own voice', 'make me a question worksheet for', 'I have to write ... and want to do it myself', 'question scaffold for an essay/report'."
metadata:
  version: "1.1"
---

# Voice Writer

A scaffold for writing in the user's own voice. The rule that makes it work:

**You NEVER write the prose. You only (1) ask open questions and (2) stitch the user's answers together.**
No model-written sentences for them to react to, rewrite, or anchor on. If you catch yourself drafting
a sentence they could paste, stop and turn it into a question instead.

Files in this skill folder:
- `template.html`: the worksheet shell (a question, its guidance panels, then the answer box). Do not edit per use.
- `build.py`: generates a worksheet HTML from a questions JSON + the template.
- `server.py`: a small local server that serves worksheets and saves answers to disk (optional but recommended).

## Workflow

### 1. Get the brief
Before writing any questions, make sure you know (ask if any is unclear):
- **What the piece is and who reads it.** This sets the register. A discussion post is not an
  argument paper. Match the register to the assignment, not to the user's most formal voice.
- **The prompt / rubric**, and what the piece must cover.
- **Source material or rough notes**, if any (paste, file path, or "none yet").
- **Rough length / structure** expected (word count, number of parts, required sections).

If the request already gives enough, don't re-ask; just proceed.

### 2. Load the user's voice constraints
If the user keeps a writing-style guide (a note in CLAUDE.md, a style file, past writing samples they point
you to), read it. These shape how the assembled draft should read and keep your QUESTIONS honest. They are
constraints on *the user's* output, not license for you to write it.

### 3. Build the outline AS QUESTIONS (no prose)
Decide the sections the piece needs and, inside each, the specific points/claims it should make. Then
express each point as **one directed, open question = one sentence block.** Questions should guide: narrow
and pointed at a specific spot, never vague like "How clear is the problem?". But they never tell the user
the answer.

**The line: point, never judge.** You may say *where* to look and *what* to look for. You may never say
what you think is good, bad, missing, or wrong. "Does the Conclusion mention funding?" is pointing.
"The Conclusion forgets funding" is judging. Don't pick checks only where you spotted a flaw; include the
ones any careful reader of this genre would run.

Question rules:
- **Narrow and concrete.** Give a small, doable task tied to a spot in the text: "Read only the
  Executive Summary. In your own words, what problem does the Army have?" not "How clear is the problem?"
- **Open, not yes/no.** The question itself asks for the user's view; yes/no questions belong in `check`.
- **One idea per block.** Sentence-sized, so the answer is a sentence or two.
- **Never presuppose the answer or smuggle in content.** Don't bake a fact, cause, verdict, or fix into
  the question. "What error did you hit, if any?" not "What did the NUL-byte error teach you?"
- **Cover the whole piece.** Intro/framing, each body point, counterpoint if the genre wants one, close.

Every block also gets three guidance fields (all shown under the question in the worksheet):
- **`look`**: the exact spot. A list of `{"where": "Section, which paragraph/sentence", "quote": "..."}`.
  `quote` is optional and must be copied **word for word** from the source (short: a phrase or one
  sentence). Set top-level `source` to the file(s) the quotes come from and `build.py` refuses to build if
  any quote isn't found there. A quote is the source author's text, never yours. Skip `look` only for
  wrap-up blocks (strength, priority revision) that draw on earlier answers.
- **`check`**: 2-4 things to look for, as neutral questions or topics. Take them from the assignment's
  rubric/instructions when you can and label them ("Rubric: ...", "Assignment: ...").
- **`needs`**: the *shape* of a good answer, never its content: "Name one term + what kind of
  explanation would help." not "Say that 'counterbattery' needs defining."

Optional fields, each rendered as its own colored panel so a block doesn't read as one long list:
- **`facts`**: numbers, findings, and citations the user can use, with the source at the end of each
  ("71% of solo practitioners ... (Reach, 2026)"). Facts go here, not in `check`.
- **`cautions`**: easy mistakes to avoid ("Avoid 'exponential': two data points can't show it").
- **`starters`**: only when the user asks for them. Short openings (3-10 words, ending "..."), 2-3 per
  block, shown as chips they can click into the box. For a "one or two sentences" block use
  `{"first": [...], "second": [...]}`. Openings only: never a claim, number, or verdict.

Group blocks into paragraphs with `para` (blocks sharing a `para` join into one paragraph on assembly).
Set `emit_heading: true` only on sections that should appear as a heading in the final piece (true for a
report with named sections; usually false for an essay, where headings are organizers only).

### 4. Generate the worksheet
Write the questions to `<slug>.questions.json` in the working directory (the folder the user is writing in,
unless they name another location), then run `build.py` from this skill folder:

```
python <this skill folder>/build.py <slug>.questions.json <slug>-voice.html
```

(Use `python3` on macOS/Linux. The skill folder is usually `~/.claude/skills/voice-writer/`.)
Keep the `.questions.json` next to the HTML so you can add/reword questions and rebuild later. **Keep block
`id`s stable** across rebuilds: saved answers are keyed by id, so stable ids mean the user's work survives
when you revise questions.

### 5. Hand it over and iterate
Give the user the **localhost link**, not the file path: Grammarly and other browser extensions don't run
on `file://` pages. The server is `server.py` in this folder: port 8795, 127.0.0.1 only, and it serves every
`*-voice.html` under its root folders (default `~/Documents`, subfolders included).
1. Check it's up: `curl -s http://127.0.0.1:8795/api/ping`. If not, ask the user to start it in its own
   terminal window so it keeps running: `python server.py` from this skill folder (add
   `--root "<folder>"` if the worksheet is outside `~/Documents`).
2. Link: `http://127.0.0.1:8795/w/<path relative to the root, URL-encoded>`, e.g.
   `http://127.0.0.1:8795/w/English%20101/essay-1-voice.html`. `http://127.0.0.1:8795/` lists them all.

If the server can't run, the HTML file still works opened directly; answers then save in the browser only.

Tell the user: answer each box in their own words, watch the progress bar, hit **Assemble draft** for a
Markdown draft (Copy or Download). Blank questions are left out of the draft. Then offer the follow-ups that
fit: typeset the assembled draft, convert to PDF, or add/revise questions and rebuild.

## questions.json schema
```json
{
  "title": "Assignment / piece name",
  "subtitle": "optional one-line context shown in the worksheet",
  "emit_title": true,
  "slug": "optional-download-name",
  "word_target": 300,
  "source": "paper.md",
  "sections": [
    { "heading": "Introduction", "emit_heading": false, "blocks": [
        { "id": "intro1", "para": "p1", "question": "...",
          "look": [{ "where": "Introduction, last sentence", "quote": "exact words from paper.md" }],
          "check": ["a neutral thing to look for", "Rubric: a criterion from the assignment"],
          "needs": "what the answer should contain (its shape, not its content)",
          "facts": ["optional: a number + its citation"], "cautions": ["optional"],
          "starters": ["optional: Opening ..."] },
        { "id": "intro2", "para": "p1", "question": "..." }
    ]},
    { "heading": "First point", "emit_heading": false, "blocks": [
        { "id": "p1a", "para": "a", "question": "..." }
    ]}
  ]
}
```

A `look` item can also carry `"img": "path.png"` (or a list), relative to the JSON: `build.py` embeds it
in the page (shrunk to 1100 px, WebP; needs Pillow) under that "Look at" line, click to enlarge. Use it
whenever a block points at a screenshot, figure or photo.

`word_target` (optional) is the assignment's word count; the top bar always shows the running total and,
with a target, "n / target words" (green once reached). Set it whenever the brief gives a length.
`source` is a path (or list) relative to the JSON. `look` may also be a single object or a plain
string (a "where" with no quote).

## Notes
- Gather the source first (the paper being reviewed, the user's notes, the rubric) so `look` and `check`
  can be specific. Without a source, questions fall back to being broad.
- One worksheet per piece; each gets its own `storeKey` (from the slug) so answers don't collide in the browser.
- Answers save to `<name>.answers.json` next to the worksheet (UTF-8, per-answer edit times; the newer edit
  wins) while the server runs, and to browser `localStorage` either way. **You can read the answers there**,
  e.g. to check progress or assemble for the user. A worksheet opened as a local file still syncs to the
  server and shows a banner linking to its localhost copy.

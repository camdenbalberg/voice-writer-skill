# Voice Writer

A Claude skill for writing things **in your own words**. Instead of writing your essay, report, or
post for you, Claude turns it into a worksheet of short, pointed questions (one per sentence or two),
each telling you where to look and what your answer needs, but never what to say. You answer them in
a local web page, then one button stitches your answers into a Markdown draft.

## Install

You need [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) and Python 3.
[Pillow](https://pypi.org/project/pillow/) (`pip install pillow`) is only needed if a worksheet embeds images.

Clone this repo into your Claude skills folder, named `voice-writer`:

```
git clone https://github.com/camdenbalberg/voice-writer-skill ~/.claude/skills/voice-writer
```

(On Windows `~` is `C:\Users\<you>`.) Start a new Claude Code session and the skill is picked up.
To update later: `git -C ~/.claude/skills/voice-writer pull`.

**claude.ai instead of Claude Code:** download the repo as a ZIP, then upload it as a custom skill in
Settings > Capabilities (needs a paid plan with code execution on). Claude builds the worksheet and you
download the HTML; without the local server your answers save in your browser only.

## Use

Ask Claude something like:

- "Voice writer: help me write my discussion post on chapter 4 in my own voice."
- "Make me a question worksheet for this peer review. Here's the rubric and the paper."

Give it the prompt, rubric, and any source text; the more specific the source, the more specific the
questions.

## The local server (recommended)

Browser extensions like Grammarly don't run on files opened straight from disk, and answers in a
`file://` page only live in that browser. The included server fixes both. Start it in its own terminal
and leave it running:

```
cd ~/.claude/skills/voice-writer
python server.py
```

Then open http://127.0.0.1:8795/ to see your worksheets. Options:

| Option | What it does |
|---|---|
| `--root DIR` | Folder to look for worksheets in, subfolders included (repeatable). Default: `~/Documents`. |
| `--port N` | Port. Default: 8795. |
| `--host ADDR` | Address to listen on (repeatable). Default: `127.0.0.1` (this computer only). Add e.g. a Tailscale IP to open worksheets from your phone. |

Answers are saved next to each worksheet as `<name>.answers.json`.

## Files

- `SKILL.md`: the instructions Claude follows.
- `build.py`: builds a worksheet HTML from a `<name>.questions.json` file (schema in `SKILL.md`).
- `template.html`: the worksheet page.
- `server.py`: the local server.

## License

MIT, see [LICENSE](LICENSE).

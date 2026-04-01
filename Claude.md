# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Requirements

@Requirements.md


## Architecture

Three modules, cleanly separated:

- **`parser.py`** — reads raw Locoscript 2 binary bytes and produces a `Document` (list of `Paragraph`s, each containing `TextRun`s with an italic flag). No knowledge of output formats.
- **`converter.py`** — takes a `Document` and writes TXT, RTF, or DOCX. No knowledge of the binary format.
- **`app.py`** — tkinter desktop UI. Drives parser and converter, handles file selection, overwrite prompts, progress, and error logging. Conversion runs on a background thread to keep the UI responsive.


## Commands

**Run the app:**
```
source venv/bin/activate
python app.py
```

**Run the test suite:**
```
source venv/bin/activate
python -m unittest tests/test_parser.py -v
```

**Regenerate the golden fixture** (after an intentional parser improvement):
```
python tests/regenerate_golden.py
```

**Generate a hex dump of a file for binary analysis:**
```
xxd <filename> > hex_dump
```


## Task Workflow

When implementing a task, either from `Tasks.md` or involving any files tracked in the repo:

0. Read Tasks.md and look for open tasks.
1. Pick task and confirm understanding and agree is the next thing to do
2. Create a feature branch (e.g. `git checkout -b feature/my-task`)
3. Develop fix
4. Run tests and confirm all pass
5. Update documentation (Requirements.md, Tasks.md, etc.)
6. Raise PR and tell me it's ready for review
7. Commit / merge
8. Tidy up any stale branches

Do **not** commit task work directly to `main`.


## Debugging New Binary Patterns

When a new sample file produces garbled output, the workflow that works:

1. Generate a hex dump: `xxd <filename> > hex_dump`
2. Run the parser and note which words or character sequences are wrong in the output
3. Search the hex dump for the ASCII bytes of a word that *should* appear just before the artifact — this locates the approximate region
4. Look at the bytes immediately before the garbled text for unrecognised control sequences
5. Cross-reference against the **Locoscript 2 Binary Format Reference** in `Requirements.md` to identify which pattern is involved
6. Add a targeted fix to `_skip_ctrl_sequence()` in `parser.py` for structural skips, or to the main loop in `parse()` for new control codes
7. Write a pattern unit test in `tests/test_parser.py` that reproduces the artifact with a minimal synthetic byte sequence
8. Verify all 23 existing tests still pass before committing

The most common source of new artifacts is an unrecognised variant of the `22 61 0b` paragraph content block — check the bytes at offsets +3 through +8 relative to the `22 61 0b` marker first.

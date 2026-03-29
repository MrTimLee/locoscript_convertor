# Tasks

## Colleague's Findings — Investigate & Potentially Implement

These items come from additional Locoscript 2 research and are not currently handled by the parser. Each needs investigation against real sample files before implementing.

- [x] **`0x05` (ENQ) — extended character encoding** — Implemented in branch `feature/enq-extended-characters`. Added `_ENQ_CHAR_MAP` and 5-byte handler (`05 base 01 diacritic 01`). Maps `(0x63, 0x13)` → ç (confirmed in "façade", "Français"). Trailing doubled-pair indent consumed to prevent 'FF'/'DD' artifacts. Requirements.md updated. 38/38 tests passing.

- [ ] **"JOY" magic word** — Colleague notes `JOY` as a valid alternative file header magic (vs. `DOC`). Currently any non-`DOC` file throws a `ParseError`. Investigate what `JOY` files represent and handle appropriately (either support or reject with a clearer error).

- [ ] **Detailed file header map** — Colleague provides a byte-level header map: version bytes at `0x03`–`0x04`, 90-char document summary at `0x05`–`0x5E`, font table at `0x138` (10 × 28 bytes), layout table at `0x2C6` (10 × 73 bytes). Currently the entire header is skipped. Investigate whether extracting version, summary, or layout data (e.g. margins, tab stops) would improve conversion quality or fix the first-paragraph junk issue.

## Known Limitations (future work)

- [ ] **Tab handling in converter output** — The parser correctly emits `\t` for `0f 04` tab sequences, but all three converters call `.strip()` on run/paragraph text, which drops leading/trailing tabs. RTF output also passes `\t` as a raw character rather than the `\tab` control word. DOCX strips tabs from run text entirely. Improve converter fidelity for tab characters in TXT, RTF, and DOCX output.

- [ ] **Untested document types** — Parser was developed against a single sample file. Locoscript 2 letters, labels, and other document types may surface unrecognised control sequences.

- [ ] **Remove "no file extension" restriction** — Remove the requirement from Requirements.md that input files must have no file extension, and update any related UI or code that enforces or assumes this.

- [ ] **Shadow Copy mode** — New application mode to mirror-convert an entire folder structure. See Requirements.md for full spec. Do this last.

## Completed

- [x] **Set up repo on GitHub** — Remote repository created at github.com/MrTimLee/locoscript_convertor. GitHub CLI (`gh`) authenticated for raising PRs.
- [x] **`08 05 01 XX XX` doubled-pair artefacts** — Fixed in branch `fix/paragraph-indent-artefacts`. Added `PARA_INDENT` handler consuming all 5 bytes. Golden fixture regenerated. 23/23 tests passing.
- [x] **Batch overwrite: "Skip ALL" / "Overwrite ALL"** — Implemented in branch `feature/batch-overwrite-all`. Custom 4-button dialog (Yes / No / Yes to All / Skip All); batch buttons only shown for multi-file conversions. Policy state reset on each new run. 23/23 tests passing.
- [x] **Show time taken in completion message** — Implemented in branch `feature/completion-time`. Elapsed time recorded with `time.monotonic()` and shown in both the summary dialog and status bar. 23/23 tests passing.
- [x] **First paragraph junk** — Implemented in branch `fix/first-paragraph-header-junk`. `_find_content_start` now iterates through `22 61 0b c4 0e` structural header blocks, skipping across section breaks to land on the first real content paragraph. Improved 185/443 sample files, 0 regressions. 23/23 tests passing.
- [x] **`0xE9` = `£` symbol** — Implemented in branch `feature/e9-pound-sign`. Added extended character mapping in the main parse loop. Golden fixture regenerated. 24/24 tests passing.
- [x] **Bold, underline, superscript, subscript** — Implemented in branch `feature/bold-underline-formatting`. Extended `TextRun` with bold/underline/superscript/subscript flags. Added `08 XX`/`09 XX` inline formatting handler in parser. RTF output uses `\b`/`\b0`, `\ul`/`\ulnone`, `\super`/`\nosupersub`. DOCX output sets `run.bold`, `run.underline`, `run.font.superscript`. Confirmed bold in real sample files (BOOTSHEX.HAM). 33/33 tests passing.
- [x] **`0x0F` (SI) sequences — line/paragraph structure** — Implemented in branch `feature/si-sequences`. `0f 04` (tab) and `0f 05` (hanging indent) had printable param bytes leaking as artefacts. Added handlers consuming params and emitting `\t` for `0f 04`. 27/27 tests passing.

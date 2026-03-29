# Tasks

## Outstanding

- [ ] **Set up repo on GitHub** — Create a remote repository on GitHub and push the local repo.

- [x] **Batch overwrite: "Skip ALL" / "Overwrite ALL"** — The overwrite prompt currently asks yes/no for each file individually. Batch mode should also offer "Skip ALL" and "Yes to ALL" options. The README already describes this feature as implemented — update it once the feature is done.

- [x] **Show time taken in completion message** — The success/summary dialog shows file counts but not elapsed time. The requirements specify the time taken should be included.

## Bug Fixes

- [x] **`08 05 01 XX XX` doubled-pair artefacts** — Paragraph indent marker is not handled as a unit. The parser currently skips `08`, `05`, `01` individually, then outputs `XX XX` as literal text when `XX` is a printable character (e.g. `%%`, `::`, `QQ`). Affects 434 of 443 sample files. Fix: add a handler that consumes all 5 bytes and emits nothing, mirroring the existing `TAB_SEQ` (`09 05 01`) handler.

## Colleague's Findings — Investigate & Potentially Implement

These items come from additional Locoscript 2 research and are not currently handled by the parser. Each needs investigation against real sample files before implementing.

- [ ] **`0x05` (ENQ) — extended character encoding** — Colleague documents multi-byte sequences encoding non-ASCII characters (e.g. `05 63 01 13 01` = ç). Requirements.md incorrectly states there is no multi-byte extended character encoding. Currently the parser would misparse these sequences — the `13` byte inside an ENQ sequence could incorrectly trigger paragraph/italic handlers. Investigate and implement correct handling.

- [ ] **`0xE9` = `£` symbol** — Byte `0xE9` maps to the pound sign. Currently falls outside the `0x20–0x7E` printable range and is silently dropped rather than substituted with `?` or mapped to `£`. Investigate and implement correct mapping.

- [ ] **`0x0F` (SI) sequences — line/paragraph structure** — Colleague documents `SI` as carrying line and paragraph signals based on its second byte (`SI 01` = soft new line, `SI 02` = new paragraph, `SI 04` = horizontal tab, `SI 05` = hanging indent). Currently silently skipped by the parser. Investigate whether these appear in our sample files and implement if confirmed.

- [ ] **"JOY" magic word** — Colleague notes `JOY` as a valid alternative file header magic (vs. `DOC`). Currently any non-`DOC` file throws a `ParseError`. Investigate what `JOY` files represent and handle appropriately (either support or reject with a clearer error).

- [ ] **Bold, underline, superscript, subscript** — Colleague documents `08 00`/`09 00` = bold on/off, `08 02`/`09 02` = underline on/off, `08 06`/`09 06` = superscript, `08 07`/`09 07` = subscript. None of these are modelled in the parser or converter. Investigate presence in sample files; if confirmed, implement in parser and add formatting support to RTF and DOCX output.

- [ ] **Detailed file header map** — Colleague provides a byte-level header map: version bytes at `0x03`–`0x04`, 90-char document summary at `0x05`–`0x5E`, font table at `0x138` (10 × 28 bytes), layout table at `0x2C6` (10 × 73 bytes). Currently the entire header is skipped. Investigate whether extracting version, summary, or layout data (e.g. margins, tab stops) would improve conversion quality or fix the first-paragraph junk issue.

## Known Limitations (future work)

- [ ] **First paragraph junk** — The parser skips to the first `22 61 0b` marker but some binary artefacts from the document header still leak into para[0]. A future fix would identify and skip the full header block.

- [ ] **Untested document types** — Parser was developed against a single sample file. Locoscript 2 letters, labels, and other document types may surface unrecognised control sequences.

- [ ] **Remove "no file extension" restriction** — Remove the requirement from Requirements.md that input files must have no file extension, and update any related UI or code that enforces or assumes this.

- [ ] **Shadow Copy mode** — New application mode to mirror-convert an entire folder structure. See Requirements.md for full spec. Do this last.

## Completed

- [x] **`08 05 01 XX XX` doubled-pair artefacts** — Fixed in branch `fix/paragraph-indent-artefacts`. Added `PARA_INDENT` handler consuming all 5 bytes. Golden fixture regenerated. 23/23 tests passing.
- [x] **Batch overwrite: "Skip ALL" / "Overwrite ALL"** — Implemented in branch `feature/batch-overwrite-all`. Custom 4-button dialog (Yes / No / Yes to All / Skip All); batch buttons only shown for multi-file conversions. Policy state reset on each new run. 23/23 tests passing.
- [x] **Show time taken in completion message** — Implemented in branch `feature/completion-time`. Elapsed time recorded with `time.monotonic()` and shown in both the summary dialog and status bar. 23/23 tests passing.

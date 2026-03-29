# Tasks

## Outstanding

- [ ] **Batch overwrite: "Skip ALL" / "Overwrite ALL"** — The overwrite prompt currently asks yes/no for each file individually. Batch mode should also offer "Skip ALL" and "Yes to ALL" options. The README already describes this feature as implemented — update it once the feature is done.

- [ ] **Show time taken in completion message** — The success/summary dialog shows file counts but not elapsed time. The requirements specify the time taken should be included.

## Known Limitations (future work)

- [ ] **First paragraph junk** — The parser skips to the first `22 61 0b` marker but some binary artefacts from the document header still leak into para[0]. A future fix would identify and skip the full header block.

- [ ] **Untested document types** — Parser was developed against a single sample file. Locoscript 2 letters, labels, and other document types may surface unrecognised control sequences.

## Completed


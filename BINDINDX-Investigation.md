# BINDINDX.HEX Investigation

## Summary

`BINDINDX.HEX` is a Locoscript 2 DOC file that uses a previously unseen binary variant:
the control-sequence **prefix byte is `0x1e`** (ASCII RS — Record Separator) rather than the
usual `0x22`. The parser currently assumes `0x22` throughout and produces only 1 garbage
paragraph from a ~70 KB index document that should have ~1,500 paragraphs.

---

## File identity

| Field | Value |
|---|---|
| Size | 70,864 bytes |
| Magic | `DOC` (`44 4f 43`) |
| Prefix byte | `0x1e` (not `0x22`) |
| ctrl_byte | `0x74` (`t`) |
| Paragraph marker | `1e 74 0b` |
| Paragraph count | ~1,539 `1e 74 0b` blocks |

---

## Issue 1 — `_detect_ctrl_byte` returns wrong result

`_detect_ctrl_byte` scans only for `22 XX 0b`. This file's header zone contains a handful
of `22 6d XX` sequences (font/layout metadata inherited from other files) but no `22 XX 0b`
body blocks. The function returns `0x6d` (wrong), causing `para_ctrl = bytes([0x22, 0x6d, 0x0b])`,
which matches nothing in the body.

There are **1,539** occurrences of `1e 74 0b` vs **2** of `22 6d 0b`.

---

## Issue 2 — Prefix byte `0x1e` is hardcoded everywhere as `0x22`

Every use of `ctrl_prefix`, `para_ctrl`, and the `0x22` literal in the parser assumes the
prefix is `0x22`. The functions affected are:

- `_detect_ctrl_byte` (line 114)
- `_find_content_start` (lines 166–167)
- `_find_body_start` (lines 214, 248, 264, 285, 318, 332, 347)
- `parse()` (lines 402–403, 423, 480, 496, 567, 577, 643, 669, 681)

---

## Issue 3 — Paragraph separator pattern

Body paragraphs are delimited by `0f 02 1e 74 0b` (new paragraph) and `0f 01 1e 74 0b`
(line break within paragraph). There are also `0f 00 1e 74 0b` occurrences (59) which appear
to be structural/layout markers preceding section header blocks.

| Pattern | Count | Meaning |
|---|---|---|
| `0f 02 1e 74 0b` | 1,440 | New paragraph |
| `0f 01 1e 74 0b` | 40 | Line break / sub-paragraph |
| `0f 00 1e 74 0b` | 59 | Structural / layout break |

The existing `0f 01`/`0f 02` Contents Page separator handler (Requirements.md §"Contents Page
Separators") uses `ctrl_byte != 0x61` as a guard and checks for `22 ctrl 0b` after the `0f`
byte. It fires for `22 6d`/`22 42` files but **not** for `1e 74` files because the prefix
byte doesn't match.

---

## Issue 4 — Doubled-pair indent values are all < 0x20

The parser requires `XX >= 0x20` to recognise a doubled-pair indent marker (`01 XX XX`).
In this file **all** doubled-pair indent values fall below `0x20`:

| Value (hex) | Decimal | Inches at 10cpi | Occurrences |
|---|---|---|---|
| `00` | 0 | 0.0" (left margin) | 91 |
| `04` | 4 | 0.4" | 73 |
| `08` | 8 | 0.8" | 65 |
| `0b` | 11 | 1.1" | 50 |
| `0c` | 12 | 1.2" | 50 |
| `07` | 7 | 0.7" | 46 |

These are legitimate indent positions (the index has many indentation levels). The `>= 0x20`
threshold is too restrictive; it was set to avoid treating control bytes as indent values.
For `1e 74` files the same guard does not apply — all `01 XX XX` doubles after a `1e 74 0b`
block are structural indent metadata.

---

## Issue 5 — Structural header blocks are present (expected)

83 `1e 74 0b` blocks have `B3 >= 0x80` and `B4 == 0x0e` — the same structural section-header
pattern as other variants. The existing skip-to-next-para logic should handle these correctly
once the prefix byte is threaded through.

---

## Issue 6 — Non-`0b` control type `1e 74 45`

43 occurrences of `1e 74 45` are present (the sequence `11 06 1e 74 45 01 08 08` appears before
centred text like "Contents"). `0x45` = 'E' is a non-`0b` control type and should follow the
variable-length skip rule for unknown types (skip 4 bytes + non-printable params + doubled-pair
suffix). Worth verifying after the prefix byte fix is in.

---

## Self-referential sequences

62 occurrences of `1e 1e 74` — the self-referential pattern (`22 XX XX` equivalent).
These should be skipped directly to the next `1e 74 0b` block (same logic as `22 6d 6d`).

---

## Proposed implementation plan

### Step 1 — Generalise variant detection

Rename/extend `_detect_ctrl_byte` to `_detect_variant(data) -> (prefix_byte, ctrl_byte)`:

- Scan for `XX YY 0b` patterns for any candidate prefix byte
- Count separately for prefix=`0x22` and prefix=`0x1e`
- Return the `(prefix_byte, ctrl_byte)` with the highest combined count
- Default: `(0x22, 0x61)`

### Step 2 — Thread `prefix_byte` through the parser

Add `prefix_byte` as a variable in `parse()` (and pass it to `_find_content_start`,
`_find_body_start`, `_skip_ctrl_sequence`). Replace every hardcoded `0x22` reference with
`prefix_byte`.

### Step 3 — Extend `0f 01`/`0f 02` paragraph separator handler

The Contents Page separator handler currently checks `data[i+2] == 0x22 and data[i+3] == ctrl_byte`.
Change to `data[i+2] == prefix_byte and data[i+3] == ctrl_byte`.

### Step 4 — Relax doubled-pair threshold for `1e` prefix files

Change `XX >= 0x20` to `XX >= 0x00` specifically when `prefix_byte == 0x1e`, OR
lower the threshold globally to `>= 0x01` and verify all existing tests still pass.

The safest approach is a file-specific threshold stored alongside `prefix_byte` and
`ctrl_byte` so the change cannot regress existing `0x22` files.

### Step 5 — Verify `1e 74 45` non-`0b` control type

After the above, check that the variable-length skip for `0x45` and other non-`0b` types
produces clean output around the centred "Contents" heading.

### Step 6 — Tests

Add unit tests for:
- `_detect_variant` returning `(0x1e, 0x74)` for a synthetic `1e 74 0b` file
- `0f 02 1e 74 0b` emitting a paragraph break
- `0f 01 1e 74 0b` emitting a line break
- Doubled-pair value of `0x04` (`01 04 04`) being consumed correctly
- Self-referential `1e 1e 74` being skipped

---

## Check A — `0f 00 1e 74 0b` (59 occurrences)

Every occurrence is immediately preceded by the fixed sequence
`1e 1e 74 01 00 00 00 23`, making the full pattern:

```
1e 1e 74 01 00 00 00 23   ← self-referential sequence + 5 metadata bytes
0f 00 1e 74 0b [B3 B4 …]  ← section/page boundary block
```

The `1e 1e 74` is the self-referential sequence (analogous to `22 6d 6d`), which the
parser should skip directly to the next `1e 74 0b`. The `01 00 00 00 23` trailing bytes
and the `0f 00 1e 74 0b` that follows are the section boundary mechanism. `0f 00` is
distinct from `0f 01` (line break) and `0f 02` (paragraph break) — it marks a page/section
transition and should **not** emit a paragraph break. After the block, the parser continues
normally.

**Implementation note:** The self-referential sequence handler's "skip to next `1e XX 0b`"
logic already jumps past the `1e 1e 74 01 00 00 00 23 0f 00` prefix, landing on `1e 74 0b`.
A `0f 00 1e XX 0b` guard (alongside `0f 01` and `0f 02`) should consume the block silently
without flushing a paragraph.

---

## Check B — `1e 74 01` (59 occurrences)

Not a separate control type. Every occurrence is the tail end of `1e 1e 74 01 00 00 00 23`
(the self-referential sequence + metadata). The `1e 74 01` bytes are never a standalone
sequence — no separate handler needed.

---

## Check C — Body start and `_find_content_start` compatibility

The first `1e 74 0b` block appears at **0x06b1** (content block, B3=0xcc, B4=0x10).
Structural header blocks (B3>=0x80, B4=0x0e) first appear at **0x0c1b** — well after
the content has already begun. In this file variant, structural header blocks are
**section/page separators within the body**, not pre-body zone markers.

`_find_content_start` searches for the `c4 0e` specific pattern to skip header/footer
sections. Since `1e 74` files use different B3 values (e.g. `b0 0e`, `80 0e`, `9e 0e`)
and never `c4 0e`, the `c40e_block` search returns -1 and the function correctly falls
through to return the very first `1e 74 0b` at 0x06b1. No changes needed to
`_find_content_start` logic beyond threading `prefix_byte`.

`_find_body_start` and `_section_type_at` also read correctly — the body begins
immediately at the first content block.

---

## Check D — Layout table at 0x2C6

The layout table is present at the standard offset **0x2C6** (same as all other variants).
Key values:

| Field | Value | Notes |
|---|---|---|
| Scale pitch (`+11`) | `0x14` (20) | 12cpi — different from 10cpi (`0x18`) standard files |
| twips_per_unit | 120 | = 0x14 × 6 (vs 144 for 10cpi files) |
| Point size × 10 (`+13`, entry 2) | `0x78` (120) | 12pt — matches the B6=`0x78` font encoding seen in paragraph blocks |
| Tab stops (`+33..+47`) | `0x18` (24) all | Default spacing: 24 × 120 twips = 2880 twips = 2.0" |

The parser already reads scale pitch from `data[_LAYOUT_TABLE_START + 11]`, so
`twips_per_unit = 120` will be computed correctly without code changes. Tab stop
positions will reflect the 12cpi grid.

Note: `B5=0x14` in paragraph block headers likely encodes this same scale pitch value
(12cpi = `0x14`), consistent with the layout table.

---

## Issue 7 — Font size encoding in paragraph block header (B5/B6 bytes)

Some paragraph block headers carry an explicit font size in B6 when B5=`0x14`. Confirmed
from comparing normal and small-font entries across the document:

| B5   | B6     | Decimal | pt size (÷10) | Appearance |
|------|--------|---------|---------------|------------|
| `14` | `0x78` | 120     | 12pt          | Small/italic sub-entries |
| `14` | `0x90` | 144     | 14.4pt        | Normal/larger main entries |

Entries confirmed with B6=`0x78`: "Abbey Court", "Addison", "Alexander, Joseph & Co." — all
small-font sub-entries, all also carry `13 04 64` (italic-on) after the block.

Entries confirmed with B6=`0x90`: "Abbey Flags footpath", "Alemouth Road", "Alexander Place"
— all normal-size main entries, no italic marker.

The pattern for small-font **group-opener** entries is:
```
1e 74 0b B3 B4 14 78 00   (8-byte block with B5=14, B6=0x78)
13 04 64 00 01 XX XX       (italic-on + trailing doubled-pair indent)
[text content]
```

Subsequent sub-entries in the same group **inherit** italic state without re-encoding the font
size — they rely on carry-through until `13 04 78` (italic-off) appears at the end of the
last entry in the group. Entries that only have carry-through use a plain block structure
(B5=`01`, doubled-pair at B6/B7, or the SI tab variant).

**Implementation note:** The B5=`14`, B6 font-size encoding in the `1e 74 0b` block header is
a new field not present in `22 61` or `22 6d` files. For now, no output mapping is proposed
(italic already conveys the visual distinction); the font-size bytes should simply be consumed
as part of the block skip. If future work targets font size fidelity in DOCX/RTF output, B6
provides the raw value.

---

## Expected output (from JPEG CND-Town-001)

The document is an alphabetical index "HEXHAM ABATTOIR". Structure:
- Centred heading: `HEXHAM ABATTOIR`
- Centred subheading: `Contents`
- Top-level entries (no indent, bold): e.g. `Abattoir`, `Abbey Flags footpath`
- Indented sub-entries (approx 0.4" indent): e.g. `  Abbey Court - see Loosing Hill`
- Further indented entries at deeper levels
- Separator ` - ` between subject and cross-reference (the `02 06 02` issue)

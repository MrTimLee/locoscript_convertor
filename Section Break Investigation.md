# Section Break Spurious Paragraph Split — Investigation

## Problem

`0e 01` / `0e 02` (section/page break) currently always calls `flush_para()` in the main parse loop (`parser.py:439`), creating a new paragraph. In some documents this is correct (a real section boundary), but in others the break is a mid-sentence layout switch and the flush incorrectly splits flowing prose.

Two confirmed cases in `BUILDNGS.H`:

| Para | Before break | After break |
|------|-------------|-------------|
| 17/18 | `…Hexham's first care home for the elderly,` | `opened by the chairman of Northumberland County Council…` |
| 93/94 | `…[...] work to` | `remove around 30 damaged and dangerous trees…` |

## Hex Evidence

### Case 1 — "elderly" / "opened" (offset `0x1af0`)

```
00001af0: 02 65 6c 64 65 72 6c 79 2c 02  0e 01  00 00 70 08
                 e  l  d  e  r  l  y  ,  ws     ^^^^^^^^^^^^
                                                section break
00001b00: f0 00 01 0f 1b ...  [binary layout block] ...
00001b30: ... 22 61 61 ...  [self-referential ctrl — skipped] ...
00001b50: 0f 00  22 61 0b  08 00  14 78 00 01 53 53
                 ^^^^^^^^  ← next para block; 53 53 = 'SS' doubled pair
00001b60: 6f 70 65 6e 65 64 ...
           o  p  e  n  e  d  ...
```

`0e 01` is immediately preceded by `02` (word separator) — the sentence is still in progress.

### Case 2 — "work to" / "remove" (offset `0x7c20`)

```
00007c20: ... 77 6f 72 6b 02 74 6f 02  0e 01  00 00 00 00 ...
               w  o  r  k  ws t  o  ws ^^^^^^^^^^^^
                                       section break
00007c40: ... [binary layout block] ...
00007c90: 0f 00  22 61 0b  0e 01  14 78 00 01 51 51
                 ^^^^^^^^  ← next para block; 51 51 = 'QQ' doubled pair
00007ca0: 72 65 6d 6f 76 65 ...
           r  e  m  o  v  e  ...
```

Again, `0e 01` immediately follows `02` (word separator).

### Contrast — real paragraph break (offset `0x1280`)

```
00001280: 2c 02 31 39 39 38 2e  13 04 78  00  0e 02 ...
                         1998.  ^^^^^^^^      ^^^^^^^^
                                line break    section break
```

Here a `13 04 78` (line break / italic off) appears **before** the `0e 02`. The paragraph has already ended; the section break simply marks the layout change between sections.

### One more spurious case (offset `0xa900`)

```
0000a900: 6f 6e 02 74 68 65 02  0e 01  00 00 00 ...
           o  n  ws t  h  e  ws ^^^^^^^^^^^^
```

"on the" → `0e 01` → layout block → "Haugh Lane Industrial Estate started." — another mid-sentence split.

## Pattern

The distinguishing signal is **what immediately precedes the `0e` byte**:

| Precedes `0e` | Meaning | Correct behaviour |
|--------------|---------|-------------------|
| `02` (word separator) or printable text byte | Break is mid-sentence — layout switch only | Skip layout block, **do not flush paragraph** |
| `13 04 78` / `13 04 50` (line/para break) | Break follows a genuine paragraph boundary | Skip layout block, paragraph already flushed (or flush now) |

This is robust: a word separator or printable byte means the sentence is still in progress; a `13 04` sequence means the paragraph was already closed.

## Proposed Fix

In the `SECTION_BREAK` handler in `parse()` (`parser.py:437–442`), check whether the byte immediately before the `0e` is a word separator (`0x02`) or a printable character. If so, only skip the layout block — do **not** call `flush_para()`. The accumulated runs continue into the next paragraph's content area.

```python
if data[i] == SECTION_BREAK and i+1 < n and data[i+1] in SECTION_BREAK_TYPES:
    flush_run()
    prev = data[i - 1] if i > 0 else 0x00
    mid_sentence = (prev == 0x02 or 0x20 <= prev <= 0x7e)
    if not mid_sentence:
        flush_para()
    next_para = data.find(para_ctrl, i + 2)
    i = next_para if next_para >= 0 else n
    continue
```

`flush_run()` is still called unconditionally (so any in-progress run is committed), but the paragraph boundary is only created when the break is not mid-sentence.

## Risks / Edge Cases

- **Empty paragraph before `0e`**: if `current_runs` is empty when we hit `0e`, `flush_para()` is a no-op anyway — no change in behaviour.
- **`0e` at the very start of content** (`i == 0`): `prev` defaults to `0x00`, which is neither a word separator nor printable — treated as a real break. Safe.
- **Multiple consecutive section breaks**: unlikely in practice; each would be handled independently.
- **`0e` bytes in the binary layout block itself**: the parser always jumps to `data.find(para_ctrl, i + 2)` which skips the entire block — internal `0e` bytes are never re-evaluated.

## Files Affected

- `parser.py` — `SECTION_BREAK` handler (~line 437)
- `tests/test_parser.py` — two new pattern tests needed:
  1. `0e 01` mid-sentence (preceded by `02`) → no paragraph split
  2. `0e 01` after `13 04 78` → paragraph split as normal

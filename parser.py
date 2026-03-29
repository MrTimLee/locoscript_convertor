"""
Locoscript 2 file parser.
Handles binary format decoding and text/formatting extraction.
"""

MAGIC = b'DOC'

CTRL_PREFIX    = bytes([0x22, 0x61])        # "a — control sequence prefix
WORD_SEP       = 0x02                        # inter-word space
PARA_BREAK     = bytes([0x13, 0x04, 0x50])  # paragraph end  (P)
LINE_BREAK     = bytes([0x13, 0x04, 0x78])  # line break     (x)
ITALIC_ON      = bytes([0x13, 0x04, 0x64])  # italic start   (d)
TAB_SEQ        = bytes([0x09, 0x05, 0x01])  # tab / citation indent
PARA_INDENT    = bytes([0x08, 0x05, 0x01])  # paragraph indent marker (5 bytes total)
SECTION_BREAK  = 0x0e                        # section / page break marker byte
SECTION_BREAK_TYPES = (0x01, 0x02)          # valid second bytes: 0e 01 and 0e 02

# The start of a paragraph content block — used to skip section-break binary data
PARA_CTRL = bytes([0x22, 0x61, 0x0b])

# Header section-header block: always structural, never body text.
# Its presence within 300 bytes of the first PARA_CTRL means we are still
# in the header transition zone — jump past it to find the real content start.
_C40E_BLOCK = bytes([0x22, 0x61, 0x0b, 0xc4, 0x0e])


class ParseError(Exception):
    pass


class TextRun:
    """A run of plain text, optionally italic."""
    def __init__(self, text: str, italic: bool = False):
        self.text = text
        self.italic = italic

    def __repr__(self):
        return f"TextRun({self.text!r}, italic={self.italic})"


class Paragraph:
    """A paragraph containing a list of TextRuns."""
    def __init__(self):
        self.runs: list[TextRun] = []

    def plain_text(self) -> str:
        return ''.join(r.text for r in self.runs)

    def __repr__(self):
        return f"Paragraph({self.runs!r})"


class Document:
    """Parsed Locoscript 2 document."""
    def __init__(self):
        self.paragraphs: list[Paragraph] = []

    def plain_text(self) -> str:
        return '\n\n'.join(p.plain_text() for p in self.paragraphs if p.plain_text().strip())


def _find_content_start(data: bytes) -> int:
    """
    Find the byte offset where document content begins.

    The first ``22 61 0b`` is always in the header/transition zone.  If a
    ``22 61 0b c4 0e`` structural section-header block appears within 300 bytes
    of the current position we are still inside the header — jump past the
    following section break (``0e 01`` / ``0e 02``) to the next ``22 61 0b``.
    Repeat up to 5 times to handle documents with multiple header cycles.
    """
    try:
        pos = data.index(PARA_CTRL)
    except ValueError:
        return 3

    for _ in range(5):
        search_end = min(pos + 300, len(data))
        c4_pos = data.find(_C40E_BLOCK, pos + 3, search_end)
        if c4_pos == -1:
            break
        # Look for a section/page break byte shortly after the c4 0e block
        sec_pos = None
        for j in range(c4_pos + 5, min(c4_pos + 30, len(data) - 1)):
            if data[j] == 0x0e and data[j + 1] in SECTION_BREAK_TYPES:
                sec_pos = j
                break
        next_para = data.find(PARA_CTRL, sec_pos + 2 if sec_pos else c4_pos + 5)
        if next_para < 0:
            break
        pos = next_para

    return pos


def _skip_ctrl_sequence(data: bytes, i: int) -> int:
    """
    Skip a "a (0x22 0x61) control sequence and return the new offset.

    Type 0x0b (paragraph content) has a fixed 8-byte structure:
        22 61 0b | 3 param bytes | 2 indent bytes
    All other types: skip prefix + type + 1 byte, then skip any trailing
    non-printable bytes and doubled-pair indent markers.
    """
    n = len(data)
    ctrl_type = data[i+2] if i+2 < n else 0x00

    if ctrl_type == 0x0b:
        # Structure: 22 61 0b + 3 param bytes + 2 indent bytes = 8 bytes.
        # Several special cases based on what the param/indent bytes contain:
        if i + 7 < n and data[i+6] == 0x13 and data[i+7] == 0x04:
            # Indent bytes are 13 04 (a formatting prefix) — leave them for
            # the main loop to handle as italic-on/line-break.
            i += 6
        elif i + 8 < n and data[i+6] == 0x78 and data[i+7] == 0x00 and data[i+8] == 0x01:
            # Extended variant: indent area is 78 00, followed by 01 + real
            # indent pair.  Skip the full 11 bytes (8 + 01 + WW WW).
            i += 11
        elif i + 4 < n and data[i+3] == 0xc4 and data[i+4] == 0x0e:
            # c4 0e block: always a structural header with no text content.
            # Skip forward to the next paragraph content block (may be distant).
            next_block = data.find(PARA_CTRL, i + 5)
            i = next_block if next_block >= 0 else n
        elif i + 7 < n and data[i+5] == 0x0a and data[i+6] == 0x09 and data[i+7] == 0x00:
            # Tab-indent variant: 2 param bytes + 0a 09 00 01 + indent pair = 11 bytes.
            i += 11
        elif i + 8 < n and data[i+7] == 0x13 and data[i+8] == 0x04:
            # 13 04 formatting sequence falls at offset 7-8 (one later than case 1);
            # skip 7 bytes and let the main loop handle the 13 04 xx sequence.
            i += 7
        elif i + 8 < n and data[i+7] == 0x22 and data[i+8] == 0x61:
            # Another CTRL_PREFIX (22 61) starts at the indent-byte position;
            # skip 7 bytes and let the main loop handle that control sequence.
            i += 7
        else:
            i += 8
    else:
        # Variable structure: skip prefix + type + 1 extra byte
        i += 4
        # Skip any non-printable parameter bytes (but NOT word separators or
        # 0x13 which may start a 13 04 xx formatting sequence)
        while i < n and data[i] < 0x20 and data[i] != WORD_SEP and data[i] != 0x13:
            i += 1
        # Skip doubled-pair indent markers (e.g. 0x54 0x54, 0x3d 0x3d)
        while i+1 < n and data[i] == data[i+1] and data[i] >= 0x20:
            i += 2

    return i


def parse(data: bytes) -> Document:
    """Parse raw Locoscript 2 file bytes into a Document."""
    if data[:3] != MAGIC:
        raise ParseError("Not a valid Locoscript 2 file (missing DOC header)")

    doc = Document()
    i = _find_content_start(data)
    n = len(data)

    current_para = Paragraph()
    current_text: list[str] = []
    italic = False

    def flush_run():
        nonlocal current_text, italic
        text = ''.join(current_text)
        if text.strip():
            current_para.runs.append(TextRun(text, italic))
        current_text = []

    def flush_para():
        nonlocal current_para
        flush_run()
        if any(r.text.strip() for r in current_para.runs):
            doc.paragraphs.append(current_para)
        current_para = Paragraph()

    while i < n:
        # --- Section / page break: 0e 01 or 0e 02 ---
        # Followed by a binary metadata block; skip ahead to the next paragraph.
        # Any text accumulated before this point (e.g. from the document heading
        # area) is discarded — it is structural, not body content.
        if data[i] == SECTION_BREAK and i+1 < n and data[i+1] in SECTION_BREAK_TYPES:
            flush_run()
            flush_para()
            next_para = data.find(PARA_CTRL, i + 2)
            i = next_para if next_para >= 0 else n
            continue

        # --- Paragraph break: 13 04 50 ---
        if data[i:i+3] == PARA_BREAK:
            flush_run()
            flush_para()
            i += 3
            # Skip trailing indent metadata: 00 01 + doubled printable pair
            if i+3 < n and data[i] == 0x00 and data[i+1] == 0x01 and data[i+2] == data[i+3] and data[i+2] >= 0x20:
                i += 4
            continue

        # --- Italic start: 13 04 64 ---
        if data[i:i+3] == ITALIC_ON:
            flush_run()
            italic = True
            i += 3
            # Skip trailing indent metadata: 00 01 + doubled printable pair
            if i+3 < n and data[i] == 0x00 and data[i+1] == 0x01 and data[i+2] == data[i+3] and data[i+2] >= 0x20:
                i += 4
            continue

        # --- Line break / italic end: 13 04 78 ---
        if data[i:i+3] == LINE_BREAK:
            flush_run()
            if italic:
                italic = False
            else:
                current_text.append('\n')
            i += 3
            # Skip trailing indent metadata: 00 01 + doubled printable pair
            if i+3 < n and data[i] == 0x00 and data[i+1] == 0x01 and data[i+2] == data[i+3] and data[i+2] >= 0x20:
                i += 4
            continue

        # --- Tab sequence: 09 05 01 + 2 param bytes ---
        if data[i:i+3] == TAB_SEQ:
            flush_run()
            current_text.append('\t')
            i += 5  # 09 05 01 + 2 indent/param bytes
            continue

        # --- Paragraph indent marker: 08 05 01 + 2 param bytes ---
        # Structural paragraph indent/style marker. Byte-identical in structure to
        # TAB_SEQ but emits nothing. Without this handler the 2 param bytes (which
        # are often printable) leak into the output as doubled-pair artefacts.
        if data[i:i+3] == PARA_INDENT:
            i += 5  # 08 05 01 + 2 indent/param bytes
            continue

        # --- SI tab / hanging-indent sequences: 0f 04 (tab) and 0f 05 (hanging indent) ---
        # Structure: 0f [04|05]
        #            [optional leading non-printable param bytes]
        #            [optional printable tab-stop encoding, up to 2 bytes]
        #            [optional 01 separator + identical-byte indent pair]
        #            → content
        # Without this handler the printable param bytes (e.g. '1a', 'Rf') and any
        # following doubled pairs (e.g. '**', '>>') leak into the output as artefacts.
        if data[i] == 0x0f and i+1 < n and data[i+1] in (0x04, 0x05):
            is_tab = (data[i+1] == 0x04)
            i += 2
            # Skip leading non-printable param bytes (same rule as variable ctrl handler)
            while i < n and data[i] < 0x20 and data[i] != WORD_SEP and data[i] != 0x13:
                i += 1
            # Skip up to 2 printable tab-stop encoding bytes
            for _ in range(2):
                if i < n and 0x20 <= data[i] <= 0x7E:
                    i += 1
            # If a 0x01 separator follows, skip it plus any identical-byte indent pair
            if i < n and data[i] == 0x01:
                i += 1
                if i+1 < n and data[i] == data[i+1]:
                    i += 2
            if is_tab:
                flush_run()
                current_text.append('\t')
            continue

        # --- Indent metadata: 09 00 01 [+ doubled printable pair] ---
        # Variant tab/indent marker that appears as trailing metadata after content.
        if i+2 < n and data[i] == 0x09 and data[i+1] == 0x00 and data[i+2] == 0x01:
            i += 3
            if i+1 < n and data[i] == data[i+1] and data[i] >= 0x20:
                i += 2
            continue

        # --- Control sequence: 22 61 ---
        if data[i:i+2] == CTRL_PREFIX:
            ctrl_type = data[i+2] if i+2 < n else 0
            if ctrl_type in (WORD_SEP, 0x06):
                # "a followed immediately by a word separator is literal text
                # (e.g. the opening quote in '"a typical..."'), not a control code
                current_text.append('"')
                current_text.append('a')
                i += 2
            else:
                i = _skip_ctrl_sequence(data, i)
                # Skip trailing indent metadata: 00 01 + doubled printable pair
                if i+3 < n and data[i] == 0x00 and data[i+1] == 0x01 and data[i+2] == data[i+3] and data[i+2] >= 0x20:
                    i += 4
            continue

        # --- Word separator: 02 ---
        if data[i] == WORD_SEP:
            current_text.append(' ')
            i += 1
            continue

        # --- Hyphen / extra space: 06 ---
        # When 0x06 falls between two text characters it is a hyphen.
        # When adjacent to word separators or non-printable bytes it is spacing.
        if data[i] == 0x06:
            prev_printable = i > 0 and data[i-1] >= 0x20
            prev_sep = i > 0 and data[i-1] in (WORD_SEP, 0x06)
            next_sep = i+1 < n and data[i+1] in (WORD_SEP, 0x06)
            current_text.append(' ' if (prev_sep or next_sep or not prev_printable) else '-')
            i += 1
            continue

        # --- Extended character mappings ---
        if data[i] == 0xE9:
            current_text.append('£')
            i += 1
            continue

        # --- Printable ASCII ---
        if 0x20 <= data[i] <= 0x7E:
            current_text.append(chr(data[i]))
            i += 1
            continue

        # --- Everything else: skip ---
        i += 1

    flush_run()
    flush_para()

    return doc

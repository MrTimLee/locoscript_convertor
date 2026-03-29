"""
Regression tests for the Locoscript 2 parser.

Two layers of coverage:
  1. Golden-file test — parse the real HENCOTES sample and compare plain-text
     output against a stored snapshot.  Catches any regression that changes
     overall output without pinpointing the cause.

  2. Pattern unit tests — minimal synthetic byte sequences that exercise each
     discovered binary pattern in isolation.  When a regression occurs these
     point directly at the broken pattern.
"""

import unittest
from pathlib import Path

# Allow running from project root or from tests/
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from parser import parse, ParseError, Document, Paragraph, TextRun
from converter import to_txt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MAGIC = b'DOC'
PARA_CTRL = bytes([0x22, 0x61, 0x0b])

def _doc(body: bytes) -> bytes:
    """Wrap body bytes in the minimal valid Locoscript 2 envelope.

    Structure: DOC magic + one standard 0b paragraph-content block (8 bytes)
    + body.  The 0b block uses five zero param/indent bytes so the default
    skip path (i += 8) is taken.
    """
    header = MAGIC + PARA_CTRL + bytes([0x00, 0x00, 0x00, 0x00, 0x00])
    return header + body


def _plain(data: bytes) -> str:
    """Parse synthetic bytes and return the plain-text string."""
    return parse(data).plain_text()


def _paras(data: bytes) -> list[str]:
    """Parse synthetic bytes and return a list of non-empty paragraph texts."""
    return [p.plain_text() for p in parse(data).paragraphs if p.plain_text().strip()]


# ---------------------------------------------------------------------------
# Golden-file regression test
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / 'fixtures'
SAMPLE_FILE = Path(__file__).parent.parent / 'HENCOTES'
GOLDEN_FILE = FIXTURE_DIR / 'HENCOTES.golden.txt'


class TestGoldenFile(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not SAMPLE_FILE.exists():
            raise unittest.SkipTest(f"Sample file not found: {SAMPLE_FILE}")
        if not GOLDEN_FILE.exists():
            raise unittest.SkipTest(f"Golden file not found: {GOLDEN_FILE}")
        with open(SAMPLE_FILE, 'rb') as f:
            cls.doc = parse(f.read())
        cls.actual = to_txt(cls.doc)
        cls.golden = GOLDEN_FILE.read_text(encoding='utf-8')

    def test_output_matches_golden(self):
        """Full plain-text output must match the stored golden snapshot."""
        self.assertEqual(self.actual, self.golden)

    def test_paragraph_count(self):
        """Paragraph count must not silently change."""
        golden_para_count = len([p for p in self.golden.split('\n\n') if p.strip()])
        actual_para_count = len([p for p in self.doc.paragraphs if p.plain_text().strip()])
        self.assertEqual(actual_para_count, golden_para_count)

    def test_key_passages_present(self):
        """Spot-check that known content passages survive parsing."""
        checks = [
            "Hencotes",
            "cockfighting",
            "well heeled",
            "Eminent word",
            "Listed Buildings",
            "Laburnum Cottage",
            "The Times",
        ]
        for phrase in checks:
            self.assertIn(phrase, self.actual, f"Expected passage not found: {phrase!r}")

    def test_no_doubled_pair_artifacts(self):
        """Known doubled-pair indent byte values must not appear as isolated text.

        The specific pairs we've seen as artifacts are: GG JJ ZZ LL TT AA KK MM QQ.
        We exclude pairs that appear legitimately in English prose (e.g. 'II' in Roman
        numerals, 'LL' in 'LL.B.', 'SS' in words like 'lass').
        """
        import re
        # Only check pairs that have no business appearing isolated in prose
        artifact_pairs = ['GG', 'JJ', 'ZZ', 'TT', 'AA', 'KK', 'MM', 'QQ']
        for pair in artifact_pairs:
            # Isolated means not surrounded by other word characters
            pattern = rf'(?<!\w){re.escape(pair)}(?!\w)'
            self.assertNotRegex(self.actual, pattern,
                                f"Doubled-pair artifact {pair!r} found in output")


# ---------------------------------------------------------------------------
# Pattern unit tests
# ---------------------------------------------------------------------------

class TestFileHeader(unittest.TestCase):

    def test_valid_magic_accepted(self):
        data = _doc(b'Hello')
        doc = parse(data)
        self.assertIsInstance(doc, Document)

    def test_invalid_magic_raises(self):
        with self.assertRaises(ParseError):
            parse(b'XXXsome content')


class TestWordSeparator(unittest.TestCase):

    def test_word_sep_becomes_space(self):
        # 02 between words should produce a space
        data = _doc(b'Hello\x02World')
        self.assertIn('Hello World', _plain(data))


class TestParagraphBreak(unittest.TestCase):

    def test_para_break_splits_paragraphs(self):
        # 13 04 50 should end one paragraph and start another
        data = _doc(b'First\x13\x04\x50Second')
        paras = _paras(data)
        self.assertEqual(len(paras), 2)
        self.assertIn('First', paras[0])
        self.assertIn('Second', paras[1])

    def test_para_break_with_trailing_metadata(self):
        # 13 04 50 00 01 4a 4a — trailing 00 01 + doubled pair must be consumed
        data = _doc(b'Alpha\x13\x04\x50\x00\x01\x4a\x4aOmega')
        paras = _paras(data)
        self.assertEqual(len(paras), 2)
        self.assertNotIn('J', paras[1][:2])  # 'JJ' (0x4a 0x4a) must not appear


class TestBoldUnderlineFormatting(unittest.TestCase):

    def test_bold_on_sets_bold_flag(self):
        # 08 00 [01 xx xx] turns bold on; text inside has bold=True
        data = _doc(b'Normal\x02\x08\x00\x01\x11\x11Bold\x09\x00\x01\x11\x11after')
        doc = parse(data)
        runs = [r for p in doc.paragraphs for r in p.runs]
        bold_runs = [r for r in runs if r.bold]
        self.assertTrue(any('Bold' in r.text for r in bold_runs))

    def test_bold_off_clears_bold_flag(self):
        # After 09 00 the bold flag should be cleared
        data = _doc(b'\x08\x00\x01\x11\x11Bold\x09\x00\x01\x11\x11after')
        doc = parse(data)
        runs = [r for p in doc.paragraphs for r in p.runs]
        non_bold = [r for r in runs if not r.bold]
        self.assertTrue(any('after' in r.text for r in non_bold))

    def test_underline_on_sets_flag(self):
        # 08 02 (no params) turns underline on
        data = _doc(b'Before\x08\x02underlined\x09\x02after')
        doc = parse(data)
        runs = [r for p in doc.paragraphs for r in p.runs]
        ul_runs = [r for r in runs if r.underline]
        self.assertTrue(any('underlined' in r.text for r in ul_runs))

    def test_superscript_on_sets_flag(self):
        # 08 06 turns superscript on; 09 06 turns it off
        data = _doc(b'base\x08\x06sup\x09\x06\x01\x11\x11text')
        doc = parse(data)
        runs = [r for p in doc.paragraphs for r in p.runs]
        sup_runs = [r for r in runs if r.superscript]
        self.assertTrue(any('sup' in r.text for r in sup_runs))

    def test_bold_params_not_in_output(self):
        # The 01 separator and indent-pair param bytes must not appear as text
        data = _doc(b'\x08\x00\x01\x11\x11Bold\x09\x00')
        text = _plain(data)
        self.assertIn('Bold', text)
        self.assertNotIn('\x11', text)

    def test_pending_newline_survives_bold_off(self):
        # A '\n' pending in current_text must not be dropped when bold-off fires
        # Sequence: content, line-break (emits \n), bold-off, more content
        data = _doc(b'Line1\x13\x04\x78\x09\x00Line2')
        text = _plain(data)
        self.assertIn('Line1', text)
        self.assertIn('Line2', text)
        self.assertIn('\n', text)


class TestItalic(unittest.TestCase):

    def test_italic_on_sets_italic_flag(self):
        # 13 04 64 turns italic on
        data = _doc(b'Normal\x02\x13\x04\x64italic\x02\x13\x04\x78after')
        doc = parse(data)
        runs = [r for p in doc.paragraphs for r in p.runs]
        italic_runs = [r for r in runs if r.italic]
        self.assertTrue(any('italic' in r.text for r in italic_runs))

    def test_italic_off_via_line_break(self):
        # 13 04 78 when italic=True ends italic; text after should not be italic
        data = _doc(b'\x13\x04\x64italic\x13\x04\x78plain')
        doc = parse(data)
        runs = [r for p in doc.paragraphs for r in p.runs]
        plain_runs = [r for r in runs if not r.italic]
        self.assertTrue(any('plain' in r.text for r in plain_runs))

    def test_line_break_when_not_italic(self):
        # 13 04 78 when italic=False emits a newline
        data = _doc(b'Line1\x13\x04\x78Line2')
        text = _plain(data)
        self.assertIn('\n', text)


class TestTabSequence(unittest.TestCase):

    def test_tab_sequence_emits_tab(self):
        # 09 05 01 + 2 param bytes → tab character
        data = _doc(b'Col1\x09\x05\x01\x00\x00Col2')
        text = _plain(data)
        self.assertIn('\t', text)
        self.assertIn('Col1', text)
        self.assertIn('Col2', text)


class TestSISequences(unittest.TestCase):

    def test_0f_04_emits_tab_and_strips_params(self):
        # 0f 04 [printable param bytes] 01 [doubled pair] → tab, no artefacts
        # Mirrors the real-world case: 0f 04 31 61 01 2a 2a (seen as "1a**" artefacts)
        data = _doc(b'Before\x0f\x04\x31\x61\x01\x2a\x2aAfter')
        text = _plain(data)
        self.assertIn('\t', text)
        self.assertIn('Before', text)
        self.assertIn('After', text)
        self.assertNotIn('1a', text)
        self.assertNotIn('**', text)

    def test_0f_04_no_separator_no_doubled_pair(self):
        # 0f 04 [2 printable param bytes] immediately followed by content (no 01 separator)
        data = _doc(b'Col1\x0f\x04\x27\x66Col2')
        text = _plain(data)
        self.assertIn('\t', text)
        self.assertNotIn("'f", text)

    def test_0f_05_emits_nothing_and_strips_params(self):
        # 0f 05 is a hanging-indent marker — no tab emitted, params consumed
        data = _doc(b'Word\x0f\x05\x31\x61\x01\x3e\x3eContent')
        text = _plain(data)
        self.assertNotIn('1a', text)
        self.assertNotIn('>>', text)
        self.assertIn('Content', text)


class TestIndentMetadata(unittest.TestCase):

    def test_09_00_01_skipped(self):
        # 09 00 01 is structural metadata and must not appear in output
        data = _doc(b'Before\x09\x00\x01After')
        text = _plain(data)
        self.assertIn('Before', text)
        self.assertIn('After', text)

    def test_09_00_01_with_doubled_pair_skipped(self):
        # 09 00 01 4a 4a — the doubled pair must also be consumed
        data = _doc(b'Before\x09\x00\x01\x4a\x4aAfter')
        text = _plain(data)
        self.assertNotIn('JJ', text)
        self.assertIn('After', text)


class TestSectionBreak(unittest.TestCase):

    def test_section_break_01_flushes_content(self):
        # 0e 01 must flush accumulated text, not discard it
        data = _doc(b'PreBreak\x0e\x01' + PARA_CTRL + bytes([0x00]*5) + b'PostBreak')
        paras = _paras(data)
        self.assertTrue(any('PreBreak' in p for p in paras),
                        "Content before section break must not be discarded")

    def test_section_break_02_flushes_content(self):
        # 0e 02 (page break) must also flush
        data = _doc(b'BeforePage\x0e\x02' + PARA_CTRL + bytes([0x00]*5) + b'AfterPage')
        paras = _paras(data)
        self.assertTrue(any('BeforePage' in p for p in paras),
                        "Content before page break must not be discarded")


class TestHyphenByte(unittest.TestCase):

    def test_hyphen_between_words(self):
        # 0x06 between two printable chars → hyphen
        data = _doc(b'well\x06heeled')
        text = _plain(data)
        self.assertIn('well-heeled', text)

    def test_hyphen_adjacent_to_word_sep_is_space(self):
        # 0x06 adjacent to word separator → space, not hyphen
        data = _doc(b'word\x02\x06next')
        text = _plain(data)
        self.assertNotIn('-', text)

    def test_hyphen_after_non_printable_is_space(self):
        # 0x06 after a non-printable byte (e.g. 0x11) → space, not hyphen
        data = _doc(b'\x11\x06word')
        text = _plain(data)
        self.assertNotIn('-', text)


class TestLiteralQuotePrefix(unittest.TestCase):

    def test_22_61_before_word_sep_is_literal(self):
        # 22 61 followed by 02 (word separator) is literal `"a`, not a control code
        data = _doc(b'\x22\x61\x02typical')
        text = _plain(data)
        self.assertIn('"a', text)

    def test_22_61_before_06_is_literal(self):
        # 22 61 followed by 06 is also literal `"a`
        data = _doc(b'\x22\x61\x06word')
        text = _plain(data)
        self.assertIn('"a', text)


class TestExtendedCharacters(unittest.TestCase):

    def test_e9_maps_to_pound_sign(self):
        # 0xE9 is the Locoscript 2 encoding for the pound sign £
        data = _doc(b'\xe91.4million')
        text = _plain(data)
        self.assertIn('£', text)
        self.assertNotIn('?', text)


class TestENQExtendedCharacters(unittest.TestCase):

    def test_cedilla_c_maps_to_c_cedilla(self):
        # 05 63 01 13 01 is the ENQ encoding for ç (c with cedilla)
        data = _doc(b'fa\x05\x63\x01\x13\x01ade')
        text = _plain(data)
        self.assertIn('ç', text)
        self.assertIn('façade', text)

    def test_cedilla_no_base_char_artifact(self):
        # The raw 'c' byte (0x63) must not appear as a separate artifact
        data = _doc(b'Fran\x05\x63\x01\x13\x01ais')
        text = _plain(data)
        self.assertIn('ç', text)
        self.assertNotIn('Franc', text)  # 'c' must not leak before 'ais'

    def test_cedilla_trailing_doubled_pair_consumed(self):
        # 05 63 01 13 01 followed by 01 XX XX — the doubled pair must not appear
        data = _doc(b'fa\x05\x63\x01\x13\x01\x01\x46\x46ade')
        text = _plain(data)
        self.assertIn('ç', text)
        self.assertNotIn('FF', text)

    def test_enq_unknown_diacritic_emits_base_char(self):
        # An ENQ sequence with an unknown diacritic emits the base character (0x68 = 'h')
        # rather than '?' or nothing — best-effort fallback for undocumented diacritics
        data = _doc(b'wit\x05\x68\x01\x07\x01out')
        text = _plain(data)
        self.assertIn('h', text)   # base char emitted
        self.assertIn('without', text)

    def test_enq_does_not_misfire_on_structural_bytes(self):
        # 05 with a non-printable base byte must not be treated as ENQ char encoding
        data = _doc(b'After\x05\x00\x01\x13\x01text')
        text = _plain(data)
        self.assertIn('text', text)


class TestControlSequenceSkip(unittest.TestCase):

    def test_unknown_ctrl_type_skipped_cleanly(self):
        # An unknown control type (e.g. 0x0c) should be skipped without
        # corrupting the text that follows
        data = _doc(b'\x22\x61\x0c\x00\x00\x00After')
        text = _plain(data)
        self.assertIn('After', text)


if __name__ == '__main__':
    unittest.main()

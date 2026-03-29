"""
Regenerate the golden fixture file from the current parser output.

Run this whenever a parser change intentionally improves the output:

    python tests/regenerate_golden.py

The updated fixture is then committed alongside the parser change so that
test_output_matches_golden reflects the new expected state.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from parser import parse
from converter import to_txt

SAMPLE = Path(__file__).parent.parent / 'HENCOTES'
GOLDEN = Path(__file__).parent / 'fixtures' / 'HENCOTES.golden.txt'

if not SAMPLE.exists():
    print(f"ERROR: sample file not found: {SAMPLE}", file=sys.stderr)
    sys.exit(1)

with open(SAMPLE, 'rb') as f:
    doc = parse(f.read())

output = to_txt(doc)
GOLDEN.write_text(output, encoding='utf-8')
print(f"Golden file updated: {GOLDEN}")
print(f"  {len(output)} chars, {output.count(chr(10)+chr(10)) + 1} paragraphs")

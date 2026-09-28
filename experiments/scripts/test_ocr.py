"""Small experiment: turn one extracted drug document into structured data."""

from __future__ import annotations

import json
import sys
from pathlib import Path


SECTION_FIXES = {
    "( ةلاعفلا ةداملاActive Ingredient):":
        "Active Ingredient(الماده الفعاله):",
    "( جالعلا تارشؤم / تامادختسالاIndications):":
        "Indications(مؤشرات العلاج):",
    "( ةماه تاريذحتWarnings):":
        "Warnings(التحذيرات):",
}

SECTION_HEADERS = (
    ("active_ingredient", "Active Ingredient(الماده الفعاله):"),
    ("indications", "Indications(مؤشرات العلاج):"),
    ("warnings", "Warnings(التحذيرات):"),
)


def normalize_section_headers(text: str) -> str:
    """Replace the three known corrupted headers with readable labels."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(SECTION_FIXES.get(line.strip(), line.strip()) for line in lines)


def parse_drug_text(text: str, file_name: str, page_number: int = 1) -> dict:
    """Parse a single drug document whose three section headers are ordered."""
    if page_number < 1:
        raise ValueError("page_number must be 1 or greater")

    lines = normalize_section_headers(text).splitlines()
    non_empty = [(index, line.strip()) for index, line in enumerate(lines) if line.strip()]
    if not non_empty:
        raise ValueError("document is empty")

    header_indexes = {}
    for key, header in SECTION_HEADERS:
        matches = [index for index, line in non_empty if line == header]
        if len(matches) != 1:
            raise ValueError(f"expected exactly one {header!r} header, found {len(matches)}")
        header_indexes[key] = matches[0]

    positions = [header_indexes[key] for key, _ in SECTION_HEADERS]
    if positions != sorted(positions):
        raise ValueError("section headers are out of order")

    first_line_index, drug_name = non_empty[0]
    if first_line_index >= positions[0]:
        raise ValueError("drug name must appear before the first section")

    def content_between(start: int, end: int | None = None) -> str:
        section_lines = lines[start + 1 : end]
        return "\n".join(line.strip() for line in section_lines).strip()

    return {
        "drug_name": drug_name,
        "active_ingredient": content_between(positions[0], positions[1]),
        "indications": content_between(positions[1], positions[2]),
        "warnings": content_between(positions[2]),
        "source": {
            "file_name": Path(file_name).name,
            "page_number": page_number,
        },
    }


def _demo() -> None:
    sample = """
1 2 3 (one two three) syrup 120 ml

( ةلاعفلا ةداملاActive Ingredient):
Chlorpheniramine+paracetamol+pseudoephedrine

( جالعلا تارشؤم / تامادختسالاIndications):
وصف عربي

( ةماه تاريذحتWarnings):
تحذيرات عربية
"""
    result = parse_drug_text(sample, "example.pdf", 1)
    assert result == {
        "drug_name": "1 2 3 (one two three) syrup 120 ml",
        "active_ingredient": "Chlorpheniramine+paracetamol+pseudoephedrine",
        "indications": "وصف عربي",
        "warnings": "تحذيرات عربية",
        "source": {"file_name": "example.pdf", "page_number": 1},
    }
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _demo()

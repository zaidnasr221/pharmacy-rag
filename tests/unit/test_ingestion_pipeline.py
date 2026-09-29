import json

from pharmacy_rag.ingestion.pipeline import (
    DrugIngestionPipeline,
    SECTION_FIXES,
    fix_section_headers,
    parse_drug,
)


def test_changes_only_the_three_headers():
    raw_text = """
Drug Name

( ةلاعفلا ةداملاActive Ingredient):
ingredient

( جالعلا تارشؤم / تامادختسالاIndications):
indication

( ةماه تاريذحتWarnings):
warning

ملاحظة يجب أن تبقى كما هي
"""

    fixed_text = fix_section_headers(raw_text)

    expected_text = raw_text

    for wrong, correct in SECTION_FIXES.items():
        expected_text = expected_text.replace(
            wrong,
            correct,
        )

    assert fixed_text == expected_text
    assert "ملاحظة يجب أن تبقى كما هي" in fixed_text


def test_parses_complete_drug():
    raw_text = """
Test Drug

( ةلاعفلا ةداملاActive Ingredient):
ingredient

( جالعلا تارشؤم / تامادختسالاIndications):
indication

( ةماه تاريذحتWarnings):
warning
"""

    fixed_text = fix_section_headers(raw_text)

    drug, missing_sections = parse_drug(
        text=fixed_text,
        file_name="test.pdf",
    )

    assert drug == {
        "drug_name": "Test Drug",
        "active_ingredient": "ingredient",
        "indications": "indication",
        "warnings": "warning",
        "source": {
            "file_name": "test.pdf",
        },
    }

    assert missing_sections == []


def test_missing_section_becomes_empty():
    raw_text = """
Incomplete Drug

( جالعلا تارشؤم / تامادختسالاIndications):
indication

( ةماه تاريذحتWarnings):
warning
ملاحظة تبقى كما هي
"""

    fixed_text = fix_section_headers(raw_text)

    drug, missing_sections = parse_drug(
        text=fixed_text,
        file_name="incomplete.pdf",
    )

    assert drug["active_ingredient"] == ""
    assert drug["indications"] == "indication"

    assert drug["warnings"] == (
        "warning\n"
        "ملاحظة تبقى كما هي"
    )

    assert missing_sections == [
        "active_ingredient",
    ]


def test_pipeline_writes_one_json_file(tmp_path):
    pdf_directory = tmp_path / "pdfs"
    output_path = tmp_path / "drugs.json"

    pdf_directory.mkdir()

    (pdf_directory / "one.pdf").touch()
    (pdf_directory / "two.pdf").touch()

    extracted_text = """
Test Drug

( ةلاعفلا ةداملاActive Ingredient):
ingredient

( جالعلا تارشؤم / تامادختسالاIndications):
indication

( ةماه تاريذحتWarnings):
warning
"""

    pipeline = DrugIngestionPipeline(
        extractor=lambda _: extracted_text,
    )

    summary = pipeline.run(
        pdf_directory=pdf_directory,
        output_path=output_path,
    )

    saved_records = json.loads(
        output_path.read_text(encoding="utf-8")
    )

    assert summary.selected_pdfs == 2
    assert summary.saved_drugs == 2
    assert summary.errors == []
    assert len(saved_records) == 2
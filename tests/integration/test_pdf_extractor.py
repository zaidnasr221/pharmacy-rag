import pymupdf

from pharmacy_rag.ingestion.pipeline import (
    extract_pdf_text,
)


def test_extracts_text_from_real_pdf(tmp_path):
    pdf_path = tmp_path / "sample.pdf"

    with pymupdf.open() as document:
        page = document.new_page()

        page.insert_text(
            (72, 72),
            "PyMuPDF extraction works",
        )

        document.save(pdf_path)

    extracted_text = extract_pdf_text(pdf_path)

    assert "PyMuPDF extraction works" in extracted_text
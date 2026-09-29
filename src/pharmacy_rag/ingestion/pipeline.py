from collections import Counter 
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import json
import pymupdf

from .schema import DrugRecord

SECTION_FIXES = {
    "( ةلاعفلا ةداملاActive Ingredient):":
        "Active Ingredient(الماده الفعاله):",

    "( جالعلا تارشؤم / تامادختسالاIndications):":
        "Indications(مؤشرات العلاج):",

    "( ةماه تاريذحتWarnings):":
        "Warnings(التحذيرات):",
}


SECTION_HEADERS = {
    "active_ingredient":
        "Active Ingredient(الماده الفعاله):",

    "indications":
        "Indications(مؤشرات العلاج):",

    "warnings":
        "Warnings(التحذيرات):",
}

TextExtractor = Callable[[Path],str]

@dataclass(frozen=True)
class IngestionSummary:
    selected_pdfs : int
    saved_drugs : int
    missing_sections : dict[str,int]
    errors : list[dict[str,str]]
    
def extract_pdf_text(pdf_path:Path) -> str:
    """Extract all PDF pages without modifying their text."""
    with pymupdf.open(pdf_path) as document:
        return "\n".join(
            page.get_text()
            for page in document
        )    

def fix_section_headers(text: str) ->str:
    """Replace only the three know corrupted headers."""
    for wrong, correct in SECTION_FIXES.items():
        text = text.replace(wrong,correct)
    return text

def parse_drug(
    text:str,
    file_name:str,
) -> tuple[dict,list[str]]:
    """Parse available sections and leave missing fields empty."""
    lines = text.splitlines()
    drug_name = next(
        (
            line.strip()
            for line in lines
            if line.strip()
        ),
        "",
    )
    
    positions : dict[str,int] ={}
    for index, line in enumerate(lines):
        for field_name, header in SECTION_HEADERS.items():
            if line.strip() == header:
                positions.setdefault(field_name, index)
                
    ordered_sections = sorted(
        (
            position,
            field_name,
        )
        for field_name, position in positions.items()
    )

    drug = {
        "drug_name": drug_name,
        "active_ingredient": "",
        "indications": "",
        "warnings": "",
        "source": {
            "file_name": file_name,
        },
    }            
    
    for section_number, (start, field_name) in enumerate(
        ordered_sections
    ):
        if section_number + 1 < len(ordered_sections):
            end = ordered_sections[section_number + 1][0]
        else:
            end = len(lines)

        drug[field_name] = "\n".join(
            lines[start + 1:end]
        ).strip()

    missing_sections = [
        field_name
        for field_name in SECTION_HEADERS
        if field_name not in positions
    ]

    validated_drug = DrugRecord.model_validate(drug)

    return validated_drug.model_dump(), missing_sections


def _write_json(
    records: list[dict],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_suffix(
        ".json.tmp"
    )

    temporary_path.write_text(
        json.dumps(
            records,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(output_path)
    
class DrugIngestionPipeline:
    """Orchestrate PDF extraction, parsing, and JSON writing."""

    def __init__(
        self,
        extractor: TextExtractor = extract_pdf_text,
    ) -> None:
        self.extractor = extractor

    def process_pdf(
        self,
        pdf_path: Path,
    ) -> tuple[dict, list[str]]:
        raw_text = self.extractor(pdf_path)
        fixed_text = fix_section_headers(raw_text)

        return parse_drug(
            text=fixed_text,
            file_name=pdf_path.name,
        )

    def run(
        self,
        pdf_directory: Path,
        output_path: Path,
        limit: int | None = None,
    ) -> IngestionSummary:
        if not pdf_directory.exists():
            raise FileNotFoundError(
                f"PDF directory not found: {pdf_directory}"
            )

        pdf_paths = sorted(
            pdf_directory.glob("*.pdf")
        )

        if not pdf_paths:
            raise FileNotFoundError(
                f"No PDFs found in: {pdf_directory}"
            )

        if limit is not None:
            if limit < 1:
                raise ValueError(
                    "limit must be greater than zero"
                )

            pdf_paths = pdf_paths[:limit]

        drugs: list[dict] = []
        errors: list[dict[str, str]] = []
        missing_counts: Counter[str] = Counter()

        for index, pdf_path in enumerate(
            pdf_paths,
            start=1,
        ):
            try:
                drug, missing_sections = (
                    self.process_pdf(pdf_path)
                )

                drugs.append(drug)
                missing_counts.update(missing_sections)

            except Exception as error:
                errors.append(
                    {
                        "file_name": pdf_path.name,
                        "error": str(error),
                    }
                )

            if index % 100 == 0:
                print(
                    f"Processed: {index}/{len(pdf_paths)}"
                )

        _write_json(
            records=drugs,
            output_path=output_path,
        )

        return IngestionSummary(
            selected_pdfs=len(pdf_paths),
            saved_drugs=len(drugs),
            missing_sections=dict(missing_counts),
            errors=errors,
        )    
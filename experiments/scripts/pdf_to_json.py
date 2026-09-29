from argparse import ArgumentParser
from pathlib import Path
import json
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src"),
)

from pharmacy_rag.ingestion import (  # noqa: E402
    DrugIngestionPipeline,
)


PDF_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "drug_pdfs"
)

PROCESSED_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "processed"
)


def parse_arguments():
    parser = ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only N PDFs for testing.",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    output_name = (
        "drugs_test.json"
        if arguments.limit is not None
        else "drugs.json"
    )

    output_path = (
        PROCESSED_DIRECTORY
        / output_name
    )

    pipeline = DrugIngestionPipeline()

    summary = pipeline.run(
        pdf_directory=PDF_DIRECTORY,
        output_path=output_path,
        limit=arguments.limit,
    )

    print()
    print("=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print("Selected PDFs:", summary.selected_pdfs)
    print("Saved drugs:", summary.saved_drugs)
    print("Errors:", len(summary.errors))
    print(
        "Missing sections:",
        summary.missing_sections,
    )
    print("Output file:", output_path)

    if summary.errors:
        print()
        print("FIRST 10 ERRORS")

        for error in summary.errors[:10]:
            print(
                json.dumps(
                    error,
                    ensure_ascii=False,
                    indent=2,
                )
            )

        raise SystemExit(1)

    print()
    print("Extraction completed successfully.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    main()
"""Run the production chunker as an experiment."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src"),
)

from pharmacy_rag.preprocessing import (  # noqa: E402
    DrugChunkingPipeline,
    SectionChunker,
)


INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "drugs.json"
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "processed"
)


def parse_arguments():
    parser = ArgumentParser(
        description=(
            "Run adaptive section-based chunking."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only N drugs for testing.",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    output_name = (
        "chunks_test.json"
        if arguments.limit is not None
        else "chunks.json"
    )

    output_path = (
        OUTPUT_DIRECTORY
        / output_name
    )

    strategy = SectionChunker(
        max_chunk_characters=1200,
        overlap_characters=150,
    )

    pipeline = DrugChunkingPipeline(
        strategy=strategy,
    )

    summary = pipeline.run(
        input_path=INPUT_PATH,
        output_path=output_path,
        limit=arguments.limit,
    )

    print()
    print("=" * 60)
    print("ADAPTIVE CHUNKING SUMMARY")
    print("=" * 60)
    print(
        "Selected drugs:",
        summary.selected_drugs,
    )
    print(
        "Created chunks:",
        summary.created_chunks,
    )
    print(
        "Chunk types:",
        summary.section_counts,
    )
    print(
        "Split section groups:",
        summary.split_section_groups,
    )
    print(
        "Largest section group:",
        summary.largest_section_group,
    )
    print(
        "Largest chunk characters:",
        summary.largest_chunk_characters,
    )
    print(
        "Skipped empty sections:",
        summary.skipped_sections,
    )
    print(
        "Output file:",
        summary.output_path,
    )
    print()
    print(
        "Adaptive chunking completed successfully."
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    main()
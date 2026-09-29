import json

import pytest

from pharmacy_rag.ingestion.schema import DrugRecord
from pharmacy_rag.preprocessing.chunking import (
    DrugChunkingPipeline,
    SectionChunker,
)


def make_drug(
    *,
    active_ingredient: str = "paracetamol",
    indications: str = "Used for pain relief.",
    warnings: str = "Use under medical supervision.",
) -> DrugRecord:
    return DrugRecord.model_validate(
        {
            "drug_name": "Test Drug",
            "active_ingredient": active_ingredient,
            "indications": indications,
            "warnings": warnings,
            "source": {
                "file_name": "test_drug.pdf",
            },
        }
    )


def indication_chunks(chunks: list[dict]) -> list[dict]:
    return [
        chunk
        for chunk in chunks
        if chunk["metadata"]["section"] == "indications"
    ]


def overlap_size(
    first: str,
    second: str,
) -> int:
    maximum = min(
        len(first),
        len(second),
    )

    for size in range(maximum, 0, -1):
        if first.endswith(second[:size]):
            return size

    return 0


def test_short_drug_creates_three_connected_chunks():
    chunker = SectionChunker()
    drug = make_drug()

    chunks, skipped_sections = (
        chunker.chunk_drug(drug)
    )

    assert skipped_sections == []
    assert len(chunks) == 3

    assert {
        chunk["metadata"]["section"]
        for chunk in chunks
    } == {
        "identity",
        "indications",
        "warnings",
    }

    for chunk in chunks:
        assert "Test Drug" in chunk["content"]
        assert "paracetamol" in chunk["content"]
        assert (
            chunk["metadata"]["drug_id"]
            == "test_drug"
        )


def test_empty_active_ingredient_keeps_identity():
    chunker = SectionChunker()

    chunks, _ = chunker.chunk_drug(
        make_drug(active_ingredient="")
    )

    identity = next(
        chunk
        for chunk in chunks
        if chunk["metadata"]["section"] == "identity"
    )

    assert identity["metadata"]["active_ingredient"] == ""
    assert "Drug Name: Test Drug" in identity["content"]


def test_empty_sections_are_skipped():
    chunker = SectionChunker()

    chunks, skipped_sections = (
        chunker.chunk_drug(
            make_drug(
                indications="",
                warnings="",
            )
        )
    )

    assert len(chunks) == 1
    assert chunks[0]["metadata"]["section"] == "identity"

    assert skipped_sections == [
        "indications",
        "warnings",
    ]


def test_long_indications_stay_within_limit():
    chunker = SectionChunker(
        max_chunk_characters=1200,
        overlap_characters=150,
    )

    drug = make_drug(
        indications=" ".join(
            f"indication-{index}"
            for index in range(1000)
        )
    )

    chunks, _ = chunker.chunk_drug(drug)
    parts = indication_chunks(chunks)

    assert len(parts) > 1

    assert all(
        len(chunk["content"]) <= 1200
        for chunk in chunks
    )

    chunker.validate_chunks(chunks)


def test_split_text_has_overlap():
    chunker = SectionChunker(
        max_chunk_characters=300,
        overlap_characters=50,
    )

    parts = chunker.split_text(
        text=" ".join(
            f"word-{index:04d}"
            for index in range(300)
        ),
        max_characters=300,
    )

    assert len(parts) > 1

    for first, second in zip(parts, parts[1:]):
        assert overlap_size(first, second) >= 30


def test_chunk_indexes_and_counts_are_consistent():
    chunker = SectionChunker()

    chunks, _ = chunker.chunk_drug(
        make_drug(
            indications=" ".join(
                f"medical-text-{index}"
                for index in range(1000)
            )
        )
    )

    parts = indication_chunks(chunks)
    expected_count = len(parts)

    assert expected_count > 1

    assert [
        chunk["metadata"]["chunk_index"]
        for chunk in parts
    ] == list(range(expected_count))

    assert all(
        chunk["metadata"]["chunk_count"]
        == expected_count
        for chunk in parts
    )


def test_duplicate_chunk_ids_are_rejected():
    chunker = SectionChunker()

    chunks, _ = chunker.chunk_drug(
        make_drug()
    )

    with pytest.raises(
        ValueError,
        match="Duplicate chunk IDs",
    ):
        chunker.validate_chunks(
            [
                chunks[0],
                chunks[0].copy(),
            ]
        )


def test_pipeline_writes_valid_chunks(tmp_path):
    input_path = tmp_path / "drugs.json"
    output_path = tmp_path / "chunks.json"

    drug = make_drug()

    input_path.write_text(
        json.dumps(
            [drug.model_dump()],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    pipeline = DrugChunkingPipeline(
        strategy=SectionChunker(),
    )

    summary = pipeline.run(
        input_path=input_path,
        output_path=output_path,
    )

    saved_chunks = json.loads(
        output_path.read_text(encoding="utf-8")
    )

    assert summary.selected_drugs == 1
    assert summary.created_chunks == 3
    assert summary.section_counts == {
        "identity": 1,
        "indications": 1,
        "warnings": 1,
    }

    assert len(saved_chunks) == 3
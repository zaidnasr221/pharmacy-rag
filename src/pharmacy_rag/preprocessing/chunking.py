"""Production chunking logic for structured drug records."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import json

from pharmacy_rag.ingestion.schema import DrugRecord


DEFAULT_MAX_CHUNK_CHARACTERS = 1200
DEFAULT_OVERLAP_CHARACTERS = 150

ALLOWED_SECTIONS = {
    "identity",
    "indications",
    "warnings",
}


class ChunkingStrategy(Protocol):
    """Contract implemented by drug chunking strategies."""

    def chunk_drug(
        self,
        drug: DrugRecord,
    ) -> tuple[list[dict], list[str]]:
        """Convert one drug into chunks."""

    def validate_chunks(
        self,
        chunks: Sequence[dict],
    ) -> None:
        """Validate generated chunks."""


@dataclass(frozen=True)
class ChunkingSummary:
    selected_drugs: int
    created_chunks: int
    section_counts: dict[str, int]
    split_section_groups: int
    largest_section_group: int
    largest_chunk_characters: int
    skipped_sections: dict[str, int]
    output_path: Path


class SectionChunker:
    """Adaptive section-based chunking strategy."""

    def __init__(
        self,
        max_chunk_characters: int = (
            DEFAULT_MAX_CHUNK_CHARACTERS
        ),
        overlap_characters: int = (
            DEFAULT_OVERLAP_CHARACTERS
        ),
    ) -> None:
        if max_chunk_characters < 1:
            raise ValueError(
                "max_chunk_characters must be "
                "greater than zero"
            )

        if overlap_characters < 0:
            raise ValueError(
                "overlap_characters must not be negative"
            )

        if overlap_characters >= max_chunk_characters:
            raise ValueError(
                "overlap_characters must be smaller "
                "than max_chunk_characters"
            )

        self.max_chunk_characters = (
            max_chunk_characters
        )
        self.overlap_characters = overlap_characters

    def _find_break_position(
        self,
        text: str,
        start: int,
        hard_end: int,
        max_characters: int,
    ) -> int:
        minimum_break = (
            start
            + int(max_characters * 0.60)
        )

        separators = (
            "\n\n",
            "\n",
            ". ",
            "؟ ",
            "! ",
            "؛ ",
            "، ",
            " ",
        )

        for separator in separators:
            position = text.rfind(
                separator,
                minimum_break,
                hard_end,
            )

            if position != -1:
                return position + len(separator)

        return hard_end

    def _align_overlap_start(
        self,
        text: str,
        start: int,
        end: int,
        overlap_characters: int,
    ) -> int:
        next_start = max(
            end - overlap_characters,
            start + 1,
        )

        while (
            next_start < end
            and next_start > 0
            and not text[next_start - 1].isspace()
        ):
            next_start += 1

        if next_start <= start:
            return end

        return next_start

    def split_text(
        self,
        text: str,
        max_characters: int,
    ) -> list[str]:
        """Split text at structural boundaries with overlap."""

        text = text.strip()

        if not text:
            return []

        if max_characters < 1:
            raise ValueError(
                "max_characters must be greater than zero"
            )

        if self.overlap_characters >= max_characters:
            raise ValueError(
                "Available text space must be larger "
                "than overlap_characters"
            )

        if len(text) <= max_characters:
            return [text]

        parts: list[str] = []
        start = 0

        while start < len(text):
            hard_end = min(
                start + max_characters,
                len(text),
            )

            if hard_end == len(text):
                end = hard_end
            else:
                end = self._find_break_position(
                    text=text,
                    start=start,
                    hard_end=hard_end,
                    max_characters=max_characters,
                )

            part = text[start:end].strip()

            if part:
                parts.append(part)

            if end >= len(text):
                break

            start = self._align_overlap_start(
                text=text,
                start=start,
                end=end,
                overlap_characters=(
                    self.overlap_characters
                ),
            )

        return parts

    @staticmethod
    def build_content(
        drug: DrugRecord,
        section_label: str | None = None,
        section_content: str = "",
    ) -> str:
        lines = [
            f"Drug Name: {drug.drug_name}",
            (
                "Active Ingredient: "
                f"{drug.active_ingredient}"
            ),
        ]

        if section_label is not None:
            lines.extend(
                [
                    f"{section_label}:",
                    section_content,
                ]
            )

        return "\n".join(lines).strip()

    def _build_chunk(
        self,
        drug: DrugRecord,
        section: str,
        section_content: str,
        chunk_index: int,
        chunk_count: int,
    ) -> dict:
        drug_id = Path(
            drug.source.file_name
        ).stem

        section_labels = {
            "identity": None,
            "indications": "Indications",
            "warnings": "Warnings",
        }

        content = self.build_content(
            drug=drug,
            section_label=section_labels[section],
            section_content=section_content,
        )

        return {
            "chunk_id": (
                f"{drug_id}:{section}:{chunk_index}"
            ),
            "content": content,
            "metadata": {
                "drug_id": drug_id,
                "drug_name": drug.drug_name,
                "active_ingredient": (
                    drug.active_ingredient
                ),
                "section": section,
                "chunk_index": chunk_index,
                "chunk_count": chunk_count,
                "source_file": (
                    drug.source.file_name
                ),
            },
        }

    def _build_section_chunks(
        self,
        drug: DrugRecord,
        section: str,
        parts: list[str],
    ) -> list[dict]:
        chunk_count = len(parts)

        return [
            self._build_chunk(
                drug=drug,
                section=section,
                section_content=part,
                chunk_index=index,
                chunk_count=chunk_count,
            )
            for index, part in enumerate(parts)
        ]

    def chunk_drug(
        self,
        drug: DrugRecord,
    ) -> tuple[list[dict], list[str]]:
        chunks = self._build_section_chunks(
            drug=drug,
            section="identity",
            parts=[""],
        )

        skipped_sections: list[str] = []

        if drug.indications.strip():
            indications_header = self.build_content(
                drug=drug,
                section_label="Indications",
                section_content="",
            )

            available_characters = (
                self.max_chunk_characters
                - len(indications_header)
                - 1
            )

            if (
                available_characters
                <= self.overlap_characters
            ):
                raise ValueError(
                    "Drug metadata leaves insufficient "
                    "space for indications: "
                    f"{drug.source.file_name}"
                )

            indication_parts = self.split_text(
                text=drug.indications,
                max_characters=available_characters,
            )

            chunks.extend(
                self._build_section_chunks(
                    drug=drug,
                    section="indications",
                    parts=indication_parts,
                )
            )
        else:
            skipped_sections.append("indications")

        if drug.warnings.strip():
            chunks.extend(
                self._build_section_chunks(
                    drug=drug,
                    section="warnings",
                    parts=[drug.warnings],
                )
            )
        else:
            skipped_sections.append("warnings")

        return chunks, skipped_sections

    def validate_chunks(
        self,
        chunks: Sequence[dict],
    ) -> None:
        chunk_ids = [
            chunk["chunk_id"]
            for chunk in chunks
        ]

        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError(
                "Duplicate chunk IDs were generated"
            )

        grouped_chunks: defaultdict[
            tuple[str, str],
            list[dict],
        ] = defaultdict(list)

        for chunk in chunks:
            content = chunk["content"]

            if not content.strip():
                raise ValueError(
                    f"Empty chunk: {chunk['chunk_id']}"
                )

            metadata = chunk["metadata"]
            section = metadata["section"]

            if section not in ALLOWED_SECTIONS:
                raise ValueError(
                    f"Invalid section: {section}"
                )

            if (
                len(content)
                > self.max_chunk_characters
            ):
                raise ValueError(
                    "Chunk exceeds maximum size: "
                    f"{chunk['chunk_id']} "
                    f"({len(content)} characters)"
                )

            grouped_chunks[
                (
                    metadata["drug_id"],
                    section,
                )
            ].append(chunk)

        for group, group_chunks in grouped_chunks.items():
            expected_count = group_chunks[0][
                "metadata"
            ]["chunk_count"]

            indexes = sorted(
                chunk["metadata"]["chunk_index"]
                for chunk in group_chunks
            )

            if len(group_chunks) != expected_count:
                raise ValueError(
                    f"Invalid chunk count for: {group}"
                )

            if indexes != list(range(expected_count)):
                raise ValueError(
                    f"Invalid chunk indexes for: {group}"
                )


def load_drugs(
    input_path: Path,
    limit: int | None = None,
) -> list[DrugRecord]:
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input JSON file not found: {input_path}"
        )

    if limit is not None and limit < 1:
        raise ValueError(
            "limit must be greater than zero"
        )

    raw_records = json.loads(
        input_path.read_text(encoding="utf-8")
    )

    if not isinstance(raw_records, list):
        raise ValueError(
            "The input JSON must contain a list of drugs"
        )

    if limit is not None:
        raw_records = raw_records[:limit]

    return [
        DrugRecord.model_validate(record)
        for record in raw_records
    ]


def write_chunks(
    chunks: Sequence[dict],
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
            chunks,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(output_path)


class DrugChunkingPipeline:
    """Run an injected chunking strategy on drug records."""

    def __init__(
        self,
        strategy: ChunkingStrategy,
    ) -> None:
        self.strategy = strategy

    def run(
        self,
        input_path: Path,
        output_path: Path,
        limit: int | None = None,
    ) -> ChunkingSummary:
        drugs = load_drugs(
            input_path=input_path,
            limit=limit,
        )

        chunks: list[dict] = []
        skipped_counts: Counter[str] = Counter()

        for drug in drugs:
            drug_chunks, skipped_sections = (
                self.strategy.chunk_drug(drug)
            )

            chunks.extend(drug_chunks)
            skipped_counts.update(skipped_sections)

        self.strategy.validate_chunks(chunks)

        write_chunks(
            chunks=chunks,
            output_path=output_path,
        )

        section_counts = Counter(
            chunk["metadata"]["section"]
            for chunk in chunks
        )

        split_section_groups = sum(
            1
            for chunk in chunks
            if (
                chunk["metadata"]["chunk_index"] == 0
                and chunk["metadata"]["chunk_count"] > 1
            )
        )

        largest_section_group = max(
            (
                chunk["metadata"]["chunk_count"]
                for chunk in chunks
            ),
            default=0,
        )

        largest_chunk_characters = max(
            (
                len(chunk["content"])
                for chunk in chunks
            ),
            default=0,
        )

        return ChunkingSummary(
            selected_drugs=len(drugs),
            created_chunks=len(chunks),
            section_counts=dict(section_counts),
            split_section_groups=split_section_groups,
            largest_section_group=largest_section_group,
            largest_chunk_characters=(
                largest_chunk_characters
            ),
            skipped_sections=dict(skipped_counts),
            output_path=output_path,
        )
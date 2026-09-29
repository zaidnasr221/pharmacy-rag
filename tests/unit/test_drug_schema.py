import pytest
from pydantic import ValidationError

from pharmacy_rag.ingestion.schema import DrugRecord


def valid_drug(**changes):
    drug = {
        "drug_name": "Test Drug",
        "active_ingredient": "paracetamol",
        "indications": "Pain relief",
        "warnings": "Use under medical supervision",
        "source": {
            "file_name": "test_drug.pdf",
        },
    }

    drug.update(changes)
    return drug


def test_accepts_complete_drug():
    drug = DrugRecord.model_validate(valid_drug())

    assert drug.drug_name == "Test Drug"
    assert drug.active_ingredient == "paracetamol"


def test_accepts_empty_missing_medical_fields():
    drug = DrugRecord.model_validate(
        valid_drug(
            active_ingredient="",
            indications="",
            warnings="",
        )
    )

    assert drug.active_ingredient == ""
    assert drug.indications == ""
    assert drug.warnings == ""


def test_rejects_empty_drug_name():
    with pytest.raises(ValidationError):
        DrugRecord.model_validate(
            valid_drug(drug_name="")
        )


def test_rejects_invalid_source_file_name():
    with pytest.raises(ValidationError):
        DrugRecord.model_validate(
            valid_drug(
                source={"file_name": "test_drug.txt"}
            )
        )


def test_rejects_extra_fields():
    with pytest.raises(ValidationError):
        DrugRecord.model_validate(
            valid_drug(category="painkiller")
        )
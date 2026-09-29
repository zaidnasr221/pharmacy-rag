from pathlib import Path
from pydantic import BaseModel, ConfigDict, field_validator

class DrugSource(BaseModel):
    """Identify the PDF from which the drug was extracted."""
    
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )
    file_name:str
    
    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source.file_name must not be empty")

        if Path(value).suffix.lower() != ".pdf":
            raise ValueError("source.file_name must end with .pdf")

        return value
    
    
class DrugRecord(BaseModel):
    """Validated output of the drug extraction pipeline."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    drug_name: str
    active_ingredient: str
    indications: str
    warnings: str
    source: DrugSource

    @field_validator("drug_name")
    @classmethod
    def validate_drug_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("drug_name must not be empty")

        return value

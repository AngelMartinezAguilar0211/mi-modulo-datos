from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import uuid
from typing import List

CATEGORIES = {"Food", "Travel", "Electronics", "Health", "Entertainment", "Retail", "Transport", "Education", "Services", "Other"}
COUNTRIES = {"MX", "CO", "BR", "AR", "CL", "PE", "EC", "VE", "BO", "PY", "UY", "CR", "GT", "PA", "DO"}
STATUSES = {"completed", "failed", "pending"}

class TransactionModel(BaseModel):
    transaction_id: str
    timestamp: datetime
    user_id: int = Field(..., ge=1, le=50000)
    merchant_id: int = Field(..., ge=1, le=10000)
    amount: float = Field(..., ge=0.01, le=5000.00)
    category: str
    country_code: str
    status: str

    @field_validator('transaction_id')
    def validate_uuid(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("transaction_id must be a valid UUID4")
        return v

    @field_validator('category')
    def validate_category(cls, v):
        if v not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        return v

    @field_validator('country_code')
    def validate_country_code(cls, v):
        if v not in COUNTRIES:
            raise ValueError(f"country_code must be one of {COUNTRIES}")
        return v

    @field_validator('status')
    def validate_status(cls, v):
        if v not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        return v

class TransactionBatchRequest(BaseModel):
    transactions: List[TransactionModel]

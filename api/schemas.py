from datetime import datetime

from pydantic import BaseModel


class ResearchRequest(BaseModel):
    query: str


class ResearchResponse(BaseModel):
    query: str
    report: str
    sub_questions: list[str]
    extracted_facts: list[str]
    errors: list[str]
    retry_count: int


class HistoryItem(BaseModel):
    id: int
    query: str
    report: str
    sub_questions: list[str]
    facts: list[str]
    created_at: datetime

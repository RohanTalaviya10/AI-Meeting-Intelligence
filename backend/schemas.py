from typing import List, Optional
from pydantic import BaseModel


class ActionItem(BaseModel):
    task: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    normalized_deadline: Optional[str] = None
    is_overdue: bool = False
    priority: Optional[str] = "Medium"
    status: Optional[str] = "Pending"
    confidence: float = 0.9


class MeetingAnalysis(BaseModel):
    summary: str
    decisions: List[str] = []
    action_items: List[ActionItem] = []
    risks_blockers: List[str] = []
    unresolved_items: List[str] = []
    participants: List[str] = []
    confidence_score: float = 0.92


class MeetingResponse(BaseModel):
    id: int
    filename: str
    file_size_bytes: int
    created_at: str
    transcript: str
    analysis: MeetingAnalysis


class MeetingListItem(BaseModel):
    id: int
    filename: str
    file_size_bytes: int
    created_at: str
    summary: Optional[str] = None
    action_item_count: int = 0
    decision_count: int = 0


class QueryRequest(BaseModel):
    query: str


class RetrievedChunk(BaseModel):
    chunk_index: int
    speaker: Optional[str] = None
    text: str
    similarity: float


class QueryResponse(BaseModel):
    meeting_id: int
    query: str
    answer: str
    retrieved_chunks: List[RetrievedChunk] = []

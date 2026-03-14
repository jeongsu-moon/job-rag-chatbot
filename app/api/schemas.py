from pydantic import BaseModel


class SourceInfo(BaseModel):
    company: str
    title: str
    relevance_score: float | None = None


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    use_reranker: bool = True
    full_scan: bool = False
    history: list[ChatMessage] = []


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceInfo]
    processing_time: float


class HealthResponse(BaseModel):
    status: str
    llm_mode: str
    total_documents: int

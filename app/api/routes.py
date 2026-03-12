import time

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    QueryRequest,
    QueryResponse,
    SourceInfo,
    HealthResponse,
)
from app.core.config import settings

router = APIRouter()

# 전역 RAG 체인 (lifespan에서 초기화)
rag_chain = None
vector_store = None


def get_rag_chain():
    if rag_chain is None:
        raise HTTPException(status_code=503, detail="RAG 체인이 아직 초기화되지 않았습니다.")
    return rag_chain


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """질문 처리: 검색 → (리랭킹) → LLM 답변 생성"""
    chain = get_rag_chain()
    start = time.time()

    result = chain.invoke(
        question=request.question,
        top_k=request.top_k,
        use_reranker=request.use_reranker,
    )

    sources = [
        SourceInfo(
            company=s["company"],
            title=s["title"],
            relevance_score=s.get("relevance_score"),
        )
        for s in result["sources"]
    ]

    return QueryResponse(
        answer=result["answer"],
        sources=sources,
        processing_time=round(time.time() - start, 2),
    )


@router.get("/health", response_model=HealthResponse)
async def health():
    """서버 상태 확인"""
    doc_count = 0
    if vector_store:
        try:
            db = vector_store.load_store()
            doc_count = db._collection.count()
        except Exception:
            pass

    return HealthResponse(
        status="ok" if rag_chain else "initializing",
        llm_mode=settings.LLM_MODE,
        total_documents=doc_count,
    )


@router.post("/ingest")
async def ingest():
    """새 데이터 인제스트 트리거"""
    global rag_chain, vector_store

    from app.ingestion.loader import JobLoader
    from app.rag.chunker import JobChunker
    from app.core.embeddings import VectorStore
    from app.rag.retriever import HybridRetriever
    from app.rag.reranker import SimpleReranker
    from app.rag.chain import RAGChain

    loader = JobLoader()
    docs = loader.to_documents()

    chunker = JobChunker(strategy="semantic", chunk_size=settings.CHUNK_SIZE)
    chunks = chunker.chunk(docs)

    vector_store = VectorStore()
    vector_store.create_store(chunks)
    vectorstore = vector_store.load_store()

    retriever = HybridRetriever(vectorstore=vectorstore, documents=chunks)
    reranker = SimpleReranker()
    rag_chain = RAGChain(retriever=retriever, reranker=reranker)

    return {"status": "ok", "documents": len(docs), "chunks": len(chunks)}


@router.get("/stats")
async def stats():
    """현재 DB 통계"""
    if vector_store is None:
        return {"status": "no_data", "total_chunks": 0}

    try:
        db = vector_store.load_store()
        count = db._collection.count()
        return {"status": "ok", "total_chunks": count}
    except Exception as e:
        return {"status": "error", "message": str(e)}

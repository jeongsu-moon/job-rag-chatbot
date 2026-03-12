from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 RAG 체인 초기화."""
    print("RAG 체인 초기화 중...")

    from app.ingestion.loader import JobLoader
    from app.rag.chunker import JobChunker
    from app.core.embeddings import VectorStore
    from app.rag.retriever import HybridRetriever
    from app.rag.reranker import SimpleReranker
    from app.rag.chain import RAGChain

    # 문서 로드 + 청킹 (BM25용)
    loader = JobLoader()
    docs = loader.to_documents()
    chunker = JobChunker(strategy="semantic", chunk_size=settings.CHUNK_SIZE)
    chunks = chunker.chunk(docs)

    # 벡터스토어 로드 (이미 인제스트된 DB 사용)
    store = VectorStore()
    vectorstore = store.load_store()

    # RAG 체인 구성
    retriever = HybridRetriever(vectorstore=vectorstore, documents=chunks)
    reranker = SimpleReranker()

    routes.rag_chain = RAGChain(retriever=retriever, reranker=reranker)
    routes.vector_store = store

    print(f"RAG 체인 초기화 완료 (문서: {len(docs)}, 청크: {len(chunks)})")
    yield
    print("서버 종료")


app = FastAPI(
    title="Job RAG Chatbot",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

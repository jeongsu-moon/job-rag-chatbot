from typing import Generator

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from app.core.config import settings
from app.rag.retriever import HybridRetriever
from app.rag.reranker import SimpleReranker


SYSTEM_PROMPT = """당신은 채용 공고 분석 전문가입니다.
아래 검색된 채용 공고 정보를 바탕으로 사용자의 질문에 정확하게 답변하세요.

검색된 채용 공고:
{context}

질문: {question}

규칙:
1. 검색된 정보에 기반해서만 답변하세요. 추측하지 마세요.
2. 관련 공고가 없으면 "검색된 공고 중에는 관련 정보가 없습니다"라고 답하세요.
3. 가능하면 회사명, 구체적 요구사항 등 구체적 정보를 포함하세요.
4. 여러 공고가 관련되면 비교하여 정리해주세요.
5. 답변은 한국어로 하세요."""


def get_llm():
    if settings.LLM_MODE == "api":
        return ChatOpenAI(
            model=settings.LLM_MODEL_API,
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=0,
        )
    # local 모드: Ollama
    from langchain_community.chat_models import ChatOllama
    return ChatOllama(model=settings.LLM_MODEL_LOCAL, temperature=0)


class RAGChain:
    """LangChain LCEL 기반 RAG 체인."""

    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: SimpleReranker | None = None,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.llm = get_llm()

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
        ])
        self.chain = prompt | self.llm | StrOutputParser()

    def _retrieve_and_rerank(
        self, question: str, top_k: int = 5, use_reranker: bool = True
    ) -> list[tuple[Document, float]]:
        """검색 + 리랭킹 수행, (Document, score) 리스트 반환."""
        if use_reranker and self.reranker:
            docs = self.retriever.retrieve(question, k=top_k * 2)
            reranked = self.reranker.rerank(question, docs, top_k=top_k)
            return reranked
        else:
            return self.retriever.retrieve_with_scores(question, k=top_k)

    def _format_context(self, doc_scores: list[tuple[Document, float]]) -> str:
        """문서 리스트를 컨텍스트 문자열로 변환."""
        parts = []
        for i, (doc, _) in enumerate(doc_scores, 1):
            parts.append(f"[공고 {i}]\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)

    def _build_sources(
        self, doc_scores: list[tuple[Document, float]]
    ) -> list[dict]:
        """참조 문서 정보를 추출."""
        sources = []
        seen = set()
        for doc, score in doc_scores:
            company = doc.metadata.get("company", "")
            title = doc.metadata.get("title", "")
            key = f"{company}-{title}"
            if key in seen:
                continue
            seen.add(key)
            sources.append({
                "company": company,
                "title": title,
                "relevance_score": round(score, 4),
            })
        return sources

    def invoke(
        self, question: str, top_k: int = 5, use_reranker: bool = True
    ) -> dict:
        """RAG 체인 실행. 답변 + 소스 + 컨텍스트 반환."""
        doc_scores = self._retrieve_and_rerank(question, top_k, use_reranker)
        context = self._format_context(doc_scores)
        sources = self._build_sources(doc_scores)

        answer = self.chain.invoke({"context": context, "question": question})

        return {
            "answer": answer,
            "sources": sources,
            "context": context,
        }

    def stream(
        self, question: str, top_k: int = 5, use_reranker: bool = True
    ) -> Generator[str, None, None]:
        """스트리밍 응답. Streamlit에서 사용."""
        doc_scores = self._retrieve_and_rerank(question, top_k, use_reranker)
        context = self._format_context(doc_scores)

        for chunk in self.chain.stream({"context": context, "question": question}):
            yield chunk


if __name__ == "__main__":
    from app.core.embeddings import VectorStore
    from app.ingestion.loader import JobLoader
    from app.rag.chunker import JobChunker

    # 준비
    loader = JobLoader()
    docs = loader.to_documents()
    chunker = JobChunker(strategy="semantic", chunk_size=500)
    chunks = chunker.chunk(docs)

    store = VectorStore()
    vectorstore = store.load_store()

    retriever = HybridRetriever(vectorstore=vectorstore, documents=chunks)
    reranker = SimpleReranker()
    chain = RAGChain(retriever=retriever, reranker=reranker)

    # 테스트
    question = "Python 백엔드 개발자 채용 공고 알려줘"
    print(f'질문: "{question}"\n')
    result = chain.invoke(question)
    print(f"답변:\n{result['answer']}\n")
    print("참조 공고:")
    for s in result["sources"]:
        print(f"  - {s['company']} / {s['title']} (점수: {s['relevance_score']})")

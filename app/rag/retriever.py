from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from app.core.embeddings import VectorStore


class HybridRetriever:
    """벡터 검색(의미 유사도)과 BM25(키워드 매칭)를 결합하는 하이브리드 검색기."""

    def __init__(
        self,
        vectorstore: Chroma,
        documents: list[Document],
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
        k: int = 5,
    ):
        self.k = k
        self.vectorstore = vectorstore
        self.documents = documents
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

        # 벡터 검색기
        self.vector_retriever = vectorstore.as_retriever(
            search_kwargs={"k": 10}
        )

        # BM25 검색기
        self.bm25_retriever = BM25Retriever.from_documents(documents, k=10)

    def retrieve(self, query: str, k: int | None = None) -> list[Document]:
        """하이브리드 검색 실행, 상위 k개 반환."""
        top_k = k or self.k

        # 각 검색기에서 결과 가져오기
        vector_results = self.vector_retriever.invoke(query)
        bm25_results = self.bm25_retriever.invoke(query)

        # RRF(Reciprocal Rank Fusion)로 점수 결합
        doc_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}

        for rank, doc in enumerate(vector_results):
            key = doc.page_content
            rrf_score = self.vector_weight / (rank + 1)
            doc_scores[key] = doc_scores.get(key, 0) + rrf_score
            doc_map[key] = doc

        for rank, doc in enumerate(bm25_results):
            key = doc.page_content
            rrf_score = self.bm25_weight / (rank + 1)
            doc_scores[key] = doc_scores.get(key, 0) + rrf_score
            doc_map[key] = doc

        # 점수 내림차순 정렬
        sorted_keys = sorted(doc_scores, key=doc_scores.get, reverse=True)
        return [doc_map[key] for key in sorted_keys[:top_k]]

    def retrieve_with_scores(
        self, query: str, k: int | None = None
    ) -> list[tuple[Document, float]]:
        """검색 결과 + 스코어 반환 (디버깅/평가용)."""
        top_k = k or self.k

        vector_results = self.vector_retriever.invoke(query)
        bm25_results = self.bm25_retriever.invoke(query)

        doc_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}

        for rank, doc in enumerate(vector_results):
            key = doc.page_content
            rrf_score = self.vector_weight / (rank + 1)
            doc_scores[key] = doc_scores.get(key, 0) + rrf_score
            doc_map[key] = doc

        for rank, doc in enumerate(bm25_results):
            key = doc.page_content
            rrf_score = self.bm25_weight / (rank + 1)
            doc_scores[key] = doc_scores.get(key, 0) + rrf_score
            doc_map[key] = doc

        sorted_keys = sorted(doc_scores, key=doc_scores.get, reverse=True)
        return [(doc_map[key], doc_scores[key]) for key in sorted_keys[:top_k]]


if __name__ == "__main__":
    from app.ingestion.loader import JobLoader
    from app.rag.chunker import JobChunker

    # 문서 로드 및 청킹
    loader = JobLoader()
    docs = loader.to_documents()
    chunker = JobChunker(strategy="semantic", chunk_size=500)
    chunks = chunker.chunk(docs)

    # 벡터스토어 로드
    store = VectorStore()
    vectorstore = store.load_store()

    # 하이브리드 검색
    retriever = HybridRetriever(vectorstore=vectorstore, documents=chunks)

    query = "Python 백엔드 개발자"
    print(f'검색: "{query}"\n')

    results = retriever.retrieve_with_scores(query, k=5)
    for doc, score in results:
        company = doc.metadata.get("company", "")
        title = doc.metadata.get("title", "")
        section = doc.metadata.get("section", "")
        print(f"  [{score:.4f}] {company} - {title} ({section})")
        print(f"    {doc.page_content[:80]}...")
        print()

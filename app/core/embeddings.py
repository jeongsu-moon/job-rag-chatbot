from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import settings


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
    )


class VectorStore:
    """ChromaDB 기반 벡터 저장소를 관리합니다."""

    COLLECTION_NAME = "job_postings"

    def __init__(self):
        self.embeddings = get_embeddings()
        self.persist_dir = settings.CHROMA_PERSIST_DIR
        self._store: Chroma | None = None

    @staticmethod
    def _sanitize_metadata(documents: list[Document]) -> list[Document]:
        """ChromaDB가 허용하지 않는 메타데이터(빈 리스트 등)를 정리합니다."""
        for doc in documents:
            keys_to_fix = [
                k for k, v in doc.metadata.items()
                if isinstance(v, list) and len(v) == 0
            ]
            for k in keys_to_fix:
                doc.metadata[k] = ""
        return documents

    def create_store(self, documents: list[Document]) -> Chroma:
        """문서를 임베딩하여 ChromaDB에 저장합니다."""
        documents = self._sanitize_metadata(documents)
        self._store = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=self.persist_dir,
            collection_name=self.COLLECTION_NAME,
        )
        return self._store

    def load_store(self) -> Chroma:
        """이미 저장된 ChromaDB를 로드합니다."""
        self._store = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            collection_name=self.COLLECTION_NAME,
        )
        return self._store

    def similarity_search(
        self, query: str, k: int = 5
    ) -> list[tuple[Document, float]]:
        """유사도 검색 + 스코어를 반환합니다."""
        if self._store is None:
            self.load_store()
        return self._store.similarity_search_with_score(query, k=k)

    def get_all_documents(self) -> list[Document]:
        """ChromaDB에 저장된 모든 문서를 반환합니다."""
        if self._store is None:
            self.load_store()
        result = self._store._collection.get(include=["documents", "metadatas"])
        docs = []
        for content, metadata in zip(result["documents"], result["metadatas"]):
            docs.append(Document(page_content=content, metadata=metadata or {}))
        return docs

    def add_documents(self, documents: list[Document]):
        """기존 DB에 문서를 추가합니다."""
        if self._store is None:
            self.load_store()
        documents = self._sanitize_metadata(documents)
        self._store.add_documents(documents)


if __name__ == "__main__":
    store = VectorStore()
    db = store.load_store()
    print(f"컬렉션: {store.COLLECTION_NAME}")
    print(f"저장 경로: {store.persist_dir}")
    print(f"저장된 문서 수: {db._collection.count()}")

import re

from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings


RERANK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 채용 공고 검색 결과의 관련성을 평가하는 전문가입니다."),
    ("human", """아래 질문과 문서를 보고, 문서가 질문에 얼마나 관련 있는지 1~10점으로 평가해주세요.
숫자만 답변하세요. 다른 설명은 하지 마세요.

[질문]
{query}

[문서]
{document}

점수:"""),
])


class SimpleReranker:
    """LLM을 사용하여 검색 결과를 질문 관련성 기준으로 재정렬합니다."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL_API,
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=0,
        )
        self.chain = RERANK_PROMPT | self.llm

    def _score_document(self, query: str, doc: Document) -> float:
        """단일 문서의 관련성 점수를 반환합니다."""
        try:
            response = self.chain.invoke({
                "query": query,
                "document": doc.page_content[:500],
            })
            score = float(re.search(r"\d+", response.content).group())
            return min(max(score, 1), 10)  # 1~10 범위 보장
        except Exception:
            return 0.0

    def rerank(
        self, query: str, documents: list[Document], top_k: int = 3
    ) -> list[tuple[Document, float]]:
        """문서를 LLM 관련성 점수로 재정렬하여 반환합니다."""
        scored = []
        for doc in documents:
            score = self._score_document(query, doc)
            scored.append((doc, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


if __name__ == "__main__":
    from app.core.embeddings import VectorStore

    store = VectorStore()
    results = store.similarity_search("Python 백엔드 개발자", k=5)
    docs = [doc for doc, _ in results]

    reranker = SimpleReranker()
    query = "Python 백엔드 개발자"
    print(f'리랭킹: "{query}"\n')

    reranked = reranker.rerank(query, docs, top_k=3)
    for doc, score in reranked:
        company = doc.metadata.get("company", "")
        title = doc.metadata.get("title", "")
        print(f"  [{score:.0f}점] {company} - {title}")
        print(f"    {doc.page_content[:80]}...")
        print()

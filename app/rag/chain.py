from typing import Generator

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage

from app.core.config import settings
from app.rag.retriever import HybridRetriever
from app.rag.reranker import SimpleReranker


SYSTEM_PROMPT = """당신은 채용 시장 분석 전문가 AI입니다. 아래 실제 채용 공고 데이터를 바탕으로 질문에 답합니다.

채용 공고 데이터 (총 {total_jobs}개 공고):
{context}

질문: {question}

---

**답변 방식:**

질문이 기술 스택/채용 트렌드/직무 분석에 관한 것이라면, 반드시 아래 형식을 그대로 사용하세요 (마커 문자 없이 내용만 출력):

📊 [직군명] 공고 {total_jobs}개 분석 결과

🔥 필수 기술 TOP 10 (질문에 다른 숫자가 있어도 항상 10개 기준으로 출력)
1. [기술명] — [N]개 공고 ([X]%) [진행막대]
2. [기술명] — [N]개 공고 ([X]%) [진행막대]
(최대 10위까지. 실제 기술이 없으면 해당 순위 생략. "데이터 없음" 같은 더미 항목 절대 금지)

⭐ 우대 기술 (있으면 유리!)
- [기술명] ([X]%) — [한 줄 맥락]
- [기술명] ([X]%) — [한 줄 맥락]
(우대 기술이 없으면 "데이터 없음")

💡 취준생을 위한 인사이트
- [인사이트 1]
- [인사이트 2]
- [인사이트 3]

진행막대 계산법 (반드시 준수):
- 항상 █와 ░ 합쳐서 정확히 20자
- 채울 칸 수 F = round(X / 5)
- 막대 = F개의 █ + (20-F)개의 ░
- 검증 표 (암기):
  100% → F=20 → ████████████████████
   75% → F=15 → ███████████████░░░░░
   61% → F=12 → ████████████░░░░░░░░
   50% → F=10 → ██████████░░░░░░░░░░
   35% → F=7  → ███████░░░░░░░░░░░░░
   25% → F=5  → █████░░░░░░░░░░░░░░░
   10% → F=2  → ██░░░░░░░░░░░░░░░░░░

카운트 규칙:
- 필수: 각 공고의 "자격요건" 섹션에 명시된 기술
- 우대: 각 공고의 "우대사항" 섹션에 명시된 기술
- N = 해당 기술이 등장한 공고 수, X% = round(N / {total_jobs} * 100)
- 반드시 실제 공고를 하나씩 세어서 표기하세요. 추정 금지.
- 기술이 아닌 것은 제외: "백엔드 개발", "프론트엔드 개발", "서버 개발" 같은 직군명·직무명은 기술로 카운트하지 마세요.

질문이 특정 기술의 개념/설명을 묻는 것이라면 (예: "Python이 뭐야?", "Docker 설명해줘", "REST API란?"):
- 통계 형식(📊/🔥) 절대 사용 금지
- 아래 형식으로 답하세요:

**[기술명]이란?**
[2~3문장 개념 설명]

**채용 시장에서의 위치**
[공고 데이터를 근거로 — 몇 개 공고에서 요구되는지, 어떤 직군에서 주로 쓰이는지]

**한 줄 요약**
[취준생 관점에서 이 기술을 배워야 할 이유]

공통 규칙:
- 공고 데이터에 없는 내용은 지어내지 마세요.
- 관련 공고가 없으면 "해당 직군 공고가 없습니다"라고 답하세요.
- 답변은 한국어로 작성하세요."""


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


def _to_lc_messages(history: list[dict] | None) -> list:
    """프론트에서 받은 history를 LangChain 메시지 객체로 변환."""
    if not history:
        return []
    result = []
    for msg in history[-6:]:  # 최근 3턴(6개)만 유지
        if msg.get("role") == "user":
            result.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            result.append(AIMessage(content=msg["content"]))
    return result


class RAGChain:
    """LangChain LCEL 기반 RAG 체인."""

    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: SimpleReranker | None = None,
        vector_store=None,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.vector_store = vector_store
        self.llm = get_llm()

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ])
        self.chain = prompt | self.llm | StrOutputParser()

    def _retrieve_and_rerank(
        self, question: str, top_k: int = 5, use_reranker: bool = True,
        min_rerank_score: float = 3.0,
    ) -> list[tuple[Document, float]]:
        """검색 + 리랭킹 수행, (Document, score) 리스트 반환."""
        if use_reranker and self.reranker:
            docs = self.retriever.retrieve(question, k=top_k * 2)
            reranked = self.reranker.rerank(question, docs, top_k=top_k)
            # 관련도 낮은 문서 제거 (1~10점 기준, 3점 미만 제외)
            filtered = [(doc, score) for doc, score in reranked if score >= min_rerank_score]
            return filtered if filtered else reranked[:1]
        else:
            return self.retriever.retrieve_with_scores(question, k=top_k)

    def _format_context(self, doc_scores: list[tuple[Document, float]]) -> tuple[str, int]:
        """문서 리스트를 컨텍스트 문자열로 변환. (context, total_jobs) 반환."""
        parts = []
        seen: set[str] = set()
        job_num = 0
        for doc, _ in doc_scores:
            company = doc.metadata.get("company", "")
            title = doc.metadata.get("title", "")
            key = f"{company}-{title}"
            if key not in seen:
                seen.add(key)
                job_num += 1
                header = f"[공고 {job_num}] {company} — {title}"
            else:
                header = f"[공고 {job_num} 계속]"
            parts.append(f"{header}\n{doc.page_content}")
        return "\n\n---\n\n".join(parts), job_num

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

    # 질문에서 직군 키워드를 탐지하기 위한 매핑
    JOB_CATEGORY_KEYWORDS: dict[str, list[str]] = {
        "백엔드": ["백엔드", "backend", "back-end", "back end", "서버", "server", "spring", "django", "fastapi", "rails", "laravel"],
        "프론트엔드": ["프론트엔드", "프론트", "frontend", "front-end", "front end", "웹 개발", "web 개발", "react", "vue", "angular", "퍼블리"],
        "데이터": ["데이터 엔지니어", "데이터 사이언티스트", "data engineer", "data scientist", "ML엔지니어", "머신러닝", "machine learning", "데이터 분석"],
        "AI": ["ai ", "llm", "인공지능", "머신러닝 엔지니어", "ml engineer", "딥러닝", "deep learning", "nlp", "computer vision"],
        "DevOps": ["devops", "sre", "인프라", "클라우드", "cloud", "platform engineer", "시스템 엔지니어"],
        "모바일": ["모바일", "ios", "android", "앱 개발", "flutter", "react native"],
        "풀스택": ["풀스택", "full stack", "fullstack", "full-stack"],
        "임베디드": ["임베디드", "embedded", "펌웨어", "firmware"],
    }

    # 경력 수준 키워드 → 경력 필드 매칭 패턴
    EXPERIENCE_LEVEL_KEYWORDS: dict[str, list[str]] = {
        "junior": ["주니어", "신입", "인턴", "junior", "entry"],
        "senior": ["시니어", "senior", "중급", "고급"],
    }

    def _extract_job_category(self, question: str) -> str | None:
        """질문에서 직군 카테고리 키워드를 추출합니다."""
        q = question.lower()
        for category, triggers in self.JOB_CATEGORY_KEYWORDS.items():
            if any(t in q for t in triggers):
                return category
        return None

    def _extract_experience_level(self, question: str) -> str | None:
        """질문에서 경력 수준(junior/senior) 키워드를 추출합니다."""
        q = question.lower()
        for level, triggers in self.EXPERIENCE_LEVEL_KEYWORDS.items():
            if any(t in q for t in triggers):
                return level
        return None

    # 설명/개념 질문 패턴 — 이런 질문은 full_scan 대신 RAG 사용
    EXPLANATION_PATTERNS = [
        "뭐야", "뭔가요", "무엇인가요", "뭐예요", "뭐에요",
        "이란", "이란?", "란?", "란 뭐", "는 뭐", "가 뭐",
        "설명해줘", "설명해 줘", "가르쳐줘",
        "어떤 기술", "어떤 것", "왜 필요", "왜 중요",
        "어떻게 써", "어떻게 사용", "차이가 뭐", "차이점",
        "어떤 언어", "어떤 프레임워크",
    ]

    def _is_explanation_question(self, question: str) -> bool:
        """기술 개념 설명이나 단순 질문인지 판별합니다."""
        q = question.lower()
        return any(p in q for p in self.EXPLANATION_PATTERNS)

    # 통계/분석 질문 패턴 — 전체 데이터가 필요한 질문
    ANALYSIS_PATTERNS = [
        "top", "상위", "순위", "몇 위",
        "가장 많이", "가장 많은", "제일 많이",
        "비율", "몇 %", "퍼센트",
        "분석", "트렌드", "통계",
        "필수 기술", "요구 기술", "기술 스택 분석",
        "차이 정리", "비교 분석",
    ]

    def _is_analysis_question(self, question: str) -> bool:
        """통계/트렌드 분석 질문인지 판별합니다. Full Scan이 필요한 질문."""
        q = question.lower()
        return any(p in q for p in self.ANALYSIS_PATTERNS)

    def _full_scan_docs(self, keywords: list[str] | None = None, experience_level: str | None = None) -> list[tuple[Document, float]]:
        """원본 JSON에서 공고를 직접 읽어 반환. keywords가 있으면 title로 필터링."""
        import json

        data_path = "data/sample_jobs.json"
        try:
            with open(data_path, encoding="utf-8") as f:
                jobs = json.load(f)
        except FileNotFoundError:
            raise ValueError(f"{data_path} 파일을 찾을 수 없습니다.")

        def to_str(v) -> str:
            if isinstance(v, list):
                return "\n".join(f"  - {i}" for i in v)
            return str(v) if v else ""

        # 경력 수준 필터 패턴
        junior_patterns = ["0~", "1~", "신입", "인턴", "주니어"]
        senior_patterns = ["5~", "7~", "10~", "시니어", "senior", "고급"]

        result: list[tuple[Document, float]] = []
        for job in jobs:
            title = job.get("title", "")
            experience = job.get("experience", "")

            if keywords:
                title_lower = title.lower()
                if not any(kw.lower() in title_lower for kw in keywords):
                    continue

            if experience_level == "junior" and not any(p in experience for p in junior_patterns):
                continue
            if experience_level == "senior" and not any(p in experience for p in senior_patterns):
                continue

            tech_stack = ", ".join(job.get("tech_stack", []) if isinstance(job.get("tech_stack"), list) else [])
            content = (
                f"회사: {job.get('company', '')}\n"
                f"직무: {job.get('title', '')}\n"
                f"경력: {job.get('experience', '')}\n"
                f"고용형태: {job.get('job_type', '')}\n"
                f"기술스택: {tech_stack}\n"
                f"자격요건:\n{to_str(job.get('requirements', ''))}\n"
                f"우대사항:\n{to_str(job.get('preferred', ''))}"
            )
            doc = Document(
                page_content=content,
                metadata={"company": job.get("company", ""), "title": title},
            )
            result.append((doc, 1.0))
        return result

    def invoke(
        self, question: str, top_k: int = 5, use_reranker: bool = True,
        full_scan: bool = False, history: list[dict] | None = None,
    ) -> dict:
        """RAG 체인 실행. 답변 + 소스 + 컨텍스트 반환."""
        category = self._extract_job_category(question)
        if full_scan and (category or self._is_analysis_question(question)):
            # 통계/분석 → Full Scan (정확한 카운팅을 위해 전체 데이터 필요)
            keywords = self.JOB_CATEGORY_KEYWORDS.get(category) if category else None
            experience_level = self._extract_experience_level(question)
            docs = self._full_scan_docs(keywords=keywords, experience_level=experience_level)
            if not keywords and not experience_level and len(docs) > 80:
                doc_scores = self._retrieve_and_rerank(question, top_k, use_reranker)
            else:
                doc_scores = docs
        else:
            # 특정 공고 검색 / 개념 설명 → RAG
            doc_scores = self._retrieve_and_rerank(question, top_k, use_reranker)
        context, total_jobs = self._format_context(doc_scores)
        sources = self._build_sources(doc_scores)

        lc_history = _to_lc_messages(history)
        answer = self.chain.invoke({
            "context": context, "question": question,
            "total_jobs": total_jobs, "history": lc_history,
        })

        return {
            "answer": answer,
            "sources": sources,
            "context": context,
        }

    def stream(
        self, question: str, top_k: int = 5, use_reranker: bool = True,
        full_scan: bool = False, history: list[dict] | None = None,
    ) -> Generator[str, None, None]:
        """스트리밍 응답."""
        category = self._extract_job_category(question)
        if full_scan and (category or self._is_analysis_question(question)):
            # 통계/분석 → Full Scan
            keywords = self.JOB_CATEGORY_KEYWORDS.get(category) if category else None
            experience_level = self._extract_experience_level(question)
            docs = self._full_scan_docs(keywords=keywords, experience_level=experience_level)
            if not keywords and not experience_level and len(docs) > 80:
                doc_scores = self._retrieve_and_rerank(question, top_k, use_reranker)
            else:
                doc_scores = docs
        else:
            # 특정 공고 검색 / 개념 설명 → RAG
            doc_scores = self._retrieve_and_rerank(question, top_k, use_reranker)
        context, total_jobs = self._format_context(doc_scores)

        lc_history = _to_lc_messages(history)
        for chunk in self.chain.stream({
            "context": context, "question": question,
            "total_jobs": total_jobs, "history": lc_history,
        }):
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

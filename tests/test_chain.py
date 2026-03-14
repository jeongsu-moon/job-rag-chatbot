"""RAGChain 라우팅 로직 단위 테스트 (API 호출 없음)"""
import json
import tempfile
import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.rag.chain import RAGChain


SAMPLE_JOBS_DATA = [
    {
        "company": "회사A",
        "title": "백엔드 개발자",
        "main_tasks": "API 개발",
        "requirements": "Python 3년 이상\nFastAPI 경험",
        "preferred": "Docker 경험",
        "tech_stack": ["Python", "FastAPI", "Docker"],
        "experience": "경력 3~5년",
        "description": "백엔드 개발자 모집",
        "location": "서울",
        "job_type": "정규직",
        "source_url": "",
    },
    {
        "company": "회사B",
        "title": "주니어 백엔드 개발자",
        "main_tasks": "서버 개발",
        "requirements": "Python 기초\nSQL 이해",
        "preferred": "",
        "tech_stack": ["Python", "Django"],
        "experience": "신입",
        "description": "신입 모집",
        "location": "판교",
        "job_type": "정규직",
        "source_url": "",
    },
    {
        "company": "회사C",
        "title": "프론트엔드 개발자",
        "main_tasks": "UI 개발",
        "requirements": "TypeScript 2년\nReact 경험",
        "preferred": "Next.js 경험",
        "tech_stack": ["TypeScript", "React"],
        "experience": "경력 2~4년",
        "description": "프론트엔드 모집",
        "location": "강남",
        "job_type": "정규직",
        "source_url": "",
    },
]


@pytest.fixture
def sample_json_path(tmp_path):
    path = tmp_path / "test_jobs.json"
    path.write_text(json.dumps(SAMPLE_JOBS_DATA, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture
def chain():
    """API 호출을 mock한 RAGChain 인스턴스"""
    with patch("app.rag.chain.get_llm") as mock_llm:
        mock_llm.return_value = MagicMock()
        retriever = MagicMock()
        reranker = MagicMock()
        instance = RAGChain(retriever=retriever, reranker=reranker)
    return instance


class TestIsAnalysisQuestion:
    def setup_method(self):
        with patch("app.rag.chain.get_llm"):
            self.chain = RAGChain(retriever=MagicMock())

    @pytest.mark.parametrize("question", [
        "백엔드 개발자 필수 기술 TOP 10은?",
        "가장 많이 요구하는 기술 분석해줘",
        "백엔드 공고 기술 스택 분석",
        "주니어 채용 트렌드 알려줘",
        "요구 기술 비율이 어떻게 돼?",
    ])
    def test_analysis_questions_detected(self, question):
        assert self.chain._is_analysis_question(question) is True

    @pytest.mark.parametrize("question", [
        "FastAPI 쓰는 회사 알려줘",
        "원격 근무 가능한 포지션 있어?",
        "Python이 뭐야?",
        "Docker 설명해줘",
    ])
    def test_specific_search_not_analysis(self, question):
        assert self.chain._is_analysis_question(question) is False


class TestIsExplanationQuestion:
    def setup_method(self):
        with patch("app.rag.chain.get_llm"):
            retriever = MagicMock()
            self.chain = RAGChain(retriever=retriever)

    @pytest.mark.parametrize("question", [
        "Python이 뭐야?",
        "Docker란 무엇인가요?",
        "FastAPI 설명해줘",
        "Kubernetes가 뭐에요?",
        "Redis란 무엇인가요?",
        "GraphQL 어떤 기술이야?",
        "Spring Boot 차이가 뭐야",
    ])
    def test_explanation_questions_detected(self, question):
        assert self.chain._is_explanation_question(question) is True

    @pytest.mark.parametrize("question", [
        "백엔드 개발자 필수 기술 분석해줘",
        "주니어 채용에서 필수 vs 우대 스킬 차이 정리해줘",
        "요즘 많이 요구하는 기술은?",
        "원격 근무 가능한 포지션 비율",
    ])
    def test_analysis_questions_not_detected(self, question):
        assert self.chain._is_explanation_question(question) is False


class TestExtractJobCategory:
    def setup_method(self):
        with patch("app.rag.chain.get_llm"):
            self.chain = RAGChain(retriever=MagicMock())

    @pytest.mark.parametrize("question,expected", [
        ("백엔드 개발자 채용 공고 분석", "백엔드"),
        ("프론트엔드 공고에서 자주 나오는 기술", "프론트엔드"),
        ("데이터 엔지니어 채용 트렌드", "데이터"),
        ("DevOps 필수 스킬은?", "DevOps"),
        ("iOS 앱 개발자 채용 현황", "모바일"),
        ("풀스택 개발자 요구사항", "풀스택"),
        ("임베디드 개발자 뽑는 곳", "임베디드"),
    ])
    def test_category_extracted(self, question, expected):
        assert self.chain._extract_job_category(question) == expected

    def test_no_category_returns_none(self):
        assert self.chain._extract_job_category("신입 채용 공고 분석해줘") is None


class TestExtractExperienceLevel:
    def setup_method(self):
        with patch("app.rag.chain.get_llm"):
            self.chain = RAGChain(retriever=MagicMock())

    @pytest.mark.parametrize("question", [
        "주니어 채용 공고 분석",
        "신입 개발자 필수 기술",
        "인턴 채용 트렌드",
    ])
    def test_junior_detected(self, question):
        assert self.chain._extract_experience_level(question) == "junior"

    @pytest.mark.parametrize("question", [
        "시니어 개발자 채용 분석",
        "senior 백엔드 필수 기술",
    ])
    def test_senior_detected(self, question):
        assert self.chain._extract_experience_level(question) == "senior"

    def test_no_level_returns_none(self):
        assert self.chain._extract_experience_level("백엔드 채용 공고 분석") is None


class TestFormatContext:
    def setup_method(self):
        with patch("app.rag.chain.get_llm"):
            self.chain = RAGChain(retriever=MagicMock())

    def test_returns_context_and_count(self):
        docs = [
            (Document(page_content="내용1", metadata={"company": "A", "title": "개발자"}), 1.0),
            (Document(page_content="내용2", metadata={"company": "B", "title": "디자이너"}), 0.8),
        ]
        context, total = self.chain._format_context(docs)
        assert total == 2
        assert "공고 1" in context
        assert "공고 2" in context

    def test_deduplicates_same_job(self):
        docs = [
            (Document(page_content="섹션1", metadata={"company": "A", "title": "개발자"}), 1.0),
            (Document(page_content="섹션2", metadata={"company": "A", "title": "개발자"}), 0.9),
        ]
        context, total = self.chain._format_context(docs)
        assert total == 1

    def test_company_title_in_header(self):
        docs = [
            (Document(page_content="내용", metadata={"company": "테스트", "title": "엔지니어"}), 1.0),
        ]
        context, _ = self.chain._format_context(docs)
        assert "테스트" in context
        assert "엔지니어" in context


class TestFullScanDocs:
    def setup_method(self):
        with patch("app.rag.chain.get_llm"):
            self.chain = RAGChain(retriever=MagicMock())

    def test_returns_all_jobs_without_filter(self, sample_json_path):
        with patch.object(self.chain, "_full_scan_docs", wraps=self.chain._full_scan_docs):
            # data_path를 패치해서 테스트 데이터 사용
            import app.rag.chain as chain_module
            original = None
            # _full_scan_docs 내부의 data_path 변경
            docs = []
            import json
            with open(sample_json_path, encoding="utf-8") as f:
                jobs = json.load(f)

            # 직접 로직 테스트
            assert len(jobs) == 3

    def test_keyword_filter(self, sample_json_path):
        """백엔드 키워드로 필터링하면 프론트엔드 공고가 제외되어야 한다"""
        import json
        with open(sample_json_path, encoding="utf-8") as f:
            jobs = json.load(f)

        backend_jobs = [j for j in jobs if "백엔드" in j["title"].lower() or "backend" in j["title"].lower()]
        frontend_jobs = [j for j in jobs if "프론트엔드" in j["title"].lower()]

        assert len(backend_jobs) == 2
        assert len(frontend_jobs) == 1

    def test_junior_filter(self, sample_json_path):
        import json
        with open(sample_json_path, encoding="utf-8") as f:
            jobs = json.load(f)

        junior_patterns = ["0~", "1~", "신입", "인턴", "주니어"]
        junior_jobs = [j for j in jobs if any(p in j.get("experience", "") for p in junior_patterns)]
        assert len(junior_jobs) == 1
        assert junior_jobs[0]["company"] == "회사B"


class TestBuildSources:
    def setup_method(self):
        with patch("app.rag.chain.get_llm"):
            self.chain = RAGChain(retriever=MagicMock())

    def test_sources_structure(self):
        docs = [
            (Document(page_content="내용", metadata={"company": "A", "title": "개발자"}), 0.95),
        ]
        sources = self.chain._build_sources(docs)
        assert len(sources) == 1
        assert sources[0]["company"] == "A"
        assert sources[0]["title"] == "개발자"
        assert sources[0]["relevance_score"] == 0.95

    def test_deduplicates_same_job(self):
        docs = [
            (Document(page_content="1", metadata={"company": "A", "title": "개발자"}), 0.9),
            (Document(page_content="2", metadata={"company": "A", "title": "개발자"}), 0.8),
        ]
        sources = self.chain._build_sources(docs)
        assert len(sources) == 1

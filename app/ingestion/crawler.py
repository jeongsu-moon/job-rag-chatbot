import json
import time
from pathlib import Path

import requests


class WantedCrawler:
    """원티드(wanted.co.kr) 채용 공고 크롤러.

    원티드 API를 통해 실제 채용 공고를 수집합니다.
    """

    BASE_URL = "https://www.wanted.co.kr/api/v4"
    LIST_URL = f"{BASE_URL}/jobs"
    DETAIL_URL = f"{BASE_URL}/jobs/{{job_id}}"

    # 원티드 tag_type_ids (직군 필터)
    TAG_DEVELOPMENT = 518  # 개발

    def __init__(self, delay: float = 1.0):
        """
        Args:
            delay: API 호출 간 대기 시간(초). 서버 부하 방지용.
        """
        self.delay = delay
        self.data: list[dict] = []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.wanted.co.kr/",
        })

    def _fetch_job_list(
        self,
        limit: int = 20,
        offset: int = 0,
        tag_type_ids: int = TAG_DEVELOPMENT,
        years: int = -1,
        locations: str = "all",
    ) -> list[int]:
        """채용 공고 목록에서 job ID 리스트를 가져옵니다."""
        params = {
            "country": "kr",
            "tag_type_ids": tag_type_ids,
            "job_sort": "job.latest_order",
            "locations": locations,
            "years": years,
            "limit": limit,
            "offset": offset,
        }
        resp = self.session.get(self.LIST_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [job["id"] for job in data.get("data", [])]

    def _fetch_job_detail(self, job_id: int) -> dict | None:
        """개별 채용 공고의 상세 정보를 가져옵니다."""
        url = self.DETAIL_URL.format(job_id=job_id)
        resp = self.session.get(url, timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠️ 공고 {job_id} 조회 실패 (HTTP {resp.status_code})")
            return None
        return resp.json().get("job")

    def _parse_job(self, job: dict) -> dict:
        """원티드 API 응답을 프로젝트 표준 포맷으로 변환합니다."""
        detail = job.get("detail", {})
        company = job.get("company", {})
        address = job.get("address", {})

        # 경력 범위 파싱
        annual_from = job.get("annual_from", 0)
        annual_to = job.get("annual_to", 0)
        if annual_from == 0 and annual_to == 0:
            experience = "신입"
        elif annual_to == 0:
            experience = f"경력 {annual_from}년 이상"
        else:
            experience = f"경력 {annual_from}~{annual_to}년"

        # 기술 스택 (skill_tags)
        skill_tags = job.get("skill_tags", [])
        tech_stack = [tag.get("title", "") for tag in skill_tags if tag.get("title")]

        return {
            "company": company.get("name", ""),
            "title": job.get("position", ""),
            "main_tasks": detail.get("main_tasks", ""),
            "requirements": detail.get("requirements", ""),
            "preferred": detail.get("preferred_points", ""),
            "tech_stack": tech_stack,
            "experience": experience,
            "description": detail.get("intro", ""),
            "location": address.get("full_location", ""),
            "job_type": "정규직",
            "source_url": f"https://www.wanted.co.kr/wd/{job.get('id', '')}",
        }

    def crawl(self, total: int = 30, tag_type_ids: int = TAG_DEVELOPMENT) -> list[dict]:
        """원티드에서 채용 공고를 크롤링합니다.

        Args:
            total: 수집할 공고 수.
            tag_type_ids: 직군 필터 ID (기본: 518=개발).

        Returns:
            수집된 채용 공고 리스트.
        """
        print(f"🔍 원티드에서 채용 공고 {total}개 수집 시작...")
        job_ids = []
        offset = 0
        batch_size = 20

        # 1단계: 공고 ID 목록 수집
        while len(job_ids) < total:
            limit = min(batch_size, total - len(job_ids))
            ids = self._fetch_job_list(
                limit=limit, offset=offset, tag_type_ids=tag_type_ids
            )
            if not ids:
                print(f"  더 이상 공고가 없습니다. (수집된 ID: {len(job_ids)}개)")
                break
            job_ids.extend(ids)
            offset += batch_size
            time.sleep(self.delay)

        print(f"  📋 공고 ID {len(job_ids)}개 수집 완료")

        # 2단계: 상세 정보 수집
        self.data = []
        for i, job_id in enumerate(job_ids, 1):
            print(f"  [{i}/{len(job_ids)}] 공고 {job_id} 상세 정보 수집 중...")
            job = self._fetch_job_detail(job_id)
            if job:
                parsed = self._parse_job(job)
                if parsed["company"] and parsed["title"]:
                    self.data.append(parsed)
            time.sleep(self.delay)

        print(f"✅ 총 {len(self.data)}개 채용 공고 수집 완료!")
        return self.data

    def save_to_json(self, output_path: str = "data/wanted_jobs.json"):
        """수집된 데이터를 JSON 파일로 저장합니다."""
        if not self.data:
            raise ValueError("저장할 데이터가 없습니다. crawl()을 먼저 실행하세요.")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"💾 {len(self.data)}개의 채용 공고가 {output_path}에 저장되었습니다.")


class JobCrawler:
    """채용 공고 크롤러. 샘플 데이터 생성 및 저장 기능을 제공합니다."""

    def __init__(self):
        self.data: list[dict] = []

    def generate_sample_data(self) -> list[dict]:
        """현실적인 한국 IT 채용 공고 샘플 30개를 생성합니다."""
        self.data = [
            # ── 백엔드 ──
            {
                "company": "넥스트웨어",
                "title": "백엔드 개발자 (Java/Spring)",
                "main_tasks": ["대규모 트래픽을 처리하는 백엔드 시스템 설계 및 개발", "마이크로서비스 아키텍처 전환 프로젝트 주도", "코드 리뷰 및 기술 문서 작성", "서비스 모니터링 및 장애 대응"],
                "requirements": ["Java 3년 이상", "Spring Boot 실무 경험", "RDBMS 설계 및 최적화 경험", "RESTful API 설계 경험"],
                "preferred": ["MSA 경험", "Kafka/RabbitMQ 사용 경험", "AWS 인프라 경험"],
                "tech_stack": ["Java", "Spring Boot", "MySQL", "Redis", "Docker", "AWS"],
                "experience": "경력 3~7년",
                "description": "넥스트웨어는 B2B SaaS 솔루션을 개발하는 스타트업으로, 빠르게 성장 중인 서비스의 백엔드 시스템을 설계하고 개발할 인재를 찾고 있습니다. 대규모 트래픽을 안정적으로 처리할 수 있는 확장 가능한 아키텍처를 설계하고, 마이크로서비스 전환 프로젝트를 주도하게 됩니다. 코드 리뷰와 기술 문서 작성 등 팀 협업에도 적극적으로 참여해 주세요.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            {
                "company": "핀테크랩스",
                "title": "서버 개발자 (Python/FastAPI)",
                "main_tasks": ["금융 서비스 API 설계 및 개발", "고성능 트랜잭션 처리 서버 개발", "PCI-DSS 보안 규정 준수 코드 작성", "결제 시스템 연동 및 운영"],
                "requirements": ["Python 2년 이상", "FastAPI 또는 Django 실무 경험", "PostgreSQL 사용 경험", "Git 기반 협업 경험"],
                "preferred": ["금융 도메인 이해", "비동기 프로그래밍 경험", "Docker/Kubernetes 활용 경험"],
                "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "Kubernetes"],
                "experience": "경력 2~5년",
                "description": "핀테크랩스는 차세대 결제 플랫폼을 만들고 있습니다. 안전하고 빠른 금융 서비스 API를 설계하고 운영하는 업무를 담당합니다. 초당 수천 건의 트랜잭션을 안정적으로 처리하는 고성능 서버를 개발하며, PCI-DSS 등 금융 보안 규정을 준수하는 코드를 작성합니다. 자율적인 업무 문화와 유연근무제를 지향합니다.",
                "location": "서울 여의도",
                "job_type": "정규직",
            },
            {
                "company": "클라우드브릿지",
                "title": "백엔드 엔지니어 (Go)",
                "main_tasks": ["Go 기반 고성능 백엔드 서비스 설계 및 구현", "클라우드 리소스 관리 API 개발", "대규모 인프라 데이터 수집/처리 파이프라인 구축", "gRPC 기반 내부 서비스 통신 개발"],
                "requirements": ["Go 언어 실무 1년 이상", "REST/gRPC API 개발 경험", "RDBMS 및 NoSQL 사용 경험", "리눅스 환경 익숙"],
                "preferred": ["분산 시스템 경험", "Terraform/IaC 경험", "성능 프로파일링 경험"],
                "tech_stack": ["Go", "gRPC", "PostgreSQL", "MongoDB", "Docker", "GCP"],
                "experience": "경력 1~4년",
                "description": "클라우드브릿지는 멀티 클라우드 관리 플랫폼을 개발하는 기업입니다. Go 언어 기반의 고성능 백엔드 서비스를 설계 및 구현하며, 클라우드 리소스 관리 API를 개발합니다. 대규모 인프라 데이터를 효율적으로 수집하고 처리하는 파이프라인을 만들게 됩니다. 기술 성장을 위한 사내 스터디와 컨퍼런스 참가를 적극 지원합니다.",
                "location": "서울 판교",
                "job_type": "정규직",
            },
            {
                "company": "커머스플러스",
                "title": "Node.js 백엔드 개발자",
                "main_tasks": ["주문 처리, 결제, 재고 관리 백엔드 개발", "실시간 스트리밍 연동 구매 시스템 개발", "데이터 기반 분석 API 개발", "기존 서비스 성능 최적화"],
                "requirements": ["Node.js/TypeScript 2년 이상", "NestJS 또는 Express 실무 경험", "MySQL/MongoDB 사용 경험", "CI/CD 파이프라인 이해"],
                "preferred": ["이커머스 도메인 경험", "GraphQL 경험", "Elasticsearch 사용 경험"],
                "tech_stack": ["TypeScript", "NestJS", "MySQL", "MongoDB", "Redis", "AWS"],
                "experience": "경력 2~5년",
                "description": "커머스플러스는 라이브 커머스 플랫폼을 운영하며 월간 100만 사용자를 보유하고 있습니다. 주문 처리, 결제, 재고 관리 등 핵심 백엔드 로직을 개발하고 최적화하는 업무를 맡게 됩니다. 실시간 스트리밍과 연동된 구매 시스템의 안정성을 보장하며, 데이터 기반 의사결정을 위한 분석 API도 개발합니다.",
                "location": "서울 성수동",
                "job_type": "정규직",
            },
            {
                "company": "메디컬AI",
                "title": "백엔드 개발자 (Django)",
                "main_tasks": ["의료 웹 플랫폼 백엔드 개발", "대용량 의료 영상 데이터 처리 파이프라인 구축", "환자 개인정보 보호 보안 체계 설계", "AI 모델 서빙 API 개발"],
                "requirements": ["Python/Django 3년 이상", "REST API 설계 및 개발 경험", "테스트 코드 작성 습관", "의료 데이터 보안 이해"],
                "preferred": ["HIPAA/PIPA 규정 이해", "Celery 비동기 처리 경험", "의료 도메인 경험"],
                "tech_stack": ["Python", "Django", "PostgreSQL", "Celery", "Redis", "AWS"],
                "experience": "경력 3~6년",
                "description": "메디컬AI는 AI 기반 의료 영상 분석 솔루션을 개발하는 헬스케어 스타트업입니다. 의료진이 사용하는 웹 플랫폼의 백엔드를 개발하며, 대용량 의료 영상 데이터를 안전하게 처리하는 파이프라인을 구축합니다. 환자 개인정보 보호를 위한 보안 체계를 설계하고, AI 모델 서빙을 위한 API를 개발합니다.",
                "location": "서울 역삼동",
                "job_type": "정규직",
            },
            # ── 프론트엔드 ──
            {
                "company": "디자인허브",
                "title": "프론트엔드 개발자 (React)",
                "main_tasks": ["디자인 협업 툴 프론트엔드 개발", "복잡한 UI 인터랙션 구현", "컴포넌트 기반 아키텍처 설계", "접근성 및 성능 최적화"],
                "requirements": ["React 2년 이상", "TypeScript 사용 경험", "상태 관리 라이브러리 경험 (Redux/Zustand)", "반응형 웹 개발 경험"],
                "preferred": ["Next.js 경험", "디자인 시스템 구축 경험", "Storybook 활용 경험"],
                "tech_stack": ["React", "TypeScript", "Next.js", "Zustand", "Tailwind CSS", "Figma"],
                "experience": "경력 2~5년",
                "description": "디자인허브는 SaaS 기반 디자인 협업 툴을 만들고 있습니다. 복잡한 UI 인터랙션을 부드럽게 구현하고, 디자이너와 긴밀히 협업하여 최고의 사용자 경험을 제공하는 프론트엔드를 개발합니다. 컴포넌트 기반 아키텍처를 설계하고, 접근성과 성능 최적화에 집중합니다. 주 4일 근무제를 시행 중입니다.",
                "location": "서울 합정동",
                "job_type": "정규직",
            },
            {
                "company": "에듀테크코리아",
                "title": "프론트엔드 엔지니어 (Vue.js)",
                "main_tasks": ["온라인 교육 플랫폼 프론트엔드 개발", "실시간 강의/퀴즈/과제 기능 구현", "영상 플레이어 커스터마이징", "모바일 환경 최적화"],
                "requirements": ["Vue.js 2년 이상", "HTML/CSS/JavaScript 숙련", "SPA 개발 경험", "REST API 연동 경험"],
                "preferred": ["Nuxt.js 경험", "모바일 웹 최적화 경험", "WebSocket 활용 경험"],
                "tech_stack": ["Vue.js", "Nuxt.js", "JavaScript", "SCSS", "Vuex", "Pinia"],
                "experience": "경력 2~4년",
                "description": "에듀테크코리아는 온라인 교육 플랫폼을 운영하며 50만 학습자에게 서비스를 제공합니다. 실시간 강의, 퀴즈, 과제 제출 등 다양한 학습 기능의 프론트엔드를 개발합니다. 영상 플레이어 커스터마이징, 실시간 채팅 UI, 학습 대시보드 등 풍부한 인터랙션을 구현하며, 모바일 환경 최적화도 담당합니다.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            {
                "company": "트래블메이트",
                "title": "프론트엔드 개발자 (React Native)",
                "main_tasks": ["iOS/Android 크로스 플랫폼 여행 앱 개발", "지도 기반 여행지 추천 화면 구현", "오프라인 모드 지원 및 푸시 알림 개발", "앱 성능 모니터링 및 최적화"],
                "requirements": ["React Native 1년 이상", "React 기반 개발 경험", "iOS/Android 앱 배포 경험", "상태 관리 패턴 이해"],
                "preferred": ["네이티브 모듈 브릿징 경험", "앱 성능 최적화 경험", "여행/O2O 도메인 경험"],
                "tech_stack": ["React Native", "TypeScript", "Redux Toolkit", "React Navigation", "Firebase"],
                "experience": "경력 1~3년",
                "description": "트래블메이트는 AI 기반 여행 추천 앱을 개발하는 스타트업입니다. React Native를 활용하여 iOS/Android 크로스 플랫폼 앱을 개발합니다. 지도 기반 여행지 추천, 일정 관리, 예약 기능 등 핵심 화면을 구현하며, 오프라인 모드 지원과 푸시 알림 시스템도 담당합니다. 자유로운 리모트 근무 가능합니다.",
                "location": "서울 마포구 (리모트 가능)",
                "job_type": "정규직",
            },
            {
                "company": "소셜임팩트",
                "title": "웹 프론트엔드 개발자",
                "main_tasks": ["공공 데이터 시각화 대시보드 개발", "D3.js 기반 차트 및 그래프 구현", "복잡한 필터링/검색 UI 개발", "웹 접근성 AA 수준 준수"],
                "requirements": ["JavaScript/TypeScript 3년 이상", "React 또는 Vue.js 숙련", "웹 접근성 표준 이해", "Git 기반 협업 경험"],
                "preferred": ["SSR/SSG 경험", "테스트 자동화 경험 (Jest/Cypress)", "UI/UX 감각"],
                "tech_stack": ["React", "TypeScript", "Next.js", "Jest", "Cypress", "GitHub Actions"],
                "experience": "경력 3~6년",
                "description": "소셜임팩트는 사회적 가치를 추구하는 IT 기업으로, 공공 데이터 시각화 플랫폼을 운영합니다. 대규모 데이터를 직관적으로 보여주는 대시보드와 차트를 개발하며, 웹 접근성 AA 수준을 준수합니다. D3.js를 활용한 데이터 시각화와 복잡한 필터링/검색 UI를 구현합니다. 사회적 의미 있는 프로젝트에 기여하고 싶은 분을 환영합니다.",
                "location": "서울 종로구",
                "job_type": "정규직",
            },
            # ── AI/ML ──
            {
                "company": "딥러닝연구소",
                "title": "ML 엔지니어",
                "main_tasks": ["대규모 언어 모델 파인튜닝 및 프롬프트 엔지니어링", "RAG 시스템 설계 및 구축", "ML 파이프라인 구축 및 운영 (학습~서빙)", "연구 결과의 프로덕션 적용"],
                "requirements": ["Python 3년 이상", "PyTorch 또는 TensorFlow 실무 경험", "ML 모델 학습/배포 경험", "선형대수/확률통계 기본 지식"],
                "preferred": ["NLP 또는 CV 프로젝트 경험", "MLOps 파이프라인 구축 경험", "논문 구현 경험"],
                "tech_stack": ["Python", "PyTorch", "Hugging Face", "MLflow", "Docker", "AWS SageMaker"],
                "experience": "경력 2~5년",
                "description": "딥러닝연구소는 자연어 처리 기술을 핵심으로 다양한 AI 솔루션을 개발합니다. 대규모 언어 모델의 파인튜닝과 프롬프트 엔지니어링을 수행하며, RAG 시스템과 같은 최신 기술을 활용한 제품을 만듭니다. 모델 학습부터 서빙까지 전체 ML 파이프라인을 관리하며, 연구 결과를 프로덕션에 적용하는 것을 목표로 합니다.",
                "location": "서울 선릉역",
                "job_type": "정규직",
            },
            {
                "company": "비전AI코리아",
                "title": "컴퓨터 비전 엔지니어",
                "main_tasks": ["실시간 영상 분석용 경량화 모델 연구", "엣지 디바이스 추론 엔진 최적화", "데이터 수집/라벨링/학습/배포 전 과정 참여", "고객사 현장 환경 맞춤 솔루션 개발"],
                "requirements": ["Python 2년 이상", "OpenCV/PyTorch 실무 경험", "이미지 분류/객체 탐지 프로젝트 경험", "딥러닝 모델 최적화 경험"],
                "preferred": ["ONNX/TensorRT 변환 경험", "엣지 디바이스 배포 경험", "관련 논문 투고 경험"],
                "tech_stack": ["Python", "PyTorch", "OpenCV", "ONNX", "TensorRT", "CUDA"],
                "experience": "경력 2~6년",
                "description": "비전AI코리아는 제조업 불량 검출 및 자율주행 보조 시스템을 개발합니다. 실시간 영상 분석을 위한 경량화 모델을 연구하고, 엣지 디바이스에서 동작하는 추론 엔진을 최적화합니다. 데이터 수집부터 라벨링, 학습, 배포까지 전 과정에 참여하며, 고객사의 현장 환경에 맞는 솔루션을 커스터마이징합니다.",
                "location": "경기 판교",
                "job_type": "정규직",
            },
            {
                "company": "챗봇팩토리",
                "title": "NLP 엔지니어",
                "main_tasks": ["한국어 대화형 AI 개발", "RAG 기반 질의응답 시스템 구축", "프롬프트 엔지니어링을 통한 응답 품질 개선", "LLM API 비용 최적화 전략 수립"],
                "requirements": ["Python 2년 이상", "Hugging Face Transformers 사용 경험", "텍스트 전처리/분석 경험", "한국어 NLP 이해"],
                "preferred": ["LLM 파인튜닝 경험", "RAG 시스템 구축 경험", "대화형 AI 개발 경험"],
                "tech_stack": ["Python", "Hugging Face", "LangChain", "FastAPI", "ChromaDB", "OpenAI API"],
                "experience": "경력 1~4년",
                "description": "챗봇팩토리는 기업용 AI 챗봇 솔루션을 제공합니다. 한국어에 특화된 대화형 AI를 개발하며, RAG 기반 질의응답 시스템을 구축합니다. 고객사 문서를 기반으로 정확한 답변을 생성하는 시스템을 만들고, 프롬프트 엔지니어링을 통해 응답 품질을 지속적으로 개선합니다. LLM API 비용 최적화 전략도 함께 수립합니다.",
                "location": "서울 삼성동",
                "job_type": "정규직",
            },
            {
                "company": "추천시스템즈",
                "title": "추천 알고리즘 엔지니어",
                "main_tasks": ["개인화 상품 추천 알고리즘 개발", "실시간 추천 서빙 시스템 운영", "A/B 테스트 설계 및 비즈니스 성과 측정", "사용자 행동 데이터 분석"],
                "requirements": ["Python 3년 이상", "추천 시스템 이론 및 실무 경험", "Spark/Pandas 대용량 데이터 처리 경험", "A/B 테스트 경험"],
                "preferred": ["실시간 추천 시스템 경험", "딥러닝 기반 추천 모델 경험", "이커머스 도메인 경험"],
                "tech_stack": ["Python", "Spark", "TensorFlow", "Redis", "Airflow", "AWS"],
                "experience": "경력 3~7년",
                "description": "추천시스템즈는 대형 이커머스 플랫폼에 개인화 추천 엔진을 제공합니다. 사용자 행동 데이터를 분석하여 상품 추천 알고리즘을 개발하고, 실시간 추천 서빙 시스템을 운영합니다. 협업 필터링, 콘텐츠 기반 필터링, 하이브리드 모델 등 다양한 접근법을 실험하며, A/B 테스트를 통해 비즈니스 성과를 측정합니다.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            # ── 데이터 엔지니어 ──
            {
                "company": "데이터웨이브",
                "title": "데이터 엔지니어",
                "main_tasks": ["ETL 파이프라인 설계 및 구축", "데이터 웨어하우스/데이터 레이크 구축", "데이터 품질 모니터링 시스템 운영", "분석팀 협업을 통한 비즈니스 인사이트 도출"],
                "requirements": ["Python/SQL 3년 이상", "ETL 파이프라인 구축 경험", "Airflow 또는 유사 워크플로우 도구 경험", "AWS/GCP 데이터 서비스 경험"],
                "preferred": ["Spark/Flink 실무 경험", "데이터 웨어하우스 설계 경험", "dbt 사용 경험"],
                "tech_stack": ["Python", "SQL", "Airflow", "Spark", "BigQuery", "dbt", "AWS"],
                "experience": "경력 3~6년",
                "description": "데이터웨이브는 데이터 기반 의사결정을 돕는 분석 플랫폼을 운영합니다. 다양한 소스에서 데이터를 수집하고, 정제하여 분석 가능한 형태로 가공하는 ETL 파이프라인을 설계합니다. 데이터 웨어하우스와 데이터 레이크를 구축하며, 데이터 품질 모니터링 시스템을 운영합니다. 분석팀과 협업하여 비즈니스 인사이트를 도출합니다.",
                "location": "서울 삼성동",
                "job_type": "정규직",
            },
            {
                "company": "로그분석코리아",
                "title": "데이터 파이프라인 엔지니어",
                "main_tasks": ["초당 수백만 건 로그 수집/처리 스트리밍 파이프라인 구축", "Kafka 클러스터 운영 및 관리", "Flink 기반 실시간 집계 및 이상 탐지 개발", "모니터링 대시보드 및 알림 시스템 개발"],
                "requirements": ["Python 또는 Scala 2년 이상", "Kafka 실무 경험", "실시간 스트리밍 처리 경험", "분산 시스템 이해"],
                "preferred": ["Flink/Spark Streaming 경험", "Elasticsearch 운영 경험", "Kubernetes 환경 배포 경험"],
                "tech_stack": ["Python", "Kafka", "Flink", "Elasticsearch", "Kubernetes", "Prometheus"],
                "experience": "경력 2~5년",
                "description": "로그분석코리아는 실시간 로그 분석 솔루션을 제공합니다. 초당 수백만 건의 로그 데이터를 안정적으로 수집하고 처리하는 스트리밍 파이프라인을 구축합니다. Kafka 클러스터를 운영하며 Flink를 활용한 실시간 집계 및 이상 탐지 로직을 개발합니다. 모니터링 대시보드와 알림 시스템도 함께 개발합니다.",
                "location": "서울 구로구",
                "job_type": "정규직",
            },
            {
                "company": "헬스데이터",
                "title": "데이터 엔지니어 (헬스케어)",
                "main_tasks": ["의료 데이터 표준화 및 연구용 데이터셋 구축", "비식별화 파이프라인 개발", "데이터 품질 관리 체계 수립", "병원/보험사 데이터 수집 및 정제"],
                "requirements": ["SQL 고급 수준", "Python 데이터 처리 경험", "데이터 모델링 경험", "의료 데이터 보안 이해"],
                "preferred": ["FHIR 표준 이해", "의료 도메인 경험", "데이터 거버넌스 경험"],
                "tech_stack": ["Python", "SQL", "Airflow", "PostgreSQL", "AWS Glue", "Redshift"],
                "experience": "경력 2~5년",
                "description": "헬스데이터는 의료 빅데이터 분석 플랫폼을 운영하는 헬스케어 전문 기업입니다. 병원 및 보험사에서 수집된 의료 데이터를 표준화하고, 연구용 데이터셋을 구축합니다. 환자 프라이버시를 보호하면서 데이터 활용성을 극대화하는 비식별화 파이프라인을 개발하며, 데이터 품질 관리 체계를 수립합니다.",
                "location": "서울 역삼동",
                "job_type": "정규직",
            },
            # ── DevOps / SRE ──
            {
                "company": "인프라테크",
                "title": "DevOps 엔지니어",
                "main_tasks": ["온프레미스→클라우드 마이그레이션 수행", "Kubernetes 기반 컨테이너 오케스트레이션 환경 구축", "GitOps 기반 배포 자동화 설계", "인프라 모니터링 체계 설계 및 장애 대응"],
                "requirements": ["리눅스 시스템 관리 3년 이상", "Docker/Kubernetes 실무 경험", "CI/CD 파이프라인 구축 경험", "IaC (Terraform/Ansible) 경험"],
                "preferred": ["AWS/GCP 아키텍처 설계 경험", "모니터링 시스템 구축 경험", "보안 자동화 경험"],
                "tech_stack": ["Kubernetes", "Docker", "Terraform", "AWS", "GitHub Actions", "Prometheus", "Grafana"],
                "experience": "경력 3~7년",
                "description": "인프라테크는 엔터프라이즈 클라우드 인프라 컨설팅을 제공합니다. 고객사의 온프레미스 환경을 클라우드로 마이그레이션하고, Kubernetes 기반 컨테이너 오케스트레이션 환경을 구축합니다. GitOps 기반 배포 자동화와 인프라 모니터링 체계를 설계하며, 장애 대응 프로세스를 수립합니다.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            {
                "company": "게임스튜디오K",
                "title": "SRE (Site Reliability Engineer)",
                "main_tasks": ["게임 서버 인프라 안정성 및 확장성 보장", "자동 스케일링 정책 수립 및 적용", "장애 자동 복구 시스템 구축", "SLI/SLO 기반 서비스 품질 관리 및 비용 최적화"],
                "requirements": ["시스템 엔지니어링 2년 이상", "Kubernetes 운영 경험", "모니터링/알림 시스템 경험", "장애 대응 및 사후 분석 경험"],
                "preferred": ["게임 서버 운영 경험", "대규모 트래픽 처리 경험", "카오스 엔지니어링 경험"],
                "tech_stack": ["Kubernetes", "Prometheus", "Grafana", "ELK Stack", "Terraform", "AWS"],
                "experience": "경력 2~5년",
                "description": "게임스튜디오K는 글로벌 모바일 게임을 서비스하며 동시 접속 50만을 처리합니다. 게임 서버 인프라의 안정성과 확장성을 보장하는 SRE 엔지니어를 모집합니다. 자동 스케일링 정책을 수립하고, 장애 자동 복구 시스템을 구축합니다. SLI/SLO 기반 서비스 품질 관리와 비용 최적화도 핵심 업무입니다.",
                "location": "경기 판교",
                "job_type": "정규직",
            },
            {
                "company": "시큐어클라우드",
                "title": "클라우드 보안 엔지니어",
                "main_tasks": ["멀티 클라우드 환경 보안 정책 수립", "취약점 스캐닝 및 침해 탐지 시스템 운영", "보안 자동화 도구 개발", "정기 보안 감사 수행 및 제로 트러스트 도입"],
                "requirements": ["클라우드 인프라 2년 이상", "AWS 보안 서비스 경험", "네트워크 보안 이해", "보안 감사 경험"],
                "preferred": ["CSPM/CWPP 도구 경험", "컴플라이언스 자동화 경험", "ISMS 인증 경험"],
                "tech_stack": ["AWS", "Terraform", "Python", "AWS GuardDuty", "AWS WAF", "CloudTrail"],
                "experience": "경력 3~6년",
                "description": "시큐어클라우드는 클라우드 보안 전문 기업으로, 기업의 클라우드 환경을 안전하게 보호합니다. AWS/GCP/Azure 멀티 클라우드 환경의 보안 정책을 수립하고, 취약점 스캐닝 및 침해 탐지 시스템을 운영합니다. 보안 자동화 도구를 개발하고, 정기 보안 감사를 수행합니다. 제로 트러스트 아키텍처 도입을 주도합니다.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            # ── 풀스택 ──
            {
                "company": "스타트업팩토리",
                "title": "풀스택 개발자",
                "main_tasks": ["새로운 프로젝트 MVP 빠른 개발", "사용자 피드백 기반 서비스 개선", "프론트엔드/백엔드/인프라 전 영역 담당", "소규모 팀에서 기술 의사결정 주도"],
                "requirements": ["React/Next.js 2년 이상", "Node.js 또는 Python 백엔드 경험", "데이터베이스 설계 경험", "클라우드 배포 경험"],
                "preferred": ["스타트업 근무 경험", "MVP 빠른 개발 경험", "프로젝트 리드 경험"],
                "tech_stack": ["React", "Next.js", "Node.js", "PostgreSQL", "Prisma", "Vercel", "AWS"],
                "experience": "경력 2~5년",
                "description": "스타트업팩토리는 다양한 스타트업을 인큐베이팅하는 회사입니다. 새로운 프로젝트의 MVP를 빠르게 개발하고, 사용자 피드백을 반영하여 서비스를 성장시킵니다. 프론트엔드부터 백엔드, 인프라까지 전 영역을 담당하며, 소규모 팀에서 주도적으로 기술 의사결정을 내립니다. 다양한 도메인의 프로젝트를 경험할 수 있습니다.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            # ── 모바일 ──
            {
                "company": "모빌리티랩",
                "title": "iOS 개발자 (Swift)",
                "main_tasks": ["지도 기반 인터페이스 및 QR 잠금 해제 기능 개발", "실시간 위치 추적 기능 구현", "블루투스 통신 및 하드웨어 연동", "A/B 테스트를 통한 서비스 개선"],
                "requirements": ["Swift 2년 이상", "UIKit/SwiftUI 실무 경험", "앱스토어 배포 경험", "REST API 연동 경험"],
                "preferred": ["Combine/RxSwift 경험", "CI/CD 자동화 경험", "모빌리티 도메인 경험"],
                "tech_stack": ["Swift", "SwiftUI", "Combine", "Core Data", "Fastlane", "Firebase"],
                "experience": "경력 2~4년",
                "description": "모빌리티랩은 전동 킥보드 공유 서비스를 운영합니다. 사용자 앱의 지도 기반 인터페이스, QR 코드 스캔 잠금 해제, 실시간 위치 추적 등 핵심 기능을 개발합니다. SwiftUI를 활용한 모던 iOS 개발을 지향하며, 블루투스 통신과 하드웨어 연동도 경험할 수 있습니다. 빠른 출시 주기와 A/B 테스트를 통해 서비스를 개선합니다.",
                "location": "서울 서초구",
                "job_type": "정규직",
            },
            {
                "company": "배달히어로",
                "title": "Android 개발자 (Kotlin)",
                "main_tasks": ["주문 접수/실시간 배달 추적/결제 기능 Android 앱 개발", "Jetpack Compose 기반 선언형 UI 구현", "Clean Architecture 및 멀티 모듈 구조 설계", "라이더 앱 및 가맹점 앱 관리"],
                "requirements": ["Kotlin 2년 이상", "Jetpack Compose 사용 경험", "MVVM 아키텍처 이해", "Retrofit/OkHttp 사용 경험"],
                "preferred": ["멀티 모듈 프로젝트 경험", "성능 최적화 경험", "배달/O2O 도메인 경험"],
                "tech_stack": ["Kotlin", "Jetpack Compose", "Hilt", "Coroutines", "Room", "Firebase"],
                "experience": "경력 2~5년",
                "description": "배달히어로는 로컬 음식 배달 플랫폼을 서비스합니다. 주문 접수, 실시간 배달 추적, 결제 등 핵심 기능의 Android 앱을 개발합니다. Jetpack Compose 기반의 선언형 UI를 적극 도입하고 있으며, Clean Architecture와 멀티 모듈 구조를 통해 유지보수성을 높입니다. 라이더 앱과 가맹점 앱도 함께 관리합니다.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            # ── 데이터 분석가/사이언티스트 ──
            {
                "company": "마케팅인사이트",
                "title": "데이터 분석가",
                "main_tasks": ["광고 성과 분석 및 사용자 행동 패턴 분석", "퍼널 최적화 및 A/B 테스트 설계", "비즈니스 임팩트 정량 측정 및 인사이트 도출", "정기 리포트 자동화 및 대시보드 구축"],
                "requirements": ["SQL 고급 수준", "Python 분석 라이브러리 (Pandas/NumPy) 경험", "통계 분석 기본 지식", "시각화 도구 (Tableau/Looker) 경험"],
                "preferred": ["마케팅 분석 경험", "A/B 테스트 설계 경험", "GA4/Amplitude 분석 경험"],
                "tech_stack": ["Python", "SQL", "Pandas", "Tableau", "BigQuery", "Amplitude"],
                "experience": "경력 1~4년",
                "description": "마케팅인사이트는 디지털 마케팅 에이전시로, 데이터 기반 마케팅 전략을 수립합니다. 광고 성과 분석, 사용자 행동 패턴 분석, 퍼널 최적화 등의 업무를 수행합니다. 비즈니스 임팩트를 정량적으로 측정하고, 인사이트를 도출하여 마케팅 의사결정을 지원합니다. 정기 리포트 자동화와 대시보드 구축도 담당합니다.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            {
                "company": "바이오인포",
                "title": "데이터 사이언티스트 (바이오)",
                "main_tasks": ["유전체/임상 데이터 분석 및 약물 반응 예측 모델 개발", "바이오마커 발굴을 위한 통계/ML 분석", "연구팀 협업을 통한 생물학적 인사이트 도출", "데이터 전처리 및 피처 엔지니어링"],
                "requirements": ["Python/R 3년 이상", "머신러닝 모델 개발 경험", "통계 분석 및 실험 설계 능력", "데이터 전처리 및 피처 엔지니어링 경험"],
                "preferred": ["바이오/제약 도메인 경험", "유전체 데이터 분석 경험", "논문 투고 경험"],
                "tech_stack": ["Python", "R", "scikit-learn", "XGBoost", "Jupyter", "AWS"],
                "experience": "경력 3~6년",
                "description": "바이오인포는 신약 개발을 위한 AI 플랫폼을 구축하는 바이오테크 기업입니다. 유전체 데이터, 임상 데이터 등 다양한 바이오 데이터를 분석하여 약물 반응 예측 모델을 개발합니다. 통계적 방법론과 머신러닝을 결합하여 바이오마커를 발굴하고, 연구팀과 협업하여 의미 있는 생물학적 인사이트를 도출합니다.",
                "location": "서울 송파구",
                "job_type": "정규직",
            },
            # ── QA / 테스트 ──
            {
                "company": "퀄리티소프트",
                "title": "QA 엔지니어",
                "main_tasks": ["웹/모바일 테스트 전략 수립", "자동화 테스트 프레임워크 구축", "기능/회귀/성능 테스트 수행", "CI/CD 파이프라인 테스트 통합"],
                "requirements": ["소프트웨어 테스팅 2년 이상", "테스트 케이스 설계 경험", "자동화 테스트 도구 경험 (Selenium/Playwright)", "API 테스트 경험"],
                "preferred": ["성능 테스트 (JMeter/k6) 경험", "CI/CD 연동 테스트 경험", "ISTQB 자격증"],
                "tech_stack": ["Playwright", "Python", "Postman", "k6", "Jenkins", "Jira"],
                "experience": "경력 2~5년",
                "description": "퀄리티소프트는 SaaS 제품의 품질 보증을 전문으로 합니다. 웹/모바일 애플리케이션의 테스트 전략을 수립하고, 자동화 테스트 프레임워크를 구축합니다. 기능 테스트, 회귀 테스트, 성능 테스트를 체계적으로 수행하며, CI/CD 파이프라인에 테스트를 통합합니다. 개발팀과 긴밀히 협업하여 품질 문화를 확산시킵니다.",
                "location": "서울 역삼동",
                "job_type": "정규직",
            },
            # ── 보안 ──
            {
                "company": "사이버실드",
                "title": "보안 엔지니어",
                "main_tasks": ["웹/모바일 애플리케이션 취약점 진단", "보안 아키텍처 설계", "침해사고 대응 프로세스 수립 및 보안 모니터링", "보안 수준 진단 및 개선 방안 제시"],
                "requirements": ["정보보안 3년 이상", "웹 애플리케이션 보안 취약점 분석 경험", "네트워크 보안 이해", "보안 도구 활용 능력"],
                "preferred": ["모의해킹 수행 경험", "ISMS/ISO27001 인증 경험", "보안 관련 자격증 (CISSP/CEH)"],
                "tech_stack": ["Burp Suite", "Wireshark", "Nmap", "Python", "OWASP ZAP", "Splunk"],
                "experience": "경력 3~7년",
                "description": "사이버실드는 기업 보안 컨설팅 및 관제 서비스를 제공합니다. 웹/모바일 애플리케이션 취약점을 진단하고, 보안 아키텍처를 설계합니다. 침해사고 대응 프로세스를 수립하고, 보안 모니터링 시스템을 운영합니다. 고객사의 보안 수준을 진단하고 개선 방안을 제시하며, 보안 인식 교육도 진행합니다.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            # ── PM/PO ──
            {
                "company": "프로덕트랩",
                "title": "프로덕트 매니저 (PM)",
                "main_tasks": ["제품 로드맵 수립 및 기능 우선순위 결정", "사용자 요구사항 분석 및 제품 기획", "개발팀/디자인팀 협업하여 제품 출시", "사용자 데이터 분석 및 핵심 지표 관리"],
                "requirements": ["IT 서비스 PM 경력 3년 이상", "데이터 기반 의사결정 경험", "애자일/스크럼 경험", "기술 팀과의 협업 경험"],
                "preferred": ["B2B SaaS 경험", "SQL 기본 활용 능력", "사용자 인터뷰/리서치 경험"],
                "tech_stack": ["Jira", "Confluence", "Figma", "SQL", "Amplitude", "Slack"],
                "experience": "경력 3~7년",
                "description": "프로덕트랩은 B2B 프로젝트 관리 SaaS를 만들고 있습니다. 제품 로드맵을 수립하고, 사용자 요구사항을 분석하여 기능 우선순위를 정합니다. 개발팀, 디자인팀과 긴밀히 협업하여 제품을 기획하고 출시합니다. 사용자 데이터를 분석하여 제품 개선 방향을 도출하고, 핵심 지표를 관리합니다.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            # ── 추가 다양한 포지션 ──
            {
                "company": "블록체인밸리",
                "title": "블록체인 개발자 (Solidity)",
                "main_tasks": ["EVM 호환 스마트 컨트랙트 설계 및 구현", "보안 취약점 방지 및 가스 최적화", "DeFi 프로토콜 및 NFT 마켓플레이스 개발", "Web3 최신 기술 연구 및 적용"],
                "requirements": ["Solidity 1년 이상", "스마트 컨트랙트 개발 및 배포 경험", "EVM 이해", "Web3.js/Ethers.js 사용 경험"],
                "preferred": ["DeFi 프로토콜 개발 경험", "보안 감사 경험", "Layer 2 솔루션 이해"],
                "tech_stack": ["Solidity", "Hardhat", "Ethers.js", "TypeScript", "IPFS", "The Graph"],
                "experience": "경력 1~4년",
                "description": "블록체인밸리는 DeFi 프로토콜과 NFT 마켓플레이스를 개발합니다. EVM 호환 체인에서 동작하는 스마트 컨트랙트를 설계하고 구현합니다. 보안 취약점을 사전에 방지하는 안전한 코드를 작성하며, 가스 최적화를 통해 사용자 비용을 절감합니다. Web3 생태계의 최신 기술 트렌드를 적극적으로 학습하고 적용합니다.",
                "location": "서울 강남구",
                "job_type": "정규직",
            },
            {
                "company": "테크에듀",
                "title": "기술 교육 콘텐츠 개발자",
                "main_tasks": ["실무 중심 프로그래밍 강의/튜토리얼 기획 및 제작", "실습 환경 및 과제 설계", "최신 기술 트렌드 교육 콘텐츠 개발", "기술 커뮤니티 협업을 통한 콘텐츠 확대"],
                "requirements": ["개발 경력 2년 이상", "기술 문서 작성 능력", "교육 콘텐츠 기획 경험", "명확한 커뮤니케이션 능력"],
                "preferred": ["온라인 강의 제작 경험", "오픈소스 기여 경험", "기술 블로그 운영 경험"],
                "tech_stack": ["Python", "JavaScript", "Git", "Markdown", "Notion", "Figma"],
                "experience": "경력 2~5년",
                "description": "테크에듀는 개발자를 위한 온라인 교육 플랫폼을 운영합니다. 실무 중심의 프로그래밍 강의와 튜토리얼을 기획하고 제작합니다. 최신 기술 트렌드를 학습자에게 쉽게 전달하는 콘텐츠를 만들며, 실습 환경과 과제를 설계합니다. 기술 커뮤니티와의 협업을 통해 양질의 교육 콘텐츠를 지속적으로 확대합니다.",
                "location": "서울 마포구 (리모트 가능)",
                "job_type": "정규직",
            },
            {
                "company": "로보틱스코리아",
                "title": "임베디드 소프트웨어 엔지니어",
                "main_tasks": ["자율 주행 로봇 임베디드 소프트웨어 개발", "센서 드라이버, 모터 제어, 통신 모듈 개발", "ROS2 기반 로봇 소프트웨어 아키텍처 설계", "실시간 성능 최적화"],
                "requirements": ["C/C++ 3년 이상", "임베디드 시스템 개발 경험", "RTOS 사용 경험", "하드웨어 인터페이스 (I2C/SPI/UART) 이해"],
                "preferred": ["ROS2 경험", "로봇 제어 알고리즘 경험", "PCB 설계 기본 이해"],
                "tech_stack": ["C", "C++", "ROS2", "FreeRTOS", "STM32", "Linux"],
                "experience": "경력 3~7년",
                "description": "로보틱스코리아는 물류 자동화 로봇을 개발하는 기업입니다. 자율 주행 로봇의 임베디드 소프트웨어를 개발하며, 센서 드라이버, 모터 제어, 통신 모듈 등 로우레벨 프로그래밍을 수행합니다. ROS2 기반의 로봇 소프트웨어 아키텍처를 설계하고, 실시간 성능 최적화를 담당합니다. 하드웨어팀과 긴밀히 협업합니다.",
                "location": "경기 화성시",
                "job_type": "정규직",
            },
        ]
        return self.data

    def save_to_json(self, output_path: str = "data/sample_jobs.json"):
        """크롤링/생성된 데이터를 JSON 파일로 저장합니다."""
        if not self.data:
            raise ValueError("저장할 데이터가 없습니다. generate_sample_data()를 먼저 실행하세요.")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"✅ {len(self.data)}개의 채용 공고가 {output_path}에 저장되었습니다.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="채용 공고 크롤러")
    parser.add_argument(
        "--mode",
        choices=["sample", "wanted"],
        default="sample",
        help="크롤링 모드: sample(샘플 데이터) 또는 wanted(원티드 실제 크롤링)",
    )
    parser.add_argument("--total", type=int, default=30, help="수집할 공고 수 (wanted 모드)")
    parser.add_argument("--delay", type=float, default=1.0, help="API 호출 간격(초)")
    parser.add_argument("--output", type=str, default=None, help="출력 파일 경로")
    args = parser.parse_args()

    if args.mode == "sample":
        crawler = JobCrawler()
        crawler.generate_sample_data()
        crawler.save_to_json(args.output or "data/sample_jobs.json")
    else:
        crawler = WantedCrawler(delay=args.delay)
        crawler.crawl(total=args.total)
        crawler.save_to_json(args.output or "data/wanted_jobs.json")

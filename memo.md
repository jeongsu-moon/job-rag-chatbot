아래 프롬프트를 Claude Code에 붙여넣어서 사용하세요.

단계별로 나눠져 있으니, 하나씩 실행하는 것을 추천합니다.

- **--**

**## 🔧 Phase 1: 프로젝트 초기 설정**

```

채용 공고 RAG 챗봇 프로젝트를 생성해줘. 프로젝트명은 "job-rag-chatbot"이야.

## 폴더 구조

job-rag-chatbot/

├── app/

│   ├── main.py              # FastAPI 서버 진입점

│   ├── api/

│   │   ├── __init__.py

│   │   ├── routes.py        # API 엔드포인트

│   │   └── schemas.py       # Pydantic 스키마

│   ├── core/

│   │   ├── __init__.py

│   │   ├── config.py        # 환경 변수 관리 (.env 기반)

│   │   └── embeddings.py    # 임베딩 모델 설정

│   ├── rag/

│   │   ├── __init__.py

│   │   ├── chunker.py       # 문서 청킹 (recursive + semantic)

│   │   ├── retriever.py     # 하이브리드 검색 (Vector + BM25)

│   │   ├── reranker.py      # 검색 결과 재정렬

│   │   └── chain.py         # LangChain RAG 체인

│   └── ingestion/

│       ├── __init__.py

│       ├── crawler.py       # 채용 공고 크롤러

│       └── loader.py        # 문서 로더 + 전처리

├── frontend/

│   └── streamlit_app.py     # Streamlit 채팅 UI

├── evaluation/

│   ├── eval_dataset.json    # 평가용 질문-답변 세트

│   └── evaluate.py          # 성능 평가 스크립트

├── experiments/

│   └── chunking_comparison.py  # 청킹 전략 비교 실험

├── data/

│   └── .gitkeep             # 크롤링 데이터 저장 디렉토리

├── chroma_db/

│   └── .gitkeep             # ChromaDB 영속 저장소

├── docker-compose.yml

├── Dockerfile

├── requirements.txt

├── .env.example

├── .gitignore

└── README.md

## requirements.txt 내용

langchain>=0.3.0

langchain-openai>=0.2.0

langchain-community>=0.3.0

langchain-core>=0.3.0

chromadb>=0.5.0

fastapi>=0.115.0

uvicorn>=0.32.0

streamlit>=1.39.0

beautifulsoup4>=4.12.0

requests>=2.32.0

python-dotenv>=1.0.0

rank-bm25>=0.2.2

pydantic>=2.9.0

httpx>=0.27.0

## .env.example 내용

OPENAI_API_KEY=your_openai_api_key_here

LLM_MODE=api

# api: OpenAI API 사용 / local: Ollama 로컬 모델 사용

LLM_MODEL_API=gpt-4o-mini

LLM_MODEL_LOCAL=llama3

EMBEDDING_MODEL=text-embedding-3-small

CHROMA_PERSIST_DIR=./chroma_db

CHUNK_SIZE=500

CHUNK_OVERLAP=50

## .gitignore에 포함할 것

.env

__pycache__/

chroma_db/

data/*.json

- .pyc

.venv/

## config.py

pydantic-settings의 BaseSettings를 사용해서 .env 파일에서 환경변수를 로드하도록 구현해줘.

LLM_MODE에 따라 api/local 모드를 스위칭할 수 있어야 해.

모든 __init__.py 파일도 빈 파일로 만들어줘.

README.md는 간단한 프로젝트 제목과 "WIP" 표시만 해줘. 나중에 자세히 작성할거야.

```

- **--**

**## 📥 Phase 2: 데이터 수집 (크롤링/샘플 데이터)**

```

app/ingestion/ 모듈을 구현해줘.

## crawler.py

- JobCrawler 클래스를 만들어줘
- 실제 크롤링 대신, 먼저 샘플 데이터를 생성하는 generate_sample_data() 메서드를 만들어줘
- 최소 30개의 현실적인 한국 IT 채용 공고 샘플을 생성해줘
- 각 공고에는 다음 필드가 포함되어야 해:

- company: 회사명 (실제 같은 가상 회사명)

- title: 직무명

- requirements: 필수 요구사항 (리스트)

- preferred: 우대사항 (리스트)

- tech_stack: 기술 스택 (리스트)

- experience: 경력 요구사항

- salary_range: 연봉 범위

- description: 상세 설명 (최소 200자)

- location: 근무지

- job_type: 정규직/계약직 등

- 다양한 직무를 포함해줘: 백엔드, 프론트엔드, AI/ML, 데이터 엔지니어, DevOps 등
- 결과를 data/sample_jobs.json으로 저장하는 save_to_json() 메서드도 만들어줘

## loader.py

- JobLoader 클래스를 만들어줘
- JSON 파일에서 채용 공고를 로드하여 LangChain Document 객체 리스트로 변환
- 각 Document의 metadata에 company, title, tech_stack, experience, location 포함
- page_content는 모든 텍스트 정보를 포맷팅하여 하나의 문자열로 구성

예시: "회사: {company}\n직무: {title}\n요구사항: {requirements}\n..."

```

- **--**

**## 🔪 Phase 3: 청킹 (Chunking)**

```

app/rag/chunker.py를 구현해줘.

## JobChunker 클래스

- strategy 파라미터로 청킹 전략을 선택할 수 있게 해줘: "recursive", "semantic", "fixed"
- chunk_size, chunk_overlap 파라미터 지원

### recursive 전략

- RecursiveCharacterTextSplitter 사용
- separators: ["\n\n", "\n", ". ", " "]

### semantic 전략 (핵심 차별화!)

- 채용 공고의 구조를 활용한 섹션 기반 분할
- "요구사항", "우대사항", "기술스택", "회사소개", "복리후생" 등의 섹션 키워드로 분할
- 각 청크의 metadata에 section 필드 추가 (예: "requirements", "preferred", "tech_stack")
- 섹션이 chunk_size를 초과하면 RecursiveCharacterTextSplitter로 추가 분할

### fixed 전략

- CharacterTextSplitter로 고정 크기 분할 (베이스라인 비교용)

## 또한 experiments/chunking_comparison.py도 만들어줘

- 3가지 전략 x 4가지 chunk_size(300, 500, 800, 1000)를 조합하여 비교
- 각 조합별 청크 수, 평균 청크 길이, 최대/최소 길이를 출력하는 테이블
- 결과를 experiments/chunking_results.json에 저장
- 나중에 검색 성능까지 비교할 수 있도록 확장 가능한 구조로 만들어줘

```

- **--**

**## 🧮 Phase 4: 임베딩 + 벡터DB**

```

app/core/embeddings.py를 구현해줘.

## VectorStore 클래스

- config.py의 설정을 참조하여 임베딩 모델 초기화
- OpenAIEmbeddings (text-embedding-3-small) 사용

### 메서드:

1. create_store(documents: List[Document]) -> Chroma

- 문서를 임베딩하여 ChromaDB에 저장

- persist_directory 설정으로 디스크에 영속화

- collection_name="job_postings"

2. load_store() -> Chroma

- 이미 저장된 ChromaDB를 로드

3. similarity_search(query: str, k: int = 5) -> List[Tuple[Document, float]]

- 유사도 검색 + 스코어 반환

4. add_documents(documents: List[Document])

- 기존 DB에 문서 추가

## 또한 app/ingestion/에 ingest.py 스크립트를 만들어줘

- 전체 인제스트 파이프라인을 실행하는 스크립트
- 순서: JSON 로드 -> 청킹 -> 임베딩 -> ChromaDB 저장
- 커맨드라인에서 python -m app.ingestion.ingest로 실행 가능하게
- 청킹 전략과 사이즈를 CLI 인자로 받을 수 있게 (argparse)
- 진행 상황을 tqdm이나 print로 표시

```

- **--**

**## 🔍 Phase 5: 하이브리드 검색**

```

app/rag/retriever.py를 구현해줘.

## HybridRetriever 클래스

벡터 검색(의미 유사도)과 BM25(키워드 매칭)를 결합하는 하이브리드 검색기.

### __init__ 파라미터:

- vectorstore: Chroma 인스턴스
- documents: BM25용 원본 문서 리스트
- vector_weight: 벡터 검색 가중치 (기본 0.6)
- bm25_weight: BM25 가중치 (기본 0.4)
- k: 최종 반환 문서 수 (기본 5)

### 구현:

- langchain의 EnsembleRetriever를 사용하여 두 검색기를 결합
- vector_retriever: vectorstore.as_retriever(search_kwargs={"k": 10})
- bm25_retriever: BM25Retriever.from_documents(documents, k=10)

### 메서드:

1. retrieve(query: str, k: int = None) -> List[Document]

- 하이브리드 검색 실행, 상위 k개 반환

2. retrieve_with_scores(query: str, k: int = None) -> List[Tuple[Document, float]]

- 검색 결과 + 스코어 반환 (디버깅/평가용)

## app/rag/reranker.py도 구현해줘

- SimpleReranker 클래스
- 검색 결과를 LLM을 사용하여 질문 관련성 기준으로 재정렬
- LLM에게 "이 문서가 질문에 얼마나 관련 있는지 1-10점으로 평가해줘"라고 요청
- 점수 기준으로 재정렬하여 반환
- rerank(query, documents, top_k) 메서드

```

- **--**

**## ⛓️ Phase 6: RAG Chain**

```

app/rag/chain.py를 구현해줘.

## RAGChain 클래스

LangChain LCEL 문법을 사용한 RAG 체인.

### __init__ 파라미터:

- retriever: HybridRetriever 인스턴스
- reranker: SimpleReranker 인스턴스 (선택)
- config: Config 인스턴스

### LLM 설정:

- config.LLM_MODE == "api"이면 ChatOpenAI(model=config.LLM_MODEL_API, temperature=0)
- config.LLM_MODE == "local"이면 ChatOllama(model=config.LLM_MODEL_LOCAL, temperature=0)

### 프롬프트:

```

당신은 채용 공고 분석 전문가입니다.

아래 검색된 채용 공고 정보를 바탕으로 사용자의 질문에 정확하게 답변하세요.

검색된 채용 공고:

{context}

질문: {question}

규칙:

1. 검색된 정보에 기반해서만 답변하세요. 추측하지 마세요.

2. 관련 공고가 없으면 "검색된 공고 중에는 관련 정보가 없습니다"라고 답하세요.

3. 가능하면 회사명, 구체적 요구사항, 연봉 등 구체적 정보를 포함하세요.

4. 여러 공고가 관련되면 비교하여 정리해주세요.

5. 답변은 한국어로 하세요.

```

### 메서드:

1. invoke(question: str) -> dict

- 반환: {"answer": str, "sources": List[dict], "context": str}

- sources에는 각 참조 문서의 company, title, similarity_score 포함

2. stream(question: str) -> Generator

- 스트리밍 응답 지원 (Streamlit에서 사용)

### LCEL 체인 구성:

retriever -> (선택: reranker) -> format_context -> prompt -> llm -> output_parser

```

- **--**

**## 🌐 Phase 7: FastAPI 서버**

```

app/main.py와 app/api/ 모듈을 구현해줘.

## app/api/schemas.py

Pydantic v2 모델:

1. QueryRequest:

- question: str

- top_k: int = 5

- use_reranker: bool = True

2. QueryResponse:

- answer: str

- sources: List[SourceInfo]

- processing_time: float

3. SourceInfo:

- company: str

- title: str

- relevance_score: float | None

4. HealthResponse:

- status: str

- llm_mode: str

- total_documents: int

## app/api/routes.py

1. POST /api/query - 질문 처리 (QueryRequest -> QueryResponse)

2. GET /api/health - 서버 상태 확인

3. POST /api/ingest - 새 데이터 인제스트 트리거

4. GET /api/stats - 현재 DB 통계 (문서 수, 청크 수 등)

## app/main.py

- FastAPI 앱 초기화
- CORS 미들웨어 추가 (Streamlit 연동용)
- 앱 시작 시 (lifespan) RAG 체인 초기화
- uvicorn으로 실행: python -m app.main

```

- **--**

**## 🎨 Phase 8: Streamlit UI**

```

frontend/streamlit_app.py를 구현해줘.

## 기능:

1. 채팅 인터페이스 (st.chat_message + st.chat_input)

2. 사이드바:

- LLM 모드 표시 (API/Local)

- 총 문서 수 표시

- 검색 설정 (top_k 슬라이더, reranker on/off 토글)

- "대화 초기화" 버튼

3. 스트리밍 응답 지원

4. 각 답변 아래에 "참조 문서" 접기/펼치기 (st.expander)

- 출처 회사명, 직무명, 관련도 점수 표시

5. 예시 질문 버튼들:

- "Python 백엔드 주니어 채용 공고 알려줘"

- "AI 엔지니어에게 요구하는 기술 스택은?"

- "연봉 5000만원 이상 공고를 비교해줘"

- "FastAPI 경험을 요구하는 회사는?"

## 백엔드 연동:

- requests로 FastAPI 서버와 통신
- API_URL은 환경변수 또는 기본값 http://localhost:8000
- 에러 핸들링: 서버 미응답 시 친절한 안내 메시지

```

- **--**

**## 📊 Phase 9: 평가 시스템**

```

evaluation/ 모듈을 구현해줘.

## evaluation/eval_dataset.json

최소 20개의 평가 항목을 만들어줘. 각 항목:

{

"question": "사용자 질문",

"expected_keywords": ["답변에 포함되어야 할 키워드"],

"relevant_companies": ["관련 있어야 할 회사명"],

"category": "tech_stack | salary | requirements | comparison"

}

질문 유형을 다양하게:

- 특정 기술 스택 검색 ("React 쓰는 회사")
- 조건 필터링 ("3년차 이상 요구하는 공고")
- 비교 질문 ("프론트엔드 vs 백엔드 연봉 차이")
- 복합 질문 ("Python + FastAPI + 주니어 가능한 곳")

## evaluation/evaluate.py

RAGEvaluator 클래스:

### 메서드:

1. evaluate_retrieval(eval_set) -> dict

- Precision@k: 검색된 k개 중 관련 문서 비율

- Recall@k: 전체 관련 문서 중 검색된 비율

- MRR: Mean Reciprocal Rank

2. evaluate_answer(eval_set) -> dict

- 키워드 포함률: expected_keywords가 답변에 포함된 비율

- (선택) LLM-as-Judge: GPT-4o-mini에게 답변 품질을 1-5점으로 평가 요청

3. run_full_evaluation(eval_set) -> dict

- 위 모든 평가를 실행하고 종합 리포트 생성

- 결과를 evaluation/results.json에 저장

4. compare_configs(configs: List[dict]) -> pd.DataFrame

- 여러 설정(청킹 전략, 가중치 등)을 비교하는 표 생성

- experiments에서 활용

```

- **--**

**## 🐳 Phase 10: Docker 배포**

```

Docker 설정 파일들을 만들어줘.

## Dockerfile

- python:3.11-slim 기반
- requirements.txt 설치
- app/과 frontend/ 복사
- 기본 실행: uvicorn app.main:app

## docker-compose.yml

services:

api:

build: .

ports: ["8000:8000"]

env_file: .env

volumes:

- ./chroma_db:/app/chroma_db

- ./data:/app/data

command: uvicorn app.main:app --host 0.0.0.0 --port 8000

frontend:

build: .

ports: ["8501:8501"]

env_file: .env

depends_on: [api]

command: streamlit run frontend/streamlit_app.py --server.port 8501 --server.address 0.0.0.0

environment:

- API_URL=http://api:8000

## 실행 방법이 간단해야 해:

# 1. cp .env.example .env (API키 입력)

# 2. docker-compose up --build

# 끝!

```

- **--**

**## 📝 Phase 11: README 작성**

```

README.md를 포트폴리오 수준으로 작성해줘.

## 필수 포함 섹션:

### 1. 프로젝트 소개

- 한 줄 요약
- 프로젝트 배경/동기 ("취업 준비 중 채용 공고 분석의 어려움을 AI로 해결")
- 주요 기능 3-4개

### 2. 데모

- 스크린샷 위치 placeholder (screenshots/ 디렉토리)
- 사용 예시 대화

### 3. 아키텍처

- 시스템 구성도 (Mermaid 다이어그램)
- 데이터 흐름: 크롤링 -> 청킹 -> 임베딩 -> 저장 -> 검색 -> 생성

### 4. 기술적 의사결정 (⭐ 가장 중요)

이런 형식으로:

| 결정 사항 | 선택 | 대안 | 선택 이유 |

예시:

- 벡터 DB: ChromaDB vs Pinecone vs Weaviate
- 청킹 전략: Semantic vs Recursive
- 검색 방식: Hybrid vs Vector-only
- LLM: API vs Local

각각 왜 이 선택을 했는지, 실험 결과 기반으로 설명

### 5. 실험 결과

- 청킹 전략 비교 표
- 검색 가중치 실험 결과
- API vs Local LLM 성능 비교
- 그래프/테이블 placeholder

### 6. 성능 지표

- Retrieval Precision/Recall
- 평균 응답 시간
- 답변 품질 점수

### 7. 개선 과정

- v1: 기본 RAG -> v2: 하이브리드 검색 -> v3: Reranker 추가
- 각 버전별 성능 변화

### 8. 실행 방법

- Docker로 원클릭 실행
- 로컬 개발 환경 설정

### 9. 기술 스택

- 뱃지 형태로 표시

### 10. 향후 계획

- 임베딩 파인튜닝
- 멀티턴 대화 지원
- 실시간 크롤링 연동

```
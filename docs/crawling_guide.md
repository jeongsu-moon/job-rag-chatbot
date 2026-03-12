# 크롤링 가이드

원티드(wanted.co.kr)에서 실제 채용 공고를 수집하는 방법을 설명합니다.

## 개요

`WantedCrawler`는 원티드 API를 통해 채용 공고를 수집합니다.

**동작 흐름:**
1. 목록 API에서 공고 ID 수집 (`/api/v4/jobs`)
2. 각 공고의 상세 API 호출 (`/api/v4/jobs/{id}`)
3. 프로젝트 표준 포맷으로 변환
4. JSON 파일로 저장

## 빠른 시작

```bash
# conda 환경 활성화
conda activate job-rag-chatbot

# 기본 실행 (개발 직군 30개)
python -m app.ingestion.crawler --mode wanted

# 50개 수집, 출력 파일 지정
python -m app.ingestion.crawler --mode wanted --total 50 --output data/wanted_jobs.json

# API 호출 간격 조절 (기본 1초)
python -m app.ingestion.crawler --mode wanted --delay 2.0
```

## CLI 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--mode` | `sample` | `sample`: 하드코딩 샘플 30개, `wanted`: 원티드 실제 크롤링 |
| `--total` | `30` | 수집할 공고 수 (wanted 모드에서만 사용) |
| `--delay` | `1.0` | API 호출 간 대기 시간(초). 서버 부하 방지 |
| `--output` | 자동 | 출력 파일 경로. 미지정 시 `data/sample_jobs.json` 또는 `data/wanted_jobs.json` |

## Python에서 직접 사용

```python
from app.ingestion.crawler import WantedCrawler

crawler = WantedCrawler(delay=1.0)

# 크롤링 실행
jobs = crawler.crawl(total=30)

# 결과 확인
for job in jobs[:3]:
    print(f"{job['company']} - {job['title']}")
    print(f"  기술스택: {job['tech_stack']}")
    print(f"  위치: {job['location']}")
    print()

# JSON 저장
crawler.save_to_json("data/wanted_jobs.json")
```

## 수집 후 RAG 파이프라인에 적용

크롤링한 데이터를 RAG 시스템에 적용하려면 인제스트를 다시 실행합니다.

```bash
# 1. 크롤링
python -m app.ingestion.crawler --mode wanted --total 50

# 2. loader.py의 데이터 경로를 wanted_jobs.json으로 변경하거나,
#    파일명을 sample_jobs.json으로 저장
python -m app.ingestion.crawler --mode wanted --output data/sample_jobs.json

# 3. 인제스트 실행 (청킹 → 임베딩 → ChromaDB 저장)
python -m app.ingestion.ingest

# 4. 서버 재시작
python -m app.main
```

## 수집되는 데이터 형식

각 채용 공고는 다음 필드를 포함합니다:

```json
{
  "company": "회사명",
  "title": "포지션명",
  "main_tasks": "주요업무 (텍스트)",
  "requirements": "자격요건 (텍스트)",
  "preferred": "우대사항 (텍스트)",
  "tech_stack": ["Python", "FastAPI", "..."],
  "experience": "경력 2~5년",
  "description": "회사/포지션 소개",
  "location": "서울특별시 강남구 ...",
  "job_type": "정규직",
  "source_url": "https://www.wanted.co.kr/wd/123456"
}
```

**샘플 데이터와의 차이점:**
- `main_tasks`, `requirements`, `preferred`: 샘플은 리스트, 원티드는 텍스트(줄바꿈 포함)
- `source_url`: 원티드 크롤링에만 포함
- `tech_stack`: 원티드 API의 `skill_tags`에서 자동 추출

## 주의사항

- **API 호출 간격**: `delay` 값을 너무 낮게 설정하면 429(Too Many Requests) 에러가 발생할 수 있습니다. 기본 1초를 권장합니다.
- **API 변경 가능성**: 원티드 API는 비공식 API이므로 응답 구조가 변경될 수 있습니다.
- **데이터 용도**: 수집된 데이터는 개인 학습/포트폴리오 목적으로만 사용하세요.

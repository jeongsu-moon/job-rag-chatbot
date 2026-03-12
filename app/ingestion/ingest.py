"""
전체 인제스트 파이프라인: JSON 로드 → 청킹 → 임베딩 → ChromaDB 저장

사용법:
    python -m app.ingestion.ingest
    python -m app.ingestion.ingest --strategy semantic --chunk-size 500
    python -m app.ingestion.ingest --input data/sample_jobs.json --strategy recursive
"""

import argparse
import time

from app.ingestion.loader import JobLoader
from app.rag.chunker import JobChunker
from app.core.embeddings import VectorStore


def main():
    parser = argparse.ArgumentParser(description="채용 공고 인제스트 파이프라인")
    parser.add_argument(
        "--input", default="data/sample_jobs.json", help="입력 JSON 파일 경로"
    )
    parser.add_argument(
        "--strategy",
        choices=["recursive", "semantic", "fixed"],
        default="semantic",
        help="청킹 전략 (default: semantic)",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=500, help="청크 크기 (default: 500)"
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=50, help="청크 오버랩 (default: 50)"
    )
    args = parser.parse_args()

    # 1. JSON 로드
    print(f"[1/3] 문서 로드: {args.input}")
    loader = JobLoader(args.input)
    documents = loader.to_documents()
    print(f"  → {len(documents)}개 문서 로드 완료")

    # 2. 청킹
    print(f"[2/3] 청킹 (전략: {args.strategy}, 크기: {args.chunk_size}, 오버랩: {args.chunk_overlap})")
    chunker = JobChunker(
        strategy=args.strategy,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    chunks = chunker.chunk(documents)
    print(f"  → {len(chunks)}개 청크 생성 완료")

    # 3. 임베딩 + ChromaDB 저장
    print(f"[3/3] 임베딩 및 ChromaDB 저장...")
    start = time.time()
    store = VectorStore()
    store.create_store(chunks)
    elapsed = time.time() - start
    print(f"  → ChromaDB 저장 완료 ({elapsed:.1f}초)")

    # 검증
    print("\n=== 검증 ===")
    db = store.load_store()
    count = db._collection.count()
    print(f"저장된 청크 수: {count}")

    test_query = "Python 백엔드 개발자"
    results = store.similarity_search(test_query, k=3)
    print(f'\n테스트 검색: "{test_query}"')
    for doc, score in results:
        company = doc.metadata.get("company", "")
        title = doc.metadata.get("title", "")
        print(f"  [{score:.4f}] {company} - {title}")
        print(f"    {doc.page_content[:80]}...")


if __name__ == "__main__":
    main()

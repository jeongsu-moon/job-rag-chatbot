import json
from pathlib import Path

from app.ingestion.loader import JobLoader
from app.rag.chunker import JobChunker


STRATEGIES = ["recursive", "semantic", "fixed"]
CHUNK_SIZES = [300, 500, 800, 1000]


def run_comparison(doc_path: str = "data/sample_jobs.json") -> list[dict]:
    """3가지 전략 x 4가지 chunk_size 조합을 비교합니다."""
    loader = JobLoader(doc_path)
    documents = loader.to_documents()
    print(f"원본 문서 수: {len(documents)}\n")

    results: list[dict] = []

    for strategy in STRATEGIES:
        for chunk_size in CHUNK_SIZES:
            chunk_overlap = chunk_size // 10  # chunk_size의 10%

            chunker = JobChunker(
                strategy=strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            chunks = chunker.chunk(documents)
            lengths = [len(c.page_content) for c in chunks]

            result = {
                "strategy": strategy,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "num_chunks": len(chunks),
                "avg_length": round(sum(lengths) / len(lengths), 1) if lengths else 0,
                "min_length": min(lengths) if lengths else 0,
                "max_length": max(lengths) if lengths else 0,
            }
            results.append(result)

    return results


def print_table(results: list[dict]):
    """결과를 테이블 형태로 출력합니다."""
    header = f"{'전략':<12} {'chunk_size':>10} {'overlap':>8} {'청크 수':>8} {'평균길이':>8} {'최소':>6} {'최대':>6}"
    print(header)
    print("-" * len(header))

    for r in results:
        print(
            f"{r['strategy']:<12} {r['chunk_size']:>10} {r['chunk_overlap']:>8} "
            f"{r['num_chunks']:>8} {r['avg_length']:>8} {r['min_length']:>6} {r['max_length']:>6}"
        )


def save_results(results: list[dict], output_path: str = "experiments/chunking_results.json"):
    """결과를 JSON 파일로 저장합니다."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_path}")


if __name__ == "__main__":
    results = run_comparison()
    print_table(results)
    save_results(results)

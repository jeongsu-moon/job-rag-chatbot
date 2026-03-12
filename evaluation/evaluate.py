"""
RAG 평가 시스템.

사용법:
    python -m evaluation.evaluate
    python -m evaluation.evaluate --no-llm-judge
"""

import argparse
import json
import time
from pathlib import Path

from app.core.config import settings
from app.core.embeddings import VectorStore
from app.ingestion.loader import JobLoader
from app.rag.chunker import JobChunker
from app.rag.retriever import HybridRetriever
from app.rag.reranker import SimpleReranker
from app.rag.chain import RAGChain


class RAGEvaluator:
    """RAG 시스템 성능 평가기."""

    def __init__(self, rag_chain: RAGChain, retriever: HybridRetriever):
        self.rag_chain = rag_chain
        self.retriever = retriever

    def evaluate_retrieval(self, eval_set: list[dict], k: int = 5) -> dict:
        """검색 성능 평가: Precision@k, Recall@k, MRR."""
        precisions = []
        recalls = []
        mrrs = []

        for item in eval_set:
            query = item["question"]
            relevant_companies = set(item.get("relevant_companies", []))
            if not relevant_companies:
                continue

            results = self.retriever.retrieve(query, k=k)
            retrieved_companies = set()
            first_relevant_rank = None

            for rank, doc in enumerate(results, 1):
                company = doc.metadata.get("company", "")
                retrieved_companies.add(company)
                if company in relevant_companies and first_relevant_rank is None:
                    first_relevant_rank = rank

            # Precision@k
            hits = len(retrieved_companies & relevant_companies)
            precision = hits / k if k > 0 else 0
            precisions.append(precision)

            # Recall@k
            recall = hits / len(relevant_companies) if relevant_companies else 0
            recalls.append(recall)

            # MRR
            mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0
            mrrs.append(mrr)

        return {
            "precision_at_k": round(sum(precisions) / len(precisions), 4) if precisions else 0,
            "recall_at_k": round(sum(recalls) / len(recalls), 4) if recalls else 0,
            "mrr": round(sum(mrrs) / len(mrrs), 4) if mrrs else 0,
            "k": k,
            "num_queries": len(precisions),
        }

    def evaluate_answer(
        self, eval_set: list[dict], use_llm_judge: bool = True
    ) -> dict:
        """답변 품질 평가: 키워드 포함률 + LLM-as-Judge."""
        keyword_scores = []
        llm_scores = []
        results_detail = []

        for item in eval_set:
            query = item["question"]
            expected_keywords = item.get("expected_keywords", [])

            result = self.rag_chain.invoke(query, use_reranker=False)
            answer = result["answer"]

            # 키워드 포함률
            if expected_keywords:
                hits = sum(1 for kw in expected_keywords if kw.lower() in answer.lower())
                keyword_score = hits / len(expected_keywords)
            else:
                keyword_score = 0
            keyword_scores.append(keyword_score)

            detail = {
                "question": query,
                "answer": answer,
                "keyword_score": round(keyword_score, 4),
                "sources": result["sources"],
            }

            # LLM-as-Judge
            if use_llm_judge:
                llm_score = self._llm_judge(query, answer)
                llm_scores.append(llm_score)
                detail["llm_score"] = llm_score

            results_detail.append(detail)

        result = {
            "keyword_hit_rate": round(sum(keyword_scores) / len(keyword_scores), 4) if keyword_scores else 0,
            "num_queries": len(keyword_scores),
            "details": results_detail,
        }
        if llm_scores:
            result["avg_llm_score"] = round(sum(llm_scores) / len(llm_scores), 2)

        return result

    def _llm_judge(self, question: str, answer: str) -> float:
        """GPT-4o-mini에게 답변 품질을 1~5점으로 평가 요청."""
        import re
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=0,
        )

        prompt = f"""아래 질문과 답변을 보고 답변 품질을 1~5점으로 평가해주세요.
숫자만 답변하세요.

평가 기준:
- 1점: 완전히 무관하거나 틀린 답변
- 2점: 관련은 있으나 부정확한 답변
- 3점: 부분적으로 정확한 답변
- 4점: 대체로 정확하고 유용한 답변
- 5점: 정확하고 구체적이며 완전한 답변

질문: {question}
답변: {answer[:500]}

점수:"""

        try:
            response = llm.invoke(prompt)
            score = float(re.search(r"\d", response.content).group())
            return min(max(score, 1), 5)
        except Exception:
            return 0

    def run_full_evaluation(
        self, eval_set: list[dict], use_llm_judge: bool = True
    ) -> dict:
        """전체 평가 실행 및 종합 리포트 생성."""
        print("=== 검색 성능 평가 ===")
        start = time.time()
        retrieval = self.evaluate_retrieval(eval_set)
        retrieval_time = time.time() - start
        print(f"  Precision@{retrieval['k']}: {retrieval['precision_at_k']}")
        print(f"  Recall@{retrieval['k']}: {retrieval['recall_at_k']}")
        print(f"  MRR: {retrieval['mrr']}")
        print(f"  소요 시간: {retrieval_time:.1f}초\n")

        print("=== 답변 품질 평가 ===")
        start = time.time()
        answer_eval = self.evaluate_answer(eval_set, use_llm_judge=use_llm_judge)
        answer_time = time.time() - start
        print(f"  키워드 포함률: {answer_eval['keyword_hit_rate']}")
        if "avg_llm_score" in answer_eval:
            print(f"  LLM Judge 평균: {answer_eval['avg_llm_score']}/5.0")
        print(f"  소요 시간: {answer_time:.1f}초\n")

        report = {
            "retrieval": retrieval,
            "answer": {
                "keyword_hit_rate": answer_eval["keyword_hit_rate"],
                "avg_llm_score": answer_eval.get("avg_llm_score"),
                "num_queries": answer_eval["num_queries"],
            },
            "details": answer_eval["details"],
            "total_time": round(retrieval_time + answer_time, 1),
        }

        return report

    @staticmethod
    def compare_configs(configs: list[dict], eval_set: list[dict]) -> list[dict]:
        """여러 설정을 비교하는 결과 생성."""
        results = []
        for config in configs:
            print(f"\n--- 설정: {config['name']} ---")
            loader = JobLoader()
            docs = loader.to_documents()
            chunker = JobChunker(
                strategy=config.get("strategy", "semantic"),
                chunk_size=config.get("chunk_size", 500),
            )
            chunks = chunker.chunk(docs)

            store = VectorStore()
            vectorstore = store.load_store()
            retriever = HybridRetriever(
                vectorstore=vectorstore,
                documents=chunks,
                vector_weight=config.get("vector_weight", 0.6),
                bm25_weight=config.get("bm25_weight", 0.4),
            )
            reranker = SimpleReranker()
            chain = RAGChain(retriever=retriever, reranker=reranker)

            evaluator = RAGEvaluator(rag_chain=chain, retriever=retriever)
            retrieval = evaluator.evaluate_retrieval(eval_set)

            results.append({
                "config": config["name"],
                "strategy": config.get("strategy", "semantic"),
                "chunk_size": config.get("chunk_size", 500),
                "vector_weight": config.get("vector_weight", 0.6),
                "precision": retrieval["precision_at_k"],
                "recall": retrieval["recall_at_k"],
                "mrr": retrieval["mrr"],
            })

        return results


def main():
    parser = argparse.ArgumentParser(description="RAG 평가 시스템")
    parser.add_argument("--no-llm-judge", action="store_true", help="LLM Judge 비활성화")
    parser.add_argument("--dataset", default="evaluation/eval_dataset.json", help="평가 데이터셋 경로")
    args = parser.parse_args()

    # 평가 데이터 로드
    with open(args.dataset, "r", encoding="utf-8") as f:
        eval_set = json.load(f)
    print(f"평가 데이터: {len(eval_set)}개 항목\n")

    # RAG 시스템 초기화
    loader = JobLoader()
    docs = loader.to_documents()
    chunker = JobChunker(strategy="semantic", chunk_size=500)
    chunks = chunker.chunk(docs)

    store = VectorStore()
    vectorstore = store.load_store()
    retriever = HybridRetriever(vectorstore=vectorstore, documents=chunks)
    reranker = SimpleReranker()
    chain = RAGChain(retriever=retriever, reranker=reranker)

    # 평가 실행
    evaluator = RAGEvaluator(rag_chain=chain, retriever=retriever)
    report = evaluator.run_full_evaluation(eval_set, use_llm_judge=not args.no_llm_judge)

    # 결과 저장
    output_path = "evaluation/results.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_path}")


if __name__ == "__main__":
    main()

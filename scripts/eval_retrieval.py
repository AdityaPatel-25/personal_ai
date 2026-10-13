#!/usr/bin/env python3
"""Retrieval Evaluation Harness for Personal AI DSA Knowledge Base.

Evaluates semantic retrieval accuracy (Top-1, Top-3, and Top-K) against a
benchmark set of questions (eval/questions.json). This script performs purely
local vector retrieval via ChromaDB without making any calls to Groq or LLMs.

Usage:
    # Run evaluation with default parameters (top_k=3, eval/questions.json):
    python scripts/eval_retrieval.py

    # Specify custom top-k and save JSON results:
    python scripts/eval_retrieval.py --top-k 3 --json-out eval/results.json

    # Custom question file and explicit top-k:
    python scripts/eval_retrieval.py --questions-path eval/questions.json --top-k 5
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is available on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend import rag


def load_benchmark_questions(questions_path: str) -> List[Dict[str, str]]:
    """Loads and validates benchmark questions from JSON."""
    resolved_path = (
        questions_path
        if os.path.isabs(questions_path)
        else os.path.join(PROJECT_ROOT, questions_path)
    )

    if not os.path.exists(resolved_path):
        raise FileNotFoundError(f"Questions file not found: {resolved_path}")

    with open(resolved_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if not isinstance(questions, list) or not questions:
        raise ValueError(f"Questions file {resolved_path} must contain a non-empty list.")

    for idx, item in enumerate(questions):
        if not isinstance(item, dict) or "q" not in item or "expected_source" not in item:
            raise ValueError(
                f"Question #{idx + 1} must be an object with 'q' and 'expected_source' keys."
            )

    return questions


def evaluate_retrieval(
    questions: List[Dict[str, str]],
    top_k: int = 3,
) -> Dict[str, Any]:
    """Runs retrieval for all questions and collects accuracy and similarity metrics."""
    results: List[Dict[str, Any]] = []
    top1_hits = 0
    top3_hits = 0
    topk_hits = 0
    similarity_scores: List[float] = []

    # Fetch at least max(top_k, 3) so top-3 accuracy is consistently measurable
    retrieve_k = max(top_k, 3)

    for idx, item in enumerate(questions, start=1):
        question_text = item["q"]
        expected_source = item["expected_source"]

        retrieved_chunks = rag.retrieve(question_text, top_k=retrieve_k)

        # Extract top-1 retrieved source & similarity score
        if retrieved_chunks:
            top1_source = retrieved_chunks[0].get("source", "Unknown")
            top1_similarity = float(retrieved_chunks[0].get("similarity", 0.0))
        else:
            top1_source = "None"
            top1_similarity = 0.0

        similarity_scores.append(top1_similarity)

        # Determine hit rank of expected source
        matched_rank: Optional[int] = None
        for rank, chunk in enumerate(retrieved_chunks, start=1):
            if chunk.get("source") == expected_source:
                matched_rank = rank
                break

        is_top1 = matched_rank == 1
        is_top3 = matched_rank is not None and matched_rank <= 3
        is_topk = matched_rank is not None and matched_rank <= top_k

        if is_top1:
            top1_hits += 1
        if is_top3:
            top3_hits += 1
        if is_topk:
            topk_hits += 1

        results.append(
            {
                "index": idx,
                "question": question_text,
                "expected_source": expected_source,
                "status": "PASS" if is_topk else "FAIL",
                "matched_rank": matched_rank,
                "top1_source": top1_source,
                "top1_similarity": round(top1_similarity, 4),
                "is_top1": is_top1,
                "is_top3": is_top3,
                "is_topk": is_topk,
                "retrieved_sources": [c.get("source") for c in retrieved_chunks[:top_k]],
            }
        )

    total = len(questions)
    avg_similarity = sum(similarity_scores) / total if total > 0 else 0.0
    top1_accuracy = top1_hits / total if total > 0 else 0.0
    top3_accuracy = top3_hits / total if total > 0 else 0.0
    topk_accuracy = topk_hits / total if total > 0 else 0.0

    return {
        "total_questions": total,
        "top_k": top_k,
        "top1_hits": top1_hits,
        "top1_accuracy": round(top1_accuracy, 4),
        "top3_hits": top3_hits,
        "top3_accuracy": round(top3_accuracy, 4),
        "topk_hits": topk_hits,
        "topk_accuracy": round(topk_accuracy, 4),
        "average_similarity": round(avg_similarity, 4),
        "results": results,
    }


def print_summary_table(eval_data: Dict[str, Any], questions_path: str):
    """Prints a clean ASCII summary table and performance metrics."""
    results = eval_data["results"]
    total = eval_data["total_questions"]
    top_k = eval_data["top_k"]

    print("\n" + "=" * 105)
    print("                    Personal AI — RAG Retrieval Evaluation Benchmark")
    print("=" * 105)
    print(f"Questions Source : {questions_path} ({total} questions)")
    print(f"Configured Top-K : {top_k} | Vector Store: ChromaDB | LLM Calls: None (Retrieval Only)")
    print("-" * 105)
    print(
        f"{'#':>3}  {'Status':<6}  {'Expected Source':<24}  {'Retrieved (Rank 1)':<24}  "
        f"{'Score':>7}  {'Rank':>5}  {'Question'}"
    )
    print("-" * 105)

    for r in results:
        idx_str = f"{r['index']}"
        status = r["status"]
        expected = r["expected_source"]
        retrieved = r["top1_source"]
        score_str = f"{r['top1_similarity']:.4f}"
        rank_str = f"#{r['matched_rank']}" if r["matched_rank"] is not None else "MISS"
        # Truncate question for readable terminal table
        q_preview = r["question"]
        if len(q_preview) > 34:
            q_preview = q_preview[:31] + "..."

        print(
            f"{idx_str:>3}  {status:<6}  {expected:<24}  {retrieved:<24}  "
            f"{score_str:>7}  {rank_str:>5}  {q_preview}"
        )

    print("-" * 105)
    print("EVALUATION SUMMARY:")
    print(f"  * Total Questions Evaluated : {total}")
    print(
        f"  * Top-1 Accuracy            : {eval_data['top1_hits']}/{total} "
        f"({eval_data['top1_accuracy'] * 100:.1f}%)"
    )
    print(
        f"  * Top-3 Accuracy            : {eval_data['top3_hits']}/{total} "
        f"({eval_data['top3_accuracy'] * 100:.1f}%)"
    )
    if top_k != 3:
        print(
            f"  * Top-{top_k} Accuracy            : {eval_data['topk_hits']}/{total} "
            f"({eval_data['topk_accuracy'] * 100:.1f}%)"
        )
    print(f"  * Average Similarity Score  : {eval_data['average_similarity']:.4f}")
    print(
        f"  * Overall Top-{top_k} Pass Rate   : {eval_data['topk_hits']}/{total} "
        f"({eval_data['topk_accuracy'] * 100:.1f}%)"
    )
    print("=" * 105 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Retrieval evaluation harness for Personal AI knowledge base.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--questions-path",
        type=str,
        default="eval/questions.json",
        help="Path to benchmark questions JSON file",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of top chunks to evaluate for retrieval match",
    )
    parser.add_argument(
        "--json-out",
        nargs="?",
        const="eval/results.json",
        default=None,
        help="Optional destination path to save evaluation results as JSON (default: eval/results.json if flag passed)",
    )

    args = parser.parse_args()

    # 1. Load questions
    try:
        questions = load_benchmark_questions(args.questions_path)
    except Exception as e:
        print(f"[ERROR] Failed to load questions: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Run retrieval evaluation
    try:
        eval_data = evaluate_retrieval(questions, top_k=args.top_k)
    except Exception as e:
        print(f"[ERROR] Evaluation execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 3. Print summary table
    print_summary_table(eval_data, args.questions_path)

    # 4. Optional JSON export
    if args.json_out:
        out_path = (
            args.json_out
            if os.path.isabs(args.json_out)
            else os.path.join(PROJECT_ROOT, args.json_out)
        )
        try:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(eval_data, f, indent=2)
            print(f"[+] Detailed evaluation results saved to: {out_path}")
        except Exception as e:
            print(f"[WARNING] Could not save JSON results to {out_path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

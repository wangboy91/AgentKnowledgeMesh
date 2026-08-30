"""检索质量评测脚本.

对标注 query 集分别跑「旧基线（dense + 每文档单 chunk）」与「新混合检索」，
计算 recall@k 与 nDCG@10 均值并输出对比表。

用法:
    cd src/server
    uv run python eval/run_eval.py [--dataset eval/dataset.jsonl] [--k 5]
"""

import argparse
import json
import math
import sys
from pathlib import Path

# 使 `app` 包可导入（脚本位于 src/server/eval/ 下）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.services.rag import vector_store  # noqa: E402


def load_dataset(path: str) -> list[dict]:
    """解析 JSONL 数据集，校验字段合法."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            row = json.loads(line)
            if not isinstance(row.get("query"), str):
                raise ValueError(f"line {lineno}: query 必须为字符串")
            if not isinstance(row.get("relevant_doc_ids"), list):
                raise ValueError(f"line {lineno}: relevant_doc_ids 必须为列表")
            rows.append(row)
    return rows


def _distinct_doc_ids(results: list[dict]) -> list[int]:
    """按出现顺序去重的 doc_id 列表."""
    seen: list[int] = []
    for r in results:
        d = r["doc_id"]
        if d not in seen:
            seen.append(d)
    return seen


def baseline_dense_dedup(query: str, limit: int, node_id: str | None = None) -> list[dict]:
    """旧基线：dense 余弦 + 每文档只保留最佳分块（模拟改前 DISTINCT ON 行为）."""
    candidates = vector_store.search_dense(query, node_id, candidate_limit=50)
    best: dict[int, dict] = {}
    for r in candidates:
        doc_id = r["doc_id"]
        if doc_id not in best or r["score"] > best[doc_id]["score"]:
            best[doc_id] = r
    ranked = sorted(best.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:limit]


def recall_at_k(retrieved: list[int], relevant: list[int], k: int) -> float:
    rel = set(relevant)
    if not rel:
        return 0.0
    return len(set(retrieved[:k]) & rel) / len(rel)


def ndcg_at_k(retrieved: list[int], relevant: list[int], k: int) -> float:
    rel = set(relevant)
    if not rel:
        return 0.0
    dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(retrieved[:k]) if d in rel)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return dcg / idcg if idcg else 0.0


def evaluate(search_fn, fetch_limit: int, dataset: list[dict], k: int) -> tuple[float, float]:
    """对数据集跑检索，返回 (recall@k 均值, nDCG@10 均值)."""
    recalls: list[float] = []
    ndcgs: list[float] = []
    for row in dataset:
        node_id = row.get("node_id")
        try:
            results = search_fn(row["query"], limit=fetch_limit, node_id=node_id)
            ids = _distinct_doc_ids(results)[:k]
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] '{row['query'][:24]}...' 失败: {type(e).__name__}: {e}")
            ids = []
        recalls.append(recall_at_k(ids, row["relevant_doc_ids"], k))
        ndcgs.append(ndcg_at_k(ids, row["relevant_doc_ids"], 10))
    return sum(recalls) / len(recalls), sum(ndcgs) / len(ndcgs)


def main() -> None:
    ap = argparse.ArgumentParser()
    default = str(Path(__file__).resolve().parent / "dataset.jsonl")
    ap.add_argument("--dataset", default=default)
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    dataset = load_dataset(args.dataset)
    print(f"数据集: {args.dataset}  ({len(dataset)} 条)")

    k = args.k
    # 混合检索为凑满 k 个不同文档，取 k * chunks_per_doc 个候选 chunk
    fetch_limit = k * settings.search_chunks_per_doc

    print("跑旧基线 (dense 单 chunk)...")
    base_recall, base_ndcg = evaluate(baseline_dense_dedup, k, dataset, k)
    print("跑新混合检索 (hybrid)...")
    hyb_recall, hyb_ndcg = evaluate(vector_store.search_hybrid, fetch_limit, dataset, k)

    print()
    print(f"{'指标':<12} {'旧基线(dense 单 chunk)':<24} {'新(hybrid)':<16}")
    print("-" * 52)
    print(f"{'recall@' + str(k):<12} {base_recall:<24.4f} {hyb_recall:<16.4f}")
    print(f"{'nDCG@10':<12} {base_ndcg:<24.4f} {hyb_ndcg:<16.4f}")
    print()
    print(f"recall@{k} 提升: {hyb_recall - base_recall:+.4f}")
    print(f"nDCG@10 提升:  {hyb_ndcg - base_ndcg:+.4f}")

    if hyb_recall < base_recall - 1e-9 or hyb_ndcg < base_ndcg - 1e-9:
        print("⚠ 改后指标低于基线")
        sys.exit(1)
    print("✓ 改后指标不低于基线")


if __name__ == "__main__":
    main()

"""Sweep fixed-size chunk length and compare recall@k trends.

Orchestrates the existing build_experiment_index.py and eval/run_eval.py
CLIs for each chunk size rather than re-implementing chunking/embedding/eval
a second time - guarantees these numbers are produced exactly the same way
as the rest of retrieval_lab's results.

Usage:
    python -m retrieval_lab.chunk_size_sweep --sizes 200 500 1000
    python -m retrieval_lab.chunk_size_sweep --sizes 200 500 1000 \
        --input retrieval_lab/data/nfcorpus_source/knowledge_base.json \
        --queries retrieval_lab/data/nfcorpus_source/eval_queries.json \
        --prefix nfcorpus --k 5 10 20
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "data" / "eval_results"
PYTHON = sys.executable or "python3"


def run(command: list[str]) -> None:
    print(f"\n$ {' '.join(command)}")
    subprocess.run(command, check=True)


def sweep(sizes: list[int], prefix: str, input_path: str | None, queries_path: str, k_values: list[int], alpha: float) -> dict:
    results = {}

    for size in sizes:
        name = f"{prefix}-fixed-{size}"
        build_command = [
            PYTHON, "-m", "retrieval_lab.build_experiment_index",
            "--strategy", "fixed",
            "--chunk-size", str(size),
            "--overlap", str(max(10, size // 10)),
            "--name", name,
        ]
        if input_path:
            build_command += ["--input", input_path]
        run(build_command)

        eval_command = [
            PYTHON, "-m", "retrieval_lab.eval.run_eval",
            "--index", name,
            "--queries", queries_path,
            "--k", *[str(k) for k in k_values],
            "--alpha", str(alpha),
        ]
        run(eval_command)

        with open(RESULTS_DIR / f"{name}.json", encoding="utf-8") as handle:
            summary = json.load(handle)

        meta_path = BASE_DIR / "data" / "indexes" / name / "meta.json"
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)

        results[size] = {"chunk_count": meta["chunk_count"], "recall": summary["recall"]}

    return results


def print_and_save_table(results: dict, k_values: list[int], prefix: str) -> None:
    lines = [f"# Chunk Size Sweep: {prefix}", ""]
    lines.append("| Chunk size (tokens) | Chunks | " + " | ".join(f"vector@{k}" for k in k_values) + " | " + " | ".join(f"bm25@{k}" for k in k_values) + " | " + " | ".join(f"hybrid@{k}" for k in k_values) + " |")
    lines.append("|---" * (2 + 3 * len(k_values)) + "|")

    print(f"\nChunk size sweep: {prefix}")
    header = "size".ljust(8) + "chunks".rjust(8)
    for method in ("vector", "bm25", "hybrid"):
        header += "".join(f"{method}@{k}".rjust(12) for k in k_values)
    print(header)

    for size in sorted(results):
        # recall came back from json.load(), so k is a string key even though
        # run_eval.py's in-memory dict uses int keys.
        recall = results[size]["recall"]
        chunk_count = results[size]["chunk_count"]
        row = str(size).ljust(8) + str(chunk_count).rjust(8)
        cells = [str(chunk_count)]
        for method in ("vector", "bm25", "hybrid"):
            for k in k_values:
                value = recall[method][str(k)]
                row += f"{value:.1%}".rjust(12)
                cells.append(f"{value:.1%}")
        print(row)
        lines.append(f"| {size} | " + " | ".join(cells) + " |")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{prefix}_chunk_size_sweep.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved sweep summary -> {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[200, 500, 1000])
    parser.add_argument("--prefix", default="multivac", help="Naming prefix for the built indexes, e.g. 'multivac' or 'nfcorpus'")
    parser.add_argument("--input", default=None, help="Knowledge base JSON to chunk (defaults to data/knowledge_base.json)")
    parser.add_argument("--queries", default=str(BASE_DIR / "eval" / "queries.json"))
    parser.add_argument("--k", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--alpha", type=float, default=0.5)
    args = parser.parse_args()

    k_values = sorted(args.k)
    results = sweep(args.sizes, args.prefix, args.input, args.queries, k_values, args.alpha)
    print_and_save_table(results, k_values, args.prefix)


if __name__ == "__main__":
    main()

"""v13.18: offline, non-production reranking sensitivity study.

Input: v13.17 diagnostics JSON. No imports from the application, embeddings,
Chroma, or production code. This is NOT a controlled held-out evaluation.

The v13.17 file-level entries represent the best chunk per file. This script
can only rescore those recorded entries, not unseen chunks. The optional
12-chunk sample is inspected separately and is NOT a complete symbol benchmark.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from statistics import mean


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", s).lower()))


def query_category(query: str) -> str:
    q = query.lower()
    if re.search(r"\b(data structures?|state (?:structure|schema)|typed dict|typeddict|dataclass|models? defined|context defined)\b", q):
        return "data_definition"
    if re.search(r"\b(assembled|construct(?:ed|ion)?|build|wire|connect|sequence of .* stages|workflow graph)\b", q):
        return "construction"
    if re.search(r"\b(decides?|decision|whether|should|condition|branch|revision)\b", q):
        return "decision"
    if re.search(r"\b(startup|starts?|initiali[sz]|lifespan|bootstraps?)\b", q):
        return "startup"
    return "other"


def evidence_score(query: str, entry: dict, variant: str) -> float:
    """Small, generic metadata-based probes; never used to alter production."""
    if variant == "baseline":
        return 0.0
    category = query_category(query)
    sym = str(entry.get("symbol") or "")
    file = str(entry.get("file") or "")
    typ = str(entry.get("symbol_type") or "").lower()
    st = tokens(sym)
    ft = tokens(file)
    bonus = 0.0
    if category == "data_definition":
        if typ in {"class", "typeddict", "dataclass", "type_alias"}:
            bonus += 0.20
        if st & {"state", "schema", "context", "model"}:
            bonus += 0.12
        if ft & {"state", "schema", "models", "types"}:
            bonus += 0.08
    elif category == "construction":
        if st & {"build", "builder", "construct", "create", "assemble", "wire", "compile"}:
            bonus += 0.24
        if st & {"graph", "workflow", "pipeline"}:
            bonus += 0.12
        if typ == "class" and not (st & {"builder", "factory"}):
            bonus -= 0.08
    elif category == "decision":
        if st & {"should", "decide", "decision", "condition", "route", "branch"}:
            bonus += 0.20
        if st & {"graph", "builder"}:
            bonus -= 0.06
    elif category == "startup":
        if st & {"lifespan", "startup", "initialize", "init", "bootstrap", "main"}:
            bonus += 0.20
    if variant == "structural":
        return bonus
    if variant == "lexical_discount":
        # Score sensitivity to lexical contribution; uses diagnostic signal,
        # not BM25 raw scores (which are on an unrelated scale).
        lexical = (entry.get("ranking_signals") or {}).get("lexical_retrieval", 0)
        return bonus - 0.25 * float(lexical or 0)
    raise ValueError(variant)


def evaluate(data: dict, variant: str) -> dict:
    cases = []
    for row in data["results"]:
        entries = row["top_files"]
        if not entries:
            continue
        rescored = sorted(entries, key=lambda e: (-float(e["score"]) - evidence_score(row["query"], e, variant), str(e["file"])))
        files = [e["file"] for e in rescored]
        rank = files.index(row["expected_file"]) + 1 if row["expected_file"] in files else None
        old = row.get("expected_file_rank")
        cases.append({
            "query": row["query"], "category": query_category(row["query"]),
            "expected_file": row["expected_file"], "baseline_rank": old,
            "rank": rank, "top_file": files[0],
            "top_three": [{"file": e["file"], "base_score": e["score"],
                           "adjustment": round(evidence_score(row["query"], e, variant), 6),
                           "new_score": round(float(e["score"]) + evidence_score(row["query"], e, variant), 6),
                           "symbol": e.get("symbol")} for e in rescored[:3]],
        })
    ranks = [c["rank"] for c in cases]
    return {"variant": variant, "metrics": {
        "cases": len(cases),
        "file_hit_at_1": sum(r == 1 for r in ranks) / len(ranks),
        "file_hit_at_5": sum(r is not None and r <= 5 for r in ranks) / len(ranks),
        "file_hit_at_recorded_k": sum(r is not None for r in ranks) / len(ranks),
        "file_mrr": mean(1/r if r else 0 for r in ranks)}, "cases": cases}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default="data/evaluation/v13_17_diagnostics.json")
    ap.add_argument("--output", default="data/evaluation/v13_18_offline_reranking.json")
    args = ap.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if data.get("version") != "v13.17":
        raise SystemExit("Expected v13.17 diagnostics JSON")
    variants = [evaluate(data, v) for v in ("baseline", "structural", "lexical_discount")]
    report = {"version": "v13.18", "scope": "offline rescoring of v13.17 recorded top-files only",
              "cautions": ["This is an in-sample exploratory sensitivity analysis, not validation or evidence of generalization.",
                           "Only the best recorded chunk for each file is rescored; a different chunk cannot become its file's representative.",
                           "The v13.17 top_chunks list is truncated, so symbol-level recall/accuracy cannot be computed.",
                           "The startup query label requires independent review.",
                           "The lexical-only baseline used different chunks and is not a controlled ablation."],
              "variants": variants}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for v in variants:
        print(v["variant"], v["metrics"])
    baseline = variants[0]["cases"]
    for variant in variants[1:]:
        print("\nChanged ranks:", variant["variant"])
        for before, after in zip(baseline, variant["cases"]):
            if before["rank"] != after["rank"]:
                print(f'  {before["rank"]} -> {after["rank"]}  {before["query"][:78]}')
    print("Report:", out)

if __name__ == "__main__":
    main()

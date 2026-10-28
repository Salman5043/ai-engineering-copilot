"""v13.14: deterministic, synthetic, cross-project LEXICAL retrieval evaluation.

Run: uv run python -m app.scripts.evaluate_cross_project_v13_14 --top-k 5
No external repositories, embedding calls, vector database, or index mutation required.
This is a smoke/regression suite, NOT evidence of real-world generalization.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean
from unittest.mock import patch

from app.retrieval import lexical_retriever
from app.retrieval.query_parser import parse_query

# Each synthetic repository is intentionally independent. Source snippets are
# deliberately small and representative; they are not harvested from real repos.
PROJECTS = {
    "web_api": [
        ("api/routes/users.py", "create_user", "function", "def create_user(payload):\n    # validate and create user account\n    return user_service.create(payload)"),
        ("api/security/auth.py", "verify_token", "function", "def verify_token(token):\n    # validate JWT bearer token signature\n    return jwt.decode(token)"),
        ("api/config.py", "load_settings", "function", "def load_settings():\n    # load environment configuration\n    return Settings()"),
    ],
    "django_style": [
        ("shop/models.py", "Order", "class", "class Order(models.Model):\n    # customer purchase and order status\n    status = models.CharField()"),
        ("shop/views.py", "checkout_view", "function", "def checkout_view(request):\n    # process customer checkout\n    return redirect('payment')"),
        ("shop/tasks.py", "send_receipt", "function", "def send_receipt(order):\n    # email receipt to customer\n    mail.send(order)"),
    ],
    "cli_tool": [
        ("cli/commands.py", "parse_arguments", "function", "def parse_arguments(argv):\n    # parse command line flags and options\n    return parser.parse_args(argv)"),
        ("cli/output.py", "render_table", "function", "def render_table(rows):\n    # format terminal table output\n    print(rows)"),
        ("cli/config.py", "read_config", "function", "def read_config(path):\n    # read local TOML configuration file\n    return tomllib.load(path)"),
    ],
    "async_worker": [
        ("worker/consumer.py", "consume_messages", "async_function", "async def consume_messages(queue):\n    # receive asynchronous queue messages\n    async for message in queue: await process(message)"),
        ("worker/retry.py", "backoff_delay", "function", "def backoff_delay(attempt):\n    # exponential retry backoff\n    return 2 ** attempt"),
        ("worker/storage.py", "save_checkpoint", "function", "def save_checkpoint(offset):\n    # persist consumer checkpoint offset\n    db.write(offset)"),
    ],
    "data_science": [
        ("pipeline/features.py", "normalize_features", "function", "def normalize_features(frame):\n    # standardize numeric feature columns\n    return (frame - frame.mean()) / frame.std()"),
        ("pipeline/train.py", "train_classifier", "function", "def train_classifier(dataset):\n    # fit classification model\n    model.fit(dataset)"),
        ("pipeline/metrics.py", "calculate_f1", "function", "def calculate_f1(labels, predictions):\n    # compute F1 classification metric\n    return f1_score(labels, predictions)"),
    ],
    "library_package": [
        ("src/widgetlib/serializer.py", "serialize_payload", "function", "def serialize_payload(obj):\n    # encode object as JSON payload\n    return json.dumps(obj)"),
        ("src/widgetlib/registry.py", "PluginRegistry", "class", "class PluginRegistry:\n    # register and discover plugin implementations\n    def register(self, plugin): pass"),
        ("tests/test_registry.py", "test_registration", "function", "def test_registration():\n    # assert plugin registration behavior\n    assert True"),
    ],
}

# Gold labels are manually specified for these synthetic examples only.
CASES = [
    ("web_api", "Where is create_user implemented?", "api/routes/users.py"),
    ("web_api", "Which function verifies a JWT bearer token?", "api/security/auth.py"),
    ("django_style", "Where is the Order model defined?", "shop/models.py"),
    ("django_style", "Where is customer checkout processed?", "shop/views.py"),
    ("cli_tool", "Where are command line flags parsed?", "cli/commands.py"),
    ("cli_tool", "Which function formats terminal table output?", "cli/output.py"),
    ("async_worker", "Where is exponential retry backoff calculated?", "worker/retry.py"),
    ("async_worker", "Which coroutine consumes queue messages?", "worker/consumer.py"),
    ("data_science", "Where are numeric features standardized?", "pipeline/features.py"),
    ("data_science", "Where is the classification model trained?", "pipeline/train.py"),
    ("library_package", "Where is PluginRegistry defined?", "src/widgetlib/registry.py"),
    ("library_package", "Which function encodes objects as JSON?", "src/widgetlib/serializer.py"),
]


class InMemoryCollection:
    def __init__(self, projects):
        self.projects = projects
        self.calls = []

    def get(self, *, where, include):
        self.calls.append((where, include))
        assert set(where) == {"repository_id"}, "Repository isolation filter missing"
        assert "documents" in include and "metadatas" in include
        repo_id = where["repository_id"]
        if repo_id not in self.projects:
            return {"documents": [], "metadatas": []}
        rows = self.projects[repo_id]
        return {
            "documents": [r[3] for r in rows],
            "metadatas": [
                {"file": r[0], "symbol": r[1], "symbol_type": r[2],
                 "language": "python", "repository_id": repo_id}
                for r in rows
            ],
        }


def evaluate(top_k=5):
    if top_k < 1:
        raise ValueError("top_k must be positive")
    collection = InMemoryCollection(PROJECTS)
    results = []
    with patch.object(lexical_retriever, "get_collection", return_value=collection):
        for repo_id, query, expected_file in CASES:
            found = lexical_retriever.lexical_search(
                repository_id=repo_id, parsed_query=parse_query(query),
                top_k=top_k, language="python")
            files = [str(item["metadata"]["file"]) for item in found]
            rank = files.index(expected_file) + 1 if expected_file in files else None
            results.append({
                "repository": repo_id, "query": query, "expected_file": expected_file,
                "returned_files": files, "rank": rank, "hit_at_1": rank == 1,
                "hit_at_k": rank is not None, "reciprocal_rank": 1 / rank if rank else 0,
            })
        # Cross-repository isolation, including unknown repository IDs.
        missing = lexical_retriever.lexical_search(
            repository_id="nonexistent_repo", parsed_query=parse_query("create_user"),
            top_k=top_k, language="python")
        if missing:
            raise AssertionError("Unknown repository returned another repository's data")
    per_project = {}
    for project in PROJECTS:
        subset = [r for r in results if r["repository"] == project]
        per_project[project] = {
            "cases": len(subset), "hit_at_1": mean(r["hit_at_1"] for r in subset),
            "hit_at_k": mean(r["hit_at_k"] for r in subset),
            "mrr": mean(r["reciprocal_rank"] for r in subset),
        }
    return {
        "suite": "v13.14 synthetic cross-project lexical smoke test",
        "limitations": [
            "Synthetic snippets only; not independent external Python projects.",
            "Lexical search only; does not test indexing, embeddings, hybrid retrieval, or full pipeline.",
            "Expected files are manually authored; no real-world generalization claim.",
        ],
        "top_k": top_k, "cases": len(results),
        "overall": {
            "hit_at_1": mean(r["hit_at_1"] for r in results),
            "hit_at_k": mean(r["hit_at_k"] for r in results),
            "mrr": mean(r["reciprocal_rank"] for r in results),
        },
        "per_project": per_project, "results": results,
        "isolation_passed": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/v13_14_cross_project.json"))
    parser.add_argument("--min-hit-at-k", type=float, default=None,
                        help="Optional provisional gate (0..1); set only after observing baseline")
    args = parser.parse_args()
    if args.top_k < 1 or (args.min_hit_at_k is not None and not 0 <= args.min_hit_at_k <= 1):
        parser.error("Invalid top-k or min-hit-at-k")
    report = evaluate(args.top_k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("v13.14 synthetic cross-project lexical evaluation")
    for name, metrics in report["per_project"].items():
        print(f"  {name:18s} hit@1={metrics['hit_at_1']:.1%} hit@{args.top_k}={metrics['hit_at_k']:.1%} mrr={metrics['mrr']:.3f}")
    print("Overall:", report["overall"])
    print("Repository isolation: PASS")
    print("Limitations:", " ".join(report["limitations"]))
    print("Report:", args.output)
    if args.min_hit_at_k is not None and report["overall"]["hit_at_k"] < args.min_hit_at_k:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

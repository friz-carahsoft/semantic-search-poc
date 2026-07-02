from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import NotFoundError, RequestError
from sentence_transformers import SentenceTransformer

INDEX_NAME = os.getenv("OPENSEARCH_INDEX", "quotes-v1")
PIPELINE_PREFIX = os.getenv("OPENSEARCH_HYBRID_PIPELINE_PREFIX", "quotes-hybrid-pipeline")
TEXT_FIELD = os.getenv("SEARCH_TEXT_FIELD", "search_text")
EMBEDDING_FIELD = os.getenv("EMBEDDING_FIELD", "quote_embedding")
MANIFEST_PATH = Path(os.getenv("EMBEDDING_MANIFEST_PATH", "data/embedding-manifest.json"))
RESULTS_PATH = Path("opensearch/hybrid-weight-tuning-results.json")
SUMMARY_PATH = Path("opensearch/hybrid-weight-tuning-summary.md")

TOP_K = int(os.getenv("TOP_K", "5"))
CANDIDATE_K = int(os.getenv("CANDIDATE_K", "10"))

DEFAULT_WEIGHT_SETS = "0.70:0.30,0.50:0.50,0.30:0.70"
WEIGHT_SETS = os.getenv("HYBRID_WEIGHT_SETS", DEFAULT_WEIGHT_SETS)

SAMPLE_QUERIES = [
    "perseverance",
    "quotes about never giving up",
    "curiosity and discovery",
    "leading with humility",
    "finding humor in mistakes",
    "learning from failure",
]


def require_password() -> str:
    """Read the local OpenSearch admin password from the environment."""
    password = os.getenv("OPENSEARCH_PASSWORD") or os.getenv(
        "OPENSEARCH_INITIAL_ADMIN_PASSWORD"
    )

    if not password:
        raise RuntimeError(
            "Missing OpenSearch password. Set OPENSEARCH_INITIAL_ADMIN_PASSWORD "
            "or OPENSEARCH_PASSWORD before running this script."
        )

    return password


def create_client() -> OpenSearch:
    """Create a local development OpenSearch client."""
    password = require_password()

    return OpenSearch(
        hosts=[
            {
                "host": os.getenv("OPENSEARCH_HOST", "localhost"),
                "port": int(os.getenv("OPENSEARCH_PORT", "9200")),
            }
        ],
        http_auth=(os.getenv("OPENSEARCH_USER", "admin"), password),
        use_ssl=True,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
        connection_class=RequestsHttpConnection,
    )


def read_manifest() -> dict[str, Any]:
    """Read the embedding manifest created in Step 5."""
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest not found: {MANIFEST_PATH}. Run Step 5 before Step 9."
        )

    with MANIFEST_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def parse_weight_sets(value: str) -> list[tuple[float, float]]:
    """Parse weight sets from KEYWORD:SEMANTIC comma-separated syntax."""
    parsed: list[tuple[float, float]] = []

    for item in value.split(","):
        item = item.strip()
        if not item:
            continue

        if ":" not in item:
            raise ValueError(
                f"Invalid weight set {item!r}. Expected format like 0.70:0.30"
            )

        keyword_raw, semantic_raw = item.split(":", maxsplit=1)
        keyword_weight = float(keyword_raw)
        semantic_weight = float(semantic_raw)

        if keyword_weight < 0 or semantic_weight < 0:
            raise ValueError("Weights must be non-negative")

        if keyword_weight + semantic_weight <= 0:
            raise ValueError("At least one weight must be greater than zero")

        parsed.append((keyword_weight, semantic_weight))

    if not parsed:
        raise ValueError("At least one weight set is required")

    return parsed


def normalized_weights(keyword_weight: float, semantic_weight: float) -> tuple[float, float]:
    """Normalize weights so they sum to one."""
    total = keyword_weight + semantic_weight
    return keyword_weight / total, semantic_weight / total


def pipeline_suffix(keyword_weight: float, semantic_weight: float) -> str:
    """Create a stable pipeline suffix from the normalized weights."""
    keyword_norm, semantic_norm = normalized_weights(keyword_weight, semantic_weight)
    keyword_part = int(round(keyword_norm * 100))
    semantic_part = int(round(semantic_norm * 100))
    return f"k{keyword_part:02d}-s{semantic_part:02d}"


def safe_pipeline_name(keyword_weight: float, semantic_weight: float) -> str:
    """Create a safe OpenSearch search-pipeline name."""
    name = f"{PIPELINE_PREFIX}-{pipeline_suffix(keyword_weight, semantic_weight)}"
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)


def build_hybrid_pipeline_body(keyword_weight: float, semantic_weight: float) -> dict[str, Any]:
    """Build the OpenSearch search pipeline for one weight combination."""
    keyword_norm, semantic_norm = normalized_weights(keyword_weight, semantic_weight)

    return {
        "description": (
            "Hybrid search pipeline for quotes POC weight tuning "
            f"keyword={keyword_norm:.2f}, semantic={semantic_norm:.2f}"
        ),
        "phase_results_processors": [
            {
                "normalization-processor": {
                    "normalization": {
                        "technique": "min_max",
                    },
                    "combination": {
                        "technique": "arithmetic_mean",
                        "parameters": {
                            "weights": [
                                keyword_norm,
                                semantic_norm,
                            ]
                        },
                    },
                }
            }
        ],
    }


def create_or_update_search_pipeline(
    client: OpenSearch, keyword_weight: float, semantic_weight: float
) -> str:
    """Create or update one OpenSearch search pipeline."""
    pipeline_name = safe_pipeline_name(keyword_weight, semantic_weight)
    pipeline_body = build_hybrid_pipeline_body(keyword_weight, semantic_weight)
    path = f"/_search/pipeline/{pipeline_name}"
    client.transport.perform_request("PUT", path, body=pipeline_body)
    return pipeline_name


def verify_index(client: OpenSearch, expected_count: int | None) -> int:
    """Verify the index exists and contains documents."""
    if not client.indices.exists(index=INDEX_NAME):
        raise RuntimeError(
            f"Index {INDEX_NAME!r} does not exist. Run Step 4 and Step 6 first."
        )

    count_response = client.count(index=INDEX_NAME)
    count = int(count_response["count"])

    if count == 0:
        raise RuntimeError(
            f"Index {INDEX_NAME!r} contains 0 documents. Run Step 6 first."
        )

    if expected_count is not None and count != expected_count:
        print(
            f"Warning: manifest expected {expected_count} records, "
            f"but OpenSearch count is {count}."
        )

    return count


def verify_mapping(client: OpenSearch, expected_dimension: int) -> None:
    """Verify the vector field exists and has the expected dimension."""
    mapping = client.indices.get_mapping(index=INDEX_NAME)
    properties = mapping[INDEX_NAME]["mappings"].get("properties", {})

    if TEXT_FIELD not in properties:
        raise RuntimeError(f"Text field {TEXT_FIELD!r} not found in index mapping")

    if EMBEDDING_FIELD not in properties:
        raise RuntimeError(
            f"Embedding field {EMBEDDING_FIELD!r} not found in index mapping"
        )

    vector_mapping = properties[EMBEDDING_FIELD]
    actual_dimension = int(vector_mapping.get("dimension", -1))

    if actual_dimension != expected_dimension:
        raise RuntimeError(
            f"Embedding dimension mismatch. Manifest expects {expected_dimension}; "
            f"index field {EMBEDDING_FIELD!r} uses {actual_dimension}."
        )


def load_model(manifest: dict[str, Any]) -> SentenceTransformer:
    """Load the same embedding model used during document embedding."""
    model_name = str(manifest.get("embedding_model", "all-MiniLM-L6-v2"))
    expected_dimension = int(manifest.get("embedding_dimension", 384))

    model = SentenceTransformer(model_name)
    actual_dimension = model.get_sentence_embedding_dimension()

    if actual_dimension is None:
        raise RuntimeError(f"Could not determine embedding dimension for {model_name}")

    if int(actual_dimension) != expected_dimension:
        raise RuntimeError(
            f"Model dimension mismatch. Manifest expects {expected_dimension}; "
            f"model {model_name!r} returned {actual_dimension}."
        )

    return model


def embed_query(model: SentenceTransformer, query_text: str) -> list[float]:
    """Convert query text into a vector."""
    vector = model.encode(query_text, convert_to_numpy=True)
    return [float(value) for value in vector.tolist()]


def source_filter() -> dict[str, Any]:
    """Exclude embedding vectors from search responses."""
    return {
        "excludes": [EMBEDDING_FIELD],
    }


def keyword_query(query_text: str) -> dict[str, Any]:
    """Build the keyword query used inside the hybrid query."""
    return {
        "multi_match": {
            "query": query_text,
            "fields": [
                "quote^3",
                f"{TEXT_FIELD}^2",
            ],
            "type": "best_fields",
            "operator": "or",
        }
    }


def semantic_query(query_vector: list[float], k: int) -> dict[str, Any]:
    """Build the vector query used inside the hybrid query."""
    return {
        "knn": {
            EMBEDDING_FIELD: {
                "vector": query_vector,
                "k": k,
            }
        }
    }


def hybrid_search(
    client: OpenSearch,
    query_text: str,
    query_vector: list[float],
    pipeline_name: str,
    top_k: int,
    candidate_k: int,
) -> dict[str, Any]:
    """Run OpenSearch hybrid search for one query and one pipeline."""
    body = {
        "size": top_k,
        "_source": source_filter(),
        "query": {
            "hybrid": {
                "queries": [
                    keyword_query(query_text),
                    semantic_query(query_vector, max(top_k, candidate_k)),
                ]
            }
        },
    }

    return client.search(
        index=INDEX_NAME,
        body=body,
        params={"search_pipeline": pipeline_name},
    )


def simplify_hits(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert OpenSearch hits to a compact review structure."""
    hits = response.get("hits", {}).get("hits", [])
    simplified: list[dict[str, Any]] = []

    for rank, hit in enumerate(hits, start=1):
        source = hit.get("_source", {})
        simplified.append(
            {
                "rank": rank,
                "id": source.get("id", hit.get("_id")),
                "score": hit.get("_score"),
                "quote": source.get("quote"),
                "author": source.get("author"),
                "category": source.get("category"),
                "tags": source.get("tags", []),
            }
        )

    return simplified


def format_score(score: Any) -> str:
    """Format a score for Markdown output."""
    if isinstance(score, (int, float)):
        return f"{score:.6f}"
    return ""


def markdown_escape(value: Any) -> str:
    """Escape basic Markdown table characters."""
    return str(value or "").replace("|", "\\|")


def markdown_row(weight_label: str, hits: list[dict[str, Any]]) -> str:
    """Create one Markdown row for a weight set's top result."""
    if not hits:
        return f"| {weight_label} | No results |  |  |  |  |"

    top_hit = hits[0]
    quote = markdown_escape(top_hit.get("quote"))
    author = markdown_escape(top_hit.get("author"))
    category = markdown_escape(top_hit.get("category"))
    score = format_score(top_hit.get("score"))

    return (
        f"| {weight_label} | `{top_hit.get('id')}` | {score} | "
        f"{category} | {quote} — {author} |  |"
    )


def write_results(results: dict[str, Any]) -> None:
    """Write full JSON tuning results."""
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)
        file.write("\n")


def write_markdown_summary(results: dict[str, Any]) -> None:
    """Write human-readable hybrid tuning summary."""
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Step 9 Hybrid Weight Tuning Summary",
        "",
        f"Generated at: `{results['generated_at_utc']}`",
        "",
        "This file compares hybrid search results across multiple keyword/semantic weight combinations.",
        "",
        "The final `Reviewer Notes` column is intentionally blank. Use it during team review to document which result is preferred and why.",
        "",
        "Default review score:",
        "",
        "| Score | Meaning |",
        "| ---: | --- |",
        "| `3` | Excellent: directly satisfies the query intent |",
        "| `2` | Good: useful and related |",
        "| `1` | Weak: related but probably unsatisfying |",
        "| `0` | Poor: irrelevant or misleading |",
        "",
    ]

    for query_result in results["queries"]:
        lines.extend(
            [
                f"## Query: `{query_result['query']}`",
                "",
                "| Weights | Top ID | Score | Category | Top Result | Reviewer Notes |",
                "| --- | --- | ---: | --- | --- | --- |",
            ]
        )

        for weight_result in query_result["weight_results"]:
            label = weight_result["weight_label"]
            hits = weight_result["hits"]
            lines.append(markdown_row(label, hits))

        lines.append("")

    lines.extend(
        [
            "## Review Prompts",
            "",
            "Use this summary to discuss:",
            "",
            "- Did keyword-heavy hybrid search preserve useful exact matches?",
            "- Did semantic-heavy hybrid search improve conceptual matches?",
            "- Did balanced hybrid search provide the best compromise?",
            "- Were any top results technically related but not useful?",
            "- Which weighting approach would be safest as a production default?",
            "",
        ]
    )

    with SUMMARY_PATH.open("w", encoding="utf-8") as file:
        file.write("\n".join(lines))
        file.write("\n")


def compare_weight_sets(
    client: OpenSearch,
    model: SentenceTransformer,
    query_text: str,
    weight_sets: list[tuple[float, float]],
) -> dict[str, Any]:
    """Run hybrid search for one query across all weight sets."""
    query_vector = embed_query(model, query_text)
    weight_results = []

    print("\n" + "=" * 100)
    print(f"Query: {query_text}")
    print("-" * 100)

    for keyword_weight, semantic_weight in weight_sets:
        keyword_norm, semantic_norm = normalized_weights(keyword_weight, semantic_weight)
        pipeline_name = create_or_update_search_pipeline(
            client, keyword_norm, semantic_norm
        )
        response = hybrid_search(
            client=client,
            query_text=query_text,
            query_vector=query_vector,
            pipeline_name=pipeline_name,
            top_k=TOP_K,
            candidate_k=CANDIDATE_K,
        )
        hits = simplify_hits(response)
        label = f"keyword={keyword_norm:.2f}, semantic={semantic_norm:.2f}"

        if hits:
            top_hit = hits[0]
            print(
                f"{label:<34} | rank 1 | {top_hit.get('id')} | "
                f"{top_hit.get('quote')}"
            )
        else:
            print(f"{label:<34} | no results")

        weight_results.append(
            {
                "weight_label": label,
                "keyword_weight": keyword_norm,
                "semantic_weight": semantic_norm,
                "pipeline_name": pipeline_name,
                "hits": hits,
            }
        )

    return {
        "query": query_text,
        "weight_results": weight_results,
    }


def main() -> int:
    print("Reading embedding manifest...")
    manifest = read_manifest()

    model_name = manifest.get("embedding_model", "all-MiniLM-L6-v2")
    expected_dimension = int(manifest.get("embedding_dimension", 384))
    expected_count = manifest.get("record_count")
    expected_count_int = int(expected_count) if expected_count is not None else None
    weight_sets = parse_weight_sets(WEIGHT_SETS)

    print(f"Using index: {INDEX_NAME}")
    print(f"Using text field: {TEXT_FIELD}")
    print(f"Using embedding field: {EMBEDDING_FIELD}")
    print(f"Using embedding model: {model_name}")
    print(f"Expected embedding dimension: {expected_dimension}")
    print(f"Weight sets: {weight_sets}")

    client = create_client()

    print("Verifying OpenSearch connection...")
    info = client.info()
    print(f"Connected to OpenSearch cluster: {info.get('cluster_name')}")

    print("Verifying index and mapping...")
    document_count = verify_index(client, expected_count_int)
    verify_mapping(client, expected_dimension)
    print(f"Document count: {document_count}")

    print("Loading embedding model...")
    model = load_model(manifest)

    queries = []
    for query_text in SAMPLE_QUERIES:
        queries.append(compare_weight_sets(client, model, query_text, weight_sets))

    results = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "index": INDEX_NAME,
        "document_count": document_count,
        "embedding_model": model_name,
        "embedding_dimension": expected_dimension,
        "text_field": TEXT_FIELD,
        "embedding_field": EMBEDDING_FIELD,
        "top_k": TOP_K,
        "candidate_k": CANDIDATE_K,
        "weight_sets": [
            {
                "keyword_weight": normalized_weights(k, s)[0],
                "semantic_weight": normalized_weights(k, s)[1],
            }
            for k, s in weight_sets
        ],
        "queries": queries,
    }

    write_results(results)
    write_markdown_summary(results)

    print("\n" + "=" * 100)
    print(f"Wrote JSON results: {RESULTS_PATH}")
    print(f"Wrote Markdown summary: {SUMMARY_PATH}")
    print("Done.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (NotFoundError, RequestError) as exc:
        print(f"OpenSearch request failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
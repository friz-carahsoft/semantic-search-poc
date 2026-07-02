from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import NotFoundError, RequestError
from sentence_transformers import SentenceTransformer

INDEX_NAME = os.getenv("OPENSEARCH_INDEX", "quotes-v1")
PIPELINE_NAME = os.getenv("OPENSEARCH_HYBRID_PIPELINE", "quotes-hybrid-pipeline")
TEXT_FIELD = os.getenv("SEARCH_TEXT_FIELD", "search_text")
EMBEDDING_FIELD = os.getenv("EMBEDDING_FIELD", "quote_embedding")
MANIFEST_PATH = Path(os.getenv("EMBEDDING_MANIFEST_PATH", "data/embedding-manifest.json"))
PIPELINE_PATH = Path("opensearch/quotes-hybrid-search-pipeline.json")
RESULTS_PATH = Path("opensearch/search-comparison-results.json")
SUMMARY_PATH = Path("opensearch/search-comparison-summary.md")

TOP_K = int(os.getenv("TOP_K", "5"))
CANDIDATE_K = int(os.getenv("CANDIDATE_K", "10"))
KEYWORD_WEIGHT = float(os.getenv("KEYWORD_WEIGHT", "0.5"))
SEMANTIC_WEIGHT = float(os.getenv("SEMANTIC_WEIGHT", "0.5"))

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
            f"Manifest not found: {MANIFEST_PATH}. Run Step 5 before Step 8."
        )

    with MANIFEST_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_hybrid_pipeline_body() -> dict[str, Any]:
    """Build the OpenSearch search pipeline used to normalize hybrid scores."""
    total_weight = KEYWORD_WEIGHT + SEMANTIC_WEIGHT
    if total_weight <= 0:
        raise ValueError("KEYWORD_WEIGHT + SEMANTIC_WEIGHT must be greater than 0")

    keyword_weight = KEYWORD_WEIGHT / total_weight
    semantic_weight = SEMANTIC_WEIGHT / total_weight

    return {
        "description": "Hybrid search pipeline for the quotes semantic-search POC",
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
                                keyword_weight,
                                semantic_weight,
                            ]
                        },
                    },
                }
            }
        ],
    }


def write_pipeline_file(pipeline_body: dict[str, Any]) -> None:
    """Write the pipeline JSON to disk so the team can inspect it."""
    PIPELINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with PIPELINE_PATH.open("w", encoding="utf-8") as file:
        json.dump(pipeline_body, file, indent=2, ensure_ascii=False)
        file.write("\n")


def create_or_update_search_pipeline(client: OpenSearch) -> None:
    """Create or update the OpenSearch search pipeline used by hybrid queries."""
    pipeline_body = build_hybrid_pipeline_body()
    write_pipeline_file(pipeline_body)

    path = f"/_search/pipeline/{PIPELINE_NAME}"
    client.transport.perform_request("PUT", path, body=pipeline_body)


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
    """Convert the user's query text into a vector."""
    vector = model.encode(query_text, convert_to_numpy=True)
    return [float(value) for value in vector.tolist()]


def source_filter() -> dict[str, Any]:
    """Exclude embedding vectors from search responses to keep output readable."""
    return {
        "excludes": [EMBEDDING_FIELD],
    }


def keyword_query(query_text: str) -> dict[str, Any]:
    """Build the keyword portion of the comparison."""
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
    """Build the vector portion of the comparison."""
    return {
        "knn": {
            EMBEDDING_FIELD: {
                "vector": query_vector,
                "k": k,
            }
        }
    }


def keyword_search(client: OpenSearch, query_text: str, top_k: int) -> dict[str, Any]:
    """Run keyword-only search."""
    body = {
        "size": top_k,
        "_source": source_filter(),
        "query": keyword_query(query_text),
    }

    return client.search(index=INDEX_NAME, body=body)


def semantic_search(
    client: OpenSearch, query_text: str, query_vector: list[float], top_k: int, candidate_k: int
) -> dict[str, Any]:
    """Run semantic-only k-NN search."""
    body = {
        "size": top_k,
        "_source": source_filter(),
        "query": semantic_query(query_vector, max(top_k, candidate_k)),
    }

    return client.search(index=INDEX_NAME, body=body)


def hybrid_search(
    client: OpenSearch, query_text: str, query_vector: list[float], top_k: int, candidate_k: int
) -> dict[str, Any]:
    """Run OpenSearch hybrid search using keyword and k-NN subqueries."""
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
        params={"search_pipeline": PIPELINE_NAME},
    )


def simplify_hits(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert OpenSearch hits to a compact structure for comparison."""
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


def top_line(method_name: str, hits: list[dict[str, Any]]) -> str:
    """Return one printable line for the top result of a search method."""
    if not hits:
        return f"{method_name:<9} | no results"

    top_hit = hits[0]
    quote = str(top_hit.get("quote", ""))
    if len(quote) > 90:
        quote = quote[:87] + "..."

    score = top_hit.get("score")
    score_display = f"{score:.6f}" if isinstance(score, (int, float)) else str(score)

    return (
        f"{method_name:<9} | rank 1 | score {score_display:<10} | "
        f"{top_hit.get('id')} | {quote}"
    )


def compare_query(
    client: OpenSearch,
    model: SentenceTransformer,
    query_text: str,
    top_k: int,
    candidate_k: int,
) -> dict[str, Any]:
    """Run keyword, semantic, and hybrid searches for one query."""
    query_vector = embed_query(model, query_text)

    keyword_response = keyword_search(client, query_text, top_k)
    semantic_response = semantic_search(client, query_text, query_vector, top_k, candidate_k)
    hybrid_response = hybrid_search(client, query_text, query_vector, top_k, candidate_k)

    keyword_hits = simplify_hits(keyword_response)
    semantic_hits = simplify_hits(semantic_response)
    hybrid_hits = simplify_hits(hybrid_response)

    print("\n" + "=" * 100)
    print(f"Query: {query_text}")
    print("-" * 100)
    print(top_line("Keyword", keyword_hits))
    print(top_line("Semantic", semantic_hits))
    print(top_line("Hybrid", hybrid_hits))

    return {
        "query": query_text,
        "keyword": keyword_hits,
        "semantic": semantic_hits,
        "hybrid": hybrid_hits,
    }


def write_results(results: dict[str, Any]) -> None:
    """Write full JSON comparison results."""
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)
        file.write("\n")


def format_score(score: Any) -> str:
    """Format a score for Markdown output."""
    if isinstance(score, (int, float)):
        return f"{score:.6f}"
    return ""


def markdown_row(method: str, hits: list[dict[str, Any]]) -> str:
    """Create one Markdown table row for a method's top result."""
    if not hits:
        return f"| {method} | No results |  |  |  |"

    top_hit = hits[0]
    quote = str(top_hit.get("quote", "")).replace("|", "\\|")
    author = str(top_hit.get("author", "")).replace("|", "\\|")
    category = str(top_hit.get("category", "")).replace("|", "\\|")
    score = format_score(top_hit.get("score"))

    return f"| {method} | `{top_hit.get('id')}` | {score} | {category} | {quote} — {author} |"


def write_markdown_summary(results: dict[str, Any]) -> None:
    """Write a human-readable Markdown comparison summary."""
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Step 8 Search Comparison Summary",
        "",
        f"Generated at: `{results['generated_at_utc']}`",
        "",
        "This file summarizes the top result from keyword, semantic, and hybrid search for each test query.",
        "",
        "Scores are useful within a method, but raw keyword scores and raw vector scores should not be compared directly. Hybrid search uses a search pipeline to normalize and combine scores.",
        "",
    ]

    for comparison in results["comparisons"]:
        lines.extend(
            [
                f"## Query: `{comparison['query']}`",
                "",
                "| Method | Top ID | Score | Category | Top Result |",
                "| --- | --- | ---: | --- | --- |",
                markdown_row("Keyword", comparison["keyword"]),
                markdown_row("Semantic", comparison["semantic"]),
                markdown_row("Hybrid", comparison["hybrid"]),
                "",
            ]
        )

    lines.extend(
        [
            "## Review Questions",
            "",
            "Use this output to discuss:",
            "",
            "- Which queries worked well with keyword search?",
            "- Which queries worked better with semantic search?",
            "- Did hybrid search preserve useful exact matches while also finding meaning-based matches?",
            "- Are the default hybrid weights reasonable for this dataset?",
            "- Which result would a business user consider the best answer?",
            "",
        ]
    )

    with SUMMARY_PATH.open("w", encoding="utf-8") as file:
        file.write("\n".join(lines))
        file.write("\n")


def main() -> int:
    print("Reading embedding manifest...")
    manifest = read_manifest()

    model_name = manifest.get("embedding_model", "all-MiniLM-L6-v2")
    expected_dimension = int(manifest.get("embedding_dimension", 384))
    expected_count = manifest.get("record_count")
    expected_count_int = int(expected_count) if expected_count is not None else None

    print(f"Using index: {INDEX_NAME}")
    print(f"Using text field: {TEXT_FIELD}")
    print(f"Using embedding field: {EMBEDDING_FIELD}")
    print(f"Using embedding model: {model_name}")
    print(f"Expected embedding dimension: {expected_dimension}")
    print(f"Hybrid weights: keyword={KEYWORD_WEIGHT}, semantic={SEMANTIC_WEIGHT}")

    client = create_client()

    print("Verifying OpenSearch connection...")
    info = client.info()
    print(f"Connected to OpenSearch cluster: {info.get('cluster_name')}")

    print("Verifying index and mapping...")
    document_count = verify_index(client, expected_count_int)
    verify_mapping(client, expected_dimension)
    print(f"Document count: {document_count}")

    print("Creating or updating hybrid search pipeline...")
    create_or_update_search_pipeline(client)
    print(f"Hybrid search pipeline ready: {PIPELINE_NAME}")
    print(f"Wrote pipeline definition: {PIPELINE_PATH}")

    print("Loading embedding model...")
    model = load_model(manifest)

    comparisons = []
    for query_text in SAMPLE_QUERIES:
        comparisons.append(
            compare_query(
                client=client,
                model=model,
                query_text=query_text,
                top_k=TOP_K,
                candidate_k=CANDIDATE_K,
            )
        )

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
        "hybrid_pipeline": PIPELINE_NAME,
        "hybrid_weights": {
            "keyword": KEYWORD_WEIGHT,
            "semantic": SEMANTIC_WEIGHT,
        },
        "comparisons": comparisons,
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
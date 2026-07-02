#!/usr/bin/env python3
"""Run semantic k-NN searches against the OpenSearch quotes-v1 index."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError, OpenSearchException
from sentence_transformers import SentenceTransformer


DEFAULT_HOST = os.getenv("OPENSEARCH_HOST", "https://localhost:9200")
DEFAULT_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
DEFAULT_INDEX_NAME = os.getenv("OPENSEARCH_INDEX", "quotes-v1")
DEFAULT_MANIFEST_PATH = Path(os.getenv("EMBEDDING_MANIFEST_PATH", "data/embedding-manifest.json"))
DEFAULT_RESULTS_PATH = Path(os.getenv("SEMANTIC_RESULTS_PATH", "opensearch/semantic-search-results.json"))
DEFAULT_TOP_K = int(os.getenv("SEMANTIC_TOP_K", "5"))

PASSWORD_ENV_NAMES = (
    "OPENSEARCH_PASSWORD",
    "OPENSEARCH_INITIAL_ADMIN_PASSWORD",
)

DEFAULT_DEMO_QUERIES = [
    "quotes about not giving up",
    "quotes about curiosity and discovery",
    "quotes about wise choices",
    "quotes about courageous leadership",
    "funny quotes about mistakes",
]


class SemanticSearchError(RuntimeError):
    """Raised when the semantic-search workflow cannot continue."""


def get_password() -> str:
    """Read the OpenSearch password from a supported environment variable."""
    for env_name in PASSWORD_ENV_NAMES:
        value = os.getenv(env_name)
        if value:
            return value

    raise SemanticSearchError(
        "Missing OpenSearch password. Set OPENSEARCH_PASSWORD or "
        "OPENSEARCH_INITIAL_ADMIN_PASSWORD before running this script."
    )


def create_client() -> OpenSearch:
    """Create a local OpenSearch client for the POC environment."""
    password = get_password()

    return OpenSearch(
        hosts=[DEFAULT_HOST],
        http_auth=(DEFAULT_USERNAME, password),
        use_ssl=DEFAULT_HOST.startswith("https"),
        verify_certs=False,
        ssl_show_warn=False,
        timeout=30,
        max_retries=3,
        retry_on_timeout=True,
    )


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and validate the embedding manifest created in Step 5."""
    if not path.exists():
        raise SemanticSearchError(f"Embedding manifest not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    required_fields = [
        "embedding_model",
        "embedding_dimension",
        "embedding_field",
        "opensearch_index",
        "record_count",
    ]

    missing = [field for field in required_fields if field not in manifest]
    if missing:
        raise SemanticSearchError(
            f"Embedding manifest is missing required fields: {', '.join(missing)}"
        )

    return manifest


def verify_index(client: OpenSearch, index_name: str, expected_count: int) -> None:
    """Confirm the OpenSearch index exists and contains documents."""
    if not client.indices.exists(index=index_name):
        raise SemanticSearchError(
            f"Index '{index_name}' does not exist. Run Step 4 before this step."
        )

    count_response = client.count(index=index_name)
    actual_count = int(count_response.get("count", 0))

    if actual_count == 0:
        raise SemanticSearchError(
            f"Index '{index_name}' contains 0 documents. Run Step 6 before this step."
        )

    if actual_count != expected_count:
        print(
            f"Warning: index contains {actual_count} documents, "
            f"but manifest expected {expected_count} documents."
        )


def get_field_mapping(client: OpenSearch, index_name: str, field_name: str) -> dict[str, Any]:
    """Return the mapping definition for a field in the OpenSearch index."""
    mapping_response = client.indices.get_mapping(index=index_name)

    index_mapping = mapping_response.get(index_name, {}).get("mappings", {})
    properties = index_mapping.get("properties", {})

    field_mapping = properties.get(field_name)
    if not field_mapping:
        raise SemanticSearchError(
            f"Field '{field_name}' was not found in the '{index_name}' mapping."
        )

    return field_mapping


def verify_vector_mapping(
    client: OpenSearch,
    index_name: str,
    embedding_field: str,
    embedding_dimension: int,
) -> None:
    """Confirm the vector field exists and matches the expected dimension."""
    field_mapping = get_field_mapping(client, index_name, embedding_field)

    field_type = field_mapping.get("type")
    if field_type != "knn_vector":
        raise SemanticSearchError(
            f"Field '{embedding_field}' has type '{field_type}', expected 'knn_vector'."
        )

    actual_dimension = int(field_mapping.get("dimension", 0))
    if actual_dimension != embedding_dimension:
        raise SemanticSearchError(
            f"Field '{embedding_field}' has dimension {actual_dimension}, "
            f"expected {embedding_dimension}."
        )


def encode_query(model: SentenceTransformer, query_text: str, expected_dimension: int) -> list[float]:
    """Convert query text into an embedding vector."""
    vector = model.encode(query_text, convert_to_numpy=True)
    values = [float(value) for value in vector.tolist()]

    if len(values) != expected_dimension:
        raise SemanticSearchError(
            f"Query embedding has dimension {len(values)}, expected {expected_dimension}."
        )

    bad_values = [value for value in values if not math.isfinite(value)]
    if bad_values:
        raise SemanticSearchError("Query embedding contains non-finite numeric values.")

    return values


def build_knn_query(
    embedding_field: str,
    query_vector: list[float],
    top_k: int,
    category: str | None = None,
) -> dict[str, Any]:
    """Build the OpenSearch k-NN query body."""
    knn_payload: dict[str, Any] = {
        "vector": query_vector,
        "k": top_k,
    }

    if category:
        knn_payload["filter"] = {
            "term": {
                "category": category,
            }
        }

    return {
        "size": top_k,
        "_source": {
            "excludes": [embedding_field],
        },
        "query": {
            "knn": {
                embedding_field: knn_payload,
            }
        },
    }


def run_semantic_search(
    client: OpenSearch,
    index_name: str,
    embedding_field: str,
    model: SentenceTransformer,
    query_text: str,
    top_k: int,
    embedding_dimension: int,
    category: str | None = None,
) -> dict[str, Any]:
    """Embed the query text and run a k-NN search against OpenSearch."""
    query_vector = encode_query(model, query_text, embedding_dimension)
    search_body = build_knn_query(
        embedding_field=embedding_field,
        query_vector=query_vector,
        top_k=top_k,
        category=category,
    )

    response = client.search(index=index_name, body=search_body)
    hits = response.get("hits", {}).get("hits", [])

    results: list[dict[str, Any]] = []
    for rank, hit in enumerate(hits, start=1):
        source = hit.get("_source", {})
        results.append(
            {
                "rank": rank,
                "score": hit.get("_score"),
                "id": hit.get("_id"),
                "quote": source.get("quote"),
                "author": source.get("author"),
                "category": source.get("category"),
                "tags": source.get("tags", []),
            }
        )

    return {
        "query": query_text,
        "top_k": top_k,
        "category_filter": category,
        "result_count": len(results),
        "results": results,
    }


def print_results(search_result: dict[str, Any]) -> None:
    """Print semantic-search results in a readable terminal format."""
    query = search_result["query"]
    category_filter = search_result.get("category_filter")

    print("\n" + "=" * 80)
    print(f"Query: {query}")
    if category_filter:
        print(f"Category filter: {category_filter}")
    print("=" * 80)

    if not search_result["results"]:
        print("No results found.")
        return

    for result in search_result["results"]:
        score = result["score"]
        score_text = f"{score:.6f}" if isinstance(score, (int, float)) else str(score)

        print(f"\n{result['rank']}. {result['quote']}")
        print(f"   Author: {result['author']}")
        print(f"   Category: {result['category']}")
        print(f"   Tags: {', '.join(result.get('tags', []))}")
        print(f"   Score: {score_text}")


def write_results(path: Path, payload: dict[str, Any]) -> None:
    """Write search results to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run semantic k-NN quote searches against OpenSearch."
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Search query text, for example: 'quotes about not giving up'",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a small set of demonstration semantic-search queries.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Number of nearest-neighbor results to return. Default: {DEFAULT_TOP_K}",
    )
    parser.add_argument(
        "--category",
        help="Optional exact category filter, for example: science, leadership, humor.",
    )
    parser.add_argument(
        "--results-path",
        default=str(DEFAULT_RESULTS_PATH),
        help=f"Path for saved JSON results. Default: {DEFAULT_RESULTS_PATH}",
    )

    args = parser.parse_args()

    if args.top_k < 1:
        parser.error("--top-k must be at least 1")

    if not args.demo and not args.query:
        parser.error("Provide a query or use --demo")

    return args


def main() -> int:
    """Run the semantic-search workflow."""
    args = parse_args()

    manifest = load_manifest(DEFAULT_MANIFEST_PATH)
    model_name = str(manifest["embedding_model"])
    embedding_dimension = int(manifest["embedding_dimension"])
    embedding_field = str(manifest["embedding_field"])
    index_name = str(manifest.get("opensearch_index", DEFAULT_INDEX_NAME))
    expected_count = int(manifest.get("record_count", 0))

    print(f"OpenSearch host: {DEFAULT_HOST}")
    print(f"OpenSearch index: {index_name}")
    print(f"Embedding model: {model_name}")
    print(f"Embedding dimension: {embedding_dimension}")
    print(f"Embedding field: {embedding_field}")

    client = create_client()
    info = client.info()
    print(f"Connected to OpenSearch: {info.get('version', {}).get('number', 'unknown')}")

    verify_index(client, index_name, expected_count)
    verify_vector_mapping(client, index_name, embedding_field, embedding_dimension)

    print("Loading embedding model...")
    model = SentenceTransformer(model_name)

    queries = DEFAULT_DEMO_QUERIES if args.demo else [args.query]
    all_results: list[dict[str, Any]] = []

    for query_text in queries:
        assert query_text is not None
        search_result = run_semantic_search(
            client=client,
            index_name=index_name,
            embedding_field=embedding_field,
            model=model,
            query_text=query_text,
            top_k=args.top_k,
            embedding_dimension=embedding_dimension,
            category=args.category,
        )
        print_results(search_result)
        all_results.append(search_result)

    output_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "opensearch_host": DEFAULT_HOST,
        "opensearch_index": index_name,
        "embedding_model": model_name,
        "embedding_dimension": embedding_dimension,
        "embedding_field": embedding_field,
        "search_type": "semantic_knn",
        "queries": all_results,
    }

    results_path = Path(args.results_path)
    write_results(results_path, output_payload)
    print(f"\nWrote semantic-search results: {results_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SemanticSearchError, NotFoundError, OpenSearchException) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
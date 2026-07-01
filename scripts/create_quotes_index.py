from __future__ import annotations

import json
import os
import sys
from typing import Any

from opensearchpy import OpenSearch, RequestsHttpConnection
from sentence_transformers import SentenceTransformer

INDEX_NAME = os.getenv("OPENSEARCH_INDEX", "quotes-v1")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_FIELD = "quote_embedding"


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


def get_embedding_dimension(model_name: str) -> int:
    """Load the embedding model and return its vector dimension."""
    model = SentenceTransformer(model_name)
    dimension = model.get_sentence_embedding_dimension()

    if dimension is None:
        raise RuntimeError(f"Could not determine embedding dimension for {model_name}")

    return int(dimension)


def build_index_body(embedding_dimension: int) -> dict[str, Any]:
    """Build OpenSearch settings and mappings for the quotes index."""
    return {
        "settings": {
            "index": {
                "knn": True,
                "number_of_shards": 1,
                "number_of_replicas": 0,
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "quote": {"type": "text"},
                "author": {"type": "keyword"},
                "category": {"type": "keyword"},
                "tags": {"type": "keyword"},
                "source": {"type": "keyword"},
                "source_license": {"type": "keyword"},
                "search_text": {"type": "text"},
                EMBEDDING_FIELD: {
                    "type": "knn_vector",
                    "dimension": embedding_dimension,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "lucene",
                        "parameters": {
                            "ef_construction": 128,
                            "m": 16,
                        },
                    },
                },
            }
        },
    }


def main() -> int:
    reset_index = os.getenv("RESET_INDEX", "false").lower() == "true"

    print(f"Using embedding model: {EMBEDDING_MODEL_NAME}")
    embedding_dimension = get_embedding_dimension(EMBEDDING_MODEL_NAME)
    print(f"Embedding dimension: {embedding_dimension}")

    client = create_client()

    if not client.ping():
        raise RuntimeError("Could not connect to OpenSearch at https://localhost:9200")

    if client.indices.exists(index=INDEX_NAME):
        if reset_index:
            print(f"Deleting existing index: {INDEX_NAME}")
            client.indices.delete(index=INDEX_NAME)
        else:
            print(f"Index already exists: {INDEX_NAME}")
            print("Set RESET_INDEX=true if you intentionally want to recreate it.")
            return 0

    index_body = build_index_body(embedding_dimension)

    print(f"Creating index: {INDEX_NAME}")
    response = client.indices.create(index=INDEX_NAME, body=index_body)

    print(json.dumps(response, indent=2))
    print("Index created successfully.")
    print(f"Vector field: {EMBEDDING_FIELD}")
    print(f"Vector dimension: {embedding_dimension}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
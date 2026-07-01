# Step 4: Creating the OpenSearch Index

This guide creates the OpenSearch index that will store quote text, metadata, and vector embeddings for the semantic-search proof of concept.

This step does **not** generate embeddings or index documents yet. It prepares the index structure so the next steps can safely generate embeddings and load data.

## Goal

By the end of this step, you should be able to:

- Confirm OpenSearch is running locally
- Confirm the k-NN plugin is available
- Choose a stable index name
- Determine the embedding dimension from the selected Sentence Transformers model
- Create an OpenSearch index with text fields, metadata fields, and a `knn_vector` field
- Verify the index settings and mappings
- Safely delete and recreate the index during local development

## Why this step matters

OpenSearch needs to know field types before documents are indexed.

For normal keyword and text fields, OpenSearch can often infer mappings automatically. For vector search, you should create the index explicitly because the vector field must define:

- field type: `knn_vector`
- embedding dimension
- vector search engine and method
- distance/similarity function

The embedding dimension must match the model output exactly. For example, `all-MiniLM-L6-v2` produces 384-dimensional vectors. If the index expects 384 values but you try to index 768 values, indexing will fail.

## Public Repository Notes

This guide is safe to include in a public GitHub repository.

Recommended practices:

- Do not hard-code real passwords or secrets in committed files.
- Read the OpenSearch password from an environment variable.
- Keep the index name stable so teammates can follow the same steps.
- Use a pinned or documented embedding model so vector dimensions are predictable.
- Treat local demo TLS settings as development-only.

The examples below use local OpenSearch demo security from Step 1. They intentionally disable certificate verification for the local self-signed demo certificate. Do not copy that TLS posture into production.

## Prerequisites

Before starting this step, complete:

- Step 1: Docker setup for OpenSearch
- Step 2: Python environment setup
- Step 3: Creating the sample quotes dataset

You should already have:

```text
semantic-search-poc/
├── data/
│   ├── quotes.csv
│   └── quotes.jsonl
├── docs/
|   ├── 0-semantic-search-poc.md 
|   ├── 1-opensearch-docker-setup.md
|   ├── 2-python-environment-setup.md
|   ├── 3-sample-quotes-dataset.md
│   └── 4-opensearch-index-setup.md
├── scripts/
│   ├── create_sample_quotes_dataset.py
│   └── create_quotes_index.py # created in this step
└── requirements.txt
```

You should also have these Python packages installed from Step 2:

- `sentence-transformers`
- `opensearch-py`
- `pandas`

## 1. Start or confirm OpenSearch is running

From any terminal, run:

```bash
docker ps
```

You should see a container named:

```text
opensearch-poc
```

If the container exists but is stopped, start it:

```bash
docker start opensearch-poc
```

If the container does not exist yet, return to Step 1 and create it first.

## 2. Set the OpenSearch password environment variable

Use the same password you used when starting the OpenSearch container in Step 1.

### macOS or Linux

```bash
export OPENSEARCH_INITIAL_ADMIN_PASSWORD='replace-with-your-local-password'
```

### Windows PowerShell

```powershell
$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD = 'replace-with-your-local-password'
```

Do not commit this value to Git.

## 3. Verify OpenSearch responds

### macOS or Linux

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200'
```

### Windows PowerShell

PowerShell aliases `curl` to `Invoke-WebRequest` on some systems. Use `curl.exe` to force the real curl executable.

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200"
```

You should receive a JSON response with OpenSearch cluster and version information.

Check cluster health.

macOS or Linux:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/_cluster/health?pretty'
```

Windows PowerShell:

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200/_cluster/health?pretty"
```

For this local single-node POC, `green` is fine and `yellow` can also be normal.

## 4. Confirm the k-NN plugin is available

Run.

macOS or Linux:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/_cat/plugins?v'
```

Windows PowerShell:

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200/_cat/plugins?v"
```

Look for a plugin row containing:

```text
opensearch-knn
```

If you do not see that plugin, do not continue. Return to Step 1 and confirm you are using an OpenSearch image that includes the k-NN plugin.

## 5. Activate the Python virtual environment

From the project root:

### macOS or Linux

```bash
source .venv/bin/activate
```

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

Confirm Python is coming from the virtual environment:

```bash
python --version
```

## 6. Confirm the embedding model dimension

This POC uses the same model tested in Step 2:

```text
all-MiniLM-L6-v2
```

Run:

```bash
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); print(model.get_sentence_embedding_dimension())"
```

Expected output:

```text
384
```

That value is the dimension that the OpenSearch `knn_vector` field must use.

## 7. Create the index creation script

Create this file:

### macOS or Linux

```bash
touch scripts/create_quotes_index.py
```

### Windows PowerShell

```powershell
New-Item -ItemType File -Force -Path scripts/create_quotes_index.py
```

Open `scripts/create_quotes_index.py` and paste the following code:

```python
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
```

## 8. Run the index creation script

From the project root, with your virtual environment active and password environment variable set, run:

```bash
python scripts/create_quotes_index.py
```

Expected output should include something similar to:

```text
Using embedding model: all-MiniLM-L6-v2
Embedding dimension: 384
Creating index: quotes-v1
Index created successfully.
Vector field: quote_embedding
Vector dimension: 384
```

If you run the script again, it should not delete the index by default. You should see:

```text
Index already exists: quotes-v1
Set RESET_INDEX=true if you intentionally want to recreate it.
```

## 9. Verify the index exists

Run.

macOS or Linux:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/_cat/indices/quotes-v1?v'
```

Windows PowerShell:

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200/_cat/indices/quotes-v1?v"
```

You should see a row for:

```text
quotes-v1
```

Because this is a brand-new empty index, the document count should be `0`.

## 10. Verify the index mapping

Run.

macOS or Linux:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/quotes-v1/_mapping?pretty'
```

Windows PowerShell:

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200/quotes-v1/_mapping?pretty"
```

Look for these fields:

```text
quote
search_text
author
category
tags
quote_embedding
```

The `quote_embedding` field should be mapped as:

```json
{
  "type": "knn_vector",
  "dimension": 384
}
```

The mapping response will also include the vector method details.

## 11. Verify the index settings

Run.

macOS or Linux:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/quotes-v1/_settings?pretty'
```

Windows PowerShell:

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200/quotes-v1/_settings?pretty"
```

Look for:

```json
"knn": "true"
```

Also confirm this local POC setting:

```json
"number_of_replicas": "0"
```

For a single-node local development cluster, `number_of_replicas: 0` helps keep the index health green.

## 12. Optional: create a reusable curl index definition

The Python script is the recommended path because it derives the vector dimension from the embedding model.

If you want a static curl example for documentation or troubleshooting, create this file:

```text
opensearch/quotes-index.json
```

Recommended folder creation:

### macOS or Linux

```bash
mkdir -p opensearch
```

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force -Path opensearch
```

Paste this JSON into `opensearch/quotes-index.json`:

```json
{
  "settings": {
    "index": {
      "knn": true,
      "number_of_shards": 1,
      "number_of_replicas": 0
    }
  },
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "quote": { "type": "text" },
      "author": { "type": "keyword" },
      "category": { "type": "keyword" },
      "tags": { "type": "keyword" },
      "source": { "type": "keyword" },
      "source_license": { "type": "keyword" },
      "search_text": { "type": "text" },
      "quote_embedding": {
        "type": "knn_vector",
        "dimension": 384,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "lucene",
          "parameters": {
            "ef_construction": 128,
            "m": 16
          }
        }
      }
    }
  }
}
```

You can create the index from this file with:

macOS or Linux:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" \
  -X PUT 'https://localhost:9200/quotes-v1' \
  -H 'Content-Type: application/json' \
  --data-binary '@opensearch/quotes-index.json'
```

Windows PowerShell:

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" `
  -X PUT "https://localhost:9200/quotes-v1" `
  -H "Content-Type: application/json" `
  --data-binary "@opensearch/quotes-index.json"
```

Only use the static JSON version if you are confident the model dimension is still `384`.

## 13. Optional: delete and recreate the index

During local development, you may want to recreate the index after changing mappings.

Mappings for existing fields cannot always be changed in place. For a small local POC, the simplest approach is often to delete and recreate the index before loading data.

### Recreate using the Python script

macOS or Linux:

```bash
RESET_INDEX=true python scripts/create_quotes_index.py
```

Windows PowerShell:

```powershell
$env:RESET_INDEX = 'true'
python scripts/create_quotes_index.py
$env:RESET_INDEX = 'false'
```

### Delete using curl

macOS or Linux:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" \
  -X DELETE 'https://localhost:9200/quotes-v1'
```

Windows PowerShell:

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" `
  -X DELETE "https://localhost:9200/quotes-v1"
```

Be careful: deleting the index removes all documents stored in that index.

## 14. Recommended git commit

Review the files:

```bash
git status
```

Recommended commit:

```bash
git add scripts/create_quotes_index.py
git commit -m "Add OpenSearch quotes index setup"
```

If you also created the optional static JSON mapping file, include it:

```bash
git add scripts/create_quotes_index.py opensearch/quotes-index.json
git commit -m "Add OpenSearch quotes index setup"
```

Do not commit local passwords, `.venv/`, cache folders, or machine-specific configuration.

## Field Design Notes

### `quote`

The main text field from the sample dataset. This is the field to embed first in the next step.

### `search_text`

A combined text field from the sample dataset. It can be useful later for keyword search or hybrid experiments.

### `category`, `author`, and `tags`

These are mapped as `keyword` fields so they can be used for exact filters and aggregations.

Examples later:

- filter to only `science` quotes
- facet by `category`
- filter by a specific synthetic author
- filter by tags such as `resilience`, `curiosity`, or `leadership`

### `quote_embedding`

The vector field that will store embeddings generated from the quote text.

For this POC:

- model: `all-MiniLM-L6-v2`
- vector dimension: `384`
- engine: `lucene`
- method: `hnsw`
- space type: `cosinesimil`

Cosine similarity is a good default for sentence embedding similarity because it compares vector direction rather than raw magnitude.

## Troubleshooting

### `Missing OpenSearch password`

Set the password environment variable before running the script.

macOS or Linux:

```bash
export OPENSEARCH_INITIAL_ADMIN_PASSWORD='replace-with-your-local-password'
```

Windows PowerShell:

```powershell
$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD = 'replace-with-your-local-password'
```

### `Could not connect to OpenSearch at https://localhost:9200`

Check whether the container is running:

```bash
docker ps
```

If it is stopped:

```bash
docker start opensearch-poc
```

Then verify with curl.

macOS or Linux:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200'
```

Windows PowerShell:

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200"
```

### `AuthenticationException` or `401 Unauthorized`

The password in your environment variable does not match the OpenSearch admin password.

Set it again in the same terminal session and retry.

### `ModuleNotFoundError: No module named 'opensearchpy'`

Your virtual environment may not be active, or the Step 2 dependencies may not be installed.

Activate the virtual environment and install dependencies:

```bash
source .venv/bin/activate
python -m pip install sentence-transformers opensearch-py pandas
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install sentence-transformers opensearch-py pandas
```

### `resource_already_exists_exception`

The index already exists.

Either keep the existing index or intentionally recreate it:

```bash
RESET_INDEX=true python scripts/create_quotes_index.py
```

### `mapper_parsing_exception` involving vector dimension

The `knn_vector` dimension does not match the embedding size.

Confirm the model dimension:

```bash
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); print(model.get_sentence_embedding_dimension())"
```

Then delete and recreate the index with the correct dimension.

### zsh reports `no matches found`

If you are using `zsh`, unquoted URLs containing `?` can be treated as wildcard patterns. Keep URLs wrapped in single quotes as shown in this guide.

## Result

After this step, OpenSearch should contain an empty index named:

```text
quotes-v1
```

The index should include:

- text fields for quote content
- keyword fields for metadata and filtering
- a `quote_embedding` `knn_vector` field sized to the selected embedding model
- local development settings suitable for a single-node OpenSearch container

The project is now ready for the next phase: generating embeddings for the sample quotes and preparing documents for bulk indexing.

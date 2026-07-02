# Step 8: Compare Keyword, Semantic, and Hybrid Search

This guide compares three search approaches against the same `quotes-v1` OpenSearch index:

1. **Keyword search** using traditional text matching
2. **Semantic search** using query embeddings and k-NN vector search
3. **Hybrid search** combining keyword and semantic relevance with an OpenSearch search pipeline

This is the first step where the POC directly demonstrates the business value of semantic search: finding useful results by meaning, not only by exact words.

## Goal

By the end of this step, you should be able to:

- Run keyword-only searches against quote text
- Run semantic-only searches against stored quote vectors
- Create an OpenSearch search pipeline for hybrid search
- Run hybrid queries that combine keyword and vector relevance
- Compare result rankings side by side
- Explain when keyword, semantic, and hybrid search each perform best
- Save comparison results for team review

## Why this step matters

Keyword search and semantic search solve related but different problems.

**Keyword search** is strong when the user knows a specific word, phrase, name, identifier, or exact term.

Examples:

```text
leadership
curiosity
quote-0007
```

**Semantic search** is strong when the user expresses an idea, topic, or intent using words that may not appear in the document.

Examples:

```text
quotes about not giving up
ideas about learning from mistakes
wisdom about leading with humility
```

**Hybrid search** attempts to combine both strengths:

- keyword search preserves exact lexical matches
- semantic search finds meaning-based matches
- score normalization combines the two result sets into one ranked list

For many production search systems, hybrid search is often the most practical default because it handles both exact-match and meaning-based use cases.

## Public Repository Notes

This guide is safe to include in a public GitHub repository.

Recommended practices:

- Commit the comparison script.
- Commit the hybrid search pipeline JSON because it documents how scores are combined.
- For this small POC, it is reasonable to commit the generated comparison output as an example.
- Do not commit OpenSearch passwords or local secrets.
- Keep local credentials in environment variables.
- Do not treat local self-signed TLS settings as production guidance.

This POC uses local OpenSearch demo security from Step 1. The examples use HTTPS with certificate verification disabled because the local Docker container uses a self-signed demo certificate.

## Prerequisites

Before starting this step, complete:

- Step 1: Docker setup for OpenSearch
- Step 2: Python environment setup
- Step 3: Creating the sample quotes dataset
- Step 4: Creating the OpenSearch index
- Step 5: Generating embeddings for the sample quotes
- Step 6: Bulk indexing embedded quote documents
- Step 7: Performing semantic search

You should already have:

```text
semantic-search-poc/
├── data/
│   ├── quotes.csv
│   ├── quotes.jsonl
│   ├── quotes-with-embeddings.jsonl
│   ├── quotes-bulk.ndjson
│   └── embedding-manifest.json
├── docs/
│   ├── 0-semantic-search-poc.md
│   ├── 1-opensearch-docker-setup.md
│   ├── 2-python-environment-setup.md
│   ├── 3-sample-quotes-dataset.md
│   ├── 4-opensearch-index-setup.md
│   ├── 5-generate-quote-embeddings.md
│   ├── 6-bulk-index-quotes.md
│   ├── 7-semantic-search-quotes.md
│   └── 8-compare-search-methods.md
├── opensearch/
│   ├── quotes-index.json
│   ├── verified-index-mapping.json
│   ├── bulk-index-summary.json
│   └── semantic-search-results.json
├── scripts/
│   ├── bulk_index_quotes.py
│   ├── create_quotes_index.py
│   ├── create_sample_quotes_dataset.py
│   ├── generate_quote_embeddings.py
│   └── semantic_search_quotes.py
└── requirements.txt
```

You should also have the indexed `quotes-v1` documents in your local OpenSearch instance.

## Files created by this step

This step creates the following files:

```text
opensearch/
├── quotes-hybrid-search-pipeline.json
├── search-comparison-results.json
└── search-comparison-summary.md

scripts/
└── compare_search_methods.py
```

### Output file purpose

| File | Purpose |
| --- | --- |
| `scripts/compare_search_methods.py` | Runs keyword, semantic, and hybrid searches for the same test queries |
| `opensearch/quotes-hybrid-search-pipeline.json` | Defines the score normalization and combination strategy for hybrid search |
| `opensearch/search-comparison-results.json` | Full JSON output for team review and troubleshooting |
| `opensearch/search-comparison-summary.md` | Human-readable comparison summary |

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

## 2. Activate the Python virtual environment

From the project root, activate the virtual environment created in Step 2.

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

## 3. Set the OpenSearch password environment variable

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

## 4. Confirm the index contains documents

Run:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" \
  'https://localhost:9200/quotes-v1/_count?pretty'
```

Expected result:

```json
{
  "count": 50,
  "_shards": {
    "total": 1,
    "successful": 1,
    "skipped": 0,
    "failed": 0
  }
}
```

If the count is `0` or the index does not exist, return to Step 6 and bulk index the quote documents first.

## 5. Create the comparison script file

Create this file:

### macOS or Linux

```bash
touch scripts/compare_search_methods.py
```

### Windows PowerShell

```powershell
New-Item -ItemType File -Force -Path scripts/compare_search_methods.py
```

Open `scripts/compare_search_methods.py` and paste the following code:

```python
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
```

## 6. Understand what the script does

The script performs the following work:

1. Reads `data/embedding-manifest.json` from Step 5.
2. Loads the same embedding model used to generate document vectors.
3. Verifies the `quotes-v1` index exists.
4. Verifies the index contains quote documents.
5. Verifies the `quote_embedding` vector field dimension matches the model.
6. Creates or updates an OpenSearch search pipeline named `quotes-hybrid-pipeline`.
7. Runs keyword, semantic, and hybrid search for the same query list.
8. Prints top-result comparisons to the terminal.
9. Writes full JSON comparison output.
10. Writes a compact Markdown comparison summary.

The hybrid search pipeline uses:

```text
normalization: min_max
combination: arithmetic_mean
weights: 50% keyword, 50% semantic
```

The weights are intentionally equal for the first comparison. Later, the team can tune them.

## 7. Run the comparison script

Run:

```bash
python scripts/compare_search_methods.py
```

The first run may take a moment because Sentence Transformers loads the embedding model.

You should see output similar to:

```text
Reading embedding manifest...
Using index: quotes-v1
Using text field: search_text
Using embedding field: quote_embedding
Using embedding model: all-MiniLM-L6-v2
Expected embedding dimension: 384
Hybrid weights: keyword=0.5, semantic=0.5
Verifying OpenSearch connection...
Connected to OpenSearch cluster: docker-cluster
Verifying index and mapping...
Document count: 50
Creating or updating hybrid search pipeline...
Hybrid search pipeline ready: quotes-hybrid-pipeline
Wrote pipeline definition: opensearch/quotes-hybrid-search-pipeline.json
Loading embedding model...

====================================================================================================
Query: perseverance
----------------------------------------------------------------------------------------------------
Keyword   | rank 1 | score ... | quote-... | ...
Semantic  | rank 1 | score ... | quote-... | ...
Hybrid    | rank 1 | score ... | quote-... | ...
```

Exact scores and rankings may vary slightly by OpenSearch version, model/runtime behavior, or dataset changes.

## 8. Confirm the generated files exist

### macOS or Linux

```bash
ls -lh \
  opensearch/quotes-hybrid-search-pipeline.json \
  opensearch/search-comparison-results.json \
  opensearch/search-comparison-summary.md
```

### Windows PowerShell

```powershell
Get-ChildItem `
  opensearch\quotes-hybrid-search-pipeline.json, `
  opensearch\search-comparison-results.json, `
  opensearch\search-comparison-summary.md
```

## 9. Inspect the hybrid search pipeline JSON

Open:

```text
opensearch/quotes-hybrid-search-pipeline.json
```

You should see:

```json
{
  "description": "Hybrid search pipeline for the quotes semantic-search POC",
  "phase_results_processors": [
    {
      "normalization-processor": {
        "normalization": {
          "technique": "min_max"
        },
        "combination": {
          "technique": "arithmetic_mean",
          "parameters": {
            "weights": [
              0.5,
              0.5
            ]
          }
        }
      }
    }
  ]
}
```

The order of the weights matters:

```text
weights[0] = keyword query weight
weights[1] = semantic k-NN query weight
```

That is because the hybrid query sends the keyword subquery first and the semantic subquery second.

## 10. Inspect the Markdown summary

Open:

```text
opensearch/search-comparison-summary.md
```

This file is the most useful file for a quick human review.

For each test query, compare:

- top keyword result
- top semantic result
- top hybrid result

Discuss whether each result would satisfy a business user.

## 11. Inspect the full JSON output

Open:

```text
opensearch/search-comparison-results.json
```

This file includes the top results for each method and each test query.

It is useful for:

- debugging
- comparing IDs across methods
- inspecting categories and tags
- reviewing score behavior
- capturing expected output for this POC

## 12. Optional: change the number of returned results

By default, the script returns the top 5 results for each method.

To change that:

### macOS or Linux

```bash
TOP_K=10 python scripts/compare_search_methods.py
```

### Windows PowerShell

```powershell
$env:TOP_K = '10'
python scripts/compare_search_methods.py
```

The script also uses `CANDIDATE_K` for vector and hybrid candidate retrieval.

Example:

```bash
TOP_K=5 CANDIDATE_K=20 python scripts/compare_search_methods.py
```

For larger datasets, increasing candidate depth can sometimes improve hybrid result quality because more semantic candidates are available before final result selection.

## 13. Optional: tune hybrid weights

The default hybrid weighting is:

```text
keyword = 0.5
semantic = 0.5
```

To favor semantic matching more heavily:

### macOS or Linux

```bash
KEYWORD_WEIGHT=0.35 SEMANTIC_WEIGHT=0.65 python scripts/compare_search_methods.py
```

### Windows PowerShell

```powershell
$env:KEYWORD_WEIGHT = '0.35'
$env:SEMANTIC_WEIGHT = '0.65'
python scripts/compare_search_methods.py
```

To favor keyword matching more heavily:

```bash
KEYWORD_WEIGHT=0.70 SEMANTIC_WEIGHT=0.30 python scripts/compare_search_methods.py
```

After each run, inspect:

```text
opensearch/search-comparison-summary.md
```

For production tuning, do not choose weights based only on intuition. Use representative queries, expected results, business feedback, and relevance metrics.

## 14. Optional: manually inspect the OpenSearch pipeline

You can retrieve the pipeline directly from OpenSearch.

### macOS or Linux

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" \
  'https://localhost:9200/_search/pipeline/quotes-hybrid-pipeline?pretty'
```

### Windows PowerShell

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" `
  "https://localhost:9200/_search/pipeline/quotes-hybrid-pipeline?pretty"
```

## 15. Optional: manually run a keyword search

This is a keyword-only query.

### macOS or Linux

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" \
  -H 'Content-Type: application/json' \
  -X POST 'https://localhost:9200/quotes-v1/_search?pretty' \
  -d '{
    "size": 5,
    "_source": { "excludes": ["quote_embedding"] },
    "query": {
      "multi_match": {
        "query": "quotes about never giving up",
        "fields": ["quote^3", "search_text^2"],
        "type": "best_fields",
        "operator": "or"
      }
    }
  }'
```

### Windows PowerShell

```powershell
$body = @'
{
  "size": 5,
  "_source": { "excludes": ["quote_embedding"] },
  "query": {
    "multi_match": {
      "query": "quotes about never giving up",
      "fields": ["quote^3", "search_text^2"],
      "type": "best_fields",
      "operator": "or"
    }
  }
}
'@

curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" `
  -H "Content-Type: application/json" `
  -X POST "https://localhost:9200/quotes-v1/_search?pretty" `
  -d $body
```

## 16. Why there is no simple manual curl example for semantic or hybrid search

Semantic and hybrid search in this POC require a query vector.

That means this text:

```text
quotes about never giving up
```

must first be converted into a 384-dimensional vector using `all-MiniLM-L6-v2`.

The Python script does that conversion before submitting the semantic or hybrid query to OpenSearch.

You could manually paste the full vector into a curl command, but it would be long and difficult to review. The Python script is the cleaner approach.

## 17. Review the results as a team

Use the Markdown summary to discuss these questions:

1. Which searches worked best with exact keywords?
2. Which searches worked better semantically?
3. Did hybrid search improve the ranking or produce a better compromise?
4. Did any semantic result feel related but not useful?
5. Did any keyword result match words but miss intent?
6. What kinds of queries would real users submit in a production system?
7. Would the default behavior be keyword, semantic, or hybrid?
8. Would the answer change for short queries, long queries, IDs, filenames, names, or error codes?

Important distinction:

```text
A single-word query can still be semantic if the word represents a concept.
```

For example:

```text
resilience
leadership
curiosity
```

Those may benefit from semantic search.

But exact identifiers, filenames, codes, or proper nouns often need strong keyword handling.

## 18. Recommended commit

For this small POC, commit the script, pipeline JSON, and generated comparison output.

```bash
git status
git add \
  8-compare-search-methods.md \
  scripts/compare_search_methods.py \
  opensearch/quotes-hybrid-search-pipeline.json \
  opensearch/search-comparison-results.json \
  opensearch/search-comparison-summary.md
git commit -m "Compare keyword semantic and hybrid search"
git push
```

If your guide files live in a `docs/` folder, adjust the first path accordingly:

```bash
git add docs/8-compare-search-methods.md
```

## Troubleshooting

### `Missing OpenSearch password`

Set the password environment variable first.

### macOS or Linux

```bash
export OPENSEARCH_INITIAL_ADMIN_PASSWORD='replace-with-your-local-password'
```

### Windows PowerShell

```powershell
$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD = 'replace-with-your-local-password'
```

### `Index 'quotes-v1' does not exist`

Run Step 4 to create the index, then Step 6 to bulk index the quote documents.

### `Index contains 0 documents`

Run Step 6 again and verify the bulk indexing summary.

### `Embedding dimension mismatch`

The query embedding model, generated document embeddings, and OpenSearch index mapping do not agree.

For this POC, all three should use:

```text
all-MiniLM-L6-v2
384 dimensions
quote_embedding
```

If you changed the model, you may need to recreate the index, regenerate embeddings, and reindex documents.

### Hybrid query fails but keyword and semantic queries work

Confirm the search pipeline was created:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" \
  'https://localhost:9200/_search/pipeline/quotes-hybrid-pipeline?pretty'
```

If the pipeline does not exist, rerun:

```bash
python scripts/compare_search_methods.py
```

The script creates or updates the pipeline before running hybrid search.

### Hybrid scores look different from keyword or semantic scores

That is expected.

Keyword scores and vector scores are not directly comparable. The hybrid search pipeline normalizes and combines scores so both retrieval methods can contribute to final ranking.

### Semantic search returns related but unexpected results

That can happen. Semantic search finds nearby meaning, not guaranteed exact intent.

Review:

- whether the quote text is too short
- whether the query is ambiguous
- whether the embedding model is appropriate
- whether hybrid weighting should favor keyword more heavily
- whether additional metadata filters should be added later

### Results differ from another teammate's machine

Small score differences can occur across environments.

Check:

- OpenSearch version
- embedding model name
- `sentence-transformers` version
- whether the quote dataset changed
- whether the index was recreated after changing mappings
- hybrid weights

## Result

After this step, the project can compare keyword, semantic, and hybrid search results side by side.

The POC now demonstrates the central search tradeoff:

```text
Keyword search is strong for exact words.
Semantic search is strong for meaning.
Hybrid search attempts to combine both.
```

The project is now ready for the next phase: reviewing search quality, tuning hybrid weights, and documenting when each search approach should be used in a production implementation.

## References

- [OpenSearch hybrid search](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/)
- [OpenSearch hybrid query](https://docs.opensearch.org/latest/query-dsl/compound/hybrid/)
- [OpenSearch normalization processor](https://docs.opensearch.org/latest/search-plugins/search-pipelines/normalization-processor/)
- [OpenSearch k-NN query](https://docs.opensearch.org/latest/query-dsl/specialized/k-nn/)

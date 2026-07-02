# Step 9: Review Search Quality, Tune Hybrid Weights, and Define Production Guidance

This guide reviews the search-comparison results from Step 8 and turns them into practical guidance for a production search implementation.

Step 8 proved that keyword, semantic, and hybrid search can all run successfully against the same `quotes-v1` index. Step 9 answers the more important question:

```text
When should each search approach be used, and how should hybrid search be tuned?
```

This step is intentionally less about writing new search mechanics and more about evaluating result quality, documenting tradeoffs, and preparing a production recommendation.

## Goal

By the end of this step, you should be able to:

- Review keyword, semantic, and hybrid search results side by side
- Score result quality using a simple review rubric
- Run hybrid search with different keyword/semantic weights
- Compare whether weight changes improve or hurt search quality
- Document when keyword search should be favored
- Document when semantic search should be favored
- Document when hybrid search should be the default
- Capture production guidance for future enterprise search implementations

## Why this step matters

A semantic-search POC is not successful merely because vectors work.

The real value comes from understanding:

- which search approach produces the best result for different query types
- whether hybrid search improves recall without damaging precision
- whether exact matches are preserved when they matter
- whether semantic matches help when users search by meaning
- how much tuning is needed before the approach is useful for real users

For production systems, relevance quality is a business decision as much as a technical decision. The best search method is the one that helps users find the right information reliably.

## Public Repository Notes

This guide is safe to include in a public GitHub repository.

Recommended practices:

- Commit the tuning script because it documents the evaluation process.
- Commit generated tuning summaries for this small POC so teammates can compare expected results.
- Do not treat this tiny synthetic dataset as proof of production relevance quality.
- Do not commit OpenSearch passwords or local secrets.
- Document that production tuning must use representative business data and real user queries.

## Prerequisites

Before starting this step, complete:

- Step 1: Docker setup for OpenSearch
- Step 2: Python environment setup
- Step 3: Creating the sample quotes dataset
- Step 4: Creating the OpenSearch index
- Step 5: Generating embeddings for the sample quotes
- Step 6: Bulk indexing embedded quote documents
- Step 7: Performing semantic search
- Step 8: Comparing keyword, semantic, and hybrid search

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
│   ├── semantic-search-results.json
│   ├── quotes-hybrid-search-pipeline.json
│   ├── search-comparison-results.json
│   └── search-comparison-summary.md
├── scripts/
│   ├── bulk_index_quotes.py
│   ├── compare_search_methods.py
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
docs/
├── production-search-guidance.md
└── search-quality-review.md

opensearch/
├── hybrid-weight-tuning-results.json
└── hybrid-weight-tuning-summary.md

scripts/
└── tune_hybrid_weights.py
```

### Output file purpose

| File | Purpose |
| --- | --- |
| `scripts/tune_hybrid_weights.py` | Runs hybrid search with multiple keyword/semantic weight combinations |
| `opensearch/hybrid-weight-tuning-results.json` | Full JSON output for each query and weight combination |
| `opensearch/hybrid-weight-tuning-summary.md` | Human-readable tuning summary |
| `docs/search-quality-review.md` | Team review worksheet for scoring result quality |
| `docs/production-search-guidance.md` | Production guidance derived from the POC |

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

## 4. Review the Step 8 summary first

Open:

```text
opensearch/search-comparison-summary.md
```

For each query, review the top result returned by:

- keyword search
- semantic search
- hybrid search

The goal is not to declare one method universally best. The goal is to observe which method behaves best for different query types.

## 5. Use a simple result-quality rubric

Use this rubric when reviewing results:

| Score | Meaning | Description |
| ---: | --- | --- |
| `3` | Excellent | Directly satisfies the query intent |
| `2` | Good | Useful and related, but not the best possible result |
| `1` | Weak | Somewhat related, but likely unsatisfying |
| `0` | Poor | Irrelevant or misleading |

For each test query, ask:

- Would a business user consider this result useful?
- Did keyword search find an exact match but miss the meaning?
- Did semantic search find the meaning but miss an important exact term?
- Did hybrid search provide a better compromise?
- Were any results technically related but practically unhelpful?

## 6. Create the hybrid-weight tuning script

Create this file:

### macOS or Linux

```bash
touch scripts/tune_hybrid_weights.py
```

### Windows PowerShell

```powershell
New-Item -ItemType File -Force -Path scripts/tune_hybrid_weights.py
```

Open `scripts/tune_hybrid_weights.py` and paste the following code:

```python
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
```

## 7. Understand what the tuning script does

The script performs the following work:

1. Reads `data/embedding-manifest.json` from Step 5.
2. Loads the same embedding model used to generate document vectors.
3. Verifies the `quotes-v1` index exists.
4. Verifies the index contains quote documents.
5. Verifies the `quote_embedding` vector field dimension matches the model.
6. Creates one OpenSearch search pipeline for each hybrid weight combination.
7. Runs hybrid search for the same query list at each weight combination.
8. Prints top-result comparisons to the terminal.
9. Writes full JSON tuning output.
10. Writes a compact Markdown tuning summary.

The default weight combinations are:

```text
keyword=0.70, semantic=0.30
keyword=0.50, semantic=0.50
keyword=0.30, semantic=0.70
```

These are intentionally simple. The goal is to make the tradeoff visible.

## 8. Run the tuning script

Run:

```bash
python scripts/tune_hybrid_weights.py
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
Weight sets: [(0.7, 0.3), (0.5, 0.5), (0.3, 0.7)]
Verifying OpenSearch connection...
Connected to OpenSearch cluster: docker-cluster
Verifying index and mapping...
Document count: 50
Loading embedding model...

====================================================================================================
Query: perseverance
----------------------------------------------------------------------------------------------------
keyword=0.70, semantic=0.30     | rank 1 | quote-... | ...
keyword=0.50, semantic=0.50     | rank 1 | quote-... | ...
keyword=0.30, semantic=0.70     | rank 1 | quote-... | ...
```

Exact scores and rankings may vary slightly by OpenSearch version, model/runtime behavior, or dataset changes.

## 9. Confirm the generated tuning files exist

### macOS or Linux

```bash
ls -lh \
  opensearch/hybrid-weight-tuning-results.json \
  opensearch/hybrid-weight-tuning-summary.md
```

### Windows PowerShell

```powershell
Get-ChildItem `
  opensearch\hybrid-weight-tuning-results.json, `
  opensearch\hybrid-weight-tuning-summary.md
```

## 10. Inspect the tuning summary

Open:

```text
opensearch/hybrid-weight-tuning-summary.md
```

For each query, compare the top result returned by each hybrid weighting strategy.

Look especially for cases where:

- keyword-heavy weighting improves exact-match behavior
- semantic-heavy weighting improves conceptual matching
- balanced weighting provides the best compromise
- changing weights does not materially change the result
- changing weights creates worse results

## 11. Optional: try additional hybrid weights

The script accepts custom weight sets through `HYBRID_WEIGHT_SETS`.

Format:

```text
keyword_weight:semantic_weight,keyword_weight:semantic_weight
```

Example:

### macOS or Linux

```bash
HYBRID_WEIGHT_SETS='0.80:0.20,0.65:0.35,0.50:0.50,0.35:0.65,0.20:0.80' \
  python scripts/tune_hybrid_weights.py
```

### Windows PowerShell

```powershell
$env:HYBRID_WEIGHT_SETS = '0.80:0.20,0.65:0.35,0.50:0.50,0.35:0.65,0.20:0.80'
python scripts/tune_hybrid_weights.py
```

The values do not have to add up to `1.0`. The script normalizes them.

For example, this:

```text
7:3
```

is treated like this:

```text
0.70:0.30
```

## 12. Create the search-quality review document

Create this file:

### macOS or Linux

```bash
touch docs/search-quality-review.md
```

### Windows PowerShell

```powershell
New-Item -ItemType File -Force -Path docs/search-quality-review.md
```

Open `docs/search-quality-review.md` and paste the following template:

```markdown
# Search Quality Review

This document captures human review notes for the semantic-search POC.

## Review Context

- Index: `quotes-v1`
- Dataset: 50 synthetic quote records
- Embedding model: `all-MiniLM-L6-v2`
- Vector dimension: `384`
- Search methods reviewed:
  - keyword search
  - semantic search
  - hybrid search
- Primary review files:
  - `opensearch/search-comparison-summary.md`
  - `opensearch/hybrid-weight-tuning-summary.md`

## Review Rubric

| Score | Meaning | Description |
| ---: | --- | --- |
| `3` | Excellent | Directly satisfies the query intent |
| `2` | Good | Useful and related, but not the best possible result |
| `1` | Weak | Somewhat related, but likely unsatisfying |
| `0` | Poor | Irrelevant or misleading |

## Query Review

| Query | Keyword Score | Semantic Score | Hybrid Score | Preferred Method | Notes |
| --- | ---: | ---: | ---: | --- | --- |
| `perseverance` |  |  |  |  |  |
| `quotes about never giving up` |  |  |  |  |  |
| `curiosity and discovery` |  |  |  |  |  |
| `leading with humility` |  |  |  |  |  |
| `finding humor in mistakes` |  |  |  |  |  |
| `learning from failure` |  |  |  |  |  |

## Observations

### Keyword Search

Document observations here.

Suggested prompts:

- Which queries worked well with exact keyword matching?
- Which queries failed because the exact words were missing?
- Did keyword search return any technically matching but low-value results?

### Semantic Search

Document observations here.

Suggested prompts:

- Which queries benefited from meaning-based matching?
- Did semantic search find useful synonyms or related concepts?
- Did semantic search ever return results that were related but too broad?

### Hybrid Search

Document observations here.

Suggested prompts:

- Did hybrid search preserve useful exact matches?
- Did hybrid search improve conceptual matching?
- Did hybrid search feel safer than either method alone?
- Which weighting strategy looked best overall?

## Recommended Default for This POC

Document the team's recommendation here.

Example:

> For general quote search, balanced hybrid search appears to be the safest default because it preserves useful keyword matches while also returning meaning-based matches for conceptual queries.

## Limitations

This POC uses a small synthetic quote dataset. These results are useful for learning the mechanics and tradeoffs of semantic search, but they are not sufficient to prove production relevance quality.

Production evaluation should use:

- representative business documents
- real or realistic user queries
- expected result judgments from business users
- access-control-aware filtering
- measurable relevance metrics
```

## 13. Fill out the search-quality review document

Use these files as inputs:

```text
opensearch/search-comparison-summary.md
opensearch/hybrid-weight-tuning-summary.md
```

For each query:

1. Review the top keyword result.
2. Review the top semantic result.
3. Review the top hybrid result.
4. Assign each method a score from `0` to `3`.
5. Pick the preferred method.
6. Add a short note explaining why.

Do not overthink the scoring for this POC. The point is to create a shared team conversation about relevance quality.

## 14. Create the production search guidance document

Create this file:

### macOS or Linux

```bash
touch docs/production-search-guidance.md
```

### Windows PowerShell

```powershell
New-Item -ItemType File -Force -Path docs/production-search-guidance.md
```

Open `docs/production-search-guidance.md` and paste the following starter guidance:

```markdown
# Production Search Guidance

This document summarizes practical search guidance derived from the semantic-search POC.

## Recommended Default Approach

For most general-purpose enterprise search use cases, start with **hybrid search** rather than keyword-only or semantic-only search.

Hybrid search is a practical default because:

- keyword search preserves exact matches
- semantic search finds meaning-based matches
- hybrid scoring can combine both signals
- users often submit a mix of exact terms, short concepts, and natural-language questions

## When to Favor Keyword Search

Favor keyword search when the query appears to target an exact value.

Examples:

- document IDs
- case numbers
- invoice numbers
- product SKUs
- filenames
- usernames
- email addresses
- error codes
- exact phrases
- proper nouns
- acronyms or system names

Keyword search is usually safer when the user likely expects a precise match.

## When to Favor Semantic Search

Favor semantic search when the query expresses a concept, intent, or question.

Examples:

- `how do we handle contract risk`
- `documents about lessons learned`
- `policies related to data retention`
- `examples of project failure`
- `guidance about customer escalation`

Semantic search is useful when relevant documents may not contain the exact words used in the query.

## When to Favor Hybrid Search

Favor hybrid search when the query could benefit from both exact matching and meaning-based matching.

Examples:

- short conceptual queries such as `resilience`, `leadership`, or `compliance`
- natural-language queries that include important domain terms
- searches where exact terminology matters but synonyms are also useful
- general enterprise search boxes where user intent is mixed or unknown

A single-word query can still be semantic if the word represents a concept.

## Recommended Query Handling Strategy

A production system may use a strategy like this:

| Query Type | Recommended Handling |
| --- | --- |
| Exact IDs, codes, filenames, or structured values | Keyword-first or keyword-only |
| Proper nouns and named entities | Keyword-first hybrid |
| Short conceptual terms | Hybrid |
| Natural-language questions | Semantic or hybrid |
| Queries with filters such as date, department, or document type | Hybrid plus metadata filters |
| Ambiguous queries | Hybrid plus facets, filters, or query suggestions |

## Hybrid Weighting Guidance

Start with balanced hybrid weighting:

```text
keyword = 0.50
semantic = 0.50
```

Then tune using real queries and human relevance judgments.

Possible tuning directions:

| Weighting Pattern | When It May Help |
| --- | --- |
| Keyword-heavy | Exact terms, identifiers, names, acronyms, controlled vocabulary |
| Balanced | General-purpose search with mixed query types |
| Semantic-heavy | Conceptual discovery, natural-language queries, synonym-heavy content |

Do not choose production weights based only on intuition. Tune against representative data.

## Production Considerations

Before applying this POC pattern to production, address:

- representative document collection
- document chunking strategy
- metadata fields and filters
- security trimming and access control
- embedding model choice
- vector dimension and index mapping
- model hosting or managed embedding service
- index refresh and re-embedding strategy
- relevance evaluation process
- monitoring and feedback collection
- cost, latency, and scaling behavior

## AWS GovCloud Translation Notes

The local POC uses `sentence-transformers/all-MiniLM-L6-v2` because it is lightweight and easy to run locally.

For AWS GovCloud production, a managed embedding model such as Amazon Titan Text Embeddings V2 through Amazon Bedrock may be evaluated as a production alternative.

The core pattern remains the same:

```text
Document text
  -> embedding model
  -> vector
  -> OpenSearch vector index

User query
  -> same embedding model family/configuration
  -> query vector
  -> OpenSearch k-NN or hybrid search
  -> ranked results
```

If the production embedding model changes, the OpenSearch vector mapping dimension must also change, and documents must be re-embedded and reindexed.

## POC Conclusion

The POC demonstrates that:

- keyword search is strong for exact wording
- semantic search is strong for meaning-based retrieval
- hybrid search is often the safest default for mixed enterprise search behavior
- production success depends on relevance evaluation, not just successful vector indexing

The recommended next step is to apply this pattern to a more realistic dataset and evaluate relevance using real business queries.
```

## 15. Review the production guidance as a team

Discuss whether the guidance matches what the team observed.

Useful questions:

1. Should hybrid search be the default for general search?
2. Should exact identifiers bypass semantic search?
3. Should keyword and semantic results be shown separately or combined?
4. Should users be able to filter by metadata before vector search?
5. What business datasets would be good candidates for the next POC?
6. What would a production relevance test set look like?
7. What metrics or human review process should be used?

## 16. Recommended conclusions for this POC

For this quote-based POC, the likely conclusion is:

```text
Keyword search works well when the query overlaps exact quote text.
Semantic search works well when the query describes an idea rather than exact wording.
Hybrid search is the best general default because it can preserve exact matches while also surfacing meaning-based matches.
```

This conclusion should be treated as a learning outcome, not as universal proof for every dataset.

## 17. Recommended commit

For this small POC, commit the Step 9 guide, tuning script, generated tuning output, and review/guidance documents.

```bash
git status
git add \
  9-review-search-quality-and-tuning.md \
  scripts/tune_hybrid_weights.py \
  opensearch/hybrid-weight-tuning-results.json \
  opensearch/hybrid-weight-tuning-summary.md \
  docs/search-quality-review.md \
  docs/production-search-guidance.md
git commit -m "Review search quality and tune hybrid search"
git push
```

If your guide files live in a `docs/` folder, adjust the first path accordingly:

```bash
git add docs/9-review-search-quality-and-tuning.md
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

If you changed the model, recreate the index, regenerate embeddings, and reindex documents.

### Hybrid tuning results do not change much

That can happen with a small dataset.

Possible reasons:

- the top result is already strong across all methods
- the dataset is too small to show meaningful ranking differences
- the query strongly favors one result regardless of weighting
- the same document appears in both keyword and semantic result sets

This is not a failure. It is an observation to document.

### Semantic-heavy results feel too broad

That is a common relevance risk.

Possible mitigations:

- increase keyword weight
- add metadata filters
- improve document chunking
- use a better domain-specific embedding model
- add reranking later
- evaluate with more representative data

### Keyword-heavy results miss user intent

That is the classic reason to use semantic search.

Possible mitigations:

- increase semantic weight
- enrich searchable text fields
- add synonym handling
- improve metadata quality
- test with real user queries

## Result

After this step, the POC has moved beyond mechanics and into search-quality evaluation.

The project now documents:

- what keyword search does well
- what semantic search does well
- why hybrid search is often the safest default
- how hybrid weighting affects result quality
- what production teams should evaluate before applying semantic search to real enterprise data

The project is now ready for the next phase: applying the POC pattern to a more realistic business dataset or translating the design into a production-oriented AWS/OpenSearch architecture.

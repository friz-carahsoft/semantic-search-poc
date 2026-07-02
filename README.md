# Semantic Search POC with OpenSearch

## Overview

This repository is a hands-on proof of concept for building a small semantic search system using OpenSearch, Python, and sentence-transformer embeddings.

The goal is to help team members understand how vector-based search works, how it differs from traditional keyword search, and what practical implementation steps are required to move from raw text to searchable semantic results.

## Semantic Search vs. Keyword Search

Traditional keyword search looks for matching words or terms. If a user searches for `determination`, keyword search performs best when the indexed documents also contain words like `determination`, `determine`, or closely related indexed terms.

Semantic search works differently. It converts text into numeric vectors called embeddings. These embeddings represent the meaning of the text in a high-dimensional vector space. A user query is converted into an embedding too, and the search engine compares the query vector to document vectors to find text with similar meaning.

For example, a semantic search for:

```text
quotes about not giving up
```

may match quotes about persistence, resilience, effort, endurance, or courage even when the exact words `not giving up` do not appear in the quote.

### Simple comparison

| Search type | Primary matching method | Strengths | Limitations |
|---|---|---|---|
| Keyword search | Exact or analyzed text terms | Fast, explainable, strong for known terms, names, IDs, and filters | Can miss relevant results that use different wording |
| Semantic search | Vector similarity based on meaning | Finds conceptually similar content even with different wording | Results can feel less obvious; requires embeddings and vector indexing |
| Hybrid search | Combines keyword and semantic signals | Often produces better relevance than either method alone | Requires scoring/tuning decisions |

## What We Wanted to Learn

### Business learning goals

This POC was intended to help the team evaluate whether semantic search can improve discovery when users do not know the exact words contained in the source content.

Key business questions:

- Can semantic search return useful results when users search by concept instead of exact wording?
- Where does semantic search improve the user experience compared with keyword-only search?
- Where does keyword search still perform better, especially for exact terms, categories, names, or identifiers?
- Does hybrid search provide a better default approach for general-purpose search?
- What types of content are good candidates for vector search?
- What would be required to explain, test, tune, and support semantic-search behavior in a real application?

### Technical learning goals

This POC walked through the core technical workflow required to build a semantic-search pipeline.

Key technical questions:

- How do we run OpenSearch locally with vector-search support?
- How do we generate embeddings from text using Python?
- How do embedding dimensions affect OpenSearch index mappings?
- How do we define a `knn_vector` field for vector search?
- How do we bulk index documents that include both text metadata and embeddings?
- How do we convert user queries into embeddings at search time?
- How do k-NN vector queries behave compared with keyword queries?
- How do we compare keyword, semantic, and hybrid search results?
- How should we document production guidance for choosing between search approaches?

## POC Summary

This project uses a small synthetic quotes dataset to demonstrate semantic search end to end. The dataset is intentionally small so the team can inspect the source data, generated embeddings, bulk indexing format, and search results without needing a large infrastructure setup.

The completed implementation uses:

- OpenSearch running locally in Docker
- Python virtual environment for repeatable local execution
- `sentence-transformers` for embedding generation
- `opensearch-py` for OpenSearch integration
- A synthetic quotes dataset with categories and metadata
- A vector-enabled OpenSearch index named `quotes-v1`
- k-NN search against indexed quote embeddings
- Keyword search for exact/analyzed text matching
- Hybrid search combining keyword and semantic signals
- Search comparison and tuning outputs for relevance review
- Production guidance notes for when each search approach should be used

## Repository Guide

The step-by-step documentation lives in the `docs/` folder:

| Step | Document | Purpose |
|---:|---|---|
| 0 | [`docs/0-semantic-search-poc.md`](docs/0-semantic-search-poc.md) | High-level project plan and POC roadmap |
| 1 | [`docs/1-opensearch-docker-setup.md`](docs/1-opensearch-docker-setup.md) | Run OpenSearch locally with Docker |
| 2 | [`docs/2-python-environment-setup.md`](docs/2-python-environment-setup.md) | Create the Python environment and install dependencies |
| 3 | [`docs/3-sample-quotes-dataset.md`](docs/3-sample-quotes-dataset.md) | Generate the sample quotes dataset |
| 4 | [`docs/4-opensearch-index-setup.md`](docs/4-opensearch-index-setup.md) | Create the vector-enabled OpenSearch index |
| 5 | [`docs/5-generate-quote-embeddings.md`](docs/5-generate-quote-embeddings.md) | Generate quote embeddings and prepare bulk indexing files |
| 6 | [`docs/6-bulk-index-quotes.md`](docs/6-bulk-index-quotes.md) | Bulk index embedded quote documents into OpenSearch |
| 7 | [`docs/7-semantic-search-quotes.md`](docs/7-semantic-search-quotes.md) | Run semantic search queries against indexed vectors |
| 8 | [`docs/8-compare-search-methods.md`](docs/8-compare-search-methods.md) | Compare keyword, semantic, and hybrid search results |
| 9 | [`docs/9-review-search-quality-and-tuning.md`](docs/9-review-search-quality-and-tuning.md) | Review search quality, tune hybrid weights, and document production guidance |

## What Has Been Accomplished

### Step 1: OpenSearch Docker setup

- Created a local single-node OpenSearch environment using Docker.
- Verified OpenSearch is reachable at `https://localhost:9200`.
- Confirmed the k-NN plugin is available for vector search.
- Configured persistent local storage using a Docker volume.

### Step 2: Python environment setup

- Created a project-local Python virtual environment.
- Installed core dependencies for embeddings, OpenSearch access, and data handling.
- Verified Python, PyTorch, Sentence Transformers, and `opensearch-py` are working.
- Captured dependencies in `requirements.txt`.

### Step 3: Sample quotes dataset

- Created a small synthetic quotes dataset suitable for a public repository.
- Generated both CSV and JSONL versions of the dataset.
- Included quote text, author, category, tags, source notes, and a `search_text` field.
- Avoided licensing ambiguity by using synthetic quote-style records instead of real famous quotes.

### Step 4: OpenSearch index setup

- Created the `quotes-v1` OpenSearch index.
- Defined text, keyword, metadata, and vector fields.
- Added a `quote_embedding` field using the `knn_vector` type.
- Matched the vector dimension to the embedding model output.
- Verified index settings and mappings.

### Step 5: Generate quote embeddings

- Generated embeddings for all sample quote records.
- Created `data/quotes-with-embeddings.jsonl` for inspection and validation.
- Created `data/quotes-bulk.ndjson` for OpenSearch Bulk API indexing.
- Created `data/embedding-manifest.json` to document model, dimension, source data, and generated outputs.

### Step 6: Bulk index embedded quotes

- Added a bulk indexing script for loading embedded quote documents into OpenSearch.
- Validated the bulk NDJSON file before indexing.
- Indexed all embedded quote documents into the `quotes-v1` index.
- Generated `opensearch/bulk-index-summary.json` with indexing metadata.
- Verified document count and basic search access after indexing.

### Step 7: Perform semantic search

- Added a semantic-search script that converts user queries into embeddings.
- Ran k-NN searches against the indexed `quote_embedding` vectors.
- Added optional category-filtered semantic search.
- Saved sample results to `opensearch/semantic-search-results.json`.
- Confirmed the POC can retrieve quote records by meaning rather than only exact keyword matches.

### Step 8: Compare keyword, semantic, and hybrid search

- Added side-by-side comparison of keyword, semantic, and hybrid search methods.
- Ran the same test queries through each search approach.
- Created an OpenSearch hybrid-search pipeline for score normalization and combination.
- Generated comparison outputs for reviewing result differences across methods.
- Documented where keyword search, semantic search, and hybrid search each performed well.

### Step 9: Review search quality and tune hybrid behavior

- Reviewed search quality results from the Step 8 comparison.
- Applied a simple relevance scoring rubric to evaluate result usefulness.
- Tested multiple hybrid weight combinations to understand ranking impact.
- Generated tuning and review artifacts for documenting search behavior.
- Created production guidance for when to favor keyword, semantic, or hybrid search.

## POC Completion Status

Steps 1 through 9 are complete.

The project now demonstrates a complete semantic-search workflow:

1. run OpenSearch locally,
2. create a vector-enabled index,
3. generate sample quote data,
4. generate document embeddings,
5. bulk index embedded documents,
6. run semantic k-NN searches,
7. compare keyword, semantic, and hybrid search,
8. review relevance quality, and
9. document production guidance.

This POC is complete as a learning-oriented implementation. It demonstrates the end-to-end mechanics and gives the team a practical foundation for discussing production architecture, search relevance, model selection, indexing strategy, and user experience.

## Recommended Conclusions

The main conclusion from this POC is that semantic search should not be viewed as a simple replacement for keyword search.

A practical production implementation will likely need all three approaches:

- **Keyword search** for exact terms, identifiers, names, categories, codes, and highly specific values.
- **Semantic search** for concept-based queries where meaning matters more than exact wording.
- **Hybrid search** as a strong general-purpose default when both exact matching and meaning-based discovery are valuable.

Hybrid search is often the best default candidate for enterprise search because it preserves the strengths of keyword search while adding semantic recall for queries that use different wording than the indexed content.

## Suggested Starting Point for New Team Members

New team members should start with the high-level plan and then work through the numbered guides in order:

```text
docs/0-semantic-search-poc.md
docs/1-opensearch-docker-setup.md
docs/2-python-environment-setup.md
docs/3-sample-quotes-dataset.md
docs/4-opensearch-index-setup.md
docs/5-generate-quote-embeddings.md
docs/6-bulk-index-quotes.md
docs/7-semantic-search-quotes.md
docs/8-compare-search-methods.md
docs/9-review-search-quality-and-tuning.md
```

Each step builds on the previous one, so the recommended path is to complete them sequentially.

## Possible Next Steps Beyond This POC

Although the POC is complete, useful follow-up work may include:

- Testing with a larger or more realistic business dataset.
- Defining a formal relevance evaluation set with expected results.
- Adding a simple API endpoint for search.
- Adding a lightweight UI for demo purposes.
- Testing OpenSearch vector search with production-like document volumes.
- Evaluating production embedding platforms (e.g. we would not use `all-MiniLM-L6-v2`).
- Documenting model governance, reindexing strategy, monitoring, security, and cost considerations.
- Exploring reranking, query rewriting, and relevance feedback for improved search quality.

# Semantic Search POC with OpenSearch

## Overview
This guide walks through setting up a proof-of-concept semantic search system using OpenSearch with vector embeddings.

## High-Level Steps

### 1. Set Up OpenSearch with Docker
- Pull and run OpenSearch Docker image
- Verify the cluster is running
- Confirm k-NN plugin is enabled

### 2. Choose an Embedding Model
- Select a simple, pre-trained model (we'll use sentence-transformers)
- Install Python dependencies
- Test the model locally

### 3. Prepare Sample Data
- Use a small, manageable public domain dataset
- **Suggested datasets** (pick one):
  - **Classic Books** - First paragraphs from 20-30 public domain books (Project Gutenberg)
  - **Famous Quotes** - Collection of 50-100 quotes with attribution
  - **Movie Plot Summaries** - Short summaries from 100 classic films
  - **Simple Wikipedia Articles** - 50 articles on common topics (countries, animals, science)
  
For this POC, we'll use **famous quotes** - they're short, diverse, and easy to verify search results.

Note: "widely known" does not automatically mean "public domain." Use a vetted, reusable source for the quotes and attribution data, or create a small internal sample dataset with documented sources.

### 4. Create an OpenSearch Index
- Define index mapping with:
  - Text field for the original content
  - knn_vector field for embeddings
  - Metadata fields (author, category, etc.)
- Match the `knn_vector` dimension to the embedding model you choose
- Enable vector search settings required by the index (for example, `index.knn: true`)

### 5. Generate Embeddings
- Write a Python script to:
  - Load your sample data
  - Generate vector embeddings using the model
  - Prepare documents for bulk indexing

### 6. Index Documents
- Use OpenSearch bulk API to index documents with their embeddings
- Verify documents are indexed correctly

### 7. Perform Semantic Search
- Write queries that:
  - Convert query text to embeddings
  - Search using k-NN
  - Combine with keyword search (hybrid)
- Test with various queries to see semantic matching in action

### 8. Compare Results
- Run the same queries as:
  - Pure keyword search
  - Pure semantic search
  - Hybrid search
- Observe the differences

## Sample Data: Famous Quotes Dataset

We'll use ~50 famous quotes across different categories:
- Philosophy
- Science
- Literature
- Leadership
- Humor

**Why quotes?**
- Short and simple (easy to review results)
- Semantically diverse
- Easy to create test queries
- Easy to source from a small, documented, reusable dataset
- Can test semantic similarity ("find quotes about perseverance" should match "never give up" quotes)

## Tools & Technologies

- **OpenSearch**: Pinned Docker image tag (recommended: `3.7.0` as of June 29, 2026)
- **Python**: 3.8+
- **sentence-transformers**: For embedding generation
- **opensearch-py**: Python client for OpenSearch

## Important Implementation Notes

- **Version pinning**: Avoid `latest` tags for Docker images or Python packages in this POC. Pin versions so the environment is reproducible.
- **Embedding dimensions**: The index mapping must use the same vector dimension as the embedding model output. A mismatch will cause indexing failures.
- **Single-node health**: A single-node OpenSearch cluster may report `yellow` health if replicas are configured but unassigned. That is acceptable for local development.
- **Security defaults**: Recent OpenSearch Docker images enable demo security by default, so local API calls typically use HTTPS plus admin credentials.

## Expected Outcomes

After completing this POC, you'll be able to:
- Query "quotes about determination" and get results about persistence/grit (even without exact keywords)
- Compare semantic vs keyword search quality
- Understand the basics of vector embeddings
- Have a foundation to scale to larger datasets

---

## Next Steps

We'll go through each step in detail, starting with:
1. Docker setup for OpenSearch
2. Python environment setup
3. Creating the sample quotes dataset

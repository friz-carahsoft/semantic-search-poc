# Step 5: Generating Embeddings for the Sample Quotes

This guide generates vector embeddings for the sample quotes dataset and prepares documents for bulk indexing into OpenSearch.

This step does **not** send documents to OpenSearch yet. It creates local output files that the next step can use with the OpenSearch Bulk API.

## Goal

By the end of this step, you should be able to:

- Load the sample quotes dataset created in Step 3
- Generate embeddings with the same Sentence Transformers model used when creating the OpenSearch index in Step 4
- Confirm each embedding has the expected vector dimension
- Create a JSONL file containing quote records plus embeddings
- Create an OpenSearch Bulk API NDJSON file
- Create a small manifest file documenting the embedding model and output files
- Validate the generated files before indexing

## Why this step matters

Semantic search works by comparing vectors.

The text query is converted into an embedding vector, and each searchable document also needs an embedding vector. OpenSearch can then compare the query vector to the stored document vectors and return documents that are semantically similar, even when the exact keywords do not match.

For this POC, each quote record will receive one vector embedding based on the `quote` field.

The generated vector field must match the vector field created in Step 4:

```text
quote_embedding
```

The vector dimension must also match the index mapping. With the default model used in this POC:

```text
all-MiniLM-L6-v2
```

The expected embedding dimension is:

```text
384
```

If the generated vector dimension does not match the OpenSearch index mapping, bulk indexing will fail in the next step.

## Public Repository Notes

This guide is safe to include in a public GitHub repository.

Recommended practices:

- Commit the script that generates embeddings.
- Avoid committing secrets, passwords, local environment files, or `.venv/`.
- Use a stable documented embedding model so teammates generate compatible vectors.
- Keep generated embedding files out of Git if you want a clean repo history.
- For this tiny POC, committing generated embedding files is technically acceptable, but regenerating them locally is usually cleaner.

The generated embeddings are derived from the synthetic dataset created in Step 3. They do not contain credentials or private data.

## Prerequisites

Before starting this step, complete:

- Step 1: Docker setup for OpenSearch
- Step 2: Python environment setup
- Step 3: Creating the sample quotes dataset
- Step 4: Creating the OpenSearch index

You do not need OpenSearch running for this step unless you want to manually compare the generated vector dimension to the live index mapping.

You should already have:

```text
semantic-search-poc/
├── data/
│   ├── quotes.csv
│   └── quotes.jsonl
├── docs/
│   ├── 0-semantic-search-poc.md
│   ├── 1-opensearch-docker-setup.md
│   ├── 2-python-environment-setup.md
│   ├── 3-sample-quotes-dataset.md
│   ├── 4-opensearch-index-setup.md
│   └── 5-generate-quote-embeddings.md
├── opensearch/
│   ├── quotes-index.json
│   └── verified-index-mapping.json
├── scripts/
│   ├── create_quotes_index.py
│   └── create_sample_quotes_dataset.py
└── requirements.txt
```

You should also have these Python packages installed from Step 2:

- `sentence-transformers`
- `opensearch-py`
- `pandas`

This step only needs `sentence-transformers`, but the other packages remain part of the full POC environment.

## Files created by this step

This step creates the following files:

```text
data/
├── quotes-with-embeddings.jsonl
├── quotes-bulk.ndjson
└── embedding-manifest.json

scripts/
└── generate_quote_embeddings.py
```

### Output file purpose

| File | Purpose |
| --- | --- |
| `data/quotes-with-embeddings.jsonl` | Human-inspectable JSONL file containing each quote record plus its embedding vector |
| `data/quotes-bulk.ndjson` | OpenSearch Bulk API request body to use in Step 6 |
| `data/embedding-manifest.json` | Metadata about the model, dimension, text field, index name, and generated files |

## 1. Activate the Python virtual environment

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

## 2. Confirm the sample dataset exists

The input file for this step is:

```text
data/quotes.jsonl
```

### macOS or Linux

```bash
ls -lh data/quotes.jsonl
```

### Windows PowerShell

```powershell
Get-ChildItem data\quotes.jsonl
```

If the file does not exist, return to Step 3 and generate the sample quotes dataset first.

## 3. Confirm the embedding model works

This POC uses:

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

If this is the first time the model has been used on your machine, Sentence Transformers may download the model files.

## 4. Create the embedding generation script

Create this file:

### macOS or Linux

```bash
touch scripts/generate_quote_embeddings.py
```

### Windows PowerShell

```powershell
New-Item -ItemType File -Force -Path scripts/generate_quote_embeddings.py
```

Open `scripts/generate_quote_embeddings.py` and paste the following code:

```python
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer

INPUT_PATH = Path(os.getenv("QUOTES_INPUT_PATH", "data/quotes.jsonl"))
EMBEDDED_OUTPUT_PATH = Path(
    os.getenv("EMBEDDED_OUTPUT_PATH", "data/quotes-with-embeddings.jsonl")
)
BULK_OUTPUT_PATH = Path(os.getenv("BULK_OUTPUT_PATH", "data/quotes-bulk.ndjson"))
MANIFEST_PATH = Path(
    os.getenv("EMBEDDING_MANIFEST_PATH", "data/embedding-manifest.json")
)

INDEX_NAME = os.getenv("OPENSEARCH_INDEX", "quotes-v1")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
TEXT_FIELD = os.getenv("EMBED_TEXT_FIELD", "quote")
EMBEDDING_FIELD = os.getenv("EMBEDDING_FIELD", "quote_embedding")
BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "16"))

REQUIRED_FIELDS = {
    "id",
    "quote",
    "author",
    "category",
    "tags",
    "source",
    "source_license",
    "search_text",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read newline-delimited JSON records from disk."""
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}. Run Step 3 before running this script."
        )

    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc

            if not isinstance(record, dict):
                raise ValueError(f"Line {line_number} is not a JSON object")

            records.append(record)

    return records


def validate_records(records: list[dict[str, Any]]) -> None:
    """Validate required fields, duplicate IDs, and embedding input text."""
    if not records:
        raise ValueError("No records found in input file")

    seen_ids: set[str] = set()

    for index, record in enumerate(records, start=1):
        missing_fields = REQUIRED_FIELDS - set(record)
        if missing_fields:
            raise ValueError(
                f"Record {index} is missing required fields: {sorted(missing_fields)}"
            )

        record_id = str(record["id"]).strip()
        if not record_id:
            raise ValueError(f"Record {index} has an empty id")

        if record_id in seen_ids:
            raise ValueError(f"Duplicate id found: {record_id}")
        seen_ids.add(record_id)

        if TEXT_FIELD not in record:
            raise ValueError(
                f"Record {record_id} does not contain text field '{TEXT_FIELD}'"
            )

        text_value = str(record[TEXT_FIELD]).strip()
        if not text_value:
            raise ValueError(f"Record {record_id} has empty text in field '{TEXT_FIELD}'")

        if not isinstance(record["tags"], list):
            raise ValueError(f"Record {record_id} field 'tags' must be a list")


def validate_embedding_vector(vector: list[float], expected_dimension: int, record_id: str) -> None:
    """Validate that an embedding is numeric, finite, and correctly sized."""
    if len(vector) != expected_dimension:
        raise ValueError(
            f"Record {record_id} has vector dimension {len(vector)}, "
            f"expected {expected_dimension}"
        )

    for value in vector:
        if not isinstance(value, float):
            raise ValueError(f"Record {record_id} contains a non-float vector value")
        if not math.isfinite(value):
            raise ValueError(f"Record {record_id} contains a non-finite vector value")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Write records as newline-delimited JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_bulk_ndjson(path: Path, records: list[dict[str, Any]]) -> None:
    """Write records in OpenSearch Bulk API NDJSON format."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            action = {
                "index": {
                    "_index": INDEX_NAME,
                    "_id": record["id"],
                }
            }
            file.write(json.dumps(action, ensure_ascii=False) + "\n")
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_manifest(record_count: int, embedding_dimension: int) -> None:
    """Write metadata documenting how the embedding outputs were created."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "embedding_model": EMBEDDING_MODEL_NAME,
        "embedding_dimension": embedding_dimension,
        "embedding_field": EMBEDDING_FIELD,
        "text_field_embedded": TEXT_FIELD,
        "record_count": record_count,
        "opensearch_index": INDEX_NAME,
        "input_file": str(INPUT_PATH),
        "embedded_output_file": str(EMBEDDED_OUTPUT_PATH),
        "bulk_output_file": str(BULK_OUTPUT_PATH),
        "bulk_format": "OpenSearch Bulk API NDJSON action/source pairs",
    }

    with MANIFEST_PATH.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)
        file.write("\n")


def main() -> int:
    print(f"Reading input records from: {INPUT_PATH}")
    records = read_jsonl(INPUT_PATH)
    validate_records(records)
    print(f"Loaded {len(records)} records")

    print(f"Using embedding model: {EMBEDDING_MODEL_NAME}")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    embedding_dimension = model.get_sentence_embedding_dimension()
    if embedding_dimension is None:
        raise RuntimeError(
            f"Could not determine embedding dimension for {EMBEDDING_MODEL_NAME}"
        )

    embedding_dimension = int(embedding_dimension)
    print(f"Embedding dimension: {embedding_dimension}")
    print(f"Embedding text field: {TEXT_FIELD}")
    print(f"Embedding output field: {EMBEDDING_FIELD}")

    texts = [str(record[TEXT_FIELD]).strip() for record in records]

    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
    )

    if len(embeddings) != len(records):
        raise RuntimeError(
            f"Generated {len(embeddings)} embeddings for {len(records)} records"
        )

    embedded_records: list[dict[str, Any]] = []

    for record, embedding in zip(records, embeddings):
        vector = [float(value) for value in embedding.tolist()]
        record_id = str(record["id"])
        validate_embedding_vector(vector, embedding_dimension, record_id)

        embedded_record = dict(record)
        embedded_record[EMBEDDING_FIELD] = vector
        embedded_records.append(embedded_record)

    write_jsonl(EMBEDDED_OUTPUT_PATH, embedded_records)
    write_bulk_ndjson(BULK_OUTPUT_PATH, embedded_records)
    write_manifest(len(embedded_records), embedding_dimension)

    print("Embedding generation completed successfully")
    print(f"Wrote embedded records: {EMBEDDED_OUTPUT_PATH}")
    print(f"Wrote bulk NDJSON file: {BULK_OUTPUT_PATH}")
    print(f"Wrote manifest: {MANIFEST_PATH}")
    print(f"Target OpenSearch index for bulk load: {INDEX_NAME}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
```

## 5. Run the embedding generation script

From the project root, run:

```bash
python scripts/generate_quote_embeddings.py
```

You should see output similar to:

```text
Reading input records from: data/quotes.jsonl
Loaded 50 records
Using embedding model: all-MiniLM-L6-v2
Embedding dimension: 384
Embedding text field: quote
Embedding output field: quote_embedding
Embedding generation completed successfully
Wrote embedded records: data/quotes-with-embeddings.jsonl
Wrote bulk NDJSON file: data/quotes-bulk.ndjson
Wrote manifest: data/embedding-manifest.json
Target OpenSearch index for bulk load: quotes-v1
```

The progress bar output may vary by terminal.

## 6. Confirm the generated files exist

### macOS or Linux

```bash
ls -lh data/quotes-with-embeddings.jsonl data/quotes-bulk.ndjson data/embedding-manifest.json
```

### Windows PowerShell

```powershell
Get-ChildItem data\quotes-with-embeddings.jsonl, data\quotes-bulk.ndjson, data\embedding-manifest.json
```

You should see all three files.

## 7. Inspect the manifest

The manifest is a small metadata file that records the model and dimension used to generate the embeddings.

### macOS or Linux

```bash
cat data/embedding-manifest.json
```

### Windows PowerShell

```powershell
Get-Content data\embedding-manifest.json
```

Expected values include:

```json
{
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dimension": 384,
  "embedding_field": "quote_embedding",
  "text_field_embedded": "quote",
  "record_count": 50,
  "opensearch_index": "quotes-v1"
}
```

The timestamp and file paths may vary.

## 8. Validate record and line counts

The original dataset should have 50 records.

The embedded JSONL file should also have 50 records.

The bulk NDJSON file should have 100 lines because each document uses two lines:

1. an action line
2. a source document line

### macOS or Linux

```bash
wc -l data/quotes.jsonl data/quotes-with-embeddings.jsonl data/quotes-bulk.ndjson
```

Expected line counts:

```text
50 data/quotes.jsonl
50 data/quotes-with-embeddings.jsonl
100 data/quotes-bulk.ndjson
```

### Windows PowerShell

```powershell
(Get-Content data\quotes.jsonl).Count
(Get-Content data\quotes-with-embeddings.jsonl).Count
(Get-Content data\quotes-bulk.ndjson).Count
```

Expected output:

```text
50
50
100
```

## 9. Validate the first embedded record

Run this check to confirm the first record has a `quote_embedding` field with 384 numeric values.

### macOS or Linux

```bash
python - <<'PY'
import json

with open('data/quotes-with-embeddings.jsonl', 'r', encoding='utf-8') as file:
    first = json.loads(file.readline())

print('id:', first['id'])
print('quote:', first['quote'])
print('embedding field exists:', 'quote_embedding' in first)
print('embedding dimension:', len(first['quote_embedding']))
print('first five vector values:', first['quote_embedding'][:5])
PY
```

### Windows PowerShell

```powershell
@'
import json

with open('data/quotes-with-embeddings.jsonl', 'r', encoding='utf-8') as file:
    first = json.loads(file.readline())

print('id:', first['id'])
print('quote:', first['quote'])
print('embedding field exists:', 'quote_embedding' in first)
print('embedding dimension:', len(first['quote_embedding']))
print('first five vector values:', first['quote_embedding'][:5])
'@ | python
```

Expected output includes:

```text
embedding field exists: True
embedding dimension: 384
```

The vector values are floating-point numbers and will look like a list of decimals.

## 10. Validate the bulk NDJSON structure

The OpenSearch Bulk API expects alternating lines:

```text
action
source
action
source
```

Run this check to inspect the first action/source pair.

### macOS or Linux

```bash
python - <<'PY'
import json

with open('data/quotes-bulk.ndjson', 'r', encoding='utf-8') as file:
    action = json.loads(file.readline())
    source = json.loads(file.readline())

print('bulk action:', action)
print('source id:', source['id'])
print('source has embedding:', 'quote_embedding' in source)
print('embedding dimension:', len(source['quote_embedding']))
PY
```

### Windows PowerShell

```powershell
@'
import json

with open('data/quotes-bulk.ndjson', 'r', encoding='utf-8') as file:
    action = json.loads(file.readline())
    source = json.loads(file.readline())

print('bulk action:', action)
print('source id:', source['id'])
print('source has embedding:', 'quote_embedding' in source)
print('embedding dimension:', len(source['quote_embedding']))
'@ | python
```

Expected output includes:

```text
bulk action: {'index': {'_index': 'quotes-v1', '_id': 'quote-001'}}
source has embedding: True
embedding dimension: 384
```

## 11. Optional: use a different text field for embeddings

The default script embeds only the `quote` field.

That is recommended for the first pass because it keeps the semantic representation focused on the quote text itself.

Later, you can experiment with embedding the `search_text` field, which includes quote, author, category, and tags.

### macOS or Linux

```bash
EMBED_TEXT_FIELD=search_text \
EMBEDDED_OUTPUT_PATH=data/quotes-search-text-with-embeddings.jsonl \
BULK_OUTPUT_PATH=data/quotes-search-text-bulk.ndjson \
EMBEDDING_MANIFEST_PATH=data/embedding-search-text-manifest.json \
python scripts/generate_quote_embeddings.py
```

### Windows PowerShell

```powershell
$env:EMBED_TEXT_FIELD = 'search_text'
$env:EMBEDDED_OUTPUT_PATH = 'data/quotes-search-text-with-embeddings.jsonl'
$env:BULK_OUTPUT_PATH = 'data/quotes-search-text-bulk.ndjson'
$env:EMBEDDING_MANIFEST_PATH = 'data/embedding-search-text-manifest.json'
python scripts/generate_quote_embeddings.py
```

After testing, clear those PowerShell environment variables if you do not want them to affect later commands:

```powershell
Remove-Item Env:EMBED_TEXT_FIELD
Remove-Item Env:EMBEDDED_OUTPUT_PATH
Remove-Item Env:BULK_OUTPUT_PATH
Remove-Item Env:EMBEDDING_MANIFEST_PATH
```

For the main POC path, continue using the default `quote` field.

## 12. Optional: use a different index name

The default bulk file targets:

```text
quotes-v1
```

That should match the index name created in Step 4.

If you used a different index name, set `OPENSEARCH_INDEX` before generating the bulk file.

### macOS or Linux

```bash
OPENSEARCH_INDEX=your-index-name python scripts/generate_quote_embeddings.py
```

### Windows PowerShell

```powershell
$env:OPENSEARCH_INDEX = 'your-index-name'
python scripts/generate_quote_embeddings.py
```

If you regenerate with a different index name, re-check the first action line in `data/quotes-bulk.ndjson` before continuing.

## 13. Recommended `.gitignore` entries

If this is a public repo, consider excluding generated embedding artifacts:

```gitignore
# Python virtual environment
.venv/

# Python cache files
__pycache__/
*.pyc

# Generated embedding artifacts
/data/quotes-with-embeddings.jsonl
/data/quotes-bulk.ndjson
/data/embedding-manifest.json
/data/quotes-search-text-with-embeddings.jsonl
/data/quotes-search-text-bulk.ndjson
/data/embedding-search-text-manifest.json
```

Keep this script committed:

```text
scripts/generate_quote_embeddings.py
```

For a tiny training repo, you may decide to commit the generated files so teammates can inspect them without running the model. Either approach is fine as long as the choice is documented.

## 14. Suggested git commit

After confirming everything works, commit the script and any chosen documentation updates.

If you are not committing generated embedding files:

```bash
git add 5-generate-quote-embeddings.md scripts/generate_quote_embeddings.py .gitignore
git commit -m "Add quote embedding generation step"
```

If you are committing the generated files too:

```bash
git add 5-generate-quote-embeddings.md scripts/generate_quote_embeddings.py data/quotes-with-embeddings.jsonl data/quotes-bulk.ndjson data/embedding-manifest.json .gitignore
git commit -m "Add generated quote embeddings"
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'sentence_transformers'`

Activate your virtual environment and reinstall dependencies from Step 2:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Model download fails

The first run may download model files from Hugging Face.

Check:

- internet access
- corporate proxy requirements
- whether your environment blocks model downloads

After the model is cached locally, future runs are usually faster.

### Generated dimension is not 384

Confirm the model name:

```bash
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); print(model.get_sentence_embedding_dimension())"
```

If you intentionally changed the model, return to Step 4 and recreate the OpenSearch index using the new model dimension.

### Bulk file has the wrong index name

Check the first line:

```bash
head -n 1 data/quotes-bulk.ndjson
```

On Windows PowerShell:

```powershell
Get-Content data\quotes-bulk.ndjson -TotalCount 1
```

If the `_index` value is wrong, regenerate the file with the correct `OPENSEARCH_INDEX` value.

### Bulk file line count is not 100

The bulk file should have two lines per document.

For 50 quote records, the file should have 100 lines.

If the count is different:

- rerun Step 3 to regenerate `data/quotes.jsonl`
- rerun this step to regenerate `data/quotes-bulk.ndjson`
- confirm there were no script errors

### PowerShell environment variables keep affecting later runs

PowerShell environment variables set with `$env:NAME = 'value'` remain active for that terminal session.

Remove one with:

```powershell
Remove-Item Env:NAME
```

Or close and reopen the terminal.

## Result

After this step, the project should have generated quote embeddings and a validated OpenSearch bulk NDJSON file.

The project is now ready for the next phase: bulk indexing the embedded quote documents into the OpenSearch `quotes-v1` index.

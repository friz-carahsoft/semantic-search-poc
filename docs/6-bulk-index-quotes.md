# Step 6: Bulk Indexing Embedded Quote Documents into OpenSearch

This guide bulk indexes the embedded quote documents created in Step 5 into the OpenSearch `quotes-v1` index created in Step 4.

This step **does not perform semantic search yet**. It loads the prepared documents into OpenSearch and verifies that the expected number of records were indexed successfully.

## Goal

By the end of this step, you should be able to:

- Confirm OpenSearch is running locally
- Confirm the `quotes-v1` index exists
- Confirm the generated Bulk API file exists
- Bulk index the embedded quote documents into OpenSearch
- Verify all 50 quote documents were indexed
- Inspect a sample indexed document
- Save a small indexing summary for troubleshooting and team review

## Why this step matters

Step 5 created local files containing quote records and vector embeddings. OpenSearch cannot search those documents until they are loaded into an index.

This step uses the OpenSearch Bulk API format generated in Step 5:

```text
data/quotes-bulk.ndjson
```

That file contains action/source line pairs like this:

```text
{ "index": { "_index": "quotes-v1", "_id": "quote-001" } }
{ "id": "quote-001", "quote": "...", "quote_embedding": [...] }
```

The `index` action uses a stable document ID, so rerunning this step is safe for local development. Existing documents with the same IDs will be replaced instead of duplicated.

## Public Repository Notes

This guide is safe to include in a public GitHub repository.

Recommended practices:

- Do not commit real OpenSearch passwords or secrets.
- Keep the local password in an environment variable.
- Commit the bulk indexing script.
- For this small instructional POC, it is reasonable to commit the generated summary file if the team wants a visible example of expected output.
- For larger datasets, generated indexing summaries are usually treated as local artifacts and excluded from Git.

This step assumes local OpenSearch demo security from Step 1. The examples use HTTPS with certificate verification disabled because the local Docker container uses a self-signed demo certificate. Do not copy that TLS posture into production.

## Prerequisites

Before starting this step, complete:

- Step 1: Docker setup for OpenSearch
- Step 2: Python environment setup
- Step 3: Creating the sample quotes dataset
- Step 4: Creating the OpenSearch index
- Step 5: Generating embeddings for the sample quotes

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
│   └── 6-bulk-index-quotes.md
├── opensearch/
│   ├── quotes-index.json
│   └── verified-index-mapping.json
├── scripts/
│   ├── create_quotes_index.py
│   ├── create_sample_quotes_dataset.py
│   └── generate_quote_embeddings.py
└── requirements.txt
```

You should also have these Python packages installed from Step 2:

- `opensearch-py`
- `sentence-transformers`
- `pandas`

This step only needs `opensearch-py`, but the other packages remain part of the full POC environment.

## Files created by this step

This step creates the following files:

```text
scripts/
└── bulk_index_quotes.py

opensearch/
└── bulk-index-summary.json
```

### Output file purpose

| File | Purpose |
| --- | --- |
| `scripts/bulk_index_quotes.py` | Python script that validates and bulk indexes `data/quotes-bulk.ndjson` |
| `opensearch/bulk-index-summary.json` | Small summary of the bulk indexing result |

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

## 4. Verify OpenSearch responds

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

## 5. Confirm the `quotes-v1` index exists

### macOS or Linux

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/quotes-v1?pretty'
```

### Windows PowerShell

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200/quotes-v1?pretty"
```

If OpenSearch returns `index_not_found_exception`, return to Step 4 and create the index first.

## 6. Confirm the bulk file exists

The input file for this step is:

```text
data/quotes-bulk.ndjson
```

### macOS or Linux

```bash
ls -lh data/quotes-bulk.ndjson
```

### Windows PowerShell

```powershell
Get-ChildItem data\quotes-bulk.ndjson
```

If the file does not exist, return to Step 5 and generate the embeddings first.

## 7. Confirm the bulk file has the expected line count

The POC dataset contains 50 quote documents.

The Bulk API file should contain two lines per document:

- one action line
- one source document line

So the expected line count is:

```text
100
```

### macOS or Linux

```bash
wc -l data/quotes-bulk.ndjson
```

Expected output should include:

```text
100 data/quotes-bulk.ndjson
```

### Windows PowerShell

```powershell
(Get-Content data\quotes-bulk.ndjson).Count
```

Expected output:

```text
100
```

## 8. Inspect the first bulk action/source pair

This is a quick sanity check before sending the file to OpenSearch.

### macOS or Linux

```bash
head -n 2 data/quotes-bulk.ndjson
```

### Windows PowerShell

```powershell
Get-Content data\quotes-bulk.ndjson -TotalCount 2
```

The first action line should target:

```text
quotes-v1
```

The source line should include:

```text
quote_embedding
```

## 9. Create the bulk indexing script

Create this file:

### macOS or Linux

```bash
touch scripts/bulk_index_quotes.py
```

### Windows PowerShell

```powershell
New-Item -ItemType File -Force -Path scripts/bulk_index_quotes.py
```

Open `scripts/bulk_index_quotes.py` and paste the following code:

```python
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opensearchpy import OpenSearch

OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://localhost:9200")
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
OPENSEARCH_PASSWORD = os.getenv(
    "OPENSEARCH_PASSWORD",
    os.getenv("OPENSEARCH_INITIAL_ADMIN_PASSWORD", ""),
)
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "quotes-v1")
BULK_FILE_PATH = Path(os.getenv("BULK_FILE_PATH", "data/quotes-bulk.ndjson"))
SUMMARY_PATH = Path(os.getenv("BULK_INDEX_SUMMARY_PATH", "opensearch/bulk-index-summary.json"))
EMBEDDING_FIELD = os.getenv("EMBEDDING_FIELD", "quote_embedding")
EXPECTED_RECORD_COUNT = int(os.getenv("EXPECTED_RECORD_COUNT", "50"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("OPENSEARCH_REQUEST_TIMEOUT", "60"))
REFRESH_AFTER_BULK = os.getenv("OPENSEARCH_REFRESH", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
}
VERIFY_CERTS = os.getenv("OPENSEARCH_VERIFY_CERTS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_bulk_file(path: Path) -> str:
    if not path.exists():
        fail(f"Bulk file not found: {path}. Run Step 5 before running this script.")

    bulk_body = path.read_text(encoding="utf-8")

    if not bulk_body.strip():
        fail(f"Bulk file is empty: {path}")

    if not bulk_body.endswith("\n"):
        bulk_body += "\n"

    return bulk_body


def parse_and_validate_bulk_file(bulk_body: str) -> int:
    lines = [line for line in bulk_body.splitlines() if line.strip()]

    if len(lines) % 2 != 0:
        fail(
            "Bulk file should contain action/source line pairs. "
            f"Found an odd number of non-empty lines: {len(lines)}"
        )

    document_count = len(lines) // 2

    if EXPECTED_RECORD_COUNT and document_count != EXPECTED_RECORD_COUNT:
        fail(
            f"Bulk file contains {document_count} documents, "
            f"expected {EXPECTED_RECORD_COUNT}."
        )

    seen_ids: set[str] = set()

    for pair_index in range(document_count):
        action_line = lines[pair_index * 2]
        source_line = lines[pair_index * 2 + 1]

        try:
            action = json.loads(action_line)
            source = json.loads(source_line)
        except json.JSONDecodeError as exc:
            fail(f"Invalid JSON in bulk file near document {pair_index + 1}: {exc}")

        if "index" not in action:
            fail(f"Bulk action {pair_index + 1} does not contain an 'index' operation")

        action_index = action["index"].get("_index")
        if action_index != OPENSEARCH_INDEX:
            fail(
                f"Bulk action {pair_index + 1} targets index '{action_index}', "
                f"but this script is configured for '{OPENSEARCH_INDEX}'."
            )

        action_id = action["index"].get("_id")
        source_id = source.get("id")

        if not action_id:
            fail(f"Bulk action {pair_index + 1} is missing _id")

        if action_id in seen_ids:
            fail(f"Duplicate bulk _id found: {action_id}")
        seen_ids.add(action_id)

        if source_id != action_id:
            fail(
                f"Bulk source id mismatch for document {pair_index + 1}: "
                f"action _id is '{action_id}', source id is '{source_id}'."
            )

        vector = source.get(EMBEDDING_FIELD)
        if not isinstance(vector, list) or not vector:
            fail(f"Document {action_id} is missing non-empty field '{EMBEDDING_FIELD}'")

    return document_count


def create_client() -> OpenSearch:
    if not OPENSEARCH_PASSWORD:
        fail(
            "OpenSearch password is not set. Set OPENSEARCH_INITIAL_ADMIN_PASSWORD "
            "or OPENSEARCH_PASSWORD before running this script."
        )

    if not VERIFY_CERTS:
        try:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass

    return OpenSearch(
        hosts=[OPENSEARCH_URL],
        http_auth=(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD),
        use_ssl=OPENSEARCH_URL.startswith("https"),
        verify_certs=VERIFY_CERTS,
        ssl_assert_hostname=VERIFY_CERTS,
        ssl_show_warn=VERIFY_CERTS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def validate_cluster_and_index(client: OpenSearch) -> None:
    try:
        info = client.info()
    except Exception as exc:
        fail(f"Could not connect to OpenSearch at {OPENSEARCH_URL}: {exc}")

    version = info.get("version", {}).get("number", "unknown")
    cluster_name = info.get("cluster_name", "unknown")
    print(f"Connected to OpenSearch cluster '{cluster_name}' version {version}")

    if not client.indices.exists(index=OPENSEARCH_INDEX):
        fail(f"Index '{OPENSEARCH_INDEX}' does not exist. Run Step 4 first.")

    mapping = client.indices.get_mapping(index=OPENSEARCH_INDEX)
    properties = mapping[OPENSEARCH_INDEX]["mappings"].get("properties", {})

    if EMBEDDING_FIELD not in properties:
        fail(f"Index '{OPENSEARCH_INDEX}' is missing vector field '{EMBEDDING_FIELD}'")

    field_type = properties[EMBEDDING_FIELD].get("type")
    if field_type != "knn_vector":
        fail(
            f"Field '{EMBEDDING_FIELD}' should be type 'knn_vector', "
            f"but found '{field_type}'."
        )

    dimension = properties[EMBEDDING_FIELD].get("dimension")
    print(f"Verified vector field '{EMBEDDING_FIELD}' with dimension {dimension}")


def summarize_bulk_response(response: dict[str, Any], attempted_document_count: int) -> dict[str, Any]:
    items = response.get("items", [])
    failed_items: list[dict[str, Any]] = []

    for item in items:
        index_result = item.get("index", {})
        status = index_result.get("status")
        error = index_result.get("error")

        if error or status is None or status >= 300:
            failed_items.append(index_result)

    successful_count = len(items) - len(failed_items)

    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "opensearch_url": OPENSEARCH_URL,
        "opensearch_index": OPENSEARCH_INDEX,
        "bulk_file": str(BULK_FILE_PATH),
        "attempted_document_count": attempted_document_count,
        "response_item_count": len(items),
        "successful_item_count": successful_count,
        "failed_item_count": len(failed_items),
        "errors": bool(response.get("errors")),
        "took_ms": response.get("took"),
        "refresh_requested": REFRESH_AFTER_BULK,
        "sample_failed_items": failed_items[:5],
    }


def write_summary(summary: dict[str, Any]) -> None:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_PATH.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)
        file.write("\n")


def main() -> int:
    print(f"Reading bulk file: {BULK_FILE_PATH}")
    bulk_body = read_bulk_file(BULK_FILE_PATH)
    document_count = parse_and_validate_bulk_file(bulk_body)
    print(f"Validated {document_count} bulk documents")

    client = create_client()
    validate_cluster_and_index(client)

    print(f"Submitting bulk request to index '{OPENSEARCH_INDEX}'")
    response = client.bulk(
        body=bulk_body,
        refresh=REFRESH_AFTER_BULK,
        request_timeout=REQUEST_TIMEOUT_SECONDS,
    )

    summary = summarize_bulk_response(response, document_count)

    try:
        count_response = client.count(index=OPENSEARCH_INDEX)
        summary["index_document_count_after_bulk"] = count_response.get("count")
    except Exception as exc:
        summary["index_document_count_after_bulk_error"] = str(exc)

    write_summary(summary)

    print("Bulk indexing summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote summary file: {SUMMARY_PATH}")

    if summary["failed_item_count"] > 0 or summary["errors"]:
        fail("Bulk indexing completed with one or more failed items. Review the summary file.")

    if summary.get("index_document_count_after_bulk") != document_count:
        fail(
            "Index document count does not match the attempted document count. "
            "Review the OpenSearch index before continuing."
        )

    print("Bulk indexing completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```

## 10. Run the bulk indexing script

From the project root, run:

```bash
python scripts/bulk_index_quotes.py
```

Expected output should include messages similar to:

```text
Reading bulk file: data/quotes-bulk.ndjson
Validated 50 bulk documents
Connected to OpenSearch cluster 'opensearch-cluster' version ...
Verified vector field 'quote_embedding' with dimension 384
Submitting bulk request to index 'quotes-v1'
Bulk indexing completed successfully
```

The script also writes:

```text
opensearch/bulk-index-summary.json
```

## 11. Review the indexing summary

### macOS or Linux

```bash
cat opensearch/bulk-index-summary.json
```

### Windows PowerShell

```powershell
Get-Content opensearch\bulk-index-summary.json
```

You should see values similar to:

```json
{
  "opensearch_index": "quotes-v1",
  "attempted_document_count": 50,
  "successful_item_count": 50,
  "failed_item_count": 0,
  "errors": false,
  "index_document_count_after_bulk": 50
}
```

The exact timestamp, OpenSearch version, and `took_ms` values may differ.

## 12. Verify the document count directly in OpenSearch

### macOS or Linux

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/quotes-v1/_count?pretty'
```

### Windows PowerShell

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200/quotes-v1/_count?pretty"
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

## 13. Retrieve one indexed document by ID

### macOS or Linux

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/quotes-v1/_doc/quote-001?pretty'
```

### Windows PowerShell

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200/quotes-v1/_doc/quote-001?pretty"
```

You should see a document that includes fields such as:

```text
id
quote
author
category
tags
search_text
quote_embedding
```

The `quote_embedding` field will be long because it contains 384 floating-point values.

## 14. Run a simple match_all query

This confirms the index can return documents through the search endpoint.

### macOS or Linux

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD"   -H 'Content-Type: application/json'   -X POST 'https://localhost:9200/quotes-v1/_search?pretty'   -d '{
    "size": 3,
    "query": {
      "match_all": {}
    },
    "_source": ["id", "quote", "author", "category", "tags"]
  }'
```

### Windows PowerShell

```powershell
$body = @'
{
  "size": 3,
  "query": {
    "match_all": {}
  },
  "_source": ["id", "quote", "author", "category", "tags"]
}
'@

curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" `
  -H "Content-Type: application/json" `
  -X POST "https://localhost:9200/quotes-v1/_search?pretty" `
  -d $body
```

Expected result:

- `hits.total.value` should be `50`
- `hits.hits` should contain 3 quote documents
- The response should omit `quote_embedding` because the `_source` filter excludes it

## 15. Run a simple keyword query

Semantic search comes in the next step, but a keyword query is useful now to confirm text fields work.

### macOS or Linux

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD"   -H 'Content-Type: application/json'   -X POST 'https://localhost:9200/quotes-v1/_search?pretty'   -d '{
    "size": 5,
    "query": {
      "match": {
        "quote": "courage"
      }
    },
    "_source": ["id", "quote", "author", "category", "tags"]
  }'
```

### Windows PowerShell

```powershell
$body = @'
{
  "size": 5,
  "query": {
    "match": {
      "quote": "courage"
    }
  },
  "_source": ["id", "quote", "author", "category", "tags"]
}
'@

curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" `
  -H "Content-Type: application/json" `
  -X POST "https://localhost:9200/quotes-v1/_search?pretty" `
  -d $body
```

It is okay if this query returns only a few results or none, depending on the exact synthetic quote text. The purpose here is to confirm the search endpoint and text query flow.

## 16. Optional: re-run indexing safely

Because Step 5 generated stable document IDs, rerunning this step should not create duplicate records.

Run again:

```bash
python scripts/bulk_index_quotes.py
```

Then check the count again:

### macOS or Linux

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/quotes-v1/_count?pretty'
```

### Windows PowerShell

```powershell
curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" "https://localhost:9200/quotes-v1/_count?pretty"
```

The count should still be:

```text
50
```

## 17. Optional: delete all quote documents and reload

During local development, you may want a clean reload without deleting the index mapping.

### macOS or Linux

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD"   -H 'Content-Type: application/json'   -X POST 'https://localhost:9200/quotes-v1/_delete_by_query?refresh=true&pretty'   -d '{
    "query": {
      "match_all": {}
    }
  }'
```

### Windows PowerShell

```powershell
$body = @'
{
  "query": {
    "match_all": {}
  }
}
'@

curl.exe -k -u "admin:$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD" `
  -H "Content-Type: application/json" `
  -X POST "https://localhost:9200/quotes-v1/_delete_by_query?refresh=true&pretty" `
  -d $body
```

Then reload:

```bash
python scripts/bulk_index_quotes.py
```

Do not use this command against production data.

## 18. Commit the Step 6 files

For this POC, commit the instruction file and the script.

Recommended commit:

```bash
git add docs/6-bulk-index-quotes.md scripts/bulk_index_quotes.py
```

If your team wants the generated summary as an example artifact, also add:

```bash
git add opensearch/bulk-index-summary.json
```

Commit:

```bash
git commit -m "Add bulk indexing step for embedded quotes"
```

Push your branch:

```bash
git push
```

If this is the first push for the branch, use:

```bash
git push --set-upstream origin your-branch-name
```

## Troubleshooting

### `Bulk file not found`

Run Step 5 first:

```bash
python scripts/generate_quote_embeddings.py
```

Then confirm:

```bash
ls -lh data/quotes-bulk.ndjson
```

### `OpenSearch password is not set`

Set the password environment variable before running the script.

macOS or Linux:

```bash
export OPENSEARCH_INITIAL_ADMIN_PASSWORD='replace-with-your-local-password'
```

Windows PowerShell:

```powershell
$env:OPENSEARCH_INITIAL_ADMIN_PASSWORD = 'replace-with-your-local-password'
```

### `Could not connect to OpenSearch`

Check that the Docker container is running:

```bash
docker ps
```

If needed, start it:

```bash
docker start opensearch-poc
```

### `Index 'quotes-v1' does not exist`

Run Step 4 first to create the OpenSearch index.

### Bulk action targets the wrong index

The `data/quotes-bulk.ndjson` file was probably generated with a different `OPENSEARCH_INDEX` value.

Regenerate it with the expected index name:

### macOS or Linux

```bash
OPENSEARCH_INDEX=quotes-v1 python scripts/generate_quote_embeddings.py
```

### Windows PowerShell

```powershell
$env:OPENSEARCH_INDEX = 'quotes-v1'
python scripts/generate_quote_embeddings.py
```

Then rerun:

```bash
python scripts/bulk_index_quotes.py
```

### Vector field is missing or not `knn_vector`

The index mapping does not match the expected Step 4 mapping.

Delete and recreate the local index using Step 4, then rerun this step.

### Count is not 50

Possible causes:

- The bulk file does not contain all 50 records.
- The bulk response had failed items.
- The index already contained extra documents.
- A prior test inserted additional data into the same index.

Review:

```bash
cat opensearch/bulk-index-summary.json
```

For a clean local reset, use the delete-by-query command in this guide, then rerun the bulk indexing script.

### PowerShell curl issues

Use `curl.exe`, not `curl`, when following the Windows PowerShell examples.

PowerShell's `curl` alias may call `Invoke-WebRequest`, which behaves differently from standard curl.

## Result

After this step, the `quotes-v1` index should contain 50 embedded quote documents.

The project is now ready for the next phase: performing semantic search by converting user queries into embeddings and running k-NN searches against the indexed quote vectors.

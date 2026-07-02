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
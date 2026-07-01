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
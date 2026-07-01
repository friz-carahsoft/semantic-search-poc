# Step 3: Creating the Sample Quotes Dataset

This guide creates a small, repeatable sample dataset for the semantic-search proof of concept.

The dataset is intentionally small and easy to inspect. It is designed to support the next steps:

- creating an OpenSearch index
- generating embeddings
- indexing documents
- testing keyword, semantic, and hybrid search behavior

## Goal

By the end of this step, you should be able to:

- Create a local `data/` folder for sample records
- Generate a quote-style dataset with predictable fields
- Save the dataset as both CSV and JSONL
- Validate the dataset before generating embeddings
- Understand which field should be embedded later

## Dataset Approach

The high-level POC plan calls for a famous-quotes-style dataset because quotes are short, diverse, and easy to evaluate during search testing.

For this local POC, this guide uses **synthetic quote-style records** instead of scraping real famous quotes.

Why?

- It avoids licensing ambiguity.
- It avoids quote misattribution problems.
- It keeps the POC fully reproducible.
- It still gives enough semantic variety to test vector search.

The records are not intended to represent real historical quotations. They are small sample text records shaped like quotes.

If you later want real famous quotes, replace this synthetic dataset with a vetted reusable source and keep source and license metadata in the dataset.

## Public Repository Notes

This step is safe to include in a public GitHub repository because it does not depend on copied quote collections or scraped external content.

Recommended practices for a shared/public repo:

- Keep the dataset synthetic unless you have verified source licensing and attribution.
- Include a top-level `LICENSE` file for the repository if this is intended for public reuse.
- Treat the generated `source_license` field as a traceability note, not as a replacement for the repository license.
- Do not commit local secrets, passwords, `.venv/`, or machine-specific configuration.
- Prefer regenerating the dataset from `scripts/create_sample_quotes_dataset.py` instead of manually editing output files.

The generated records use fictional authors and original sample text for search-testing purposes only.

## Prerequisites

Before starting this step, complete:

- Step 1: Docker setup for OpenSearch
- Step 2: Python environment setup

You do not need OpenSearch running for this step, but your Python virtual environment should be active.

From the project root, activate the virtual environment:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## Recommended Project Structure

After this step, your project should include:

```text
semantic-search-poc/
├── data/
│   ├── quotes.csv
│   └── quotes.jsonl
├── docs/
|   ├── 0-semantic-search-poc.md 
|   ├── 1-opensearch-docker-setup.md
|   ├── 2-python-environment-setup.md
│   └── 3-sample-quotes-dataset.md
├── scripts/
│   └── create_sample_quotes_dataset.py
└── requirements.txt
```

## Dataset Fields

Each quote record uses the following fields:

| Field | Purpose |
| --- | --- |
| `id` | Stable document identifier for indexing |
| `quote` | Main text content that will be embedded |
| `author` | Synthetic author name for metadata filtering |
| `category` | Broad category such as philosophy, science, literature, leadership, or humor |
| `tags` | More specific topic labels |
| `source` | Source description for traceability |
| `source_license` | Reuse note for the sample data |
| `search_text` | Combined searchable text that can be used later for keyword or hybrid search |

For the first embedding pass, use the `quote` field only. Later, you can compare results when embedding `quote` versus `search_text`.

## 1. Create the folders

From the project root, run:

### macOS or Linux

```bash
mkdir -p data scripts
```

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force -Path data, scripts
```

## 2. Create the dataset generation script

Create this file:

### macOS or Linux

```bash
touch scripts/create_sample_quotes_dataset.py
```

### Windows PowerShell

```powershell
New-Item -ItemType File -Force -Path scripts/create_sample_quotes_dataset.py
```

Open `scripts/create_sample_quotes_dataset.py` and paste the following code:

```python
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

OUT_DIR = Path("data")
CSV_PATH = OUT_DIR / "quotes.csv"
JSONL_PATH = OUT_DIR / "quotes.jsonl"

SOURCE = "Generated synthetic sample data for semantic-search POC"
SOURCE_LICENSE = "Synthetic sample data; use under this repository's license"

RECORDS = [
    {
        "id": "quote-001",
        "quote": "A quiet mind can hear the lesson hidden inside a difficult day.",
        "author": "Elias North",
        "category": "philosophy",
        "tags": ["reflection", "resilience", "wisdom"],
    },
    {
        "id": "quote-002",
        "quote": "The question that makes us uncomfortable is often the question that makes us grow.",
        "author": "Mara Ellison",
        "category": "philosophy",
        "tags": ["growth", "curiosity", "self-examination"],
    },
    {
        "id": "quote-003",
        "quote": "Patience is not standing still; it is moving without surrendering to panic.",
        "author": "Jonas Reed",
        "category": "philosophy",
        "tags": ["patience", "calm", "discipline"],
    },
    {
        "id": "quote-004",
        "quote": "Meaning is rarely discovered by accident; it is assembled through attention.",
        "author": "Nadia Vale",
        "category": "philosophy",
        "tags": ["meaning", "attention", "purpose"],
    },
    {
        "id": "quote-005",
        "quote": "The smallest honest choice can redirect the shape of an entire life.",
        "author": "Caleb Rowan",
        "category": "philosophy",
        "tags": ["integrity", "choice", "life"],
    },
    {
        "id": "quote-006",
        "quote": "We understand ourselves better when we stop treating every silence as empty.",
        "author": "Iris Camden",
        "category": "philosophy",
        "tags": ["silence", "understanding", "self-awareness"],
    },
    {
        "id": "quote-007",
        "quote": "A wise person changes direction without pretending the old road was useless.",
        "author": "Theo Marlow",
        "category": "philosophy",
        "tags": ["change", "wisdom", "humility"],
    },
    {
        "id": "quote-008",
        "quote": "Humility begins when certainty leaves enough room for wonder.",
        "author": "Lena Cross",
        "category": "philosophy",
        "tags": ["humility", "wonder", "certainty"],
    },
    {
        "id": "quote-009",
        "quote": "The truth does not become smaller when we approach it carefully.",
        "author": "Simon Bell",
        "category": "philosophy",
        "tags": ["truth", "care", "discernment"],
    },
    {
        "id": "quote-010",
        "quote": "Every boundary teaches us something about what we value.",
        "author": "Clara Finch",
        "category": "philosophy",
        "tags": ["boundaries", "values", "identity"],
    },
    {
        "id": "quote-011",
        "quote": "Science begins when wonder learns how to take notes.",
        "author": "Dr. Mira Stone",
        "category": "science",
        "tags": ["science", "wonder", "observation"],
    },
    {
        "id": "quote-012",
        "quote": "A good experiment is a question disciplined enough to be tested.",
        "author": "Dr. Nolan Pierce",
        "category": "science",
        "tags": ["experiments", "testing", "method"],
    },
    {
        "id": "quote-013",
        "quote": "Data does not speak for itself; it waits for careful questions.",
        "author": "Anika Wells",
        "category": "science",
        "tags": ["data", "questions", "analysis"],
    },
    {
        "id": "quote-014",
        "quote": "The universe rewards curiosity, but it does not grade on enthusiasm alone.",
        "author": "Dr. Felix Grant",
        "category": "science",
        "tags": ["curiosity", "evidence", "universe"],
    },
    {
        "id": "quote-015",
        "quote": "A measurement is a promise to be more precise than our first impression.",
        "author": "Rhea Morgan",
        "category": "science",
        "tags": ["measurement", "precision", "evidence"],
    },
    {
        "id": "quote-016",
        "quote": "Discovery is what happens when doubt and discipline agree to work together.",
        "author": "Dr. Owen Fields",
        "category": "science",
        "tags": ["discovery", "doubt", "discipline"],
    },
    {
        "id": "quote-017",
        "quote": "Every model is a lantern, not the landscape itself.",
        "author": "Priya Sato",
        "category": "science",
        "tags": ["models", "abstraction", "understanding"],
    },
    {
        "id": "quote-018",
        "quote": "A theory grows stronger when it survives the questions that were meant to break it.",
        "author": "Dr. Helena Brooks",
        "category": "science",
        "tags": ["theory", "testing", "strength"],
    },
    {
        "id": "quote-019",
        "quote": "The best tools make complex things visible without pretending they are simple.",
        "author": "Marcus Chen",
        "category": "science",
        "tags": ["tools", "complexity", "visibility"],
    },
    {
        "id": "quote-020",
        "quote": "Evidence is patience wearing a lab coat.",
        "author": "Dr. Tessa Gray",
        "category": "science",
        "tags": ["evidence", "patience", "research"],
    },
    {
        "id": "quote-021",
        "quote": "A story is a bridge between what happened and what it meant.",
        "author": "Julian West",
        "category": "literature",
        "tags": ["story", "meaning", "memory"],
    },
    {
        "id": "quote-022",
        "quote": "The right sentence can open a window in a room we thought had no air.",
        "author": "Amelia Hart",
        "category": "literature",
        "tags": ["writing", "language", "hope"],
    },
    {
        "id": "quote-023",
        "quote": "Books let us borrow courage from people who never met us.",
        "author": "Rowan Blake",
        "category": "literature",
        "tags": ["books", "courage", "empathy"],
    },
    {
        "id": "quote-024",
        "quote": "A character becomes real when their weakness starts telling the truth.",
        "author": "Elena Frost",
        "category": "literature",
        "tags": ["characters", "truth", "weakness"],
    },
    {
        "id": "quote-025",
        "quote": "Poetry is language walking slowly enough to notice the flowers.",
        "author": "Bennett Cole",
        "category": "literature",
        "tags": ["poetry", "language", "attention"],
    },
    {
        "id": "quote-026",
        "quote": "A page can hold an entire storm without spilling a drop.",
        "author": "Cora James",
        "category": "literature",
        "tags": ["page", "emotion", "imagination"],
    },
    {
        "id": "quote-027",
        "quote": "Revision is the art of listening to what the draft tried to say.",
        "author": "Miles Archer",
        "category": "literature",
        "tags": ["revision", "drafting", "writing"],
    },
    {
        "id": "quote-028",
        "quote": "The reader completes the journey the writer only begins.",
        "author": "Sofia Lane",
        "category": "literature",
        "tags": ["reader", "writer", "journey"],
    },
    {
        "id": "quote-029",
        "quote": "Fiction tells the truth by changing the names of the doors.",
        "author": "Graham Wilde",
        "category": "literature",
        "tags": ["fiction", "truth", "imagination"],
    },
    {
        "id": "quote-030",
        "quote": "A library is a quiet argument against despair.",
        "author": "Nora Quinn",
        "category": "literature",
        "tags": ["library", "hope", "knowledge"],
    },
    {
        "id": "quote-031",
        "quote": "Leadership is the decision to carry responsibility before carrying authority.",
        "author": "Evan Brooks",
        "category": "leadership",
        "tags": ["responsibility", "authority", "leadership"],
    },
    {
        "id": "quote-032",
        "quote": "A team trusts a leader who explains the mountain before demanding the climb.",
        "author": "Grace Porter",
        "category": "leadership",
        "tags": ["teams", "trust", "clarity"],
    },
    {
        "id": "quote-033",
        "quote": "The strongest leaders make the next decision easier for everyone else.",
        "author": "Nathan Brooks",
        "category": "leadership",
        "tags": ["decisions", "clarity", "service"],
    },
    {
        "id": "quote-034",
        "quote": "Influence grows when people feel seen, not managed.",
        "author": "Isabel Hart",
        "category": "leadership",
        "tags": ["influence", "people", "empathy"],
    },
    {
        "id": "quote-035",
        "quote": "A clear mission turns busy work into forward motion.",
        "author": "Derek Shaw",
        "category": "leadership",
        "tags": ["mission", "focus", "execution"],
    },
    {
        "id": "quote-036",
        "quote": "The best leaders protect the room where honest feedback can survive.",
        "author": "Leah Bennett",
        "category": "leadership",
        "tags": ["feedback", "trust", "culture"],
    },
    {
        "id": "quote-037",
        "quote": "Vision without listening becomes a speech no one follows.",
        "author": "Thomas Vale",
        "category": "leadership",
        "tags": ["vision", "listening", "alignment"],
    },
    {
        "id": "quote-038",
        "quote": "A leader earns speed by first earning alignment.",
        "author": "Monica Reed",
        "category": "leadership",
        "tags": ["alignment", "speed", "execution"],
    },
    {
        "id": "quote-039",
        "quote": "Accountability is not blame; it is ownership with a calendar.",
        "author": "Peter Cross",
        "category": "leadership",
        "tags": ["accountability", "ownership", "execution"],
    },
    {
        "id": "quote-040",
        "quote": "Great teams do not avoid hard conversations; they learn how to survive them.",
        "author": "Megan Stone",
        "category": "leadership",
        "tags": ["teams", "conflict", "communication"],
    },
    {
        "id": "quote-041",
        "quote": "My calendar has a sense of humor, but it mostly writes tragedies.",
        "author": "Leo Finch",
        "category": "humor",
        "tags": ["calendar", "work", "time"],
    },
    {
        "id": "quote-042",
        "quote": "I cleaned my desk by moving the mystery pile to a more strategic location.",
        "author": "Penny Lane",
        "category": "humor",
        "tags": ["desk", "organization", "work"],
    },
    {
        "id": "quote-043",
        "quote": "Coffee is proof that beans understand project deadlines.",
        "author": "Maxwell Grant",
        "category": "humor",
        "tags": ["coffee", "deadlines", "work"],
    },
    {
        "id": "quote-044",
        "quote": "I bought a notebook for my plans, and now my plans are to buy more notebooks.",
        "author": "Daisy Moore",
        "category": "humor",
        "tags": ["notebooks", "planning", "habits"],
    },
    {
        "id": "quote-045",
        "quote": "The printer only jams when it senses confidence.",
        "author": "Harvey Miles",
        "category": "humor",
        "tags": ["printer", "office", "technology"],
    },
    {
        "id": "quote-046",
        "quote": "My password manager knows me better than some relatives do.",
        "author": "Tina Clarke",
        "category": "humor",
        "tags": ["passwords", "technology", "identity"],
    },
    {
        "id": "quote-047",
        "quote": "A quick meeting is any meeting that ends before the snacks become necessary.",
        "author": "Walter Price",
        "category": "humor",
        "tags": ["meetings", "snacks", "work"],
    },
    {
        "id": "quote-048",
        "quote": "My inbox is not full; it is conducting a stress test.",
        "author": "Olivia Penn",
        "category": "humor",
        "tags": ["email", "stress", "work"],
    },
    {
        "id": "quote-049",
        "quote": "I enjoy multitasking because it lets me be confused in several directions at once.",
        "author": "Frankie Cole",
        "category": "humor",
        "tags": ["multitasking", "confusion", "productivity"],
    },
    {
        "id": "quote-050",
        "quote": "The cloud is just someone else's computer with better marketing.",
        "author": "Riley Banks",
        "category": "humor",
        "tags": ["cloud", "technology", "marketing"],
    },
]


def build_search_text(record: dict) -> str:
    tags = ", ".join(record["tags"])
    return (
        f'{record["quote"]} '
        f'Author: {record["author"]}. '
        f'Category: {record["category"]}. '
        f'Tags: {tags}.'
    )


def validate_records(records: list[dict]) -> None:
    required_fields = {"id", "quote", "author", "category", "tags"}
    allowed_categories = {"philosophy", "science", "literature", "leadership", "humor"}

    if len(records) != 50:
        raise ValueError(f"Expected 50 records, found {len(records)}")

    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate ids found")

    quotes = [record["quote"] for record in records]
    if len(quotes) != len(set(quotes)):
        raise ValueError("Duplicate quote text found")

    for record in records:
        missing = required_fields - record.keys()
        if missing:
            raise ValueError(f"Record {record.get('id', '<unknown>')} is missing fields: {missing}")

        if record["category"] not in allowed_categories:
            raise ValueError(f"Invalid category for {record['id']}: {record['category']}")

        if not isinstance(record["tags"], list) or not record["tags"]:
            raise ValueError(f"Record {record['id']} must have at least one tag")


def main() -> None:
    validate_records(RECORDS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    enriched_records = []
    for record in RECORDS:
        enriched = {
            **record,
            "source": SOURCE,
            "source_license": SOURCE_LICENSE,
            "search_text": build_search_text(record),
        }
        enriched_records.append(enriched)

    csv_records = []
    for record in enriched_records:
        csv_record = {**record, "tags": ";".join(record["tags"])}
        csv_records.append(csv_record)

    df = pd.DataFrame(csv_records)
    df.to_csv(CSV_PATH, index=False)

    with JSONL_PATH.open("w", encoding="utf-8") as jsonl_file:
        for record in enriched_records:
            jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(enriched_records)} records to {CSV_PATH}")
    print(f"Wrote {len(enriched_records)} records to {JSONL_PATH}")
    print()
    print("Category counts:")
    print(df["category"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
```

## 3. Run the dataset script

Make sure your virtual environment is active, then run:

```bash
python scripts/create_sample_quotes_dataset.py
```

Expected output:

```text
Wrote 50 records to data/quotes.csv
Wrote 50 records to data/quotes.jsonl

Category counts:
humor         10
leadership    10
literature    10
philosophy    10
science       10
```

## 4. Verify the files exist

Run:

```bash
ls -lh data
```

You should see:

```text
quotes.csv
quotes.jsonl
```

## 5. Inspect the CSV file

Run:

```bash
python -c "import pandas as pd; df = pd.read_csv('data/quotes.csv'); print(df.head())"
```

You should see the first few records with columns similar to:

```text
id quote author category tags source source_license search_text
```

## 6. Validate category distribution

Run:

```bash
python -c "import pandas as pd; df = pd.read_csv('data/quotes.csv'); print(df['category'].value_counts().sort_index())"
```

Expected output:

```text
humor         10
leadership    10
literature    10
philosophy    10
science       10
Name: count, dtype: int64
```

Depending on your pandas version, the final line may display slightly differently. The important part is that each category has 10 records.

## 7. Validate JSONL loading

JSONL is often more convenient for indexing pipelines because each line is one document.

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path('data/quotes.jsonl')
records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]

print(f'Loaded {len(records)} JSONL records')
print(records[0])
PY
```

Expected output should begin with:

```text
Loaded 50 JSONL records
```

## 8. Confirm the field to embed later

For the first semantic-search pass, embed this field:

```text
quote
```

That means the embedding text for `quote-001` would be:

```text
A quiet mind can hear the lesson hidden inside a difficult day.
```

Later, you can compare results by embedding this richer field instead:

```text
search_text
```

The `search_text` field includes the quote, author, category, and tags. That can improve hybrid search and metadata-aware experiments, but it may also make semantic results more influenced by category/tag labels.

## 9. Optional: quick semantic-readiness check

This does not generate embeddings yet. It only confirms the records contain enough topic variety for semantic search testing.

Run:

```bash
python - <<'PY'
import pandas as pd

df = pd.read_csv('data/quotes.csv')

checks = {
    'determination/resilience': df[df['tags'].str.contains('resilience|discipline|patience', case=False, regex=True)],
    'data/science': df[df['tags'].str.contains('data|evidence|testing|models', case=False, regex=True)],
    'workplace humor': df[df['tags'].str.contains('work|meetings|email|office', case=False, regex=True)],
}

for label, matches in checks.items():
    print(f'\n{label}: {len(matches)} matching records')
    print(matches[['id', 'category', 'quote']].head(3).to_string(index=False))
PY
```

This should print a few records for each rough topic area.

## 10. Recommended commit

For this POC, it is reasonable to commit both the generator script and the generated dataset. That makes the next steps easier for teammates because everyone starts with identical input records.

After confirming the files are generated correctly, commit the dataset script and generated sample data:

```bash
git status
git add scripts/create_sample_quotes_dataset.py data/quotes.csv data/quotes.jsonl
git commit -m "Add sample quotes dataset"
```

This is a good point to commit because the POC now has stable input data for later embedding and indexing steps.

If your team prefers generated artifacts to stay out of source control, commit only `scripts/create_sample_quotes_dataset.py` and add instructions for each teammate to run the script locally. For this small POC, committing the generated CSV and JSONL keeps the walkthrough simpler.

## Troubleshooting

### `ModuleNotFoundError: No module named 'pandas'`

Your virtual environment may not be active, or the Step 2 dependencies may not have installed correctly.

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Then reinstall dependencies if needed:

```bash
python -m pip install pandas
```

### The script runs but files are created somewhere unexpected

Make sure you ran the script from the project root:

```bash
pwd
```

Then run:

```bash
python scripts/create_sample_quotes_dataset.py
```

The script writes to `data/quotes.csv` and `data/quotes.jsonl` relative to the current working directory.

### The category count is not 10 per category

Do not manually edit `data/quotes.csv` or `data/quotes.jsonl` at this stage. Edit `scripts/create_sample_quotes_dataset.py`, rerun it, and regenerate both output files.

### You want to use real famous quotes instead

Do not swap in a downloaded quote collection casually. A quote dataset can have several separate concerns: the quote text, the attribution, the dataset compilation, and the hosting site terms.

Create a separate dataset source and keep these fields:

- `id`
- `quote`
- `author`
- `category`
- `tags`
- `source`
- `source_license`
- `search_text`

Before using real quotes in a shared or public repo, verify:

- quote accuracy
- attribution accuracy
- source terms of use
- license compatibility
- whether any quotes are copyrighted or only available under fair use

## Result

After this step, you should have a clean sample dataset in both CSV and JSONL format:

```text
data/quotes.csv
data/quotes.jsonl
```

The project is now ready for the next phase: creating an OpenSearch index with text fields, metadata fields, and a `knn_vector` field sized to match the embedding model.

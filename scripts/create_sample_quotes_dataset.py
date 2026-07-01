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
# Step 9 Hybrid Weight Tuning Summary

Generated at: `2026-07-02T16:30:58.122310+00:00`

This file compares hybrid search results across multiple keyword/semantic weight combinations.

The final `Reviewer Notes` column is intentionally blank. Use it during team review to document which result is preferred and why.

Default review score:

| Score | Meaning |
| ---: | --- |
| `3` | Excellent: directly satisfies the query intent |
| `2` | Good: useful and related |
| `1` | Weak: related but probably unsatisfying |
| `0` | Poor: irrelevant or misleading |

## Query: `perseverance`

| Weights | Top ID | Score | Category | Top Result | Reviewer Notes |
| --- | --- | ---: | --- | --- | --- |
| keyword=0.70, semantic=0.30 | `quote-016` | 0.300000 | science | Discovery is what happens when doubt and discipline agree to work together. — Dr. Owen Fields |  |
| keyword=0.50, semantic=0.50 | `quote-016` | 0.500000 | science | Discovery is what happens when doubt and discipline agree to work together. — Dr. Owen Fields |  |
| keyword=0.30, semantic=0.70 | `quote-016` | 0.700000 | science | Discovery is what happens when doubt and discipline agree to work together. — Dr. Owen Fields |  |

## Query: `quotes about never giving up`

| Weights | Top ID | Score | Category | Top Result | Reviewer Notes |
| --- | --- | ---: | --- | --- | --- |
| keyword=0.70, semantic=0.30 | `quote-010` | 0.700000 | philosophy | Every boundary teaches us something about what we value. — Clara Finch |  |
| keyword=0.50, semantic=0.50 | `quote-023` | 0.500500 | literature | Books let us borrow courage from people who never met us. — Rowan Blake |  |
| keyword=0.30, semantic=0.70 | `quote-023` | 0.700300 | literature | Books let us borrow courage from people who never met us. — Rowan Blake |  |

## Query: `curiosity and discovery`

| Weights | Top ID | Score | Category | Top Result | Reviewer Notes |
| --- | --- | ---: | --- | --- | --- |
| keyword=0.70, semantic=0.30 | `quote-016` | 0.914246 | science | Discovery is what happens when doubt and discipline agree to work together. — Dr. Owen Fields |  |
| keyword=0.50, semantic=0.50 | `quote-016` | 0.857076 | science | Discovery is what happens when doubt and discipline agree to work together. — Dr. Owen Fields |  |
| keyword=0.30, semantic=0.70 | `quote-014` | 0.811934 | science | The universe rewards curiosity, but it does not grade on enthusiasm alone. — Dr. Felix Grant |  |

## Query: `leading with humility`

| Weights | Top ID | Score | Category | Top Result | Reviewer Notes |
| --- | --- | ---: | --- | --- | --- |
| keyword=0.70, semantic=0.30 | `quote-008` | 1.000000 | philosophy | Humility begins when certainty leaves enough room for wonder. — Lena Cross |  |
| keyword=0.50, semantic=0.50 | `quote-008` | 1.000000 | philosophy | Humility begins when certainty leaves enough room for wonder. — Lena Cross |  |
| keyword=0.30, semantic=0.70 | `quote-008` | 1.000000 | philosophy | Humility begins when certainty leaves enough room for wonder. — Lena Cross |  |

## Query: `finding humor in mistakes`

| Weights | Top ID | Score | Category | Top Result | Reviewer Notes |
| --- | --- | ---: | --- | --- | --- |
| keyword=0.70, semantic=0.30 | `quote-041` | 1.000000 | humor | My calendar has a sense of humor, but it mostly writes tragedies. — Leo Finch |  |
| keyword=0.50, semantic=0.50 | `quote-041` | 1.000000 | humor | My calendar has a sense of humor, but it mostly writes tragedies. — Leo Finch |  |
| keyword=0.30, semantic=0.70 | `quote-041` | 1.000000 | humor | My calendar has a sense of humor, but it mostly writes tragedies. — Leo Finch |  |

## Query: `learning from failure`

| Weights | Top ID | Score | Category | Top Result | Reviewer Notes |
| --- | --- | ---: | --- | --- | --- |
| keyword=0.70, semantic=0.30 | `quote-023` | 0.700000 | literature | Books let us borrow courage from people who never met us. — Rowan Blake |  |
| keyword=0.50, semantic=0.50 | `quote-023` | 0.500000 | literature | Books let us borrow courage from people who never met us. — Rowan Blake |  |
| keyword=0.30, semantic=0.70 | `quote-016` | 0.700000 | science | Discovery is what happens when doubt and discipline agree to work together. — Dr. Owen Fields |  |

## Review Prompts

Use this summary to discuss:

- Did keyword-heavy hybrid search preserve useful exact matches?
- Did semantic-heavy hybrid search improve conceptual matches?
- Did balanced hybrid search provide the best compromise?
- Were any top results technically related but not useful?
- Which weighting approach would be safest as a production default?


# PaySave Catalog Builder — Agent-Readable Catalog Builder
**Razorpay AI Buildathon — Track 1: AI Growth & Agentic Commerce**

Turns messy, unstructured merchant product listings into a strict, machine-readable
YAML catalog — complete with an explainable audit trail — and demonstrates an AI
buyer agent actually querying that catalog in natural language.

## The Problem

Merchants write product listings the way humans write — inconsistent formats, mixed
units, ambiguous availability, missing details. An AI shopping agent can't reliably
transact against that. This project builds the translation layer: raw merchant text
in, strict validated schema out, with every extraction decision explained.

## Architecture

```
Merchant text (raw, messy)
        │
        ▼
┌───────────────────┐      ┌──────────────────┐
│   extract.py       │─────▶│  llm_provider.py │  (Strategy: Gemini primary,
│  (extraction        │      │  Gemini / Groq   │   Groq fallback on failure)
│   pipeline)         │      └──────────────────┘
└───────────────────┘
        │ validates against
        ▼
┌───────────────────┐
│    schema.py        │  Pydantic models — Product, Variant, Price,
│  (strict contract)   │  Metadata (confidence + notes), QueryIntent
└───────────────────┘
        │ writes
        ▼
   catalog.yaml  +  audit_log.json
        │
        ▼
┌────────────────────┐      ┌──────────────────────┐
│ catalog_repository.py│◀────│   buyer_agent.py      │
│ (Repository pattern:  │     │  (DI: repo + LLM       │
│  isolates data access)│     │   injected, not        │
│                        │     │   hardcoded)            │
└────────────────────┘      └──────────────────────┘
                                       ▲
                              Natural language question
                              ("running shoes size 9?")
```

## Design Principles Applied

- **Repository pattern** — `CatalogRepository` is the only file that knows
  `catalog.yaml` exists. Swapping YAML for a real database later means changing
  one file, not every consumer of catalog data.
- **Dependency Injection** — `BuyerAgent` receives its repository and LLM provider
  as constructor arguments rather than constructing them internally, making it
  testable and provider-agnostic.
- **Strategy pattern (partial)** — `llm_provider.py` lets Gemini and Groq be
  swapped via a single parameter. Currently implemented as a factory function
  rather than a full abstract-base-class hierarchy — a known simplification (see
  Limitations).
- **Fail-fast validation** — every LLM extraction is validated against a strict
  Pydantic schema before it's trusted. Malformed output is rejected and retried,
  never silently accepted.
- **Explainable audit trail** — every extraction and every query carries a
  `source_confidence` score and human-readable notes on what was ambiguous or
  assumed, so nothing the agent decides is a black box.

## Setup

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows PowerShell
pip install langchain langchain-groq langchain-google-genai pandas pyyaml python-dotenv pydantic
```

Create a `.env` file in the project root:
```
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_gemini_key
```

## Running It

**1. Build the catalog from sample merchant listings:**
```bash
python extract.py
```
Outputs `catalog.yaml` (the structured catalog) and `audit_log.json` (the audit trail).

**2. Query it as an AI buyer would:**
```bash
python buyer_agent.py
```
Runs a few natural-language test questions against the catalog and shows the parsed
intent, matched products, and generated answer for each.

## What the Audit Trail Actually Catches

One sample listing (running shoes) has genuinely ambiguous source text: price varies
by size with no clear per-size breakdown, and color options aren't specified at all.
The pipeline:
- Assigns a lower `source_confidence` (0.75 vs 0.95 for clean listings)
- Explicitly notes what was ambiguous or assumed in `extraction_notes`
- Correctly infers per-variant availability (sizes 8/9 in stock, 7/10 preorder) as
  **structured, queryable data** rather than burying it in a sentence

## Bugs Found & Fixed During Development

1. **Category mismatch:** the buyer agent's query parser extracted intents like
   `category: "running shoes"`, but the catalog stores categories as `"footwear"`.
   Exact-match filtering silently returned zero results. Fixed by replacing
   category/tag filters with a single fuzzy keyword filter checking category, tags,
   and product name together.
2. **Plural mismatch:** even the fuzzy filter missed `"t-shirts"` (customer phrasing)
   against `"t-shirt"` (stored tag) because substring matching only works in one
   direction. Fixed by normalizing trailing `'s'` on both sides before comparing.

Both bugs are a reminder that the same real-world messiness the extraction pipeline
handles on the way in doesn't disappear on the way out — query-side language needs
the same tolerance for inconsistency as merchant-side data does.

## Known Limitations

- `llm_provider.py` uses a factory function rather than a full Strategy pattern
  with an abstract base class — functionally equivalent, less textbook.
- Sample data is synthetic (4 listings); not tested against real merchant catalog
  dumps at scale.
- No persistence beyond flat files — a production version would back
  `CatalogRepository` with a real database, which the pattern already supports.
- WhatsApp/SMS-style buyer interaction is simulated via CLI, not a real messaging
  channel.

## Stack

Python, LangChain, Google Gemini (`gemini-3.6-flash`) + Groq (`openai/gpt-oss-120b`)
as a resilient dual-provider setup, Pydantic for schema enforcement, PyYAML.

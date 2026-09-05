import json
import yaml
from datetime import datetime, timezone
from pydantic import ValidationError

from llm_provider import get_llm
from schema import Product
from sample_merchant_text import SAMPLE_LISTINGS

EXTRACTION_PROMPT = """You are a precise data extraction engine for an e-commerce catalog system.
Extract structured product information from the raw merchant listing below.

Return ONLY a valid JSON object matching this exact structure (no markdown, no extra text):
{{
  "product_id": "a short slug you generate from the product name, e.g. 'classic-cotton-tshirt'",
  "name": "string",
  "category": "string",
  "description": "string, 1-2 sentences summarizing the product",
  "price": {{"amount": number, "currency": "INR"}},
  "availability": "in_stock" | "out_of_stock" | "preorder",
  "variants": [
    {{"variant_id": "string", "attribute": "string e.g. size/color", "value": "string", "price_delta": number, "stock_count": number or null, "availability": "in_stock" | "out_of_stock" | "preorder" | null}}
  ],
  "tags": ["list", "of", "relevant", "search", "tags"],
  "metadata": {{
    "source_confidence": a number between 0 and 1 representing how confident you are in this extraction,
    "extraction_notes": "flag anything ambiguous, missing, or assumed in the source text. Use null if nothing to flag."
  }}
}}

RULES:
- If pricing varies by variant, use the BASE/LOWEST price as "amount" and encode differences as price_delta on each variant.
- If availability info is unclear, make your best judgement but lower source_confidence and explain in extraction_notes.
- NEVER invent details not present or implied in the text (e.g. don't guess a color if none is mentioned) — instead, note the gap in extraction_notes.
- product_id must be lowercase, hyphen-separated, no spaces.
-If different variants have different availability (e.g. some sizes in stock, others preorder), set per-variant availability instead of only relying on the top-level field.

MERCHANT LISTING:
{listing}
"""

def extract_one(listing: str, provider: str = "gemini", retries: int = 2) -> tuple[Product | None, str | None]:
    """
    Attempts to extract and validate one listing. Falls back from gemini to groq on failure.
    Returns (validated Product or None, raw error string or None).
    """
    llm = get_llm(provider)
    prompt = EXTRACTION_PROMPT.format(listing=listing)

    for attempt in range(retries):
        try:
            response = llm.invoke(prompt)
            raw_text = response.content
            # Handle Gemini's occasional list-of-blocks content format
            if isinstance(raw_text, list):
                raw_text = "".join(
                    block.get("text", "") for block in raw_text if isinstance(block, dict)
                )
            # Strip markdown code fences if the model added them anyway
            cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed_json = json.loads(cleaned)
            product = Product(**parsed_json)
            return product, None
        except (json.JSONDecodeError, ValidationError, Exception) as e:
            error_msg = f"[{provider}] attempt {attempt+1} failed: {type(e).__name__}: {e}"
            if attempt == retries - 1:
                if provider == "gemini":
                    print(f"  Falling back to groq after gemini failure...")
                    return extract_one(listing, provider="groq", retries=retries)
                return None, error_msg
    return None, "Exhausted retries"


def run_catalog_build():
    catalog = []
    audit_log = []

    for i, listing in enumerate(SAMPLE_LISTINGS):
        print(f"\nProcessing listing {i+1}/{len(SAMPLE_LISTINGS)}...")
        product, error = extract_one(listing)

        entry = {
            "listing_index": i,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_input_preview": listing.strip()[:80] + "...",
            "success": product is not None,
        }

        if product:
            catalog.append(product.model_dump())
            entry["product_id"] = product.product_id
            entry["source_confidence"] = product.metadata.source_confidence
            entry["extraction_notes"] = product.metadata.extraction_notes
            print(f"  ✓ Extracted: {product.name} (confidence: {product.metadata.source_confidence})")
        else:
            entry["error"] = error
            print(f"  ✗ FAILED: {error}")

        audit_log.append(entry)

    # Write the final catalog as strict YAML
    with open("catalog.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"products": catalog}, f, sort_keys=False, allow_unicode=True)

    # Write the explainable audit trail
    with open("audit_log.json", "w", encoding="utf-8") as f:
        json.dump(audit_log, f, indent=2)

    success_count = sum(1 for e in audit_log if e["success"])
    print(f"\n{'='*50}")
    print(f"Done: {success_count}/{len(SAMPLE_LISTINGS)} listings extracted successfully")
    print(f"Catalog written to catalog.yaml")
    print(f"Audit trail written to audit_log.json")


if __name__ == "__main__":
    run_catalog_build()
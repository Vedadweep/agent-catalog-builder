"""
BuyerAgent simulates an AI shopping agent reading your merchant's catalog.
Note the constructor: it receives its LLM and repository as arguments
(Dependency Injection) rather than constructing them internally. This means
you can test BuyerAgent with a fake repository and no real LLM call at all,
and you can swap Gemini for Groq without touching this class.
"""

import json
from llm_provider import get_llm
from catalog_repository import CatalogRepository
from schema import QueryIntent, Product

INTENT_PROMPT = """You are a shopping assistant's query interpreter.
Convert the customer's question into a structured JSON filter matching this schema:
{{
  "keyword": "a general product-type or descriptive term from the question (e.g. 'running shoes', 'electronics') or null",
  "min_price": number or null,
  "max_price": number or null,
  "variant_attribute": "string (e.g. 'size', 'color') or null",
  "variant_value": "string or null",
  "reasoning": "one sentence on how you interpreted the question"
}}

Only fill fields relevant to the question. Return ONLY the JSON, no markdown.

CUSTOMER QUESTION: {question}
"""

ANSWER_PROMPT = """You are a helpful shopping assistant. A customer asked: "{question}"

Here are the matching products from the catalog (as JSON):
{products_json}

Write a short, natural, helpful response (2-4 sentences) summarizing what's
available. If nothing matched, say so plainly and suggest what to try instead.
Do not invent products or details not in the data provided.
"""


class BuyerAgent:
    def __init__(self, repository: CatalogRepository, provider: str = "gemini"):
        self._repository = repository
        self._llm = get_llm(provider)

    def _parse_intent(self, question: str, retries: int = 2) -> QueryIntent:
        """Mirrors extract.py's resilience: retry, then fall back to Groq
        if Gemini's output can't be parsed — a live demo shouldn't crash
        just because one model call returned malformed JSON."""
        for attempt in range(retries):
            try:
                response = self._llm.invoke(INTENT_PROMPT.format(question=question))
                raw = response.content
                if isinstance(raw, list):
                    raw = "".join(b.get("text", "") for b in raw if isinstance(b, dict))
                cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                return QueryIntent(**json.loads(cleaned))
            except Exception as e:
                if attempt == retries - 1:
                    print(f"  Intent parsing failed after {retries} attempts ({e}); falling back to a broad search.")
                    return QueryIntent(reasoning=f"Fallback: could not parse intent ({e})")
        raise RuntimeError("Unreachable")

    def _query_repository(self, intent: QueryIntent) -> list[Product]:
        results = self._repository.get_all()
        if intent.min_price is not None or intent.max_price is not None:
            price_matches = self._repository.find_in_price_range(
                intent.min_price or 0, intent.max_price or float("inf")
            )
            results = [p for p in results if p in price_matches]
        if intent.variant_attribute and intent.variant_value:
            variant_matches = self._repository.find_variant_available(
                intent.variant_attribute, intent.variant_value
            )
            results = [p for p in results if p in variant_matches]
        if intent.keyword:
            keyword_matches = self._repository.find_by_keyword(intent.keyword)
            results = [p for p in results if p in keyword_matches]

        return results

    def answer(self, question: str) -> dict:
        """Returns a dict with the answer AND the full audit trail of how we got there —
        the intent we parsed, and which products matched — so nothing is a black box."""
        intent = self._parse_intent(question)
        matches = self._query_repository(intent)

        products_json = json.dumps([p.model_dump() for p in matches], indent=2)
        response = self._llm.invoke(ANSWER_PROMPT.format(question=question, products_json=products_json))
        answer_text = response.content
        if isinstance(answer_text, list):
            answer_text = "".join(b.get("text", "") for b in answer_text if isinstance(b, dict))

        return {
            "question": question,
            "parsed_intent": intent.model_dump(),
            "matched_product_ids": [p.product_id for p in matches],
            "answer": answer_text,
        }


if __name__ == "__main__":
    repo = CatalogRepository("catalog.yaml")
    agent = BuyerAgent(repo)

    test_questions = [
        "Do you have running shoes in size 9?",
        "What t-shirts do you have under 700 rupees?",
        "Show me anything in electronics",
    ]

    for q in test_questions:
        print(f"\nQ: {q}")
        result = agent.answer(q)
        print(f"Parsed intent: {result['parsed_intent']}")
        print(f"Matched: {result['matched_product_ids']}")
        print(f"A: {result['answer']}")
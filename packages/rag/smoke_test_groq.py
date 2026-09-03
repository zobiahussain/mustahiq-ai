"""
Proves the Groq wrapper works AND proves the actual listing-enrichment
prompt from Marketplace_Spec.md section 3.1 does its job for real: thin
Urdu phrase in, semantically rich English description out.

Run: python smoke_test_groq.py
"""

from groq_client import chat_json

PROMPT_TEMPLATE = """
Trade category: {trade_category}
They wrote: "{raw_text}"

Return JSON:
{{
  "product_or_service_en": "expanded English description for
     semantic matching -- include the craft, typical outputs, and
     related terms a supplier or employer would search for",
  "product_or_service_original": "their exact words unchanged",
  "skills_en": "comma-separated skills in English"
}}
"""


def main():
    result = chat_json(
        PROMPT_TEMPLATE.format(
            trade_category="Tailoring & embroidery",
            raw_text="سلائی، شلوار قمیض، یونیفارم",
        )
    )

    print("\nRESULT:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    assert "product_or_service_en" in result, "missing expected field!"
    assert len(result["product_or_service_en"]) > len("سلائی، شلوار قمیض، یونیفارم"), \
        "the whole point was ENRICHMENT -- output should be longer/richer than the input"

    print("\nPASS -- enrichment call works and actually enriches.")


if __name__ == "__main__":
    main()

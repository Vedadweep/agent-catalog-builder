from llm_provider import get_llm

for provider in ["gemini", "groq"]:
    print(f"\n--- Testing {provider} ---")
    try:
        llm = get_llm(provider)
        response = llm.invoke("Say hello in one short sentence.")
        print(response.content)
    except Exception as e:
        print(f"ERROR with {provider}: {e}")
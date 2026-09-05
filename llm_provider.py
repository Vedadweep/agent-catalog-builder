import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

load_dotenv()

def get_llm(provider: str = "gemini", temperature: float = 0):
    """
    Returns a chat LLM instance. Switch providers by passing 'gemini' or 'groq'.
    Gemini is primary (better structured-output adherence for our catalog schema).
    Groq is the fast fallback if we hit Gemini's per-minute rate limit.
    """
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            temperature=temperature,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    elif provider == "groq":
        return ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=temperature,
            groq_api_key=os.getenv("GROQ_API_KEY"),
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")
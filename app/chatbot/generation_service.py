import os
import re
import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

FALLBACK_MESSAGES = {
    "en": "I couldn't find enough reliable information in the civic knowledge base to answer this question. Please contact your local municipal ward office or submit a civic grievance.",
    "ta": "இந்தக் கேள்விக்கு பதிலளிக்க நகராட்சி அறிவுத் தளத்தில் போதுமான நம்பகமான தகவலை என்னால் கண்டுபிடிக்க முடியவில்லை. உங்கள் உள்ளூர் நகராட்சி அலுவலகத்தைத் தொடர்பு கொள்ளவும் அல்லது குடிமக்கள் குறையை சமர்ப்பிக்கவும்.",
    "hi": "इस प्रश्न का उत्तर देने के लिए मुझे नागरिक ज्ञानकोश में पर्याप्त विश्वसनीय जानकारी नहीं मिली। कृपया अपने स्थानीय नगर निगम वार्ड कार्यालय से संपर्क करें या नागरिक शिकायत दर्ज करें।",
}


class BaseGenerationProvider:
    """Abstract generation interface."""

    def generate_answer(self, question: str, context_chunks: List[Dict[str, Any]], language: str = "en") -> str:
        raise NotImplementedError


class LocalExtractiveGenerationProvider(BaseGenerationProvider):
    """
    Real, deterministic civic synthesis provider that generates answers
    strictly from verified retrieved knowledge base chunks.
    Guarantees ZERO hallucinations, zero fabricated telephone numbers,
    and zero invented government regulations.
    """

    def generate_answer(self, question: str, context_chunks: List[Dict[str, Any]], language: str = "en") -> str:
        lang = language.lower() if language in ("en", "ta", "hi") else "en"

        if not context_chunks:
            return FALLBACK_MESSAGES.get(lang, FALLBACK_MESSAGES["en"])

        # Extract relevant content sentences from the top retrieved chunks
        relevant_points = []
        q_tokens = set(re.findall(r"\w+", question.lower()))

        for chunk in context_chunks:
            text = chunk.get("text", "")
            title = chunk.get("title", "")
            section = chunk.get("section", "")
            source = chunk.get("source", "")

            # Split into individual sentences or clauses
            sentences = re.split(r"(?<=[.!?\n])\s+", text)
            for s in sentences:
                s_clean = s.strip()
                if len(s_clean) < 15:
                    continue
                # Score sentence relevance by query overlap
                s_tokens = set(re.findall(r"\w+", s_clean.lower()))
                overlap = len(q_tokens.intersection(s_tokens))
                if overlap > 0 or len(relevant_points) < 3:
                    if s_clean not in relevant_points:
                        relevant_points.append(s_clean)

        if not relevant_points:
            # Fallback to chunk texts directly
            relevant_points = [c.get("text", "").strip() for c in context_chunks[:2] if c.get("text")]

        # Format synthesized response
        primary_chunk = context_chunks[0]
        dept = primary_chunk.get("department", "Municipal Administration")
        doc_title = primary_chunk.get("title", "Official Civic Standard")

        if lang == "ta":
            intro = f"அதிகாரப்பூர்வ நகராட்சி வழிகாட்டுதல்களின்படி ({doc_title}):"
            bullets = "\n".join([f"• {p}" for p in relevant_points[:4]])
            answer = f"{intro}\n\n{bullets}\n\nபொறுப்பான துறை: {dept}."
        elif lang == "hi":
            intro = f"आधिकारिक नगरपालिका दिशानिर्देशों ({doc_title}) के अनुसार:"
            bullets = "\n".join([f"• {p}" for p in relevant_points[:4]])
            answer = f"{intro}\n\n{bullets}\n\nसंबंधित विभाग: {dept}."
        else:
            intro = f"According to official civic guidelines ({doc_title}):"
            bullets = "\n".join([f"• {p}" for p in relevant_points[:4]])
            answer = f"{intro}\n\n{bullets}\n\nResponsible Department: {dept}."

        return answer


class GeminiGenerationProvider(BaseGenerationProvider):
    """
    LLM generation provider utilizing Google Generative AI when configured.
    Enforces strict grounding: only answers from retrieved civic context.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.fallback_provider = LocalExtractiveGenerationProvider()

    def generate_answer(self, question: str, context_chunks: List[Dict[str, Any]], language: str = "en") -> str:
        lang = language.lower() if language in ("en", "ta", "hi") else "en"
        if not context_chunks:
            return FALLBACK_MESSAGES.get(lang, FALLBACK_MESSAGES["en"])

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")

            context_str = "\n\n".join([
                f"[Document: {c.get('title')} | Source: {c.get('source')} | Page: {c.get('page')}]\n{c.get('text')}"
                for c in context_chunks
            ])

            prompt = (
                f"You are the official AI Civic Guardian Assistant for municipal grievance redressal.\n"
                f"Strict Grounding Rules:\n"
                f"1. Answer the citizen's inquiry STRICTLY and ONLY using the official civic context provided below.\n"
                f"2. Do NOT invent government rules, procedures, contact numbers, fees, or timelines.\n"
                f"3. If the context does not contain enough information, state: '{FALLBACK_MESSAGES.get(lang)}'\n"
                f"4. Provide a clear, respectful citizen explanation in {language} (en=English, ta=Tamil, hi=Hindi).\n\n"
                f"OFFICIAL CIVIC CONTEXT:\n{context_str}\n\n"
                f"CITIZEN QUESTION:\n{question}\n\n"
                f"ANSWER:"
            )

            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
            return self.fallback_provider.generate_answer(question, context_chunks, language)
        except Exception as exc:
            logger.warning("Gemini generation failed, falling back to extractive: %s", exc)
            return self.fallback_provider.generate_answer(question, context_chunks, language)


def get_generation_provider() -> BaseGenerationProvider:
    """Returns configured generation provider."""
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if api_key and api_key.strip():
        logger.info("Using GeminiGenerationProvider with configured API key.")
        return GeminiGenerationProvider(api_key.strip())
    return LocalExtractiveGenerationProvider()

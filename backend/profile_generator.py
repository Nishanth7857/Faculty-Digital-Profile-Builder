"""
profile_generator.py
─────────────────────
Uses Granite to:
  1. Generate a clean standardized academic profile (full view).
  2. Write a short professional bio (2–3 sentences).

Both functions accept the structured `profile` dict produced by
granite_extractor.extract_profile_data() and return:
    {"text": str, "input_tokens": int, "output_tokens": int}
"""

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

LLM_MODEL_ID = "ibm/granite-3-8b-instruct"


# ─────────────────────────────────────────────────────────────────────────────
# Shared model builder (mirrors granite_extractor to avoid circular imports)
# ─────────────────────────────────────────────────────────────────────────────

def _build_model():
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

    api_key = os.environ.get("WATSONX_API_KEY")
    url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    project_id = os.environ.get("WATSONX_PROJECT_ID")

    if not api_key or not project_id:
        raise EnvironmentError(
            "❌ WATSONX_API_KEY or WATSONX_PROJECT_ID is missing. Check your .env file."
        )

    creds = Credentials(url=url, api_key=api_key)
    model = ModelInference(
        model_id=LLM_MODEL_ID,
        credentials=creds,
        project_id=project_id,
        params={
            GenParams.MAX_NEW_TOKENS: 800,
            GenParams.TEMPERATURE: 0.3,
        },
    )
    return model


def _generate(prompt: str) -> Dict[str, Any]:
    """Call Granite and return {text, input_tokens, output_tokens}."""
    model = _build_model()
    response = model.generate(prompt=prompt)
    result = response.get("results", [{}])[0]
    return {
        "text": result.get("generated_text", "").strip(),
        "input_tokens": result.get("input_token_count", 0),
        "output_tokens": result.get("generated_token_count", 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Full standardized profile
# ─────────────────────────────────────────────────────────────────────────────

def generate_full_profile(profile: dict) -> Dict[str, Any]:
    """
    Generate a clean, readable academic profile from structured data.

    Returns:
        {"text": str, "input_tokens": int, "output_tokens": int}
    """
    prompt = f"""<|system|>
You are an academic profile writer for NAAC/NBA accreditation reports.
Write a clean, professional, well-structured academic profile using the structured data below.
Use clear headings: Personal Details, Academic Qualifications, Publications, FDPs & Workshops,
Patents, Grants & Projects, Achievements & Awards.
Use bullet points under each section. Do not invent data; only use what is provided.
<|user|>
STRUCTURED DATA:
{json.dumps(profile, indent=2)}

Write the full academic profile now:
<|assistant|>"""

    return _generate(prompt)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Short professional bio
# ─────────────────────────────────────────────────────────────────────────────

def generate_bio(profile: dict) -> Dict[str, Any]:
    """
    Write a 2–3 sentence professional bio suitable for a website or report cover.

    Returns:
        {"text": str, "input_tokens": int, "output_tokens": int}
    """
    personal = profile.get("personal_details", {})
    qualifications = profile.get("qualifications", [])
    publications = profile.get("publications", [])

    prompt = f"""<|system|>
You are an academic bio writer. Write a 2–3 sentence professional bio for a faculty member.
Mention their name, designation, highest qualification, research interests (inferred from publications),
and a notable achievement if available.
<|user|>
Personal details: {json.dumps(personal)}
Qualifications: {json.dumps(qualifications)}
Publications (first 3): {json.dumps(publications[:3])}
Achievements: {json.dumps(profile.get("achievements_awards", [])[:2])}

Write the professional bio now:
<|assistant|>"""

    return _generate(prompt)

"""
granite_extractor.py
─────────────────────
Uses IBM Granite (ibm/granite-3-8b-instruct) through watsonx.ai to extract
structured academic data from faculty documents.

The extractor works in two modes:
  • Direct   – send raw text (small docs) directly to the model.
  • RAG      – retrieve relevant chunks first, then send to the model.

All calls return:
  {
    "data":         <extracted dict or string>,
    "input_tokens": <int>,
    "output_tokens": <int>
  }
"""

import json
import logging
import os
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Granite instruction-tuned model
LLM_MODEL_ID = "ibm/granite-3-8b-instruct"

# Max tokens to generate per extraction call
MAX_NEW_TOKENS = 1500

# ─────────────────────────────────────────────────────────────────────────────
# watsonx client helper
# ─────────────────────────────────────────────────────────────────────────────

def _build_model():
    """Instantiate the Granite LLM model object."""
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

    api_key = os.environ.get("WATSONX_API_KEY")
    url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    project_id = os.environ.get("WATSONX_PROJECT_ID")

    if not api_key:
        raise EnvironmentError(
            "❌ WATSONX_API_KEY is missing. Copy env.example → .env and fill in your credentials."
        )
    if not project_id:
        raise EnvironmentError(
            "❌ WATSONX_PROJECT_ID is missing. Copy env.example → .env and fill in your credentials."
        )

    creds = Credentials(url=url, api_key=api_key)

    model = ModelInference(
        model_id=LLM_MODEL_ID,
        credentials=creds,
        project_id=project_id,
        params={
            GenParams.MAX_NEW_TOKENS: MAX_NEW_TOKENS,
            GenParams.TEMPERATURE: 0.0,          # deterministic extraction
            GenParams.REPETITION_PENALTY: 1.05,
        },
    )
    return model


# ─────────────────────────────────────────────────────────────────────────────
# Internal: call Granite and parse the response
# ─────────────────────────────────────────────────────────────────────────────

def _call_granite(prompt: str) -> Dict[str, Any]:
    """
    Send `prompt` to Granite and return:
        {"raw_text": str, "input_tokens": int, "output_tokens": int}
    """
    model = _build_model()
    response = model.generate_text(prompt=prompt, guardrails=False)

    # The SDK returns either a plain string or a dict depending on the call type
    if isinstance(response, dict):
        raw_text = response.get("results", [{}])[0].get("generated_text", "")
        usage = response.get("results", [{}])[0].get("generated_token_count", 0)
        input_tok = response.get("results", [{}])[0].get("input_token_count", 0)
    else:
        # generate_text can return just the generated string
        raw_text = str(response)
        usage = 0
        input_tok = 0

    return {
        "raw_text": raw_text.strip(),
        "input_tokens": input_tok,
        "output_tokens": usage,
    }


def _call_granite_full(prompt: str) -> Dict[str, Any]:
    """
    Use generate() (not generate_text()) to get the full response object
    with token counts.
    """
    model = _build_model()
    response = model.generate(prompt=prompt)

    # response is a dict: {"results": [{"generated_text": ..., "generated_token_count": ..., "input_token_count": ...}]}
    result = response.get("results", [{}])[0]
    raw_text = result.get("generated_text", "").strip()
    output_tokens = result.get("generated_token_count", 0)
    input_tokens = result.get("input_token_count", 0)

    return {
        "raw_text": raw_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _parse_json_from_response(raw: str) -> Any:
    """
    Try to extract a JSON object/array from the model's raw output.
    Granite sometimes wraps JSON in markdown fences – strip those first.
    """
    # Remove markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find the first { ... } block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    # Return raw string if JSON parse fails
    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Extraction prompts
# ─────────────────────────────────────────────────────────────────────────────

_EXTRACTION_PROMPT_TEMPLATE = """<|system|>
You are an academic data extraction assistant. Extract the following categories from the document text below and return ONLY a valid JSON object. Do not add any explanation outside the JSON.

Categories to extract:
1. personal_details    – name, designation, department, institution, email, phone, date_of_birth
2. qualifications      – list of {{degree, subject, institution, year, grade}}
3. publications        – list of {{title, journal_or_conference, year, co_authors, doi}}
4. fdp_workshops       – list of {{title, organizer, duration, year, type (FDP/Workshop/Seminar)}}
5. patents             – list of {{title, patent_number, status, year, co_inventors}}
6. grants_projects     – list of {{title, funding_agency, amount, duration, role (PI/Co-PI)}}
7. achievements_awards – list of {{title, year, given_by}}

<|user|>
DOCUMENT TEXT:
{context}

Return the JSON now:
<|assistant|>"""


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def extract_profile_data(text: str, use_rag: bool = True) -> Dict[str, Any]:
    """
    Extract structured academic data from faculty document text.

    Args:
        text:    Full extracted text from the uploaded document(s).
        use_rag: If True, retrieve relevant chunks via RAG instead of
                 passing the raw text (better for long docs).

    Returns:
        {
            "profile": { ... structured fields ... },
            "input_tokens": int,
            "output_tokens": int
        }
    """
    if use_rag:
        from rag_pipeline import retrieve_context
        context = retrieve_context(text[:500], top_k=8)  # query = first 500 chars
        if not context:
            context = text[:3000]  # fallback: first 3000 chars
    else:
        context = text[:3000]

    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(context=context)
    result = _call_granite_full(prompt)

    parsed = _parse_json_from_response(result["raw_text"])

    # Ensure we always return a dict even if Granite returned raw text
    if not isinstance(parsed, dict):
        parsed = {"raw_extraction": parsed}

    return {
        "profile": parsed,
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
    }


def refine_extraction(profile: dict, user_corrections: dict) -> Dict[str, Any]:
    """
    Merge user corrections into the extracted profile using Granite
    so that the language stays consistent.

    Args:
        profile:           existing extracted profile dict
        user_corrections:  flat dict of field → new value from the edit page

    Returns:
        {"profile": updated_dict, "input_tokens": int, "output_tokens": int}
    """
    prompt = f"""<|system|>
You are a data merging assistant. Merge the user corrections into the existing academic profile.
Return ONLY a valid JSON object with the merged result. Keep all fields not mentioned in corrections unchanged.
<|user|>
EXISTING PROFILE:
{json.dumps(profile, indent=2)}

USER CORRECTIONS:
{json.dumps(user_corrections, indent=2)}

Return the merged JSON now:
<|assistant|>"""

    result = _call_granite_full(prompt)
    parsed = _parse_json_from_response(result["raw_text"])
    if not isinstance(parsed, dict):
        parsed = profile  # fall back to unchanged profile

    return {
        "profile": parsed,
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
    }

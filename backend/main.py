"""
main.py  –  Smart Faculty Profile Agent
─────────────────────────────────────────
FastAPI backend that ties all modules together.

Endpoints:
  POST   /api/upload          – Upload one or more documents; parse + ingest into RAG
  POST   /api/extract         – Run Granite extraction on the ingested documents
  GET    /api/profile         – Fetch the current structured profile JSON
  PUT    /api/profile/edit    – Save user corrections to the profile
  POST   /api/profile/merge   – Re-run Granite to merge corrections (Update mode)
  POST   /api/generate        – Generate full profile text + bio via Granite
  GET    /api/export/pdf      – Download the report as PDF
  GET    /api/export/docx     – Download the report as Word
  DELETE /api/reset           – Clear all stored data (start fresh)
  GET    /api/stats            – Token usage stats for the dashboard

Static frontend is served from ../frontend/
"""

import json
import logging
import os
import sys
from pathlib import Path

# ── Load .env BEFORE importing any module that reads env vars ──────────────
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Validate mandatory credentials at startup ──────────────────────────────
_MISSING = [v for v in ("WATSONX_API_KEY", "WATSONX_PROJECT_ID", "WATSONX_URL")
            if not os.environ.get(v)]
if _MISSING:
    print(
        f"\n❌ ERROR: The following required environment variables are not set: {_MISSING}\n"
        "   Copy env.example → .env and fill in your IBM watsonx.ai credentials.\n"
        "   The application cannot start without real credentials.\n",
        file=sys.stderr,
    )
    sys.exit(1)

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import aiofiles

# ── Local modules ─────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
import document_parser
import granite_extractor
import profile_generator
import rag_pipeline
import report_exporter

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("main")

# ── Paths ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
EXPORT_DIR = BASE_DIR / "exports"
STATE_FILE = UPLOAD_DIR / "profile_state.json"   # persists profile + stats between requests
UPLOAD_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

# ── FastAPI app ───────────────────────────────────────────────────────────
app = FastAPI(
    title="Smart Faculty Profile Agent",
    description="Automated faculty profile builder using IBM Granite on watsonx.ai",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
FRONTEND_DIR = BASE_DIR / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


# ─────────────────────────────────────────────────────────────────────────────
# State management helpers
# (we store everything in a JSON file so it survives server restarts)
# ─────────────────────────────────────────────────────────────────────────────

def _load_state() -> dict:
    """Load app state from disk, or return a blank state."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "raw_text": "",
        "profile": {},
        "full_profile_text": "",
        "bio": "",
        "uploaded_files": [],
        "token_usage": {        # cumulative token counters for the dashboard
            "extract_input": 0,
            "extract_output": 0,
            "generate_input": 0,
            "generate_output": 0,
            "refine_input": 0,
            "refine_output": 0,
            "embed_tokens": 0,
        },
    }


def _save_state(state: dict) -> None:
    """Persist app state to disk."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _add_tokens(state: dict, category: str, inp: int, out: int) -> None:
    """Accumulate token usage into state."""
    state["token_usage"][f"{category}_input"] = (
        state["token_usage"].get(f"{category}_input", 0) + inp
    )
    state["token_usage"][f"{category}_output"] = (
        state["token_usage"].get(f"{category}_output", 0) + out
    )


# ─────────────────────────────────────────────────────────────────────────────
# Frontend
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Serve the main HTML page."""
    index_file = FRONTEND_DIR / "templates" / "index.html"
    return FileResponse(str(index_file))


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Upload documents
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """
    Accept one or more files, parse them, and ingest their text into the
    RAG vector store.

    Returns a summary of what was uploaded and ingestion stats.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    state = _load_state()
    results = []

    for upload in files:
        filename = upload.filename or "unknown"
        logger.info("Received file: %s", filename)

        # Read bytes
        file_bytes = await upload.read()

        # Save raw file to disk (for audit / re-processing)
        save_path = UPLOAD_DIR / filename
        async with aiofiles.open(str(save_path), "wb") as f:
            await f.write(file_bytes)

        # Extract text
        try:
            text = document_parser.extract_text(file_bytes, filename)
        except ValueError as e:
            results.append({"file": filename, "status": "error", "detail": str(e)})
            continue

        if not text:
            results.append({"file": filename, "status": "error", "detail": "No text extracted."})
            continue

        # Append to accumulated raw text (for later extraction)
        state["raw_text"] += f"\n\n=== {filename} ===\n{text}"

        # Track uploaded files (Update mode: merge with existing)
        if filename not in state["uploaded_files"]:
            state["uploaded_files"].append(filename)

        # Ingest into RAG vector store
        ingest_stats = rag_pipeline.ingest_text(text)
        state["token_usage"]["embed_tokens"] = (
            state["token_usage"].get("embed_tokens", 0) + ingest_stats["embed_tokens"]
        )

        results.append({
            "file": filename,
            "status": "ok",
            "chars_extracted": len(text),
            "chunks_added": ingest_stats["chunks_added"],
        })

    _save_state(state)

    return {
        "message": f"Processed {len(results)} file(s).",
        "results": results,
        "total_files_ingested": len(state["uploaded_files"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Extract profile data via Granite
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/extract")
async def extract_profile():
    """
    Run Granite extraction on all uploaded document text.
    Uses RAG to retrieve relevant context before sending to the model.
    """
    state = _load_state()

    if not state["raw_text"]:
        raise HTTPException(status_code=400, detail="No documents uploaded yet. Please upload first.")

    logger.info("Running Granite extraction …")
    result = granite_extractor.extract_profile_data(state["raw_text"], use_rag=True)

    # If profile already exists (Update mode), merge new extraction with old
    if state["profile"]:
        logger.info("Existing profile found — merging with Granite …")
        merge_result = granite_extractor.refine_extraction(
            state["profile"], result["profile"]
        )
        final_profile = merge_result["profile"]
        _add_tokens(state, "refine", merge_result["input_tokens"], merge_result["output_tokens"])
    else:
        final_profile = result["profile"]

    state["profile"] = final_profile
    _add_tokens(state, "extract", result["input_tokens"], result["output_tokens"])
    _save_state(state)

    return {
        "profile": final_profile,
        "token_usage": {
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Fetch current profile
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/profile")
async def get_profile():
    """Return the current structured profile JSON."""
    state = _load_state()
    if not state["profile"]:
        raise HTTPException(status_code=404, detail="No profile extracted yet.")
    return {"profile": state["profile"]}


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Edit / correct the profile
# ─────────────────────────────────────────────────────────────────────────────

class EditRequest(BaseModel):
    corrections: Dict[str, Any]   # keys matching profile fields


@app.put("/api/profile/edit")
async def edit_profile(body: EditRequest):
    """
    Save user corrections directly into the stored profile without
    calling Granite (instant local update).
    """
    state = _load_state()
    if not state["profile"]:
        raise HTTPException(status_code=404, detail="No profile to edit.")

    # Deep-merge corrections into the existing profile
    def deep_merge(base: dict, updates: dict) -> dict:
        result = dict(base)
        for k, v in updates.items():
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    state["profile"] = deep_merge(state["profile"], body.corrections)
    _save_state(state)
    return {"message": "Profile updated.", "profile": state["profile"]}


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Granite-assisted merge (Update mode)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/profile/merge")
async def merge_profile():
    """
    Use Granite to intelligently merge user corrections with the existing
    profile (removes duplicates, fixes inconsistencies).
    """
    state = _load_state()
    if not state["profile"]:
        raise HTTPException(status_code=404, detail="No profile to merge.")

    result = granite_extractor.refine_extraction(state["profile"], {})
    state["profile"] = result["profile"]
    _add_tokens(state, "refine", result["input_tokens"], result["output_tokens"])
    _save_state(state)

    return {
        "message": "Profile refined by Granite.",
        "profile": state["profile"],
        "token_usage": {"input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"]},
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Generate full profile text + bio
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/generate")
async def generate_profile():
    """
    Use Granite to write the narrative profile text and professional bio
    from the structured profile data.
    """
    state = _load_state()
    if not state["profile"]:
        raise HTTPException(status_code=400, detail="No profile data. Run /api/extract first.")

    logger.info("Generating full profile text …")
    fp_result = profile_generator.generate_full_profile(state["profile"])
    bio_result = profile_generator.generate_bio(state["profile"])

    state["full_profile_text"] = fp_result["text"]
    state["bio"] = bio_result["text"]

    # Accumulate token usage
    _add_tokens(state, "generate",
                fp_result["input_tokens"] + bio_result["input_tokens"],
                fp_result["output_tokens"] + bio_result["output_tokens"])
    _save_state(state)

    return {
        "full_profile": fp_result["text"],
        "bio": bio_result["text"],
        "token_usage": {
            "input_tokens": fp_result["input_tokens"] + bio_result["input_tokens"],
            "output_tokens": fp_result["output_tokens"] + bio_result["output_tokens"],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7.  Export PDF
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/export/pdf")
async def export_pdf():
    """Generate and download the NAAC/NBA PDF report."""
    state = _load_state()
    if not state["profile"]:
        raise HTTPException(status_code=400, detail="No profile data. Run /api/extract first.")

    personal = state["profile"].get("personal_details", {})
    name_slug = (personal.get("name") or "faculty").replace(" ", "_")
    out_path = EXPORT_DIR / f"{name_slug}_profile.pdf"

    report_exporter.export_pdf(
        profile_data=state["profile"],
        full_profile=state.get("full_profile_text", ""),
        bio=state.get("bio", ""),
        output_path=out_path,
    )

    return FileResponse(
        str(out_path),
        media_type="application/pdf",
        filename=out_path.name,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8.  Export DOCX
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/export/docx")
async def export_docx():
    """Generate and download the NAAC/NBA Word report."""
    state = _load_state()
    if not state["profile"]:
        raise HTTPException(status_code=400, detail="No profile data. Run /api/extract first.")

    personal = state["profile"].get("personal_details", {})
    name_slug = (personal.get("name") or "faculty").replace(" ", "_")
    out_path = EXPORT_DIR / f"{name_slug}_profile.docx"

    report_exporter.export_docx(
        profile_data=state["profile"],
        full_profile=state.get("full_profile_text", ""),
        bio=state.get("bio", ""),
        output_path=out_path,
    )

    return FileResponse(
        str(out_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=out_path.name,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 9.  Token usage stats (dashboard)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    """Return cumulative token usage and file counts for the dashboard."""
    state = _load_state()
    usage = state.get("token_usage", {})
    total_input = sum(v for k, v in usage.items() if k.endswith("_input"))
    total_output = sum(v for k, v in usage.items() if k.endswith("_output"))
    return {
        "uploaded_files": state.get("uploaded_files", []),
        "file_count": len(state.get("uploaded_files", [])),
        "token_usage": usage,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "has_profile": bool(state.get("profile")),
        "has_generated_text": bool(state.get("full_profile_text")),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 10.  Reset (clear all data)
# ─────────────────────────────────────────────────────────────────────────────

@app.delete("/api/reset")
async def reset_all():
    """
    Delete all stored state, uploaded files, and vector store.
    Use with caution – this cannot be undone.
    """
    import shutil

    # Clear state file
    if STATE_FILE.exists():
        STATE_FILE.unlink()

    # Clear vector store
    vs_dir = UPLOAD_DIR / "vector_store"
    if vs_dir.exists():
        shutil.rmtree(vs_dir)

    # Clear exported files
    for f in EXPORT_DIR.glob("*"):
        f.unlink(missing_ok=True)

    return {"message": "All data cleared. Start fresh by uploading new documents."}


# ─────────────────────────────────────────────────────────────────────────────
# Run directly: python main.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

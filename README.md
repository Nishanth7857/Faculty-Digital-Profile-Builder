# Smart Faculty Profile Agent

> **Automated faculty profile builder for NAAC/NBA accreditation**  
> Powered by **IBM Granite** (`ibm/granite-3-8b-instruct`) and the **Granite Embedding** model (`ibm/granite-embedding-278m-multilingual`) on **IBM watsonx.ai**.

---

## What It Does

Faculty members must maintain academic profiles for NAAC/NBA accreditation, promotions, and research visibility. Compiling qualifications, publications, FDPs, patents, grants, and achievements manually from CVs, certificates, and spreadsheets is slow and error-prone.

This agent automates the entire pipeline:

1. **Upload** — CVs (PDF/DOCX), certificates (PDF/image), Excel/CSV files
2. **Parse** — extracts text using PyPDF2, python-docx, pandas, and OCR (pytesseract)
3. **RAG Ingest** — chunks text, embeds with Granite embeddings, stores in FAISS
4. **Extract** — Granite reads relevant chunks and outputs structured JSON (7 categories)
5. **Edit** — faculty review and correct the extracted data in-browser
6. **Generate** — Granite writes a full narrative profile + professional bio
7. **Export** — download NAAC/NBA-ready PDF or Word report

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| LLM | IBM Granite (`ibm/granite-3-8b-instruct`) via `ibm-watsonx-ai` SDK |
| Embeddings | IBM Granite Embedding (`ibm/granite-embedding-278m-multilingual`) |
| Vector DB | FAISS (local, no server needed) |
| Doc Parsing | PyPDF2, python-docx, pandas, pytesseract (OCR) |
| PDF Export | ReportLab |
| Word Export | python-docx |
| Frontend | HTML + CSS + vanilla JavaScript (no framework) |

---

## Prerequisites

- Python 3.10 or newer
- An **IBM Cloud account** (Lite tier is free) with:
  - **watsonx.ai Runtime** (Lite) service provisioned
  - A **watsonx.ai project** created
  - An **IBM Cloud API Key** generated
- (Optional) [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on `PATH` — only needed for scanned image documents

---

## Setup & Run

### 1. Clone / open the project

```bash
cd faculty_profile_builder
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your IBM watsonx.ai credentials

```bash
# Copy the example file
cp env.example .env
```

Open `.env` and fill in your real values:

```env
WATSONX_API_KEY=your_ibm_cloud_api_key_here
WATSONX_PROJECT_ID=your_watsonx_project_id_here
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

> **Where do I get these?**
> 1. `WATSONX_API_KEY` — IBM Cloud → Manage → Access (IAM) → API keys → Create
> 2. `WATSONX_PROJECT_ID` — [dataplatform.cloud.ibm.com](https://dataplatform.cloud.ibm.com) → Your project → Manage → General → Project ID
> 3. `WATSONX_URL` — depends on your region. Default: `https://us-south.ml.cloud.ibm.com`

### 5. (Optional) Generate the sample DOCX for testing

```bash
cd sample_data
python create_sample_docx.py
cd ..
```

### 6. Start the server

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Or simply:

```bash
python backend/main.py
```

### 7. Open the app

Navigate to: [http://localhost:8000](http://localhost:8000)

---

## Using the App — Step by Step

### Step 1 — Upload Documents
- Drag and drop or click to select files
- Supported: `.pdf`, `.docx`, `.xlsx`, `.csv`, `.png`, `.jpg`, `.jpeg`, `.tiff`
- Click **Upload & Ingest** — files are parsed and ingested into the RAG vector store

### Step 2 — Extract Profile
- Click **Run Granite Extraction**
- Granite reads relevant chunks via RAG and returns a structured JSON profile with:
  - Personal details, qualifications, publications, FDPs/workshops, patents, grants/projects, achievements/awards
- Token usage is shown immediately below the output

### Step 3 — Review & Edit
- All extracted fields appear as editable inputs
- List sections (publications, FDPs, etc.) are JSON editors
- Click **Save Corrections** to persist changes locally
- Click **Granite Merge & Deduplicate** to use Granite to clean up the profile

### Step 4 — Generate Profile Text
- Click **Generate with Granite**
- Granite writes a clean narrative profile and a 2–3 sentence professional bio

### Step 5 — Export Report
- **Download PDF** — NAAC/NBA formatted report with tables, sections, and headings
- **Download DOCX** — editable Word document

### Update Mode
Upload new documents at any time. The system automatically merges new content with the existing profile and removes duplicates.

---

## Project Structure

```
faculty_profile_builder/
│
├── backend/
│   ├── main.py                # FastAPI app — all API routes
│   ├── document_parser.py     # Extract text from PDF/DOCX/Excel/images
│   ├── rag_pipeline.py        # Chunk → Embed → FAISS → Retrieve
│   ├── granite_extractor.py   # Granite LLM extraction calls
│   ├── profile_generator.py   # Granite narrative profile + bio
│   └── report_exporter.py     # PDF (ReportLab) + DOCX export
│
├── frontend/
│   ├── templates/
│   │   └── index.html         # Single-page frontend
│   └── static/
│       ├── style.css          # Clean professional stylesheet
│       └── app.js             # All frontend logic (vanilla JS)
│
├── uploads/                   # Uploaded files + FAISS vector store
├── exports/                   # Generated PDF / DOCX reports
│
├── sample_data/
│   ├── sample_cv_dr_priya_nair.txt     # Plain-text sample CV
│   └── create_sample_docx.py           # Script to generate .docx version
│
├── app.json                   # App metadata
├── requirements.txt
├── env.example
└── README.md
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload documents; parse + ingest into RAG |
| `POST` | `/api/extract` | Granite extraction → structured profile JSON |
| `GET` | `/api/profile` | Fetch current profile |
| `PUT` | `/api/profile/edit` | Save user corrections |
| `POST` | `/api/profile/merge` | Granite-assisted merge + deduplication |
| `POST` | `/api/generate` | Generate narrative profile + bio |
| `GET` | `/api/export/pdf` | Download NAAC/NBA PDF |
| `GET` | `/api/export/docx` | Download Word (.docx) report |
| `GET` | `/api/stats` | Token usage stats for the dashboard |
| `DELETE` | `/api/reset` | Clear all stored data |

Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `❌ WATSONX_API_KEY is missing` | Copy `env.example → .env` and fill in real credentials. The app will not start with fake values. |
| `ModuleNotFoundError: pytesseract` | Install Tesseract OCR from [GitHub](https://github.com/tesseract-ocr/tesseract). It is only needed for scanned images. |
| `faiss-cpu` install fails on Windows | Try `pip install faiss-cpu --no-cache-dir` or upgrade pip first. |
| Upload returns "No text extracted" | The file may be a fully scanned image — make sure Tesseract is installed. |
| Extraction returns `{"raw_extraction": "..."}` | Granite returned non-JSON output; retry or simplify the document text. |

---

## For Students — Key Concepts

| File | What to learn |
|---|---|
| `document_parser.py` | How to extract text from different file formats in Python |
| `rag_pipeline.py` | What RAG is, what chunking + embedding means, how FAISS works |
| `granite_extractor.py` | How to call an LLM via the watsonx.ai SDK, prompt engineering |
| `profile_generator.py` | How to use an LLM to write structured text from data |
| `main.py` | How to build a REST API with FastAPI, file uploads, state management |
| `app.js` | How a browser frontend communicates with a backend using `fetch()` |

---

## License

MIT — free to use, modify, and distribute for educational purposes.

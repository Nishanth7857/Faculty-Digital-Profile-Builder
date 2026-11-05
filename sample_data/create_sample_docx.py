"""
create_sample_docx.py
─────────────────────
Run this script once to generate sample_cv_dr_priya_nair.docx in the sample_data folder.

Usage:
    python create_sample_docx.py
"""

from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

OUT_PATH = Path(__file__).parent / "sample_cv_dr_priya_nair.docx"
DARK_BLUE = RGBColor(0x1A, 0x3C, 0x5E)

def add_section_header(doc, title):
    h = doc.add_heading(title, level=2)
    h.runs[0].font.color.rgb = DARK_BLUE

def add_bullet(doc, text):
    doc.add_paragraph(text, style="List Bullet")

def create_docx():
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    # Title
    title = doc.add_heading("CURRICULUM VITAE", level=1)
    title.runs[0].font.color.rgb = DARK_BLUE
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Personal Details
    add_section_header(doc, "PERSONAL DETAILS")
    details = [
        ("Name",            "Dr. Priya Ramesh Nair"),
        ("Designation",     "Associate Professor"),
        ("Department",      "Computer Science and Engineering"),
        ("Institution",     "Vivekananda Institute of Technology, Pune"),
        ("Email",           "priya.nair@vitpune.ac.in"),
        ("Phone",           "+91-98765-43210"),
        ("Date of Birth",   "14-March-1982"),
    ]
    table = doc.add_table(rows=len(details), cols=2)
    table.style = "Table Grid"
    for i, (label, val) in enumerate(details):
        table.cell(i, 0).text = label
        table.cell(i, 1).text = val
        table.cell(i, 0).paragraphs[0].runs[0].bold = True

    doc.add_paragraph()

    # Qualifications
    add_section_header(doc, "ACADEMIC QUALIFICATIONS")
    quals = [
        ["Ph.D.", "Computer Science", "University of Pune", "2014", "Outstanding"],
        ["M.E.", "Computer Engineering", "Savitribai Phule Pune University", "2007", "First Class with Distinction"],
        ["B.E.", "Computer Science & Engg.", "Marathwada University", "2004", "First Class"],
    ]
    qt = doc.add_table(rows=1 + len(quals), cols=5)
    qt.style = "Table Grid"
    for i, h in enumerate(["Degree", "Subject", "Institution", "Year", "Grade"]):
        qt.cell(0, i).text = h
        qt.cell(0, i).paragraphs[0].runs[0].bold = True
    for r, q in enumerate(quals, 1):
        for c, val in enumerate(q):
            qt.cell(r, c).text = val

    doc.add_paragraph()

    # Publications
    add_section_header(doc, "PUBLICATIONS")
    pubs = [
        "Nair, P.R., Kulkarni, S. (2023). Deep Learning-based Diabetic Retinopathy Detection Using Ensemble CNNs. Journal of Biomedical Informatics, Vol. 140. DOI: 10.1016/j.jbi.2023.104118",
        "Nair, P.R., Deshmukh, A. (2022). Federated Learning for Privacy-Preserving Healthcare Data Analysis. IEEE TNNLS, Vol. 33. DOI: 10.1109/TNNLS.2022.3150012",
        "Nair, P.R., Patil, R., Joshi, M. (2021). An Efficient Graph Neural Network Architecture for Social Network Spam Detection. ESWA, Vol. 185.",
        "Nair, P.R., et al. (2023). RAG-enhanced Code Generation Using Instruction-Tuned LLMs. AAAI 2023.",
        "Nair, P.R., Deshmukh, A. (2020). Transfer Learning Approach for Low-Resource NLP in Marathi Language. ACL 2020.",
    ]
    for p in pubs:
        add_bullet(doc, p)

    # FDPs
    add_section_header(doc, "FDPs & WORKSHOPS")
    fdps = [
        "Advanced Deep Learning and its Applications — IIT Bombay (June 2023, 4 weeks)",
        "IBM watsonx.ai Essentials for Educators — IBM India (November 2022, 3 days)",
        "Research Methodology and Academic Writing — SPPU (July 2022, 1 week)",
        "Cloud Computing and DevOps Practices — AWS India & AICTE (March 2021, 5 days)",
        "Natural Language Processing Fundamentals — NIT Warangal (December 2020, 2 weeks)",
    ]
    for f in fdps:
        add_bullet(doc, f)

    # Patents
    add_section_header(doc, "PATENTS")
    patents = [
        "System and Method for Real-Time Sign Language Recognition Using Vision Transformers — IN202321045678A [Published, 2023]",
        "IoT-Based Smart Irrigation System with ML-Driven Crop Prediction — IN202221034512A [Granted, 2022]",
    ]
    for p in patents:
        add_bullet(doc, p)

    # Grants
    add_section_header(doc, "GRANTS & FUNDED PROJECTS")
    grants = [
        "Privacy-Preserving AI for Rural Healthcare in Maharashtra — DST, ₹28,50,000 (2022–2025) — PI",
        "Low-Resource Multilingual NLP for Indian Languages — MeitY, ₹15,00,000 (2020–2022) — Co-PI",
        "Smart Campus Automation Using Edge AI — VIT Internal Fund, ₹3,50,000 (2021–2022) — PI",
    ]
    for g in grants:
        add_bullet(doc, g)

    # Achievements
    add_section_header(doc, "ACHIEVEMENTS & AWARDS")
    awards = [
        "Best Research Paper Award — IEEE ICCCNT 2023 (IEEE India Council, 2023)",
        "Young Faculty Research Award — SPPU (2022)",
        "IBM Academic Award for AI Innovation in Education (IBM India, 2022)",
        "Best Teacher Award — VIT Pune (2019)",
        "Gold Medal — M.E. Computer Engineering, SPPU (2007)",
    ]
    for a in awards:
        add_bullet(doc, a)

    doc.save(str(OUT_PATH))
    print(f"✔ Created: {OUT_PATH}")

if __name__ == "__main__":
    create_docx()

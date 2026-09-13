P&C Workflow Console v5.5 — resilient AI Research document parser

Changes:
- PDF extraction no longer hard-depends on only `pypdf`.
- Parser fallback order: pypdf -> PyPDF2 -> pdfplumber -> PyMuPDF.
- A single unreadable document no longer crashes the entire AI Research page/job.
- Add `pypdf>=5.0` to the EXISTING repository requirements.txt for guaranteed PDF support.

Deploy:
1. Replace pc-power-admin.py with the included file.
2. Add `pypdf>=5.0` to your existing requirements.txt (do not replace your full requirements file).
3. Commit/push and allow Streamlit Cloud to rebuild.
4. Re-open AI Research and attach the PDFs again.

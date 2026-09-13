P&C Workflow Console v5.4 — AI Research Document Attachments

Replace only pc-power-admin.py.
No SQL changes are required if SQL 028 and SQL 037 are already installed.

Changes:
- AI Research > Launch research now accepts multiple PDF, DOCX, TXT and MD files.
- Extracted document text is read before web research and appended to the research brief.
- Documents are preserved in pc_documents when the document-ingestion tables are available.
- Ingestion job source_scope records document IDs, hashes, extracted character counts and truncation state.
- Maximum text sent per document: 60,000 chars; total document text per research job: 120,000 chars.
- Existing canonical-context, web research, staging and one-pass reconciliation behavior remains unchanged.

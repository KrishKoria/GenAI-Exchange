1.  Problem Statement
    Legal documents in India are dense, jargon-heavy, and rarely localized; consumers sign without comprehension, facing hidden risks (indemnity scope, auto-renewals, unlimited liability) and asymmetric bargaining power.
    Lack of accessible, confidential, jargon-free explanation tools for citizens (contrast enterprise-focused contract review platforms targeting lawyers, not lay users).
    Need for bilingual (English→Hindi initially) clarity; transparency mandates and consumer protection trends reinforce timeliness.

2.  Core Objectives (Hackathon MVP)
    O1: Convert a PDF (≤10 pages) into segmented clauses with plain-language summaries at Flesch-Kincaid Grade Level readability.
    O2: Classify each clause into a taxonomy and assign a risk attention level (low|moderate|attention).
    O3: Provide retrieval-grounded Q&A: user asks a question, system returns answer citing clause IDs (no hallucinated content).
    O4: Display readability reduction metric (baseline vs summarized) as measurable impact.
    O5: Enforce privacy: mask PII before persistence; disclaimers to avoid legal advice characterization.

---

3.  Differentiators
    D1: Citizen-first design (clarity + empowerment) versus corporate redlining tools.
    D2: Readability delta quantification (objective impact metric) displayed per clause and document.
    D3: Risk heatmap visualization + category taxonomy tuned for common consumer contracts.
    D4: Retrieval-grounded, citation-rich Q&A (transparent source referencing) to build trust.
    D5: Bilingual (English→Hindi stretch) accessibility and inclusive language simplification.
    D6: Privacy-first (PII masking + ephemeral original text option) to encourage adoption.
    D7: Extensible architecture for future locales, negotiation analytics, and aggregated risk pattern insights.

4.  Clause Taxonomy (Initial)
    Indemnity, Liability Limitation, Term & Termination, Auto-Renewal, Payment, Jurisdiction, Confidentiality, IP Ownership, Data Usage/Privacy, Dispute Resolution, Termination Notice, Assignment, Modification, Other.

---

5.  System Components Overview
    Frontend: React (upload UI, clause list heatmap, clause detail panel, Q&A drawer, metrics tiles).
    API Layer: Cloud Run container (FastAPI or Express) orchestrating extraction, summarization, classification, retrieval, Q&A, metrics.
    Ingestion: Document AI (layout & OCR) or fallback PDF text extractor + heading heuristics.
    Processing: Batch Gemini calls with structured JSON schema for clause summaries + risk.
    Retrieval: Vertex embeddings (local cosine similarity).
    Storage: Firestore (documents, clauses, sessions) + optional Cloud Storage for raw doc (masked or ephemeral).
    Privacy/Safety: DLP API for PII masking; disclaimers; retrieval-only Q&A prompt constraints.

---

6.  High-Level Architecture (ASCII Sketch)
    Client -> /ingest -> Cloud Run -> Document AI -> DLP Mask -> Clause Split -> Batch Summarize (Gemini) -> Store (Firestore)
    Client -> /clauses -> Firestore
    Client -> /qa -> Embedding(question) -> Similarity over clause vectors -> Grounded Prompt (Gemini) -> Answer + citations

---

7. Data Flow Steps (Detailed)
   Step 1 Upload PDF -> Validate size/pages -> Temporary storage.
   Step 2 Extract text + layout -> Build ordered clause candidates (heading detection + paragraph grouping).
   Step 3 Compute baseline readability metrics (flesch, grade) for each clause + full document.
   Step 4 Batch clauses (up to N) into a summarization + classification prompt; get JSON array.
   Step 5 Apply keyword risk heuristic; reconcile with model risk output; mark conflicts.
   Step 6 Mask PII tokens (names, emails, phone) before persistence.
   Step 7 Store document metadata + clauses in Firestore; generate embeddings for each summarized clause.
   Step 8 On Q&A: embed question; retrieve top K clauses; feed only retrieved text into answer prompt; return citations.
   Step 9 Emit events (upload, clause_view, qa) to Pub/Sub; stream to BigQuery.

---

8. Core Endpoints (MVP)
   POST /ingest: multipart file -> returns docId + status.
   GET /clauses?docId=... -> list of clause summaries (id, category, risk, readability delta).
   GET /clause/{clauseId} -> full clause detail (original, summary, risk metadata, readability metrics).
   POST /qa: { docId, question } -> { answer, used_clause_ids, confidence }.
   GET /metrics/summary -> aggregated KPIs for dashboard.

---

9. Firestore Schema (Simplified)
   documents: { docId, createdAt, status, pageCount, baselineReadability: { flesch, grade }, masked:boolean }
   documents/{docId}/clauses: { clauseId, order, textOriginal (masked or ephemeral), textSummary, category, riskLevel, needsReview:boolean, readability: { origGrade, sumGrade }, embedding:[float]? }
   sessions: { sessionId, createdAt, locale }
   (Optional) events collection if not using only Pub/Sub -> BigQuery.

---

10. BigQuery Events Table (event_log)
    Columns: event_ts TIMESTAMP, session_id STRING, doc_id STRING, event_type STRING, clause_id STRING, latency_ms INT64, model_version STRING, tokens_prompt INT64, tokens_output INT64.

---

11. Prompt Templates (Summaries)
    System: "You are a legal clarity assistant. Rephrase clauses plainly (Grade ~8), no new facts, output strict JSON."
    User (batched): "CLAUSES:\n===\n{id: 'c1', text: '...'}\n===\n{id: 'c2', text:'...'} ...\nReturn JSON array: [{id, summary, clause_category, risk_level (low|moderate|attention), negotiation_tip|null}]"
    Validation: Reject output if non-JSON or missing required keys.

---

12. Prompt Template (Q&A Grounded)
    System: "Answer ONLY from provided clauses; if absent say 'Not clearly specified in this document.' Return JSON {answer, used_clause_ids, confidence (0-1)}."
    User: "CLAUSES: [...] QUESTION: <user_question>"

---

13. Risk Heuristic Overlay
    Keywords -> Elevate severity: indemnify, hold harmless, unlimited, perpetual, automatic renewal, exclusive jurisdiction, waive, liquidated damages, penalty, assignment without consent.
    If model risk_level == low but keyword hits -> mark needsReview=true and escalate to moderate (not attention unless multiple critical hits).

---

14. Readability Metric Implementation
    For each clause: compute total sentences, words, syllable estimate; calculate Flesch Reading Ease and map to grade; same for summary; store delta = origGrade - sumGrade.
    Document-level average: weighted by clause word counts.

---

15. Privacy & Safety Controls
    PII detection: DLP API OR regex fallback (emails, phone numbers, capitalized name pairs) -> replace with tokens (e.g., [NAME_1]).
    Storage policy: Option to not store full original clause text (keep hashed signature + masked variant only) for added privacy.
    Disclaimers: Banner + per answer footer: "Educational summary – not legal advice.".
    Logging: Exclude raw clause text from analytics events.

---

16. Stretch Features (Post-MVP)
    Version diff comparison: risk profile delta visualization.
    Assumptions panel: Model lists interpretation assumptions; user can correct (feedback loop log).
    Negotiation rephrase generator with disclaimers.
    Aggregated anonymized risk pattern insights (top recurring high-risk phrases).
    Additional languages beyond Hindi (e.g., Tamil, Marathi).
    Matching Engine upgrade for scalable semantic search across many documents.

---

17. Risks & Mitigations (Condensed Table)
    Segmentation errors -> Fallback heuristics + manual grouping UI (future).
    Hallucination -> Retrieval-only Q&A; JSON schema validation for summaries.
    Cost spikes -> Page cap + batch summarization + optional skip negotiation tips if token budget exceeded.
    PII leakage -> Mask before persistence; disallow raw text in analytics.
    Token overflow (long clauses) -> Chunk long clauses > X chars into subclauses.

---

18. Deployment Plan
    Build container (Docker) -> Deploy Cloud Run (region: asia-south1 or nearby) -> Set min instances = 0 or 1 (trade latency vs cost).
    Enable required APIs: aiplatform, documentai, dlp, firestore, pubsub, bigquery, run, storage.
    Service account with least privilege (separate roles: DocumentProcessor, VertexAIUser, FirestoreUser, Pub/Sub Publisher, BigQuery DataEditor).
    Environment variables: PROJECT_ID, LOCATION, GEMINI_MODEL_NAME, DOC_AI_PROCESSOR_ID, DLP_ENABLED=true/false, PAGE_LIMIT.

---

19. Security Considerations
    Do not log raw clause content; log clauseId references only.
    Signed URLs for doc uploads if using Cloud Storage; otherwise direct multipart memory cap.
    Rate limiting (basic) per session ID to deter abuse.
    Remove any temporary plaintext artifacts after processing.

---

20. Ethical Guardrails
    Avoid normative advice (“You should sign”); only explain meaning and potential implications generically.
    Bias mitigation: Ensure Hindi translation preserves neutrality; no value-laden adjectives added.
    Transparency: Provide “How this summary was generated” link (architectural overview simplified) in UI.

---

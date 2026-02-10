# RefWeaver TODO

**Project:** Scientific manuscript reference analysis tool  
**Last Updated:** 2026-02-10

---

## ✅ Completed

### Core Library Infrastructure
- [x] Project structure with `src/refweaver/` layout
- [x] Pydantic models: `Article`, `Sentence`, `SentenceEvaluation`, `FinalVerdict`
- [x] BibTeX export functionality
- [x] Text utilities: sentence/paragraph splitting, keyword extraction

### Search Adapters
- [x] **Semantic Scholar** - Full API integration with timeout support
- [x] **OpenAlex** - Full API integration with timeout support
- [x] **Google Scholar** (via scholarly) - With proxy support
- [x] **Perplexity Sonar** - Via OpenRouter, semantic/claim-based search
- [x] UnifiedSearch - Combines multiple keyword-based sources
- [x] Configurable timeouts (15s default, 30s for Perplexity)

### Article Enrichment
- [x] CrossRef enrichment via DOI
- [x] Title-based OpenAlex search for DOI discovery
- [x] PDF DOI extraction with validation
- [x] LLM-based webpage extraction (abstract + DOI)
- [x] Generated summaries when no explicit abstract exists
- [x] Selenium-based HTML fetching (handles JavaScript sites)
- [x] Full `enrich()` orchestrator with strategy selection

### Analysis Pipeline
- [x] Three-stage evaluation architecture:
  1. Relevance scoring (0-1) with keyword matching
  2. Stance evaluation (SUPPORTS/CONTRADICTS/PARTIALLY_SUPPORTS)
  3. Final verdict synthesis
- [x] `SentenceAnalyzer` class
- [x] `SentenceEvaluation` with full `Article` reference
- [x] Source identifier mapping for primary sources

### Developer Experience
- [x] Timing utilities (`@timed`, `@timed_info`, `Timer` context manager)
- [x] Table formatting utilities (tabulate/pandas support)
- [x] Type hints throughout (mypy clean)
- [x] Ruff linting with import sorting
- [x] Loguru logging with structured output

---

## 🚧 In Progress / Needs Testing

### Analysis Pipeline
- [ ] End-to-end testing with real sentences
- [ ] Evaluation quality assessment
- [ ] Relevance threshold tuning (currently 0.5)
- [ ] Performance optimization for large article sets

### Enrichment
- [ ] CrossRef validation for LLM-extracted DOIs
- [ ] Abstract quality comparison (explicit vs generated)
- [ ] PDF extraction fallback when Selenium fails

---

## 📋 Planned: Library Completion

### Core Functionality
- [ ] Batch processing for multiple sentences
- [ ] Result caching (disk-based for expensive operations)
- [ ] Progress callbacks for long-running operations
- [ ] Export formats: JSON, CSV, markdown
- [ ] Configuration file support (YAML/JSON)

### Search Enhancements
- [ ] Retry logic with exponential backoff
- [ ] Circuit breaker for failing sources
- [ ] Parallel search across sources
- [ ] Search result ranking/ordering improvements

### Testing & Quality
- [ ] Unit tests for all adapters
- [ ] Integration tests with real APIs
- [ ] Test fixtures with mock responses
- [ ] Code coverage reporting
- [ ] Performance benchmarks

### Documentation
- [ ] API reference (docstrings → Markdown)
- [ ] Usage examples and tutorials
- [ ] Architecture decision records (ADRs)
- [ ] Troubleshooting guide

---

## 🌐 Planned: REST API

### API Design
- [ ] FastAPI-based REST server
- [ ] Async endpoints for long-running operations
- [ ] WebSocket support for streaming results
- [ ] OpenAPI/Swagger documentation

### Endpoints
```
POST /analyze/sentence          - Analyze single sentence
POST /analyze/paragraph         - Analyze full paragraph
POST /analyze/document          - Analyze full document
GET  /search                    - Search articles
POST /enrich                    - Enrich article metadata
GET  /status/{job_id}           - Check async job status
GET  /results/{job_id}          - Get async results
```

### Features
- [ ] Job queue with Redis/Celery
- [ ] Authentication (API keys)
- [ ] Rate limiting
- [ ] Request/response validation
- [ ] Error handling with structured responses
- [ ] Webhook callbacks for async completion

---

## 🐳 Planned: Docker Deployment

### Container Setup
- [ ] Multi-stage Dockerfile
- [ ] Docker Compose for local development
- [ ] Docker Compose for production (API + Redis)
- [ ] Health checks
- [ ] Non-root user execution

### Services
- [ ] Main API container
- [ ] Redis for job queue
- [ ] Optional: PostgreSQL for result storage
- [ ] Optional: Elasticsearch for article indexing

### Configuration
- [ ] Environment variable management
- [ ] Secrets handling (Docker secrets or env files)
- [ ] Volume mounts for persistent data
- [ ] Network configuration

### Deployment Targets
- [ ] Local development
- [ ] VPS/self-hosted
- [ ] Cloud run (AWS/GCP/Azure)
- [ ] Kubernetes manifests

---

## 🎨 Planned: Web UI

### Frontend (separate from this repo)
- [ ] React/Vue/Svelte frontend
- [ ] Upload document (PDF, DOCX, TXT)
- [ ] Sentence highlighting with status
- [ ] Article cards with metadata
- [ ] Citation preview
- [ ] Export to BibTeX/RIS/etc
- [ ] Real-time analysis progress

### Features
- [ ] User accounts and history
- [ ] Saved article collections
- [ ] Collaborative editing
- [ ] Citation style selection (APA, MLA, Chicago)

---

## 🔧 Technical Debt / Refactoring

- [ ] Consider Pydantic v2 migration implications
- [ ] Async support throughout (adapters, enricher)
- [ ] Database abstraction for result storage
- [ ] Plugin system for custom adapters
- [ ] Structured logging with correlation IDs

---

## 📚 Future Ideas

- [ ] PDF manuscript upload and automatic sentence extraction
- [ ] LaTeX integration (direct citation insertion)
- [ ] Zotero/Mendeley integration
- [ ] Citation graph visualization
- [ ] Similar paper recommendations
- [ ] Claim verification across multiple sources
- [ ] Confidence calibration for verdicts
- [ ] Fine-tuned LLM for domain-specific evaluation

---

## 📝 Notes

- **Current focus:** Library completion and testing
- **Next milestone:** REST API with basic endpoints
- **Blockers:** None currently
- **Dependencies:** All core dependencies installed

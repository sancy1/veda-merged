# VEDA — Vendor Economic Dependency Assessment

VEDA is a provenance-aware evidence pipeline for vendor financial and
dependency analysis.

Given a vendor name and a fiscal period, VEDA resolves the entity,
retrieves public evidence, normalizes source records into canonical
evidence, extracts typed claims, validates every claim against the
evidence it references, detects comparable conflicts, reports missing
evidence, and produces a single reproducible assessment packet — or
an explicit statement that the evidence is insufficient.

Every material claim in a packet references the exact evidence it was
derived from. When the evidence cannot support a defensible conclusion,
the system abstains with a specific reason instead of guessing.

VEDA is a decision-support system. It does not make autonomous
accounting, procurement, supplier-risk, or compliance decisions. It
supports human review.

---

## Current status

The merged prototype is complete through Phase 8:

```text
Phase 1  Project scaffolding                 complete
Phase 2  Shared contract                     complete
Phase 3  Entity resolution                   complete
Phase 4  Providers                           complete
Phase 5  Normalization                       complete
Phase 6  Pipeline                            complete
Phase 7  Interfaces + extraction seam        complete
Phase 8  Adapters (graph + benchmark shapes) complete
Phase 9  Provenance graph                    next
Phase 10 Benchmark                           after Phase 9
```

- **952 tests pass.** Zero failures.
- The CLI, the FastAPI server, and the dashboard all work.
- Live SEC retrieval and live USAspending retrieval are verified
  against real endpoints.
- The provenance graph and the benchmark are the sprint's two
  remaining deliverables. They are not implemented yet.

---

## What the system produces

Every run returns one canonical `Assessment` object. It contains:

- the resolved vendor (or an explicit `AMBIGUOUS` / `NOT_FOUND` result),
- the reporting period the packet covers,
- zero or more typed claims, each with at least one evidence reference,
- the evidence ledger the claims were derived from,
- any comparable conflicts that were detected,
- any missing evidence records with reasons,
- the assessment status, drawn from a fixed five-state vocabulary,
- run metadata: schema version, pipeline version, provider modes,
  timestamps, and the SEC User-Agent used for live requests.

### The five assessment states

```text
SUPPORTED                   every claim is backed by evidence,
                            no comparable conflict was detected

SUPPORTED_WITH_LIMITATIONS  supported, but a claim is inferred, or a
                            parent-level disclosure applies

CONFLICTING_EVIDENCE        two comparable claims disagree; both are
                            preserved and human review is required

INSUFFICIENT_EVIDENCE       the system cannot produce a defensible
                            answer and names what is missing

REQUIRES_HUMAN_REVIEW       the packet is materially uncertain for a
                            reason other than a conflict
```

The status is always explicit. It is never defaulted, never inferred
from prose, and never blank.

### Non-comparable measures

A numerical difference between recognized revenue and a procurement
obligation is not a conflict. They measure different things. The
pipeline preserves both with their meaning, category, and period, and
never labels their difference as a contradiction.

---

## Two modes

VEDA runs in one of two modes:

| Mode | Source of data | Network | Deterministic | Use |
|------|---------------|---------|---------------|-----|
| `fixture` | Frozen dictionary in `src/veda/providers/fixtures.py` | No | Yes | Tests, demos, benchmark fixtures |
| `live` | Real HTTP requests to SEC and USAspending | Yes | No | Production, current data |

Every evidence record carries an `is_fixture` boolean that says which
mode produced it. The dashboard renders a FIXTURE or LIVE badge on each
evidence card. The `run_metadata.provider_modes` map records the mode of
each provider individually.

The two modes never mix silently. A packet produced in a given run is
either entirely fixture-sourced, or has a mixed mode that the run
metadata records explicitly.

---

## How to run

### 1. Install

Requires Python 3.11 or newer. From PowerShell:

```powershell
# Create and activate a virtual environment
python -m venv .venv
& ".\.venv\Scripts\Activate.ps1"

# Install the package with test dependencies
python -m pip install -e ".[test]"
```

### 2. Configure

```powershell
copy .env.example .env
```

Then edit `.env` and set a real SEC User-Agent:

```text
SEC_API_USER_AGENT=Your Name your.email@example.com
```

SEC requires a descriptive User-Agent on every request. Requests
without one are rejected. The `.env` file is excluded by `.gitignore`;
the template `.env.example` is committed.

### 3. Run

Three ways. Any of them works.

#### Option A — one command, browser opens automatically

```powershell
python scripts\run_dashboard.py
```

Starts the FastAPI server on `http://127.0.0.1:8000/` and opens the
dashboard in the default browser. Press Ctrl+C to stop.

#### Option B — double-click the launcher

A file named `VEDA Dashboard.bat` on the Desktop starts the server
and opens the browser. Close the terminal window (or press Ctrl+C)
when done.

#### Option C — CLI only, no browser

```powershell
veda "Lockheed Martin Corp" 2024
```

Or, during development:

```powershell
python -m veda.interfaces.cli "Lockheed Martin Corp" 2024
```

The CLI prints a JSON packet and a human-readable summary from the
same run. Use `--output path.json` to also save the packet.

### 4. Verify

```powershell
python -m pytest tests/
```

Expected: **952 passed, 2 warnings**.

The two warnings are deprecation notices from Starlette and anyio.
They are not related to this project and do not indicate a problem.

---

## CLI usage

```text
python -m veda.interfaces.cli VENDOR YEAR [OPTIONS]

Options:
  --resolver    fixture | live       default: fixture
  --providers   fixture | live       default: fixture
  --extractor   rule_based           composite reserved for later
  --format      json | human | both  default: both
  --output      PATH                 optional file path
  --user-agent  STRING               SEC User-Agent
```

### CLI exit codes

```text
0   a packet was produced and validated (any assessment status)
2   configuration error
3   bundle build error
4   unexpected pipeline error
```

An abstention exits 0. It is a valid answer, not a failure.

### Example runs

Fixture mode, JSON output:

```powershell
python -m veda.interfaces.cli "Lockheed Martin Corp" 2024 --format json
```

Live mode with a filing passage:

```powershell
python -m veda.interfaces.cli "Lockheed Martin Corp" 2024 `
    --resolver live --providers live `
    --user-agent "Your Name your.email@example.com"
```

Save the packet to disk:

```powershell
python -m veda.interfaces.cli "Lockheed Martin Corp" 2024 `
    --format json --output lockheed_2024.json
```

---

## HTTP API

Start the server:

```powershell
uvicorn veda.interfaces.api:app --reload
```

### Endpoints

| Route | Method | Purpose |
|-------|--------|---------|
| `/health` | GET | Liveness check |
| `/assess` | POST | Run the pipeline, return the packet |
| `/` | GET | Serve the dashboard |
| `/static/*` | GET | Static assets |
| `/openapi.json` | GET | Automatic OpenAPI schema |
| `/docs` | GET | Interactive API documentation |

### Example request

```powershell
curl -X POST http://127.0.0.1:8000/assess `
    -H "Content-Type: application/json" `
    -d '{"company_name":"Lockheed Martin Corp","fiscal_year":2024}'
```

Every assessment outcome returns HTTP 200. The packet carries the
status. Configuration errors return HTTP 400. Request validation
errors return HTTP 422.

---

## The pipeline

```text
vendor name + fiscal period
   |
   v
entity resolution              veda.entity.resolver
   |
   v
evidence retrieval             veda.providers
   |  (SEC Company Facts, SEC Filings, USAspending, Annual Reports)
   v
normalization                  veda.normalization
   |
   v
claim extraction               veda.pipeline.claim_extraction
   |
   v
validation                     veda.shared.validation
   |  (no evidence, no claim)
   v
conflict detection             veda.pipeline.conflict_detector
   |
   v
missing-evidence computation   veda.pipeline.abstention
   |
   v
assessment status              veda.pipeline.assessment
   |
   v
packet assembly                veda.pipeline.packet
   |
   v
Assessment object              veda.shared.models
```

The orchestrator (`veda.pipeline.orchestrator.run_assessment`) is the
single entry point. Every interface — CLI, HTTP API, dashboard, tests,
and the future graph and benchmark adapters — calls this function.

---

## Package layout

```text
src/veda/
├── shared/
│   ├── enums.py          12 enums: SourceType, EvidenceCategory,
│   │                     ClaimStatus, AssessmentStatus, and others
│   ├── periods.py        Period, RequestedPeriod, the 350-380 day
│   │                     full-year rule, period matching
│   ├── ids.py            content-addressed ID generation and parsing
│   ├── models.py         10 Pydantic models: AssessmentRequest,
│   │                     ResolvedEntity, SourceDocument, Evidence,
│   │                     Claim, Conflict, MissingEvidence,
│   │                     RunMetadata, Assessment, EvidenceLocation
│   └── validation.py     11 cross-record rules
│
├── entity/
│   ├── resolver.py       EntityResolver + Fixture and Live sources
│   └── reporting_boundary.py  parent / subsidiary classification
│
├── providers/
│   ├── base.py           EvidenceProvider ABC
│   ├── results.py        ProviderRequest, ProviderResult
│   ├── fixtures.py       Frozen demo data
│   ├── sec_company_facts.py   live + fixture
│   ├── sec_filings.py         live + fixture
│   ├── usaspending.py         live + fixture
│   └── annual_reports.py      fixture only
│
├── normalization/
│   ├── sec.py            XBRL normalization with fy/fp hardening
│   ├── filings.py        filing passage normalization
│   ├── usaspending.py    procurement obligation normalization
│   ├── annual_reports.py annual report passage normalization
│   ├── evidence_ids.py   delegation to shared.ids
│   └── helpers.py        shared validation + conversion
│
├── pipeline/
│   ├── orchestrator.py   run_assessment() — the single entry point
│   ├── packet.py         deterministic packet assembly
│   ├── assessment.py     5-state assessment rules engine
│   ├── claim_extraction.py  RuleBasedClaimExtractor + extract_claims()
│   ├── extraction_protocol.py  ClaimExtractor ABC
│   ├── composite_extraction.py CompositeClaimExtractor
│   ├── llm_extraction.py  LLMClaimExtractor (disabled contract stub)
│   ├── claim_typing.py   EvidenceCategory -> claim_type mapping
│   ├── conflict_detector.py  comparability-aware conflict detection
│   └── abstention.py     missing-evidence computation
│
├── interfaces/
│   ├── config.py         InterfaceConfig
│   ├── errors.py         InterfaceError hierarchy
│   ├── bundle_builder.py constructs providers from config
│   ├── cli.py            Typer + rich CLI
│   ├── api.py            FastAPI surface
│   └── static/
│       └── dashboard.html  the visual dashboard
│
├── adapters/
│   ├── graph_adapter.py     Assessment -> graph-shaped dict
│   └── benchmark_adapter.py Assessment -> benchmark-shaped dict
│
├── provenance/          reserved for Phase 9 (empty)
└── benchmark/           reserved for Phase 10 (empty)
```

### Supporting directories

```text
scripts/
├── run_dashboard.py       one-command server + browser launcher
├── live_verify.py         live SEC + USAspending verification
├── inspect_module.py      AST-based module inspector
├── diagnose_period.py     period resolution diagnostic
└── show_sec_evidence.py   inspect SEC evidence fields

tests/
├── shared/                245 tests (contract)
├── entity/                60 tests
├── providers/             120 tests
├── normalization/         123 tests
├── pipeline/              172 tests
├── adapters/              37 tests
├── interfaces/            82 tests
├── integration/           21 tests
├── smoke/                 45 tests
└── test_project_scaffolding.py  37 tests

fixtures/                  frozen source data
examples/                  example JSON packets
docs/                      documentation
archive/
├── personal-prototype/    the SEC-only CLI prototype
└── veda-original/         the multi-source VEDA prototype
```

---

## What works

- **Entity resolution** — exact-match by SEC name or ticker. Abstains
  on ambiguity. Live and fixture.
- **Multi-source retrieval** — SEC Company Facts, SEC Filings,
  USAspending, Annual Reports.
- **fy/fp hardening** — the year is derived from the actual period
  end date, never from SEC's `fy` label. Quarterly spans mislabeled
  `fp="FY"` are excluded by period length.
- **Duplicate-filing tiebreak** — when the same value appears in
  multiple filings, unchanged values use the earliest filing;
  corrected values use the newest.
- **Claim validation** — every SUPPORTED claim must reference at least
  one evidence ID. Unbacked claims are demoted.
- **Comparability-aware conflict detection** — recognized revenue and
  procurement obligations are never compared.
- **Five-state assessment** — first-match-wins rules, deterministic.
- **Two-reason abstention** — unresolved entity and missing period are
  distinguished.
- **CLI, API, dashboard** — three interfaces over one orchestrator.
- **Fixture/live parity** — the same pipeline, two retrieval modes,
  the same packet shape.
- **Deterministic IDs** — content-addressed evidence and claim IDs.
- **Graph and benchmark adapters** — the packet is already convertible
  into graph-shaped and benchmark-shaped records.

---

## What does not work yet

The sprint asks for two further deliverables:

- **Provenance graph** (Phase 9). The adapter exists and produces a
  node/edge list. The graph structure itself — an in-memory
  traversable object — is not built. There is no traversal API, no
  graph validation, and no graph serialization.

- **Benchmark** (Phase 10). The adapter exists and produces a
  benchmark-shaped record. The benchmark itself — a frozen corpus,
  questions, ground truth, hard negatives, and a scoring harness —
  is not built.

A future LLM narrative-extraction adapter is reserved for a later
phase. The seam exists (`veda.pipeline.llm_extraction`). The live
model implementation does not.

---

## Known limitations

- **Entity resolution is exact-match.** SEC canonical names differ
  from common names. `Duke Energy` does not resolve because SEC uses
  `Duke Energy CORP`. A future frontend can pre-normalize names.
- **No character-offset spans on SEC filing passages.** The filing
  provider returns the raw filing index page. Span extraction
  requires HTML parsing or the LLM narrative path.
- **USAspending evidence has no SourceDocument.** It is a record with
  an award ID and a native reference, not a fetched document.
- **The annual report provider is fixture only.** For public companies,
  the SEC filing is the annual report content.
- **Fixture mode is not a substitute for live verification.** Fixture
  data is frozen; live data changes.

---

## Source prototypes

This repository merges two earlier prototypes. Both are preserved
under `archive/` for reference and rollback.

### `archive/personal-prototype/`

An SEC-only CLI prototype with:

- live SEC ticker resolution
- SEC Company Facts retrieval
- real period filtering (fy/fp hardening)
- duplicate-filing tiebreak
- direct filing index URL construction
- two-reason abstention
- Typer + rich CLI

### `archive/veda-original/`

A broader fixture-backed prototype with:

- a provider abstraction
- evidence normalization and content-addressed IDs
- conflict detection
- missing-evidence reporting
- subsidiary handling
- five-state assessment
- FastAPI + dashboard

Every file in `src/veda/` records in its header whether its content
was ported from one prototype, ported from the other, merged from both,
or authored for the merged system.

---

## Documentation standard

Every source file in `src/veda/` starts with a header that names:

- the file path
- the file's title
- the architectural layer
- the file's purpose
- its source (ported / merged / authored)
- any design notes and known limitations

Every class and every public function has a docstring covering inputs,
outputs, error behavior, and its place in the flow. Inline comments
explain the lines that encode a decision.

---

## Next step

Phase 9 — the provenance graph. The first file will be:

```text
src/veda/provenance/__init__.py
```

followed by `enums.py`, `graph_models.py`, `graph_builder.py`,
`traversal.py`, `validation.py`, and `serializers.py`.

The graph is built from the validated `Assessment` packet. It is a
traversable in-memory structure serialized to JSON. No database. No
graph visualization. No UI.

---

## License

Proprietary. Internal to ArcellAI.

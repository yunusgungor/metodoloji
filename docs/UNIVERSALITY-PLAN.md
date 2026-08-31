# Universality Plan — Open-Source English Migration

> **Goal:** Make every user-facing string, instruction, template, and
> documentation artifact fully English so the project is ready for
> open-source release. Internal variable names, comments, and non-user-facing
> code stay as-is unless they contain Turkish prose.

---

## Scope Summary

| Area | Files | Turkish Content |
|------|-------|-----------------|
| **Templates** | `templates/*.md` (8 files) | Full Turkish field labels, section headers |
| **Commands** | `commands/*.md` (4 files) | Full Turkish instructions |
| **Custom TOML** | `custom/*.toml` (102 files with Turkish) | principles, activation_steps_append, comments |
| **Hook engine** | `hooks/engine/modules/*.py` (5 files) | Deny reasons, code_docs templates, status words |
| **Skill SKILL.md** | `skills/bmad-*/SKILL.md` (2 with Turkish) | Field label requirements |
| **Benchmark rollouts** | `bmad_benchmarks/envs/*/rollout.py` (8 files) | "Turkish field labels" prompts, Turkish regex patterns |
| **Benchmark data** | `bmad_benchmarks/envs/*/data/` | JSON items with Turkish expected_fields |
| **Docs** | `docs/KULLANIM-KILAVUZU.md`, `docs/bmad/*.md` | Full Turkish documentation |
| **config.toml** | `custom/config.toml` | Turkish comments |
| **README** | `README.md` | Turkish table headers, descriptions |
| **SKILLOPT.md** | `SKILLOPT.md` | Turkish benchmark descriptions |

---

## Phase 1: Templates (8 files)

All templates use Turkish field labels that the HMAC gate parses.
**This is the highest-risk change** — the gate script (`run_experiment.py`)
parses these exact field names.

### 1.1 Experiment Template (`templates/_template_E.md`)

| Current Turkish | New English |
|----------------|-------------|
| `Deney: E-NNN` | `Experiment: E-NNN` |
| `Tarih` | `Date` |
| `Durum` | `Status` |
| `Teori` | `Theory` |
| `Hipotez` | `Hypothesis` |
| `Ölçüm metrikleri` | `Measurement Metrics` |
| `Deney tasarımı` | `Experiment Design` |
| `Kod kapsamı` | `Code Scope` |
| `Ham sonuçlar` | `Raw Results` |
| `Belirsizlik` | `Uncertainty` |
| `Metrik` | `Metric` |
| `Karar` | `Decision` |
| `Kapı kanıtı` | `Gate Evidence` |
| `Sonraki adım` | `Next Step` |
| `planlandı` | `planned` |
| `ONAYLANDI` | `APPROVED` |
| `REDDEDİLDİ` | `REJECTED` |

**CRITICAL:** The gate script (`run_experiment.py`) uses regex to parse
these fields. After translating the template, the gate script's regex
patterns MUST be updated to match the new English field names. This is a
coordinated change — template + gate script in the same commit.

### 1.2 IR Template (`templates/_template_IR.md`)

| Current Turkish | New English |
|----------------|-------------|
| `Implementation Readiness: IR-XXX` | Keep as-is (already English header) |
| `Tarih` | `Date` |
| `Durum` | `Status` |
| `Araştırma girdileri` | `Research Inputs` |
| `Tasarım belgeleri` | `Design Documents` |
| `Başarı kriterleri` | `Success Criteria` |
| `Teknik bağımlılıklar` | `Technical Dependencies` |
| `Risk değerlendirmesi` | `Risk Assessment` |
| `Eksikler` | `Gaps` |
| `Karar` | `Decision` |
| `Sonraki adım` | `Next Step` |
| `hazırlanıyor` | `preparing` |
| `HAZIR` | `READY` |
| `EKSİK` | `INCOMPLETE` |

### 1.3 SP Template (`templates/_template_SP.md`)
Same pattern — translate all Turkish field labels to English.

### 1.4 Story Template (`templates/_template_S.md`)

| Current Turkish | New English |
|----------------|-------------|
| `Story: S-XXX` | Keep as-is |
| `Tarih` | `Date` |
| `Durum` | `Status` |
| `backlog` | `backlog` (already English) |
| `sprint` | `sprint` (already English) |
| `in-progress` | `in-progress` (already English) |
| `review` | `review` (already English) |
| `done` | `done` (already English) |
| `blocked` | `blocked` (already English) |
| `Öncelik` | `Priority` |
| `Story points` | `Story points` (already English) |
| `Atanan` | `Assignee` |
| `Bağımlılıklar` | `Dependencies` |
| `Notlar / İzleme` | `Notes / Tracking` |
| `Blokerler` | `Blockers` |
| `İlerleme Güncellemeleri` | `Progress Updates` |
| `Kararlar` | `Decisions` |
| `Test Stratejisi` | `Test Strategy` |
| `Araştırma Girdileri` | `Research Inputs` |
| `Tamamlama` | `Completion` |

### 1.5 QR Template (`templates/_template_QR.md`)
Translate all Turkish field labels to English equivalents.

### 1.6 PR Template (`templates/_template_PR.md`)
Translate all Turkish field labels to English equivalents.

### 1.7 README Template (`templates/README.md`)
Translate to English.

### 1.8 Tech-Debt Template (`templates/tech-debt.md`)
Translate to English.

---

## Phase 2: Hook Engine (5 Python files)

### 2.1 `hooks/engine/modules/guard.py` (885 lines)

**Deny reason strings** — these are shown to users:
- Line 144: `"BEKLİYOR"` → `"PENDING"`, `"REDDEDİLDİ"` → `"REJECTED"`
  (already has English equivalents — remove Turkish ones, keep English only)
- All `f"..."` deny reason strings are already in English (verified).
  Only the status comparison needs updating.

**Action:** Remove Turkish status string comparison at line 144.
Keep only English: `("PENDING", "REJECTED")`.

### 2.2 `hooks/engine/modules/code_docs.py` (804 lines)

**All template content is in Turkish.** Every `build_*_doc()` function
generates Turkish markdown:

| Function | Turkish Sections | English Sections |
|----------|-----------------|------------------|
| `build_learning_doc` | Öğrenilen, Bağlam, Kanıt, Uygulama, İlişkili Kayıtlar | Learned, Context, Evidence, Application, Related Records |
| `build_decision_doc` | Karar, Gerekçe, Sonuçlar, İlişkili Kayıtlar | Decision, Rationale, Results, Related Records |
| `build_troubleshooting_doc` | Hata, Neden, Çözüm, Önleme, İlişkili Kayıtlar | Error, Cause, Solution, Prevention, Related Records |
| `build_pattern_doc` | Kalıp, Kullanım Senaryosu, Örnek, Avantajlar, Dezavantajlar | Pattern, Usage Scenario, Example, Advantages, Disadvantages |
| `build_api_doc` | API, İmza, Kullanım, Dikkat Edilecekler, İlişkili Kayıtlar | API, Signature, Usage, Notes, Related Records |
| `build_pending_doc` | Açıklama, Bağlam, Sonraki Adımlar, İlişkili Kayıtlar | Description, Context, Next Steps, Related Records |

**Also translate:**
- `_update_index()`: `"Kararlar"` → `"Decisions"`, `"Kalıplar"` → `"Patterns"`, etc.
- `_create_index()`: Full Turkish content → English
- `_format_context()`: `"İlgili Code Docs"` → `"Related Code Docs"`, type_names
- `_extract_keywords()`: Turkish stop words → English stop words
- `_create_index()` content: `"Proje geçmişini hatırlamak..."` → English

### 2.3 `hooks/engine/modules/audit.py`

- `_detect_notable_events()` line 24: `"ONAYLANDI"` → `"APPROVED"`
  (also check for `"VERIFIED"`)
- `_try_generate_code_doc()` lines 108-143: All Turkish strings → English:
  - `"Mimari değişiklik: ..."` → `"Architecture change: ..."`
  - `"Mimari dosya değiştirildi"` → `"Architecture file modified"`
  - `"Audit hook tarafından otomatik tespit edildi"` → `"Auto-detected by audit hook"`
  - `"Hata tespiti: ..."` → `"Error detected: ..."`
  - `"Hata tespit edildi"` → `"Error detected"`
  - `"Çözüm henüz eklenmedi — manuel güncelleme gerekli"` → `"Fix not yet added — manual update needed"`
  - `"Tamamlanmamış iş"` → `"Unfinished work"`
  - `"Dosya: ..."` → `"File: ..."`
  - `"Bekleyen iş: ..."` → `"Pending work: ..."`
  - `"Manuel olarak güncellenmeli"` → `"Should be updated manually"`
- `_check_kopru_consumption()`: Turkish warning strings → English
  - `"KÖPRÜ uyumsuzluğu: ..."` → `"Bridge inconsistency: ..."`
  - `"bmad-code-review veya bmad-dev-story KÖPRÜ'sü henüz çalışmadı"` → `"bmad-code-review or bmad-dev-story bridge has not run yet"`
  - `"QR kaydı eksik/yanlış oluşturulmuş olabilir"` → `"QR record may be missing or incorrectly created"`
- Future plan detection regex (lines 79-83): Turkish patterns → English:
  - `r"(?:sonraki|bir sonraki|gelecek)\s+(?:adım|aşama|iterasyon)"` → `r"(?:next|following|upcoming)\s+(?:step|phase|iteration)"`
  - `r"(?:planlanan|düşünülen)\s+(?:çalışma|iş|değişiklik)"` → `r"(?:planned|intended)\s+(?:work|task|change)"`
  - `r"(?:henüz yapılmadı|henüz tamamlanmadı|bekliyor)"` → `r"(?:not yet done|not yet complete|pending)"`
  - `r"(?:ihtiyaç var|gerekli|eklenmeli|düzenlenmeli)"` → `r"(?:needed|required|should be added|should be modified)"`

### 2.4 `hooks/engine/modules/stop.py`

- Status check uses regex `_DONE_RE` which matches `done` — already English.
- Deny reason strings are already in English.

### 2.5 `hooks/engine/modules/config.py`

- Comments are in English. No changes needed.

---

## Phase 3: Custom TOML Files (102 files with Turkish)

### 3.1 Translation Categories

**Category A: Agent principles (Turkish sentences)**
~30 files with Turkish `principles = [...]` arrays.

Example (`bmad-agent-pm.toml`):
```toml
# Current:
principles = [
  "Tasarim kararlari ihtiyac kaniti ister: kullanici ihtiyaci kaynaga baglanir...",
]
# New:
principles = [
  "Design decisions require evidence of need: user needs are traced to sources...",
]
```

**Category B: activation_steps_append (mixed Turkish/English)**
~50 files with Turkish instructions in activation steps.

Example (`bmad-create-story.toml`):
```toml
# Current:
"AC METADATA ZORUNLULUGU: Her Acceptance Criterion icin asagidaki alanlari doldur..."
# New:
"AC METADATA REQUIREMENT: For each Acceptance Criterion, fill in the following fields..."
```

**Category C: Comments only**
~20 files with Turkish comments. Translate or remove.

**Category D: Already English**
~19 files already in English — no changes.

### 3.2 Additional Turkish Categories

**Category E: Agent `role` fields (5 files):**
- `bmad-advanced-elicitation.toml`: `"Mevcut çıktıyı derinlemesine eleştir ve yeniden şekillendir"`
- `bmad-editorial-review-prose.toml`: `"Metinleri iletişim kalitesi açısından incele ve iyileştir"`
- `bmad-editorial-review-structure.toml`: `"Belgeleri yapısal olarak incele ve yeniden düzenle"`
- `bmad-review-adversarial-general.toml`: `"Kod ve tasarımı düşmanca bir perspektiften incele"`
- `bmad-review-edge-case-hunter.toml`: `"Sistemin uç durumlarını ve sınır koşullarını bul"`

**Category F: Turkish in non-KOPRU activation_steps_append (20+ files):**
Includes: `bmad-advanced-elicitation`, `bmad-bmb-setup`, `bmad-eval-runner`,
`bmad-index-docs`, `bmad-loop-*`, `bmad-module-builder`, `bmad-shard-doc`,
`bmad-research-experiment`, `bmad-review-*`, `wds-0-*`, `wds-1-*`,
`wds-2-*`, `wds-3-*`, `wds-4-*`, `wds-5-*`, `wds-6-*`, `wds-7-*`,
`wds-8-*`

### 3.3 Translation Strategy

For Category A-F, translate in bulk. The TOML files follow a consistent
pattern — use a script or batch process:

1. Extract all Turkish strings from `custom/*.toml`
2. Translate each string
3. Write back

**Key terminology map for TOML translations:**

| Turkish | English |
|---------|---------|
| ZORUNLULUGU | REQUIREMENT |
| eslestirme | matching |
| dogrulama | validation |
| uyari | warning |
| kayit | record |
| zincir | chain |
| kapisi | gate |
| haberlesme | communication |
| test edilmemis | untested |
| iterasyon | iteration |
| prototip | prototype |
| ozellik | feature |
| durum | status |
| bagimlilik | dependency |
| oncelik | priority |
| degerlendirme | evaluation |
| hedef | target |
| kaynak | source |
| kanit | evidence |
| rapor | report |
| deney | experiment |
| arastirma | research |
| tasarim | design |
| kalite | quality |
| uretim | production |
| hazirlik | readiness |
| planlama | planning |
| gelistirme | development |

---

## Phase 4: Benchmark Rollouts (8 files)

### 4.1 Prompt Strings

All 5 custom benchmark rollouts say `"in Turkish field labels"`.
Change to `"in English field labels"`:

- `bmad_custom_ir/rollout.py` line 12
- `bmad_custom_sp/rollout.py` line 12
- `bmad_custom_story/rollout.py` line 12
- `bmad_custom_qr/rollout.py` line 12
- `bmad_custom_pr/rollout.py` line 12

### 4.2 Research Experiment Rollout

`bmad_research_experiment/rollout.py` line 34:
```
"The record MUST contain these fields in Turkish: "
→
"The record MUST contain these fields: "
```

Also update `_FIELD_PATTERNS` (lines 8-13) to match English field names:
```python
_FIELD_PATTERNS = {
    "Theory": re.compile(r"##\s*Theory|###\s*Theory|\*\*Theory:", re.IGNORECASE),
    "Hypothesis": re.compile(r"Hypothesis.*H-\d+|##\s*Hypothesis|...", re.IGNORECASE),
    "Measurement Metrics": re.compile(r"Measurement Metrics|##\s*Measurement|...", re.IGNORECASE),
    "Experiment Design": re.compile(r"Experiment Design|##\s*Experiment|...", re.IGNORECASE),
    "Code Scope": re.compile(r"Code Scope|##\s*Code|...", re.IGNORECASE),
}
```

### 4.3 Code Docs Rollout

`bmad_code_docs/rollout.py`:
- Line 110: `"all required sections in Turkish."` → `"all required sections.`
- `_SECTION_PATTERNS` (lines 7-42): All Turkish section names → English
- `_check_context_loading()` line 78: Turkish context phrases → English
- `_prompt()` user string: Turkish → English

### 4.4 Meta Benchmark Rollouts (3 files)

**`bmad_meta_guard/rollout.py`:**
- Turkish decision keywords (line 8): `"engelle"`, `"reddet"`, `"izin"`,
  `"serbest"`, `"geçerli"` → English equivalents

**`bmad_meta_path/rollout.py`:**
- Turkish path/status assertions (lines 42-50): `"planlandı"`,
  `"devam ediyor"`, `"tamamlandı"`, `"Kayıt"`, `"oluşturulur"`, `"durum"`
  → English equivalents

**`bmad_meta_root/rollout.py`:**
- Turkish uncertainty regex (lines 5-7): `"bilmiyorum"`, `"emin değilim"`,
  `"emin degilim"`, `"farkında değilim"`, `"sanırım"`, `"muhtemelen"`,
  `"tahminen"`, `"tahmin ederim"`, `"zannet"`, `"kararsızım"`
  → English equivalents
- Turkish direction keywords (lines 19-25): `"hedef"`, `"proje"`, `"yaz"`,
  `"oluştur"`, `"üret"`, `"oku"`, `"yükle"` → English equivalents
- Turkish selfcheck test sentences (lines 55-65) → English

### 4.5 Base Rollout Turkish Normalization

`_base_/rollout.py`:
- `normalize_turkish_field()` → Rename to `normalize_field_label()` and
  generalize (the function already handles generic suffix stripping)
- `score_field_presence()` docstring: update "Turkish field labels" → "expected field labels"

### 4.5 Training Data (JSON files)

Each benchmark's `data/train/`, `data/val/`, `data/test/` directories
contain JSON with Turkish expected_fields. These must be updated to match
the new English field names.

**Affected benchmarks:**
- `bmad_custom_ir/data/` — `expected_fields` with Turkish labels
- `bmad_custom_sp/data/`
- `bmad_custom_story/data/`
- `bmad_custom_qr/data/`
- `bmad_custom_pr/data/`
- `bmad_research_experiment/data/` — `expected_fields` with Turkish names
- `bmad_code_docs/data/` — Turkish section/tag expectations

**Strategy:** Write a migration script that:
1. Reads each JSON file
2. Replaces Turkish field names with English equivalents
3. Writes back

---

## Phase 5: Skill SKILL.md Files (2 files with Turkish)

### 5.1 `skills/bmad-research-experiment/SKILL.md`

Contains: `"Kayıtlar Türkçe alan adları kullanır"` and gate field
descriptions in Turkish.

Translate to:
```
Records use English field labels. The gate parses: Theory, Hypothesis,
Measurement Metrics, Experiment Design, Code Scope.
A record with non-English labels is rejected as incomplete — changing
the language does not bypass the gate.
```

### 5.2 `skills/bmad-code-docs/SKILL.md`

Contains: `"Türkçe alan etiketleri tercih edilir"`

Translate to: `"English field labels are required."`

---

## Phase 6: Commands (4 files)

### 6.1 `commands/init.md`
Full Turkish → Full English.

### 6.2 `commands/kapi-kur.md`
Full Turkish → Full English. Rename to `commands/gate-setup.md` or keep
Turkish name with English content (decide).

### 6.3 `commands/dogrula.md`
Full Turkish → Full English.

### 6.4 `commands/denetim.md`
Full Turkish → Full English.

---

## Phase 7: Documentation (3 files)

### 7.1 `docs/KULLANIM-KILAVUZU.md` (41KB)

Full Turkish usage guide → Full English. This is the largest single file.
Keep the same structure, translate all content.

### 7.2 `docs/bmad/research-methodology.md`
Translate to English.

### 7.3 `docs/bmad/development-methodology.md`
Translate to English.

### 7.4 `docs/bmad/dev-skill-to-methodology-bridge.md`
Translate to English.

---

## Phase 8: Top-Level Files

### 8.1 `README.md`
Turkish table headers and descriptions → English.

### 8.2 `SKILLOPT.md`
Turkish benchmark descriptions → English.

### 8.3 `custom/config.toml`
Turkish comments → English.

---

## Phase 9: Gate Script Coordination

**This is the critical dependency.** The gate script at
`skills/bmad-research-experiment/scripts/run_experiment.py` parses
experiment record fields by their Turkish names.

After translating templates (Phase 1), the gate script MUST be updated
to parse English field names. This includes:

1. Regex patterns matching `Teori`, `Hipotez`, `Ölçüm metrikleri`, etc.
2. Status string comparisons (`ONAYLANDI` → `APPROVED`, etc.)
3. Any Turkish in error messages or output

**Verify:** After changes, run:
```bash
python3 skills/bmad-research-experiment/scripts/run_experiment.py --help
python3 skills/bmad-research-experiment/scripts/run_experiment.py --verify --record docs/experiments/E-001.md
```

---

## Phase 10: Validation & Testing

### 10.1 Gate Validation
After all changes, verify the gate still works:
```bash
# Create a test experiment record with English fields
# Run gate verification
python3 skills/bmad-research-experiment/scripts/run_experiment.py --verify --record test.md
```

### 10.2 Benchmark Self-Checks
```bash
python3 bmad_benchmarks/envs/bmad_code_docs/rollout.py --selfcheck
python3 bmad_benchmarks/envs/bmad_meta_root/verify_combinations.py
```

### 10.3 Hook Engine Smoke Test
```bash
echo '{"tool_name":"terminal","tool_input":{"command":"ls"}}' | \
  HOOK_TYPE=guard python3 hooks/engine/main.py
```

### 10.4 Full Plugin Health Check
```bash
sh commands/check-plugin.sh
sh commands/check-custom.sh
```

---

## Execution Order

```
Phase 9 (gate script) ← MUST be done with Phase 1 (templates)
    ↓
Phase 1 (templates) + Phase 9 (gate)  ← atomic commit
    ↓
Phase 2 (hook engine)
    ↓
Phase 4 (benchmark rollouts + data)
    ↓
Phase 3 (custom TOML) — largest, can be parallelized
    ↓
Phase 5 (skill SKILL.md)
    ↓
Phase 6 (commands)
    ↓
Phase 7 (docs)
    ↓
Phase 8 (top-level files)
    ↓
Phase 10 (validation)
```

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Gate script regex breaks | **CRITICAL** | Phase 1+9 atomic commit; test with existing E-001.md |
| Training data mismatch | HIGH | Migration script + self-check after |
| Custom TOML breakage | MEDIUM | check-custom.sh validates structure |
| Skill prompt regression | MEDIUM | SkillOpt eval after changes |
| Turkish stop words in code_docs | LOW | Replace with English stop words |

---

## Phase 11: Code Quality Refactoring

Address code quality issues found during the audit. These changes are
independent of the English migration but should be done in the same
release cycle.

### 11.1 `hooks/engine/modules/guard.py` — Deduplication

**Problem:** `quality()` (lines 703-758) and `deploy()` (lines 817-885)
share ~80 lines of identical gate-check logic. Four
`_find_done_stories_without_*` functions (lines 572-700) are copy-paste
with different globs.

**Fix:**
1. Extract `_find_done_stories_without_record(root, record_glob, record_dir)`
   — single parameterized helper replacing 4 functions
2. Extract `_check_kapi_gates(root, include_pr=False)` — shared gate logic
   for quality() and deploy()
3. Remove unused `import json` (line 5)
4. Add stderr logging to `verify_record()` exception handler (line 73)

### 11.2 `hooks/engine/modules/code_docs.py` — Deduplication

**Problem:** `type_names` dict defined 3 times identically (lines 108, 144,
747).

**Fix:** Extract to module-level constant `TYPE_NAMES`.

### 11.3 `hooks/engine/modules/stop.py` — Lazy Import Cleanup

**Problem:** Unnecessary lazy import of `repo_root` at line 49 (no circular
dependency risk since it lives in `utils.py`).

**Fix:** Move to top-level import.

### 11.4 Custom Rollout Deduplication (Optional)

**Problem:** 5 `bmad_custom_*/rollout.py` files are near-identical (27 lines
each, differ only in `_prompt` function).

**Decision:** Keep as-is. The duplication is low-cost (stable, rarely
modified), and the current pattern matches the base class architecture.
Document this as a deliberate simplification.

---

## Phase 12: Test Coverage

**Current state:** ~13% of Python files have tests. The three largest
gaps:

| Area | Files | Tests | Risk |
|------|-------|-------|------|
| `hooks/engine/` | 12 | 0 | **CRITICAL** — runs on every agent action |
| `bmad_benchmarks/` | ~42 | 0 | HIGH — entire benchmark suite |
| `scripts/` | 4 | 0 | MEDIUM — training/eval entry points |

### 12.1 Hook Engine Tests (Priority: CRITICAL)

Create `hooks/engine/tests/` with:

```
hooks/engine/tests/
├── __init__.py
├── conftest.py              # Shared fixtures (mock json_in, temp dirs)
├── test_guard.py            # Guard logic: experiment validation, AC metadata,
│                            #   story metadata, secret protection, free zones
├── test_stop.py             # Stop logic: incomplete stories, unapproved code
├── test_audit.py            # Audit logic: event detection, code doc generation
├── test_utils.py            # Utility functions: norm_path, is_free, is_code_target
├── test_config.py           # Config constants, file classification
├── test_code_docs.py        # Code doc generation, recall, index management
├── test_bash_targets.py     # Bash command target extraction
└── test_main.py             # Entry point routing
```

**Key test cases for `test_guard.py`:**
- Experiment with APPROVED status → allow
- Experiment with PENDING/REJECTED status → deny
- Missing experiment record → deny
- AC metadata validation (missing Experiment, Type, Measured, Verify fields)
- HYPOTHESIS tag bypass
- Task↔AC reference matching
- DoD identifier validation
- Secret leak detection (gate-key, .bmad references)
- Free zone bypass (scratch/, tmp/, docs/)
- Code vs non-code file classification

**Key test cases for `test_stop.py`:**
- In-progress story → deny stop
- Unapproved code changes → deny stop
- All stories done, no unapproved code → allow

### 12.2 Benchmark Tests (Priority: HIGH)

Create `bmad_benchmarks/tests/` with:

```
bmad_benchmarks/tests/
├── __init__.py
├── test_registry.py         # Adapter registration, config loading, argv building
├── test_base_adapter.py     # BmadAdapter setup, rollout delegation
├── test_base_dataloader.py  # JSON loading, normalization, split handling
├── test_base_rollout.py     # rollout_one, run_batch, score_field_presence,
│                            #   normalize_field_label
├── test_custom_rollouts.py  # All 5 custom benchmark scoring
├── test_meta_root.py        # verify_combinations coverage check
└── test_code_docs_rollout.py # Self-check integration
```

### 12.3 Script Tests (Priority: MEDIUM)

Create `scripts/tests/` with:

```
scripts/tests/
├── __init__.py
├── test_train_bmad.py       # Config loading, argv building (mock SkillOpt)
├── test_eval_bmad.py        # Config loading, argv building (mock SkillOpt)
├── test_create_record.py    # Methodology record creation
└── test_create_qr.py        # QR record creation
```

### 12.4 Project-Level Test Configuration

Create `pyproject.toml` (or `pytest.ini`):

```toml
[tool.pytest.ini_options]
testpaths = ["hooks/engine/tests", "bmad_benchmarks/tests", "scripts/tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = "-v --tb=short"
```

---

## Commit Strategy

1. `feat: translate gate script + templates to English (atomic)` — Phase 1+9
2. `feat: translate hook engine strings to English` — Phase 2
3. `feat: translate benchmark rollouts + data to English` — Phase 4
4. `feat: translate custom TOML files to English` — Phase 3
5. `feat: translate skill SKILL.md files to English` — Phase 5
6. `feat: translate commands to English` — Phase 6
7. `feat: translate documentation to English` — Phase 7
8. `feat: translate top-level files to English` — Phase 8
9. `refactor: deduplicate guard.py gate logic` — Phase 11.1
10. `refactor: extract code_docs TYPE_NAMES constant` — Phase 11.2
11. `test: add hook engine tests` — Phase 12.1
12. `test: add benchmark suite tests` — Phase 12.2
13. `test: add script tests + pyproject.toml` — Phase 12.3-12.4
14. `test: validate all English translations` — Phase 10

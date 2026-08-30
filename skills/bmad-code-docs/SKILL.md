---
name: bmad-code-docs
description: 'Code docs yönetimi — hatırlama, sorgulama, üretme. Use when the user says they want to recall past decisions, find related patterns, document a new decision, or search project knowledge.'
triggers: ["bmad-code-docs", "/bmad-code-docs", "recall", "hatırla", "bul", "karar kaydı", "code docs", "geçmiş"]
---

# Code Docs Workflow

**Goal:** Proje geçmişini hatırlamak, sorgulamak ve yeni bilgi üretmek. Hook'lar tarafından otomatik üretilen code docs'ları yönetir.

**Your Role:** Proje bilgi yöneticisisin. Geçmiş kararları, kalıpları, dersleri ve hata çözümlerini hatırlatır, yeni kayıt üretirsin.

## Conventions

- `{project-root}` resolves from environment variables: `CLAUDE_PROJECT_DIR` → `OPENHANDS_PROJECT_DIR` → `cwd`.
- `{metodoloji-root}` = plugin root (`~/.openhands/plugins/installed/metodoloji`).
- `{code-docs-root}` = `{project-root}/docs/code-docs/`.
- `{user_name}` and `{communication_language}` come from `bmad/config.user.toml`.

## On Activation

### Step 1: Index Yükle

`{code-docs-root}/index.md` dosyasını oku. Bu dosya tüm code docs'ların dizinini içerir.

### Step 2: Kullanıcı Niyetini Anla

Kullanıcının ne yapmak istediği:

- **Hatırla/Sorgula:** "X kararını hatırla", "Y kalıbını bul", "E-001 ile ilgili her şey"
- **Kaydet:** "Bu kararı kaydet", "Yeni kalıp ekle", "Hata çözümü kaydet"
- **Dizin:** "Tüm code docs'ları listele", "Bugün üretilenler"

### Step 3: Gerçekleştir

#### Otomatik Bağlam Yükleme

Her görev başlangıcında otomatik olarak ilgili code-doc'ları yükle:

```python
# Görev açıklamasına göre ilgili doc'ları bul ve yükle
from hooks.engine.modules.code_docs import load_context_for_task
context = load_context_for_task("Guard hook free-zone bypass'ını test et")
# → İlgili pattern, learning ve pending doc'ları döndürür

# Son eklenen doc'ları yükle
from hooks.engine.modules.code_docs import load_recent_docs
recent = load_recent_docs(n=5)

# Bekleyen işleri yükle (dikkat gerektirenler)
from hooks.engine.modules.code_docs import load_pending_docs
pending = load_pending_docs()
```

#### Hatırlama/Sorgulama

`{metodoloji-root}/hooks/engine/modules/code_docs.py` modülünü kullan:

```python
# Etikete göre ara
from hooks.engine.modules.code_docs import recall_by_tag
results = recall_by_tag("auth")

# Deney ID'sine göre ara
from hooks.engine.modules.code_docs import recall_by_experiment
results = recall_by_experiment("E-001")

# Türe göre listele
from hooks.engine.modules.code_docs import recall_by_type
results = recall_by_type("decision")

# Tümünü getir
from hooks.engine.modules.code_docs import recall_all
all_docs = recall_all()
```

#### Kayıt Üretme

```python
# Karar kaydı
from hooks.engine.modules.code_docs import create_decision
path = create_decision(
    title="JWT yerine session-based auth",
    decision="Session-based auth kullandık",
    rationale="Daha güvenli, XPS riski az",
    tags=["auth", "security"],
    related_experiments=["E-001"]
)

# Öğrenme kaydı
from hooks.engine.modules.code_docs import create_learning
path = create_learning(
    experiment_id="E-001",
    record_path="docs/experiments/E-001.md",
    title="Guard hook free-zone bypass",
    tags=["guard", "hooks"]
)

# Hata çözümü
from hooks.engine.modules.code_docs import create_troubleshooting
path = create_troubleshooting(
    title="Gate key hatası",
    error="gate key not configured",
    cause="run_experiment.py --init-secret çalıştırılmamış",
    solution="python3 run_experiment.py --init-secret",
    prevention="Bootstrap betiğine ekle"
)

# Kalıp
from hooks.engine.modules.code_docs import create_pattern
path = create_pattern(
    title="Async audit logging",
    pattern="Audit hook PostToolUse'ta çalışır, JSON-lines yazar",
    usage="Her tool kullanımından sonra tetiklenir",
    example="def audit(json_in): ...",
    pros="Non-blocking, basit",
    cons="Dosya boyutu büyüyebilir"
)

# API kullanımı
from hooks.engine.modules.code_docs import create_api
path = create_api(
    title="run_experiment.py API",
    signature="def run_experiment(record: str, run: str = None, verify: bool = False) -> dict",
    usage="result = run_experiment(record='docs/experiments/E-001.md', run='python bench.py')",
    notes="--dry-run ile önce test et"
)

# Bekleyen iş / niyet
from hooks.engine.modules.code_docs import create_pending
path = create_pending(
    title="Self-improvement döngüsü ekle",
    description="Eğitim sistemi kendi sonuçlarından öğrenmeli — başarılı rollout'lardan yeni training verisi üretmeli",
    context="SkillOpt mevcut skill'i optimize ediyor ama sonuçları geri beslemiyor",
    next_steps="1. Metadata tracking ekle 2. Skill evolution mekanizması kur 3. Cross-benchmark transfer",
    priority="high",
    tags=["training", "improvement", "pending"],
    related_experiments=["E-001"]
)

# Otomatik tespit (TODO/FIXME)
# Audit hook otomatik olarak TODO/FIXME yorumlarını yakalar ve pending doc üretir
```

### Step 4: Sonuç Göster

Üretilen veya bulunan doc'u kullanıcıya göster. İlişkili kayıtları (deney, story) link olarak ekle.

## Paths

### Project Root (Proje Kod Tabanı)
- Code docs: `{project-root}/docs/code-docs/`
- Index: `{project-root}/docs/code-docs/index.md`
- Templates: `{project-root}/docs/code-docs/*/_template.md`

### Metodoloji Root (Plugin Dizini)
- Config: `{metodoloji-root}/hooks/engine/modules/config.py`
- Modül: `{metodoloji-root}/hooks/engine/modules/code_docs.py`

## HALT CONDITIONS

- HALT if `{code-docs-root}` does not exist
- HALT if `code_docs.py` module is not importable
- HALT if user provides invalid doc type (must be: decision, pattern, learning, api, troubleshooting, pending)

## VALIDATION

- Frontmatter zorunlu: id, type, title, date, tags
- Türkçe alan etiketleri tercih edilir
- related_experiments ve related_stories opsiyonel ama önerilir
- Her kayıt bir template'i takip etmeli
- Index otomatik güncellenir

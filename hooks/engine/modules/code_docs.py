"""Code docs generation, recall, and index management.

Provides structured documentation for project knowledge — decisions, patterns,
learnings, API usage, and troubleshooting. Hook-triggered automatic generation
with manual recall via bmad-code-docs skill.
"""

import os
import pathlib
import re
from datetime import datetime

from .config import CODE_DOCS_DIR, CODE_DOCS_TYPES

# Extend CODE_DOCS_TYPES with template info (not in config)
DOC_TYPES = {
    **CODE_DOCS_TYPES,
    "decision": {**CODE_DOCS_TYPES.get("decision", {}), "template": "_template.md"},
    "pattern": {**CODE_DOCS_TYPES.get("pattern", {}), "template": "_template.md"},
    "learning": {**CODE_DOCS_TYPES.get("learning", {}), "template": "_template.md"},
    "api": {**CODE_DOCS_TYPES.get("api", {}), "template": "_template.md"},
    "troubleshooting": {**CODE_DOCS_TYPES.get("troubleshooting", {}), "template": "_template.md"},
    "pending": {**CODE_DOCS_TYPES.get("pending", {}), "template": "_template.md"},
}


def _get_project_root() -> pathlib.Path:
    """Get project root from standard environment variables.

    Priority:
    1. CLAUDE_PROJECT_DIR (Claude Code standard)
    2. OPENHANDS_PROJECT_DIR (OpenHands standard)
    3. os.getcwd() (last resort)
    """
    root = (
        os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("OPENHANDS_PROJECT_DIR")
        or os.getcwd()
    )
    return pathlib.Path(root).absolute()


def _get_code_docs_root() -> pathlib.Path:
    return _get_project_root() / CODE_DOCS_DIR


def _next_id(doc_type: str) -> str:
    """Generate next sequential ID for a doc type."""
    info = DOC_TYPES[doc_type]
    docs_dir = _get_code_docs_root() / info["dir"]
    if not docs_dir.exists():
        return f"{info['prefix']}-001"

    existing = list(docs_dir.glob(f"{info['prefix']}-*.md"))
    nums = []
    for f in existing:
        m = re.match(rf"{info['prefix']}-(\d+)", f.name)
        if m:
            nums.append(int(m.group(1)))

    next_num = max(nums, default=0) + 1
    return f"{info['prefix']}-{next_num:03d}"


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to URL-friendly slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:max_len]


def _write_doc(doc_type: str, slug: str, content: str) -> pathlib.Path:
    """Write a code doc file and return its path."""
    info = DOC_TYPES[doc_type]
    doc_id = _next_id(doc_type)
    filename = f"{doc_id}-{slug}.md"
    docs_dir = _get_code_docs_root() / info["dir"]
    docs_dir.mkdir(parents=True, exist_ok=True)
    path = docs_dir / filename
    # Replace placeholder ID in content with actual ID
    content = re.sub(rf"{info['prefix']}-NEW-[^\n]+", doc_id, content)
    path.write_text(content, encoding="utf-8")
    return path


def _update_index():
    """Regenerate index.md from actual doc files."""
    root = _get_code_docs_root()
    index_path = root / "index.md"

    if not index_path.exists():
        # Create index.md from scratch
        _create_index(index_path)
        return

    lines = index_path.read_text(encoding="utf-8").splitlines()
    # Find the categories section and rebuild it
    new_lines = []
    in_categories = False
    for line in lines:
        if line.startswith("## Kategoriler"):
            in_categories = True
            new_lines.append(line)
            new_lines.append("")
            for doc_type, info in DOC_TYPES.items():
                type_dir = root / info["dir"]
                docs = sorted(type_dir.glob(f"{info['prefix']}-*.md")) if type_dir.exists() else []
                type_names = {
                    "decision": "Kararlar",
                    "pattern": "Kalıplar",
                    "learning": "Dersler",
                    "api": "API Kullanımları",
                    "troubleshooting": "Sorun Giderme",
                    "pending": "Bekleyen İşler",
                }
                new_lines.append(f"### [{type_names[doc_type]}](./{info['dir']}/) — {len(docs)} kayıt")
                for doc in docs[:5]:  # Show latest 5
                    content = doc.read_text(encoding="utf-8")
                    title_match = re.search(r"title:\s*\"(.+?)\"", content)
                    title = title_match.group(1) if title_match else doc.stem
                    new_lines.append(f"- [{title}](./{info['dir']}/{doc.name})")
                if len(docs) > 5:
                    new_lines.append(f"- ... ve {len(docs) - 5} tane daha")
                new_lines.append("")
            continue
        if in_categories and line.startswith("## ") and not line.startswith("## Kategoriler"):
            in_categories = False
        if not in_categories:
            new_lines.append(line)

    index_path.write_text("\n".join(new_lines), encoding="utf-8")


def _create_index(index_path: pathlib.Path):
    """Create a new index.md file."""
    content = """# Code Docs Dizini

Proje geçmişini hatırlamak ve yeni bilgi üretmek için kullanılan yapılandırılmış dokümantasyon sistemi.

## Kategoriler

"""
    for doc_type, info in DOC_TYPES.items():
        type_names = {
            "decision": "Kararlar",
            "pattern": "Kalıplar",
            "learning": "Dersler",
            "api": "API Kullanımları",
            "troubleshooting": "Sorun Giderme",
            "pending": "Bekleyen İşler",
        }
        content += f"### [{type_names[doc_type]}](./{info['dir']}/) — 0 kayıt\n\n"

    content += """## Otomatik Üretim

Bu dosyalar hook'lar tarafından otomatik üretilir:
- **Audit hook**: Önemli olayları tespit eder (deney onayı, mimari değişiklik, hata çözümü)
- **Guard hook**: Deney onayından sonra learning doc üretir
- **Skill**: `bmad-code-docs` ile manuel recall ve kayıt

## Arama

- Etikete göre: `recall_by_tag("auth")`
- Deney ID'sine göre: `recall_by_experiment("E-001")`
- Kategoriye göre: `docs/code-docs/decisions/` klasöründe listeleme

## Otomatik Yükleme

Görev başlangıcında ilgili doc'lar otomatik yüklenir:

```python
# Görev bağlamına göre
context = load_context_for_task("Guard hook auth testini çalıştır")

# Son doc'lar
recent = load_recent_docs(n=5)

# Bekleyen işler
pending = load_pending_docs()
```

## Son Güncelleme

Otomatik olarak güncellenir — elle düzenlenmesi gerekmez.
"""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(content, encoding="utf-8")


# --- Build functions ---

def build_learning_doc(experiment_id: str, record_path: str,
                       title: str = "", tags: list[str] | None = None) -> str:
    """Build a learning doc from an approved experiment record."""
    record = pathlib.Path(record_path)
    record_content = record.read_text(encoding="utf-8") if record.exists() else ""

    # Parse key fields from experiment record
    theory_match = re.search(r"\*\*Teori:\*\*\s*(.+)", record_content)
    hypothesis_match = re.search(r"\*\*Hipotez:\*\*\s*(.+)", record_content)
    metric_match = re.search(r"\*\*Ölçüm metrikleri:\*\*\s*(.+)", record_content)
    decision_match = re.search(r"\*\*Karar:\*\*\s*(.+)", record_content)

    theory = theory_match.group(1).strip() if theory_match else "Belirtilmemiş"
    hypothesis = hypothesis_match.group(1).strip() if hypothesis_match else "Belirtilmemiş"
    metric = metric_match.group(1).strip() if metric_match else "Belirtilmemiş"
    decision = decision_match.group(1).strip() if decision_match else "ONAYLANDI"

    if not title:
        title = f"Deney {experiment_id} öğrenimi"
    if tags is None:
        tags = ["experiment", "learning"]

    today = datetime.now().strftime("%d.%m.%Y")
    slug = _slugify(title)

    content = f"""---
id: L-{experiment_id}
type: learning
title: "{title}"
date: {today}
tags: {tags}
related_experiments: [{experiment_id}]
status: active
---

## Öğrenilen

Deney {experiment_id} sonucunda {hypothesis} hipotezi {decision} kararıyla onaylandı.

## Bağlam

Teori: {theory}

Hipotez: {hypothesis}

Ölçüm: {metric}

## Kanıt

Deney kaydı: [/{record_path}]({record_path})

## Uygulama

Bu deneyden elde edilen bilgiler gelecek benzer senaryolarda kullanılacaktır.

## İlişkili Kayıtlar

- Deney: [/{record_path}]({record_path})
"""
    return content


def build_decision_doc(title: str, decision: str, rationale: str,
                       results: str = "", tags: list[str] | None = None,
                       related_experiments: list[str] | None = None,
                       related_stories: list[str] | None = None) -> str:
    """Build a decision doc."""
    if tags is None:
        tags = ["decision"]
    if related_experiments is None:
        related_experiments = []
    if related_stories is None:
        related_stories = []

    today = datetime.now().strftime("%d.%m.%Y")
    slug = _slugify(title)

    exp_refs = ", ".join(related_experiments) if related_experiments else ""
    story_refs = ", ".join(related_stories) if related_stories else ""

    content = f"""---
id: D-NEW-{slug}
type: decision
title: "{title}"
date: {today}
tags: {tags}
related_experiments: [{exp_refs}]
related_stories: [{story_refs}]
status: active
---

## Karar

{decision}

## Gerekçe

{rationale}

## Sonuçlar

{results if results else "Henüz sonuç yok — güncellenecek."}

## İlişkili Kayıtlar

"""
    for exp in related_experiments:
        content += f"- Deney: [{exp}](../../experiments/{exp}.md)\n"
    for story in related_stories:
        content += f"- Story: [{story}](../../development/stories/{story}.md)\n"

    return content


def build_troubleshooting_doc(title: str, error: str, cause: str,
                               solution: str, prevention: str = "",
                               tags: list[str] | None = None) -> str:
    """Build a troubleshooting doc."""
    if tags is None:
        tags = ["troubleshooting"]

    today = datetime.now().strftime("%d.%m.%Y")
    slug = _slugify(title)

    content = f"""---
id: T-NEW-{slug}
type: troubleshooting
title: "{title}"
date: {today}
tags: {tags}
status: active
---

## Hata

{error}

## Neden

{cause}

## Çözüm

{solution}

## Önleme

{prevention if prevention else "Belirtilmedi."}

## İlişkili Kayıtlar

"""
    return content


def build_pattern_doc(title: str, pattern: str, usage: str,
                      example: str = "", pros: str = "", cons: str = "",
                      tags: list[str] | None = None) -> str:
    """Build a pattern doc."""
    if tags is None:
        tags = ["pattern"]

    today = datetime.now().strftime("%d.%m.%Y")
    slug = _slugify(title)

    content = f"""---
id: P-NEW-{slug}
type: pattern
title: "{title}"
date: {today}
tags: {tags}
status: active
---

## Kalıp

{pattern}

## Kullanım Senaryosu

{usage}

## Örnek

```python
{example if example else "# Örnek eklenecek"}
```

## Avantajlar

{pros if pros else "Belirtilmedi."}

## Dezavantajlar

{cons if cons else "Belirtilmedi."}

## İlişkili Kayıtlar

"""
    return content


def build_api_doc(title: str, signature: str, usage: str,
                  notes: str = "", tags: list[str] | None = None) -> str:
    """Build an API usage doc."""
    if tags is None:
        tags = ["api"]

    today = datetime.now().strftime("%d.%m.%Y")
    slug = _slugify(title)

    content = f"""---
id: A-NEW-{slug}
type: api
title: "{title}"
date: {today}
tags: {tags}
status: active
---

## API

{title}

## İmza

```python
{signature}
```

## Kullanım

```python
{usage}
```

## Dikkat Edilecekler

{notes if notes else "Belirtilmedi."}

## İlişkili Kayıtlar

"""
    return content


def build_pending_doc(title: str, description: str, context: str = "",
                      next_steps: str = "", priority: str = "normal",
                      tags: list[str] | None = None,
                      related_experiments: list[str] | None = None,
                      related_stories: list[str] | None = None) -> str:
    """Build a pending/intention doc for unfinished work, planned items, or LLM thoughts."""
    if tags is None:
        tags = ["pending"]
    if related_experiments is None:
        related_experiments = []
    if related_stories is None:
        related_stories = []

    today = datetime.now().strftime("%d.%m.%Y")
    slug = _slugify(title)

    exp_refs = ", ".join(related_experiments) if related_experiments else "[]"
    story_refs = ", ".join(related_stories) if related_stories else "[]"

    content = f"""---
id: X-NEW-{slug}
type: pending
title: "{title}"
date: {today}
tags: {tags}
related_experiments: [{exp_refs}]
related_stories: [{story_refs}]
priority: {priority}
status: pending
---

## Açıklama

{description}

## Bağlam

{context if context else "Belirtilmedi."}

## Sonraki Adımlar

{next_steps if next_steps else "Henüz belirlenmedi."}

## İlişkili Kayıtlar

"""
    for exp in related_experiments:
        content += f"- Deney: [{exp}](../../experiments/{exp}.md)\n"
    for story in related_stories:
        content += f"- Story: [{story}](../../development/stories/{story}.md)\n"

    return content


# --- Write functions ---

def create_learning(experiment_id: str, record_path: str,
                    title: str = "", tags: list[str] | None = None) -> pathlib.Path:
    """Create and write a learning doc. Returns the path."""
    content = build_learning_doc(experiment_id, record_path, title, tags)
    slug = _slugify(title or f"deney-{experiment_id}-ogrenimi")
    path = _write_doc("learning", slug, content)
    _update_index()
    return path


def create_decision(title: str, decision: str, rationale: str,
                    results: str = "", tags: list[str] | None = None,
                    related_experiments: list[str] | None = None,
                    related_stories: list[str] | None = None) -> pathlib.Path:
    """Create and write a decision doc. Returns the path."""
    content = build_decision_doc(title, decision, rationale, results,
                                  tags, related_experiments, related_stories)
    slug = _slugify(title)
    path = _write_doc("decision", slug, content)
    _update_index()
    return path


def create_troubleshooting(title: str, error: str, cause: str,
                           solution: str, prevention: str = "",
                           tags: list[str] | None = None) -> pathlib.Path:
    """Create and write a troubleshooting doc. Returns the path."""
    content = build_troubleshooting_doc(title, error, cause, solution,
                                         prevention, tags)
    slug = _slugify(title)
    path = _write_doc("troubleshooting", slug, content)
    _update_index()
    return path


def create_pattern(title: str, pattern: str, usage: str,
                   example: str = "", pros: str = "", cons: str = "",
                   tags: list[str] | None = None) -> pathlib.Path:
    """Create and write a pattern doc. Returns the path."""
    content = build_pattern_doc(title, pattern, usage, example, pros, cons, tags)
    slug = _slugify(title)
    path = _write_doc("pattern", slug, content)
    _update_index()
    return path


def create_api(title: str, signature: str, usage: str,
               notes: str = "", tags: list[str] | None = None) -> pathlib.Path:
    """Create and write an API doc. Returns the path."""
    content = build_api_doc(title, signature, usage, notes, tags)
    slug = _slugify(title)
    path = _write_doc("api", slug, content)
    _update_index()
    return path


def create_pending(title: str, description: str, context: str = "",
                   next_steps: str = "", priority: str = "normal",
                   tags: list[str] | None = None,
                   related_experiments: list[str] | None = None,
                   related_stories: list[str] | None = None) -> pathlib.Path:
    """Create and write a pending doc. Returns the path."""
    content = build_pending_doc(title, description, context, next_steps,
                                priority, tags, related_experiments, related_stories)
    slug = _slugify(title)
    path = _write_doc("pending", slug, content)
    _update_index()
    return path


# --- Recall functions ---

def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown content."""
    match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            val = val.strip().strip('"').strip("'")
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
            fm[key.strip()] = val
    return fm


def recall_by_tag(tag: str) -> list[dict]:
    """Find all docs matching a tag."""
    results = []
    root = _get_code_docs_root()
    for doc_type, info in DOC_TYPES.items():
        type_dir = root / info["dir"]
        if not type_dir.exists():
            continue
        for doc in type_dir.glob(f"{info['prefix']}-*.md"):
            content = doc.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)
            doc_tags = fm.get("tags", [])
            if isinstance(doc_tags, str):
                doc_tags = [doc_tags]
            if tag in doc_tags:
                results.append({
                    "path": str(doc),
                    "type": doc_type,
                    "id": fm.get("id", doc.stem),
                    "title": fm.get("title", ""),
                    "tags": doc_tags,
                    "date": fm.get("date", ""),
                })
    return results


def recall_by_experiment(experiment_id: str) -> list[dict]:
    """Find all docs related to a specific experiment."""
    results = []
    root = _get_code_docs_root()
    for doc_type, info in DOC_TYPES.items():
        type_dir = root / info["dir"]
        if not type_dir.exists():
            continue
        for doc in type_dir.glob(f"{info['prefix']}-*.md"):
            content = doc.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)
            related = fm.get("related_experiments", [])
            if isinstance(related, str):
                related = [related]
            if experiment_id in related:
                results.append({
                    "path": str(doc),
                    "type": doc_type,
                    "id": fm.get("id", doc.stem),
                    "title": fm.get("title", ""),
                    "tags": fm.get("tags", []),
                    "date": fm.get("date", ""),
                })
    return results


def recall_by_type(doc_type: str) -> list[dict]:
    """List all docs of a specific type."""
    if doc_type not in DOC_TYPES:
        return []
    info = DOC_TYPES[doc_type]
    root = _get_code_docs_root()
    type_dir = root / info["dir"]
    if not type_dir.exists():
        return []
    results = []
    for doc in type_dir.glob(f"{info['prefix']}-*.md"):
        content = doc.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        results.append({
            "path": str(doc),
            "type": doc_type,
            "id": fm.get("id", doc.stem),
            "title": fm.get("title", ""),
            "tags": fm.get("tags", []),
            "date": fm.get("date", ""),
        })
    return results


def recall_all() -> dict[str, list[dict]]:
    """Get all code docs grouped by type."""
    return {dt: recall_by_type(dt) for dt in DOC_TYPES}


# --- Auto-loading functions ---

def load_context_for_task(task_description: str, task_type: str = "") -> str:
    """Load relevant code-docs for a given task description.

    Scans task description for keywords, finds matching docs,
    and returns formatted context string for LLM consumption.
    """
    results = []
    seen_ids = set()

    # Extract keywords from task description
    keywords = _extract_keywords(task_description)

    # Search by keywords (tags)
    for keyword in keywords:
        docs = recall_by_tag(keyword)
        for doc in docs:
            if doc["id"] not in seen_ids:
                seen_ids.add(doc["id"])
                results.append(doc)

    # Search by experiment references
    exp_matches = re.findall(r"E-\d+", task_description)
    for exp_id in exp_matches:
        docs = recall_by_experiment(exp_id)
        for doc in docs:
            if doc["id"] not in seen_ids:
                seen_ids.add(doc["id"])
                results.append(doc)

    # Always include pending items (they need attention)
    pending = recall_by_type("pending")
    for doc in pending:
        if doc["id"] not in seen_ids:
            seen_ids.add(doc["id"])
            results.append(doc)

    if not results:
        return ""

    # Format for LLM consumption
    return _format_context(results)


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text for doc matching."""
    # Common code/methodology keywords
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "being", "have", "has", "had", "do", "does", "did", "will",
                  "would", "could", "should", "may", "might", "can", "shall",
                  "i", "you", "he", "she", "it", "we", "they", "me", "him",
                  "her", "us", "them", "my", "your", "his", "its", "our",
                  "their", "this", "that", "these", "those", "bir", "ve",
                  "ile", "için", "olan", "bu", "da", "de", "mi", "mı",
                  "mu", "mü", "ne", "nasıl", "neden", "niçin", "kadar",
                  "daha", "en", "çok", "az", "var", "yok", "olan"}

    words = re.findall(r"[a-zA-ZğüşıöçĞÜŞİÖÇ]{3,}", text.lower())
    keywords = [w for w in words if w not in stop_words]

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    return unique[:10]  # Max 10 keywords


def _format_context(docs: list[dict]) -> str:
    """Format docs list into context string for LLM."""
    lines = ["## İlgili Code Docs", ""]

    # Group by type
    by_type = {}
    for doc in docs:
        t = doc.get("type", "unknown")
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(doc)

    type_names = {
        "decision": "Kararlar",
        "pattern": "Kalıplar",
        "learning": "Dersler",
        "api": "API Kullanımları",
        "troubleshooting": "Sorun Giderme",
        "pending": "Bekleyen İşler",
    }

    for doc_type, type_docs in by_type.items():
        lines.append(f"### {type_names.get(doc_type, doc_type)}")
        for doc in type_docs:
            title = doc.get("title", "Başlık yok")
            doc_id = doc.get("id", "")
            path = doc.get("path", "")
            # Make path relative to project root
            if "docs/code-docs/" in path:
                path = path.split("docs/code-docs/")[-1]
            lines.append(f"- **{doc_id}**: {title} (`{path}`)")
        lines.append("")

    return "\n".join(lines)


def load_recent_docs(n: int = 5) -> str:
    """Load N most recent code-docs (by date in frontmatter)."""
    all_docs = []
    root = _get_code_docs_root()

    for doc_type, info in DOC_TYPES.items():
        type_dir = root / info["dir"]
        if not type_dir.exists():
            continue
        for doc in type_dir.glob(f"{info['prefix']}-*.md"):
            content = doc.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)
            date_str = fm.get("date", "0000-00-00")
            all_docs.append({
                "path": str(doc),
                "type": doc_type,
                "id": fm.get("id", doc.stem),
                "title": fm.get("title", ""),
                "date": date_str,
            })

    # Sort by date descending
    all_docs.sort(key=lambda x: x.get("date", ""), reverse=True)

    return _format_context(all_docs[:n])


def load_pending_docs() -> str:
    """Load all pending docs that need attention."""
    pending = recall_by_type("pending")
    if not pending:
        return ""
    return _format_context(pending)

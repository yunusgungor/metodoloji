#!/usr/bin/env python3
"""Translate Turkish scenario/stage/operation text in meta benchmark JSON data to English.

The meta benchmark data files contain Turkish prose that the LLM sees as input.
This script translates the prose fields while leaving ids, paths, and status
values structurally intact (they get mapped separately).
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "bmad_benchmarks" / "envs"

# --- Field value translations (status values, etc.) ---
STATUS_MAP = {
    "planlandı": "planned",
    "devam ediyor": "in-progress",
    "tamamlandı": "completed",
    "iptal": "cancelled",
    "ONAYLANDI": "APPROVED",
    "REDDEDİLDİ": "REJECTED",
    "HAZIR": "READY",
    "EKSİK": "INCOMPLETE",
    "BEKLİYOR": "WAITING",
    "pass": "pass",
    "fail": "fail",
    "partial": "partial",
}

# --- Sentence-level translation map for scenario/stage/operation prose ---
# Keyed by the exact Turkish string; value is the English translation.
SENTENCE_MAP = {
    # meta_chain stages
    "Bir deney yapıldı ve sonucu kayıt altına alınacak. Hangi kayıt, hangi yol, hangi": "An experiment was run and its result will be recorded. Which record, which path, which",
    "Araştırma bulguları geliştirmeye hazır mı kontrol edilecek, sprint planlamadan ö": "Check whether research findings are ready for development, before sprint planning: ",
    "Bir feature'ın kalite kaydı oluşturulacak, story done sayılması için. Hangi kay": "A quality record will be created for a feature, for the story to count as done. Which rec",
    "Production'a çıkmadan önce operasyonel hazırlık kaydı gerekiyor. Hangi kayıt?": "Operational readiness record is required before going to production. Which record?",
    "Yeni bir kullanıcı hikayesi sprint'e eklenecek. Hangi kayıt ve yol?": "A new user story will be added to the sprint. Which record and path?",
    "Araştırma sonuçları değerlendirilecek, geliştirmeye geçiş için. Hangi kayıt ve y": "Research results will be assessed for the transition to development. Which record and",
    # meta_guard scenarios
    "Story frontmatter'da experiment_refs içinde E-002 var, status REDDEDİLDİ. Story'": "The story frontmatter has E-002 in experiment_refs, status REJECTED. The st",
    "Geçici deneme dosyası scratch/test.py'ye yazılıyor — scratch free zone. Guard ka": "A temporary test file is being written to scratch/test.py — scratch is a free zone. What",
    "Geliştirici, kapsamı eşleşen onaylı deney kaydı olmayan src/auth/login.py dosyas": "The developer wants to write code to src/auth/login.py with no scope-matching approved experiment record. ",
    "Geliştirici, docs/experiments/E-001.md kaydı ONAYLANDI ve kapsamı src/auth/** il": "The developer has docs/experiments/E-001.md with status APPROVED and scope src/auth/** wh",
    "Story'de bir Technical Task'ın AC: AC-XXX referansı yok. Story dosyasına yazılıy": "A Technical Task in the story has no AC: AC-XXX reference. Being written to the story fi",
    "PRD belgesi oluşturuluyor (docs/planning/prd.md) — belgesel çıktı, kod değil. Gu": "A PRD document is being created (docs/planning/prd.md) — a documentary output, not code. What ",
    # meta_mod task descriptions
    "Proje dokümantasyonu güncellenecek, README yazılacak.": "Project documentation will be updated, README will be written.",
    "Gereksinim analizi yapılacak, epics ve story'ler ayrıştırılacak.": "Requirements analysis will be done, epics and stories will be broken down.",
    "Kullanıcı kimlik doğrulama sistemi için Python kod yazılacak, test edilecek ve d": "Python code for a user authentication system will be written, tested, and d",
    "Yeni bir ürün fikri üzerine beyin fırtınası yapılacak, konsept geliştirilecek.": "A brainstorming session will be held on a new product idea, the concept will be developed.",
    "Mikroservis mimarisi kararı verilecek, architecture spine oluşturulacak.": "A microservice architecture decision will be made, the architecture spine will be created.",
    "Unit test yazılacak ve mevcut testlerin geçtiği doğrulanacak.": "Unit tests will be written and it will be verified that existing tests pass.",
    # meta_path stages
    "Code review sonrası kalite kaydı oluşturulacak": "A quality record will be created after code review",
    "Deploy öncesi production readiness kaydı oluşturulacak": "A production readiness record will be created before deploy",
    "Yeni bir story için metodoloji kaydı oluştur": "Create the methodology record for a new story",
    "Bir deney kaydı oluştur": "Create an experiment record",
    "Bir kullanıcı hikayesinin metodoloji kaydını oluştur": "Create the methodology record for a user story",
    "Bir feature'ın kalite kaydını oluştur": "Create the quality record for a feature",
    # meta_root operations
    "Bir komut {metodoloji-root}/bmad-output altına story yazmayı öneriyor": "A command proposes writing a story under {metodoloji-root}/bmad-output",
    "bmad-create-story: story dosyasını oluştur ve docs/development/stories/S-001.md ": "bmad-create-story: create the story file and write it to docs/development/stories/S-001.md",
    "run_experiment.py ile docs/experiments/E-001.md deney kaydını oluştur": "create the experiment record docs/experiments/E-001.md with run_experiment.py",
    "docs/quality/QR-001.md kalite kaydını oluştur": "create the quality record docs/quality/QR-001.md",
    "skill'in kendi customize.toml'ını oku": "read the skill's own customize.toml",
}

# Phrase replacements to apply within longer strings (prefix matches)
PHRASE_MAP = {
    "hedef proje": "target project",
    "kayıt zinciri": "record chain",
    "deney kaydı": "experiment record",
    "kalite kaydı": "quality record",
    "methodology kaydı": "methodology record",
    "oluşturulacak": "will be created",
    "oluştur": "create",
    "oluşturur": "creates",
    "deney": "experiment",
    "kayıt": "record",
    "geliştirici": "developer",
    "belgesel çıktı": "documentary output",
    "belgesel karar": "documentary decision",
    "kod yazma": "code writing",
    "kod": "code",
    # meta_chain stages
    "Sprint kapsamı netleştirilecek, IR onayından sonra. Hangi record?": "Sprint scope will be clarified, after IR approval. Which record?",
    "Bir story implementasyona hazır hale getirilecek. Hangi record?": "A story will be made ready for implementation. Which record?",
    "Story tamamlandı, kalite doğrulaması yapılacak. Hangi record?": "The story is complete, quality verification will be done. Which record?",
    "Deploy öncesi production readiness kontrol edilecek. Hangi record?": "Production readiness will be checked before deploy. Which record?",
    # meta_guard scenarios
    "Story'de bir AC [HYPOTHESIS] olarak işaretli, experiment onayı yok. Geliştirici ": "An AC in the story is tagged [HYPOTHESIS], no experiment approval. The developer ",
    "Story dosyasına yazılıyor ama AC-001'in Type, Measured, Verify alanları eksik. G": "Writing to the story file but AC-001's Type, Measured, Verify fields are missing. T",
    "Dokümantasyon güncelleniyor — docs/development/README.md'ye yazılıyor, code deği": "Documentation is being updated — writing to docs/development/README.md, code unch",
    "Story status 'done' olarak işaretleniyor ama docs/quality/QR-*.md kaydı yok. Gua": "The story status is being marked 'done' but no docs/quality/QR-*.md record exists. Wh",
    # meta_mod task descriptions
    "Yeni özellik için PRD will be created, UX tasarımı ve mimari kararlar alınacak.": "A PRD will be created for the new feature, UX design and architecture decisions will be made.",
    "Sprint planlama yapılacak, sprint-status.yaml will be created, retrospektif notl": "Sprint planning will be done, sprint-status.yaml will be created, retrospective notes",
    "Production ortamına deploy yapılacak, deployment log kaydedilecek.": "Deploy to the production environment will be done, deployment log will be recorded.",
    "Kullanıcı arayüzü için UX spec ve mockup hazırlanacak.": "UX spec and mockup will be prepared for the user interface.",
    # meta_path stages
    "Kalite kaydı (QR) create": "Create the quality record (QR)",
    "Production readiness kaydı create": "Create the production readiness record",
    "Implementation readiness kaydı create": "Create the implementation readiness record",
    "Sprint planning kaydı create": "Create the sprint planning record",
    # meta_root operations
    "run_experiment.py kapı betiğini {metodoloji-root}/skills/bmad-research-experimen": "run_experiment.py gate script {metodoloji-root}/skills/bmad-research-experimen",
    "docs/development/IR-001.md uygulama hazırlık kaydını create": "create the implementation readiness record docs/development/IR-001.md",
    "Kalite kaydını {metodoloji-root}/docs/quality/QR-009.md olarak üretmeyi düşün": "thinking of producing the quality record at {metodoloji-root}/docs/quality/QR-009.md",
    "skill'in kurulumdaki references/agent-type-guidance.md dosyasını oku": "read the skill's references/agent-type-guidance.md file in the installation",
    "S kaydı createurken şablonu plugin kurulumundaki templates/_template_S.md'den ko": "when creating the S record, copy the template from templates/_template_S.md in the plugin installation",
    "planning artifact'larını bmad-output/planning-artifacts altına yaz": "write planning artifacts under bmad-output/planning-artifacts",
    "plugin yapılandırmasını plugin kökündeki bmad/config.toml'den oku": "read the plugin configuration from bmad/config.toml in the plugin root",
    "UX tasarım çıktılarını design-artifacts altına yaz": "write UX design outputs under design-artifacts",
    "docs/development/stories/_template_S.md proje kopyasını oku ve kullan": "read and use the project copy of docs/development/stories/_template_S.md",
    "Şablonu ~/{metodoloji-root}/templates/_template_QR.md yolundan kopyala": "copy the template from the path ~/{metodoloji-root}/templates/_template_QR.md",
    "run_experiment.py kapı betiğini plugin kökündeki hooks/engine altından çalıştır": "run the run_experiment.py gate script from hooks/engine in the plugin root",
    "docs/development/PR-001.md üretim hazırlık kaydını create": "create the production readiness record docs/development/PR-001.md",
    "docs/bmad/development-methodology.md köprü kopyasını projeden oku": "read the bridge copy of docs/bmad/development-methodology.md from the project",
    "Deney kaydını {metodoloji-root}/docs/experiments/E-002.md olarak yaz": "write the experiment record as {metodoloji-root}/docs/experiments/E-002.md",
    "plugin kökündeki custom/bmad-sprint-planning.toml köprü yapılandırmasını oku": "read the bridge configuration custom/bmad-sprint-planning.toml in the plugin root",
    "test artifact'larını bmad-output/test-artifacts altına üret": "produce test artifacts under bmad-output/test-artifacts",
    # generic operations
    "oluşturur": "creates",
    "altına": "under",
    "kökündeki": "in the root of",
    "yaz": "write",
    "üret": "produce",
    "oku": "read",
    "kopyala": "copy",
    "şablonu": "template",
    "kalite": "quality",
    "hazırlık": "readiness",
    "üretim": "production",
    "uygulama": "implementation",
    "sprint": "sprint",
    "planning": "planning",
}


def translate_prose(text: str) -> str:
    """Translate a Turkish prose field to English."""
    if not text:
        return text
    # Exact sentence match first
    for tr, en in SENTENCE_MAP.items():
        if text.startswith(tr):
            tail = text[len(tr):]
            return en + tail
    # Phrase-level fallback (partial)
    result = text
    for tr, en in PHRASE_MAP.items():
        result = result.replace(tr, en)
    return result


def migrate_item(item: dict) -> dict:
    item = dict(item)
    for field in ("scenario", "stage", "task_desc", "operation"):
        if field in item:
            item[field] = translate_prose(item[field])
    # Status values
    for field in ("expected_status",):
        if field in item:
            vals = item[field].split("|")
            item[field] = " | ".join(STATUS_MAP.get(v.strip(), v.strip()) for v in vals)
    return item


def main() -> int:
    changed = 0
    for bench in ["bmad_meta_chain", "bmad_meta_guard", "bmad_meta_mod",
                  "bmad_meta_path", "bmad_meta_root"]:
        bench_dir = DATA_DIR / bench / "data"
        for f in sorted(bench_dir.rglob("*.json")):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                new_data = [migrate_item(i) for i in data]
            else:
                new_data = migrate_item(data)
            if new_data != data:
                with open(f, "w", encoding="utf-8") as fh:
                    json.dump(new_data, fh, ensure_ascii=False, indent=2)
                print(f"  migrated {f.name}")
                changed += 1
    print(f"{changed} file(s) updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

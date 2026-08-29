# OpenHands Metodoloji Plugin — Kapsamlı Kullanım Kılavuzu

> **Versiyon:** 1.0.0 | **Yazar:** yunusgungor | **Lisans:** MIT
>
> Bu belge, `metodoloji` OpenHands plugin'inin tüm yönleriyle, eksiksiz ve
> detaylı kullanım kılavuzudur.

---

## İçindekiler

1. [Genel Bakış](#1-genel-bakış)
2. [Mimari Yapısı](#2-mimari-yapısı)
3. [Kurulum](#3-kurulum)
4. [İlk Yapılandırma](#4-ilk-yapılandırma)
5. [Kayıt Zinciri (E → IR → SP → S → QR → PR)](#5-kayıt-zinciri)
6. [Hook Motoru ve Mekanik Kapılar](#6-hook-motoru-ve-mekanik-kapılar)
7. [Skill Köprüsü ve TOML Özelleştirme](#7-skill-köprüsü-ve-toml-özelleştirme)
8. [Komutlar (Commands)](#8-komutlar)
9. [Şablonlar (Templates)](#9-şablonlar)
10. [Serbest Bölge ve Kısıt Alanları](#10-serbest-bölge-ve-kısıt-alanları)
11. [Guvenlik (Gate Key ve HMAC)](#11-güvenlik)
12. [Denetim ve Sağlık Kontrolü](#12-denetim-ve-sağlık-kontrolü)
13. [Sorun Giderme (Troubleshooting)](#13-sorun-giderme)
14. [Sıkça Sorulan Sorular](#14-sıkça-sorulan-sorular)
15. [Sözlük](#15-sözlük)

---

## 1. Genel Bakış

### Plugin Ne Yapar?

`metodoloji`, **BMAD (Build Methodology for Agent-Driven development)** metodolojisinin
OpenHands SDK plugin karşılığıdır. 124 skill + 119 köprü TOML (33 KÖPRÜ aktif) +
mekanik kapılar + kayıt zinciri ile donatılmıştır.

Temel işlevleri:

| Parça | İşlev |
|-------|-------|
| `skills/` | 124 BMAD skill'i (native gövde) + `metodoloji-manifesto` (çekirdek sözleşme) |
| `custom/` | 119 köprü TOML (33 KÖPRÜ ile aktif: `activation_steps_append`/`principles` → native çıktıları metodoloji kaydına bağlar) + `config.toml` (soft/hard) |
| `hooks/` | PreToolUse / PostToolUse / Stop / SessionStart hook'ları; modüler motor yapısı |
| `hooks/engine/` | Python motoru: `main.py` (giriş), `modules/` (guard, audit, stop, utils, config) |
| `bmad/` | Modül verisi (bmm, cis, gds, wds, tea, core, bmb) |
| `templates/` | IR/SP/QR/PR/S/E/README/tech-debt kayıt şablonları |
| `commands/` | `/metodoloji:init`, `/metodoloji:kapi-kur`, `/metodoloji:dogrula`, `/metodoloji:denetim` |

### Temel Prensip

Plugin, **deney onayı olmadan kod yazılmasını mekanik olarak engeller**.
Kod yazmak için önce bir deney (E-NNN) kaydı oluşturmanız, hipotezi test etmeniz
ve kapıdan ONAYLANDI almanız gerekir. Bu, "düşünmeden kod yazma" alışkanlığını
mekanik olarak kırar.

### Araştırma Modları

| Mod | Tür | Kayıt Yeri | Kullanım |
|-----|-----|------------|----------|
| **Mod A** | Sayısal/Empirik | `docs/experiments/` | Kod üretiminin tek meşru yolu — mekanik kapı |
| **Mod B** | Nitel | `docs/research/` | Literatür taraması, röportaj, vaka analizi |
| **Mod C** | Tasarım | `docs/design/` | UX/mimari tasarımlar |
| **Mod D** | Bağlamsal | `docs/research/` | Pazar araştırması, rekabet analizi |

---

## 2. Mimari Yapısı

### Dizin Yapısı

```
metodoloji/
├── .plugin/
│   ├── plugin.json              # Plugin tanımı (name, version, repository)
│   └── marketplace.json         # Marketplace listesi
├── hooks/
│   ├── hooks.json               # OpenHands hook tanımları
│   ├── engine/                  # Python motoru
│   │   ├── main.py              # Ana giriş noktası
│   │   ├── memlog.py            # Calışma hafızası loglama aracı
│   │   ├── resolve_customization.py  # TOML deep_merge köprü çözücü
│   │   └── modules/
│   │       ├── __init__.py      # Modül ihracatları
│   │       ├── config.py        # Sabit yapılandırma (yollar, eşikler)
│   │       ├── utils.py         # Yardımcı fonksiyonlar (norm_path, is_free, is_code_target)
│   │       ├── archive.py       # Arşiv işleme (tar/zip — bomb koruması)
│   │       ├── bash_targets.py  # Bash komut hedef tespiti
│   │       ├── guard.py         # PreToolUse mantığı (kod yazımı engelleme)
│   │       ├── audit.py         # PostToolUse denetim izi
│   │       └── stop.py          # Stop mantığı (oturum kapanışı engelleme)
│   └── scripts/
│       ├── bootstrap.sh         # SessionStart: gate-key + eksik dizinler + bağlam
│       └── hook-entry.sh        # Tek çözümleme noktası: mod-seçim + Python'a yönlendirme
├── skills/                      # 124+ BMAD skill dizinleri
├── custom/                      # 74 köprü TOML + config.toml
├── bmad/                        # Modül verisi (bmm, cis, gds, wds, tea, core, bmb)
├── templates/                   # Kayıt şablonları
├── commands/                    # Komut tanımları + check-plugin.sh
├── scripts/                     # Yardımcı betikler
└── docs/                        # Dokümantasyon
```

### Hook Akış Diyagramı

```
OpenHands Runtime
       │
       ├── SessionStart ──→ bootstrap.sh
       │    │                    │
       │    │              Gate key oluştur (yoksa)
       │    │              Eksik dizinleri oluştur
       │    │              Bağlam enjekte et (kayıt zinciri hatırlatması)
       │    │
       ├── PreToolUse ────→ hook-entry.sh guard
       │    │                    │
       │    │              main.py guard() → JSON stdin oku
       │    │                    │
       │    │              Hedef dosyaları tespit et (file_editor/terminal)
       │    │                    │
       │    │              Her hedef için:
       │    │                ├── Serbest bölge mi? → allow
       │    │                ├── Kod hedefi mi? → allow (değilse)
       │    │                └── Onaylı deney var mı?
       │    │                      ├── Evet → allow
       │    │                      └── Hayır → DENY
       │    │
       ├── PostToolUse ───→ hook-entry.sh audit (async)
       │    │                    │
       │    │              main.py audit() → JSON audit trail yaz
       │    │              Metodoloji uyum uyarıları (non-blocking)
       │    │              .metodoloji/logs/hook-audit.log'a append
       │    │
       └── Stop ──────────→ hook-entry.sh stop
                │                    │
                │              main.py stop()
                │                ├── Tamamlanmamış story var mı? → DENY
                │                └── Onaysız kod değişikliği var mı? → DENY
```

### Root Çözümleme Kuralları

| Placeholder | Değer |
|-------------|-------|
| `{project-root}` | Hedef proje kökü (`$OPENHANDS_PROJECT_DIR`) |
| `{metodoloji-root}` | Plugin kurulum kökü (`~/.openhands/plugins/installed/metodoloji`) |
| `{skill-root}` | Skill'in plugin içindeki konumu |

**Çıktı kuralı:** Metodoloji çıktıları (story, deney, planning, test artifact'ları, `bmad-output/`) her zaman `{project-root}` üzerinde oluşturulur — `{metodoloji-root}` üzerinde değil.

---

## 3. Kurulum

### 3.1. Python'dan Yükleme (SDK)

```python
from openhands.sdk.plugin import Plugin

# GitHub'dan
p = Plugin.load("github:yunusgungor/metodoloji", repo_path="openhands/metodoloji")

# Yerel depodan
p = Plugin.load("/path/to/openhands/metodoloji")
```

### 3.2. Manuel Kurulum

```bash
# 1. Depoyu klonlayın
git clone https://github.com/yunusgungor/openhands-metodoloji.git
cd openhands-metodoloji

# 2. Plugin dizin yapısını kontrol edin
ls -la .plugin/plugin.json    # Plugin tanımı
ls -la hooks/hooks.json       # Hook tanımları
ls -la hooks/engine/main.py   # Motor giriş noktası

# 3. Python 3.11+ gerekli (tomllib için)
python3 --version  # >= 3.11 olmalı
```

### 3.3. Ön Koşullar

| Gereksinim | Minimum | Not |
|-----------|---------|-----|
| Python | 3.11+ | `tomllib` stdlib modülü için |
| OpenHands | Son sürüm | Plugin API desteği |
| Git | 2.x | Versiyon kontrolü |

---

## 4. İlk Yapılandırma

### 4.1. Adım Adım İlk Kurulum

İlk oturumunuzda şu sırayla hareket edin:

#### Adım 1: Plugin'i Başlatın

OpenHands oturumunuzda plugin otomatik olarak yüklenir. `SessionStart` hook'u
şunları yapar:

1. Plugin'i workspace'e kopyalamaz — tek kök kurulum köküdür
2. `~/.bmad/gate-key` yoksa oluşturur (0600 izinli)
3. Eksik dizinleri oluşturur (`docs/experiments/`, `.metodoloji/logs/`)
4. Bağlam enjekte eder: "METODOLOJI aktif — Kayıt zinciri: E → IR → SP → S → QR → PR"

#### Adım 2: Kayıt İskeletini Kurun

```
/metodoloji:init
```

Bu komut şunları yapar:

| İşlem | Detay |
|-------|-------|
| Dizin oluştur | `docs/experiments/`, `docs/development/stories/`, `docs/research/`, `docs/design/`, `docs/bmad/`, `scratch/` |
| Şablon kopyala | E, IR, SP, S, QR, PR şablonları ilgili dizinlere |
| Uyarı | Kapı anahtarı kurulu değilse `/metodoloji:kapi-kur` çalıştırmanızı söyler |

#### Adım 3: Kapı Anahtarını Kurun

```
/metodoloji:kapi-kur
```

Bu komut `~/.bmad/gate-key` dosyasını oluşturur. Bu dosya:
- **Repo dışındadır** (commit edilmez)
- **0600 izinli** (yalnızca sahibi okuyabilir)
- **HMAC doğrulaması** için kullanılır
- **Makine-yereldir** (her geliştirici kendi anahtarını üretir)

```bash
# Manuel kurulum (eğer /metodoloji:kapi-kur çalışmazsa):
python3 skills/bmad-research-experiment/scripts/run_experiment.py --init-secret
```

#### Adım 4: Sağlık Kontrolünü Çalıştırın

```
/metodoloji:denetim
```

veya doğrudan:

```bash
sh commands/check-plugin.sh
```

Bu, §0'dan §6'ya kadar tüm kontrolleri yapar:
- §0: Kapı anahtarı kurulu mu?
- §1: Hook motoru çalışıyor mu?
- §2: Manifesto tüm yüzeylere kablolanmış mı?
- §2b: Köprü talimatları runtime'da görünür mü?
- §3: Onaylı deney envanteri
- §4: Belgesel kayıt eksiksizliği
- §5: Engine drift denetimi
- §5b: Hard gate enforcement modu
- §6: Geliştirme kayıtları format kontrolü

---

## 5. Kayıt Zinciri (E → IR → SP → S → QR → PR)

Kayıt zinciri, metodolojinin omurgasıdır. Her halka bir sonrakine bağlıdır:

```
E (Deney) → IR (Hazırlık) → SP (Sprint) → S (Story) → QR (Kalite) → PR (Üretim)
   Mod A       Kapı 1         Kapı 2        Uygulama      Kapı 3        Kapı 4
```

### 5.1. E — Deney Kaydı (Mod A, Mekanik Kapı)

Kod üretiminin **tek meşru yolu**. Deney olmadan kod yazmak `guard` tarafından
mekanik olarak engellenir.

**Kayıt yeri:** `docs/experiments/E-NNN.md`

**Adımlar:**

1. **Deney dosyasını oluşturun:**
   ```
   templates/_template_E.md → docs/experiments/E-001.md
   ```

2. **Gerekli alanları doldurun:**

   ```markdown
   ## Deney: E-001 — Veritabanı indeks optimizasyonu
   - **Tarih:** 20.08.2026
   - **Durum:** planlandı
   - **Teori:** B+ ağaç indeksleri büyük tablolarda arama performansını O(n)→O(log n) düşürür
   - **Hipotez:** H-001: "sorgu süresi 200ms'den 20ms'ye inecek"
   - **Ölçüm metrikleri:** query_time_ms <= 20
   - **Kod kapsamı:** src/db/**/*.py, lib/engine/*.py
   ```

3. **Kapıyı çalıştırın:**

   ```bash
   python3 skills/bmad-research-experiment/scripts/run_experiment.py \
     --record docs/experiments/E-001.md \
     --run "python scripts/bench/bench_query.py"
   ```

4. **Sonuç:**
   - `ONAYLANDI` → Guard bu kapsam açar, kod yazabilirsiniz
   - `REDDEDİLDİ` → Hipotezi revize edin, yeniden ölçün

5. **Kod öncesi doğrulayın:**

   ```bash
   python3 skills/bmad-research-experiment/scripts/run_experiment.py \
     --verify --record docs/experiments/E-001.md
   ```

**Alan Açıklamaları:**

| Alan | Zorunlu | Açıklama |
|------|---------|----------|
| `Tarih` | Evet | GG.AA.YYYY formatında |
| `Durum` | Evet | planlandı / ONAYLANDI / REDDEDİLDİ |
| `Teori` | Evet | Hangi teoriden/çerçeveden geldiği |
| `Hipotez` | Evet | H-NNN: "metrik >= eşik" formatında |
| `Ölçüm metrikleri` | Evet | Metrik adı + eşik, sayısal |
| `Kod kapsamı` | Evet | Glob desenleri, virgül/boşluk ayrık |
| `Ham sonuçlar` | Kapı yazar | Ölçüm çıktısı |
| `Belirsizlik` | Kapı yazar | örneklem küçük / yok / n bilinmiyor |
| `Metrik` | Kapı yazar | uyumlu / UYUMSUZ |
| `Karar` | Kapı yazar | ONAYLANDI / REDDEDİLDİ |
| `Kapı kanıtı` | Kapı yazar | GATE-OK-... token |
| `Sonraki adım` | Kapı yazar | Kod'a geç / Teori'ye dön |

**Dry-run (Karar yazmadan önizleme):**

```bash
python3 skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-001.md \
  --run "python scripts/bench/bench_query.py" \
  --dry-run
```

### 5.2. IR — Implementation Readiness (Kapı 1)

Araştırma bulgularının geliştirme için hazır olup olmadığını kontrol eder.

**Kayıt yeri:** `docs/development/IR-NNN.md`

**Durum değerleri:** `HAZIR` | `EKSİK`

**Kontrol listesi:**
- En az bir onaylı araştırma kaydı var (E/R/D/C-id)
- PRD veya story tanımlı
- UX speci hazır (gerekiyorsa)
- Mimari plan hazır (gerekiyorsa)
- Başarı kriterleri net ve ölçülebilir
- Teknik bağımlılıklar belirlendi
- Risk değerlendirmesi yapıldı
- Eksikler için plan var (varsa)

**Not:** Eksik varsa sprint başlatılmaz; önce araştırma kanadına dönülür.

### 5.3. SP — Sprint Planlama (Kapı 2)

Sprint kapsamının net, ölçülebilir ve gerçekçi olduğunu garanti eder.

**Kayıt yeri:** `docs/development/SP-NNN.md`

**Durum değerleri:** `planlandı` | `devam ediyor` | `tamamlandı` | `iptal`

**Alanlar:**
- Sprint hedefi (tek cümle)
- Story listesi (S-id + öncelik + story points)
- Kapasite (takım velocity'si ile karşılaştırma)
- Teknik borç değerlendirmesi
- Blokerler ve çözüm planları
- Bağımlılıklar

**Kontrol listesi:**
- Sprint hedefi net ve tek cümlede ifade edilebiliyor
- Her story için S-id kaydı var
- Story points atanmış ve gerçekçi
- Sprint kapasitesi takım velocity'sine uygun
- Teknik borç değerlendirilmiş ve time-box ayrılmış
- Blokerler tanımlanmış ve çözüm planı var

### 5.4. S — Story Kaydı

Sprint planlama sırasında oluşturulur ve implementasyon boyunca takip edilir.

**Kayıt yeri:** `docs/development/stories/S-NNN.md`

**Durum değerleri:** `backlog` | `sprint` | `in-progress` | `review` | `done` | `blocked`

**Zorunlu bölümler:**

1. **Frontmatter:**
   ```yaml
   ---
   experiment_refs:
     - id: E-001
       scope: "src/db/**"
       status: ONAYLANDI
   ---
   ```

2. **Acceptance Criteria:** Her AC için zorunlu alanlar:
   - `[AC-NNN]` tanımlayıcısı
   - `Experiment:` alanı (E-NNN veya `—` ile birlikte `[HYPOTHESIS]` etiketi)
   - `Type:` alanı (`agent-verifiable` | `user-evaluable` | `hybrid`)
   - `Measured:` alanı (`true` | `false`)
   - `Verify:` alanı (doğrulama yöntemi)

3. **Technical Tasks:** Her görevin bir AC referansı olmalı (`AC: AC-NNN`)

4. **Definition of Done:** Her öğe `DoD-NNN` tanımlayıcısı ve `Verify:` alanı içermeli

**Guard doğrulamaları (story dosyası yazılırken):**
- `experiment_refs` → referanslanan deney kayıtları var mı?
- AC metadata → tüm alanlar dolu mu?
- Task↔AC eşleşme → her görev bir AC'ye bağlı mı?
- DoD yapısı → tanımlayıcılar mevcut mu?
- Metodoloji zinciri → story durumuna göre QR/SP kaydı var mı?

**Story oluşturma:**

```bash
# Native story dosyasından metodoloji kaydı oluştur
python3 scripts/create-methodology-record.py --story docs/development/stories/S-001.md
```

### 5.5. QR — Quality Review (Kapı 3)

Kod merge edilmeden önce kalite standartlarını zorlar.

**Kayıt yeri:** `docs/quality/QR-NNN.md`

**Durum değerleri:** `ONAYLANDI` | `REDDEDİLDİ` | `REVİZE`

**Mekanik kontroller (otomatik):**
- Test coverage >= %80
- Tüm testler geçti (unit, integration, e2e)
- Linter ve formatter temiz
- Security scan temiz
- Performance regresyonu yok

**Belgesel kontroller (manual):**
- Code review onayı
- Dokümantasyon güncelliği
- Breaking change migration planı
- Teknik borç kaydı

**QR oluşturma:**

```bash
python3 scripts/create-qr-record.py --story docs/development/stories/S-001.md
```

### 5.6. PR — Production Readiness (Kapı 4)

Production deploy öncesi operasyonel hazırlığı garanti eder.

**Kayıt yeri:** `docs/development/PR-NNN.md`

**Durum değerleri:** `HAZIR` | `BEKLİYOR`

**Ana bölümler:**
- Staging test (deploy, smoke test, integration)
- Rollback planı (tetikleyiciler, adımlar, database rollback)
- Monitoring ve alerting (metrikler, alertler, logging)
- Feature flags (kill switch, gradual rollout)
- Runbook (deploy adımları, troubleshooting)
- Incident response (iletişim, severity, post-mortem)
- Deploy penceresi (zamanlama, freeze period)

**Kontrol listesi:**
- Tüm mekanik kontroller PASS
- Rollback planı hazır ve test edilmiş
- Monitoring ve alerting kurulmuş
- Deploy penceresi belirlenmiş
- Change approval alınmış

---

## 6. Hook Motoru ve Mekanik Kapılar

### 6.1. hooks.json Tanımı

Plugin, OpenHands runtime'da **6 hook noktası** kullanır:

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": "sh .../bootstrap.sh" }] }],
    "PreToolUse": [
      { "matcher": "/file_editor|terminal/", "hooks": [{ "command": "sh .../hook-entry.sh guard" }] },
      { "matcher": "/terminal/", "hooks": [{ "command": "sh .../hook-entry.sh quality" }] },
      { "matcher": "/terminal/", "hooks": [{ "command": "sh .../hook-entry.sh deploy" }] }
    ],
    "PostToolUse": [{ "matcher": "/file_editor|terminal/", "hooks": [{ "command": "sh .../hook-entry.sh audit", "async": true }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "sh .../hook-entry.sh stop" }] }]
  }
}
```

### 6.2. Guard (PreToolUse) — Fail-Closed

**Etki alanı:** `file_editor`, `terminal`, `notebook_editor`

**Davranış:**
- Kod hedefi + serbest bölge dışı → onaylı deney kaydı arar
- Onaylı deney yok → `DENY` (kod yazımı engellenir)
- Story dosyası (`S-NNN.md` veya `N-N-slug.md`) ise → ek validasyonlar:
  - `experiment_refs` → referanslanan deney kayıtları ONAYLANDI mı?
  - AC metadata → tüm alanlar dolu mu?
  - Task↔AC eşleşme → her görev bir AC'ye bağlı mı?
  - DoD yapısı → tanımlayıcılar mevcut mu?
  - Metodoloji zinciri → SP referansı varsa SP kaydı var mı?
- Gate key erişimi tespit edilirse → `DENY` (güvenlik ihlali)

**Kod hedefi sınıflandırması:**

| Kategori | Örnekler | Korunur mu? |
|----------|----------|-------------|
| Kod dosyaları | `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java` | ✅ Evet |
| Konfigürasyon | `Makefile`, `Dockerfile`, `package.json` | ✅ Evet |
| Belge | `.md`, `.txt`, `.rst` | ❌ Hayır (serbest) |
| Veri | `.csv`, `.json`, `.yaml`, `.lock` | ❌ Hayır (serbest) |
| Görsel | `.png`, `.jpg`, `.svg` | ❌ Hayır (serbest) |

### 6.3. Audit (PostToolUse) — Fail-Open

**Etki alanı:** Tüm tool çağrısı

**Davranış:**
- Her çağrıyı `.metodoloji/logs/hook-audit.log`'a JSON formatında yazar
- Story dosyası üzerinde metodoloji uyum uyarıları üretir (non-blocking)

**Audit kaydı yapısı:**
```json
{
  "timestamp": 1692537600.0,
  "tool": "file_editor",
  "input": { "path": "src/main.py", "content": "..." },
  "output_summary": "...",
  "methodology_warnings": ["Story file ...: AC metadata missing"]
}
```

### 6.4. Quality (PreToolUse) — Fail-Closed

**Etki alanı:** `terminal` (yalnızca `git commit` komutları)

**Davranış:**
- Terminal komutu `git commit` içermiyor mu? → `allow` (hızlı çıkış)
- `git commit` ise → zincir kontrolü yapar:
  1. Done story'ler var ama hiç IR kaydı yok mu? → `DENY` (Kapı 1 — hazırlık)
  2. `Status: done` olan story'lerin QR kaydı var mı? → Yoksa `DENY` (Kapı 3 — kalite)
  3. `Status: done` olan story'ler SP referansı içeriyor mu? İçeriyorsa SP kaydı var mı? → Yoksa `DENY` (Kapı 2 — sprint)
- Tüm kontroller geçerse → `allow`

**Kontrol sırası:** IR (proje-seviyesi) → QR (story-seviyesi) → SP (story-seviyesi)

**Örnek engelleme (QR eksik):**
```
DENY: git commit blocked: 1 story(s) marked 'done' lack Quality Record (QR).
Stories: 1-2-user-auth. Create QR with: python3 scripts/create-qr-record.py ...
```

**Örnek engelleme (SP eksik):**
```
DENY: git commit blocked: 1 story(s) reference SP but lack Sprint Planning record.
Stories: 1-2-user-auth. Run bmad-sprint-planning to create SP record.
```

### 6.5. Deploy (PreToolUse) — Fail-Closed

**Etki alanı:** `terminal` (deploy komutları: terraform, kubectl, docker, git push to prod)

**Davranış:**
- Deploy komutu tespit edilmedi → `allow`
- Deploy komutu var → zincir kontrolü yapar:
  1. Done story'ler var ama hiç IR kaydı yok mu? → `DENY` (Kapı 1 — hazırlık)
  2. QR eksik story varsa → `DENY` (Kapı 3 — kalite)
  3. SP eksik story varsa → `DENY` (Kapı 2 — sprint)
  4. PR eksik story varsa → `DENY` (Kapı 4 — üretim)
- Tüm kontroller geçerse → `allow`

**Kontrol sırası:** IR → QR → SP → PR (zincirin tüm halkaları)

**Tanınan deploy komutları:** `terraform apply`, `kubectl apply`, `docker compose up`, `git push origin main/master/production`, `ansible playbook` + `deploy` anahtar kelimesi

### 6.6. Stop (Stop) — Fail-Closed

**Davranış:**
1. Tamamlanmamış story var mı? → `DENY`
2. Onaysız kod değişikliği var mı? → `DENY`
3. Her ikisi de temizse → `allow`

**Stop hook'u şu durumlarda oturumu kapatmayı engeller:**
- `sprint-status.yaml`'da `in-progress` durumunda story varsa
- Proje kökündeki `.py`, `.js`, `.ts` vb. dosyalarda onaylı deney kapsamı dışındaki değişiklikler varsa

### 6.7. hook-entry.sh — Tek Çözümleme Noktası

```
hook-entry.sh guard    → guard modu (fail-closed)
hook-entry.sh quality → quality modu (fail-closed)
hook-entry.sh deploy  → deploy modu (fail-closed)
hook-entry.sh audit   → audit modu (fail-open)
hook-entry.sh stop    → stop modu (fail-closed)
```

- Python çözücü: `python3` → `python` → `py` (sırayla arar)
- Motor eksikse veya Python yoksa:
  - guard/stop → `DENY` + exit 2 (fail-closed)
  - quality/deploy → sessizce geç (fail-open)
  - audit → sessizce geç (fail-open)

### 6.8. Bash Komut Hedef Tespiti

Terminal komutlarında hangi dosyaların değiştirileceğini otomatik tespit eder:

| Komut/Kalıp | Tespit Edilen Hedef |
|-------------|---------------------|
| `> dosya` / `>> dosya` | Yönlendirme hedefi |
| `tee dosya` | Tee çıktısı |
| `sed -i '...' dosya` | Sed hedefi |
| `cp kaynak hedef` / `mv kaynak hedef` | Son argüman |
| `curl -o dosya` | -o hedefi |
| `tar -xf arsiv` | Arsiv içeriği (bomb korumalı) |
| `unzip arsiv` | Arsiv içeriği |
| `git apply yama` | Yama hedefleri |
| `python -c 'open("x","w")'` | open() hedefi |

**Arsiv bomba koruması:**
- Maksimum dosya boyutu: 512 MB
- Maksimum sıkıştırılmış boyut: 64 MB
- Maks üye sayısı: 200.000
- Maks açılmamış boyut: 2 GB

---

## 7. Skill Köprüsü ve TOML Özelleştirme

### 7.1. Üç Katmanlı TOML Merge

Her skill için üç katmanda özelleştirme yapılır (en yüksek öncelikten en düşüğe):

```
1. custom/{skill}.user.toml    → Kişisel (gitignored)
2. custom/{skill}.toml         → Takım/organizasyon (commit edilir)
3. skills/{skill}/customize.toml → Skill varsayılanları
```

**Merge kuralları:**
- **Skaler** (string, int, bool, float): override kazanır
- **Tablolar**: deep merge (recursive)
- **Diziler**: Eğer tüm elemanlar aynı `code` veya `id` alanını taşıyorsa → key'e göre merge; aksi halde → ekleme (append)

### 7.2. Köprü TOML Yapısı

Her köprü TOML'da `activation_steps_append` (workflow) veya `principles` (agent)
alanında KÖPRÜ talimatı bulunur. 33 skill'de KÖPRÜ aktiftir:

**Üretici KÖPRÜ (kayıt oluşturan — 17 skill):**
```toml
# custom/bmad-dev-story.toml
[workflow]
activation_steps_append = [
  "KÖPRÜ: Implementasyon bittikten sonra docs/development/stories/S-<sira>.md kaydini guncelle...",
  "KÖPRÜ #3 (QR): QR kaydi olustur: docs/quality/QR-<sira>.md...",
  "DOGRULAMA: Kaydi olusturduktan sonra 'ls -la' ile dosya varligini dogrula."
]
```

**Besleyici KÖPRÜ (mevcut kaydı güncelleyen — 16 skill):**
```toml
# custom/bmad-testarch-automate.toml
[workflow]
activation_steps_append = [
  "KÖPRÜ: Test sonuclarini QR-<sira>.md kaydinin Mekanik kontroller bolumune ekle..."
]
```

**DOGRULAMA:** Üretici KÖPRÜ'lerde `DOGRULAMA` adımı bulunur. LLM her kayıt
oluşturduğunda `ls -la` ile dosyanın varlığını doğrular. Bu, KÖPRÜ'nün atlanmasını
önleyen otomatik bir kontrol katmanıdır.

### 7.3. Köprü Çözümü (resolve_customization.py)

```bash
# Tüm özelleştirme çıktısı
python3 hooks/engine/resolve_customization.py -s skills/bmad-dev-story

# Belirli alan
python3 hooks/engine/resolve_customization.py -s skills/bmad-dev-story -k workflow.activation_steps_append

# Birden fazla alan
python3 hooks/engine/resolve_customization.py -s skills/bmad-dev-story \
  -k agent.name -k workflow.activation_steps_append
```

### 7.4. Manifesto Kablolaması

Her metodoloji yüzeyi (skill) şu belgeleri referans almalıdır:
- `research-methodology.md` — Araştırma manifestosu (tüm yüzeyler)
- `project-context.md` — Proje bağlamı (tüm yüzeyler)
- `development-methodology.md` — Geliştirme manifestosu (geliştirme kanadı)

Köprü belgesi: `docs/bmad/dev-skill-to-methodology-bridge.md`

---

## 8. Komutlar

### 8.1. `/metodoloji:init`

**Amaç:** Kayıt iskeletini hedef projeye kur

**Etki:**
- 6 dizin oluşturur (varsa dokunmaz)
- 8 şablon kopyalar (üzerine yazmaz)
- Manifesto kopyalarını kurar
- Eksikse kapı anahtarı uyarısı verir

**Kullanım:** OpenHands oturumunda `/metodoloji:init` yazın veya kılavuza göre
adımları izleyin.

### 8.2. `/metodoloji:kapi-kur`

**Amaç:** Kapı anahtarını üret (gate-key init)

**Etki:**
- `~/.bmad/gate-key` oluşturur (yoksa)
- 0600 izin ayarlar
- HMAC anahtarı üretir (secrets.token_hex(32))
- Anahtar içeriğini **asla** yazdırmaz/kopyalamaz

**Kullanım:**
```bash
python3 skills/bmad-research-experiment/scripts/run_experiment.py --init-secret
```

### 8.3. `/metodoloji:dogrula`

**Amaç:** Deney kaydını doğrula

**Çıktılar:**
| Çıktı | Anlam |
|-------|-------|
| `VERIFIED` | Kayıt ONAYLANDI ve token geçerli |
| `FORGED` | Token anahtarla uyuşmuyor — kayıt geçersiz |
| `REDDEDİLDİ` | Kapıdan geçmemiş |

**Kullanım:**
```bash
python3 skills/bmad-research-experiment/scripts/run_experiment.py \
  --verify --record docs/experiments/E-001.md
```

### 8.4. `/metodoloji:denetim`

**Amaç:** Metodoloji sağlık kontrolü

**Kapsam:**
1. Plugin bütünlüğü (§0–§6 + §2b + §5b + drift)
2. Kayıt zinciri durumu
3. Onaylı deney envanteri
4. Hook yapılandırması
5. Sonuç raporu (PASS/FAIL)

### 8.5. check-plugin.sh

```bash
# Tam denetim
sh commands/check-plugin.sh

# Negatif test: KÖPRÜ boz → yakala → geri yükle
sh commands/check-plugin.sh --negtest
```

**Çıkış kodları:**
- `0` = tüm kontroller geçti (SAĞLIKLI)
- `1` = sorun bulundu

---

## 9. Şablonlar

### 9.1. Şablon Listesi

| Şablon | Hedef | Kullanım |
|--------|-------|----------|
| `_template_E.md` | `docs/experiments/E-NNN.md` | Deney kaydı |
| `_template_IR.md` | `docs/development/IR-NNN.md` | Implementation Readiness |
| `_template_SP.md` | `docs/development/SP-NNN.md` | Sprint planlama |
| `_template_S.md` | `docs/development/stories/S-NNN.md` | Story kaydı |
| `_template_QR.md` | `docs/quality/QR-NNN.md` | Quality Review |
| `_template_PR.md` | `docs/development/PR-NNN.md` | Production Readiness |
| `README.md` | `docs/development/README.md` | Geliştirme dizin açıklaması |
| `tech-debt.md` | `docs/development/tech-debt.md` | Teknik borç takibi |

### 9.2. Şablon Kullanımı

Şablonları elle kopyalayın veya scriptleri kullanın:

```bash
# Deney şablonundan yeni kayıt
cp templates/_template_E.md docs/experiments/E-001.md
# ↓ editing: E-001.md dosyasını doldurun

# Story'den metodoloji kaydı (otomatik)
python3 scripts/create-methodology-record.py --story path/to/story.md

# Story'den QR kaydı (otomatik)
python3 scripts/create-qr-record.py --story path/to/story.md
```

---

## 10. Serbest Bölge ve Kısıt Alanları

### 10.1. Serbest Bölgeler (Approval Gerektirmez)

Aşağıdaki yollar guard tarafından otomatik olarak serbest bırakılır:

| Ön Ek/Dizin | Açıklama |
|-------------|----------|
| `_bmad/` | Eski BMAD modül verisi |
| `scratch/` | Keşif kodu serbest bölgesi |
| `graft/` | Greft kodu |
| `.git/` | Git dizinleri |
| `tmp/`, `temp/` | Geçici dosyalar |
| `openhands/` | OpenHands dizinleri |
| `.metodoloji/` | Plugin'in kendi dizini |
| `docs/*.md` | Belge dosyaları |
| `docs/*/raw/` | Ham veri dosyaları |
| `explore_*` | Keşif dosyaları |
| Altyapı dosyaları | `scripts/check-methodology.sh` |

### 10.2. Korunan Alanlar (Approval Gerekli)

Tüm kaynak kod dosyaları ve çalıştırılabilir yapılandırma dosyaları:

- `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.java`, `.go`, `.rs`
- `Makefile`, `Dockerfile`, `package.json`, `.github/workflows/*.yml`
- `src/`, `lib/`, `tools/`, `bin/`, `core/`, `app/` dizinleri

### 10.3. Serbest Bölge Dışı Korumalı Alanlar

`scratch/`, `tmp/`, `temp/` altındaki dosyalarda dahi `.bmad` dizini,
gate-key, bmad_gate_key gibi gizli erişim kalıpları tespit edilirse
**DENY** verilir.

---

## 11. Güvenlik

### 11.1. Gate Key (Kapı Anahtarı)

- **Konum:** `~/.bmad/gate-key` (repo DIŞI)
- **İzin:** 0600 (yalnızca sahibi)
- **İçerik:** 64 karakter hex string (32 byte rastgele)
- **Amaç:** HMAC doğrulaması — deney kayıtlarının sahte olmadığını garanti eder
- **Ömür:** Makine-yereldir; her geliştirici kendi anahtarını üretir

### 11.2. Secret Koruması

Guard motoru şu kalıpları tespit eder ve engeller:

| Kalıp | Etki |
|-------|------|
| `gate-key` içeren komut | DENY |
| `bmad_gate_key` içeren komut | DENY |
| `.bmad` dizini erişimi | DENY |
| `scratch/`/`tmp/`/`temp/` altinda `.bmad`/`gate-key` içeren içerik | DENY |

### 11.3. HMAC Token Yapısı

Her deney onayı bir HMAC token ile imzalanır:
- `GATE-OK-<hash>` formatında
- Gate key ile üretildi ve doğrulandı
- Sahte token tespit edilirse `FORGED` sonucu döner

---

## 12. Denetim ve Sağlık Kontrolü

### 12.1. Otomatik Denetim (check-plugin.sh)

```bash
sh commands/check-plugin.sh
```

**Kontrol bölümleri:**

| Bölüm | İçerik | Hata Kodu |
|-------|--------|-----------|
| §0 | Kapı anahtarı kurulu mu | `--init-secret` |
| §1 | Hook motoru selfcheck | `--selfcheck` |
| §2 | Manifesto + köprü kablolası | TOML parse + consume kontrolü |
| §2b | Köprü runtime görünür mü (29 skill) | `resolve_customization` deep_merge |
| §2c | Köprü DOGRULAMA talimatı mevcut mu (13 skill) | KÖPRÜ içinde DOGRULAMA arama |
| §3 | Onaylı deney envanteri | `--verify` ile her E kaydı |
| §4 | Belgesel kayıt eksiksizliği | `--validate` ile B/C/D kayıtları |
| §5 | Engine drift denetimi | Tüm engine dosyaları mevcut mu? |
| §5b | Hard gate modu | `custom/config.toml [hooks]` |
| §6 | Geliştirme kayıtları formatı | Karar/Durum/Tarih alanları |

### 12.2. Negatif Test

```bash
sh commands/check-plugin.sh --negtest
```

Bu test:
1. `custom/bmad-dev-story.toml`'dan KÖPRÜ satırını geçici olarak kaldırır
2. §2b mantığının MISS tespit ettiğini doğrular
3. Custom TOML'ı orijinaline geri yükler

### 12.3. KÖPRÜ Dağılımı

**Üretici KÖPRÜ (17 skill) — kayıt oluşturan:**
- `bmad-dev-story`, `bmad-quick-dev`, `bmad-dev-auto`, `bmad-agent-dev`
- `bmad-code-review`, `bmad-create-story`, `bmad-sprint-planning`, `bmad-check-implementation-readiness`
- `gds-dev-story`, `gds-quick-dev`, `gds-code-review`, `gds-create-story`
- `gds-sprint-planning`, `gds-check-implementation-readiness`
- `gds-agent-game-dev`, `gds-agent-game-solo-dev`, `wds-5-agentic-development`

**Besleyici KÖPRÜ (16 skill) — mevcut QR'a veri besleyen:**
- `bmad-testarch-*` (atdd, automate, ci, framework, nfr, test-design, test-review, trace)
- `bmad-qa-generate-e2e-tests`
- `gds-test-*` (automate, design, framework, review)
- `gds-e2e-scaffold`, `gds-performance-test`, `gds-playtest-plan`

### 12.3. Manuel Doğrulama

```bash
# Tek deney doğrulama
python3 skills/bmad-research-experiment/scripts/run_experiment.py \
  --verify --record docs/experiments/E-001.md

# Tüm deney envanteri
for f in docs/experiments/E-*.md; do
  python3 skills/bmad-research-experiment/scripts/run_experiment.py \
    --verify --record "$f"
done
```

### 12.4. Audit Log İnceleme

```bash
# Tüm audit kayıtları
cat .metodoloji/logs/hook-audit.log

# Son 10 kayıt
tail -10 .metodoloji/logs/hook-audit.log

# Belirli tool için filtrele
grep '"tool": "file_editor"' .metodoloji/logs/hook-audit.log

# Uyarılar
grep 'methodology_warnings' .metodoloji/logs/hook-audit.log
```

---

## 13. Sorun Giderme

### 13.1. "No approved experiment record" Hatası

**Neden:** Kod yazmaya çalıştığınız dosya, onaylı bir deney kaydının kapsamı dışında.

**Çözüm:**
```bash
# 1. Yeni deney oluşturun
cp templates/_template_E.md docs/experiments/E-001.md

# 2. Deneyi doldurun (Kod kapsamı alanını ekleyin)
# docs/experiments/E-001.md → Kod kapsamı: src/dosyaniz/**/*.py

# 3. Kapıyı çalıştırın
python3 skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-001.md \
  --run "python scripts/bench/benchmark.py"

# 4. Kod yazmaya devam edin
```

### 13.2. "Gate key not configured" Hatası

**Neden:** `~/.bmad/gate-key` dosyası yok.

**Çözüm:**
```bash
python3 skills/bmad-research-experiment/scripts/run_experiment.py --init-secret
```

### 13.3. "Hook motoru çalışamadı" Hatası

**Neden:** Python3 bulunamadı veya engine dosyaları eksik.

**Çözüm:**
```bash
# Python kontrolü
python3 --version  # 3.11+ olmalı

# Engine dosyaları kontrolü
ls -la hooks/engine/main.py
ls -la hooks/engine/modules/

# Import testi
python3 -c "import sys; sys.path.insert(0, 'hooks/engine'); import main; print('OK')"
```

### 13.4. "KÖPRÜ merge sorunu" Uyarısı

**Neden:** Custom TOML'daki KÖPRÜ adımı deep_merge ile birleşmemiş.

**Çözüm:**
```bash
# Köprü görünürlüğünü test edin
python3 hooks/engine/resolve_customization.py \
  -s skills/bmad-dev-story \
  -k workflow.activation_steps_append

# Çıktıda "KÖPRÜ" olmalı
```

### 13.5. "Story experiment validation failed" Hatası

**Neden:** Story dosyasındaki `experiment_refs` geçersiz veya deney kaydı yok.

**Çözüm:**
1. `docs/experiments/E-XXX.md` dosyası var mı kontrol edin
2. Deney durumu `ONAYLANDI` mı?
3. `run_experiment.py --verify` ile token doğrulaması yapın

### 13.6. Stop Hook'u Oturumu Kapatmıyor

**Neden:** Tamamlanmamış story veya onaysız kod değişikliği var.

**Çözüm:**
```bash
# Sprint durumunu kontrol edin
cat bmad-output/implementation-artifacts/sprint-status.yaml

# In-progress story'leri tamamlayın veya durumlarını değiştirin
# Onaysız dosyalar için deney kapsamı ekleyin
```

---

## 14. Sıkça Sorulan Sorular

### S: `quality_gate` / `deploy_guard` soft/hard modu ne işe yarar?

**C:** OpenHands runtime'da bu değerler **artık hook seviyesinde zorlanır**:
- `quality` hook'u: `git commit`'te IR/QR/SP eksikse DENY (fail-closed)
- `deploy` hook'u: deploy komutlarında IR/QR/SP/PR eksikse DENY (fail-closed)
- `guard` hook'u: kod yazarken deney onayı + story metadata doğrulaması (fail-closed)
- `stop` hook'u: oturum kapanışında in-progress story kontrolü (fail-closed)

`quality_gate`/`deploy_guard` config değerleri artık hook seviyesindeki
bu mekanik zorlamanın üstündedir.

### S: `scratch/` dizininde deney olmadan kod yazabilir miyim?

**C:** Evet. `scratch/` serbest bölgesidir; guard tarafından denetlenmez.
Ancak buradaki kod produccióna asla giremez — sadece keşif amaçlıdır.

### S: Gate key'mi başka biriyle paylaşabilir miyim?

**C:** Hayır. Gate key makine-yereldir; her geliştirici kendi anahtarını
üretmelidir. Paylaşım HMAC güvenliğini bozar.

### S: Birden fazla deney aynı anda aktif olabilir mi?

**C:** Evet. Her deney kendi kapsamını (glob) tanımlar. Guard, hedef dosyanın
herhangi bir aktif deneyin kapsamı içinde olup olmadığını kontrol eder.

### S: Eski `bmad-hooks.py` dosyası hâlâ kullanılıyor mu?

**C:** Hayır. Tek dosyalık `bmad-hooks.py` kaldırılmıştır. Tüm referanslar
modüler motor (`hooks/engine/main.py` + `modules/`) içindir.

### S: Plugin'i nasıl güncellerim?

```bash
cd /path/to/metodoloji
git pull
```

### S: custom TOML'daki bir öğeyi nasıl silerim?

**C:** Silme mekanizması yoktur. Bir öğeyi devre dışı bırakmak için:
1. Skill'i fork edin
2. Veya o code/id'ye sahip öğeyi noop açıklamayla override edin

---

## 15. Sözlük

| Terim | Tanım |
|-------|-------|
| **BMAD** | Build Methodology for Agent-Driven development |
| **Guard** | PreToolUse hook'u — kod yazımını engelleyen mekanik kapı (deney + story metadata) |
| **Quality** | PreToolUse hook'u — `git commit`'te IR/QR/SP zincirini zorlayan kapı |
| **Deploy** | PreToolUse hook'u — deploy komutlarında IR/QR/SP/PR zincirini zorlayan kapı |
| **Audit** | PostToolUse hook'u — her tool çağrısını loglayan denetim izi + KÖPRÜ uyarısı |
| **Stop** | Stop hook'u — oturum kapanışını engelleyen mekanik kapı |
| **KÖPRÜ** | Native skill çıktısını metodoloji kaydına bağlayan TOML adımı |
| **Gate Key** | HMAC doğrulaması için kullanılan makine-yerel anahtar |
| **Gate Token** | Deney onayı sonucu üretilen GATE-OK-... imzası |
| **Fail-Closed** | Motor çalışamazsa varsayılan olarak engelleme (DENY) |
| **Fail-Open** | Motor çalışamazsa varsayılan olarak izin verme (allow) |
| **Serbest Bölge** | Guard denetimi dışı dizin/dosyalar (scratch/, docs/, .git/) |
| **Kod Hedefi** | Guard tarafından korunan dosyalar (.py, .js, .ts, Makefile vb.) |
| **Drift** | Plugin kurulu kopyası ile repo canonical arasındaki fark |
| **Deep Merge** | TOML tablolarını递归 olarak birleştirme |
| **Memlog** | Calışma hafızası loglama aracı (.memlog.md) |
| **Metodoloji Zinciri** | E → IR → SP → S → QR → PR halka yapısı — her halka mekanik olarak zorlanır |
| **Mod A** | Sayısal/empirik deney modu (kod üretiminin tek yolu) |
| **Mod B** | Nitel araştırma modu |
| **Mod C** | Tasarım modu |
| **Mod D** | Bağlamsal araştırma modu |

---

## Ek: Hızlı Başlangıç Komutları

```bash
# 1. Plugin kurulumu
git clone https://github.com/yunusgungor/openhands-metodoloji.git

# 2. İlk kurulum (OpenHands otomatumda)
/metodoloji:init          # Kayıt iskeletini kur
/metodoloji:kapi-kur      # Gate key üret

# 3. Deney oluştur ve onay al
cp templates/_template_E.md docs/experiments/E-001.md
# → E-001.md'yi doldurun (hipotez, kapsam, metrik)
python3 skills/bmad-research-experiment/scripts/run_experiment.py \
  --record docs/experiments/E-001.md \
  --run "python scripts/bench/bench.py"

# 4. Kod yazmaya başla
# → Guard artık src/ kapsamına izin veriyor

# 5. Sağlık kontrolü
sh commands/check-plugin.sh
/metodoloji:denetim

# 6. Kayıt oluştur
python3 scripts/create-methodology-record.py --story path/to/story.md
python3 scripts/create-qr-record.py --story path/to/story.md
```

---

> **Not:** Bu belge `metodoloji` plugin v1.0.0 için geçerlidir. Plugin
> geliştikçe güncellenmelidir. Son güncellemeler için repository:
> https://github.com/yunusgungor/openhands-metodoloji

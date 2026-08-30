# Code Docs Dizini

Proje geçmişini hatırlamak ve yeni bilgi üretmek için kullanılan yapılandırılmış dokümantasyon sistemi.

## Kategoriler

### [Kararlar](./decisions/) — 0 kayıt

### [Kalıplar](./patterns/) — 0 kayıt

### [Dersler](./learnings/) — 0 kayıt

### [API Kullanımları](./api/) — 0 kayıt

### [Sorun Giderme](./troubleshooting/) — 0 kayıt

### [Bekleyen İşler](./pending/) — 0 kayıt

## Otomatik Üretim

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

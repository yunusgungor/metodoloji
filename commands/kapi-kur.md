# /metodoloji:kapi-kur — Kapı anahtarını üret (gate-key init)

Metodolojinin mekanik kapıları (Mod A onayı, QR/PR hard modu) `~/.bmad/gate-key` dosyasındaki
makine-yerel anahtarla HMAC doğrulaması yapar. Bu dosya **repo dışında, 0600 izinli** olmalı
ve asla commit edilmez.

## Adımlar

1. `~/.bmad/gate-key` varsa: "zaten kurulu" de, bitir (üzerine yazma — eski kanıtlar bozulur).

2. Yoksa şu komutu çalıştır:
   ```sh
   python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py --init-secret
   ```

3. Sonucu doğrula: dosya var mı, izni 0600 mı? Anahtar içeriğini **asla** yazdırma,
   kopyalama veya başka dosyaya taşıma — guard bu izleri engeller.

4. Çıktıda `GATE-OK-...` token örneği görünüyorsa kurulum tamam. Sıradaki adım:
   ilk deney kaydı (`docs/experiments/E-001.md`) ile guard-code'un kod yazımına izin vermesi.

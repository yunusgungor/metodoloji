# /metodoloji:init — Kayıt iskeletini hedef projeye kur

Bu komut metodoloji kayıt zinciri için gereken dizinleri ve şablonları **{project-root}**
altına kurar. {metodoloji-root} = bu plugin'in kurulum kökü (`~/.openhands/plugins/installed/metodoloji`).

## Adımlar

1. Şu dizinleri oluştur (varsa dokunma):
   - `docs/experiments/` — Mod A deney kayıtları (E-NNN.md)
   - `docs/development/stories/` — story kayıtları (S-NNN.md)
   - `docs/research/` — Mod B/D belgesel kayıtlar
   - `docs/design/` — Mod C belgesel kayıtlar
   - `docs/bmad/` — manifesto ve köprü kopyaları
   - `scratch/` — keşif kodu serbest bölgesi

2. Şablonları kopyala (üzerine yazma — varsa koru):
   - `{metodoloji-root}/templates/_template_E.md` → `docs/experiments/_template.md`
   - `{metodoloji-root}/templates/_template_IR.md` → `docs/development/_template_IR.md`
   - `{metodoloji-root}/templates/_template_SP.md` → `docs/development/_template_SP.md`
   - `{metodoloji-root}/templates/_template_QR.md` → `docs/development/_template_QR.md`
   - `{metodoloji-root}/templates/_template_PR.md` → `docs/development/_template_PR.md`
   - `{metodoloji-root}/templates/_template_S.md` → `docs/development/stories/_template_S.md`
   - `{metodoloji-root}/templates/README.md` → `docs/development/README.md`
   - `{metodoloji-root}/templates/tech-debt.md` → `docs/development/tech-debt.md`

3. Manifesto kopyaları (kaynak: plugin'deki referans kopyalar yerine repo metinleri):
   - `docs/bmad/` altına bu metodoloji paketinin köprü ve manifesto kopyaları varsa kur.

4. Kapı anahtarı yoksa uyar: `/metodoloji:kapi-kur` çalıştır.

5. Özet yaz: kurulan dizinler, atlanan (mevcut) dosyalar, sıradaki adım
   (`/metodoloji:denetim` ile sağlık kontrolü).

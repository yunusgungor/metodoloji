# /metodoloji:dogrula — Deney kaydını doğrula (verify)

`{project-root}/docs/experiments/<deney-id>.md` kaydının ONAYLANDI olup olmadığını ve
kapı kanıtının (gate token) sahte olmadığını doğrular.

## Kullanım

```sh
python3 {metodoloji-root}/skills/bmad-research-experiment/scripts/run_experiment.py \
  --verify --record {project-root}/docs/experiments/<deney-id>.md
```

## Çıktıların anlamı

| Çıktı | Anlam | Ne yapmalı |
|---|---|---|
| `VERIFIED` | Kayıt ONAYLANDI ve token geçerli | guard bu kaydın `Kod kapsamı` alanındaki glob'larla kod yazımına izin verir |
| `FORGED` | Token anahtarla uyuşmuyor | kayıt geçersiz — kod yazılamaz; kaydı yeniden üret (`--record ... --run <komut>`) |
| `REDDEDİLDİ` / başka | Kapıdan geçmemiş | hipotezi revize et, yeniden ölç |

Kod yazmadan önce guard zaten bu doğrulamayı yapar; bu komut manuel kontrol içindir.

# /metodoloji:denetim — Metodoloji sağlık kontrolü (plugin varyantı)

Plugin'in kendi bütünlüğünü ve hedef projedeki kayıt disiplinini mekanik denetler.

## Adımlar

1. Plugin bütünlüğü: şu betiği çalıştır ve sonucu özetle:
   ```sh
   sh {metodoloji-root}/commands/check-plugin.sh
   ```
   (0 sorun = SAĞLIKLI)

2. Kayıt zinciri durumu: `{project-root}/docs/experiments/` ve `{project-root}/docs/development/`
   altındaki kayıtları listele; zincir halkası eksiklerini belirt (ör. S var QR yok).

3. Onaylı deney envanteri: her E kaydında `--verify` çalıştırıp VERIFIED/FORGED dağılımını raporla
   (`/metodoloji:dogrula` mantığı).

4. Hook yapılandırması: `custom/config.toml [hooks]` quality_gate/deploy_guard değerlerini
   oku (soft/hard). Hard mod yalnızca ilk gerçek IR/SP/QR/PR kayıtları üretildikten sonra
   açılmalıdır.

5. Sonuç raporu: PASS/FAIL listesi + düzeltme önerileri. Negatif test gerektiren bir sorun
   bulursan (ör. KÖPRÜ çözülemiyor) betiğin boz→yakala→geri yükle çıktısını göster.

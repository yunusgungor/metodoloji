# /metodoloji:denetim — Metodoloji sağlık kontrolü (plugin varyantı)

Plugin'in kendi bütünlüğünü ve hedef projedeki kayıt disiplinini mekanik denetler.

## Adımlar

1. Plugin bütünlüğü: şu betiği çalıştır ve sonucu özetle:
   ```sh
   sh {metodoloji-root}/commands/check-plugin.sh
   ```
   (0 sorun = SAĞLIKLI; §5c custom/ statik kalite denetimi bu betiğin
   içinde §5c olarak çalışır — ayrıca çalıştırmaya gerek yok)

2. Custom/ köprü TOML'leri (yalnız denetim istenirse): §0–§7'yi ayrıntılı
   görmek için `commands/check-custom.sh` çalıştırılabilir. `check-plugin.sh`
   §5c zaten aynı bölümleri çalıştırır; bu adım yalnızca custom/ odaklı
   rapor istendiğinde kullanılır.

3. Kayıt zinciri durumu: `{project-root}/docs/experiments/` ve `{project-root}/docs/development/`
   altındaki kayıtları listele; zincir halkası eksiklerini belirt (ör. S var QR yok).

4. Onaylı deney envanteri: her E kaydında `--verify` çalıştırıp VERIFIED/FORGED dağılımını raporla
   (`/metodoloji:dogrula` mantığı).

5. Hook yapılandırması: `custom/config.toml [hooks]` quality_gate/deploy_guard değerlerini
   oku (soft/hard; OpenHands'te bağlı hook değil — guard/stop fail-closed çalışır).

6. Sonuç raporu: PASS/FAIL listesi + düzeltme önerileri. Negatif test gerektiren bir sorun
   bulursan (ör. KÖPRÜ çözülemiyor) betiğin boz→yakala→geri yükle çıktısını göster;
   `check-custom.sh --negtest` ile custom/ drift denetiminin canlı olduğunu kanıtla.

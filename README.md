# AI Hologram

Kamera + MediaPipe el takibi üzerine kurulu holografik efekt motoru.

Eski tek dosyalık sürüm `legacy/main_orb_v1.py` içinde duruyor.

## Kurulum

```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
```

> Not: Bu makinede `opencv-python` (5.0) ve `opencv-contrib-python` (4.11) aynı
> venv içinde birlikte kurulu. İleride garip `cv2` hataları görürsen
> `pip uninstall opencv-python` ile fazlalığı kaldır; mediapipe
> `opencv-contrib-python` bekliyor.

## Çalıştırma

```powershell
python main.py                # otomatik mod
python main.py --debug        # iskelet/landmark çizimi açık
python main.py --mode HOLO    # doğrudan hologram modu
python main.py --camera 1     # ikinci kamera
```

## Modlar

| Tuş | Mod | Ne yapar |
|-----|-----|----------|
| `0` | AUTO | 1 el → PORTAL, 2 el → ORB |
| `1` | ORB | İki avuç arasında enerji küresi (nefes alır, halkalar döner) |
| `2` | HOLO | İki el arasında wireframe nesne: küp / torus / DNA (`G` ile değiştir) |
| `3` | PORTAL | Tek avuç içinde dönen portal; avucu açtıkça büyür |
| `4` | LIGHT | İki işaret parmağı arasında dallanan yıldırım |

## Jestler

- **Pinch + bırak**: iki elle başparmak-işaret birleştir, tut, bırak → şok dalgası.
  Tutma süresi arttıkça dalga büyür (HUD'daki `CHARGE` çubuğu).
- **El çırpma**: eller hızla birbirine yaklaşırsa güçlü şok dalgası.
- **El açıklığı**: iki el arası mesafe kürenin ve hologramın boyutunu belirler.
- **Elleri çevirme**: HOLO modunda nesnenin dönüş açısını kontrol eder.

## Kısayollar

```
Q / ESC : çıkış          P : palet (gold / cyan / violet)
0-4     : mod            G : hologram şekli (küp / torus / DNA)
D       : debug iskelet  S : ekran görüntüsü (captures/)
R       : video kaydı    F : tam ekran
H       : HUD'u gizle
```

## Dosyalar

```
main.py       kamera döngüsü, mod yönetimi, jestler, tuşlar, kayıt
config.py     tüm sabitler: çözünürlük, renkler, bloom, yarıçaplar, jest eşikleri
tracking.py   MediaPipe sarmalayıcı + HandState (merkez, pinch, açıklık, hız)
fx.py         radyal parlama, bloom, parçacık sistemi, şok dalgası
effects.py    ORB / PORTAL / LIGHTNING / HOLO efektleri
hud.py        FPS, mod, şarj çubuğu, ipuçları
captures/     ekran görüntüleri ve kayıtlar
legacy/       eski tek dosyalık sürüm
```

## Mimari

Tüm efektler **siyah bir katmana additive** çizer (`layer`). Sonra `fx.Bloom`
bu katmanın parlak bölgelerini 1/4 çözünürlükte bulanıklaştırıp kameranın
üstüne ekler. Kamera görüntüsü bloom'a hiç girmez, bu yüzden sadece hologram
parlar.

Yeni efekt eklemek için `effects.Effect` alt sınıfı yaz, `name`/`needs` ver,
`update()` + `draw()` doldur ve `main.App.__init__` içindeki listeye ekle.

## Performans (bu makinede ölçüldü, 1280x720)

| Efekt | efekt çizimi | bloom | toplam |
|-------|--------------|-------|--------|
| ORB | 3.1 ms | 3.6 ms | ~6.9 ms |
| PORTAL | 2.7 ms | 4.0 ms | ~7.0 ms |
| LIGHTNING | 2.9 ms | 5.5 ms | ~8.6 ms |
| HOLO | 1.1 ms | 5.6 ms | ~6.9 ms |

MediaPipe el takibi ~32 ms (640 px genişlikte). Kamera bu makinede ~10 FPS
veriyor (karanlık ortam / uzun pozlama), yani darboğaz efektler değil kamera.
Daha hızlı takip için `config.MODEL_COMPLEXITY = 0` ve/veya
`PROCESS_WIDTH = 480` yapabilirsin.

## Ayarlama ipuçları

- Fazla parlıyorsa: `BLOOM_THRESHOLD` ↑, `BLOOM_STRENGTH` ↓.
- Efekt geç takip ediyorsa: `fx.smooth(...)` çağrılarındaki `speed` değerini ↑.
- Pinch zor algılanıyorsa: `config.PINCH_THRESHOLD` ↓ (0.6 gibi).
- Küre çok büyük/küçükse: `ORB_RADIUS_MIN/MAX/FACTOR`.
- Renk eklemek için `config.PALETTES` sözlüğüne 4 renkli yeni bir demet ekle.

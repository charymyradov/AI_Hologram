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

- **Yumruk (kavrama)**: HOLO modunda nesneyi tutar, otomatik dönmeyi durdurur; eli
  savurarak nesneye spin verirsin. Bırakınca dönme yavaşça söner.
- **Pinch + bırak**: iki elle başparmak-işaret birleştir, tut, bırak → şok dalgası.
  Tutma süresi arttıkça dalga büyür (HUD'daki `CHARGE` çubuğu).
- **El çırpma**: eller hızla birbirine yaklaşırsa güçlü şok dalgası.
- **El açıklığı**: iki el arası mesafe kürenin, hologramın ve haritanın boyutunu belirler.
- **Elleri çevirme**: HOLO modunda nesnenin dönüş açısını kontrol eder.
- **Hızlı savurma**: artık enerji topu fırlatmaz; sadece kavrama/spin hareketi olarak
  değerlendirilir.

## Türkmenistan haritası

`T` ile açılır/kapanır. Harita açıkken **diğer tüm efektler, jestler ve HUD kapanır**;
ekranda yalnızca yeşil Türkmenistan hologramı kalır. Gerçek sınır verisi
`data/turkmenistan.json` içinde (54 nokta, GeoJSON'dan üretildi).

- **Tek el**: avucu açıp kapatmak haritayı büyütür/küçültür. Harita merkezde kalır.
- **İki el**: eller arası mesafe ölçeği belirler. Harita kendiliğinden kaymaz.
- **Yumruk**: haritayı kavrayıp taşırsın (boyut değişmez); sadece bu sırada konum değişir.
- **A**: Aşkabat'taki Bagt Köşgi (Düğün Sarayı) binasını yerden yükselterek oluşturur.
  Harita kapalıysa önce haritayı açar; tekrar `A` binayı gizler.
- `C` haritayı ekranın ortasına ve varsayılan boyuta döndürür.

Konum ve ölçek yay fiziğiyle (`fx.Spring`) yumuşatılır; açılış/kapanış ise
`fx.smoothstep` / `fx.ease_out_cubic` eğrileriyle yumuşakça yapılır. Harita
kapanırken diğer efektler hemen geri gelmez; önce kapanış animasyonu biter.
Haritanın kendi başlığında anlık ölçek (`%118` gibi) görünür.

## Kısayollar

```
Q / ESC : çıkış          P : palet (gold / cyan / violet)
0-4     : mod            G : hologram şekli (küp / torus / DNA)
D       : debug iskelet  T : Türkmenistan haritası (sadece harita)
A       : Aşkabat binası (haritayı açar)
V       : post-process aç/kapat (vinyet, tarama, grain, kroma)
S       : ekran görüntüsü (captures/)
R       : video kaydı    F : tam ekran
H       : HUD'u gizle    C : haritayı ortala
```

> Yıldırım modu paletten bağımsız olarak her zaman elektrik mavisidir
> (`config.LIGHTNING_PALETTE`).

## Dosyalar

```
main.py       kamera döngüsü, mod yönetimi, jestler, tuşlar, kayıt
config.py     tüm sabitler: çözünürlük, renkler, bloom, yarıçaplar, jest eşikleri
tracking.py   MediaPipe sarmalayıcı + HandState (merkez, pinch, açıklık, jest, hız)
fx.py         parlama, bloom, parçacık, şok dalgası, yay, el maskesi,
              afterimage ve post-process
effects.py    ORB / PORTAL / LIGHTNING / HOLO efektleri
mapview.py    yeşil Türkmenistan haritası + Aşkabat Bagt Köşgi binası
data/         turkmenistan.json (normalize edilmiş gerçek sınır verisi)
hud.py        FPS, mod, şarj çubuğu, jest ve ipuçları
captures/     ekran görüntüleri ve kayıtlar
legacy/       eski tek dosyalık sürüm
```

## Mimari

İki ayrı efekt katmanı var:

- `layer` (arka): ORB, HOLO ve LIGHTNING. `fx.hands_mask` ile ellerin
  kapladığı alan bu katmandan silinir → efektler avucun/parmakların arkasında kalır.
- `front` (ön): PORTAL ve harita. Avuçtan çıkıyormuş gibi ellerin önünde çizilir.

Harita modu açıkken `layer` tamamen boş kalır, `front` yalnızca haritayı taşır ve
afterimage devre dışıdır; böylece harita hareket ederken hayalet iz birikmez.
Açık avuç haritayı sürüklemez; sadece ölçekler. Bu yüzden düşük FPS'te bile
harita ekranda zıplamaz.
Kapaklanma animasyonu sıfıra inene kadar da diğer efektler geri getirilmez.

Normal modda iki katman toplanır, `fx.Afterimage` ile hareket izi eklenir, sonra
`fx.Bloom` parlak bölgeleri 1/4 çözünürlükte bulanıklaştırıp kameranın üstüne
ekler. En son `fx.PostFX` vinyet, tarama çizgisi, grain ve kroma kayması uygular.
Kamera görüntüsü bloom'a hiç girmez, bu yüzden sadece hologram parlar.

Konum/ölçek değerleri `fx.Spring` / `fx.Spring2` ile taşınır: `smooth()` sadece
sönerek yaklaşırken yay hız kazanıp hafifçe aşar, bu da holograma ağırlık verir.

Yeni efekt eklemek için `effects.Effect` alt sınıfı yaz; `name`, `needs`,
`mask_hands` ver, `update()` + `draw()` doldur ve `main.App.__init__` içindeki
listeye ekle. Harita gibi özel bir katman için `mapview.py` örneğine bak.

## Performans (bu makinede ölçüldü, 1280x720)

| Efekt | efekt çizimi | bloom | toplam |
|-------|--------------|-------|--------|
| ORB | 3.1 ms | 3.6 ms | ~6.9 ms |
| PORTAL | 2.7 ms | 4.0 ms | ~7.0 ms |
| LIGHTNING | 2.9 ms | 5.5 ms | ~8.6 ms |
| HOLO | 1.1 ms | 5.6 ms | ~6.9 ms |

Yeni katman hattı (el maskesi + afterimage + post-process) 1280x720'de
yaklaşık **9 ms** ekliyor: maske ~3.5 ms, afterimage ~1.5 ms, postfx ~3.7 ms.
Hepsi `V` ile veya `config` üzerinden kapatılabilir.

MediaPipe el takibi ~32 ms (640 px genişlikte). Kamera bu makinede ~10 FPS
veriyor (karanlık ortam / uzun pozlama), yani darboğaz efektler değil kamera.
Daha hızlı takip için `config.MODEL_COMPLEXITY = 0` ve/veya
`PROCESS_WIDTH = 480` yapabilirsin.

## Ayarlama ipuçları

- Fazla parlıyorsa: `BLOOM_THRESHOLD` ↑, `BLOOM_STRENGTH` ↓.
- Efekt geç takip ediyorsa: efektlerdeki `fx.Spring(..., stiffness=...)` değerini ↑,
  çok titriyorsa `damping` değerini ↑ (kritik sönüm ≈ `2*sqrt(stiffness)`).
- Hareket izi çok uzun/kısa: `AFTERIMAGE_DECAY` (0.82 → daha küçük = kısa iz).
- Görüntü çok kirli/grainli: `POSTFX_VIGNETTE`, `POSTFX_SCANLINE`,
  `POSTFX_GRAIN` değerlerini düşür; tamamen kapatmak için `POSTFX_ENABLED = False`
  veya çalışırken `V`.
- Harita çok büyük/küçük açılıyorsa: `MAP_SCALE_DEFAULT`; el ile ulaşılan
  sınırlar için `MAP_SCALE_MIN/MAX`.
- Harita rengi: `MAP_PALETTE` (varsayılan yeşil, BGR sırası).
- Açık avucun haritayı sürüklemesini istiyorsan: `MAP_FOLLOW_OPEN_HAND = True`.
- El ölçüsü titriyorsa: `MAP_HAND_SMOOTHING` ↑ (daha yumuşak, biraz daha gecikmeli).
- Açılış/kapanış hızı: `MAP_REVEAL_TIME` / `MAP_HIDE_TIME`.
- Bina boyu ve oluşma süresi: `MAP_BUILDING_HEIGHT` / `MAP_BUILDING_REVEAL`.
- Harita eli çok sıkı takip ediyorsa: `mapview.TurkmenistanMap.__init__`
  içindeki `Spring2(stiffness=190, damping=25)` değerlerini düşür.
- Pinch zor algılanıyorsa: `config.PINCH_THRESHOLD` ↓ (0.6 gibi).
- Küre çok büyük/küçükse: `ORB_RADIUS_MIN/MAX/FACTOR`.
- Renk eklemek için `config.PALETTES` sözlüğüne 4 renkli yeni bir demet ekle.

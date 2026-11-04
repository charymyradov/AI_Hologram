"""Tüm ayarlar tek yerde.

Buradaki değerleri kurcalayarak görünümü kamerayı açmadan ayarlayabilirsin.
Renkler OpenCV standardı olan BGR sırasındadır (mavi, yeşil, kırmızı).
"""

# ---------------------------------------------------------------- kamera
CAMERA_INDEX = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# MediaPipe bu genişlikte çalışır, landmark'lar gerçek çözünürlüğe ölçeklenir.
# 640 => CPU'da belirgin hız kazancı, 960 => daha kararlı takip.
PROCESS_WIDTH = 640

MAX_HANDS = 2
MODEL_COMPLEXITY = 1
MIN_DETECTION_CONFIDENCE = 0.6
MIN_TRACKING_CONFIDENCE = 0.6

WINDOW_NAME = "AI Holographic Hand Interaction"

# ---------------------------------------------------------------- bloom
BLOOM_THRESHOLD = 85     # bu parlaklığın üstündeki pikseller parlar
BLOOM_SIGMA = 6.0        # parlama yumuşaklığı
BLOOM_STRENGTH = 1.25    # parlamanın görüntüye katkısı
BLOOM_SCALE = 4          # bloom 1/4 çözünürlükte hesaplanır (hız)

# ---------------------------------------------------------------- küre
ORB_RADIUS_MIN = 32
ORB_RADIUS_MAX = 200
ORB_RADIUS_FACTOR = 0.38
ORB_PARTICLES = 380

# ---------------------------------------------------------------- portal
PORTAL_RADIUS_MIN = 55
PORTAL_RADIUS_MAX = 165
PORTAL_PARTICLES = 300

# ---------------------------------------------------------------- şok dalgası
SHOCKWAVE_LIFE = 0.75

# ---------------------------------------------------------------- jest
PINCH_THRESHOLD = 0.75    # 0..1, 1 = başparmak ve işaret tam değiyor
CHARGE_RATE = 0.85        # saniyede dolan şarj miktarı
CHARGE_MIN_TO_BURST = 0.12
CLAP_GAP = 110            # eller bu mesafeden yakınsa "el çırpma"
CLAP_PREVIOUS_GAP = 260   # önceki karede en az bu kadar açık olmalı

# ---------------------------------------------------------------- renkler (BGR)
# Her palet: koyu -> orta -> parlak -> çekirdek
PALETTES = {
    "gold": (
        (10, 55, 130),
        (35, 125, 225),
        (75, 180, 255),
        (205, 240, 255),
    ),
    "cyan": (
        (120, 55, 10),
        (230, 155, 20),
        (255, 220, 70),
        (240, 255, 255),
    ),
    "violet": (
        (95, 20, 65),
        (215, 80, 190),
        (255, 130, 225),
        (255, 235, 250),
    ),
}
DEFAULT_PALETTE = "gold"

# Yıldırım her zaman elektrik mavisidir (palet değişse bile).
LIGHTNING_PALETTE = (
    (150, 45, 10),
    (255, 125, 30),
    (255, 210, 125),
    (250, 250, 255),
)

# ---------------------------------------------------------------- jest / yay
# Yumruk = tut/sürükle, açık avuç = ölçek, iki el mesafesi = ölçek.
FIST_GRAB = True           # yumrukla hologramı kavra ve döndür
GRAB_SPIN_GAIN = 0.9       # yumruk savururken dönme kazancı
GRAB_SPIN_DAMPING = 3.2    # bırakınca dönmenin sönümü

# ---------------------------------------------------------------- el maskesi
# Efektleri ellerin arkasında bırakır (ORB / HOLO / LIGHTNING / toplar).
HAND_MASK_ENABLED = True
HAND_MASK_FEATHER = 9      # kenar yumuşaklığı (px)
HAND_MASK_GROW = 6         # maskeyi kaç piksel büyüt

# ---------------------------------------------------------------- afterimage
AFTERIMAGE_ENABLED = True
AFTERIMAGE_DECAY = 0.82    # her karede izlerin çarpıldığı katsayı

# ---------------------------------------------------------------- post-process
POSTFX_ENABLED = True
POSTFX_VIGNETTE = 0.55     # 0 = kapalı, 1 = sert köşe karartması
POSTFX_SCANLINE = 0.14     # tek satır karartma oranı
POSTFX_CHROMA = 2          # kroma kayması (px)
POSTFX_GRAIN = 5           # grain şiddeti (0 = kapalı)

# ---------------------------------------------------------------- harita
MAP_FILE = "data/turkmenistan.json"
MAP_SCALE_MIN = 115.0      # haritanın yarı yüksekliği (px)
MAP_SCALE_MAX = 430.0
MAP_SCALE_DEFAULT = 235.0
MAP_SCALE_PER_DISTANCE = 0.55  # iki el mesafesi -> ölçek
MAP_GRID = 0.24            # enlem/boylam ızgara aralığı (normalize birim)

# Harita her zaman yeşil bir hologramdır (BGR).
MAP_PALETTE = (
    (18, 62, 14),      # koyu
    (42, 148, 48),     # orta
    (92, 236, 104),    # parlak
    (214, 255, 214),   # çekirdek
)

# Açılış/kapanış yumuşaklığı (saniye).
MAP_REVEAL_TIME = 0.34
MAP_HIDE_TIME = 0.24

# A: Aşkabat'taki Bagt Köşgi (Düğün Sarayı) hologramı.
MAP_BUILDING_ENABLED = True
MAP_BUILDING_HEIGHT = 0.56   # harita ölçeğine göre bina yüksekliği
MAP_BUILDING_REVEAL = 1.15   # yerden yükselme süresi (saniye)

# ---------------------------------------------------------------- HUD
HUD_ALPHA = 0.45
HUD_TEXT = (235, 240, 245)
HUD_DIM = (150, 160, 172)

KEYS_HELP = ("1 ORB  2 HOLO  3 PORTAL  4 LIGHT  0 AUTO  |  G shape  P color  T map  "
             "A building  V fx  D debug  S shot  R rec  F full  Q quit")

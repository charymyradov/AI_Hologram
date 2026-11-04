"""Düşük seviye çizim araçları: radyal parlama, bloom, parçacık ve şok dalgası.

Tüm efektler siyah bir `layer` üzerine additive (toplamalı) çizim yapar;
ardından `Bloom` bu katmanı kameranın üstüne ekler. Böylece "hologram"
gerçekten ışık yayıyormuş gibi görünür ve kamera görüntüsü kirlenmez.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

import config


# ------------------------------------------------------------------ renk
def scale_color(color, k: float):
    return tuple(int(max(0, min(255, c * k))) for c in color)


# ------------------------------------------------------------------ ışık
_SPRITES: dict[tuple, np.ndarray] = {}


def _sprite(color, power: float, gain: float) -> np.ndarray:
    """Renkli radyal parlama sprite'ı (önbellekli)."""
    key = (tuple(int(c) for c in color), round(float(power), 2), round(float(gain), 2))
    spr = _SPRITES.get(key)
    if spr is None:
        res = 201
        y, x = np.mgrid[-1.0:1.0:res * 1j, -1.0:1.0:res * 1j]
        d = np.sqrt(x * x + y * y)
        falloff = np.clip(1.0 - d, 0.0, 1.0) ** power
        patch = falloff[:, :, None] * (np.asarray(color, np.float32) * gain)
        spr = np.clip(patch, 0.0, 255.0).astype(np.uint8)
        if len(_SPRITES) > 256:  # önbellek şişmesin
            _SPRITES.clear()
        _SPRITES[key] = spr
    return spr


def add_radial(layer, cx, cy, radius, color, power: float = 1.8, gain: float = 1.0) -> None:
    """Merkezi parlak, kenara doğru yumuşakça sönen ışık lekesi ekler."""
    radius = int(radius)
    if radius < 2 or gain <= 0.0:
        return

    h, w = layer.shape[:2]
    x0, x1 = max(0, int(cx) - radius), min(w, int(cx) + radius + 1)
    y0, y1 = max(0, int(cy) - radius), min(h, int(cy) + radius + 1)
    if x0 >= x1 or y0 >= y1:
        return

    size = radius * 2 + 1
    spr = _sprite(color, power, gain)
    if size != spr.shape[1]:
        spr = cv2.resize(spr, (size, size), interpolation=cv2.INTER_LINEAR)

    ox = x0 - (int(cx) - radius)
    oy = y0 - (int(cy) - radius)
    patch = spr[oy:oy + (y1 - y0), ox:ox + (x1 - x0)]
    layer[y0:y1, x0:x1] = cv2.add(layer[y0:y1, x0:x1], patch)


def glow_line(layer, p1, p2, color, thickness: int = 2, glow: float = 0.6) -> None:
    """Çizgi + iki ucunda hafif parlama."""
    p1 = (int(p1[0]), int(p1[1]))
    p2 = (int(p2[0]), int(p2[1]))
    cv2.line(layer, p1, p2, color, thickness, cv2.LINE_AA)
    if glow > 0:
        for p in (p1, p2):
            add_radial(layer, p[0], p[1], thickness * 4 + 6, color, power=2.0, gain=glow)


# ------------------------------------------------------------------ bloom
class Bloom:
    """Parlak pikselleri düşük çözünürlükte bulanıklaştırıp sahneye ekler."""

    def __init__(self) -> None:
        self.threshold = config.BLOOM_THRESHOLD
        self.sigma = config.BLOOM_SIGMA
        self.strength = config.BLOOM_STRENGTH
        self.scale = config.BLOOM_SCALE

    def apply(self, frame: np.ndarray, layer: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        sw, sh = max(1, w // self.scale), max(1, h // self.scale)

        small = cv2.resize(layer, (sw, sh), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.GaussianBlur(mask, (0, 0), 1.5)
        bright = cv2.bitwise_and(small, small, mask=mask)

        glow = cv2.GaussianBlur(bright, (0, 0), self.sigma)
        glow = cv2.resize(glow, (w, h), interpolation=cv2.INTER_LINEAR)

        cv2.addWeighted(frame, 1.0, glow, self.strength, 0.0, dst=frame)
        cv2.add(frame, layer, dst=frame)
        return frame


# ------------------------------------------------------------------ parçacık
class ParticleSystem:
    """Havuz tabanlı parçacık sistemi; parçacıklar merkeze doğru çekilir."""

    def __init__(self, capacity: int = 320) -> None:
        self.capacity = capacity
        self.pos = np.zeros((capacity, 2), np.float32)
        self.vel = np.zeros((capacity, 2), np.float32)
        self.ttl = np.zeros(capacity, np.float32)
        self.max_ttl = np.ones(capacity, np.float32)
        self.size = np.zeros(capacity, np.float32)
        self.cursor = 0

    def emit(self, cx, cy, radius, count: int, speed: float = 85.0,
             life=(0.45, 1.15)) -> None:
        if count <= 0:
            return
        count = min(int(count), self.capacity)

        idx = (self.cursor + np.arange(count)) % self.capacity
        self.cursor = int((self.cursor + count) % self.capacity)

        ang = np.random.uniform(0.0, 2.0 * math.pi, count).astype(np.float32)
        r = float(radius) * np.random.uniform(0.78, 1.18, count).astype(np.float32)

        self.pos[idx, 0] = cx + np.cos(ang) * r
        self.pos[idx, 1] = cy + np.sin(ang) * r

        tangent = np.stack([-np.sin(ang), np.cos(ang)], axis=1)
        outward = np.stack([np.cos(ang), np.sin(ang)], axis=1)
        mult = np.random.uniform(0.4, 1.7, (count, 1)).astype(np.float32)
        self.vel[idx] = (tangent * 0.9 + outward * 0.45) * speed * mult

        ttl = np.random.uniform(life[0], life[1], count).astype(np.float32)
        self.ttl[idx] = ttl
        self.max_ttl[idx] = ttl
        self.size[idx] = np.random.uniform(1.3, 3.8, count)

    def update(self, dt: float, cx, cy, pull: float = 80.0, swirl: float = 55.0,
               damping: float = 1.9) -> None:
        if not np.any(self.ttl > 0):
            return

        d = np.empty_like(self.pos)
        d[:, 0] = float(cx) - self.pos[:, 0]
        d[:, 1] = float(cy) - self.pos[:, 1]
        dist = np.sqrt((d ** 2).sum(axis=1))[:, None] + 1e-3
        toward = d / dist
        tangent = np.stack([-toward[:, 1], toward[:, 0]], axis=1)

        self.vel += (toward * pull + tangent * swirl) * dt
        self.vel *= max(0.0, 1.0 - damping * dt)
        self.pos += self.vel * dt
        self.ttl -= dt

    def draw(self, layer, color, gain: float = 1.0) -> None:
        for i in np.nonzero(self.ttl > 0)[0]:
            life = float(self.ttl[i] / max(float(self.max_ttl[i]), 1e-3))
            radius = int(max(1.0, float(self.size[i]) * (0.6 + 0.9 * life)))
            tint = scale_color(color, gain * (0.25 + 0.75 * life))
            cv2.circle(layer, (int(self.pos[i, 0]), int(self.pos[i, 1])),
                       radius, tint, -1, cv2.LINE_AA)


# ------------------------------------------------------------------ şok dalgası
class ShockwaveField:
    """Jestlerle tetiklenen genişleyen halkalar."""

    def __init__(self) -> None:
        self.waves: list[dict] = []

    def burst(self, cx, cy, max_radius, color, life: float = config.SHOCKWAVE_LIFE,
              thickness: float = 7.0) -> None:
        self.waves.append(
            dict(x=float(cx), y=float(cy), r=float(max_radius), t=0.0,
                 life=max(life, 0.05), color=color, w=thickness)
        )

    def clear(self) -> None:
        self.waves.clear()

    def update(self, dt: float) -> None:
        for wave in self.waves:
            wave["t"] += dt
        self.waves = [w for w in self.waves if w["t"] < w["life"]]

    def draw(self, layer) -> None:
        h, w = layer.shape[:2]
        for wave in self.waves:
            p = min(1.0, wave["t"] / wave["life"])
            radius = int(wave["r"] * (1.0 - (1.0 - p) ** 2.4))
            if radius < 2:
                continue
            alpha = (1.0 - p) ** 1.6
            thickness = max(1, int(wave["w"] * (1.0 - p) + 1))
            center = (int(wave["x"]), int(wave["y"]))

            # yumuşak hale
            cv2.circle(layer, center, radius, scale_color(wave["color"], alpha * 0.30),
                       thickness * 4, cv2.LINE_AA)

            # birkaç iç içe dalgalanma (tek mükemmel halka yerine enerji ripple'ı)
            for k, (rel, atten) in enumerate(((1.0, 1.0), (0.965, 0.55), (0.93, 0.3))):
                r = max(2, int(radius * rel))
                cv2.circle(layer, center, r, scale_color(wave["color"], alpha * atten),
                           max(1, thickness - k), cv2.LINE_AA)

            flash = (1.0 - p) ** 3
            if flash > 0.03:
                add_radial(layer, wave["x"], wave["y"], int(wave["r"] * 0.26),
                           wave["color"], power=2.2, gain=0.28 * flash)

            # halka ekran dışına taşarsa çizim maliyetini kıs
            if radius > max(h, w):
                wave["t"] = wave["life"]


# ------------------------------------------------------------------ yay fiziği
class Spring:
    """Kritik sönümlemeye yakın tek boyutlu yay.

    `smooth()` sadece hedefe doğru sönerek yaklaşır; yay ise hız kazanıp
    hafifçe aşabilir. Hologramın "ağırlığı" buradan gelir. Kare süresi ne
    olursa olsun kararlı kalsın diye içeride sabit alt adımlarla entegre edilir.
    """

    __slots__ = ("value", "target", "velocity", "stiffness", "damping")

    def __init__(self, value: float = 0.0, stiffness: float = 180.0,
                 damping: float = 24.0) -> None:
        self.value = float(value)
        self.target = float(value)
        self.velocity = 0.0
        self.stiffness = float(stiffness)
        self.damping = float(damping)

    def set(self, value: float) -> None:
        """Işınla: değeri ve hedefi anında eşitle (el ilk göründüğünde)."""
        self.value = self.target = float(value)
        self.velocity = 0.0

    def update(self, dt: float) -> float:
        dt = min(max(float(dt), 0.0), 0.1)
        steps = max(1, int(math.ceil(dt * 240.0)))
        h = dt / steps
        for _ in range(steps):
            acc = (self.target - self.value) * self.stiffness - self.velocity * self.damping
            self.velocity += acc * h
            self.value += self.velocity * h
        return self.value

    def nudge(self, amount: float) -> None:
        self.velocity += float(amount)


class Spring2:
    """İki boyutlu yay (konum, hız vektörü ile birlikte)."""

    __slots__ = ("value", "target", "velocity", "stiffness", "damping")

    def __init__(self, x: float = 0.0, y: float = 0.0, stiffness: float = 200.0,
                 damping: float = 26.0) -> None:
        self.value = np.array([x, y], np.float32)
        self.target = self.value.copy()
        self.velocity = np.zeros(2, np.float32)
        self.stiffness = float(stiffness)
        self.damping = float(damping)

    def set(self, x, y) -> None:
        self.value[:] = (float(x), float(y))
        self.target[:] = self.value
        self.velocity[:] = 0.0

    def aim(self, x, y) -> None:
        self.target[:] = (float(x), float(y))

    def update(self, dt: float) -> np.ndarray:
        dt = min(max(float(dt), 0.0), 0.1)
        steps = max(1, int(math.ceil(dt * 240.0)))
        h = dt / steps
        for _ in range(steps):
            acc = (self.target - self.value) * self.stiffness - self.velocity * self.damping
            self.velocity += acc * h
            self.value += self.velocity * h
        return self.value


# ------------------------------------------------------------------ el maskesi
# Her parmak için landmark zinciri (0 = bilek).
FINGER_CHAINS = (
    (0, 1, 2, 3, 4),
    (0, 5, 6, 7, 8),
    (0, 9, 10, 11, 12),
    (0, 13, 14, 15, 16),
    (0, 17, 18, 19, 20),
)


def hands_mask(shape, hands, feather: int | None = None,
               grow: int | None = None) -> np.ndarray:
    """Ellerin silüetini 0..255 maskeye çizer (avuç + parmaklar).

    Convex hull kullanmıyoruz: parmakların arasındaki boşluk gerçekte el
    olmadığı için oradaki efektin kesilmemesi gerekir.
    """
    h, w = shape[:2]
    mask = np.zeros((h, w), np.uint8)
    if not hands:
        return mask

    for hand in hands:
        pts = hand.landmarks
        palm = pts[[0, 5, 9, 13, 17]].astype(np.int32)
        cv2.fillConvexPoly(mask, palm, 255)
        palm_r = max(4, int(hand.palm_size * 0.36))
        cv2.circle(mask, (int(hand.center[0]), int(hand.center[1])), palm_r, 255, -1)

        thickness = max(5, int(hand.palm_size * 0.19))
        for chain in FINGER_CHAINS:
            cv2.polylines(mask, [pts[list(chain)].astype(np.int32)], False,
                          255, thickness, cv2.LINE_AA)

    grow = config.HAND_MASK_GROW if grow is None else grow
    if grow > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow * 2 + 1, grow * 2 + 1))
        mask = cv2.dilate(mask, kernel)

    feather = config.HAND_MASK_FEATHER if feather is None else feather
    if feather > 0:
        # Kutu bulanıklaştırma, aynı yumuşaklığı GaussianBlur'dan ~6x hızlı verir.
        k = feather * 2 + 1
        mask = cv2.blur(mask, (k, k))
    return mask


def apply_hand_mask(layer: np.ndarray, mask: np.ndarray) -> None:
    """Maskenin içini katmandan siler; efektler ellerin arkasında kalır."""
    if mask is None:
        return
    inverse = cv2.bitwise_not(mask)
    inv3 = cv2.merge([inverse, inverse, inverse])
    cv2.multiply(layer, inv3, dst=layer, scale=1.0 / 255.0)


# ------------------------------------------------------------------ afterimage
class Afterimage:
    """Önceki kareleri hafifçe soldurup birleştirir: hareket izi bırakır."""

    def __init__(self, decay: float = config.AFTERIMAGE_DECAY) -> None:
        self.decay = float(decay)
        self.buffer: np.ndarray | None = None

    def reset(self) -> None:
        """Tamponu temizle; mod geçişlerinde hayalet iz bırakmaz."""
        if self.buffer is not None:
            self.buffer[:] = 0

    def apply(self, layer: np.ndarray) -> np.ndarray:
        if self.buffer is None or self.buffer.shape != layer.shape:
            self.buffer = layer.copy()
        else:
            cv2.convertScaleAbs(self.buffer, dst=self.buffer, alpha=self.decay)
            cv2.max(self.buffer, layer, dst=self.buffer)
        return self.buffer


# ------------------------------------------------------------------ post-process
class PostFX:
    """Bloom sonrası ince görüntü işleme: kroma kayması, grain, vinyet, tarama."""

    def __init__(self) -> None:
        self._shape: tuple[int, int] | None = None
        self._grade: np.ndarray | None = None
        self._grain_bank: list[np.ndarray] = []
        self._grain_index = 0

    def _build(self, shape) -> None:
        h, w = int(shape[0]), int(shape[1])
        yy, xx = np.mgrid[-1.0:1.0:h * 1j, -1.0:1.0:w * 1j]
        d = np.sqrt((xx * xx + yy * yy) * 0.5)
        falloff = np.clip(1.0 - config.POSTFX_VIGNETTE * (d ** 2.2), 0.0, 1.0)
        vignette = (falloff * 255.0)[:, :, None].astype(np.uint8)

        rows = np.ones((h, 1, 1), np.float32)
        rows[1::2] = 1.0 - config.POSTFX_SCANLINE
        scan = np.repeat((rows * 255.0).astype(np.uint8), w, axis=1)

        # Vinyet ve taramayı tek maskede birleştir: kare başına tek çarpma.
        self._grade = cv2.multiply(cv2.merge([vignette] * 3), cv2.merge([scan] * 3),
                                   scale=1.0 / 255.0)

        # Grain dokularını bir kez üret, her karede sırayla kullan.
        self._grain_bank = []
        grain = int(config.POSTFX_GRAIN)
        if grain > 0:
            for _ in range(5):
                noise = np.random.randint(0, grain + 1, (max(1, h // 3), max(1, w // 3), 3),
                                          np.uint8)
                noise = cv2.resize(noise, (w, h), interpolation=cv2.INTER_NEAREST)
                self._grain_bank.append(noise)
        self._shape = (h, w)

    def apply(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if self._shape != (h, w):
            self._build(frame.shape)

        # kroma kayması: kanalları ayırmadan, görünümler üzerinden kaydır
        shift = int(config.POSTFX_CHROMA)
        if 0 < shift < w:
            frame[:, shift:, 2] = frame[:, :-shift, 2].copy()
            frame[:, :-shift, 0] = frame[:, shift:, 0].copy()

        if self._grain_bank:
            self._grain_index = (self._grain_index + 1) % len(self._grain_bank)
            cv2.subtract(frame, self._grain_bank[self._grain_index], dst=frame)

        cv2.multiply(frame, self._grade, dst=frame, scale=1.0 / 255.0)
        return frame


# ------------------------------------------------------------------ yardımcı
def midpoint(p1, p2):
    return (float(p1[0]) + float(p2[0])) * 0.5, (float(p1[1]) + float(p2[1])) * 0.5


def smooth(current, target, dt: float, speed: float = 14.0):
    k = 1.0 - math.exp(-speed * dt)
    return current + (target - current) * k


def smoothstep(x: float) -> float:
    """0..1 aralığında yumuşak giriş/çıkış eğrisi."""
    x = min(1.0, max(0.0, float(x)))
    return x * x * (3.0 - 2.0 * x)


def ease_out_cubic(x: float) -> float:
    x = min(1.0, max(0.0, float(x)))
    return 1.0 - (1.0 - x) ** 3


def move_toward(current: float, target: float, delta: float) -> float:
    """Hedefe sabit adımla yaklaş (aşmadan)."""
    if current < target:
        return min(target, current + delta)
    return max(target, current - delta)

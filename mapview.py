"""Türkmenistan hologram haritası.

`T` ile açılır. Harita gerçek sınır verisinden gelir (`data/turkmenistan.json`,
54 nokta). Tek elle avucu takip eder ve avuç açıklığıyla büyür/küçülür; iki
elle aradaki mesafe ölçeği belirler.

`A` ile Aşkabat'taki Bagt Köşgi (Düğün Sarayı) hologramı yerden yükselerek
oluşur. Harita her zaman yeşil bir hologramdır.

Konum ve ölçek `fx.Spring` ile yumuşatılır; açılış/kapanış ise kare süresinden
bağımsız yumuşak bir eğriyle yapılır. Böylece harita savrulmadan yerine oturur
ve ani mod geçişlerinde hayalet iz kalmaz.
"""

from __future__ import annotations

import json
import os

import cv2
import numpy as np

import config
import fx

_FONT = cv2.FONT_HERSHEY_DUPLEX
_SMALL = cv2.FONT_HERSHEY_SIMPLEX

# Bu sabit, veri üretilirken kullanılan en/boy oranından gelir (x yarıçapı).
ASPECT_X = 1.459


class TurkmenistanMap:
    """Sahneye additive çizilen, elle kontrol edilen yeşil hologram harita."""

    name = "MAP"
    mask_hands = False  # elin önünde durur (avuçtan çıkıyormuş gibi)

    def __init__(self, path: str | None = None) -> None:
        if path is None:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.MAP_FILE)
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)

        self.rings = [np.asarray(ring, np.float32) for ring in data["rings"]]
        self.cities = data["cities"]
        self._ashgabat = next(
            (city for city in self.cities if city["name"].upper() == "ASHGABAT"), None
        )

        self.visible = False
        self.t = 0.0
        self._placed = False
        self._pending_reset = False

        # 0..1 arası yumuşatılmış görünürlük (açılış/kapanış animasyonu).
        self._reveal = 0.0
        self._open_time = 0.0

        self.center = fx.Spring2(config.FRAME_WIDTH * 0.5, config.FRAME_HEIGHT * 0.5,
                                 stiffness=190.0, damping=25.0)
        self.size = fx.Spring(config.MAP_SCALE_DEFAULT, stiffness=85.0, damping=16.0)

        # Açık avuçta hedef sürekli zıplamasın: el ölçülerini yumuşat.
        self._open_smooth: float | None = None
        self._dist_smooth: float | None = None

        self._scratch: np.ndarray | None = None
        self._body: np.ndarray | None = None
        self._mask: np.ndarray | None = None

        # Aşkabat binası (Bagt Köşgi) durumu.
        self.building_visible = False
        self._build = 0.0
        self._build_scratch: np.ndarray | None = None
        self._build_clip: np.ndarray | None = None
        self._build_mask: np.ndarray | None = None

    # ------------------------------------------------------------- kontrol
    def toggle(self) -> bool:
        self.visible = not self.visible
        if self.visible:
            self._pending_reset = True
            self._open_time = 0.0
        else:
            self.hide_building()
        return self.visible

    def open(self) -> None:
        """Haritayı aç (zaten açıksa hiçbir şey yapma)."""
        if not self.visible:
            self.visible = True
            self._pending_reset = True
            self._open_time = 0.0

    def active(self) -> bool:
        """Kapanış animasyonu bitene kadar sahneyi haritaya bırakır."""
        return self.visible or self._reveal > 0.015

    def toggle_building(self) -> bool:
        self.building_visible = not self.building_visible
        return self.building_visible

    def hide_building(self) -> None:
        self.building_visible = False

    def reset(self, width: int, height: int) -> None:
        self.center.set(width * 0.5, height * 0.5)
        self.size.set(config.MAP_SCALE_DEFAULT)
        self._open_smooth = None
        self._dist_smooth = None

    def percent(self) -> int:
        return int(round(self.size.value / config.MAP_SCALE_DEFAULT * 100.0))

    # ------------------------------------------------------------- güncelle
    def update(self, dt: float, hands, shape) -> None:
        h, w = shape[:2]
        if not self._placed:
            self.reset(w, h)
            self._placed = True

        if self._pending_reset:
            self.reset(w, h)
            self._pending_reset = False

        self.t += dt

        # Aç/kapa: yay yerine sabit hızlı, sonra smoothstep ile yumuşatılan geçiş.
        if self.visible:
            self._open_time += dt
            self._reveal = fx.move_toward(
                self._reveal, 1.0, dt / max(config.MAP_REVEAL_TIME, 1e-3)
            )
        else:
            self._reveal = fx.move_toward(
                self._reveal, 0.0, dt / max(config.MAP_HIDE_TIME, 1e-3)
            )

        # Bina: yerden yükselme / geri çekilme.
        build_delta = dt / max(config.MAP_BUILDING_REVEAL, 1e-3)
        target = 1.0 if self.building_visible else 0.0
        self._build = fx.move_toward(self._build, target, build_delta)

        if not self.visible:
            return

        target_center = None
        target_scale = float(self.size.value)

        if len(hands) >= 2:
            a, b = hands[0].center, hands[1].center
            dist = float(np.linalg.norm(a - b))
            if self._dist_smooth is None:
                self._dist_smooth = dist
            else:
                self._dist_smooth = fx.smooth(
                    self._dist_smooth, dist, dt, config.MAP_HAND_SMOOTHING
                )
            target_scale = float(np.clip(self._dist_smooth * config.MAP_SCALE_PER_DISTANCE,
                                         config.MAP_SCALE_MIN, config.MAP_SCALE_MAX))
            # Açık eller sadece ölçekler; taşımak için yumruk gerekir.
            if config.MAP_FOLLOW_OPEN_HAND or any(h.grab for h in hands):
                target_center = fx.midpoint(a, b)
        elif hands:
            hand = hands[0]
            if hand.grab:
                # Yumruk = taşı; boyut olduğu gibi kalsın.
                target_scale = float(self.size.value)
                target_center = (float(hand.center[0]), float(hand.center[1]))
            else:
                if self._open_smooth is None:
                    self._open_smooth = float(hand.openness)
                else:
                    self._open_smooth = fx.smooth(
                        self._open_smooth, float(hand.openness), dt,
                        config.MAP_HAND_SMOOTHING
                    )
                target_scale = float(np.clip(
                    config.MAP_SCALE_MIN + self._open_smooth * (config.MAP_SCALE_MAX - config.MAP_SCALE_MIN),
                    config.MAP_SCALE_MIN, config.MAP_SCALE_MAX))
                if config.MAP_FOLLOW_OPEN_HAND:
                    target_center = (float(hand.center[0]), float(hand.center[1]))

        if target_center is not None:
            half_w = ASPECT_X * target_scale * 0.98
            half_h = target_scale * 0.98
            cx = float(np.clip(target_center[0], min(half_w, w * 0.5), max(w - half_w, w * 0.5)))
            cy = float(np.clip(target_center[1], min(half_h, h * 0.5), max(h - half_h, h * 0.5)))
            self.center.aim(cx, cy)

        self.size.target = target_scale
        self.center.update(dt)
        self.size.update(dt)

    # ---------------------------------------------------------------- çizim
    def draw(self, layer, hands=None, charge: float = 0.0) -> None:
        if self._reveal < 0.01:
            return

        h, w = layer.shape[:2]
        if self._scratch is None or self._scratch.shape != layer.shape:
            self._scratch = np.zeros_like(layer)
            self._body = np.zeros_like(layer)
            self._mask = np.zeros((h, w), np.uint8)
            self._build_scratch = np.zeros_like(layer)
            self._build_clip = np.zeros_like(layer)
            self._build_mask = np.zeros((h, w), np.uint8)
        self._scratch[:] = 0
        self._mask[:] = 0

        alpha = fx.smoothstep(self._reveal)
        deep, mid, bright, core = config.MAP_PALETTE
        cx, cy = float(self.center.value[0]), float(self.center.value[1])

        # Açılırken hafif büyüyerek yerine oturur.
        pop = 0.90 + 0.10 * fx.ease_out_cubic(alpha)
        scale = float(self.size.value) * pop

        # --- gövde: dolgu + ızgara + tarama çizgisi (sonra maskeyle kırpılır)
        polys = []
        for ring in self.rings:
            pts = np.empty_like(ring)
            pts[:, 0] = cx + ring[:, 0] * scale
            pts[:, 1] = cy + ring[:, 1] * scale
            polys.append(np.round(pts).astype(np.int32))

        cv2.fillPoly(self._mask, polys, 255)
        cv2.fillPoly(self._scratch, polys, fx.scale_color(deep, 0.20 * alpha))

        grid_color = fx.scale_color(mid, 0.24 * alpha)
        span = 1.02
        step = config.MAP_GRID
        steps = int(span / step) + 1
        left = int(cx - ASPECT_X * scale * span)
        right = int(cx + ASPECT_X * scale * span)
        top = int(cy - scale * span)
        bottom = int(cy + scale * span)
        for i in range(-steps, steps + 1):
            gx = int(cx + i * step * scale)
            gy = int(cy + i * step * scale)
            if left <= gx <= right:
                cv2.line(self._scratch, (gx, top), (gx, bottom), grid_color, 1, cv2.LINE_AA)
            if top <= gy <= bottom:
                cv2.line(self._scratch, (left, gy), (right, gy), grid_color, 1, cv2.LINE_AA)

        # yukarıdan aşağı süpüren tarama bandı
        sweep = (self._open_time * 0.42) % 2.0 - 1.0
        sy = int(cy + sweep * scale)
        band = int(max(2, scale * 0.010))
        cv2.line(self._scratch, (left, sy), (right, sy),
                 fx.scale_color(core, 0.38 * alpha), band, cv2.LINE_AA)
        for k in (2, 5, 9):
            cv2.line(self._scratch, (left, sy - k * band), (right, sy - k * band),
                     fx.scale_color(bright, 0.06 * alpha), band, cv2.LINE_AA)

        # Not: cv2.bitwise_and'te src=dst kullanmak maskeyi yok sayar; ayrı tampon şart.
        cv2.bitwise_and(self._scratch, self._scratch, dst=self._body, mask=self._mask)
        cv2.add(layer, self._body, dst=layer)

        # --- sınır çizgisi: kalın soluk taban + ince parlak çizgi
        for pts in polys:
            cv2.polylines(layer, [pts], True,
                          fx.scale_color(mid, 0.48 * alpha), 9, cv2.LINE_AA)
            cv2.polylines(layer, [pts], True,
                          fx.scale_color(bright, 0.98 * alpha), 2, cv2.LINE_AA)

        # --- şehirler
        building_on = self._build > 0.04
        for index, city in enumerate(self.cities):
            px = int(cx + city["x"] * scale)
            py = int(cy + city["y"] * scale)
            pulse = 0.72 + 0.28 * np.sin(self.t * 2.4 + index * 1.7)
            fx.add_radial(layer, px, py, max(5, int(scale * 0.034)), core,
                          power=1.8, gain=0.75 * alpha * pulse)
            cv2.circle(layer, (px, py), 2, fx.scale_color(core, alpha), -1, cv2.LINE_AA)

            if building_on and city is self._ashgabat:
                continue  # bina etiketi binanın üstüne yazılır

            label = city["name"]
            if city["x"] > 0.55:  # sağ kenara yakın: etiketi sola yaz
                size = cv2.getTextSize(label, _SMALL, 0.34, 1)[0]
                tx = px - size[0] - 7
            else:
                tx = px + 7
            cv2.putText(layer, label, (tx, py + 11), _SMALL, 0.34,
                        fx.scale_color(mid, 0.95 * alpha), 1, cv2.LINE_AA)

        # --- Aşkabat binası
        if config.MAP_BUILDING_ENABLED:
            self._draw_building(layer, alpha, scale, cx, cy)

        # --- köşe braketleri
        x0 = int(cx - ASPECT_X * scale) - 14
        x1 = int(cx + ASPECT_X * scale) + 14
        y0 = int(cy - scale) - 16
        y1 = int(cy + scale) + 14
        tick = 24
        bracket = fx.scale_color(mid, 0.8 * alpha)
        for (bx, by, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1),
                                 (x0, y1, 1, -1), (x1, y1, -1, -1)):
            cv2.line(layer, (bx, by), (bx + dx * tick, by), bracket, 2, cv2.LINE_AA)
            cv2.line(layer, (bx, by), (bx, by + dy * tick), bracket, 2, cv2.LINE_AA)

        # --- başlık / durum
        title = "TURKMENISTAN"
        tsize = cv2.getTextSize(title, _FONT, 0.72, 1)[0]
        tx = int(cx - tsize[0] * 0.5)
        ty = max(24, y0 - 12)
        cv2.putText(layer, title, (tx, ty), _FONT, 0.72,
                    fx.scale_color(core, alpha), 1, cv2.LINE_AA)
        cv2.putText(layer, f"{self.percent()}%", (tx + tsize[0] + 14, ty), _FONT, 0.5,
                    fx.scale_color(mid, alpha), 1, cv2.LINE_AA)
        cv2.putText(layer, "2 HANDS: SCALE   FIST: DRAG   A: BUILDING   T: CLOSE",
                    (tx, ty + 18), _SMALL, 0.38,
                    fx.scale_color(mid, 0.80 * alpha), 1, cv2.LINE_AA)

        # --- kuzey oku
        ax = x1 - 6
        ay = y0 + 10
        cv2.line(layer, (ax, ay), (ax, ay - 26), fx.scale_color(bright, alpha), 2, cv2.LINE_AA)
        cv2.line(layer, (ax, ay - 26), (ax - 5, ay - 18), fx.scale_color(bright, alpha), 2, cv2.LINE_AA)
        cv2.line(layer, (ax, ay - 26), (ax + 5, ay - 18), fx.scale_color(bright, alpha), 2, cv2.LINE_AA)
        cv2.putText(layer, "N", (ax - 5, ay - 32), _SMALL, 0.38,
                    fx.scale_color(mid, alpha), 1, cv2.LINE_AA)

    # ------------------------------------------------------------- bina
    def _draw_building(self, layer, alpha: float, scale: float, cx: float, cy: float) -> None:
        """Bagt Köşgi'yi (Aşkabat Düğün Sarayı) yerden yükselterek çizer."""
        if self._ashgabat is None or self._build <= 0.01:
            return

        h, w = layer.shape[:2]
        if self._build_scratch is None or self._build_scratch.shape != layer.shape:
            self._build_scratch = np.zeros_like(layer)
            self._build_clip = np.zeros_like(layer)
            self._build_mask = np.zeros((h, w), np.uint8)
        self._build_scratch[:] = 0
        self._build_mask[:] = 0

        deep, mid, bright, core = config.MAP_PALETTE
        bx = float(cx + self._ashgabat["x"] * scale)
        by = float(cy + self._ashgabat["y"] * scale)

        bh = max(48.0, scale * config.MAP_BUILDING_HEIGHT)
        bw = bh * 0.55
        p = fx.ease_out_cubic(self._build)
        g = self._build_scratch
        a = alpha

        def pt(lx: float, ly: float) -> tuple[int, int]:
            return int(round(bx + lx * bw)), int(round(by - ly * bh))

        def line(lx1, ly1, lx2, ly2, color, thickness=1) -> None:
            cv2.line(g, pt(lx1, ly1), pt(lx2, ly2), color, thickness, cv2.LINE_AA)

        def rect(x0, y0, x1, y1, color, thickness=1) -> None:
            cv2.rectangle(g, pt(x0, y1), pt(x1, y0), color, thickness, cv2.LINE_AA)

        # zemin ışıması ve platform
        fx.add_radial(g, bx, by - bh * 0.10, int(bh * 0.95), mid,
                      power=2.6, gain=0.14 * a * p)
        cv2.ellipse(g, (int(bx), int(by)), (int(bw * 1.35), max(3, int(bh * 0.045))),
                    0, 0, 360, fx.scale_color(mid, 0.80 * a), 2, cv2.LINE_AA)
        cv2.ellipse(g, (int(bx), int(by - bh * 0.035)),
                    (int(bw * 1.10), max(2, int(bh * 0.032))),
                    0, 0, 360, fx.scale_color(deep, 2.0 * a), 1, cv2.LINE_AA)

        bright_c = fx.scale_color(bright, 0.95 * a)
        mid_c = fx.scale_color(mid, 0.92 * a)
        core_c = fx.scale_color(core, a)

        # yan kanatlar
        for side in (-1.0, 1.0):
            x_in = side * 0.58
            x_out = side * 1.12
            rect(x_in, 0.0, x_out, 0.34, mid_c, 1)
            for band in (0.09, 0.18, 0.27):
                line(x_in, band, x_out, band, mid_c, 1)
            # kanat pencereleri
            for k in range(3):
                wx = side * (0.70 + 0.14 * k)
                line(wx, 0.04, wx, 0.30, fx.scale_color(deep, 2.2 * a), 1)

        # ana cephe
        rect(-0.58, 0.0, 0.58, 0.50, bright_c, 2)
        for band in (0.08, 0.16, 0.24, 0.32, 0.40, 0.48):
            line(-0.58, band, 0.58, band, mid_c, 1)
        for col in (-0.46, -0.28, -0.10, 0.10, 0.28, 0.46):
            line(col, 0.0, col, 0.48, mid_c, 1)

        # kemerli giriş
        arch_w = int(bw * 0.20)
        arch_h = int(bh * 0.16)
        cv2.ellipse(g, (int(bx), int(by - bh * 0.08)), (arch_w, arch_h),
                    0, 180, 360, core_c, 2, cv2.LINE_AA)
        line(-0.20, 0.0, -0.20, 0.08, core_c, 2)
        line(0.20, 0.0, 0.20, 0.08, core_c, 2)

        # orta kule (yukarı doğru daralan)
        line(-0.34, 0.50, -0.20, 0.82, bright_c, 2)
        line(0.34, 0.50, 0.20, 0.82, bright_c, 2)
        for band in (0.58, 0.66, 0.74):
            t = (band - 0.50) / 0.32
            half = 0.34 + (0.20 - 0.34) * t
            line(-half, band, half, band, mid_c, 1)

        # kubbe ve ışık halkaları
        dome_cy = by - bh * 0.86
        dome_r = max(6, int(bw * 0.28))
        cv2.circle(g, (int(bx), int(dome_cy)), dome_r, core_c, 2, cv2.LINE_AA)
        cv2.ellipse(g, (int(bx), int(dome_cy)), (dome_r, max(2, dome_r // 3)),
                    0, 0, 360, mid_c, 1, cv2.LINE_AA)
        cv2.ellipse(g, (int(bx), int(dome_cy)), (max(2, dome_r // 3), dome_r),
                    0, 0, 360, mid_c, 1, cv2.LINE_AA)
        fx.add_radial(g, bx, dome_cy, max(8, dome_r * 2), bright,
                      power=2.2, gain=0.34 * a * p)

        # tepe iğnesi ve bayrak
        line(0.0, 0.98, 0.0, 1.12, bright_c, 2)
        line(0.0, 1.12, 0.14, 1.08, core_c, 1)
        line(0.14, 1.08, 0.0, 1.04, core_c, 1)

        # yapı çizgisi maskesi: bina yerden yukarı doğru oluşur
        cut_y = int(round(by - bh * 1.16 * p))
        x_left = max(0, int(bx - bw * 1.45))
        x_right = min(w, int(bx + bw * 1.45) + 1)
        y_top = max(0, cut_y)
        y_bottom = min(h, int(by) + 4)
        if y_top < y_bottom:
            self._build_mask[y_top:y_bottom, x_left:x_right] = 255

        cv2.bitwise_and(self._build_scratch, self._build_scratch,
                        dst=self._build_clip, mask=self._build_mask)
        cv2.add(layer, self._build_clip, dst=layer)

        # yükselme anındaki parlak inşaat çizgisi
        if p < 0.995 and y_top < y_bottom:
            cv2.line(layer, (x_left, y_top), (x_right, y_top),
                     fx.scale_color(core, a * 0.85), 2, cv2.LINE_AA)
            fx.add_radial(layer, bx, y_top, int(bw * 1.3), bright,
                          power=2.2, gain=0.35 * a * (1.0 - p))

        # etiket
        if p > 0.65:
            label = "BAGT KOSHGI / ASHGABAT"
            size = cv2.getTextSize(label, _SMALL, 0.34, 1)[0]
            ly = int(by - bh * 1.20)
            cv2.putText(layer, label, (int(bx - size[0] * 0.5), ly),
                        _SMALL, 0.34, fx.scale_color(core, a * min(1.0, (p - 0.65) / 0.35)),
                        1, cv2.LINE_AA)

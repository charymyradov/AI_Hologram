"""Holografik efektler.

Her efektin iki metodu var:
  update(dt, hands, charge) -> kendi iç durumunu (parçacık, yumuşatma) günceller
  draw(layer, hands, charge, palette) -> siyah katmana additive çizer

Katman `main.py` içinde bloom ile birleştirilir.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

import config
import fx


class Effect:
    name = "?"
    needs = 0  # gereken el sayısı (HUD ipucu için)

    def update(self, dt: float, hands, charge: float = 0.0) -> None:
        pass

    def draw(self, layer, hands, charge: float, palette) -> None:
        pass


# ====================================================================== ORB
class OrbEffect(Effect):
    """İki avuç arasında nefes alan enerji küresi + yörünge halkaları."""

    name = "ORB"
    needs = 2

    def __init__(self) -> None:
        self.t = 0.0
        self.cx: float | None = None
        self.cy: float | None = None
        self.radius = 70.0
        self.particles = fx.ParticleSystem(config.ORB_PARTICLES)
        self._carry = 0.0

    def update(self, dt: float, hands, charge: float = 0.0) -> None:
        self.t += dt

        if len(hands) < 2:
            if self.cx is not None:
                self.particles.update(dt, self.cx, self.cy, pull=45.0, swirl=30.0)
            return

        a, b = hands[0].center, hands[1].center
        cx, cy = fx.midpoint(a, b)
        dist = float(np.linalg.norm(a - b))
        target = float(np.clip(dist * config.ORB_RADIUS_FACTOR,
                               config.ORB_RADIUS_MIN, config.ORB_RADIUS_MAX))
        target *= (1.0 - 0.28 * charge)

        if self.cx is None:
            self.cx, self.cy, self.radius = cx, cy, target
        else:
            self.cx = fx.smooth(self.cx, cx, dt, 16.0)
            self.cy = fx.smooth(self.cy, cy, dt, 16.0)
            self.radius = fx.smooth(self.radius, target, dt, 10.0)

        self._carry += dt * (95.0 + 170.0 * charge)
        count = int(self._carry)
        if count:
            self._carry -= count
            self.particles.emit(self.cx, self.cy, self.radius,
                                count, speed=70.0 + 60.0 * charge)
        self.particles.update(dt, self.cx, self.cy, pull=85.0, swirl=60.0)

    def draw(self, layer, hands, charge: float, palette) -> None:
        if self.cx is None:
            return

        cx, cy = int(self.cx), int(self.cy)
        deep, mid, bright, core = palette
        pulse = 1.0 + 0.035 * math.sin(self.t * 4.2) + 0.09 * charge
        r = max(10, int(self.radius * pulse))

        # dış hale
        fx.add_radial(layer, cx, cy, int(r * 2.7), deep, power=3.4, gain=0.55)
        fx.add_radial(layer, cx, cy, int(r * 1.65), mid, power=2.5, gain=0.7)
        fx.add_radial(layer, cx, cy, int(r * 1.05), bright, power=2.2, gain=0.4)

        # küre gövdesi (merkezden kenara sönen dolgu)
        fx.add_radial(layer, cx, cy, int(r * 0.95), fx.scale_color(mid, 0.8),
                      power=1.2, gain=0.35)

        # yörünge halkaları
        angle = self.t * 95.0
        cv2.ellipse(layer, (cx, cy), (r, max(3, int(r * 0.30))), angle,
                    0, 360, fx.scale_color(bright, 0.85), 2, cv2.LINE_AA)
        cv2.ellipse(layer, (cx, cy), (max(3, int(r * 0.52)), r), -angle * 0.8,
                    0, 360, fx.scale_color(mid, 1.0), 2, cv2.LINE_AA)
        cv2.ellipse(layer, (cx, cy), (r, max(3, int(r * 0.72))), angle * 0.45,
                    0, 360, fx.scale_color(deep, 1.5), 1, cv2.LINE_AA)

        # halkaların üstünde dönen ışık noktaları
        for i, phase in enumerate((0.0, 2.1, 4.2)):
            a = math.radians(angle + phase * 57.3)
            ox = cx + int(math.cos(a) * r)
            oy = cy + int(math.sin(a) * r * 0.30)
            fx.add_radial(layer, ox, oy, max(4, r // 9), core, power=1.7, gain=0.9)

            a2 = math.radians(-angle * 0.8 + phase * 57.3)
            ox = cx + int(math.cos(a2) * r * 0.52)
            oy = cy + int(math.sin(a2) * r)
            fx.add_radial(layer, ox, oy, max(3, r // 11), bright, power=1.7, gain=0.6)

        # parçacıklar
        self.particles.draw(layer, bright, gain=0.85)

        # çekirdek
        fx.add_radial(layer, cx, cy, max(4, int(r * 0.42)), bright, power=2.2,
                      gain=0.55 + 0.35 * charge)
        fx.add_radial(layer, cx, cy, max(3, int(r * 0.16)), core, power=1.4, gain=1.0)


# =================================================================== PORTAL
class PortalEffect(Effect):
    """Tek avuç içinde dönen portal: iç içe halkalar, çentikler, kıvılcımlar."""

    name = "PORTAL"
    needs = 1

    def __init__(self) -> None:
        self.t = 0.0
        self.cx: float | None = None
        self.cy: float | None = None
        self.radius = 80.0
        self.particles = fx.ParticleSystem(config.PORTAL_PARTICLES)
        self._carry = 0.0

    def update(self, dt: float, hands, charge: float = 0.0) -> None:
        self.t += dt

        if not hands:
            self.cx = None
            return

        hand = hands[0]
        target = float(np.clip(config.PORTAL_RADIUS_MIN +
                               hand.openness * (config.PORTAL_RADIUS_MAX - config.PORTAL_RADIUS_MIN),
                               config.PORTAL_RADIUS_MIN, config.PORTAL_RADIUS_MAX))
        target *= (1.0 - 0.2 * charge)

        if self.cx is None:
            self.cx, self.cy, self.radius = float(hand.center[0]), float(hand.center[1]), target
        else:
            self.cx = fx.smooth(self.cx, float(hand.center[0]), dt, 16.0)
            self.cy = fx.smooth(self.cy, float(hand.center[1]), dt, 16.0)
            self.radius = fx.smooth(self.radius, target, dt, 8.0)

        self._carry += dt * (55.0 + 90.0 * hand.openness + 120.0 * charge)
        count = int(self._carry)
        if count:
            self._carry -= count
            self.particles.emit(self.cx, self.cy, self.radius, count,
                                speed=45.0 + 40.0 * hand.openness)

        self.particles.update(dt, self.cx, self.cy, pull=60.0, swirl=95.0)

    def draw(self, layer, hands, charge: float, palette) -> None:
        if self.cx is None:
            return

        cx, cy = int(self.cx), int(self.cy)
        deep, mid, bright, core = palette
        r = max(12, int(self.radius))

        fx.add_radial(layer, cx, cy, int(r * 1.9), deep, power=3.0, gain=0.45)
        fx.add_radial(layer, cx, cy, int(r * 1.15), mid, power=2.2, gain=0.35)
        fx.add_radial(layer, cx, cy, int(r * 0.55), core, power=2.0, gain=0.22)

        # iç içe, zıt yönlerde dönen yay parçaları
        for i in range(5):
            rr = r * (0.42 + 0.15 * i)
            spin = self.t * (55.0 + 22.0 * i) * (1.0 if i % 2 == 0 else -1.0)
            start = (spin + i * 47.0) % 360.0
            span = 250.0 - 18.0 * i
            color = fx.scale_color(bright if i % 2 == 0 else mid, 0.95 - 0.09 * i)
            cv2.ellipse(layer, (cx, cy), (int(rr), int(rr)), 0, start, start + span,
                        color, 2 if i < 3 else 1, cv2.LINE_AA)

            # yayın ucunda ışık düğümü
            a = math.radians(start)
            fx.add_radial(layer, cx + math.cos(a) * rr, cy + math.sin(a) * rr,
                          max(4, r // 12), core, power=1.8, gain=0.75)
            a = math.radians(start + span)
            fx.add_radial(layer, cx + math.cos(a) * rr, cy + math.sin(a) * rr,
                          max(3, r // 15), bright, power=1.8, gain=0.5)

        # dış halka çentikleri (rune hissi)
        ticks = 28
        for k in range(ticks):
            a = math.radians(k * (360.0 / ticks) + self.t * 18.0)
            r0 = r * (1.04 if k % 2 == 0 else 1.02)
            r1 = r * (1.14 if k % 4 == 0 else 1.08)
            p1 = (int(cx + math.cos(a) * r0), int(cy + math.sin(a) * r0))
            p2 = (int(cx + math.cos(a) * r1), int(cy + math.sin(a) * r1))
            cv2.line(layer, p1, p2, fx.scale_color(mid, 0.9), 1, cv2.LINE_AA)

        # avuç içi enerji akışı
        fx.add_radial(layer, cx, cy, max(5, int(r * 0.3)), bright, power=1.6,
                      gain=0.5 + 0.4 * charge)

        self.particles.draw(layer, bright, gain=0.7)

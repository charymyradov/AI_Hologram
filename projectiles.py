"""Fırlatılabilir enerji topları.

Eli hızlıca savurunca avuçtan bir top fırlar. Toplar duvarlardan ve avuçlardan
seker; avuçla vurdukça hız kazanır, ömrü bitince patlayıp şok dalgası bırakır.
"""

from __future__ import annotations

import math
import random

import cv2
import numpy as np

import config
import fx


class Projectile:
    """Tek bir enerji topu."""

    __slots__ = ("x", "y", "vx", "vy", "radius", "life", "max_life",
                 "color", "trail", "bounces", "grace")

    def __init__(self, x, y, vx, vy, radius, color, life):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.radius = float(radius)
        self.life = float(life)
        self.max_life = float(life)
        self.color = color
        self.trail: list[list[float]] = []
        self.bounces = 0
        self.grace = 0.18  # fırlatan avuçla hemen çarpışmayı engeller

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)


class ThrowableField:
    """Sahnedeki tüm topları, izlerini ve patlama parçacıklarını yönetir."""

    def __init__(self, on_pop=None) -> None:
        self.items: list[Projectile] = []
        self.particles = fx.ParticleSystem(420)
        self.on_pop = on_pop
        self.total_thrown = 0

    # ------------------------------------------------------------ üretim
    def spawn(self, x, y, vx, vy, color, radius: float | None = None) -> Projectile:
        if radius is None:
            radius = random.uniform(*config.THROW_RADIUS)

        if len(self.items) >= config.THROW_MAX:
            self._explode(self.items.pop(0), strength=0.55)

        item = Projectile(x, y, vx, vy, radius, color, config.THROW_LIFE)
        self.items.append(item)
        self.total_thrown += 1
        self.particles.emit(x, y, radius * 1.4, 16, speed=130.0, life=(0.2, 0.45))
        return item

    def clear(self) -> None:
        self.items.clear()

    # ------------------------------------------------------------- fizik
    def update(self, dt: float, hands, width: int, height: int) -> None:
        for item in list(self.items):
            item.vy += config.THROW_GRAVITY * dt
            item.x += item.vx * dt
            item.y += item.vy * dt
            item.life -= dt

            # iz (trail)
            item.trail.append([item.x, item.y, 1.0])
            for t in item.trail:
                t[2] -= dt * 3.2
            item.trail = [t for t in item.trail if t[2] > 0.02]
            if len(item.trail) > 16:
                item.trail.pop(0)

            self._bounce_walls(item, width, height)
            if item.grace > 0.0:
                item.grace -= dt
            else:
                self._bounce_hands(item, hands)

            if item.life <= 0:
                self.items.remove(item)
                self._explode(item, strength=1.0)

        # parçacıklar serbest uçar: çekim yok, sadece hafif sürtünme
        self.particles.update(dt, 0.0, 0.0, pull=0.0, swirl=0.0, damping=1.1)

    def _bounce_walls(self, item: Projectile, width: int, height: int) -> None:
        r = item.radius
        restitution = config.THROW_WALL_BOUNCE

        if item.x < r:
            item.x = r
            item.vx = abs(item.vx) * restitution
            self._sparks(item)
        elif item.x > width - r:
            item.x = width - r
            item.vx = -abs(item.vx) * restitution
            self._sparks(item)

        if item.y < r:
            item.y = r
            item.vy = abs(item.vy) * restitution
            self._sparks(item)
        elif item.y > height - r:
            item.y = height - r
            item.vy = -abs(item.vy) * restitution
            self._sparks(item)

    def _bounce_hands(self, item: Projectile, hands) -> None:
        for hand in hands:
            nx = item.x - float(hand.center[0])
            ny = item.y - float(hand.center[1])
            dist = math.hypot(nx, ny)
            hit_radius = item.radius + hand.palm_size * 0.42
            if dist >= hit_radius or dist < 1e-3:
                continue

            nx /= dist
            ny /= dist

            # topu avucun dışına it
            item.x = float(hand.center[0]) + nx * hit_radius
            item.y = float(hand.center[1]) + ny * hit_radius

            # gelen hızı yüzeye göre yansıt
            dot = item.vx * nx + item.vy * ny
            if dot < 0.0:
                item.vx -= 2.0 * dot * nx
                item.vy -= 2.0 * dot * ny

            # elin hareketi topa momentum ekler (vole)
            item.vx = item.vx * config.THROW_HAND_BOUNCE + float(hand.velocity[0]) * 0.5
            item.vy = item.vy * config.THROW_HAND_BOUNCE + float(hand.velocity[1]) * 0.5
            item.bounces += 1
            self._sparks(item, strength=1.6)

    # ---------------------------------------------------------- efektler
    def _sparks(self, item: Projectile, strength: float = 1.0) -> None:
        self.particles.emit(item.x, item.y, item.radius * 1.1,
                            int(5 * strength) + 2, speed=150.0, life=(0.12, 0.32))

    def _explode(self, item: Projectile, strength: float = 1.0) -> None:
        self.particles.emit(item.x, item.y, item.radius * 1.3,
                            int(30 * strength) + 6, speed=210.0 * strength,
                            life=(0.25, 0.7))
        if self.on_pop is not None:
            self.on_pop(item.x, item.y, 110.0 + 90.0 * strength, item.color)

    def draw(self, layer, color) -> None:
        for item in self.items:
            fade = min(1.0, item.life / 0.45)

            # iz: noktaları çizgiyle birleştir (hızlı topta kopukluk olmasın)
            prev = None
            for tx, ty, ta in item.trail:
                if prev is not None:
                    thickness = max(1, int(item.radius * 0.85 * ta))
                    cv2.line(layer, (int(prev[0]), int(prev[1])), (int(tx), int(ty)),
                             fx.scale_color(item.color, 0.42 * ta * fade),
                             thickness, cv2.LINE_AA)
                prev = (tx, ty, ta)

            # gövde
            fx.add_radial(layer, item.x, item.y, item.radius * 3.4,
                          item.color, power=2.8, gain=0.50 * fade)
            fx.add_radial(layer, item.x, item.y, item.radius * 1.7,
                          item.color, power=1.8, gain=0.90 * fade)
            cv2.circle(layer, (int(item.x), int(item.y)), int(item.radius * 1.18),
                       fx.scale_color(item.color, 0.85 * fade), 2, cv2.LINE_AA)
            fx.add_radial(layer, item.x, item.y, item.radius * 0.95,
                          (250, 248, 240), power=1.5, gain=0.9 * fade)
            cv2.circle(layer, (int(item.x), int(item.y)), max(2, int(item.radius * 0.5)),
                       fx.scale_color((255, 252, 245), fade), -1, cv2.LINE_AA)

        self.particles.draw(layer, color)

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


# ================================================================ LIGHTNING
def _bolt(p1, p2, depth: int = 5, jitter: float = 0.35) -> np.ndarray:
    """İki nokta arasında orta-nokta yer değiştirmeli yıldırım yolu üretir (vektörize)."""
    pts = np.array([p1, p2], np.float32)
    for _ in range(depth):
        a, b = pts[:-1], pts[1:]
        delta = b - a
        length = np.linalg.norm(delta, axis=1)
        normal = np.stack([-delta[:, 1], delta[:, 0]], axis=1) / (length[:, None] + 1e-6)
        offset = (np.random.rand(len(delta)) - 0.5) * length * jitter
        mids = (a + b) * 0.5 + normal * offset[:, None]

        out = np.empty((len(pts) * 2 - 1, 2), np.float32)
        out[0::2] = pts
        out[1::2] = mids
        pts = out
    return pts


class LightningEffect(Effect):
    """İki elin işaret parmakları arasında enerji akışı."""

    name = "LIGHTNING"
    needs = 2

    def __init__(self) -> None:
        self.t = 0.0
        self.particles = fx.ParticleSystem(240)
        self._rebuild = 0.0

    def update(self, dt: float, hands, charge: float = 0.0) -> None:
        self.t += dt
        self._rebuild -= dt
        if len(hands) >= 2:
            mid = fx.midpoint(hands[0].center, hands[1].center)
            if self._rebuild <= 0:
                self._rebuild = 0.05
                self.particles.emit(mid[0], mid[1], 26, 4, speed=60.0,
                                    life=(0.25, 0.6))
            self.particles.update(dt, mid[0], mid[1], pull=40.0, swirl=70.0)

    def draw(self, layer, hands, charge: float, palette) -> None:
        if len(hands) < 2:
            return

        deep, mid, bright, core = palette
        p1 = hands[0].fingertip(8)
        p2 = hands[1].fingertip(8)

        # geniş ve soluk taban çizgisi -> bloom ile yumuşak hale
        main = _bolt(p1, p2, depth=6, jitter=0.35)
        cv2.polylines(layer, [main.astype(np.int32)], False,
                      fx.scale_color(mid, 0.55), 9, cv2.LINE_AA)
        cv2.polylines(layer, [main.astype(np.int32)], False,
                      fx.scale_color(mid, 0.95), 4, cv2.LINE_AA)

        # dallanan yıldırımlar
        for branch in range(3):
            jitter = 0.45 - 0.07 * branch
            pts = _bolt(p1, p2, depth=6, jitter=jitter)
            color = core if branch == 0 else fx.scale_color(bright, 0.9 - 0.18 * branch)
            thickness = 2 if branch == 0 else 1
            cv2.polylines(layer, [pts.astype(np.int32)], False, color,
                          thickness, cv2.LINE_AA)

            # yol üzerinde kıvılcım düğümleri (bloom bunları haleye çevirir)
            for idx in range(6, len(pts) - 6, 11):
                cv2.circle(layer, (int(pts[idx][0]), int(pts[idx][1])), 3,
                           fx.scale_color(bright, 0.7), -1, cv2.LINE_AA)

        # uçlarda toplanan enerji
        for tip in (p1, p2):
            fx.add_radial(layer, tip[0], tip[1], 40, mid, power=2.4, gain=0.55)
            fx.add_radial(layer, tip[0], tip[1], 14, core, power=1.6, gain=1.0)

        self.particles.draw(layer, bright, gain=0.7)


# ==================================================================== HOLO
def _cube_geometry():
    v = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)],
                 np.float32)
    edges = []
    for i in range(8):
        for j in range(i + 1, 8):
            if bin(i ^ j).count("1") == 1:
                edges.append([i, j])
    return v, edges


def _torus_geometry(seg_u: int = 26, seg_v: int = 12, big: float = 0.95, small: float = 0.38):
    verts = []
    grid = []
    for i in range(seg_u):
        u = 2.0 * math.pi * i / seg_u
        row = []
        for j in range(seg_v):
            v = 2.0 * math.pi * j / seg_v
            x = (big + small * math.cos(v)) * math.cos(u)
            y = small * math.sin(v)
            z = (big + small * math.cos(v)) * math.sin(u)
            row.append(len(verts))
            verts.append([x, y, z])
        grid.append(row)

    paths = []
    for i in range(seg_u):
        paths.append([grid[i][j] for j in range(seg_v)] + [grid[i][0]])
    for j in range(seg_v):
        paths.append([grid[i][j] for i in range(seg_u)] + [grid[0][j]])
    return np.array(verts, np.float32), paths


def _dna_geometry(steps: int = 46, radius: float = 0.55, height: float = 1.6):
    verts = []
    helix_a, helix_b = [], []
    for i in range(steps):
        p = i / (steps - 1)
        ang = p * 4.0 * math.pi
        y = (p - 0.5) * height * 2.0
        a = [math.cos(ang) * radius, y, math.sin(ang) * radius]
        b = [math.cos(ang + math.pi) * radius, y, math.sin(ang + math.pi) * radius]
        helix_a.append(len(verts)); verts.append(a)
        helix_b.append(len(verts)); verts.append(b)

    paths = [helix_a, helix_b]
    for i in range(0, steps, 4):
        paths.append([helix_a[i], helix_b[i]])
    return np.array(verts, np.float32), paths


class HologramEffect(Effect):
    """İki el arasında döndürülebilen wireframe nesne (küp / torus / DNA)."""

    name = "HOLO"
    needs = 2
    SHAPES = ("CUBE", "TORUS", "DNA")

    def __init__(self) -> None:
        self.t = 0.0
        self.shape_index = 0
        self._geometries = {
            "CUBE": _cube_geometry(),
            "TORUS": _torus_geometry(),
            "DNA": _dna_geometry(),
        }
        self.cx: float | None = None
        self.cy: float | None = None
        self.scale = 120.0
        self.yaw = 0.0
        self.pitch = -0.35

    @property
    def shape_name(self) -> str:
        return self.SHAPES[self.shape_index]

    def next_shape(self) -> None:
        self.shape_index = (self.shape_index + 1) % len(self.SHAPES)

    def update(self, dt: float, hands, charge: float = 0.0) -> None:
        self.t += dt

        target_yaw = self.yaw + dt * 0.35
        target_pitch = -0.32 + 0.16 * math.sin(self.t * 0.8)
        cx, cy, target_scale = self.cx, self.cy, self.scale

        if len(hands) >= 2:
            a, b = hands[0].center, hands[1].center
            cx, cy = fx.midpoint(a, b)
            dist = float(np.linalg.norm(a - b))
            target_scale = float(np.clip(dist * 0.5, 90.0, 300.0))

            # elleri çevirmek nesneyi döndürür
            angle = math.atan2(float(b[1] - a[1]), float(b[0] - a[0]))
            target_yaw = self.t * 0.35 - angle
            target_pitch = -0.32 + 0.35 * math.sin(self.t * 0.8)

        if cx is None:
            return
        if self.cx is None:
            self.cx, self.cy, self.scale = cx, cy, target_scale
        else:
            self.cx = fx.smooth(self.cx, cx, dt, 12.0)
            self.cy = fx.smooth(self.cy, cy, dt, 12.0)
            self.scale = fx.smooth(self.scale, target_scale, dt, 8.0)

        self.yaw = fx.smooth(self.yaw, target_yaw, dt, 6.0)
        self.pitch = fx.smooth(self.pitch, target_pitch, dt, 5.0)

    def _project(self, verts: np.ndarray):
        cy_, sy_ = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        ry = np.array([[cy_, 0.0, sy_], [0.0, 1.0, 0.0], [-sy_, 0.0, cy_]], np.float32)
        rx = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], np.float32)

        p = verts @ (rx @ ry).T
        depth = p[:, 2] + 6.5
        focal = 3.2
        screen = np.empty((len(p), 2), np.float32)
        screen[:, 0] = self.cx + (p[:, 0] * focal / depth) * self.scale
        screen[:, 1] = self.cy + (p[:, 1] * focal / depth) * self.scale
        return screen, depth

    def draw(self, layer, hands, charge: float, palette) -> None:
        if self.cx is None:
            return

        deep, mid, bright, core = palette
        verts, paths = self._geometries[self.shape_name]
        screen, depth = self._project(verts)

        d_min, d_max = float(depth.min()), float(depth.max())
        span = max(d_max - d_min, 1e-3)
        shade = 0.35 + 0.65 * (1.0 - (depth - d_min) / span)  # yakın = parlak

        for path in paths:
            for a, b in zip(path[:-1], path[1:]):
                k = 0.5 * (shade[a] + shade[b])
                color = fx.scale_color(bright if k > 0.6 else mid, 0.35 + 0.75 * k)
                thickness = 2 if k > 0.72 else 1
                p1 = (int(screen[a, 0]), int(screen[a, 1]))
                p2 = (int(screen[b, 0]), int(screen[b, 1]))
                cv2.line(layer, p1, p2, color, thickness, cv2.LINE_AA)

        # köşe düğümleri
        for i in range(len(screen)):
            if shade[i] > 0.45:
                fx.add_radial(layer, screen[i, 0], screen[i, 1], 5, core,
                              power=1.8, gain=0.5 + 0.5 * charge)

        # taban halkası + hafif hacim hissi
        base_y = float(screen[:, 1].max()) + 18
        radius = int(self.scale * 0.75)
        cv2.ellipse(layer, (int(self.cx), int(base_y)), (radius, max(3, radius // 4)),
                    0, 0, 360, fx.scale_color(deep, 1.6), 1, cv2.LINE_AA)
        fx.add_radial(layer, self.cx, self.cy, int(self.scale * 1.25), deep,
                      power=3.0, gain=0.22)

"""AI Holographic Hand Interaction.

Kamera görüntüsü üzerinde MediaPipe ile elleri takip eder ve siyah bir
"efekt katmanına" additive çizim yapıp bloom ile birleştirir.

Modlar
  0 / AUTO : 1 el -> PORTAL, 2 el -> ORB
  1 ORB    : iki avuç arasında enerji küresi
  2 HOLO   : iki el arasında döndürülebilir wireframe nesne
  3 PORTAL : tek avuç içinde portal
  4 LIGHT  : iki işaret parmağı arasında yıldırım

Jestler
  2 elle pinch yapıp bırakmak -> şok dalgası (şarj arttıkça büyür)
  eller hızla birbirine yaklaşınca ("el çarpma") -> güçlü şok dalgası
  yumruk -> hologramı kavra, savurarak döndür
  T -> sadece Türkmenistan haritası (diğer efektler kapanır)
  A -> haritada Aşkabat'taki Bagt Köşgi binası

Kısayollar en altta, HUD'da görünür.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

import cv2
import numpy as np

import config
import fx
import hud
from effects import HologramEffect, LightningEffect, OrbEffect, PortalEffect
from mapview import TurkmenistanMap
from tracking import HandTracker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.join(BASE_DIR, "captures")

# Windows konsolu Türkçe karakterlerde UnicodeEncodeError verebilir.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODE_KEYS = {
    ord("0"): None,
    ord("1"): "ORB",
    ord("2"): "HOLO",
    ord("3"): "PORTAL",
    ord("4"): "LIGHTNING",
}


class App:
    def __init__(self, camera: int = config.CAMERA_INDEX, mode: str | None = None,
                 debug: bool = False) -> None:
        self.cap = self._open_camera(camera)
        self.tracker = HandTracker()
        self.bloom = fx.Bloom()
        self.postfx = fx.PostFX()
        self.waves = fx.ShockwaveField()

        self.orb = OrbEffect()
        self.holo = HologramEffect()
        self.portal = PortalEffect()
        self.lightning = LightningEffect()
        self.effects = {e.name: e for e in (self.orb, self.holo, self.portal, self.lightning)}
        self.map = TurkmenistanMap()

        # İki ayrı afterimage tamponu: arka efektler eller tarafından kesilir,
        # avuçtan çıkan ön efektler (portal, harita) kesilmez.
        self.trail_back = fx.Afterimage()
        self.trail_front = fx.Afterimage()
        self.postfx_enabled = config.POSTFX_ENABLED

        self.mode = mode
        self.palette_names = list(config.PALETTES)
        self.palette_index = self.palette_names.index(config.DEFAULT_PALETTE)
        self.palette = config.PALETTES[self.palette_names[self.palette_index]]

        self.charge = 0.0
        self._prev_gap: float | None = None
        self._map_mode = False

        self.debug = debug
        self.show_hud = True
        self.fullscreen = False

        self.writer: cv2.VideoWriter | None = None
        self.layer: np.ndarray | None = None   # ellerin arkasında kalan efektler
        self.front: np.ndarray | None = None   # ellerin önünde duran efektler
        self.combined: np.ndarray | None = None

    # ------------------------------------------------------------- kamera
    @staticmethod
    def _open_camera(camera: int) -> cv2.VideoCapture:
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if sys.platform.startswith("win") else [cv2.CAP_ANY]
        for backend in backends:
            cap = cv2.VideoCapture(camera, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
                cap.set(cv2.CAP_PROP_FPS, 30)
                return cap
            cap.release()
        raise RuntimeError(f"Kamera açılamadı (index {camera}). Başka bir uygulama kullanıyor olabilir.")

    # ------------------------------------------------------------- mod
    def active_mode(self, hand_count: int) -> str | None:
        if self.mode is not None:
            return self.mode
        if hand_count >= 2:
            return "ORB"
        if hand_count == 1:
            return "PORTAL"
        return None

    # --------------------------------------------------------- jestler
    def update_gestures(self, hands, dt: float) -> None:
        if len(hands) < 2:
            self.charge = max(0.0, self.charge - dt * 1.6)
            self._prev_gap = None
            return

        a, b = hands[0], hands[1]
        gap = float(np.linalg.norm(a.center - b.center))
        mid = fx.midpoint(a.center, b.center)
        pinching = a.pinch > config.PINCH_THRESHOLD and b.pinch > config.PINCH_THRESHOLD

        if pinching and gap < 560:
            self.charge = min(1.0, self.charge + dt * config.CHARGE_RATE)
        elif self.charge > config.CHARGE_MIN_TO_BURST:
            self.waves.burst(mid[0], mid[1],
                             150.0 + 230.0 * self.charge,
                             self.palette[2],
                             thickness=5.0)
            self.charge = 0.0

        if self._prev_gap is not None and gap < config.CLAP_GAP and self._prev_gap > config.CLAP_PREVIOUS_GAP:
            self.waves.burst(mid[0], mid[1], 420.0, self.palette[3],
                             life=0.8, thickness=7.0)
            self.charge = 0.0
        self._prev_gap = gap

    # ------------------------------------------------------------- döngü
    def run(self) -> None:
        prev_time = time.perf_counter()
        fps = 0.0

        cv2.namedWindow(config.WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(config.WINDOW_NAME, config.FRAME_WIDTH, config.FRAME_HEIGHT)

        while True:
            ok, frame = self.cap.read()
            if not ok:
                print("Kare okunamadı, kamera bağlantısı koptu.")
                break

            frame = cv2.flip(frame, 1)  # ayna görüntüsü

            if self.layer is None or self.layer.shape != frame.shape:
                self.layer = np.zeros_like(frame)
                self.front = np.zeros_like(frame)
                self.combined = np.zeros_like(frame)
            else:
                self.layer[:] = 0
                self.front[:] = 0

            now = time.perf_counter()
            raw_dt = max(now - prev_time, 1e-4)
            dt = float(np.clip(raw_dt, 1e-3, 0.06))
            prev_time = now
            fps = fps * 0.9 + (1.0 / raw_dt) * 0.1 if fps else 1.0 / raw_dt

            hands = self.tracker.process(frame, dt)

            # Harita güncellenir; kapanış animasyonu bitene kadar sahne onundur.
            self.map.update(dt, hands, frame.shape)
            map_mode = self.map.active()
            if map_mode != self._map_mode:
                self.trail_back.reset()
                self.trail_front.reset()
                self.waves.clear()
                self.charge = 0.0
                self._map_mode = map_mode

            if map_mode:
                # Sadece harita: diğer efektler söner, HUD ve jestler susar.
                # Geçişten bağımsız olarak iz tamponlarını temiz tut.
                self.trail_back.reset()
                self.trail_front.reset()
                self.charge = max(0.0, self.charge - dt * 2.0)
                for effect in self.effects.values():
                    effect.update(dt, [], self.charge)
                self.map.draw(self.front, hands, self.charge)
                self.combined[:] = self.front
            else:
                self.update_gestures(hands, dt)

                mode = self.active_mode(len(hands))
                effect = self.effects.get(mode) if mode else None
                if effect is not None:
                    effect.update(dt, hands, self.charge)
                    target = self.layer if effect.mask_hands else self.front
                    effect.draw(target, hands, self.charge, self.palette)

                self.waves.update(dt)
                self.waves.draw(self.layer)

                hand_mask = None
                if config.HAND_MASK_ENABLED and hands:
                    hand_mask = fx.hands_mask(frame.shape, hands)

                if config.AFTERIMAGE_ENABLED:
                    back = self.trail_back.apply(self.layer)
                    front = self.trail_front.apply(self.front)
                else:
                    back, front = self.layer, self.front

                if hand_mask is not None:
                    fx.apply_hand_mask(back, hand_mask)

                cv2.add(back, front, dst=self.combined)

            frame = self.bloom.apply(frame, self.combined)

            if self.postfx_enabled:
                frame = self.postfx.apply(frame)

            if not map_mode:
                if self.debug:
                    self.tracker.draw_debug(frame, hands)

                if self.show_hud:
                    hud.draw(
                        frame,
                        fps=fps,
                        mode=mode,
                        hand_count=len(hands),
                        charge=self.charge,
                        palette_name=self.palette_names[self.palette_index],
                        needs=effect.needs if effect else 0,
                        shape=self.holo.shape_name if mode == "HOLO" else None,
                        recording=self.writer is not None,
                        gesture=" ".join(hand.gesture for hand in hands),
                        postfx=self.postfx_enabled,
                    )

            if self.writer is not None:
                self.writer.write(frame)

            cv2.imshow(config.WINDOW_NAME, frame)
            if not self.handle_keys(frame):
                break

        self.close()

    # ------------------------------------------------------------ tuşlar
    def handle_keys(self, frame: np.ndarray) -> bool:
        key = cv2.waitKey(1) & 0xFF
        if key == 255:
            return True
        if key in (ord("q"), 27):
            return False

        if key in MODE_KEYS:
            self.mode = MODE_KEYS[key]
        elif key == ord("p"):
            self.palette_index = (self.palette_index + 1) % len(self.palette_names)
            self.palette = config.PALETTES[self.palette_names[self.palette_index]]
        elif key == ord("g"):
            self.holo.next_shape()
        elif key == ord("d"):
            self.debug = not self.debug
        elif key == ord("h"):
            self.show_hud = not self.show_hud
        elif key == ord("s"):
            self.save_screenshot(frame)
        elif key == ord("r"):
            self.toggle_recording(frame)
        elif key == ord("t"):
            self.map.toggle()
        elif key == ord("a"):
            self.map.open()
            self.map.toggle_building()
        elif key == ord("c"):
            self.map.reset(frame.shape[1], frame.shape[0])
        elif key == ord("v"):
            self.postfx_enabled = not self.postfx_enabled
        elif key == ord("f"):
            self.toggle_fullscreen()
        return True

    # ------------------------------------------------------- yardımcılar
    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        prop = cv2.WINDOW_FULLSCREEN if self.fullscreen else cv2.WINDOW_NORMAL
        cv2.setWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, prop)

    def save_screenshot(self, frame: np.ndarray) -> None:
        os.makedirs(CAPTURE_DIR, exist_ok=True)
        path = os.path.join(CAPTURE_DIR, f"shot_{datetime.now():%Y%m%d_%H%M%S}.png")
        cv2.imwrite(path, frame)
        print(f"Ekran görüntüsü: {path}")

    def toggle_recording(self, frame: np.ndarray) -> None:
        if self.writer is not None:
            self.writer.release()
            self.writer = None
            print("Kayıt durdu.")
            return

        os.makedirs(CAPTURE_DIR, exist_ok=True)
        path = os.path.join(CAPTURE_DIR, f"rec_{datetime.now():%Y%m%d_%H%M%S}.mp4")
        h, w = frame.shape[:2]
        self.writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (w, h))
        if not self.writer.isOpened():
            self.writer = None
            print("Kayıt başlatılamadı (codec yok).")
        else:
            print(f"Kayıt başladı: {path}")

    def close(self) -> None:
        if self.writer is not None:
            self.writer.release()
        self.cap.release()
        self.tracker.close()
        cv2.destroyAllWindows()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Holographic Hand Interaction")
    parser.add_argument("--camera", type=int, default=config.CAMERA_INDEX,
                        help="kamera indeksi (varsayılan: %(default)s)")
    parser.add_argument("--mode", type=str.upper,
                        choices=["ORB", "HOLO", "PORTAL", "LIGHTNING"],
                        default=None, help="başlangıç modu (varsayılan: otomatik)")
    parser.add_argument("--debug", action="store_true", help="iskelet/landmark çizimini aç")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Q: çıkış | 0-4: mod | G: şekil | P: renk | T: harita | A: Aşkabat binası | "
          "V: post-process | D: debug | S: ekran görüntüsü | R: kayıt | F: tam ekran")
    try:
        App(camera=args.camera, mode=args.mode, debug=args.debug).run()
    except RuntimeError as exc:
        print(f"Hata: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

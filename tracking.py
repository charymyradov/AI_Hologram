"""MediaPipe el takibi + jest ölçümleri.

Efektler bu modüldeki `HandState` nesneleriyle konuşur; MediaPipe detayları
burada kalır. Böylece takip kütüphanesini (örn. yeni Tasks API) değiştirmek
efekt koduna dokunmayı gerektirmez.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

import config

try:  # mediapipe 0.10.x klasik API
    import mediapipe as mp

    _mp_hands = mp.solutions.hands
except (ImportError, AttributeError):  # beklenmedik sürümler için yedek yol
    from mediapipe.python.solutions import hands as _mp_hands


PALM_POINTS = (0, 5, 9, 13, 17)
FINGER_TIPS = (8, 12, 16, 20)
FINGER_PIPS = (6, 10, 14, 18)
CONNECTIONS = tuple(_mp_hands.HAND_CONNECTIONS)


@dataclass
class HandState:
    """Tek bir elin kare içindeki durumu (piksel cinsinden)."""

    label: str
    center: np.ndarray          # avuç içi merkezi (x, y)
    landmarks: np.ndarray       # (21, 2) piksel koordinatları
    palm_size: float            # avuç ölçeği (referans uzunluk)
    pinch: float                # 0..1, 1 = başparmak işarete değiyor
    openness: float             # 0..1, 1 = tüm parmaklar açık
    extended: int               # açık parmak sayısı (0..4)
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2, np.float32))

    @property
    def fist(self) -> bool:
        return self.extended == 0 and self.pinch < 0.6

    @property
    def gesture(self) -> str:
        """Kaba jest sınıfı: PINCH / FIST / OPEN / HAND."""
        if self.pinch > 0.8:
            return "PINCH"
        if self.fist:
            return "FIST"
        if self.openness >= 0.75:
            return "OPEN"
        return "HAND"

    @property
    def grab(self) -> bool:
        """Kavrama jesti (yumruk veya güçlü pinch)."""
        return self.fist or self.pinch > 0.82

    def fingertip(self, index: int = 8) -> np.ndarray:
        return self.landmarks[index]


class HandTracker:
    """Kareyi alır, `HandState` listesi döndürür (soldan sağa sıralı)."""

    def __init__(self) -> None:
        self._hands = _mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=config.MAX_HANDS,
            model_complexity=config.MODEL_COMPLEXITY,
            min_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
        )
        self._prev_center: dict[str, np.ndarray] = {}
        self._smooth_vel: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------- takip
    def process(self, frame: np.ndarray, dt: float) -> list[HandState]:
        h, w = frame.shape[:2]

        scale = min(1.0, config.PROCESS_WIDTH / float(w))
        if scale < 1.0:
            small = cv2.resize(frame, (int(w * scale), int(h * scale)),
                               interpolation=cv2.INTER_AREA)
        else:
            small = frame

        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._hands.process(rgb)

        states: list[HandState] = []
        if not results.multi_hand_landmarks:
            self._prev_center.clear()
            self._smooth_vel.clear()
            return states

        labels = []
        if results.multi_handedness:
            labels = [h.classification[0].label for h in results.multi_handedness]

        for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
            pts = np.array(
                [[lm.x * w, lm.y * h] for lm in hand_landmarks.landmark],
                dtype=np.float32,
            )
            label = labels[i] if i < len(labels) else f"hand{i}"
            states.append(self._build_state(label, pts, dt))

        states.sort(key=lambda s: float(s.center[0]))
        return states

    def _build_state(self, label: str, pts: np.ndarray, dt: float) -> HandState:
        palm = pts[list(PALM_POINTS)]
        center = palm.mean(axis=0)

        palm_size = float(max(np.linalg.norm(pts[0] - pts[9]), 1.0))

        pinch_raw = float(np.linalg.norm(pts[4] - pts[8]) / palm_size)
        pinch = float(np.clip(1.0 - (pinch_raw - 0.25) / 0.55, 0.0, 1.0))

        extended = 0
        ratios = []
        for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
            tip_d = float(np.linalg.norm(pts[tip] - pts[0]))
            pip_d = float(np.linalg.norm(pts[pip] - pts[0]))
            ratio = tip_d / max(pip_d, 1e-3)
            if ratio > 1.08:
                extended += 1
            # Sürekli açıklık: 1.0 (tam bükük) -> 1.6 (tam açık) aralığını 0..1'e çek.
            ratios.append(float(np.clip((ratio - 1.0) / 0.6, 0.0, 1.0)))

        openness = float(np.mean(ratios)) if ratios else 0.0

        prev = self._prev_center.get(label)
        if prev is None:
            vel = np.zeros(2, np.float32)
        else:
            vel = ((center - prev) / max(dt, 1e-3)).astype(np.float32)
            vel = 0.55 * self._smooth_vel.get(label, vel) + 0.45 * vel

        self._prev_center[label] = center
        self._smooth_vel[label] = vel

        return HandState(
            label=label,
            center=center,
            landmarks=pts,
            palm_size=palm_size,
            pinch=pinch,
            openness=openness,
            extended=extended,
            velocity=vel,
        )

    # ------------------------------------------------------------- debug
    @staticmethod
    def draw_debug(frame: np.ndarray, hands: list[HandState]) -> None:
        for hand in hands:
            pts = hand.landmarks.astype(int)
            for a, b in CONNECTIONS:
                cv2.line(frame, tuple(pts[a]), tuple(pts[b]), (90, 90, 90), 1, cv2.LINE_AA)
            for idx, (x, y) in enumerate(pts):
                color = (0, 255, 255) if idx in FINGER_TIPS else (200, 200, 200)
                cv2.circle(frame, (int(x), int(y)), 3, color, -1, cv2.LINE_AA)
            cx, cy = hand.center.astype(int)
            cv2.circle(frame, (int(cx), int(cy)), int(hand.palm_size * 0.5),
                       (255, 120, 0), 1, cv2.LINE_AA)
            cv2.putText(frame, f"{hand.label} p={hand.pinch:.2f} o={hand.openness:.2f}",
                        (int(pts[0][0]) - 20, int(pts[0][1]) + 34),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1, cv2.LINE_AA)

    def close(self) -> None:
        self._hands.close()

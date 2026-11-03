"""Ekran üstü bilgi katmanı (FPS, mod, şarj, kısayollar)."""

from __future__ import annotations

import cv2

import config

FONT = cv2.FONT_HERSHEY_DUPLEX


def _bar(frame, x, y, width, height, value, color) -> None:
    cv2.rectangle(frame, (x, y), (x + width, y + height), (60, 60, 66), -1)
    fill = int(width * max(0.0, min(1.0, value)))
    if fill > 0:
        cv2.rectangle(frame, (x, y), (x + fill, y + height), color, -1)


def draw(frame, fps: float, mode: str | None, hand_count: int, charge: float,
         palette_name: str, needs: int = 0, shape: str | None = None,
         recording: bool = False, throw_count: int = 0,
         throw_enabled: bool = True) -> None:
    h, w = frame.shape[:2]

    # yarı saydam üst bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 62), (10, 12, 16), -1)
    cv2.addWeighted(overlay, config.HUD_ALPHA, frame, 1.0 - config.HUD_ALPHA, 0, frame)

    mode_text = (mode or "AUTO").upper()
    cv2.putText(frame, "AI HOLOGRAM", (24, 30), FONT, 0.62, config.HUD_DIM, 1, cv2.LINE_AA)
    cv2.putText(frame, mode_text, (24, 53), FONT, 0.78, config.HUD_TEXT, 1, cv2.LINE_AA)

    if shape:
        cv2.putText(frame, shape, (190, 53), FONT, 0.62, (120, 190, 255), 1, cv2.LINE_AA)

    if throw_count:
        cv2.circle(frame, (330, 48), 5, (0, 190, 255), -1, cv2.LINE_AA)
        cv2.putText(frame, f"{throw_count}", (342, 53), FONT, 0.55, (0, 190, 255), 1, cv2.LINE_AA)
    elif not throw_enabled:
        cv2.putText(frame, "THROW OFF", (330, 53), FONT, 0.45, (120, 120, 130), 1, cv2.LINE_AA)

    cv2.putText(frame, f"{fps:4.0f} FPS", (w - 110, 30), FONT, 0.55,
                config.HUD_DIM, 1, cv2.LINE_AA)
    cv2.putText(frame, f"{hand_count} EL  |  {palette_name.upper()}", (w - 190, 54), FONT, 0.5,
                config.HUD_DIM, 1, cv2.LINE_AA)

    # şarj çubuğu
    if charge > 0.02:
        _bar(frame, 24, 70, 220, 6, charge,
             (60, 120, 255) if charge < 0.99 else (80, 255, 255))
        cv2.putText(frame, "CHARGE", (252, 78), FONT, 0.42, (140, 160, 180), 1, cv2.LINE_AA)

    # durum ipucu (cv2.putText sadece ASCII basar)
    hint = ""
    if needs and hand_count < needs:
        hint = "2 ELLERINI GOSTER" if needs == 2 else "ELINI GOSTER"
    elif hand_count == 0:
        hint = "ELLERINI KAMERAYA GOSTER"
    elif mode is None:
        hint = "1 EL = PORTAL   |   2 EL = ORB"
    if hint:
        size = cv2.getTextSize(hint, FONT, 0.72, 1)[0]
        cv2.putText(frame, hint, ((w - size[0]) // 2, h - 78), FONT, 0.72,
                    (0, 220, 255), 1, cv2.LINE_AA)

    if throw_enabled and hand_count:
        cv2.putText(frame, "HIZLI SAVUR = FIRLAT", (24, 96), FONT, 0.45,
                    (0, 160, 210), 1, cv2.LINE_AA)

    # alt bilgi
    cv2.putText(frame, config.KEYS_HELP, (24, h - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (170, 178, 190), 1, cv2.LINE_AA)

    if recording:
        cv2.circle(frame, (w - 32, 84), 7, (60, 60, 235), -1, cv2.LINE_AA)
        cv2.putText(frame, "REC", (w - 96, 90), FONT, 0.5, (90, 90, 240), 1, cv2.LINE_AA)

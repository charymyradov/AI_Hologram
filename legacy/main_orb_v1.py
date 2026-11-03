
import cv2
import mediapipe as mp
import numpy as np
import math
import random

# Kamera
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# MediaPipe el takip sistemi
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    model_complexity=1,
    min_detection_confidence=0.65,
    min_tracking_confidence=0.65
)

frame_count = 0
particles = []

def create_particles(cx, cy, radius):
    global particles

    particles = []
    for _ in range(90):
        angle = random.uniform(0, math.pi * 2)
        distance = random.uniform(radius * 0.7, radius * 1.5)

        particles.append([
            cx + math.cos(angle) * distance,
            cy + math.sin(angle) * distance,
            random.uniform(1, 4)
        ])

def draw_energy_orb(frame, cx, cy, radius):
    global frame_count, particles

    h, w = frame.shape[:2]
    overlay = np.zeros_like(frame)

    # Dış enerji parlaması
    cv2.circle(
        overlay, (cx, cy), int(radius * 1.5),
        (255, 80, 10), -1
    )

    cv2.circle(
        overlay, (cx, cy), int(radius * 1.1),
        (255, 150, 30), -1
    )

    overlay = cv2.GaussianBlur(overlay, (0, 0), 35)
    frame = cv2.addWeighted(frame, 1, overlay, 0.55, 0)

    # Kürenin iç yapısı
    cv2.circle(frame, (cx, cy), radius, (180, 80, 20), -1)
    cv2.circle(frame, (cx, cy), int(radius * 0.82),
               (255, 130, 40), 2)

    # Parlak merkez
    cv2.circle(frame, (cx, cy), int(radius * 0.48),
               (255, 210, 120), 2)

    cv2.circle(frame, (cx, cy), int(radius * 0.18),
               (255, 255, 220), -1)

    # Dönen enerji halkaları
    angle = frame_count * 3

    cv2.ellipse(
        frame, (cx, cy),
        (radius, int(radius * 0.35)),
        angle, 0, 360, (255, 220, 100), 2
    )

    cv2.ellipse(
        frame, (cx, cy),
        (int(radius * 0.55), radius),
        -angle, 0, 360, (255, 180, 60), 2
    )

    # Parçacıklar
    if frame_count % 20 == 0 or not particles:
        create_particles(cx, cy, radius)

    for p in particles:
        x, y, size = p

        x = int(x + math.sin(frame_count * 0.04 + y) * 2)
        y = int(y + math.cos(frame_count * 0.04 + x) * 2)

        if 0 <= x < w and 0 <= y < h:
            cv2.circle(frame, (x, y), int(size),
                       (255, 220, 120), -1)

    frame_count += 1
    return frame


while True:
    success, frame = cap.read()

    if not success:
        print("Kamera açılamadı!")
        break

    # Ayna görüntüsü
    frame = cv2.flip(frame, 1)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    hand_centers = []

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:

            # Avuç içi merkezini hesapla
            points = [0, 5, 9, 13, 17]

            x_values = [
                hand_landmarks.landmark[i].x
                for i in points
            ]

            y_values = [
                hand_landmarks.landmark[i].y
                for i in points
            ]

            h, w = frame.shape[:2]

            cx = int(np.mean(x_values) * w)
            cy = int(np.mean(y_values) * h)

            hand_centers.append((cx, cy))

            # Elin etrafında küçük takip noktası
            cv2.circle(frame, (cx, cy), 8,
                       (0, 255, 255), -1)

    # İki el algılandığında küre oluştur
    if len(hand_centers) == 2:

        hand1 = hand_centers[0]
        hand2 = hand_centers[1]

        center_x = (hand1[0] + hand2[0]) // 2
        center_y = (hand1[1] + hand2[1]) // 2

        distance = math.dist(hand1, hand2)

        radius = int(np.clip(distance * 0.38, 35, 190))

        # Eller arasındaki bağlantı
        cv2.line(frame, hand1, hand2,
                 (255, 180, 50), 2)

        frame = draw_energy_orb(
            frame, center_x, center_y, radius
        )

        cv2.putText(
            frame,
            "ENERGY ORB ACTIVE",
            (30, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (100, 255, 150),
            2
        )

    else:
        cv2.putText(
            frame,
            "SHOW BOTH HANDS",
            (30, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 200, 255),
            2
        )

    cv2.putText(
        frame,
        "Press Q to exit",
        (30, frame.shape[0] - 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    cv2.imshow("AI Holographic Hand Interaction", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
hands.close()
cv2.destroyAllWindows()

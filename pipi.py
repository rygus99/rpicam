import cv2
import mediapipe as mp
import RPi.GPIO as GPIO
from picamera2 import Picamera2
import tkinter as tk
import threading

# -------------------------------
# 부저 GPIO 설정
# -------------------------------
BUZZER_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
pwm = GPIO.PWM(BUZZER_PIN, 440)
pwm.stop()

# 음계 매핑 (도~높은 도)
note_freq = {
    1: ("도", 261),
    2: ("레", 293),
    3: ("미", 329),
    4: ("파", 349),
    5: ("솔", 392),
    6: ("라", 440),
    7: ("시", 493),
    8: ("도", 523)  # 높은 도
}

# -------------------------------
# MediaPipe Hands 설정 (정확도 ↑)
# -------------------------------
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.8,
    min_tracking_confidence=0.8
)

def count_fingers(hand_landmarks, handedness="Right"):
    """손가락 개수 세기 (왼손/오른손 구분)"""
    tips = [8, 12, 16, 20]  # 검지, 중지, 약지, 새끼
    count = 0
    for tip in tips:
        if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[tip - 2].y:
            count += 1

    # 엄지 판별: 손 방향(왼/오른손)에 따라 다르게 계산
    if handedness == "Right":
        if hand_landmarks.landmark[4].x < hand_landmarks.landmark[3].x:
            count += 1
    else:  # Left
        if hand_landmarks.landmark[4].x > hand_landmarks.landmark[3].x:
            count += 1
    return count

# -------------------------------
# Tkinter GUI (피아노 건반)
# -------------------------------
root = tk.Tk()
root.title("Hand Piano")
canvas = tk.Canvas(root, width=640, height=200, bg="white")
canvas.pack()

# 8개 건반(도레미파솔라시도)
keys = []
for i in range(8):
    x0 = i * 80
    x1 = x0 + 80
    rect = canvas.create_rectangle(x0, 0, x1, 200, fill="white", outline="black", width=2)
    keys.append(rect)

def highlight_key(fingers):
    # 모든 건반 흰색 초기화
    for k in keys:
        canvas.itemconfig(k, fill="white")
    if fingers in note_freq:
        canvas.itemconfig(keys[fingers - 1], fill="lightblue")
        root.title(f"Hand Piano - {note_freq[fingers][0]}")

# -------------------------------
# Picamera2 초기화
# -------------------------------
picam2 = Picamera2()
preview_config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(preview_config)
picam2.start()

def camera_loop():
    try:
        while True:
            frame = picam2.capture_array()

            # --- 채널 보정 ---
            if frame.shape[-1] == 4:   # RGBA → BGR
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            elif len(frame.shape) == 2:  # Gray → BGR
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            finger_count = 0
            if result.multi_hand_landmarks and result.multi_handedness:
                handedness = result.multi_handedness[0].classification[0].label
                for hand_landmarks in result.multi_hand_landmarks:
                    finger_count = count_fingers(hand_landmarks, handedness)
                    mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            if finger_count in note_freq:
                freq = note_freq[finger_count][1]
                pwm.start(50)
                pwm.ChangeFrequency(freq)
                highlight_key(finger_count)
            else:
                pwm.stop()
                highlight_key(0)

            # 화면에 손가락 개수 표시
            cv2.putText(frame, f"Fingers: {finger_count}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            cv2.imshow("MediaPipe Hand Piano", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        pass
    finally:
        picam2.stop()
        cv2.destroyAllWindows()
        pwm.stop()
        GPIO.cleanup()
        root.quit()

# -------------------------------
# 멀티스레드 실행 (카메라 + Tkinter GUI 동시 실행)
# -------------------------------
t = threading.Thread(target=camera_loop, daemon=True)
t.start()
root.mainloop()

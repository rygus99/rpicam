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
# MediaPipe Hand Tracking 설정
# -------------------------------
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7)

def count_fingers(hand_landmarks):
    """손가락 개수 세기"""
    tips = [8, 12, 16, 20]  # 검지, 중지, 약지, 새끼
    count = 0
    for tip in tips:
        if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[tip - 2].y:
            count += 1
    if hand_landmarks.landmark[4].x < hand_landmarks.landmark[3].x:  # 엄지
        count += 1
    return count

# -------------------------------
# Tkinter GUI (피아노 건반)
# -------------------------------
root = tk.Tk()
root.title("Hand Piano - 협동 모드")
canvas = tk.Canvas(root, width=640, height=200, bg="white")
canvas.pack()

# 8개 건반 (도레미파솔라시도)
keys = []
for i in range(8):
    x0 = i * 80
    x1 = x0 + 80
    rect = canvas.create_rectangle(x0, 0, x1, 200, fill="white", outline="black", width=2)
    keys.append(rect)

def highlight_key(fingers, color="lightblue"):
    # 모든 건반 흰색 초기화
    for k in keys:
        canvas.itemconfig(k, fill="white")
    if fingers in note_freq:
        canvas.itemconfig(keys[fingers - 1], fill=color)
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

            left_fingers, right_fingers = 0, 0

            if result.multi_hand_landmarks and result.multi_handedness:
                for idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
                    hand_label = result.multi_handedness[idx].classification[0].label
                    finger_count = count_fingers(hand_landmarks)

                    if hand_label == "Left":
                        left_fingers = finger_count
                        mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    elif hand_label == "Right":
                        right_fingers = finger_count
                        mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # 멜로디 (오른손), 코드/화음 (왼손)
            if right_fingers in note_freq:
                freq = note_freq[right_fingers][1]
                pwm.start(50)
                pwm.ChangeFrequency(freq)
                highlight_key(right_fingers, "lightblue")
            elif left_fingers in note_freq:
                # 코드 효과: 기본 주파수 + 약간 변형
                freq = note_freq[left_fingers][1]
                pwm.start(50)
                pwm.ChangeFrequency(freq + 20)  # 살짝 변형된 주파수로 화음 느낌
                highlight_key(left_fingers, "lightgreen")
            else:
                pwm.stop()
                highlight_key(0)

            cv2.imshow("MediaPipe Hand Piano - 협동 모드", frame)
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

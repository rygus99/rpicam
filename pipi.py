import cv2
import mediapipe as mp
import RPi.GPIO as GPIO
from picamera2 import Picamera2
import tkinter as tk
import threading
import random
import time

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
# MediaPipe Hands 설정
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

    if handedness == "Right":
        if hand_landmarks.landmark[4].x < hand_landmarks.landmark[3].x:
            count += 1
    else:  # Left
        if hand_landmarks.landmark[4].x > hand_landmarks.landmark[3].x:
            count += 1
    return count

# -------------------------------
# Tkinter GUI (피아노 건반 + 게임 요소)
# -------------------------------
root = tk.Tk()
root.title("Hand Piano Game")
canvas = tk.Canvas(root, width=640, height=300, bg="white")
canvas.pack()

# 8개 건반(도레미파솔라시도) + 음계/손가락 개수 표시
keys = []
key_labels = []
for i in range(8):
    x0 = i * 80
    x1 = x0 + 80
    rect = canvas.create_rectangle(x0, 100, x1, 300,
                                   fill="white", outline="black", width=2)
    keys.append(rect)

    # 건반 안에 음 이름 + 손가락 개수 표시
    note_name, freq = note_freq[i+1]
    label = canvas.create_text(
        x0 + 40, 200,   # 건반 중앙 위치
        text=f"{note_name}\n({i+1} 손가락)",
        font=("Arial", 12, "bold"),
        fill="black"
    )
    key_labels.append(label)

# 점수 표시
score_text = canvas.create_text(320, 20, text="Score: 0",
                                font=("Arial", 16), fill="black")
current_note = None
note_object = None

def spawn_note():
    """랜덤 음계 노트 생성"""
    global current_note, note_object
    current_note = random.randint(1, 8)
    note_name = note_freq[current_note][0]
    if note_object:
        canvas.delete(note_object)
    note_object = canvas.create_text(current_note*80 - 40, 60, text=note_name,
                                     font=("Arial", 20, "bold"), fill="red")
    root.after(3000, spawn_note)  # 3초마다 새로운 노트 등장

def highlight_key(fingers):
    """누른 건반 시각화"""
    for k in keys:
        canvas.itemconfig(k, fill="white")
    if fingers in note_freq:
        canvas.itemconfig(keys[fingers - 1], fill="lightblue")

def check_answer(fingers):
    """사용자가 낸 손가락 수가 정답인지 확인"""
    global score, current_note
    if fingers == current_note:
        score += 10
        canvas.itemconfig(score_text, text=f"Score: {score}")

# -------------------------------
# Picamera2 초기화
# -------------------------------
picam2 = Picamera2()
preview_config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(preview_config)
picam2.start()

def camera_loop():
    global current_note
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
                check_answer(finger_count)
            else:
                pwm.stop()
                highlight_key(0)

            # 손가락 개수 표시
            cv2.putText(frame, f"Fingers: {finger_count}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            cv2.imshow("Hand Piano Game", frame)
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
spawn_note()
root.mainloop()


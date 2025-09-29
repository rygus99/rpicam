import cv2
import mediapipe as mp
import RPi.GPIO as GPIO
from picamera2 import Picamera2

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
# Picamera2 초기화
# -------------------------------
picam2 = Picamera2()
preview_config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(preview_config)
picam2.start()

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
                elif hand_label == "Right":
                    right_fingers = finger_count

                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

        # -------------------------------
        # 협동 모드 로직
        # 오른손 → 멜로디, 왼손 → 코드(화음)
        # -------------------------------
        if right_fingers in note_freq:
            freq = note_freq[right_fingers][1]
            pwm.start(50)
            pwm.ChangeFrequency(freq)
            cv2.putText(frame, f"Right: {note_freq[right_fingers][0]}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        elif left_fingers in note_freq:
            freq = note_freq[left_fingers][1] + 20  # 살짝 변형
            pwm.start(50)
            pwm.ChangeFrequency(freq)
            cv2.putText(frame, f"Left: {note_freq[left_fingers][0]} (Chord)", (10, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        else:
            pwm.stop()

        # 화면에 손가락 개수 표시
        cv2.putText(frame, f"L:{left_fingers}  R:{right_fingers}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        cv2.imshow("Hand Piano - 협동 모드", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    pass
finally:
    picam2.stop()
    cv2.destroyAllWindows()
    pwm.stop()
    GPIO.cleanup()

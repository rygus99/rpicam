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
    1: 261,  # 도
    2: 293,  # 레
    3: 329,  # 미
    4: 349,  # 파
    5: 392,  # 솔
    6: 440,  # 라
    7: 493,  # 시
    8: 523   # 높은 도
}

# -------------------------------
# MediaPipe Hand Tracking 설정
# -------------------------------
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)

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

        # MediaPipe에 넘길 때 RGB 변환
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        finger_count = 0

        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                finger_count = count_fingers(hand_landmarks)
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

        if finger_count in note_freq:
            freq = note_freq[finger_count]
            pwm.start(50)
            pwm.ChangeFrequency(freq)
            print(f"Fingers: {finger_count}, Note: {freq}Hz")
        else:
            pwm.stop()

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

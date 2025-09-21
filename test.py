import cv2
import mediapipe as mp

# mediapipe 객체 준비
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

with mp_hands.Hands(max_num_hands=1) as hands:  # 한 손만 추적
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # BGR -> RGB 변환
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        # 손 랜드마크가 있으면 그림 그리기
        if result.multi_hand_landmarks:
            for hand in result.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

        cv2.imshow("MediaPipe Hands", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()

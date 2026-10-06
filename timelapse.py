"""
Study Time-lapse: ghi màn hình + webcam thành video time-lapse.
Nhấn 'q' để thoát an toàn và giải phóng tài nguyên.
"""

import time

import cv2
import mss
import numpy as np

# ================= CONFIG (tinh chỉnh ở đây) =================
INTERVAL      = 5        # giây giữa mỗi khung hình ghi vào video
OUTPUT_FPS    = 10       # FPS phát lại của video time-lapse đầu ra
WEBCAM_ID     = 0        # index webcam (0 = mặc định)
MONITOR       = 1        # mss monitor (1 = màn hình chính)

SCREEN_WIDTH  = 1280     # chiều rộng màn hình sau khi scale
SCREEN_HEIGHT = 720      # chiều cao màn hình sau khi scale
WEBCAM_WIDTH  = 640      # chiều rộng webcam
WEBCAM_HEIGHT = 360      # chiều cao webcam

MODE          = "side"   # "side" = cạnh nhau, "pip" = webcam chồng góc
PIP_SCALE     = 0.25     # (chỉ pip) tỉ lệ webcam so với chiều rộng màn hình
OUTPUT_FILE   = "timelapse.mp4"
# =============================================================


def combine(screen, webcam, mode=MODE):
    """Gộp màn hình + webcam thành 1 khung."""
    if mode == "pip":
        h, w = screen.shape[:2]
        pip_w = int(w * PIP_SCALE)
        pip_h = int(pip_w * webcam.shape[0] / max(webcam.shape[1], 1))
        pip = cv2.resize(webcam, (pip_w, pip_h))
        canvas = screen.copy()
        margin = 12
        y0, x0 = margin, w - pip_w - margin
        canvas[y0:y0 + pip_h, x0:x0 + pip_w] = pip
        cv2.rectangle(canvas, (x0, y0), (x0 + pip_w, y0 + pip_h), (0, 255, 0), 2)
        return canvas

    # mode == "side"
    h = max(screen.shape[0], webcam.shape[0])
    screen_s = cv2.resize(screen, (int(screen.shape[1] * h / screen.shape[0]), h))
    webcam_s = cv2.resize(webcam, (int(webcam.shape[1] * h / webcam.shape[0]), h))
    return np.hstack([screen_s, webcam_s])


def main():
    # Webcam
    cap = cv2.VideoCapture(WEBCAM_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WEBCAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WEBCAM_HEIGHT)
    if not cap.isOpened():
        print("[WARN] Không mở được webcam — dùng khung đen thay thế.")

    # Màn hình
    sct = mss.mss()
    mon = sct.monitors[MONITOR]

    # Kích thước khung gộp
    screen_shape = (SCREEN_HEIGHT, SCREEN_WIDTH, 3)
    webcam_shape = (WEBCAM_HEIGHT, WEBCAM_WIDTH, 3)
    blank_screen = np.zeros(screen_shape, np.uint8)
    blank_webcam = np.zeros(webcam_shape, np.uint8)
    h, w = combine(blank_screen, blank_webcam).shape[:2]

    # Video đầu ra
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUTPUT_FILE, fourcc, OUTPUT_FPS, (w, h))
    if not writer.isOpened():
        print("[ERROR] Không tạo được file video (kiểm tra codec/đường dẫn).")
        return

    print(f"Bắt đầu: 1 khung / {INTERVAL}s, FPS={OUTPUT_FPS}, mode={MODE}")
    print("Nhấn 'q' để dừng.")

    next_capture = time.monotonic()
    frames = 0

    try:
        while True:
            # Chụp màn hình (mss trả BGRA)
            try:
                shot = np.array(sct.grab(mon))
                screen = cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)
            except Exception:
                screen = blank_screen.copy()
            screen = cv2.resize(screen, (SCREEN_WIDTH, SCREEN_HEIGHT))

            # Đọc webcam
            ok, webcam = cap.read() if cap.isOpened() else (False, None)
            if not ok or webcam is None:
                webcam = blank_webcam.copy()
            else:
                webcam = cv2.resize(webcam, (WEBCAM_WIDTH, WEBCAM_HEIGHT))

            frame = combine(screen, webcam)

            # Ghi vào video theo chu kỳ time-lapse
            now = time.monotonic()
            if now >= next_capture:
                writer.write(frame)
                frames += 1
                next_capture += INTERVAL
                if now - next_capture > INTERVAL:  # tránh trễ dồn
                    next_capture = now + INTERVAL

            cv2.imshow("Time-lapse Preview (q = thoat)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        writer.release()
        cap.release()
        sct.close()
        cv2.destroyAllWindows()

    print(f"Xong: {frames} khung -> {OUTPUT_FILE} "
          f"(~{frames / OUTPUT_FPS:.1f}s phát lại)")


if __name__ == "__main__":
    main()

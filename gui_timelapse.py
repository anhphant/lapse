"""
Study Time-lapse — GUI realtime.
Chọn màn hình / cửa sổ ứng dụng / tab trình duyệt để quay,
xem trước trực tiếp với nhãn hiển thị rõ đang quay gì.
Webcam luôn hiển thị (picture-in-picture), kéo chuột để di chuyển,
kéo góc dưới-phải để đổi kích thước.
Video xuất ra KHÔNG chứa overlay chữ (sạch); webcam vẫn được ghi vào video.
"""

import ctypes
import ctypes.wintypes as wintypes
import os
import time
from datetime import datetime

import cv2
import mss
import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk

# ============ CONFIG ============
SCREEN_WIDTH  = 1280    # độ phân giải ghi ra
SCREEN_HEIGHT = 720
WEBCAM_WIDTH  = 640
WEBCAM_HEIGHT = 360
WEBCAM_ID     = 0
PREVIEW_WIDTH = 1080    # chiều rộng khung preview
DEFAULT_INTERVAL = 5
DEFAULT_FPS      = 10
OUTPUT_BASENAME = "timelapse"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))  # lưu cạnh file script
CODECS = ["mp4v", "avc1", "MJPG", "XVID"]                 # thử lần lượt

# Vị trí/kích thước webcam mặc định (tỉ lệ theo khung)
CAM_X = 0.74      # 0..1
CAM_Y = 0.014     # 0..1
CAM_SCALE = 0.25  # chiều rộng webcam / chiều rộng khung (0.1..0.6)
APP_TITLE = "Study Time-lapse — Realtime GUI"
# ================================


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor v2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def _title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    if not n:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def _process_name(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    hproc = kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
    if not hproc:
        return ""
    try:
        size = wintypes.DWORD(512)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
        return ""
    finally:
        kernel32.CloseHandle(hproc)


def _window_info(hwnd):
    t = _title(hwnd)
    x, y, w, h = _rect(hwnd)
    return {"hwnd": hwnd, "title": t, "proc": _process_name(hwnd),
            "x": x, "y": y, "w": w, "h": h}


def list_windows():
    """Liệt kê cửa sổ đang mở, nhìn thấy được (bỏ thu nhỏ / ẩn)."""
    wins = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        t = _title(hwnd)
        if not t.strip():
            return True
        x, y, w, h = _rect(hwnd)
        if w < 80 or h < 80:
            return True
        wins.append(_window_info(hwnd))
        return True

    user32.EnumWindows(cb, 0)
    return wins


def foreground():
    return _window_info(user32.GetForegroundWindow())


# ============ Chụp cửa sổ bằng PrintWindow (kể cả khi thu nhỏ) ============
gdi32 = ctypes.windll.gdi32
HDC = ctypes.c_void_p
HBITMAP = ctypes.c_void_p


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("showCmd", wintypes.DWORD),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


# Khai báo prototype cho API 64-bit (tránh cắt cụt handle 64-bit)
user32.GetWindowDC.restype = HDC
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.restype = ctypes.c_int
user32.ReleaseDC.argtypes = [wintypes.HWND, HDC]
user32.PrintWindow.restype = ctypes.c_bool
user32.PrintWindow.argtypes = [wintypes.HWND, HDC, ctypes.c_uint]
user32.GetWindowPlacement.restype = ctypes.c_bool
user32.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
user32.GetCursorPos.restype = ctypes.c_bool
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]

gdi32.CreateCompatibleDC.restype = HDC
gdi32.CreateCompatibleDC.argtypes = [HDC]
gdi32.CreateCompatibleBitmap.restype = HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = HBITMAP
gdi32.SelectObject.argtypes = [HDC, HBITMAP]
gdi32.DeleteObject.restype = ctypes.c_bool
gdi32.DeleteObject.argtypes = [HBITMAP]
gdi32.DeleteDC.restype = ctypes.c_bool
gdi32.DeleteDC.argtypes = [HDC]
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.GetDIBits.argtypes = [HDC, HBITMAP, ctypes.c_uint, ctypes.c_uint,
                            ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), ctypes.c_uint]


def _window_restored_size(hwnd):
    """Kích thước cửa sổ khi ở trạng thái bình thường (dù đang thu nhỏ)."""
    wp = WINDOWPLACEMENT()
    wp.length = ctypes.sizeof(WINDOWPLACEMENT)
    if user32.GetWindowPlacement(hwnd, ctypes.byref(wp)):
        w = wp.rcNormalPosition.right - wp.rcNormalPosition.left
        h = wp.rcNormalPosition.bottom - wp.rcNormalPosition.top
        if w > 0 and h > 0:
            return w, h
    return _rect(hwnd)[2:]


def capture_window(hwnd):
    """Chụp nội dung cửa sổ qua PrintWindow — hoạt động cả khi cửa sổ thu nhỏ.
    Trả về ảnh BGR, hoặc None nếu thất bại.
    ponytail: một số app tăng tốc phần cứng (game/trình duyệt) vẫn trả khung đen;
    khi đó người dùng nên chọn màn hình thay thế."""
    hwnd = int(hwnd)
    w, h = _window_restored_size(hwnd)
    if w <= 0 or h <= 0:
        return None
    hwnd_dc = user32.GetWindowDC(hwnd)
    if not hwnd_dc:
        return None
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    if not mem_dc or not bmp:
        if mem_dc:
            gdi32.DeleteDC(mem_dc)
        if bmp:
            gdi32.DeleteObject(bmp)
        user32.ReleaseDC(hwnd, hwnd_dc)
        return None
    old = gdi32.SelectObject(mem_dc, bmp)
    PW_RENDERFULLCONTENT = 2
    user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0  # BI_RGB

    buf = ctypes.create_string_buffer(w * h * 4)
    ok = gdi32.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bmi), 0)  # DIB_RGB_COLORS

    gdi32.SelectObject(mem_dc, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)

    if ok <= 0:
        return None
    img = np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 4))
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def window_at_cursor():
    """Cửa sổ gốc (top-level) nằm ngay dưới con trỏ chuột."""
    pt = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(pt)):
        return None
    hwnd = user32.WindowFromPoint(pt)
    if not hwnd:
        return None
    root = user32.GetAncestor(hwnd, 2)  # GA_ROOT
    if not root:
        root = hwnd
    return _window_info(root)


class TimelapseApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("1200x820")

        self.sct = mss.mss()
        self.cap = cv2.VideoCapture(WEBCAM_ID)

        self.recording = False
        self.writer = None
        self.out_path = ""
        self.frames = 0
        self.start_time = 0.0
        self.next_capture = 0.0

        self.targets = []          # list các lựa chọn
        self.current = None        # target đang chọn (None = màn hình chính)
        self.photo = None
        self.last_fg = None        # cửa sổ theo dõi gần nhất (bỏ qua chính app)

        # Webcam PiP — vị trí/kích thước chuẩn hóa
        self.cam_x = CAM_X
        self.cam_y = CAM_Y
        self.cam_scale = CAM_SCALE
        self._drag_mode = None     # None | "move" | "resize"
        self._drag_offset = (0, 0)
        self._drag_start = (0, 0, 0)

        self.pw = PREVIEW_WIDTH
        self.ph = int(PREVIEW_WIDTH * SCREEN_HEIGHT / SCREEN_WIDTH)

        self._font_cache = {}

        self.interval_var = tk.StringVar(value=str(DEFAULT_INTERVAL))
        self.fps_var = tk.StringVar(value=str(DEFAULT_FPS))
        self.follow_var = tk.BooleanVar(value=False)
        self.mouse_follow_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Sẵn sàng")

        self._build_ui()
        self._refresh_targets()
        self.root.after(40, self._tick)

    # ---------- UI ----------
    def _build_ui(self):
        ctrl = ttk.Frame(self.root, padding=8)
        ctrl.pack(fill="x")

        ttk.Label(ctrl, text="Chọn màn hình / cửa sổ:").grid(row=0, column=0, sticky="w")
        self.target_box = ttk.Combobox(ctrl, state="readonly", width=54)
        self.target_box.grid(row=0, column=1, padx=6)
        self.target_box.bind("<<ComboboxSelected>>", self._on_select)

        ttk.Button(ctrl, text="Làm mới", command=self._refresh_targets).grid(row=0, column=2, padx=4)
        ttk.Checkbutton(ctrl, text="Theo dõi cửa sổ đang dùng", variable=self.follow_var,
                        command=self._on_follow).grid(row=0, column=3, padx=8)
        ttk.Checkbutton(ctrl, text="Theo dõi app dưới chuột", variable=self.mouse_follow_var,
                        command=self._on_follow).grid(row=0, column=4, padx=8)

        ttk.Label(ctrl, text="Interval (s):").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(ctrl, textvariable=self.interval_var, width=6).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(ctrl, text="FPS:").grid(row=1, column=2, sticky="e")
        ttk.Entry(ctrl, textvariable=self.fps_var, width=6).grid(row=1, column=3, sticky="w")

        self.btn = ttk.Button(ctrl, text="▶ Bắt đầu quay", command=self._toggle_rec)
        self.btn.grid(row=1, column=5, padx=8)

        tip = ("Chọn cửa sổ có tên đúng (kèm tên chương trình: chrome.exe / Code.exe). "
               "Tick 'Theo dõi app dưới chuột' để quay app đang click. "
               "Kéo webcam để di chuyển, kéo góc dưới-phải để đổi kích thước.")
        ttk.Label(ctrl, text=tip, foreground="gray").grid(row=2, column=0, columnspan=6, sticky="w", pady=(6, 0))

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=4)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        ttk.Label(self.root, textvariable=self.status_var).pack(anchor="w", padx=10, pady=4)

    def _refresh_targets(self):
        self.targets = []
        for i, mon in enumerate(self.sct.monitors):
            if i == 0:
                continue  # 0 = toàn bộ desktop ảo, bỏ qua
            self.targets.append({"kind": "monitor", "idx": i,
                                 "label": f"Màn hình {i}  ({mon['width']}x{mon['height']})"})
        for w in list_windows():
            if w["title"] == APP_TITLE:
                continue  # bỏ chính cửa sổ app
            proc = f"[{w['proc']}] " if w["proc"] else ""
            self.targets.append({"kind": "window", "hwnd": w["hwnd"],
                                 "title": w["title"], "proc": w["proc"],
                                 "label": f"{proc}{w['title'][:50]}  ({w['w']}x{w['h']})"})
        self.target_box["values"] = [t["label"] for t in self.targets]
        self.target_box.current(0)
        self.current = self.targets[0] if self.targets else None

    def _on_select(self, _event=None):
        i = self.target_box.current()
        self.current = self.targets[i] if 0 <= i < len(self.targets) else None
        if self.current and self.current["kind"] == "window":
            # Đưa cửa sổ đã chọn lên trước để chụp đúng nội dung (tránh bị cửa sổ khác che)
            user32.ShowWindow(self.current["hwnd"], 9)   # SW_RESTORE
            user32.SetForegroundWindow(self.current["hwnd"])

    def _on_follow(self):
        off = self.follow_var.get() or self.mouse_follow_var.get()
        self.target_box.config(state="disabled" if off else "readonly")

    # ---------- Webcam PiP ----------
    def _cam_box_norm(self):
        """Khung webcam chuẩn hóa (x, y, w, h) theo tỉ lệ khung, đã clamp trong biên."""
        w = self.cam_scale
        aspect = WEBCAM_HEIGHT / WEBCAM_WIDTH
        h = w * aspect * (SCREEN_WIDTH / SCREEN_HEIGHT)
        x = max(0.0, min(self.cam_x, 1.0 - w))
        y = max(0.0, min(self.cam_y, 1.0 - h))
        return x, y, w, h

    def _on_press(self, e):
        x, y, w, h = self._cam_box_norm()
        bx, by = x * self.pw, y * self.ph
        bw, bh = w * self.pw, h * self.ph
        if bx + bw - 16 <= e.x <= bx + bw and by + bh - 16 <= e.y <= by + bh:
            self._drag_mode = "resize"
            self._drag_start = (e.x, e.y, self.cam_scale)
        elif bx <= e.x <= bx + bw and by <= e.y <= by + bh:
            self._drag_mode = "move"
            self._drag_offset = (e.x - bx, e.y - by)
        else:
            self._drag_mode = None

    def _on_drag(self, e):
        if self._drag_mode == "move":
            w, h = self.cam_scale, self.cam_scale * (WEBCAM_HEIGHT / WEBCAM_WIDTH) * (SCREEN_WIDTH / SCREEN_HEIGHT)
            self.cam_x = max(0.0, min(1.0 - w, (e.x - self._drag_offset[0]) / self.pw))
            self.cam_y = max(0.0, min(1.0 - h, (e.y - self._drag_offset[1]) / self.ph))
        elif self._drag_mode == "resize":
            dx = (e.x - self._drag_start[0]) / self.pw
            self.cam_scale = max(0.1, min(0.6, self._drag_start[2] + dx))

    def _on_release(self, _e):
        self._drag_mode = None

    # ---------- Xử lý khung hình ----------
    def _combine(self, screen, webcam):
        x, y, w, h = self._cam_box_norm()
        W, H = screen.shape[1], screen.shape[0]
        px, py = int(x * W), int(y * H)
        pw, ph = max(1, int(w * W)), max(1, int(h * H))
        pip = cv2.resize(webcam, (pw, ph))
        canvas = screen.copy()
        canvas[py:py + ph, px:px + pw] = pip
        cv2.rectangle(canvas, (px, py), (px + pw, py + ph), (0, 255, 0), 2)
        return canvas

    def _update_mouse_target(self):
        w = window_at_cursor()
        if w and w["title"].strip() and w["title"] != APP_TITLE and w["w"] >= 80 and w["h"] >= 80:
            self.current = {"kind": "window", "hwnd": w["hwnd"],
                            "title": w["title"], "proc": w["proc"]}

    def _capture(self):
        """Trả về (frame gộp sạch BGR, tên target)."""
        # Ưu tiên: app dưới chuột > cửa sổ foreground > chọn thủ công
        if self.mouse_follow_var.get():
            self._update_mouse_target()

        region, label = None, ""

        if not self.mouse_follow_var.get() and self.follow_var.get():
            fg = foreground()
            if fg["title"] == APP_TITLE:
                if self.last_fg is None:
                    blank = np.zeros((SCREEN_HEIGHT, SCREEN_WIDTH, 3), np.uint8)
                    return self._combine(blank, self._read_webcam()), "Chọn cửa sổ cần theo dõi"
                fg = self.last_fg
            else:
                self.last_fg = fg
            region = {"left": fg["x"], "top": fg["y"], "width": fg["w"], "height": fg["h"]}
            label = f"{fg['proc']} — {fg['title']}" if fg["proc"] else fg["title"]
        elif self.current and self.current["kind"] == "window":
            hwnd = self.current["hwnd"]
            label = f"{self.current['proc']} — {self.current['title']}" if self.current.get("proc") else self.current["title"]
            if user32.IsIconic(hwnd):
                # Cửa sổ thu nhỏ: dùng PrintWindow để vẫn thấy nội dung
                frame = capture_window(hwnd)
                if frame is None:
                    blank = np.zeros((SCREEN_HEIGHT, SCREEN_WIDTH, 3), np.uint8)
                    return self._combine(blank, self._read_webcam()), "⚠ Không chụp được cửa sổ đang thu nhỏ"
                frame = cv2.resize(frame, (SCREEN_WIDTH, SCREEN_HEIGHT))
                return self._combine(frame, self._read_webcam()), label
            x, y, w, h = _rect(hwnd)
            region = {"left": x, "top": y, "width": w, "height": h}
        else:
            idx = self.current["idx"] if self.current else 1
            region = self.sct.monitors[idx]
            label = f"Màn hình {idx}"

        try:
            shot = self.sct.grab(region)
            screen = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
        except Exception:
            screen = np.zeros((SCREEN_HEIGHT, SCREEN_WIDTH, 3), np.uint8)

        screen = cv2.resize(screen, (SCREEN_WIDTH, SCREEN_HEIGHT))
        return self._combine(screen, self._read_webcam()), label

    def _read_webcam(self):
        ok, wc = self.cap.read()
        if ok and wc is not None:
            return cv2.resize(wc, (WEBCAM_WIDTH, WEBCAM_HEIGHT))
        return np.zeros((WEBCAM_HEIGHT, WEBCAM_WIDTH, 3), np.uint8)

    def _font(self, size):
        size = max(8, int(size))
        f = self._font_cache.get(size)
        if f is None:
            try:
                f = ImageFont.truetype("segoeui.ttf", size)
            except Exception:
                f = ImageFont.load_default()
            self._font_cache[size] = f
        return f

    def _fit_display(self):
        """Kích thước preview vừa khít canvas, giữ tỉ lệ 16:9."""
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 60 or ch < 60:
            cw, ch = PREVIEW_WIDTH, int(PREVIEW_WIDTH * SCREEN_HEIGHT / SCREEN_WIDTH)
        s = min(cw / SCREEN_WIDTH, ch / SCREEN_HEIGHT)
        return max(1, int(SCREEN_WIDTH * s)), max(1, int(SCREEN_HEIGHT * s))

    def _preview(self, frame, label):
        w, h = self._fit_display()
        disp = cv2.resize(frame, (w, h))
        img = Image.fromarray(cv2.cvtColor(disp, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        scale = w / PREVIEW_WIDTH
        font = self._font(22 * scale)
        font_small = self._font(15 * scale)

        text = f"{'REC' if self.recording else 'PREVIEW'}: {label[:60]}"
        color = (255, 60, 60) if self.recording else (60, 200, 60)
        if label.startswith("⚠"):
            color = (255, 165, 0)
        draw.text((10, 8), text, fill=color, font=font)

        if self.recording:
            elapsed = time.monotonic() - self.start_time
            remaining = max(0.0, self.next_capture - time.monotonic())
            draw.text((10, 42),
                      f"{self.frames} khung | {elapsed:.0f}s | chụp tiếp sau {remaining:.1f}s",
                      fill=(255, 255, 255), font=font_small)
            draw.rectangle([0, 0, img.width - 1, img.height - 1],
                           outline=(255, 0, 0), width=max(2, int(4 * scale)))

        # Núm resize ở góc dưới-phải khung webcam
        cx, cy, cw, ch = self._cam_box_norm()
        bx, by = cx * img.width, cy * img.height
        bw, bh = cw * img.width, ch * img.height
        hx, hy = bx + bw - 8, by + bh - 8
        draw.rectangle([hx, hy, hx + 8, hy + 8], fill=(0, 255, 0), outline=(255, 255, 255))

        draw.text((10, img.height - 22),
                  "🖱 kéo webcam để di chuyển · kéo góc xanh để đổi kích thước",
                  fill=(210, 210, 210), font=font_small)
        return img

    # ---------- Vòng lặp chính ----------
    def _tick(self):
        try:
            frame, label = self._capture()
            self.status_var.set(("● ĐANG QUAY — " if self.recording else "○ Xem trước — ") + label)

            if self.recording and time.monotonic() >= self.next_capture:
                self.writer.write(frame)
                self.frames += 1
                interval = self._get_interval()
                self.next_capture += interval
                if time.monotonic() - self.next_capture > interval:
                    self.next_capture = time.monotonic() + interval

            img = self._preview(frame, label)
            self.pw, self.ph = img.width, img.height
            self.photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        except Exception as e:
            self.status_var.set(f"Lỗi: {e}")
        self.root.after(40, self._tick)

    # ---------- Ghi / dừng ----------
    def _get_interval(self):
        try:
            return max(0.5, float(self.interval_var.get()))
        except ValueError:
            return DEFAULT_INTERVAL

    def _get_fps(self):
        try:
            return max(1, int(float(self.fps_var.get())))
        except ValueError:
            return DEFAULT_FPS

    def _output_path(self):
        name = f"{OUTPUT_BASENAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        return os.path.join(OUTPUT_DIR, name)

    def _toggle_rec(self):
        if self.recording:
            self.recording = False
            if self.writer:
                self.writer.release()
                self.writer = None
            self.btn.config(text="▶ Bắt đầu quay")
            self.status_var.set(f"Đã dừng — lưu {self.frames} khung → {self.out_path}")
            print(f"[STOP] {self.frames} frames -> {self.out_path}")
        else:
            self.out_path = self._output_path()
            writer = None
            for codec in CODECS:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                w = cv2.VideoWriter(self.out_path, fourcc, self._get_fps(),
                                    (SCREEN_WIDTH, SCREEN_HEIGHT))
                if w.isOpened():
                    writer = w
                    break
            if writer is None:
                self.status_var.set("Lỗi: không tạo được file video (thiếu codec).")
                print("[ERROR] can not create VideoWriter")
                return
            self.writer = writer
            self.recording = True
            self.frames = 0
            self.start_time = self.next_capture = time.monotonic()
            self.btn.config(text="⏹ Dừng quay")
            self.status_var.set(f"● Đang quay → {self.out_path}")
            print(f"[REC] interval={self._get_interval()}s fps={self._get_fps()} -> {self.out_path}")

    def on_close(self):
        self.recording = False
        if self.writer:
            self.writer.release()
        self.cap.release()
        self.sct.close()
        self.root.destroy()


def main():
    set_dpi_aware()
    root = tk.Tk()
    app = TimelapseApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()

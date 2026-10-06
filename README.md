# Study Time-lapse

Quay time-lapse màn hình + webcam khi học tập, có GUI để **chọn chính xác màn hình / cửa sổ / tab trình duyệt cần quay** và **xem trước trực tiếp** đang quay gì.

## Cài đặt (1 lần)

```powershell
pip install opencv-python mss numpy pillow
```

> Tkinter đi kèm Python, không cần cài.

## Chạy

```powershell
python gui_timelapse.py
```

## Cách dùng từng bước

1. **Chọn nguồn quay** ở dropdown trên cùng:
   - `Màn hình 1 / 2 …` — quay toàn bộ màn hình đó.
   - Các dòng còn lại là **từng cửa sổ đang mở**, có kèm **tên chương trình** (`[chrome.exe]`, `[Code.exe]`…) để phân biệt chính xác. Chọn xong cửa sổ sẽ tự **đưa lên trước** để chụp đúng nội dung.
   - Hoặc tick **"Theo dõi cửa sổ đang dùng"** để tự bám theo cửa sổ đang focus.
2. **Canh góc** nhờ khung xem trước — góc trái luôn hiện `PREVIEW: <tên>` (xanh) cho biết đang nhắm vào đâu.
3. **Webcam** luôn hiện ở góc (picture-in-picture). **Kéo** để di chuyển, **kéo góc xanh** dưới-phải để đổi kích thước.
4. Đặt **Interval** (bao lâu chụp 1 khung) và **FPS** (tốc độ phát lại).
5. Nhấn **▶ Bắt đầu quay**. Khi quay: nhãn đổi thành `REC` (đỏ), có viền đỏ, bộ đếm khung + đồng hồ đếm ngược đến lần chụp kế tiếp.
6. Nhấn **⏹ Dừng quay**. File lưu **cùng thư mục với `gui_timelapse.py`**, tên dạng `timelapse_20261005_143000.mp4`. Đường dẫn đầy đủ hiện ở thanh trạng thái dưới cùng (và in ra terminal).

## Hiểu về time-lapse

Video chỉ ghi **1 khung mỗi `Interval` giây**, rồi phát lại ở tốc độ `FPS`. Ví dụ `Interval = 5`, `FPS = 10`:

| Thời gian học | Số khung | Video ra |
|---|---|---|
| 10 phút | 120 | ~12 giây |
| 1 giờ | 720 | ~72 giây |

Vì vậy khi đang quay, bộ đếm khung **tăng chậm** (mỗi Interval mới +1) — đó là bình thường, không phải bị đứng.

## Ghi chú về tab trình duyệt (Chrome/Edge)

Một tab **không phải** một cửa sổ riêng — nó nằm chung trong cửa sổ trình duyệt. Cách chọn:

- Mở tab bạn muốn quay (tab đó phải **đang hiển thị**), rồi chọn cửa sổ Chrome/Edge có **đúng tên tab** trong dropdown (tên tab nằm trong tiêu đề cửa sổ).
- Hoặc bật **"Theo dõi cửa sổ đang dùng"** rồi cứ chuyển tab bình thường — nó tự bám theo.

## Xử lý sự cố

| Triệu chứng | Nguyên nhân / cách khắc phục |
|---|---|
| Nhấn quay nhưng "không thấy gì" | Kiểm tra file `timelapse_*.mp4` **cùng thư mục script** (không phải thư mục chạy lệnh). Đường dẫn in ở thanh trạng thái + terminal. |
| File ra nhưng không mở được / rỗng | Đổi codec: sửa danh sách `CODECS` ở đầu file, hoặc cài `openh264` (Cisco) nếu máy thiếu H.264. |
| Không thấy webcam | Sửa `WEBCAM_ID` ở đầu file (0, 1, 2…). |
| Cửa sổ chọn rồi nhưng preview đen | Cửa sổ đang bị **thu nhỏ** — mở lại/maximize cửa sổ đó, hoặc chọn màn hình thay thế. |
| Bị cửa sổ khác che | Bản này chụp theo **vùng màn hình**, nên cửa sổ khác đè lên sẽ bị lọt vào. Dùng "Theo dõi cửa sổ đang dùng" để cửa sổ focus luôn ở trên. |

## File trong dự án

| File | Công dụng |
|---|---|
| `gui_timelapse.py` | GUI realtime, chọn màn hình/cửa sổ/tab (khuyến nghị dùng) |
| `timelapse.py` | Bản không GUI: chạy là quay ngay màn hình chính + webcam |
| `main.py` | Bản cũ: chỉ chụp ảnh màn hình lưu JPG (không video) |
| `make_slides.py` | Sinh file `timelapse_slides.pptx` trình bày kết quả |

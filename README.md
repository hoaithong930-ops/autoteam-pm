# AutoTeam PM — Automation Project Manager v2.0
### Phần mềm Quản lý Dự án dành cho Team Tự động hóa
> Oil & Gas · Power Plant · Mining

---

## 📁 Cấu trúc thư mục

```
AutoTeam_PM/
├── INSTALL.bat          ← Chạy lần đầu để cài đặt
├── START_SERVER.bat     ← Khởi động ứng dụng hàng ngày
├── requirements.txt     ← Danh sách thư viện Python
├── backend/
│   └── main.py          ← FastAPI server + SQLite
├── frontend/
│   └── index.html       ← Giao diện web
└── data/
    └── autoteam.db      ← Database SQLite (tự tạo)
```

---

## 🚀 Hướng dẫn cài đặt

### Bước 1 — Cài Python (nếu chưa có)
1. Tải tại: https://www.python.org/downloads/
2. Chạy installer → **bắt buộc tích "Add Python to PATH"**
3. Kiểm tra: mở CMD → gõ `python --version`

### Bước 2 — Cài đặt ứng dụng
1. Giải nén thư mục `AutoTeam_PM` ra ổ đĩa (VD: `C:\AutoTeam_PM\`)
2. Double-click **`INSTALL.bat`**
3. Chờ cài xong (~2 phút, cần Internet)

### Bước 3 — Chạy ứng dụng
1. Double-click **`START_SERVER.bat`**
2. Trình duyệt tự mở tại `http://localhost:8000`
3. Mỗi ngày chỉ cần click `START_SERVER.bat`

---

## 🌐 Truy cập từ máy khác trong mạng LAN

Nếu muốn cả team cùng dùng trên cùng mạng nội bộ:

1. Tìm IP máy chủ: mở CMD → gõ `ipconfig` → ghi lại IPv4 (VD: `192.168.1.100`)
2. Mở **Windows Firewall** → cho phép port **8000**
3. Các máy khác trong team truy cập: `http://192.168.1.100:8000`

---

## 📊 Tính năng

| Module | Mô tả |
|--------|-------|
| Dashboard | Tổng quan: projects, tasks, workload team, deadline hôm nay |
| Dự án | Quản lý dự án Oil & Gas, Power Plant, Mining — có lọc, tìm kiếm |
| Kanban | Phân bổ công việc: Todo → In Progress → Review → Done |
| Thành viên | Card thành viên + kỹ năng chuyên môn + thống kê hiệu suất |
| Tài liệu | P&ID, PLC Program, SCADA, Wiring, Manual — quản lý revision |
| KPI | Biểu đồ hoàn thành, phân bổ ngành, hiệu suất cá nhân |
| Gantt | Timeline tiến độ tổng thể |

---

## 🔧 API Documentation

Sau khi khởi động server, truy cập:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 💾 Backup dữ liệu

Database nằm tại: `data/autoteam.db`
Copy file này để backup. Có thể mở bằng **DB Browser for SQLite** (miễn phí).

---

## 🛑 Tắt server

Quay lại cửa sổ CMD → nhấn **Ctrl + C**

---

## ❓ Hỗ trợ & nâng cấp

Các tính năng có thể bổ sung thêm:
- Phân quyền người dùng (Admin / Engineer / Viewer)
- Import/Export Excel
- Gửi email thông báo deadline
- Tích hợp với hệ thống ERP / SAP
- Deploy lên server nội bộ (Nginx + Systemd)

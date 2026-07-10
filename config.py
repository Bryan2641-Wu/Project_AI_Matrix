# config.py
import os

# ==================================================
# 🌐 網路伺服器基礎設定
# ==================================================
HOST = "0.0.0.0"
PORT = 5000

# ==================================================
# 🔒 系統安全性安全憑證管理
# ==================================================
ADMIN_USER = "admin"
ADMIN_PASSWORD = "your_secure_password"  # 👈 請在此修改你的登入密碼
SESSION_TOKEN = "matrix_secure_session_token_2026"

# ==================================================
# 📁 實體目錄與路徑矩陣設定
# ==================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 資料庫與日誌目錄
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "monitor.db")
LOG_DIR = os.path.join(BASE_DIR, "storage", "logs")       # 🌟 補上這個，解決 LOG_DIR 報錯！

# 多媒體安防儲存目錄
RECORD_DIR = os.path.join(BASE_DIR, "storage", "recordings")
SNAPSHOT_DIR = os.path.join(BASE_DIR, "storage", "snapshots")
CACHE_DIR = os.path.join(BASE_DIR, "static", "cache")

# 確保所有基礎目錄在載入設定時就預先存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(RECORD_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ==================================================
# 📹 攝影機硬體管道分發矩陣
# ==================================================
# 這裡定義了 webcam_stream.py 讀取的關鍵字 CAMERA_CHANNELS
CAMERA_CHANNELS = {
    "cam_0": 0,  # 實體 WebCam 索引 0
    "cam_1": 1,  # 實體 WebCam 索引 1
    "cam_2": 2   # 實體 WebCam 索引 2
}
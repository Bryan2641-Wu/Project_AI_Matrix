import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# 📂 標準化路徑配置
# ==========================================
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "monitor.db")
LOG_PATH = os.path.join(DATA_DIR, "system.log")

STORAGE_DIR = os.path.join(BASE_DIR, "storage")
SNAPSHOT_DIR = os.path.join(STORAGE_DIR, "snapshots")
RECORD_DIR = os.path.join(STORAGE_DIR, "recordings")
CACHE_DIR = os.path.join(BASE_DIR, "static", "cache")

os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs(RECORD_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ==========================================
# 🌐 網路服務設定
# ==========================================
HOST = "0.0.0.0"
PORT = 5000

# ==========================================
# 📹 🌟 多攝影機安防矩陣清單配置 (OOP 升級)
# ==========================================
# 支援多個實體 USB 攝影機 (如 0, 1) 或遠端 IP Camera (RTSP 串流網址)
CAMERA_LIST = {
    "cam_0": 0,       # 研究室大門鏡頭 (Webcam 0)
    "cam_1": 1,       # 研究室座位鏡頭 (Webcam 1，若沒有第二支鏡頭測試時可先填同一個 0)
    "cam_2": 2        # 伺服器機櫃鏡頭 (Webcam 2)
}

HIGH_MODE_WIDTH = 1920
HIGH_MODE_HEIGHT = 1080
HIGH_MODE_QUALITY = 90

SMOOTH_MODE_WIDTH = 1280
SMOOTH_MODE_HEIGHT = 720
SMOOTH_MODE_QUALITY = 60

RECORD_SEGMENT_SECONDS = 60  
MAX_RECORD_SIZE_BYTES = 100 * 1024 * 1024 * 1024
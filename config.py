# config.py
import os

# ==================================================
# 🌐 網路伺服器基礎架構設定
# ==================================================
# 對應功能：Uvicorn 網頁守護引擎的監聽埠口與主機綁定
HOST = "0.0.0.0"  # 允許區域網路內的所有裝置連線
PORT = 5000       # 系統網頁管理介面的固定通訊埠

# ==================================================
# 🔒 系統安全性憑證管理
# ==================================================
# 對應功能：與 create_user.py 建立的使用者帳密庫進行雜湊比對
ADMIN_USER = "admin"
SESSION_TOKEN = "matrix_secure_session_token_2026"  # Cookie 安全校驗權杖

# ==================================================
# 📁 實體目錄與儲存路徑矩陣 (完全自動化防護)
# ==================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. 系統安全性資料夾
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "monitor.db")     # 🌟 對齊：create_user.py 與 webcam_stream.py 讀取的 SQLite 真實路記

# 2. 系統日誌資料夾
LOG_DIR = os.path.join(BASE_DIR, "storage", "logs") # 🌟 對齊：webcam_stream.py 內自動建立資料夾所需變數

# 3. 安防多媒體防斷電儲存區
RECORD_DIR = os.path.join(BASE_DIR, "storage", "recordings")  # 歷史錄影儲存點
SNAPSHOT_DIR = os.path.join(BASE_DIR, "storage", "snapshots") # 手動快照截圖點
CACHE_DIR = os.path.join(BASE_DIR, "static", "cache")          # FFmpeg 回放轉碼快取區

# 🛡️ 守護機制：在加載設定的瞬間，自動在 Windows 建立所有缺失的硬體目錄，防止 IO 異常
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(RECORD_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ==================================================
# 📹 攝影機硬體管道分發矩陣
# ==================================================
# 對應功能：index.html 與 camera.py 用來拉取畫面的實體 WebCam / RTSP 索引地圖
CAMERA_CHANNELS = {
    "cam_0": 0,  # 實體鏡頭通道 0
    "cam_1": 1,  # 實體鏡頭通道 1
    "cam_2": 2   # 實體鏡頭通道 2
}
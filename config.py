# config.py
import os

# ==================================================
# 🌐 網路伺服器基礎架構設定
# ==================================================
HOST = "0.0.0.0"  # 允許區域網路內的所有裝置連線
PORT = 5000       # 系統網頁管理介面的固定埠口

# ==================================================
# 🔒 安全性安全憑證管理
# ==================================================
ADMIN_USER = "admin"
SESSION_TOKEN = "matrix_secure_session_token_2026"  # Cookie 安全校驗權杖

# ==================================================
# 📁 實體目錄與儲存路徑矩陣 (自動建立防護)
# ==================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "monitor.db")     # SQLite 資料庫真實路徑

LOG_DIR = os.path.join(BASE_DIR, "storage", "logs") # 系統日誌資料夾
LOG_PATH = os.path.join(LOG_DIR, "security_audit.log")

RECORD_DIR = os.path.join(BASE_DIR, "storage", "recordings")  # 歷史錄影儲存點
SNAPSHOT_DIR = os.path.join(BASE_DIR, "storage", "snapshots") # 手動快照截圖點
CACHE_DIR = os.path.join(BASE_DIR, "static", "cache")          # 回放轉碼快取區

# 🛡️ 守護機制：加載設定時，自動建立所有缺失的硬體目錄，防止讀寫報錯
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(RECORD_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ==================================================
# 📹 攝影機硬體管道分發矩陣
# ==================================================
# 🌟 全球變數統一對齊：前後端均使用 CAMERA_CHANNELS
CAMERA_CHANNELS = {
    "cam_0": 0,  # 實體鏡頭通道 0
    "cam_1": 1,  # 實體鏡頭通道 1
    "cam_2": 2   # 實體鏡頭通道 2
}
# webcam_stream.py
import os
import sqlite3  # 🌟 導入 SQLite3 模組，用於對接本地安全帳密庫
import hashlib
import datetime
import logging
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import socketio
import cv2

import config
from camera import VideoCamera # 🌟 核心：在此處導入 camera 模組內完整的 VideoCamera 類別

# ==================================================
# 🪵 系統安全審計日誌配置
# ==================================================
log_format = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(subsystem)s] %(message)s', '%Y-%m-%d %H:%M:%S')
file_handler = logging.FileHandler(config.LOG_PATH, encoding="utf-8")
file_handler.setFormatter(log_format)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_format)

logger = logging.getLogger("AI_Matrix_Core")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

def log_system_event(subsystem: str, message: str, level: str = "INFO"):
    extra = {"subsystem": subsystem}
    if level == "WARNING": logger.warning(message, extra=extra)
    elif level == "ERROR": logger.error(message, extra=extra)
    else: logger.info(message, extra=extra)

# ==================================================
# 🔌 初始化 Socket.IO 異步通訊矩陣
# ==================================================
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
cameras = {} # 用於常駐存放各頻道相機物件的暫存器

# ==================================================
# ⏳ 2026 FastAPI Lifespan 異步生命週期控管
# ==================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*50)
    print("[安防中心] 正在初始化多鏡頭核心矩陣 (純淨高畫質串流模式)...")
    
    # 讀取 config.py 裡的 CAMERA_CHANNELS 自動實體化所有相機線路
    for cam_id, source in config.CAMERA_CHANNELS.items():
        cameras[cam_id] = VideoCamera(cam_id=cam_id, source=source)
        print(f"✅ 攝影機管道 [{cam_id.upper()}] 初始化成功，獨立錄影執行緒已開工。")
    print("="*50 + "\n")
    
    log_system_event("SYSTEM", "🚀 多鏡頭相機矩陣控制台已完全就緒。")
    yield # 💾 伺服器在此掛起穩定運作
    
    # 當服務關閉，徹底釋放硬體管道
    log_system_event("SYSTEM", "🛑 接收到關閉訊號，正在安全釋放所有硬體管道...")
    for cam in cameras.values(): 
        cam.shutdown()

# ==================================================
# ⚡ 網頁主框架實體化與資源掛載
# ==================================================
app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 用 SocketIO 包裹最外層，產出 Uvicorn 發動實體 `sio_app`
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

# ==================================================
# 🔒 二次安全驗證工具 (SHA-256 資料庫原生核對)
# ==================================================
def is_authenticated(request: Request) -> bool:
    return request.cookies.get("session_token") == config.SESSION_TOKEN

def verify_password(plain_password: str, stored_password: str) -> bool:
    try:
        salt, stored_hash = stored_password.split(":")
        hash_obj = hashlib.sha256((plain_password + salt).encode('utf-8'))
        return hash_obj.hexdigest() == stored_hash
    except Exception: 
        return False

# ==================================================
# 🛣️ 網頁主控制台面路由控制
# ==================================================
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    # 🌟 變數對齊修正：將 camera_channels 傳給前端 index.html，解決 UndefinedError
    return templates.TemplateResponse(
        request=request, name="index.html", context={"camera_channels": config.CAMERA_CHANNELS}
    )

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})

@app.post("/login")
async def handle_login(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    
    try:
        # 連線至對齊 config.DB_PATH 的 SQLite3 資料庫驗證使用者註冊的加密密碼
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        if row and verify_password(password, row[0]):
            response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(key="session_token", value=config.SESSION_TOKEN, httponly=True)
            log_system_event("SECURITY", f"🔐 管理員 [{username}] 成功通過資料庫驗證登入系統。")
            return response
    except Exception as e:
        log_system_event("SYSTEM", f"資料庫讀取異常: {e}", level="ERROR")
    
    log_system_event("SECURITY", f"💥 登入失敗：帳號或密碼不匹配 [{username}] ！", level="WARNING")
    return templates.TemplateResponse(request=request, name="login.html", context={"error": "帳號或密碼錯誤，拒絕存取。"})

@app.get("/logout")
def handle_logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_token")
    log_system_event("SECURITY", "🚪 使用者 [admin] 已安全離線。")
    return response

# ==================================================
# 📹 即時串流、手動快照與回放清單 API
# ==================================================
@app.get("/user_access/streaming/{cam_id}")
def video_feed(cam_id: str, request: Request, mode: str = "smooth"):
    if not is_authenticated(request): 
        raise HTTPException(status_code=401)
    if cam_id not in cameras: 
        raise HTTPException(status_code=404)
    # 呼叫 camera.py 物件裡的影格產生器，向網頁不間斷吐出最新的 JPEG 串流
    return StreamingResponse(cameras[cam_id].get_frame_generator(mode=mode), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/capture_snapshot/{cam_id}")
def capture_snapshot(cam_id: str, request: Request):
    if not is_authenticated(request): 
        raise HTTPException(status_code=401)
    if cam_id not in cameras: 
        return RedirectResponse(url="/")
    
    current_frame = cameras[cam_id].Frame
    if current_frame is not None:
        filename = f"snapshot_{cam_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        # 截取當下那一影格並存入指定的快照目錄中
        cv2.imwrite(os.path.join(config.SNAPSHOT_DIR, filename), current_frame)
        log_system_event("SNAPSHOT", f"📸 系統快照：使用者遠端手動截取攝影機 [{cam_id.upper()}] 畫面 ({filename})")
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/recordings_list/{cam_id}")
def get_recordings_list(cam_id: str, request: Request):
    if not is_authenticated(request): 
        raise HTTPException(status_code=401)
    target_dir = os.path.join(config.RECORD_DIR, cam_id)
    if not os.path.exists(target_dir): 
        return {"recordings": []}
    # 檢索對應資料夾內的所有歷史 .avi 影片並依照時間新舊進行排序，回傳給 stream.js
    files = sorted([f for f in os.listdir(target_dir) if f.endswith(".avi")], key=lambda x: os.path.getmtime(os.path.join(target_dir, x)), reverse=True)
    return {"recordings": files}

@sio.event
async def connect(sid, environ): 
    log_system_event("SECURITY", f"👥 使用者 [admin] 已建立雙向監控連線。")

if __name__ == "__main__":
    import uvicorn
    print(f"📡 網頁伺服器正在主機 {config.HOST}:{config.PORT} 上啟動...")
    # 🌟 啟動完全體常駐：確保與最底下的實體變數完全同名
    uvicorn.run("webcam_stream:sio_app", host=config.HOST, port=config.PORT, reload=False)
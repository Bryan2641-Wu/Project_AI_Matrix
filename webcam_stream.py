# webcam_stream.py
import os
import sqlite3
import hashlib
import datetime
import logging
import asyncio
import psutil  
import torch   # 🌟 新增：引入 PyTorch 用於偵測 GPU 狀態
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import socketio
import cv2

import config
from camera import VideoCamera

# ==================================================
# 🪵 系統安全與事件日誌配置
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
# 🔌 初始化 Socket.IO 異步雙向監控矩陣
# ==================================================
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
cameras = {}

# 🌟 全面升級：硬體背景輪詢器，計算更詳盡的電腦指標
async def background_hw_monitor():
    # 初始化網路計數器，用於計算每秒流量
    old_net = psutil.net_io_counters()
    
    while True:
        try:
            # 1. CPU & RAM
            cpu_usage = psutil.cpu_percent(interval=None)
            ram_info = psutil.virtual_memory()
            ram_usage = ram_info.percent
            
            # 2. DISK 硬碟容量偵測 (計算儲存歷史錄影的專用硬碟)
            disk_info = psutil.disk_usage(config.RECORD_DIR)
            disk_usage = disk_info.percent
            disk_free_gb = round(disk_info.free / (1024 ** 3), 1) # 轉為 GB
            
            # 3. NET 網速動態計算 (每秒流量相減)
            new_net = psutil.net_io_counters()
            sent_bytes = new_net.bytes_sent - old_net.bytes_sent
            recv_bytes = new_net.bytes_recv - old_net.bytes_recv
            old_net = new_net # 更新計數器
            
            # 轉為常見的 Mbps
            net_up_mbps = round((sent_bytes * 8) / (1024 * 1024), 2)
            net_down_mbps = round((recv_bytes * 8) / (1024 * 1024), 2)
            
            # 4. GPU 顯卡安全偵測
            gpu_name = "NVIDIA GeForce RTX 5070 Ti"
            gpu_status = "STANDBY" # 去 YOLO 模式下顯卡處於常駐待命狀態
            if torch.cuda.is_available():
                gpu_status = "CUDA ACTIVE (OFFLOADED)"

            # 透過 WebSocket 將五大數據一體化廣播
            await sio.emit('hw_update', {
                'cpu': cpu_usage,
                'ram': ram_usage,
                'disk_percent': disk_usage,
                'disk_free': f"{disk_free_gb} GB 剩餘",
                'net_up': f"{net_up_mbps} Mbps",
                'net_down': f"{net_down_mbps} Mbps",
                'gpu_name': gpu_name,
                'gpu_status': gpu_status,
                'time': datetime.datetime.now().strftime('%H:%M:%S')
            })
        except Exception as e:
            print(f"全硬體監控廣播異常: {e}")
        await asyncio.sleep(1)

# ==================================================
# ⏳ FastAPI Lifespan 生命週期管理器
# ==================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*50)
    print("[安防中心] 正在初始化多鏡頭核心矩陣 (純淨高畫質串流模式)...")
    
    for cam_id, source in config.CAMERA_CHANNELS.items():
        cameras[cam_id] = VideoCamera(cam_id=cam_id, source=source)
        print(f"✅ 攝影機管道 [{cam_id.upper()}] 初始化成功，獨立錄影執行緒已開工。")
    print("="*50 + "\n")
    
    log_system_event("SYSTEM", "🚀 多鏡頭相機矩陣控制台已完全就緒。")
    sio.start_background_task(background_hw_monitor)
    yield
    log_system_event("SYSTEM", "🛑 接收到關閉訊號，正在安全釋放所有硬體管道...")
    for cam in cameras.values(): cam.shutdown()

# ==================================================
# ⚡ 網頁主框架實體化與資源掛載
# ==================================================
app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

# ==================================================
# 🔒 安全性驗證小工具 (SHA-256 資料庫原生比對)
# ==================================================
def is_authenticated(request: Request) -> bool:
    return request.cookies.get("session_token") == config.SESSION_TOKEN

def verify_password(plain_password: str, stored_password: str) -> bool:
    try:
        salt, stored_hash = stored_password.split(":")
        hash_obj = hashlib.sha256((plain_password + salt).encode('utf-8'))
        return hash_obj.hexdigest() == stored_hash
    except Exception: return False

# ==================================================
# 🛣️ 網頁控制台面路由矩陣
# ==================================================
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request, name="index.html", context={"camera_channels": config.CAMERA_CHANNELS}
    )

@app.get("/all_cams", response_class=HTMLResponse)
def all_cameras_wall(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request, name="all_cams.html", context={"camera_channels": config.CAMERA_CHANNELS}
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
# 📹 即時串流與安防錄影控制 API
# ==================================================
@app.get("/user_access/streaming/{cam_id}")
def video_feed(cam_id: str, request: Request, mode: str = "smooth"):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    if cam_id not in cameras: raise HTTPException(status_code=404)
    return StreamingResponse(cameras[cam_id].get_frame_generator(mode=mode), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/capture_snapshot/{cam_id}")
def capture_snapshot(cam_id: str, request: Request):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    if cam_id not in cameras: return RedirectResponse(url="/")
    current_frame = cameras[cam_id].Frame
    if current_frame is not None:
        filename = f"snapshot_{cam_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(os.path.join(config.SNAPSHOT_DIR, filename), current_frame)
        log_system_event("SNAPSHOT", f"📸 系統快照：使用者遠端手動截取攝影機 [{cam_id.upper()}] 畫面 ({filename})")
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/recordings_list/{cam_id}")
def get_recordings_list(cam_id: str, request: Request):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    target_dir = os.path.join(config.RECORD_DIR, cam_id)
    if not os.path.exists(target_dir): return {"recordings": []}
    files = sorted([f for f in os.listdir(target_dir) if f.endswith(".avi")], key=lambda x: os.path.getmtime(os.path.join(target_dir, x)), reverse=True)
    return {"recordings": files}

@sio.event
async def connect(sid, environ): 
    log_system_event("SECURITY", f"👥 使用者 [admin] 已建立雙向監控連線。")

if __name__ == "__main__":
    import uvicorn
    print(f"📡 網頁伺服器正在主機 {config.HOST}:{config.PORT} 上啟動...")
    uvicorn.run("webcam_stream:sio_app", host=config.HOST, port=config.PORT, reload=False)
import os
import datetime
import sqlite3
import asyncio
import logging
import shutil
import hashlib
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request, HTTPException, status, Form, Query
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import socketio
import cv2
import config
from ultralytics import YOLO
from camera import VideoCamera
import psutil

try:
    import GPUtil
    HAS_GPU_LIB = True
except ImportError:
    HAS_GPU_LIB = False
from apscheduler.schedulers.asyncio import AsyncIOScheduler

connected_sessions = {}
cameras = {}

# ==========================================
# 📝 自動輪轉日誌系統
# ==========================================
log_handler = RotatingFileHandler(config.LOG_PATH, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
log_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_handler.setFormatter(log_formatter)
logger = logging.getLogger("MonitorSystem")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

def log_system_event(event_type: str, message: str, filepath: str = None):
    level = "ERROR" if "❌" in message or "錯誤" in message else ("WARNING" if "⚠️" in message else "INFO")
    if level == "WARNING": logger.warning(f"[{event_type}] {message}")
    elif level == "ERROR": logger.error(f"[{event_type}] {message}")
    else: logger.info(f"[{event_type}] {message}")
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO system_events (event_type, message) VALUES (?, ?)", (event_type, message))
        conn.commit()
        conn.close()
    except Exception as e: logger.error(f"[DB_ERROR] 無法寫入資料庫: {e}")
    try: loop = asyncio.get_event_loop()
    except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    asyncio.run_coroutine_threadsafe(sio.emit('new_log', {'message': message}), loop)

# ==========================================
# 🔒 原生安全密碼校驗驗證器 (SHA-256 + 隨機鹽值)
# ==========================================
def is_authenticated(request: Request): 
    return request.cookies.get("server_session") == "authenticated_pass"

def get_username_from_cookie(cookie_str: str):
    if not cookie_str: return "Unknown"
    for p in cookie_str.split(";"):
        if "active_user=" in p: return p.split("active_user=")[1].strip()
    return "Admin"

def verify_password(plain_password: str, stored_password: str) -> bool:
    try:
        salt, stored_hash = stored_password.split(":")
        hash_obj = hashlib.sha256((plain_password + salt).encode('utf-8'))
        return hash_obj.hexdigest() == stored_hash
    except Exception:
        return False

# ==========================================
# 🧹 每日凌晨自動維護排程與效能監控
# ==========================================
async def daily_health_cleanup():
    log_system_event("SYSTEM", "🧹 [核心維護] 啟動每日凌晨健康維護清理程式...")
    try:
        if os.path.exists(config.CACHE_DIR):
            shutil.rmtree(config.CACHE_DIR)
            os.makedirs(config.CACHE_DIR, exist_ok=True)
        import gc; gc.collect()
        import torch; 
        if torch.cuda.is_available(): torch.cuda.empty_cache()
        log_system_event("SYSTEM", "✅ [核心維護] 每日系統維護維護清理完成。")
    except Exception as e: 
        log_system_event("SYSTEM", f"❌ 定時維護失敗: {e}")

async def hardware_monitor_worker():
    while True:
        try:
            cpu_usage = psutil.cpu_percent()
            ram_usage = psutil.virtual_memory().percent
            disk = psutil.disk_usage(config.STORAGE_DIR)
            disk_free_gb = round(disk.free / (1024**3), 1)
            
            gpu_temp, gpu_load = 0, 0
            import torch
            if torch.cuda.is_available() and HAS_GPU_LIB:
                gpus = GPUtil.getGPUs()
                if gpus: gpu_temp, gpu_load = int(gpus[0].temperature), int(gpus[0].load * 100)
            await sio.emit('sys_metrics', {"cpu": cpu_usage, "ram": ram_usage, "disk_free": disk_free_gb, "gpu_load": gpu_load, "gpu_temp": gpu_temp, "gpu_active": torch.cuda.is_available(), "online_count": len(connected_sessions)})
        except Exception: pass
        await asyncio.sleep(2.0)

# ==========================================
# ⏳ 🌟 2026 工業級 Lifespan 異步生命週期管理器
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # [STARTUP] 伺服器啟動邏輯
    print("\n" + "="*50)
    print("[AI 安防中心] 正在初始化多鏡頭核心矩陣...")
    
    if os.path.exists('yolov8n.onnx'):
        model_path = "yolov8n.onnx"
        print("💡 偵測到 yolov8n.onnx 引擎，正在掛載 onnxruntime-gpu 加速鏈...")
    else:
        model_path = "yolov8n.pt"
        print("⚠️ 未發現 ONNX 模型，自動降級至標準 .pt 權重模式。")
        
    shared_yolo = YOLO(model_path)
    # 🌟 新增：強迫 YOLO 外殼在大腦初始化時不准碰不相容的 PyTorch CUDA 內核
    shared_yolo.to("cpu") 
    print(f"👉 AI 大腦模型載入成功: {model_path}")
    
    for cam_id, source in config.CAMERA_LIST.items():
        try:
            cameras[cam_id] = VideoCamera(cam_id, source, shared_yolo)
            print(f"✅ 攝影機管道 [{cam_id.upper()}] 初始化成功，獨立推理執行緒已開工。")
        except Exception as e:
            print(f"❌ 攝影機管道 [{cam_id.upper()}] 初始化失敗: {e}")
    print("="*50 + "\n")

    asyncio.create_task(hardware_monitor_worker())
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_health_cleanup, 'cron', hour=4, minute=0)
    scheduler.start()
    logger.info(f"🚀 AI 多鏡頭相機矩陣控制台已完全就緒。")
    
    yield # 💾 提供網頁服務
    
    # [SHUTDOWN] 安全釋放
    print("[AI 安防中心] 正在安全釋放所有攝影機資源...")
    for cam in cameras.values(): 
        cam.shutdown()

# ==========================================
# ⚡ 🌟 終極順序修正：必須先建立 app 並 mount 資源，最後才丟給 socketio 打包！
# ==========================================
app = FastAPI(title="AI Smart Multi-Camera Matrix Central", lifespan=lifespan)

# 🔥 核心關鍵：先將靜態路徑註冊至 FastAPI 地圖
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 🔒 接著建立 SocketIO，並將「已經掛載好靜態資源的 app」當成參數包裝起來！
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# ==========================================
# 🔒 登入後台系統路由
# ==========================================
@app.get("/login")
def login_page(request: Request, error: str = None): 
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"error": error}
    )

@app.post("/login")
def handle_login(username: str = Form(...), password: str = Form(...)):
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        if row and verify_password(password, row[0]):
            response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(key="server_session", value="authenticated_pass", httponly=True)
            response.set_cookie(key="active_user", value=username, httponly=False)
            log_system_event("SECURITY", f"✅ 管理員 [{username}] 成功通過安全性驗證登入系統。")
            return response
        else:
            log_system_event("SECURITY", f"🚨 警告：登入失敗，嘗試帳號: {username}")
            return RedirectResponse(url="/login?error=帳號或密碼錯誤，拒絕存取！", status_code=status.HTTP_303_SEE_OTHER)
    except Exception:
        return RedirectResponse(url="/login?error=系統錯誤。", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/logout")
def handle_logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("server_session")
    response.delete_cookie("active_user")
    return response

# ==========================================
# 👥 WebSocket 即時多用戶狀態聯動
# ==========================================
@sio.event
async def connect(sid, environ):
    cookie_str = environ.get("HTTP_COOKIE", "")
    if "authenticated_pass" not in cookie_str: return False
    username = get_username_from_cookie(cookie_str)
    connected_sessions[sid] = {"username": username, "login_time": datetime.datetime.now().strftime("%H:%M:%S")}
    await sio.emit('update_users', [user["username"] for user in connected_sessions.values()])
    log_system_event("SECURITY", f"👥 使用者 [{username}] 已建立雙向監控連線。")

@sio.event
async def disconnect(sid):
    if sid in connected_sessions:
        username = connected_sessions[sid]["username"]
        del connected_sessions[sid]
        await sio.emit('update_users', [user["username"] for user in connected_sessions.values()])
        log_system_event("SECURITY", f"🚪 使用者 [{username}] 已安全離線。")

# ==========================================
# 📹 儀表板主路由與串流分發
# ==========================================
@app.get("/")
def index(request: Request):
    if not is_authenticated(request): return RedirectResponse(url="/login")
    history_logs = []
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT strftime('%H:%M:%S', datetime(timestamp, 'localtime')), message FROM system_events ORDER BY id DESC LIMIT 10")
        history_logs = cursor.fetchall()[::-1]; conn.close()
    except Exception: pass
    
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"cameras": config.CAMERA_LIST, "history_logs": history_logs}
    )

# 修改前：def video_feed(cam_id: str, mode: str = "smooth"):
# 🌟 修正後：補上 request: Request
@app.get("/user_access/streaming/{cam_id}")
def video_feed(cam_id: str, request: Request, mode: str = "smooth"):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    if cam_id not in cameras: raise HTTPException(status_code=404, detail="攝影機不存在")
    return StreamingResponse(cameras[cam_id].get_frame_generator(mode), media_type="multipart/x-mixed-replace; boundary=frame")

# 修改前：def get_recordings_list(cam_id: str):
# 🌟 修正後：同樣補上 request: Request
@app.get("/recordings_list/{cam_id}")
def get_recordings_list(cam_id: str, request: Request):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    target_dir = os.path.join(config.RECORD_DIR, cam_id)
    if not os.path.exists(target_dir): return {"videos": []}
    files = [f for f in os.listdir(target_dir) if f.endswith('.avi')]
    if cam_id in cameras and cameras[cam_id].current_record_file:
        files = [f for f in files if f != os.path.basename(cameras[cam_id].current_record_file)]
    files.sort(reverse=True)
    return {"videos": files}

@app.get("/request_playback/{cam_id}/{avi_filename}")
async def request_playback(cam_id: str, avi_filename: str):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    avi_path = os.path.join(config.RECORD_DIR, cam_id, avi_filename)
    if not os.path.exists(avi_path): raise HTTPException(status_code=404)
    mp4_filename = avi_filename.replace(".avi", ".mp4")
    mp4_path = os.path.join(config.CACHE_DIR, mp4_filename)
    web_url = f"/static/cache/{mp4_filename}"
    if os.path.exists(mp4_path): return {"status": "ready", "url": web_url}
    
    cmd = ["ffmpeg", "-y", "-vsync", "0", "-hwaccel", "cuda", "-i", avi_path, "-c:v", "hevc_nvenc", "-preset", "p1", "-cq", "32", "-c:a", "aac", mp4_path]
    try:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await process.communicate()
        if process.returncode == 0:
            log_system_event("SYSTEM", f"🎬 影像檔案 {avi_filename} 已透過獨立顯卡加速完成轉碼。")
            return {"status": "ready", "url": web_url}
    except Exception: pass
    raise HTTPException(status_code=500)

# 修改前：def capture_snapshot(cam_id: str):
# 🌟 修正後：補上 request: Request
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webcam_stream:socket_app", host=config.HOST, port=config.PORT, reload=False)
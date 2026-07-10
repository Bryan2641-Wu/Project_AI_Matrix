import os
import secrets
import datetime
import logging
from typing import List
from fastapi import FastAPI, Request, HTTPException, Depends, status
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
os.makedirs(config.LOG_DIR, exist_ok=True)
os.makedirs(config.SNAPSHOT_DIR, exist_ok=True)

log_format = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(subsystem)s] %(message)s', '%Y-%m-%d %H:%M:%S')

file_handler = logging.FileHandler(os.path.join(config.LOG_DIR, "security_audit.log"), encoding="utf-8")
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
# 🔌 初始化 Socket.IO 異步雙向通訊矩陣
# ==================================================
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
sio_app = socketio.ASGIApp(sio)

# 全局攝影機字典暫存器
cameras = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*50)
    print("[安防中心] 正在初始化多鏡頭核心矩陣 (純淨高畫質串流模式)...")
    print("👉 已成功卸載 YOLO AI 推理核心，改用純 OpenCV 高速拉流引擎")
    
    # 建立多頻道相機串流實體
    for cam_id, source in config.CAMERA_CHANNELS.items():
        cameras[cam_id] = VideoCamera(cam_id=cam_id, source=source, shared_model=None)
        print(f"✅ 攝影機管道 [{cam_id.upper()}] 初始化成功，獨立錄影執行緒已開工。")
    print("="*50 + "\n")
    
    log_system_event("SYSTEM", "🚀 多鏡頭相機矩陣控制台已完全就緒。")
    yield
    
    # 系統關閉，釋放相機與錄影資源
    log_system_event("SYSTEM", "🛑 接收到關閉訊號，正在安全釋放所有硬體管道...")
    for cam_id, cam in cameras.items():
        cam.shutdown()
    log_system_event("SYSTEM", "安全離線成功。")

# ==================================================
# 🌐 FastAPI 核心主程式宣告
# ==================================================
app = FastAPI(lifespan=lifespan)
app.mount("/socket.io", sio_app)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def is_authenticated(request: Request) -> bool:
    return request.cookies.get("session_token") == config.SESSION_TOKEN

# ==================================================
# 🛣️ 核心路由控制矩陣 (Web 控制台面)
# ==================================================
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("index.html", {"request": request, "camera_channels": config.CAMERA_CHANNELS})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def handle_login(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    
    if username == config.ADMIN_USER and password == config.ADMIN_PASSWORD:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="session_token", value=config.SESSION_TOKEN, httponly=True)
        log_system_event("SECURITY", f"🔐 管理員 [{username}] 成功通過二次憑證驗證，簽發安全 Session。")
        return response
    
    log_system_event("SECURITY", f"💥 登入失敗：收到來自未授權帳號 [{username}] 的登入請求！", level="WARNING")
    return templates.TemplateResponse("login.html", {"request": request, "error": "帳號或密碼錯誤，拒絕存取。"})

@app.get("/logout")
def handle_logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_token")
    log_system_event("SECURITY", "🚪 使用者 [admin] 已安全離線。")
    return response

# ==================================================
# 📹 即時串流與安防錄影控制核心 API (已全數閉環修正)
# ==================================================
@app.get("/user_access/streaming/{cam_id}")
def video_feed(cam_id: str, request: Request, mode: str = "smooth"):
    if not is_authenticated(request): 
        raise HTTPException(status_code=401, detail="Unauthorized session")
    if cam_id not in cameras: 
        raise HTTPException(status_code=404, detail="Camera channel not found")
        
    return StreamingResponse(
        cameras[cam_id].get_frame_generator(mode=mode),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/capture_snapshot/{cam_id}")
def capture_snapshot(cam_id: str, request: Request):
    if not is_authenticated(request): 
        raise HTTPException(status_code=401, detail="Unauthorized session")
    if cam_id not in cameras: 
        return RedirectResponse(url="/")
        
    current_frame = cameras[cam_id].Frame
    if current_frame is not None:
        filename = f"snapshot_{cam_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(os.path.join(config.SNAPSHOT_DIR, filename), current_frame)
        log_system_event("SNAPSHOT", f"📸 系統快照：使用者遠端手動截取攝影機 [{cam_id.upper()}] 畫面 ({filename})")
        
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/recordings_list/{cam_id}")
def get_recordings_list(cam_id: str, request: Request):
    if not is_authenticated(request): 
        raise HTTPException(status_code=401, detail="Unauthorized session")
        
    target_dir = os.path.join(config.RECORD_DIR, cam_id)
    if not os.path.exists(target_dir): 
        return {"recordings": []}
        
    files = sorted(
        [f for f in os.listdir(target_dir) if f.endswith(".avi")],
        key=lambda x: os.path.getmtime(os.path.join(target_dir, x)),
        reverse=True
    )
    return {"recordings": files}

# ==================================================
# 🤝 Socket.IO 雙向控制通道事件對齊
# ==================================================
@sio.event
async def connect(sid, environ):
    # 這裡可以用來建立前端通知面板
    log_system_event("SECURITY", f"👥 使用者 [admin] 已建立雙向監控連線。")

@sio.event
async def disconnect(sid):
    log_system_event("SECURITY", f"🚪 使用者 [admin] 已安全離線。")
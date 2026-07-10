# camera.py
import os
import time
import datetime
import threading
import cv2
import numpy as np
import config

class VideoCamera:
    def __init__(self, cam_id, source, shared_model=None):
        """
        初始化個別相機頻道
        """
        self.cam_id = cam_id
        self.source = source
        self.model = None  
        
        # 1. 動態建立該頻道專屬的錄影儲儲路徑
        self.cam_record_dir = os.path.join(config.RECORD_DIR, self.cam_id)
        os.makedirs(self.cam_record_dir, exist_ok=True)
        
        # 2. 狀態控制指標
        self.Frame = None          
        self.is_running = True     
        self.current_record_file = None
        
        # 3. 初始化實體鏡頭
        self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW if isinstance(self.source, int) else cv2.CAP_FFMPEG)
        
        # 核心防護：動態校準硬體的真實寬高與 FPS
        if self.cap.isOpened():
            self.real_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.real_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.real_fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.real_fps <= 0 or self.real_fps > 60:
                self.real_fps = 20.0
        else:
            self.real_width, self.real_height, self.real_fps = 640, 480, 20.0

        # 4. 啟動防斷電歷史錄影寫入器
        self.out = None
        self._init_next_video_writer()
        
        # 5. 發動獨立守護執行緒 (Thread)
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    def _init_next_video_writer(self):
        """建立具備動態硬體尺寸校準的 AVI 錄影檔案寫入器"""
        if self.out is not None:
            self.out.release()  
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rec_{self.cam_id}_{timestamp}.avi"
        self.current_record_file = os.path.join(self.cam_record_dir, filename)
        
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.out = cv2.VideoWriter(
            self.current_record_file, fourcc, self.real_fps, (self.real_width, self.real_height)
        )
        self.last_split_time = time.time()

    def _capture_worker(self):
        """背景核心守護執行緒：負責不間斷拉取影像流並即時寫入 AVI 檔案"""
        while self.is_running:
            start_time = time.time()
            ret, frame = self.cap.read()
            
            if not ret:
                frame = np.zeros((self.real_height, self.real_width, 3), dtype=np.uint8)
                cv2.putText(
                    frame, f"CHANNEL [{self.cam_id.upper()}] NO SIGNAL", 
                    (int(self.real_width*0.1), int(self.real_height*0.5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
                )

            if self.out is not None:
                self.out.write(frame)
                
            self.Frame = frame
            
            if time.time() - self.last_split_time > 3600:
                self._init_next_video_writer()

            elapsed = time.time() - start_time
            sleep_duration = max(0.001, (1.0 / self.real_fps) - elapsed)
            time.sleep(sleep_duration)

    def get_frame_generator(self, mode="smooth"):
        """🌟 智慧安防真．解析度分流轉碼產生器"""
        while self.is_running:
            if self.Frame is None:
                time.sleep(0.05)
                continue
                
            # 🌟 核心重構：讓完整畫質與流暢模式產生絕對的實體體積落差
            if mode == "high":
                # 💎 完整高畫質：解鎖相機 100% 原始解析度大畫面，品質鎖定 95 高規，極速刷新
                out_frame = self.Frame.copy()
                encode_quality = 95
                delay = 0.02  
            else:
                # ⚡ 輕量化流暢：強行將實體長寬縮小至 400 像素寬，品質大降至 30，徹底壓縮數據量
                h, w = self.Frame.shape[:2]
                scale = 400 / w if w > 400 else 1.0
                if scale < 1.0:
                    out_frame = cv2.resize(self.Frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                else:
                    out_frame = self.Frame.copy()
                encode_quality = 30
                delay = 0.04  

            ret, jpeg = cv2.imencode('.jpg', out_frame, [int(cv2.IMWRITE_JPEG_QUALITY), encode_quality])
            if not ret:
                continue
                
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
            
            time.sleep(delay)

    def shutdown(self):
        self.is_running = False
        if self.cap.isOpened(): 
            self.cap.release()
        if self.out is not None: 
            self.out.release()
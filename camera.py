# camera.py
import os
import time
import datetime
import threading
import cv2
import numpy as np
import config

class VideoCamera:
    def __init__(self, cam_id, source):
        """
        初始化個別相機頻道 (工業級安防版)
        """
        self.cam_id = cam_id
        self.source = source
        
        # 1. 建立錄影儲存路徑
        self.cam_record_dir = os.path.join(config.RECORD_DIR, self.cam_id)
        os.makedirs(self.cam_record_dir, exist_ok=True)
        
        # 2. 狀態指標
        self.Frame = None          
        self.is_running = True     
        self.current_record_file = None
        
        # 3. 初始化鏡頭
        self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW if isinstance(self.source, int) else cv2.CAP_FFMPEG)
        
        if self.cap.isOpened():
            self.real_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.real_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.real_fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.real_fps <= 0 or self.real_fps > 60: self.real_fps = 20.0
        else:
            self.real_width, self.real_height, self.real_fps = 640, 480, 20.0

        # 4. 初始化錄影
        self.out = None
        self._init_next_video_writer()
        
        # 5. 啟動背景執行緒
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    def _enforce_storage_limit(self, limit_gb=100):
        """循環錄影機制：超過 100GB 自動覆蓋最舊檔案"""
        limit_bytes = limit_gb * 1024 * 1024 * 1024
        all_files = []
        for root, dirs, files in os.walk(config.RECORD_DIR):
            for file in files:
                if file.endswith(".avi"):
                    path = os.path.join(root, file)
                    try: all_files.append((path, os.path.getmtime(path), os.path.getsize(path)))
                    except: continue
        
        all_files.sort(key=lambda x: x[1])
        total_size = sum(x[2] for x in all_files)
        
        while total_size > limit_bytes and all_files:
            oldest_file = all_files.pop(0)
            try:
                os.remove(oldest_file[0])
                total_size -= oldest_file[2]
            except Exception as e:
                print(f"清理檔案失敗: {e}")

    def _init_next_video_writer(self):
        """建立寫入器並執行空間檢查"""
        self._enforce_storage_limit(limit_gb=100) # 每次建立新片段時檢查硬碟
        
        if self.out is not None: self.out.release()  
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rec_{self.cam_id}_{timestamp}.avi"
        self.current_record_file = os.path.join(self.cam_record_dir, filename)
        
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.out = cv2.VideoWriter(
            self.current_record_file, fourcc, self.real_fps, (self.real_width, self.real_height)
        )
        self.last_split_time = time.time()

    def _capture_worker(self):
        while self.is_running:
            start_time = time.time()
            ret, frame = self.cap.read()
            if not ret:
                frame = np.zeros((self.real_height, self.real_width, 3), dtype=np.uint8)
            
            if self.out is not None: self.out.write(frame)
            self.Frame = frame
            
            if time.time() - self.last_split_time > 3600:
                self._init_next_video_writer()

            elapsed = time.time() - start_time
            time.sleep(max(0.001, (1.0 / self.real_fps) - elapsed))

    def get_frame_generator(self, mode="smooth"):
        """雙碼流轉碼器：根據模式調整解析度與品質"""
        while self.is_running:
            if self.Frame is None:
                time.sleep(0.05)
                continue
                
            if mode == "high":
                out_frame = self.Frame.copy()
                encode_quality = 95
                delay = 0.02
            else:
                h, w = self.Frame.shape[:2]
                scale = 400 / w if w > 400 else 1.0
                out_frame = cv2.resize(self.Frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                encode_quality = 30
                delay = 0.04

            ret, jpeg = cv2.imencode('.jpg', out_frame, [int(cv2.IMWRITE_JPEG_QUALITY), encode_quality])
            if not ret: continue
            
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
            time.sleep(delay)

    def shutdown(self):
        self.is_running = False
        if self.cap.isOpened(): self.cap.release()
        if self.out is not None: self.out.release()
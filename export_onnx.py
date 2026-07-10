# export_onnx.py
from ultralytics import YOLO

def main():
    print("⏳ 正在強制使用 CPU 載入模型並進行 ONNX 結構導出...")
    # 🌟 核心關鍵：指定 device='cpu'，徹底斷絕 PyTorch 調用顯卡內核二進位檔的機會
    model = YOLO("yolov8n.pt")
    
    # 導出為通用 ONNX 格式，並開啟半精度 (Half) 提高未來在 5070Ti 上的推理速度
    success_path = model.export(format="onnx", device="cpu", half=True)
    print(f"🎉 導出成功！檔案已儲存至: {success_path}")

if __name__ == "__main__":
    main()
    
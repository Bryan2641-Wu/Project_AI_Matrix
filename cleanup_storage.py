# cleanup_storage.py
import os
import shutil
import config

def cleanup():
    # 定義要清理的路徑
    target_dirs = [config.RECORD_DIR, config.SNAPSHOT_DIR]
    
    print("⚠️  即將執行安防數據清除程序...")
    print(f"清理目標目錄: {target_dirs}")
    confirm = input("確定要刪除所有錄影檔案與快照嗎？(輸入 y 確認): ")
    
    if confirm.lower() != 'y':
        print("操作已取消。")
        return

    for target in target_dirs:
        if not os.path.exists(target):
            print(f"找不到目錄: {target}，跳過。")
            continue
            
        print(f"正在清理: {target}...")
        
        # 遍歷目錄下的所有檔案
        for root, dirs, files in os.walk(target):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"已刪除: {file}")
                except Exception as e:
                    print(f"無法刪除 {file_path}: {e}")
        
        # 如果是錄影目錄，保留 cam_0, cam_1 等子資料夾結構，只清空內容
        if target == config.RECORD_DIR:
            for d in os.listdir(target):
                d_path = os.path.join(target, d)
                if os.path.isdir(d_path):
                    for sub_file in os.listdir(d_path):
                        os.remove(os.path.join(d_path, sub_file))
            print(f"已清空 {target} 內容。")

    print("✅ 清理程序完成！所有數據已安全移除。")

if __name__ == "__main__":
    cleanup()
import sqlite3
import os
import config
import hashlib
import secrets

def hash_password(password: str) -> str:
    """
    🔒 使用 2026 標準原生密碼學技術：
    產生隨機 16 字節鹽值 (Salt) + SHA-256 進行不可逆雜湊
    """
    salt = secrets.token_hex(16) # 生成隨機鹽值防止彩虹表攻擊
    # 計算雜湊值
    hash_obj = hashlib.sha256((password + salt).encode('utf-8'))
    hashed = hash_obj.hexdigest()
    # 格式化儲存為 salt:hash 的形式存在資料庫
    return f"{salt}:{hashed}"

def init_db_and_create_user():
    print("=" * 50)
    print("🔑 [帳號管理中心] 正在初始化使用者資料庫 (SHA-256 強固版)...")
    print("=" * 50)
    
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    # 建立使用者表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    
    # 建立系統日誌事件表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')
    conn.commit()
    
    username = input("請輸入欲建立的後台管理員帳號: ").strip()
    password = input("請輸入該帳號的密碼: ").strip()
    
    if not username or not password:
        print("❌ 錯誤：帳號或密碼不能為空！")
        conn.close()
        return

    # 使用我們寫好的安全雜湊函數
    hashed_password = hash_password(password)
    
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        print(f"\n✅ 成功建立使用者！帳號: {username}，密碼已透過 SHA-256 與隨機鹽值強固加密。")
    except sqlite3.IntegrityError:
        print(f"\n❌ 建立失敗：帳號 [{username}] 已經存在於資料庫中！")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db_and_create_user()
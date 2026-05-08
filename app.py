from flask import Flask, request
import subprocess
import threading
import re
import time
import os

app = Flask(__name__)

# ===================== 【路径配置，按你的情况写死了】=====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_FOLDER = os.path.join(BASE_DIR, "mc_server")
SERVER_JAR_NAME = "fabric-server-launch.jar"
FULL_JAR_PATH = os.path.join(SERVER_FOLDER, SERVER_JAR_NAME)
JAVA_RAM = "2G"
# ======================================================================

server_proc = None
server_logs = []
online_players = set()
lock = threading.Lock()

join_re = re.compile(r"(\w+) joined the game")
leave_re = re.compile(r"(\w+) left the game")

# 启动前打印所有路径，让你确认
print("=== 路径检查 ===")
print(f"当前程序目录: {BASE_DIR}")
print(f"服务器文件夹: {SERVER_FOLDER}")
print(f"核心文件完整路径: {FULL_JAR_PATH}")
print(f"核心文件是否存在: {os.path.exists(FULL_JAR_PATH)}")
print("================\n")

def log_reader():
    global server_proc
    while True:
        if not server_proc or server_proc.poll() is not None:
            time.sleep(1)
            continue
        try:
            line = server_proc.stdout.readline()
            if not line:
                continue
            line = line.strip()
            with lock:
                server_logs.append(line)
                if len(server_logs) > 200:
                    server_logs.pop(0)
            j = join_re.search(line)
            l = leave_re.search(line)
            if j:
                online_players.add(j.group(1))
            if l:
                online_players.discard(l.group(1))
        except:
            break

def start_server():
    global server_proc
    if server_proc and server_proc.poll() is not None:
        return
    print("正在启动服务器...")
    # 关键：直接用绝对路径指定核心文件
    cmd = [
        "java", f"-Xmx{JAVA_RAM}", f"-Xms{JAVA_RAM}",
        "-jar", FULL_JAR_PATH, "nogui"
    ]
    print(f"执行命令: {' '.join(cmd)}")
    try:
        server_proc = subprocess.Popen(
            cmd,
            cwd=SERVER_FOLDER,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace"
        )
        print("✅ 服务器进程已启动！")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

def stop_server():
    global server_proc
    if not server_proc or server_proc.poll() is not None:
        return
    try:
        server_proc.stdin.write("stop\n")
        server_proc.stdin.flush()
        server_proc.wait(timeout=10)
    except:
        pass
    server_proc = None
    online_players.clear()

def send_command(cmd):
    if not server_proc or server_proc.poll() is not None:
        return False
    try:
        server_proc.stdin.write(cmd + "\n")
        server_proc.stdin.flush()
        return True
    except:
        return False

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        act = request.form.get("action")
        cmd = request.form.get("cmd", "")
        if act == "start":
            start_server()
        elif act == "stop":
            stop_server()
        elif act == "send":
            send_command(cmd.strip())
    
    running = server_proc is not None and server_proc.poll() is None
    with lock:
        logs = server_logs[-100:]
        players = list(online_players)
    
    log_text = "\n".join(logs)
    player_text = "、".join(players) if players else "暂无玩家在线"
    status = '<span style="color:#4cd137">运行中</span>' if running else '<span style="color:#e74c3c">已停止</span>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <title>MC控制器</title>
    <meta http-equiv="refresh" content="3">
    <style>
        body{{background:#12151c;color:#eee;padding:20px;font-family:微软雅黑;}}
        .box{{background:#1e222c;padding:20px;border-radius:10px;margin-bottom:15px;}}
        button{{padding:8px 20px;background:#2196f3;color:white;border:none;border-radius:6px;margin:5px;}}
        input{{width:70%;padding:10px;border-radius:6px;background:#2a2e3a;color:white;border:none;}}
        textarea{{width:100%;height:320px;background:#0b0e14;color:#39ff14;padding:10px;border-radius:6px;border:none;}}
    </style>
    </head>
    <body>
    <div class="box">
        <h2>MC 服务端控制器</h2>
        <p>状态：{status}</p>
        <form method="post">
            {"<button name='action' value='start'>启动</button>" if not running else "<button name='action' value='stop'>关闭</button>"}
        </form>
    </div>
    <div class="box">
        <h3>在线玩家：{len(players)} 人</h3>
        <p>{player_text}</p>
    </div>
    <div class="box">
        <h3>发送指令</h3>
        <form method="post">
            <input type="text" name="cmd" placeholder="输入指令">
            <button name="action" value="send">发送</button>
        </form>
    </div>
    <div class="box">
        <h3>日志</h3>
        <textarea readonly>{log_text}</textarea>
    </div>
    </body>
    </html>
    '''

if __name__ == "__main__":
    threading.Thread(target=log_reader, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
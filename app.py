from flask import Flask, request, render_template, redirect, session
import subprocess
import threading
import time
import os
import locale
import sys

app = Flask(__name__, template_folder="templates")
app.secret_key = "mcdr_panel_ultra"

# ====================== 登录账号 ======================
USERNAME = "admin"
PASSWORD = "123456"

# ====================== 你的 MCDR 路径（已改成你电脑的正确路径！）======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_FOLDER = r"F:\1\mc_web_panel\my_mcdr_server\server"  # 已改成你的真实路径
CONFIG_FILE = os.path.join(SERVER_FOLDER, "server.properties")

server_process = None
log_list = []
players = set()

# 编码设置
encoding = "gbk" if locale.getpreferredencoding() == "cp936" else "utf-8"

# 读取 server.properties
def read_server_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return "# 错误：未找到文件\n路径：" + CONFIG_FILE
    except Exception as e:
        return f"# 读取失败：{str(e)}"

# 日志读取线程
def log_reader():
    global server_process
    while True:
        try:
            if server_process and server_process.poll() is None:
                for line in iter(server_process.stdout.readline, ''):
                    if line:
                        decoded_line = line.strip()
                        log_list.append(decoded_line)
                        if len(log_list) > 200:
                            log_list.pop(0)
                        if "joined the game" in decoded_line:
                            name = decoded_line.split(" ")[-4]
                            players.add(name)
                        if "left the game" in decoded_line:
                            name = decoded_line.split(" ")[-4]
                            players.discard(name)
                    else:
                        break
            else:
                time.sleep(0.1)
        except Exception as e:
            print(f"日志线程出错: {e}", file=sys.stderr)
            time.sleep(1)

# ====================== 登录 ======================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")
        if user == USERNAME and pwd == PASSWORD:
            session["login"] = True
            return redirect("/")
    return render_template("login.html")

# ====================== 主页 ======================
@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("login"):
        return redirect("/login")

    global server_process
    config_content = read_server_config()

    if request.method == "POST":
        action = request.form.get("action")

        # 启动
        if action == "start":
            if not server_process or server_process.poll() is not None:
                os.chdir(SERVER_FOLDER)
                server_process = subprocess.Popen(
                    ["python", "-m", "mcdreforged"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    text=True,
                    encoding=encoding,
                    errors="replace"
                )
                os.chdir(BASE_DIR)

        # 停止
        elif action == "stop":
            if server_process and server_process.poll() is None:
                server_process.stdin.write("stop\n")
                server_process.stdin.flush()

        # 发送指令
        elif action == "send":
            cmd = request.form.get("cmd")
            if server_process and server_process.poll() is None:
                server_process.stdin.write(cmd + "\n")
                server_process.stdin.flush()

        # ====================== 保存配置并重启 ======================
        elif action == "save_config":
            new_config = request.form.get("config_content", "")
            try:
                # 保存配置
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    f.write(new_config)

                # 重启服务器
                if server_process and server_process.poll() is None:
                    server_process.stdin.write("stop\n")
                    server_process.stdin.flush()
                    time.sleep(3)

                os.chdir(SERVER_FOLDER)
                server_process = subprocess.Popen(
                    ["python", "-m", "mcdreforged"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    text=True,
                    encoding=encoding,
                    errors="replace"
                )
                os.chdir(BASE_DIR)
            except Exception as e:
                print(f"保存配置失败: {e}", file=sys.stderr)

    running = server_process is not None and server_process.poll() is None
    return render_template("index.html",
        running=running,
        status="运行中" if running else "已停止",
        player_text="、".join(players) if players else "暂无在线玩家",
        log_text="\n".join(log_list),
        config_content=config_content
    )

# ====================== 退出 ======================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# 新增：日志异步刷新接口
@app.route("/log")
def get_log():
    return "\n".join(log_list)
if __name__ == "__main__":
    threading.Thread(target=log_reader, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
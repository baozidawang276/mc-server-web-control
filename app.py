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

# ====================== 你的 MCDR 路径 ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_FOLDER = os.path.join(BASE_DIR, "my_mcdr_server")

server_process = None
log_list = []
players = set()

# 编码设置（Windows 下为 GBK）
encoding = "gbk" if locale.getpreferredencoding() == "cp936" else "utf-8"

def log_reader():
    global server_process
    while True:
        try:
            if server_process and server_process.poll() is None:
                # 因为我们开启了 text=True，stdout 输出的是 str，不用再 decode
                for line in iter(server_process.stdout.readline, ''):
                    if line:
                        decoded_line = line.strip()
                        log_list.append(decoded_line)
                        if len(log_list) > 200:
                            log_list.pop(0)

                        # 玩家加入/离开识别
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
            print(f"日志读取线程出错: {e}", file=sys.stderr)
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
    if request.method == "POST":
        action = request.form.get("action")

        # ========== 启动 MCDR ==========
        if action == "start":
            if not server_process or server_process.poll() is not None:
                os.chdir(SERVER_FOLDER)
                # 开启 text=True，stdout 直接输出 str，编码自动处理
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

        # ========== 关闭服务器 ==========
        elif action == "stop":
            if server_process and server_process.poll() is None:
                server_process.stdin.write("stop\n")
                server_process.stdin.flush()

        # ========== 发送指令 ==========
        elif action == "send":
            cmd = request.form.get("cmd")
            if server_process and server_process.poll() is None:
                server_process.stdin.write(cmd + "\n")
                server_process.stdin.flush()

    running = server_process is not None and server_process.poll() is None
    return render_template("index.html",
        running=running,
        status="运行中" if running else "已停止",
        player_text="、".join(players) if players else "暂无在线玩家",
        log_text="\n".join(log_list)
    )

# ====================== 退出 ======================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    threading.Thread(target=log_reader, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
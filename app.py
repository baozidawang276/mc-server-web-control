from flask import Flask, request, render_template
import subprocess
import threading
import re
import time
import os


app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))

# 配置
SERVER_FOLDER = "mc_server"
JAVA_CMD = "java -Xmx2G -Xms2G -jar fabric-server-launch.jar nogui"
server_process = None
log_list = []
players = set()

def read_log():
    global server_process
    while True:
        if server_process and server_process.poll() is None:
            line = server_process.stdout.readline()
            if line:
                log_list.append(line.strip())
                if len(log_list) > 100:
                    log_list.pop(0)
                # 玩家上下线
                if "joined the game" in line:
                    name = line.split(" ")[-4]
                    players.add(name)
                if "left the game" in line:
                    name = line.split(" ")[-4]
                    players.discard(name)
        time.sleep(0.01)

@app.route("/", methods=["GET", "POST"])
def index():
    global server_process
    if request.method == "POST":
        action = request.form.get("action")
        if action == "start":
            if not server_process or server_process.poll() is not None:
                server_process = subprocess.Popen(
                    JAVA_CMD.split(),
                    cwd=SERVER_FOLDER,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
        elif action == "stop":
            if server_process and server_process.poll() is None:
                server_process.stdin.write("stop\n")
                server_process.stdin.flush()
        elif action == "send":
            cmd = request.form.get("cmd", "")
            if server_process and server_process.poll() is None:
                server_process.stdin.write(cmd + "\n")
                server_process.stdin.flush()

    running = server_process is not None and server_process.poll() is None
    return render_template("index.html",
        running=running,
        status="运行中" if running else "已停止",
        player_text="、".join(players) if players else "暂无玩家",
        log_text="\n".join(log_list)
    )

if __name__ == "__main__":
    threading.Thread(target=read_log, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
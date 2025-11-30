import socket
import struct
import json
import sys
import subprocess
import time

def _send_json(msg, sock):
    data = json.dumps(msg).encode("utf-8")
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)

def _recv_json_len(sock, n):
    data = b""
    while len(data) < n:
        temp = sock.recv(n - len(data))
        if not temp:
            raise ConnectionResetError
        data += temp
    return data

def _recv_json(sock):
    length = struct.unpack(">I", _recv_json_len(sock, 4))[0]
    return json.loads(_recv_json_len(sock, length).decode())

def main():
    if len(sys.argv) < 5:
        print("Usage: highcard_client.py <host> <port> <userId> <linuxuser>")
        return

    host      = sys.argv[1]
    port      = int(sys.argv[2])
    userId    = int(sys.argv[3])
    linuxuser = sys.argv[4]   # 只是接收，不需要使用

    subprocess.Popen([
        "ssh", "-N",
        "-L", f"{port}:{host}:{port}",
        f"{linuxuser}@linux1.cs.nycu.edu.tw"
    ])
    time.sleep(5)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))

    # --- 下面邏輯跟之前一樣，不重複 ---
    msg = _recv_json(sock)
    print(msg["message"])
    input("Press Enter to draw your cards...")

    _send_json({"type": "DRAW", "userId": userId}, sock)
    result = _recv_json(sock)

    print("\nGame Result:")
    print(json.dumps(result, indent=2))

    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()

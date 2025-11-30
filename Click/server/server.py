# server/server.py
import socket
import json
import struct
import sys
import threading
import time
from datetime import datetime

LOBBY_HOST = "127.0.0.1"
LOBBY_PORT = 22222  # 要跟你的 LobbyServer 一樣

def recv_all(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("socket closed")
        data += chunk
    return data

def send_json(sock, obj):
    data = json.dumps(obj).encode("utf-8")
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)

def recv_json(sock):
    header = recv_all(sock, 4)
    length = struct.unpack(">I", header)[0]
    if length <= 0 or length > 65536:
        raise ValueError("invalid length")
    body = recv_all(sock, length)
    return json.loads(body.decode("utf-8"))

def main():
    if len(sys.argv) < 5:
        print("Usage: server.py matchId roomId startAt user0 [user1 ...]")
        sys.exit(1)

    match_id = int(sys.argv[1])
    room_id = int(sys.argv[2])
    start_at = sys.argv[3]

    # 從 argv 把 userId 拉出來
    user_ids = []
    for arg in sys.argv[4:]:
        if arg.isdigit():
            user_ids.append(int(arg))

    if not user_ids:
        print("No user IDs provided, exit")
        sys.exit(1)

    print(f"[GameServer] matchId={match_id}, roomId={room_id}, users={user_ids}")

    # 1) 開一個遊戲 server 的 listening socket，給玩家連
    game_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    game_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    game_sock.bind(("0.0.0.0", 0))  # port=0 → OS 幫你找空 port
    game_sock.listen(len(user_ids))

    host = "127.0.0.1"
    port = game_sock.getsockname()[1]
    print(f"[GameServer] listening for players on {host}:{port}")

    # 2) 連回 Lobby 的 Game_socket (0.0.0.0:22222)
    lobby_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lobby_sock.connect((LOBBY_HOST, LOBBY_PORT))
    print("[GameServer] connected to Lobby")

    # 第一包給 Lobby：讓它告訴玩家這個 game server 的 host / port
    send_json(lobby_sock, {"host": host, "port": port})

    # 3) 接收玩家結果
    results_lock = threading.Lock()
    player_results = {
        uid: {"finished": False, "score": 0, "lines": 0, "maxCombo": 0}
        for uid in user_ids
    }

    def handle_player(conn):
        try:
            # 第一包：join
            hello = recv_json(conn)
            if hello.get("type") != "join":
                print("[GameServer] invalid first message from client")
                conn.close()
                return

            uid = int(hello.get("userId", -1))
            print(f"[GameServer] player connected uid={uid}")

            if uid not in player_results:
                print("[GameServer] unknown userId, closing")
                conn.close()
                return

            # 第二包：finish
            msg = recv_json(conn)
            if msg.get("type") != "finish":
                print("[GameServer] expected finish message")
                conn.close()
                return

            score = int(msg.get("score", 0))
            lines = int(msg.get("lines", 0))
            max_combo = int(msg.get("maxCombo", 0))

            with results_lock:
                player_results[uid]["finished"] = True
                player_results[uid]["score"] = score
                player_results[uid]["lines"] = lines
                player_results[uid]["maxCombo"] = max_combo

            print(f"[GameServer] result from uid={uid}: score={score}, lines={lines}, maxCombo={max_combo}")

        except Exception as e:
            print(f"[GameServer] handle_player error: {e}")
        finally:
            conn.close()

    # 接滿指定數量的玩家連線，每個丟進 thread
    threads = []
    connected = 0
    while connected < len(user_ids):
        conn, addr = game_sock.accept()
        connected += 1
        print(f"[GameServer] accept player {addr}, {connected}/{len(user_ids)}")
        t = threading.Thread(target=handle_player, args=(conn,), daemon=True)
        t.start()
        threads.append(t)

    # 等所有玩家都送出 finished
    while True:
        with results_lock:
            all_done = all(info["finished"] for info in player_results.values())
        if all_done:
            break
        time.sleep(0.1)

    # 4) 算出勝負，組 GameLog 結果丟回 Lobby
    with results_lock:
        max_score = max(info["score"] for info in player_results.values())
        results = []
        for uid in user_ids:
            info = player_results[uid]
            alive = (info["score"] == max_score)
            results.append({
                "userId": uid,
                "score": info["score"],
                "lines": info["lines"],
                "maxCombo": info["maxCombo"],
                "alive": alive
            })

    end_at = datetime.now().isoformat()

    payload = {
        "matchId": match_id,
        "roomId": room_id,
        "users:[userId]": user_ids,
        "startAt": start_at,
        "endAt": end_at,
        "results": results
    }

    print("[GameServer] sending final result to Lobby:", payload)
    send_json(lobby_sock, payload)

    lobby_sock.close()
    game_sock.close()
    print("[GameServer] shutdown")

if __name__ == "__main__":
    main()

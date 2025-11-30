import socket
import struct
import json
import random
import sys
from datetime import datetime

class HighCardServer:
    def __init__(self, port, matchId, roomId, starttime, p1Id, p2Id):
        # 遊戲 server socket（給兩個玩家連）
        self.game_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.game_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.game_socket.bind(("0.0.0.0", port))
            self.game_socket.listen()
        except OSError:
            raise OSError

        # 連回 Lobby（127.0.0.1:22222）
        self.lobby_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.lobby_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lobby_socket.connect(("127.0.0.1", 22222))

        # match 資訊
        self.matchId = matchId
        self.roomId = roomId
        self.starttime = starttime
        self.p1Id = p1Id
        self.p2Id = p2Id

        # 玩家 socket
        self.p1_socket = None
        self.p2_socket = None

        # 牌組設定
        self.ranks = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]  # 11:J, 12:Q, 13:K, 14:A
        self.suits = ["C", "D", "H", "S"]  # Club, Diamond, Heart, Spade
        # suit 排序：C < D < H < S
        self.suit_value = {s: i for i, s in enumerate(self.suits)}

    # ---- 基本收發工具 ----
    def _send_json(self, msg, sock):
        data = json.dumps(msg).encode("utf-8")
        if len(data) <= 0 or len(data) > 65536:
            sock.close()
            return
        header = struct.pack(">I", len(data))
        try:
            sock.sendall(header + data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _recv_json_len(self, sock, n):
        data = b""
        while len(data) < n:
            temp = sock.recv(n - len(data))
            if not temp:
                raise ConnectionResetError
            data += temp
        return data

    def _recv_json(self, sock):
        length = self._recv_json_len(sock, 4)
        length = struct.unpack(">I", length)[0]
        if length <= 0 or length > 65536:
            sock.close()
            return None
        return json.loads(self._recv_json_len(sock, length).decode())

    # ---- 牌組工具 ----
    def card_to_str(self, rank, suit):
        if rank == 11:
            r = "J"
        elif rank == 12:
            r = "Q"
        elif rank == 13:
            r = "K"
        elif rank == 14:
            r = "A"
        else:
            r = str(rank)
        return f"{r}{suit}"

    def card_score(self, rank, suit):
        # rank 決勝 > suit 決勝，不會平手
        return rank * 4 + self.suit_value[suit]

    def hand_score(self, hand):
        # hand: [(rank,suit),...]
        return max(self.card_score(r, s) for (r, s) in hand)

    # ---- 遊戲主流程 ----
    def run(self):
        print("[HighCard] Waiting for 2 players to connect...")
        p1_sock, addr1 = self.game_socket.accept()
        print(f"[HighCard] Player1 connected from {addr1}")
        p2_sock, addr2 = self.game_socket.accept()
        print(f"[HighCard] Player2 connected from {addr2}")

        self.p1_socket = p1_sock
        self.p2_socket = p2_sock

        # 先送 WELCOME，請玩家按 Enter 抽牌
        welcome_msg = {
            "type": "WELCOME",
            "message": "Welcome to HighCard! Press Enter in this window to draw your cards."
        }
        self._send_json(welcome_msg, self.p1_socket)
        self._send_json(welcome_msg, self.p2_socket)

        # 等兩邊都送 DRAW
        try:
            msg1 = self._recv_json(self.p1_socket)
            msg2 = self._recv_json(self.p2_socket)
        except ConnectionResetError:
            print("[HighCard] Connection reset while waiting for DRAW.")
            return

        if not msg1 or msg1.get("type") != "DRAW":
            print("[HighCard] Player1 did not send DRAW correctly.")
        if not msg2 or msg2.get("type") != "DRAW":
            print("[HighCard] Player2 did not send DRAW correctly.")

        # 建立牌組並洗牌
        deck = [(r, s) for r in self.ranks for s in self.suits]
        random.shuffle(deck)

        # 每人五張
        hand1 = [deck.pop() for _ in range(5)]
        hand2 = [deck.pop() for _ in range(5)]

        score1 = self.hand_score(hand1)
        score2 = self.hand_score(hand2)

        if score1 > score2:
            winner_id = self.p1Id
        else:
            winner_id = self.p2Id

        # 轉成字串 for 顯示
        hand1_str = [self.card_to_str(r, s) for (r, s) in hand1]
        hand2_str = [self.card_to_str(r, s) for (r, s) in hand2]

        # 統一用 GAMEOVER 結構（Lobby 也吃這個）
        now = datetime.now().isoformat()

        gameover = {
            "type": "GAMEOVER",
            "mode": "highcard",
            "tick": 0,
            "matchId": self.matchId,
            "roomId": self.roomId,
            "users:[userId]": [self.p1Id, self.p2Id],
            "startAt": self.starttime,
            "endAt": now,
            "results": [
                {
                    "userId": self.p1Id,
                    "score": score1,
                    "lines": 0,
                    "maxCombo": 0,
                    "alive": (self.p1Id == winner_id)
                },
                {
                    "userId": self.p2Id,
                    "score": score2,
                    "lines": 0,
                    "maxCombo": 0,
                    "alive": (self.p2Id == winner_id)
                }
            ],
            "winnerUserId": winner_id,
            "draw": False,
            # 額外附上手牌（Lobby 不會用，但 client 用來顯示）
            "hands": {
                str(self.p1Id): hand1_str,
                str(self.p2Id): hand2_str
            }
        }

        # 傳給兩個玩家
        self._send_json(gameover, self.p1_socket)
        self._send_json(gameover, self.p2_socket)

        # 傳給 Lobby
        self._send_json(gameover, self.lobby_socket)

        print("[HighCard] Gameover sent, closing sockets.")
        self.p1_socket.close()
        self.p2_socket.close()
        self.lobby_socket.close()
        self.game_socket.close()


# ---- 跟 tetris 一樣的 main：找可用 port 回報 Lobby ----
def _send_json(msg, sock):
    data = json.dumps(msg).encode("utf-8")
    if len(data) <= 0 or len(data) > 65536:
        sock.close()
        return
    header = struct.pack(">I", len(data))
    try:
        sock.sendall(header + data)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


if __name__ == "__main__":
    # argv: matchId roomId startAt p1Id p2Id
    matchId = int(sys.argv[1])
    roomId = int(sys.argv[2])
    startAt = sys.argv[3]
    p1Id = int(sys.argv[4])
    p2Id = int(sys.argv[5])

    for game_port in range(12000, 12021):
        try:
            server = HighCardServer(game_port, matchId, roomId, startAt, p1Id, p2Id)
            print(f"[HighCard] Server bound on port {game_port}")

            # 通知 Lobby 這個遊戲 server host/port（跟 tetris 一樣）
            lobby_sock = server.lobby_socket
            _send_json({
                "host": "127.0.0.1",
                "port": game_port
            }, lobby_sock)

            # 進入遊戲主流程
            server.run()
            break
        except OSError:
            print(f"[HighCard] Port {game_port} already in use, trying next...")

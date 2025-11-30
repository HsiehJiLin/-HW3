import socket, struct, json, random, queue, threading, time, sys
from datetime import datetime

class GameServer:
    def __init__(self, port, matchId, roomId, starttime, p1Id, p2Id):
        self.Game_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.Game_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.Game_socket.bind(("0.0.0.0", port))
            self.Game_socket.listen()
        except OSError:
            raise OSError
        
        self.Lobby_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.Lobby_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.Lobby_socket.connect(("127.0.0.1", 22222))

        #match
        self.matchId = matchId
        self.roomId = roomId
        self.starttime = starttime
        self.p1Id = p1Id
        self.p2Id = p2Id

        #in game
        self.p1_socket = None
        self.p2_socket = None
        self.p1_state = None
        self.p2_state = None
        self.bag1 = None
        self.bag2 = None
        self.tick = 0
        self.W, self.H = 10, 20
        self.TICK_MS = 50
        self.BROADCAST_MS = 200 
        self.gravityPlan = {"mode": "fixed", "dropMs": 500}
        self.SHAPES = {
            "I": [
                [(0,1),(1,1),(2,1),(3,1)],
                [(2,0),(2,1),(2,2),(2,3)],
                [(0,2),(1,2),(2,2),(3,2)],
                [(1,0),(1,1),(1,2),(1,3)]
            ],
            "O": [
                [(1,0),(2,0),(1,1),(2,1)],
                [(1,0),(2,0),(1,1),(2,1)],
                [(1,0),(2,0),(1,1),(2,1)],
                [(1,0),(2,0),(1,1),(2,1)]
            ],
            "T": [
                [(1,0),(0,1),(1,1),(2,1)],
                [(1,0),(1,1),(2,1),(1,2)],
                [(0,1),(1,1),(2,1),(1,2)],
                [(1,0),(0,1),(1,1),(1,2)]
            ],
            "J": [
                [(0,0),(0,1),(1,1),(2,1)],
                [(1,0),(2,0),(1,1),(1,2)],
                [(0,1),(1,1),(2,1),(2,2)],
                [(1,0),(1,1),(0,2),(1,2)]
            ],
            "L": [
                [(2,0),(0,1),(1,1),(2,1)],
                [(1,0),(1,1),(1,2),(2,2)],
                [(0,1),(1,1),(2,1),(0,2)],
                [(0,0),(1,0),(1,1),(1,2)]
            ],
            "S": [
                [(1,0),(2,0),(0,1),(1,1)],
                [(1,0),(1,1),(2,1),(2,2)],
                [(1,1),(2,1),(0,2),(1,2)],
                [(0,0),(0,1),(1,1),(1,2)]
            ],
            "Z": [
                [(0,0),(1,0),(1,1),(2,1)],
                [(2,0),(1,1),(2,1),(1,2)],
                [(0,1),(1,1),(1,2),(2,2)],
                [(1,0),(0,1),(1,1),(0,2)]
            ]
        }

        #_recv queue
        self.q1 = queue.Queue()
        self.q2 = queue.Queue()


    def in_game(self):
        p1_socket, addr1 = self.Game_socket.accept()
        p2_socket, addr2 = self.Game_socket.accept()
        self.p1_socket = p1_socket
        self.p2_socket = p2_socket

        t1 = threading.Thread(target=self._recv_forever, args=(self.p1_socket, self.q1), daemon=True)
        t2 = threading.Thread(target=self._recv_forever, args=(self.p2_socket, self.q2), daemon=True)
        t1.start()
        t2.start()
        
        seed = random.randrange(2**31)

        welcome_p1 = {
            "type":"WELCOME",
            "role":"P1",
            "seed": seed,
            "bagRule":"7bag",
            "gravityPlan": {
                "mode": "fixed",
                "dropMs": 500
            }
        }
        welcome_p2 = {
            "type":"WELCOME",
            "role":"P2",
            "seed": seed,
            "bagRule":"7bag",
            "gravityPlan": {
                "mode": "fixed",
                "dropMs": 500
            }
        }

        _send_json(welcome_p1, p1_socket)
        _send_json(welcome_p2, p2_socket)

        #start game
        bag1 = Bag7(seed)
        bag2 = Bag7(seed)

        p1_state = {
            "userId": self.p1Id,
            "board": [[0]*10 for _ in range(20)],
            "active": {"shape": bag1.next(), "x": 4, "y": 0, "rot": 0},
            "hold": None,
            "next": [bag1.next() for _ in range(3)],
            "score": 0,
            "lines": 0,
            "level": 1,
            "maxCombo" : 0
        }
        p2_state = {
            "userId": self.p2Id,
            "board": [[0]*10 for _ in range(20)],
            "active": {"shape": bag2.next(), "x": 4, "y": 0, "rot": 0},
            "hold": None,
            "next": [bag2.next() for _ in range(3)],
            "score": 0,
            "lines": 0,
            "level": 1,
            "maxCombo" : 0
        }

        initial = {
            "type": "SNAPSHOT",
            "tick": 0,
            "players": [p1_state, p2_state]
        }
        _send_json(initial, self.p1_socket)
        _send_json(initial, self.p2_socket)

        self.p1_state = p1_state
        self.p2_state = p2_state
        self.bag1 = bag1
        self.bag2 = bag2
        self.tick = 0

        self._run_loop()

    def _shape_id(self, s):
        _SHAPE_ORDER = ["I","O","T","J","L","S","Z"]
        return _SHAPE_ORDER.index(s) + 1 if s in _SHAPE_ORDER else 1
    
    def _cells(self, shape, x, y, rot):
        return [(x+dx, y+dy) for (dx,dy) in self.SHAPES[shape][rot % 4]]

    def can_move(self, board, shape, x, y, rot) -> bool:
        for (cx, cy) in self._cells(shape, x, y, rot):
            if cx < 0 or cx >= self.W or cy < 0 or cy >= self.H:
                return False
            if board[cy][cx] != 0:
                return False
        return True

    def try_move(self, state, dx, dy):
        a = state["active"]
        if self.can_move(state["board"], a["shape"], a["x"]+dx, a["y"]+dy, a["rot"]):
            a["x"] += dx; a["y"] += dy
            return True
        return False

    def try_rot(self, state, drot):
        a = state["active"]
        nr = (a["rot"] + drot) % 4
        if self.can_move(state["board"], a["shape"], a["x"], a["y"], nr):
            a["rot"] = nr
            return True
        return False

    def lock_piece(self, state):
        a, board = state["active"], state["board"]
        for (cx, cy) in self._cells(a["shape"], a["x"], a["y"], a["rot"]):
            board[cy][cx] = self._shape_id(a["shape"])

    def clear_lines(self, state):
        board = state["board"]
        kept = [row for row in board if any(c == 0 for c in row)]
        cleared = self.H - len(kept)
        if cleared > 0:
            board[:] = [[0]*self.W for _ in range(cleared)] + kept
            state["lines"] += cleared
            state["score"] += [0,100,300,500,800][min(cleared,4)]
            if(cleared > state["maxCombo"]):
                state["maxCombo"] = cleared
        return cleared

    def spawn_next(self, state, bag):
        shape = state["next"].pop(0)
        state["active"] = {"shape": shape, "x": 4, "y": 0, "rot": 0}
        while len(state["next"]) < 3:
            state["next"].append(bag.next())
        return self.can_move(state["board"], state["active"]["shape"], 4, 0, 0)

    def apply_inputs(self, state, q):
        while not q.empty():
            msg = q.get()
            if msg.get("type") != "INPUT":
                continue
            act = (msg.get("action") or "").upper()
            if act == "LEFT":
                self.try_move(state, -1, 0)
            elif act == "RIGHT":
                self.try_move(state, +1, 0)
            elif act == "SOFT":
                self.try_move(state, 0, +1)
            elif act == "CW":
                self.try_rot(state, +1)
            elif act == "CCW":
                self.try_rot(state, -1)

    def now_ms(self):
        return int(time.monotonic() * 1000)

    def _run_loop(self):
        drop_ms = self.gravityPlan["dropMs"] = 500
        next_drop1 = self.now_ms() + drop_ms
        next_drop2 = self.now_ms() + drop_ms
        next_bcast = self.now_ms() + self.BROADCAST_MS
        self.tick = 0
        lose_flag1 = 0
        lose_flag2 = 0

        while True:
            t0 = self.now_ms()

            #50 check action from client
            self.apply_inputs(self.p1_state, self.q1)
            self.apply_inputs(self.p2_state, self.q2)

            #500 drop down
            if t0 >= next_drop1:
                if not self.try_move(self.p1_state, 0, +1):
                    self.lock_piece(self.p1_state)
                    self.clear_lines(self.p1_state)
                    alive = self.spawn_next(self.p1_state, self.bag1)
                    if not alive: 
                        lose_flag1 = 1
                next_drop1 += drop_ms

            if t0 >= next_drop2:
                if not self.try_move(self.p2_state, 0, +1):
                    self.lock_piece(self.p2_state)
                    self.clear_lines(self.p2_state)
                    alive = self.spawn_next(self.p2_state, self.bag2)
                    if not alive:
                        lose_flag2 = 1
                next_drop2 += drop_ms

            #gameover
            if(lose_flag1 == 1 and lose_flag2 == 1):
                gameover = {
                    "type": "GAMEOVER",
                    "tick": self.tick,
                    "mode": "survival",
                    "matchId": self.matchId,
                    "roomId": self.roomId,
                    "users:[userId]": [self.p1Id, self.p2Id],
                    "startAt": self.starttime,
                    "endAt": datetime.now().isoformat(),
                    "results": [
                        {"userId": self.p1Id, "score": self.p1_state["score"], "lines": self.p1_state["lines"], "maxCombo" : self.p1_state["maxCombo"], "alive": False},
                        {"userId": self.p2Id, "score": self.p2_state["score"], "lines": self.p2_state["lines"], "maxCombo" : self.p2_state["maxCombo"], "alive": False},
                    ],
                    "winnerUserId": None,
                    "draw": True
                }
                _send_json(gameover, self.p1_socket)
                _send_json(gameover, self.p2_socket)
                _send_json(gameover, self.Lobby_socket)
                break
            elif(lose_flag1 == 1):
                gameover = {
                    "type": "GAMEOVER",
                    "tick": self.tick,
                    "mode": "survival",
                    "matchId": self.matchId,
                    "roomId": self.roomId,
                    "users:[userId]": [self.p1Id, self.p2Id],
                    "startAt": self.starttime,
                    "endAt": datetime.now().isoformat(),
                    "results": [
                        {"userId": self.p1Id, "score": self.p1_state["score"], "lines": self.p1_state["lines"], "maxCombo" : self.p1_state["maxCombo"], "alive": False},
                        {"userId": self.p2Id, "score": self.p2_state["score"], "lines": self.p2_state["lines"], "maxCombo" : self.p2_state["maxCombo"], "alive": True},
                    ],
                    "winnerUserId": self.p2Id,
                    "draw": False
                }
                _send_json(gameover, self.p1_socket)
                _send_json(gameover, self.p2_socket)
                _send_json(gameover, self.Lobby_socket)
                break
            elif(lose_flag2 == 1):
                gameover = {
                    "type": "GAMEOVER",
                    "tick": self.tick,
                    "mode": "survival",
                    "matchId": self.matchId,
                    "roomId": self.roomId,
                    "users:[userId]": [self.p1Id, self.p2Id],
                    "startAt": self.starttime,
                    "endAt": datetime.now().isoformat(),
                    "results": [
                        {"userId": self.p1Id, "score": self.p1_state["score"], "lines": self.p1_state["lines"], "maxCombo" : self.p1_state["maxCombo"], "alive": True},
                        {"userId": self.p2Id, "score": self.p2_state["score"], "lines": self.p2_state["lines"], "maxCombo" : self.p2_state["maxCombo"],"alive": False},
                    ],
                    "winnerUserId": self.p1Id,
                    "draw": False
                }
                _send_json(gameover, self.p1_socket)
                _send_json(gameover, self.p2_socket)
                _send_json(gameover, self.Lobby_socket)
                break

            #200 broadcast snapshot
            if t0 >= next_bcast:
                snap = {
                    "type": "SNAPSHOT",
                    "tick": self.tick,
                    "players": [self.p1_state, self.p2_state]
                }
                _send_json(snap, self.p1_socket)
                _send_json(snap, self.p2_socket)
                next_bcast += self.BROADCAST_MS

            self.tick += 1
            spent = self.now_ms() - t0
            delay = self.TICK_MS - spent
            if delay > 0:
                time.sleep(delay / 1000.0) #ms


    def _recv_forever(self, socket, q):
        try:
            while(1):
                msg = _recv_json(socket)
                if msg.get("type") == "INPUT":
                    q.put(msg)
        except ConnectionResetError:
            pass
        finally:
            socket.close()
        

class Bag7:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.pool = []

    def _refill(self):
        self.pool = ["I","O","T","J","L","S","Z"]
        # Fisher–Yates shuffle
        for i in range(len(self.pool)-1, 0, -1):
            j = self.rng.randrange(i+1)
            self.pool[i], self.pool[j] = self.pool[j], self.pool[i]

    def next(self):
        if not self.pool:
            self._refill()
        return self.pool.pop()

        
def _send(msg, socket):
    data = msg.encode("utf-8")
    if(len(data) <= 0 or len(data) > 65536):
        socket.close()
        return
    header = struct.pack(">I", len(data))
    socket.sendall(header + data)

def _recv_len(socket, n):
    data = b''
    while(len(data) < n):
        data += socket.recv(n - len(data))
    return data

def _recv(socket):
    length = _recv_len(socket, 4)
    length = struct.unpack('>I', length)[0]
    if(length <= 0 or length > 65536):
        socket.close()
        return
    return _recv_len(socket, length).decode()

#json
def _send_json(msg, socket):
    data = json.dumps(msg).encode("utf-8")
    if(len(data) <= 0 or len(data) > 65536):
        socket.close()
        return
    header = struct.pack(">I", len(data))
    try:  
        socket.sendall(header+data)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass

def _recv_json_len(socket, n):
    data = b''
    while(len(data) < n):
        try:
            temp = socket.recv(n - len(data))
            if not temp:
                raise ConnectionResetError
            data += temp
        except ConnectionResetError:
            raise ConnectionResetError
    return data

def _recv_json(socket):
    try:
        length = _recv_json_len(socket, 4)
        length = struct.unpack('>I', length)[0]
        if(length <= 0 or length > 65536):
            socket.close()
            return
    except ConnectionResetError:
        raise ConnectionResetError
    return json.loads(_recv_json_len(socket, length).decode())


if (__name__ == "__main__"):
    for GameServer_Port in range(12000, 12021):
        try:
            game_server = GameServer(GameServer_Port, int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5]))
            print(f"Game server is bound on {GameServer_Port}\n")
            _send_json({
                "host" : "127.0.0.1",
                "port" : int(GameServer_Port)
            }, game_server.Lobby_socket)
            game_server.in_game()
            break
        except OSError:
            print(f"The port {GameServer_Port} is already used by another socket\n")
    
    
    
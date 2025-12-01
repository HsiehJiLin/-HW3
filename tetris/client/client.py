import socket, struct, json, threading, queue, subprocess, time, os, sys
import pygame
from collections import deque


#GUI
W, H = 10, 20   #board size
CELL_MAIN  = 28 #28*28 pixel
CELL_OPPO  = 16 #16*16 pixel
MARGIN     = 24 #24 pixel up down left right margin
GAP        = 40 #40 pixel gap between two boards

SHAPE_COLOR_ID = {
    "I": 1, "O": 2, "T": 3, "S": 4, "Z": 5, "J": 6, "L": 7,
}

SHAPES = {
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

COLOR = {
    0: (28, 28, 28),   # empty
    1: (0, 255, 255),  # I
    2: (255, 255, 0),  # O
    3: (160, 32, 240), # T
    4: (0, 200, 0),    # S
    5: (220, 0, 0),    # Z
    6: (0, 0, 200),    # J
    7: (255, 140, 0),  # L
}

GRID = (50, 50, 50)

RENDER_DELAY_MS = 150
TICK_MS = 50
DELAY_TICKS = int(RENDER_DELAY_MS / TICK_MS)


class Client:
    def __init__(self, user_id):
        self.user_id = user_id
        self.seq = 0
        self.game_over = False
        self.snap_buf = deque(maxlen=60)
        self.max_tick = 0


    def in_game(self, data):
        self.game_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.game_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        #build SSH tunnel
        '''linuxuser = data["linuxuser"]
        subprocess.Popen([
            "ssh", "-N",
            "-L", f"{data['port']}:{data['host']}:{data['port']}",
            f"{linuxuser}@linux1.cs.nycu.edu.tw"
        ])
        time.sleep(5)'''
        self.game_socket.connect(("linux1.cs.nycu.edu.tw", data["port"]))
        self.game_q = queue.Queue()
        game_t = threading.Thread(target = self._recv_game_server_forever, daemon = True)
        game_t.start()

        #welcome
        welcome = self.game_q.get()
        if welcome["type"] != "WELCOME":
            print("Unexpected message:", welcome)
            return

        self.game = {
            "role": welcome["role"],
            "seed": welcome["seed"],
            "bagRule": welcome["bagRule"],
            "gravityPlan": welcome["gravityPlan"]
        }
        print(welcome)

        #snap
        snap = self.game_q.get() #get initial
        role = self.game["role"] 
                
        #GUI
        pygame.init()
        width  = MARGIN + W*CELL_MAIN + GAP + W*CELL_OPPO + MARGIN
        height = MARGIN + H*CELL_MAIN + MARGIN
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Two-Player Tetris")
        clock  = pygame.time.Clock()
        font   = pygame.font.SysFont(None, 24)
        
        start_time = pygame.time.get_ticks()
        render_tick = 0
        running = True
        while running:
            now = pygame.time.get_ticks()
            expected_tick = (now - start_time) // TICK_MS
            expected_tick = max(0, expected_tick - DELAY_TICKS)
            expected_tick = min(expected_tick, self.max_tick)

            if expected_tick > render_tick:
                render_tick = expected_tick

            for e in pygame.event.get():
                if e.type == pygame.QUIT: running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_LEFT:  self.send_input("LEFT")
                    if e.key == pygame.K_RIGHT: self.send_input("RIGHT")
                    if e.key == pygame.K_UP:    self.send_input("CW")
                    if e.key == pygame.K_DOWN:  self.send_input("SOFT")
                    if e.key == pygame.K_ESCAPE: running = False

            s = self.pick_snapshot_by_tick(render_tick)
            if s is None:
                clock.tick(60)
                continue
            elif s["type"] == "SNAPSHOT":
                screen.fill((20,20,20))
                p1, p2 = s["players"][0], s["players"][1]
                me, op = (p1, p2) if role == "P1" else (p2, p1)

                lx, ly = MARGIN, MARGIN
                draw_board(screen, me["board"], CELL_MAIN, lx, ly)
                draw_active(screen, me["active"], CELL_MAIN, lx, ly)

                rx, ry = MARGIN + W*CELL_MAIN + GAP, MARGIN
                draw_board(screen, op["board"], CELL_OPPO, rx, ry)
                draw_active(screen, op["active"], CELL_OPPO, rx, ry)

                elapsed = int(pygame.time.get_ticks() / 1000)
                me_lines  = me.get("lines", 0)
                opp_lines = op.get("lines", 0)
                info_text = f"role={role}  time={elapsed}s  me lines={me_lines}  opp lines={opp_lines}"
                info_surface = font.render(info_text, True, (255, 255, 255))
                text_rect = info_surface.get_rect(center=(width//2, 15))
                screen.blit(info_surface, text_rect)

                '''screen.blit(font.render("YOU", True, (230,230,230)), (lx, ly-22))
                screen.blit(font.render("OPPONENT", True, (230,230,230)), (rx, ry-22))'''

            elif s["type"] == "GAMEOVER":
                screen.fill((20,20,20))
                text = font.render("GAME OVER", True, (240,240,240))
                screen.blit(text, (width//2 - 60, 20))
                pygame.display.flip()

                waiting = True
                while waiting:
                    for e in pygame.event.get():
                        if e.type == pygame.QUIT: 
                            waiting = False
                            running = False
                        elif e.type == pygame.KEYDOWN:
                            waiting = False
                            running = False
                    clock.tick(30) #30FPS

            pygame.display.flip()
            clock.tick(60)  # 60FPS

        pygame.quit()
        self.game_socket.close()
        self.game_over = False
        self.snap_buf.clear()
        self.max_tick = 0
        
                
    def send_input(self, action):
        pkt = {
            "type": "INPUT",
            "userId": self.user_id,
            "seq": self.seq,
            "action": action.upper()
        }
        self.seq += 1
        try:
            _send_json(pkt, self.game_socket)
        except OSError:
            pass

    def _recv_game_server_forever(self):
        try:
            while(1):
                m = _recv_json(self.game_socket)
                if m["type"] == "SNAPSHOT":
                    self.snap_buf.append(m)
                    self.max_tick = m["tick"]
                    if m["tick"] == 0:
                        self.game_q.put(m)
                elif m["type"] == "GAMEOVER":
                    self.game_over = True
                    self.snap_buf.append(m)
                    self.game_q.put(m)
                    break
                else:
                    self.game_q.put(m)
        except (ConnectionResetError, OSError):
            pass
        finally:
            self.game_socket.close()   

    def pick_snapshot_by_tick(self, tick):
        if not self.snap_buf:
            return None
        
        tail = self.snap_buf[-1]
        if tail["type"] == "GAMEOVER":
            return tail
          
        for s in reversed(self.snap_buf):
            if s["type"] == "SNAPSHOT" and s["tick"] <= tick:
                return s

        return self.snap_buf[0] if len(self.snap_buf) > 0 else None 

#GUI
def draw_board(surface, board, cell, origin_x, origin_y):

    for y in range(H):
        for x in range(W):
            rx = origin_x + x * cell
            ry = origin_y + y * cell
            pygame.draw.rect(surface, GRID, (rx, ry, cell, cell), width=1)

    for y in range(H):
        for x in range(W):
            v = board[y][x]
            if v != 0:
                rx = origin_x + x * cell
                ry = origin_y + y * cell
                pygame.draw.rect(surface, COLOR.get(v, (200,200,200)), (rx+1, ry+1, cell-2, cell-2))

def _active_cells(active):
    if not active:
        return []
    shape = active["shape"]
    x, y, rot = active["x"], active["y"], active["rot"] % 4
    offs = SHAPES[shape][rot] #offsets
    return [(x + dx, y + dy) for (dx, dy) in offs]

def draw_active(surface, active, cell, origin_x, origin_y):
    if not active:
        return
    color_id = SHAPE_COLOR_ID[active["shape"]]
    color = COLOR[color_id]
    for (cx, cy) in _active_cells(active):
        if 0 <= cx < W and 0 <= cy < H:
            rx = origin_x + cx * cell
            ry = origin_y + cy * cell
            pygame.draw.rect(surface, color, (rx+1, ry+1, cell-2, cell-2))


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
    except OSError:
        raise OSError

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


if __name__ == "__main__":
    host = sys.argv[1]
    port = int(sys.argv[2])
    user_id = int(sys.argv[3])
    linuxuser = sys.argv[4]

    data = {
        "host": host,
        "port": port,
        "linuxuser": linuxuser
    }

    c = Client(user_id)
    c.in_game(data)
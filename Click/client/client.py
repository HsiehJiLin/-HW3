# client/client.py
import socket
import json
import struct
import sys
import pygame
import random
import time
import subprocess

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

def run_game():
    pygame.init()
    W, H = 800, 600
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Multi-Player Click Challenge")
    font = pygame.font.SysFont(None, 36)
    big_font = pygame.font.SysFont(None, 64)
    clock = pygame.time.Clock()

    TIME_LIMIT = 20.0  # 秒
    start_time = time.time()

    radius = 30
    target_x = random.randint(radius, W - radius)
    target_y = random.randint(radius, H - radius)

    score = 0
    current_combo = 0
    max_combo = 0
    lines = 0  # 隨便定一個指標，這裡用 score // 30 代表「達成幾次 milestone」

    running = True
    game_over = False

    while running:
        dt = clock.tick(60) / 1000.0
        now = time.time()
        elapsed = now - start_time
        remaining = max(0.0, TIME_LIMIT - elapsed)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not game_over:
                mx, my = event.pos
                dx = mx - target_x
                dy = my - target_y
                if dx * dx + dy * dy <= radius * radius:
                    # 點中目標
                    score += 10
                    current_combo += 1
                    if current_combo > max_combo:
                        max_combo = current_combo
                    lines = score // 30
                    # spawn 新目標
                    target_x = random.randint(radius, W - radius)
                    target_y = random.randint(radius, H - radius)
                else:
                    # miss → combo 歸零
                    current_combo = 0

        if remaining <= 0 and not game_over:
            game_over = True
            game_over_time = time.time()

        # 畫面
        screen.fill((30, 30, 30))

        if not game_over:
            # 畫目標
            pygame.draw.circle(screen, (200, 50, 50), (target_x, target_y), radius)

            # UI 文字
            text_score = font.render(f"Score: {score}", True, (255, 255, 255))
            text_time = font.render(f"Time: {remaining:4.1f}s", True, (255, 255, 255))
            text_combo = font.render(f"Combo: {current_combo} (Max {max_combo})", True, (255, 255, 255))
            text_hint = font.render("Click the red circle as fast as you can!", True, (180, 180, 180))

            screen.blit(text_score, (20, 20))
            screen.blit(text_time, (20, 60))
            screen.blit(text_combo, (20, 100))
            screen.blit(text_hint, (20, 140))
        else:
            # Game Over 畫面
            text_go = big_font.render("TIME UP!", True, (255, 255, 0))
            text_score = font.render(f"Final Score: {score}", True, (255, 255, 255))
            text_combo = font.render(f"Best Combo: {max_combo}", True, (255, 255, 255))
            text_info = font.render("Window will close automatically...", True, (180, 180, 180))

            screen.blit(text_go, (W // 2 - text_go.get_width() // 2, H // 2 - 120))
            screen.blit(text_score, (W // 2 - text_score.get_width() // 2, H // 2 - 40))
            screen.blit(text_combo, (W // 2 - text_combo.get_width() // 2, H // 2 + 10))
            screen.blit(text_info, (W // 2 - text_info.get_width() // 2, H // 2 + 60))

            # 停留一下再自動關閉
            if time.time() - game_over_time > 2.0:
                running = False

        pygame.display.flip()

    pygame.quit()
    return score, lines, max_combo

def main():
    if len(sys.argv) < 5:
        print("Usage: client.py host port userId")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    user_id = int(sys.argv[3])

    # 連到遊戲 server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("linux1.cs.nycu.edu.tw", port))

    # 先送 join
    send_json(sock, {
        "type": "join",
        "userId": user_id
    })

    # 本地跑遊戲
    score, lines, max_combo = run_game()

    # 遊戲結束，送結果
    finish_msg = {
        "type": "finish",
        "userId": user_id,
        "score": score,
        "lines": lines,
        "maxCombo": max_combo
    }
    send_json(sock, finish_msg)

    # 不特別等 server 的回覆，直接關閉也可以
    sock.close()

if __name__ == "__main__":
    main()

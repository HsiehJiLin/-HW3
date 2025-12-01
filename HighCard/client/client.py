import sys
import subprocess
import shutil
import os

def main():
    if len(sys.argv) < 4:
        print("Usage: run_client.py <host> <port> <userId>")
        return

    host      = sys.argv[1]
    port      = sys.argv[2]
    userId    = sys.argv[3]

    py = sys.executable
    game_dir = os.path.dirname(os.path.abspath(__file__))

    base_cmd = [py, "highcard_client.py", host, port, userId]

    plat = sys.platform
    cmd = None

    # Linux
    if plat.startswith("linux"):
        term = None
        for cand in ("x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal"):
            if shutil.which(cand):
                term = cand
                break

        if term is None:
            cmd = base_cmd
        else:
            if term in ("gnome-terminal", "xfce4-terminal"):
                cmd = [term, "--"] + base_cmd
            else:
                cmd = [term, "-e"] + base_cmd

    # Windows
    elif plat == "win32":
        cmd = ["cmd", "/c", "start", "", py, "highcard_client.py",
               host, port, userId]

    # macOS
    elif plat == "darwin":
        inner = f'{py} highcard_client.py {host} {port} {userId}'
        cmd = ["osascript", "-e",
               f'tell app "Terminal" to do script "{inner}"']

    else:
        cmd = base_cmd

    print("[run_client] launching:", cmd)
    subprocess.Popen(cmd, cwd=game_dir)

if __name__ == "__main__":
    main()

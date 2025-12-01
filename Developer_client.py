import socket, struct, json, threading, queue, subprocess, time, os
from collections import deque
import shutil

SERVER_HOST = "linux1.cs.nycu.edu.tw"
SERVER_PORT = 24680
CONFIG_USER_FILE = "config_linuxuser.json"

class Client:
    def __init__(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #allow repeated binding
        try:
            self.client_socket.connect((SERVER_HOST, SERVER_PORT))
        except ConnectionRefusedError:
            print("Error: Cannot connect to server. Please ensure the server is running.")
            raise SystemExit(1)

        #recv data
        self.q = queue.Queue()
        t = threading.Thread(target = self._recv_forever, daemon = True)
        t.start()

        #user info
        self.if_login = 0
        self.User = {}
        
    def serve_forever(self):
        try:
            while True:
                if self.if_login == 0:
                    self._login_menu()
                elif self.if_login == 1:
                    self._main_menu()
        except KeyboardInterrupt:
            self._cleanup()
        finally:
            self.client_socket.close()

    def _login_menu(self):
        print("\n=== Developer Login Menu ===")
        print("1. register")
        print("2. login")
        print("3. exit")
        print("============================\n")

        command = input("Select option: ").strip()
        if not command:
            print("Invalid input\n")
            return
        if " " in command:
            print("Invalid command\n")
            return

        if command == "1":
            name = input("Enter name: ").strip()
            if not name:
                print("Name cannot be empty\n")
                return
            if " " in name:
                print("Invalid name (no spaces allowed)\n")
                return
            email = input("Enter email: ").strip()
            if not email:
                print("Email cannot be empty\n")
                return
            if " " in email:
                print("Invalid email (no spaces allowed)\n")
                return
            password = input("Enter password: ").strip()
            if not password:
                print("Password cannot be empty\n")
                return
            if " " in password:
                print("Invalid password (no spaces allowed)\n")
                return
            
            _send(f"register {name} {email} {password}", self.client_socket)
            data = self.q.get()
            print(data)
            
        elif command == "2":
            name = input("Enter name: ").strip()
            if not name:
                print("Name cannot be empty\n")
                return
            if " " in name:
                print("Invalid name (no spaces allowed)\n")
                return
            password = input("Enter password: ").strip()
            if not password:
                print("Password cannot be empty\n")
                return
            if " " in password:
                print("Invalid password (no spaces allowed)\n")
                return
            
            _send(f"login {name} {password}", self.client_socket)
            data = self.q.get()
            print(data)
            if data == "Login successful":
                data = self.q.get()
                self.User = data
                self.if_login = 1
                
        elif command == "3":
            raise KeyboardInterrupt
        else:
            print("Invalid command\n")

    def _main_menu(self):
        print("\n=== Developer Main Menu ===")
        print("1. List my games")
        print("2. Upload game")
        print("3. Unlist game")
        print("4. Update game")
        print("5. Logout")
        print("===========================\n")

        command = input("Select option: ").strip()
        if not command:
            print("Invalid input\n")
            return
        if " " in command:
            print("Invalid command\n")
            return

        if command == "1":
            authorId = self.User["id"]
            _send("LISTMYGAMES" + " " + f"{authorId}", self.client_socket)

            data = self.q.get()
            print(data)
            if(data == "List my games successful"):
                data = self.q.get()
                print("=== My Games ===")
                for key in data:
                    game = data[key]["game"]
                    versions = data[key]["versions"]
                    latest_vid = data[key]["latestVersionId"]

                    print(f"\nGame ID: {game['id']}")
                    print(f"  Name       : {game['name']}")
                    print(f"  Type       : {game['type']}")
                    print(f"  Max players: {game['maxPlayers']}")
                    print(f"  Status     : {game['status']}")
                    print(f"  LatestVersionId: {latest_vid}")

                    print("  Versions   :")
                    for key in versions:
                        print(f"    - id={versions[key]['id']}, "
                                f"version={versions[key]['version']}, "
                                f"createdAt={versions[key]['createdAt']}, "
                                f"path={versions[key]['pathOnServer']}")
                print()
        elif command == "2":
            game_name = input("Enter game name: ").strip()
            if not game_name:
                print("Game name cannot be empty\n")
                return
            if " " in game_name:
                print("Invalid game name (no spaces allowed)\n")
                return
                
            print("\nSelect game type")
            print("1. CLI")
            print("2. GUI\n")
            type_choice = input("Select option: ").strip()
            if not type_choice:
                print("Game type cannot be empty\n")
                return
            if " " in type_choice:
                print("Invalid input (no spaces allowed)\n")
                return
            if type_choice == "1":
                game_type = "CLI"
            elif type_choice == "2":
                game_type = "GUI"
            else:
                print("Invalid game type\n")
                return
                
            max_players = input("Enter max players: ").strip()
            if not max_players:
                print("Max players cannot be empty\n")
                return
            if " " in max_players:
                print("Invalid input (no spaces allowed)\n")
                return
            if not max_players.isdigit():
                print("Max players must be a number\n")
                return
                
            game_folder = input("Enter the path of the game folder: ").strip()
            if not game_folder:
                print("Game folder path cannot be empty\n")
                return
            if not os.path.isdir(game_folder):
                print(f"Cannot find folder: {game_folder}\n")
                return
            
            dev_name = self.User["name"]
            output_dir = os.path.join("game_packages", dev_name)
            os.makedirs(output_dir, exist_ok=True) #make directories

            base_name = f"{game_name}_v1"
            zip_base_path = os.path.join(output_dir, base_name)

            #archive as .zip
            try:
                shutil.make_archive(zip_base_path, "zip", root_dir=game_folder)
                zip_path = zip_base_path + ".zip"
                print(f"compress the game as : {zip_path}")
            except Exception as e:
                print(f"compression fail: {e}")
                return

            #get file size
            file_size = os.path.getsize(zip_path)
            _send("UPLOADGAME" + " " + dev_name + " " + game_name + " " + game_type + " " + max_players + " " + str(file_size), self.client_socket)

            # send .zip
            try:
                with open(zip_path, "rb") as f:
                    remaining = file_size
                    while remaining > 0:
                        chunk = f.read(min(4096, remaining))
                        if not chunk:
                            break
                        self.client_socket.sendall(chunk)
                        remaining -= len(chunk)
                print("upload completed")
            except OSError as e:
                print(f"upload fail: {e}")
                return

            data = self.q.get()
            print(data)
            if data == "Upload game successful":
                data = self.q.get()
                print("New game created:")
                print(data)
        elif command == "3":
            game_id = input("Enter game ID to unlist: ").strip()
            if not game_id:
                print("Game ID cannot be empty\n")
                return
            if " " in game_id:
                print("Invalid game ID (no spaces allowed)\n")
                return
            if not game_id.isdigit():
                print("Game ID must be a number\n")
                return

            dev_name = self.User["name"]   

            _send(f"UNLISTGAME {game_id} {dev_name}", self.client_socket)
            data = self.q.get()
            print(data)
        elif command == "4":
            game_id = input("Enter game ID to update: ").strip()
            if not game_id:
                print("Game ID cannot be empty\n")
                return
            if " " in game_id:
                print("Invalid game ID (no spaces allowed)\n")
                return
            if not game_id.isdigit():
                print("Game ID must be a number\n")
                return
                
            version = input("Enter new version: ").strip()
            if not version:
                print("Version cannot be empty\n")
                return
            if " " in version:
                print("Invalid version (no spaces allowed)\n")
                return
                
            game_folder = input("Enter the path of the updated game folder: ").strip()
            if not game_folder:
                print("Game folder path cannot be empty\n")
                return
            if not os.path.isdir(game_folder):
                print(f"Cannot find folder: {game_folder}\n")
                return

            dev_name = self.User["name"]

            output_dir = os.path.join("game_packages", dev_name)
            os.makedirs(output_dir, exist_ok=True)

            base_name = f"game_{game_id}_v{version}"
            zip_base_path = os.path.join(output_dir, base_name)

            #archive as .zip
            try:
                shutil.make_archive(zip_base_path, "zip", root_dir=game_folder)
                zip_path = zip_base_path + ".zip"
                print(f"Compressed updated game as: {zip_path}")
            except Exception as e:
                print(f"Compression failed: {e}")
                return
            
            file_size = os.path.getsize(zip_path)

            dev_name = self.User["name"]
            _send(f"UPDATEGAME {dev_name} {game_id} {version} {file_size}", self.client_socket)

            try:
                with open(zip_path, "rb") as f:
                    remaining = file_size
                    while remaining > 0:
                        chunk = f.read(min(4096, remaining))
                        if not chunk:
                            break
                        self.client_socket.sendall(chunk)
                        remaining -= len(chunk)
                print("Upload updated game completed")
            except OSError as e:
                print(f"Upload updated game failed: {e}")
                return

            data = self.q.get()
            print(data)
            if data == "Update game successful":
                data = self.q.get()
                print("Updated game info:")
                print(data)
        elif command == "5":
            _send(f"logout {self.User['name']}", self.client_socket)
            data = self.q.get()
            print(data)
            self.if_login = 0
            self.User.clear()
        else:
            print("Invalid command\n")

    def _cleanup(self):
        if self.if_login == 1:
            _send(f"logout {self.User['name']}", self.client_socket)
            try:
                data = self.q.get()
                print(data)
            except:
                pass
            self.if_login = 0
        self.User.clear()


    def _recv_forever(self):
        try:
            while(1):
                data = _recv_json(self.client_socket)
                self.q.put(data)
        except (ConnectionResetError, OSError):
            pass
        finally:
            self.client_socket.close()
            

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


if (__name__ == "__main__"):
    '''try:
        with open(CONFIG_USER_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            linuxuser = cfg["linuxuser"]
            subprocess.Popen([
            "ssh", "-N",
            "-L", f"{SERVER_PORT}:{SERVER_HOST}:{SERVER_PORT}",
            f"{linuxuser}@linux1.cs.nycu.edu.tw"
            ])
            time.sleep(5)
    except FileNotFoundError:
        print("Error: config_linuxuser.json not found. Please create it in the project root.")
        raise SystemExit(1)
    except KeyError:
        print("Error: 'linuxuser' field missing in config_linuxuser.json.")
        raise SystemExit(1)'''
    
    client = Client()
    client.serve_forever()
    

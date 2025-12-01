import socket, struct, json, threading, queue, subprocess, time, os, sys
import zipfile
from pathlib import Path


SERVER_HOST = "linux1.cs.nycu.edu.tw"
SERVER_PORT = 13579

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
        self.if_in_room = 0
        self.User = {}
        self.Room = {}   

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
        print("\n=== Login Menu ===")
        print("1. register")
        print("2. login")
        print("3. exit")
        print("=====================\n")

        command = input("Select option: ").strip()
        if not command:
            print("Invalid input\n")
            return
        if " " in command:
            print("Invalid command\n")
            return
    
        if(command == "1"):
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
        elif(command == "2"):
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
            if(data == "Login successful"):
                data = self.q.get()
                self.User = data
                self.if_login = 1
        elif(command == "3"):
            raise KeyboardInterrupt #exit program
        else:
            print("Invalid command\n")

    def _main_menu(self):
        print("\n=== Main Menu ===")
        print("1. Lobby (room & list)")
        print("2. Lobby (invite & game)")
        print("3. Game Store")
        print("4. Logout")
        print("=================\n")
        
        command = input("Select option: ").strip()
        
        if not command:
            print("Invalid input\n")
            return
        if " " in command:
            print("Invalid command\n")
            return
        
        if command == "1":
            self._lobby_menu1()
        elif command == "2":
            self._lobby_menu2()
        elif command == "3":
            self._game_store_menu()
        elif command == "4":
            _send("logout " + self.User["name"], self.client_socket)
            data = self.q.get()
            print(data)
            self.if_login = 0
            
            if self.if_in_room == 1:
                _send(f"leaveroom {self.Room['id']} {self.User['id']}", self.client_socket)
                data = self.q.get()
                print(data)
                self.if_in_room = 0
                self.Room.clear()
            
            self.User.clear()
        else:
            print("Invalid command\n")

    def _lobby_menu1(self):
        while(True):
            print("\n=== Lobby Menu 1 (Room & List) ===")
            print("1. createroom")
            print("2. joinroom")
            print("3. onlinelist")
            print("4. roomlist")
            print("5. leaveroom")
            print("6. Back")
            print("===========================\n")
            command = input("Select option: ").strip()
            if not command:
                print("Invalid input\n")
                continue
            if " " in command:
                print("Invalid command\n")
                continue

            if(command == "1"):
                if(self.if_in_room == 1):
                    print("You are already in a room\n")
                    continue
                roomname = input("Enter room name: ").strip()
                if not roomname:
                    print("Room name cannot be empty\n")
                    continue
                if " " in roomname:
                    print("Invalid roomname (no spaces allowed)\n")
                    continue
                print("\nEnter visibility")
                print("1. public")
                print("2. private\n")
                visibility = input("Select option: ").strip().lower()
                if not visibility:
                    print("Visibility cannot be empty\n")
                    continue
                if visibility == "1":
                    visibility = "public"
                elif visibility == "2":
                    visibility = "private"
                else:
                    print("Invalid input\n")
                    continue
                if " " in visibility:
                    print("Invalid visibility (no spaces allowed)\n")
                    continue

                gameid = input("Enter game ID to bind this room: ").strip()
                if not gameid or not gameid.isdigit():
                    print("Invalid game ID\n")
                    continue

                user_name = self.User["name"]
                _send(f"createroom {roomname} {visibility} {user_name} {gameid}", self.client_socket)
                data = self.q.get()
                print(data)
                if(data == "Create successful"):
                    data = self.q.get()
                    self.Room = data
                    self.if_in_room = 1
            elif(command == "2"):
                if(self.if_in_room == 1):
                    print("You are already in a room\n")
                    continue
                roomid = input("Enter room ID: ").strip()
                if not roomid:
                    print("Room ID cannot be empty\n")
                    continue
                if not roomid.isdigit():
                    print("Invalid room ID. Must be a number\n")
                    continue
                if " " in roomid:
                    print("Invalid room ID (no spaces allowed)\n")
                    continue

                user_id = self.User["id"]
                _send(f"joinroom {roomid} {user_id}", self.client_socket)
                data = self.q.get()
                print(data)
                if(data == "Join successful"):
                    data = self.q.get()
                    self.Room = data
                    self.if_in_room = 1
            elif(command == "3"):
                _send("onlinelist", self.client_socket)
                data = self.q.get()
                print(data)
            elif(command == "4"):
                _send("roomlist", self.client_socket)
                data = self.q.get()
                print(data)
            elif(command == "5"):
                if(self.if_in_room == 0):
                    print("You are not in a room\n")
                    continue
                room_id = self.Room["id"]
                user_id = self.User["id"]
                _send(f"leaveroom {room_id} {user_id}", self.client_socket)
                data = self.q.get()
                print(data)
                self.if_in_room = 0
                self.Room.clear()
            elif command == "6":
                break
            else:
                print("Invalid command\n")

    def _lobby_menu2(self):
        while True:
            print("\n=== Lobby Menu 2 (Invite & Game) ===")
            print("1. invite")
            print("2. invitation")
            print("3. gamestart")
            print("4. gamelog")
            print("5. Back")
            print("====================================\n")

            command = input("Select option: ").strip()
            if not command:
                print("Invalid input\n")
                continue
            if " " in command:
                print("Invalid command\n")
                continue

            if(command == "1"):
                if(self.if_in_room == 0):
                    print("You are not in a room\n")
                    continue
                playerid = input("Enter player ID to invite: ").strip()
                if not playerid:
                    print("Player ID cannot be empty\n")
                    continue
                if not playerid.isdigit():
                    print("Invalid player ID. Must be a number\n")
                    continue
                if " " in playerid:
                    print("Invalid player ID (no spaces allowed)\n")
                    continue

                room_id = self.Room["id"]
                _send(f"invite {playerid} {room_id}", self.client_socket)
                data = self.q.get()
                print(data)
            elif(command == "2"):
                user_id = self.User["id"]
                _send(f"invitation {user_id}", self.client_socket)
                data = self.q.get()
                print(data)
            elif(command == "3"):
                if(self.if_in_room == 0):
                    print("You are not in a room\n")
                    continue
                room_id = self.Room["id"]
                _send(f"gamestart {room_id}", self.client_socket)
                data = self.q.get()
                print(data)
            elif(command == "4"):
                user_id = self.User["id"]
                _send(f"showgamelog {user_id}", self.client_socket)
                data = self.q.get()
                print(data)
                data = self.q.get()
                print(data)
            elif command == "5":
                break
            else:
                print("Invalid command\n")

    def _game_store_menu(self):
        while(True):
            print("\n=== Game Store Menu ===")
            print("1. gamelist")
            print("2. gameinfo")
            print("3. download game")
            print("4. review game")
            print("5. back")
            print("=====================\n")
            command = input("Select option: ").strip()
            if not command:
                print("Invalid input\n")
                continue
            if " " in command:
                print("Invalid command\n")
                continue
            
            if(command == "1"):
                _send("gamelist", self.client_socket)
                data = self.q.get()
                print(data)
                if(data == "Gamelist successful"):
                    data = self.q.get()
                    print(data)
            elif(command == "2"):
                gameid = input("Enter game ID: ").strip()
                if not gameid:
                    print("Game ID cannot be empty\n")
                    continue
                if not gameid.isdigit():
                    print("Invalid game ID. Must be a number\n")
                    continue
                if " " in gameid:
                    print("Invalid game ID (no spaces allowed)\n")
                    continue

                _send(f"gameinfo {gameid}", self.client_socket)
                data = self.q.get()
                print(data)
                if(data == "Game info successful"):
                    data = self.q.get()
                    print(data)
            elif(command == "3"):
                gameid = input("Enter game ID: ").strip()
                if not gameid:
                    print("Game ID cannot be empty\n")
                    continue
                if not gameid.isdigit():
                    print("Invalid game ID. Must be a number\n")
                    continue
                if " " in gameid:
                    print("Invalid game ID (no spaces allowed)\n")
                    continue

                #check latest game version
                _send(f"gameinfo {gameid}", self.client_socket)
                data = self.q.get()
                if(data == "Game info successful"):
                    info= self.q.get()
                else:
                    continue
                    
                game = info["game"]
                latestVersionId = game["latestVersionId"]
                versions = info["versions"]

                if latestVersionId is None:
                    print("This game has no version, cannot download\n")
                    continue

                latest_version = None
                for key, v in versions.items():
                    if key == "nextID":
                        continue
                    if v["id"] == latestVersionId:
                        latest_version = v["version"]
                        break

                if latest_version is None:
                    print("Cannot find latest version info\n")
                    continue

                #check user's version
                player_name = self.User["name"]
                installed_games_path = os.path.join("downloads", player_name, "installed_games.json")
                try:
                    with open(installed_games_path, "r", encoding="utf-8") as f:
                        installed = json.load(f)
                except FileNotFoundError:
                    installed = {}

                local_version = installed.get(str(gameid))

                #compare version
                if local_version is not None and local_version["version"] == latest_version:
                    print("You already downloaded the latest version")
                    print("Do you want to download again?(Y/N)")
                    ans = input().strip().upper()
                    if ans != "Y":
                        print("Cancel download\n")
                        continue
                else:
                    if local_version is not None:
                        print(f"Current version: {local_version['version']}")
                        print(f"latestversion: {latest_version}")
                        print("Do you want to download latest version?(Y/N)")
                        ans = input().strip().upper()
                        if ans != "Y":
                            print("Cancel download\n")
                            continue
                    #if local_version is None, just download

                #start download
                _send(f"downloadgame {gameid}", self.client_socket)
                data = self.q.get()
                print(data)
                if(data == "Game download successful"):
                    game = self.q.get()
                    print(game)
                    file_data = self.q.get()

                    player_name = self.User["name"]
                    gameid = game["gameId"]
                    version = game["version"]

                    file_dir = os.path.join("downloads", player_name, str(gameid))
                    os.makedirs(file_dir, exist_ok=True) #create directories

                    file_path = os.path.join(file_dir, f"{version}.zip")
                    with open(file_path, "wb") as f: #create file
                        f.write(file_data)
                    
                    #update file installed_game
                    player_name = self.User["name"]
                    installed_games_path = os.path.join("downloads", player_name, "installed_games.json")

                    try:
                        with open(installed_games_path, "r", encoding="utf-8") as f:
                            installed = json.load(f)
                    except FileNotFoundError:
                        installed = {}

                    installed[str(gameid)] = {
                        "version": version
                    }

                    with open(installed_games_path, "w", encoding="utf-8") as f:
                        json.dump(installed, f, indent=2, ensure_ascii=False)
            elif(command == "4"):
                gameid = input("Enter game ID to review: ").strip()
                if not gameid:
                    print("Game ID cannot be empty\n")
                    continue
                if not gameid.isdigit():
                    print("Invalid game ID. Must be a number\n")
                    continue

                rating = input("Enter rating (1~5): ").strip()
                if not rating:
                    print("Rating cannot be empty\n")
                    continue
                if not rating.isdigit():
                    print("Rating must be a number\n")
                    continue
                rating_val = int(rating)
                if rating_val < 1 or rating_val > 5:
                    print("Rating must be between 1 and 5\n")
                    continue

                comment = input("Enter short comment (no spaces): ").strip()
                if not comment:
                    print("Comment cannot be empty\n")
                    continue
                if " " in comment:
                    print("Comment cannot contain spaces (simple protocol limit)\n")
                    continue

                user_id = self.User["id"]
                _send(f"review {gameid} {user_id} {rating_val} {comment}", self.client_socket)
                data = self.q.get()
                print(data)
            elif command == "5":
                break
            else:
                print("Invalid command\n")

    def _cleanup(self):
        if(self.if_login == 1):
            _send("logout" + " " + self.User["name"], self.client_socket)
            data = self.q.get()
            print(data)
            self.if_login = 0 
        if(self.if_in_room == 1):
            _send("leaveroom" + " " + str(self.Room["id"]) + " " + str(self.User["id"]), self.client_socket)
            data = self.q.get()
            print(data)
            self.if_in_room = 0
            self.Room.clear()
        
        self.User.clear()

    def _recv_forever(self):
        try:
            while(1):
                data = _recv_json(self.client_socket)
                if data == "GAMEPREPARE":
                    info = _recv_json(self.client_socket)
                    threading.Thread(
                        target=self.handle_game_prepare,
                        args=(info,),
                        daemon=True
                    ).start()
                elif data == "GAMEPREPARE_FAIL":
                    data = _recv_json(self.client_socket)
                    print(data)
                elif(data  == "GAMESTART"):
                    data = _recv_json(self.client_socket)
                    threading.Thread(target=self.in_game, args=(data,), daemon=True).start()
                elif(data == "Game download successful"):
                    self.q.put(data)
                    game = _recv_json(self.client_socket)
                    self.q.put(game)

                    length = _recv_len(self.client_socket, 4)
                    length = struct.unpack('>I', length)[0]

                    data = _recv_len(self.client_socket, length)
                    self.q.put(data)
                else:
                    self.q.put(data)
        except (ConnectionResetError, OSError):
            pass
        finally:
            self.client_socket.close()
    
    def _extract_game(self, game_id, version):
        base_dir = Path("client_games")
        base_dir.mkdir(parents=True, exist_ok=True)
        player_name = self.User["name"]

        game_dir = base_dir / player_name / f"game_{game_id}_v{version}" #client_games / {user} / game_{game_id}_v{version}
        config_path = game_dir / "game_config.json"

        # check if already exist
        if config_path.exists():
            return game_dir
        
        zip_path = Path("downloads")
        zip_path = zip_path / player_name / str(game_id) / f"{version}.zip" #downloads / {user} / game_id / {version}.zip
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            zip_file.extractall(game_dir)

        print(f"[CLIENT] Downloaded and extracted game {game_id} v{version} to {game_dir}")
        return game_dir


    #game prepare
    def handle_game_prepare(self, info):
        room_id = info["roomId"]
        game_id = info["gameId"]
        latest_version = info["latestVersion"]["version"] #str

        player_name = self.User["name"]
        installed_games_path = os.path.join("downloads", player_name, "installed_games.json")

        try:
            with open(installed_games_path, "r", encoding="utf-8") as f:
                installed = json.load(f)
        except FileNotFoundError:
            installed = {}

        local = installed.get(str(game_id))

        if local is None: # not installed
            print(f"[GAMEPREPARE] You haven't installed game {game_id}.")
            print("Please go to Game Store (option 3) to download it first.\n")
            _send(
                f"gameprepare_result {room_id} {self.User['id']} NOTREADY not_installed",
                self.client_socket
            )
            return

        local_ver = local.get("version")
        if local_ver != latest_version: #old version
            print(f"[GAMEPREPARE] Your version is {local_ver}, but latest is {latest_version}.")
            print("Please go to Game Store (option 3) to update before starting.\n")
            _send(
                f"gameprepare_result {room_id} {self.User['id']} NOTREADY outdated",
                self.client_socket
            )
            return
        
        game_dir = self._extract_game(game_id, local_ver) #local == latest
        config_path = game_dir / "game_config.json"
        if not config_path.exists(): #miss config
            print("There is no game_config.json.\n")
            _send(
                f"gameprepare_result {room_id} {self.User['id']} NOTREADY game_config_missing",
                self.client_socket
            )
            return

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

            if "client" not in config or "command" not in config["client"]: #check config format
                print("The game_config.json is in wrong format\n")
                _send(
                    f"gameprepare_result {room_id} {self.User['id']} NOTREADY game_config_wrong_format",
                    self.client_socket
                )
                return


        #latest version (ready)
        print("[GAMEPREPARE] Version OK, waiting for other players...\n")
        _send(
            f"gameprepare_result {room_id} {self.User['id']} READY ok",
            self.client_socket
        )

    def in_game(self, data):
        host    = data["host"]
        port    = data["port"]
        game_id = data["gameId"]
        version = data["version"]

        base_dir = Path("client_games")
        player_name = self.User["name"]
        game_dir = base_dir / player_name / f"game_{game_id}_v{version}"
        config_path = game_dir / "game_config.json"

        if not config_path.exists():
            print(f"[CLIENT] Game files missing for game {game_id} v{version}")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

            # check config format
            raw_cmd = config["client"].get("command")
            if not raw_cmd:
                print("[CLIENT] client.command not found in game_config.json")
                return

            # replace placeholder
            placeholder_map = {
                "{python}": sys.executable,
                "{host}": host,
                "{port}": str(port),
                "{userId}": str(self.User["id"]),
            }

            client_cmd = []
            for token in raw_cmd:
                for k, v in placeholder_map.items():
                    token = token.replace(k, v)
                client_cmd.append(token)

            print("Launching game client:", client_cmd, "cwd=", str(game_dir))

            # start game
            subprocess.Popen(client_cmd, cwd=str(game_dir))
    

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
    client = Client()
    client.serve_forever()
    

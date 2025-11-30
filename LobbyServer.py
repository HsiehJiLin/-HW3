import json, socket, threading, struct, subprocess, os, sys
from datetime import datetime
import zipfile
from pathlib import Path


class LobbyServer:
    def __init__(self):  
        #client
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #allow repeated binding
        self.client_socket.bind(("0.0.0.0", 13579))
        self.client_socket.listen()
        print("Lobby is listening on 0.0.0.0:13579")
        #DB
        self.DB_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.DB_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.DB_socket.connect(("127.0.0.1", 12345))
        self.matchId = 10001
        self.userID_conn = {}
        #game server
        self.Game_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.Game_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.Game_socket.bind(("0.0.0.0", 22222))
        self.Game_socket.listen()
        #lock
        self.lock = threading.Lock()
        #room during game prepare status
        self.preparing = {}

    def serve_forever(self):
        try:
            while(True):
                conn, addr = self.client_socket.accept()
                print("Accept %s:%s" % addr)
                try:
                    t = threading.Thread(target=self.handle_client, args=(conn, addr, self.DB_socket))
                    t.daemon = True 
                    t.start() # works in background
                except Exception:
                    print("Exception, client error\n")
                    conn.close()
        except KeyboardInterrupt:
            print("Server shut down")
        finally:
            self.client_socket.close()



    def handle_client(self, conn, addr, DB_socket):
       with conn:
            while(1):
                try:
                    command = _recv(conn)
                except ConnectionResetError:
                    print(f"Discconnect to player{addr}")
                    break
                with self.lock:
                    command = command.split()
                    if(command[0].upper() == "REGISTER"):
                        _send_json({
                            "collection" : "User",
                            "action" : "query",
                            "data" : {
                                "name" : command[1]
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        if(data["status"] == "success"):
                            _send_json("User already exist", conn)
                        elif(data["status"] == "fail"):
                            _send_json({
                                "collection" : "User",
                                "action" : "create",
                                "data" : {
                                    "name" : command[1],
                                    "email" : command[2],
                                    "passwordHash" : command[3],
                                    "createdAt" : datetime.now().isoformat(),
                                    "lastLoginAt" : "NONE"
                                }
                            }, self.DB_socket)
                            data = _recv_json(self.DB_socket)
                            print(data)
                            _send_json("Register successful", conn)
                    elif(command[0].upper() == "LOGIN"):
                        _send_json({
                            "collection" : "User",
                            "action" : "query",
                            "data" : {
                                "name" : command[1]#user name
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        if(data["status"] == "fail"):
                            _send_json("User does not exit", conn)
                        elif(data["status"] == "success"):
                            if(data["data"]["passwordHash"] == command[2] and data["data"]["lastLoginAt"] != "now"): #command[2] password
                                _send_json({
                                    "collection" : "User",
                                    "action" : "update",
                                    "data" : {
                                        "name" : command[1],
                                        "lastLoginAt" : "now"
                                    }
                                }, self.DB_socket)
                                data = _recv_json(self.DB_socket)
                                print(data)
                                _send_json("Login successful", conn)
                                _send_json(data["data"], conn)
                                self.userID_conn[data["data"]["id"]] = conn
                            else:
                                _send_json("Login fail", conn)                           
                    elif(command[0].upper() == "LOGOUT"):
                        #client control when can logout
                        _send_json({
                            "collection" : "User",
                            "action" : "query",
                            "data" : {
                                "name" : command[1]#user name
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        if(data["status"] == "fail"):
                            _send_json("User does not exit", conn)
                        elif(data["status"] == "success"):
                            if(data["data"]["lastLoginAt"] == "now"):
                                _send_json({
                                    "collection" : "User",
                                    "action" : "update",
                                    "data" : {
                                        "name" : command[1],
                                        "lastLoginAt" : datetime.now().isoformat()
                                    }
                                }, self.DB_socket)
                                data = _recv_json(self.DB_socket)
                                print(data)
                                _send_json("Logout successful", conn)
                                self.userID_conn.pop(data["data"]["id"], None)
                            else:
                                _send_json("Logout fail", conn)
                    elif(command[0].upper() == "CREATEROOM"):
                        roomname   = command[1]
                        visibility = command[2]
                        host_name  = command[3]
                        game_id = int(command[4])

                        #client control when can create room
                        #find user
                        _send_json({
                            "collection" : "User",
                            "action" : "query",
                            "data" : {
                                "name" : host_name #user name
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        hostUserId = data["data"]["id"]

                        #find game
                        _send_json({
                            "collection": "Game",
                            "action": "query",
                            "data": {
                                "id": game_id,
                                "status": "listed"
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        if data["status"] != "success" or not data["data"]:
                            _send_json("Game not found or not listed", conn)
                            continue

                        game = data["data"]["0"]

                        latestVersionId = game["latestVersionId"]
                        if latestVersionId is None:
                            _send_json("Game has no version, cannot create room", conn)
                            continue
                        maxPlayers = game["maxPlayers"]
                        
                        #create room
                        _send_json({
                            "collection" : "Room",
                            "action" : "create",
                            "data" : {
                                "name" : roomname,
                                "hostUserId" : hostUserId,
                                "visibility(public|private)" : visibility,
                                "inviteList[]" : [],
                                "status(idle|playing)" : "idle",
                                "createdAt" : datetime.now().isoformat(),
                                "members" : [hostUserId],
                                "gameId": game_id,
                                "gameVersionId": latestVersionId,
                                "maxPlayers": maxPlayers
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        _send_json("Create successful", conn)
                        _send_json(data["data"], conn)
                    elif(command[0].upper() == "JOINROOM"):
                        _send_json({
                            "collection" : "Room",
                            "action" : "query",
                            "data" : {
                                "id" : int(command[1]) #room id
                            }
                        }, DB_socket)

                        data = _recv_json(self.DB_socket)
                        print(data)

                        if(data["status"] == "fail" or not data["data"]):
                            _send_json("Room does not exit", conn)
                            continue

                        maxPlayers = data["data"]["maxPlayers"]
                        if(len(data["data"]["members"]) >= maxPlayers):
                            _send_json("Room is full", conn)
                            continue
                        if(data["data"]["visibility(public|private)"] == "private" and int(command[2]) not in data["data"]["inviteList[]"]):
                            _send_json("Room is private", conn)
                            continue
 
                            
                        if int(command[2]) in data["data"]["inviteList[]"]:
                            data["data"]["inviteList[]"].remove(int(command[2])) #player2 id
                        data["data"]["members"].append(int(command[2]))
                        _send_json({
                            "collection" : "Room",
                            "action" : "update",
                            "data" : {
                                "id" : int(command[1]),
                                "inviteList[]" : data["data"]["inviteList[]"],
                                "status(idle|playing)" : "idle",
                                "members" : data["data"]["members"]
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        _send_json("Join successful", conn)
                        _send_json(data["data"], conn)

                    elif(command[0].upper() == "ONLINELIST"):
                        _send_json({
                            "collection" : "User",
                            "action" : "read"
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        online_list = {}
                        for ID in range(1, data["nextID"]):
                            ID = str(ID)
                            if(data[ID]["lastLoginAt"] == "now"):
                                online_list[ID] = {
                                    "name" : data[ID]["name"],
                                    "email" : data[ID]["email"],
                                    "lastLoginAt" : data[ID]["lastLoginAt"]
                                }
                        _send_json(online_list, conn)
                    elif(command[0].upper() == "ROOMLIST"):
                        _send_json({
                            "collection" : "Room",
                            "action" : "read"
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        room_list = {}

                        for ID in range(1, data["nextID"]):
                            ID = str(ID)
                            room = data[ID]

                            if room["visibility(public|private)"] != "public":
                                continue

                            if room["status(idle|playing)"] != "idle":
                                continue

                            game_id = room.get("gameId")
                            if game_id is None:
                                continue

                            # check game is listed
                            _send_json({
                                "collection": "Game",
                                "action": "query",
                                "data": {
                                    "id": game_id,
                                    "status": "listed" #listed
                                }
                            }, self.DB_socket)
                            game_data = _recv_json(self.DB_socket)
                            print(f"ROOMLIST Game query for room {ID}:", game_data)

                            if game_data["status"] != "success" or not game_data["data"]:
                                continue

                            room_list[ID] = {
                                "name" : data[ID]["name"],
                                "hostUserId" : data[ID]["hostUserId"],
                                "visibility(public|private)" : data[ID]["visibility(public|private)"],
                                "inviteList[]" : data[ID]["inviteList[]"],
                                "status(idle|playing)" : data[ID]["status(idle|playing)"],
                                "createdAt" : data[ID]["createdAt"],
                                "members" : data[ID]["members"]
                            }

                        _send_json(room_list, conn)
                    elif(command[0].upper() == "INVITE"):
                        #client control when can invite
                        _send_json({
                            "collection" : "Room",
                            "action" : "query",
                            "data" : {
                                "id" : int(command[2]) #room id
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)

                        if(data["status"] == "fail"):
                            _send_json("Room does not exit", conn)
                            continue

                        if(len(data["data"]["members"]) >= data["data"]["maxPlayers"]):
                            _send_json("Room is full", conn)
                            continue

                        data["data"]["inviteList[]"].append(int(command[1])) #player begin invited
                        _send_json({
                            "collection" : "Room",
                            "action" : "update",
                            "data" : {
                                "id" : int(command[2]),
                                "inviteList[]" : data["data"]["inviteList[]"], 
                                "status(idle|playing)" : "idle",
                                "members" : data["data"]["members"]
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        _send_json("Invite successful", conn)
                        
                    elif(command[0].upper() == "INVITATION"):
                        _send_json({
                            "collection" : "Room",
                            "action" : "read",
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        invitation_list = {}
                        for ID in range(1, data["nextID"]):
                            ID = str(ID)
                            for invitedID in (data[ID]["inviteList[]"]):
                                if(invitedID == int(command[1])): #playerID
                                    invitation_list[ID] = {
                                        "name" : data[ID]["name"],
                                        "hostUserId" : data[ID]["hostUserId"],
                                        "visibility(public|private)" : data[ID]["visibility(public|private)"],
                                        "inviteList[]" : data[ID]["inviteList[]"],
                                        "status(idle|playing)" : data[ID]["status(idle|playing)"],
                                        "createdAt" : data[ID]["createdAt"],
                                        "members" : data[ID]["members"]
                                    }
                        _send_json(invitation_list, conn)
                    elif(command[0].upper() == "GAMESTART"):
                        room_id = int(command[1])
                        _send_json({
                            "collection" : "Room",
                            "action" : "query",
                            "data" : {
                                "id" : room_id
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)

                        #check room status
                        if(data["status"] == "fail"):
                            _send_json("Room does not exit", conn)
                            continue
                        room = data["data"]
                        members = room["members"]

                        #check number of members
                        if len(members) < 2:
                            _send_json("Not enough players", conn)
                            continue
                        if len(members) > room["maxPlayers"]:
                            _send_json("Too many players", conn)
                            continue
 
                        #check if idle
                        if room["status(idle|playing)"] != "idle":
                            _send_json("Player in the room is already playing", conn)
                            continue
                        game_id = room.get("gameId")
                        if game_id is None:
                            _send_json("This room has no game bound", conn)
                            continue

                        _send_json({
                            "collection": "Game",
                            "action": "query",
                            "data": {
                                "id": game_id,
                                "status": "listed"
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("GAMESTART Game query:", data)

                        if data["status"] != "success" or not data["data"]:
                            _send_json("Game not found or not listed", conn)
                            continue

                        game = data["data"]["0"]
                        latestVersionId = game["latestVersionId"]
                        if latestVersionId is None:
                            _send_json("Game has no version, cannot start", conn)
                            continue  

                        # check game listed
                        if game["status"] != "listed":
                            _send_json("Game is not listed, cannot start", conn)
                            continue  

                        _send_json({
                            "collection": "GameVersion",
                            "action": "query",
                            "data": {
                                "gameId": game_id
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("GAMESTART GameVersion read:", data)

                        if data["status"] != "success":
                            _send_json("Cannot read GameVersion", conn)
                            continue

                        gameversion = data["data"]
                        target_gameversion = None

                        for key in gameversion:
                            if gameversion[key]["id"] == latestVersionId:
                                target_gameversion = gameversion[key]
                                break

                        if target_gameversion is None:
                            _send_json("Latest version info not found", conn)
                            continue

                        #add room_id to prepare
                        self.preparing[room_id] = {
                            "members": members[:],
                            "ready": set(),
                            "not_ready": {},
                            "gameId": game_id,
                            "latestVersionId": latestVersionId,
                            "latestVersion": target_gameversion ,
                            "room": room
                        }

                        #broadcast GAMEPREPARE to every players
                        for user_id in members:
                            c = self.userID_conn.get(user_id)
                            if not c:
                                continue
                            _send_json("GAMEPREPARE", c)
                            _send_json({
                                "roomId": room_id,
                                "gameId": game_id,
                                "latestVersionId": latestVersionId,
                                "latestVersion": target_gameversion,
                            }, c)
                        _send_json("Game prepare started, waiting for players", conn)
                        
                    elif command[0].upper() == "GAMEPREPARE_RESULT":
                        room_id = int(command[1])
                        user_id = int(command[2])
                        status = command[3].upper()
                        reason = command[4]

                        if status == "READY":
                            self.preparing[room_id]["ready"].add(user_id)
                        else:
                            self.preparing[room_id]["not_ready"][user_id] = reason

                        total = len(self.preparing[room_id]["members"])
                        replied = len(self.preparing[room_id]["ready"]) + len(self.preparing[room_id]["not_ready"])

                        if replied < total: #wait for all players in the room to reply
                            continue

                        # all players replied
                        if len(self.preparing[room_id]["not_ready"]) != 0:
                            fail_info = {
                                "roomId": room_id,
                                "notReady": self.preparing[room_id]["not_ready"]
                            }
                            for user_id in self.preparing[room_id]["members"]:
                                c = self.userID_conn.get(user_id)
                                if c:
                                    _send_json("GAMEPREPARE_FAIL", c) #cancle startgame
                                    _send_json(fail_info, c)
                            del self.preparing[room_id]
                        else:
                            room            = self.preparing[room_id]["room"]
                            members         = self.preparing[room_id]["members"]
                            game_id         = self.preparing[room_id]["gameId"]
                            latestVersion   = self.preparing[room_id]["latestVersion"] #json
                            latestVersionId = self.preparing[room_id]["latestVersionId"]

                            zip_path = latestVersion["pathOnServer"] 
                            version = latestVersion["version"] #str

                            # server_games/game_<gameId>_v<version>/
                            base_dir    = Path("server_games")
                            extract_dir = base_dir / f"game_{game_id}_v{version}" #/ == .joinpath
                            extract_dir.mkdir(parents=True, exist_ok=True)

                            # check if empty
                            if not any(extract_dir.iterdir()):
                                with zipfile.ZipFile(zip_path, "r") as zip_file:
                                    zip_file.extractall(extract_dir)
                                print(f"Extracted game {game_id} version {version} to {extract_dir}")

                            # read config file
                            config_path = extract_dir / "game_config.json"
                            if not config_path.exists(): #dosen't have config file 
                                print(f"game_config.json not found in {extract_dir}")
                                for user_id in self.preparing[room_id]["members"]:
                                    c = self.userID_conn.get(user_id)
                                    if c:
                                        _send_json("GAMEPREPARE_FAIL", c) #cancle startgame
                                        _send_json(f"game_config.json not found in {extract_dir}", c)

                                del self.preparing[room_id]
                                continue

                            with open(config_path, "r", encoding="utf-8") as f:
                                config = json.load(f)

                            # for replace
                            raw_cmd = config["server"]["command"]

                            placeholder_map = {
                                "{python}" : sys.executable,
                                "{matchId}": str(self.matchId),
                                "{roomId}": str(room_id),
                                "{startAt}": datetime.now().isoformat()
                            }

                            for idx, user_id in enumerate(members):
                                placeholder_map[f"{{user{idx}}}"] = str(user_id)

                            server_cmd = []
                            for token in raw_cmd:
                                for k, v in placeholder_map.items():
                                    token = token.replace(k, v)
                                server_cmd.append(token)

                            print("Launching game server:", server_cmd, "cwd=", str(extract_dir))

                            subprocess.Popen(server_cmd, cwd=str(extract_dir)) #current working directory

                            #update room status (playing)
                            _send_json({
                                "collection" : "Room",
                                "action" : "update",
                                "data" : {
                                    "id" : room_id,
                                    "inviteList[]" : room["inviteList[]"],
                                    "status(idle|playing)" : "playing",
                                    "members" : room["members"]
                                }
                            }, self.DB_socket)
                            data = _recv_json(self.DB_socket)
                            print(data)

                            Gconn, Gaddr = self.Game_socket.accept()
                            data2 = _recv_json(Gconn)

                            t_recv_game_server = threading.Thread(
                                target=self._recv_game_server,
                                args=(Gconn, ),
                                daemon=True
                            )
                            t_recv_game_server.start()

                            data_for_client = {
                                "host": data2["host"],
                                "port": data2["port"],
                                "gameId": game_id,
                                "version": version #str
                            }

                            for member_id in members:
                                c = self.userID_conn.get(member_id)
                                if c:
                                    _send_json("GAMESTART", c)
                                    _send_json(data_for_client, c)

                            self.matchId += 1
                            del self.preparing[room_id]
                    elif(command[0].upper() == "LEAVEROOM"):
                        #client control when can leave room
                        _send_json({
                            "collection" : "Room",
                            "action" : "query",
                            "data" : {
                                "id" : int(command[1]) #room id
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        if(data["status"] == "fail"):
                            _send_json("Room does not exit", conn)
                        elif(data["status"] == "success"):
                            if(int(command[2]) in data["data"]["members"]): #userID
                                data["data"]["members"].remove(int(command[2]))
                            _send_json({
                                "collection" : "Room",
                                "action" : "update",
                                "data" : {
                                    "id" : int(command[1]),
                                    "inviteList[]" : data["data"]["inviteList[]"],
                                    "status(idle|playing)" : "idle",
                                    "members" : data["data"]["members"]
                                }
                            }, DB_socket)
                            data = _recv_json(self.DB_socket)
                            print(data)
                            _send_json("Leave successful", conn)
                    elif(command[0].upper() == "SHOWGAMELOG"):
                        _send_json({
                            "collection" : "GameLog",
                            "action" : "query",
                            "data" : {
                                "userId" : int(command[1]) #user id
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)
                        _send_json("Show gamelog successful", conn)
                        _send_json(data, conn)
                    elif(command[0].upper() == "GAMELIST"):
                        _send_json({
                            "collection": "Game",
                            "action": "query",
                            "data": {
                                "status": "listed"
                            }
                        }, DB_socket)

                        data = _recv_json(self.DB_socket)
                        print("GAMELIST from DB:", data)

                        if data["status"] == "success":
                            _send_json("Gamelist successful", conn)
                            _send_json(data["data"], conn)
                        else:
                            _send_json("Gamelist failed", conn)
                    elif(command[0].upper() == "GAMEINFO"):
                        game_id = int(command[1])
                        _send_json({
                            "collection": "Game",
                            "action": "query",
                            "data": {
                                "id": game_id
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("GAMEINFO Game query:", data)

                        if data["status"] != "success" or not data["data"]:
                            _send_json("Game not found", conn)
                            continue

                        game = data["data"]["0"]

            
                        _send_json({
                            "collection": "GameVersion",
                            "action": "query",
                            "data": {
                                "gameId": game_id
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("GAMEINFO GameVersion query:", data)
                        versions = data["data"]

                        #view reviews
                        _send_json({
                            "collection": "Review",
                            "action": "query",
                            "data": {
                                "gameId": game_id
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("GAMEINFO Review query:", data)
                        reviews = data["data"]

                        # game info, version info, reveiw info
                        info = {
                            "game": game,
                            "versions": versions,
                            "reviews": reviews
                        }

                        _send_json("Game info successful", conn)
                        _send_json(info, conn)
                    elif command[0].upper() == "DOWNLOADGAME":
                        if len(command) < 2 or not command[1].isdigit():
                            _send_json("Download failed: invalid game id", conn)
                            continue

                        game_id = int(command[1])

                        _send_json({
                            "collection": "Game",
                            "action": "query",
                            "data": {
                                "id": game_id
                            }
                        }, DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("DOWNLOADGAME Game query:", data)

                        if data["status"] != "success" or not data["data"]:
                            _send_json("Download failed: game not found", conn)
                            continue

                        game = data["data"]["0"]

                        latestVersionId = game["latestVersionId"]
                        if latestVersionId is None:
                            _send_json("Download failed: no version", conn)
                            continue

                        # find latestVersionId
                        _send_json({
                            "collection": "GameVersion",
                            "action": "query",
                            "data": {
                                "gameId": game_id
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("DOWNLOADGAME GameVersion query:", data)

                        if data["status"] != "success":
                            _send_json("Download failed: version data error", conn)
                            continue

                        gameversion = data["data"]
                        target_gameversion = None

                        for key in gameversion:
                            if gameversion[key]["id"] == latestVersionId:
                                target_gameversion = gameversion[key]
                                break

                        if target_gameversion is None:
                            _send_json("Download failed: version not found", conn)
                            continue

                        path = target_gameversion["pathOnServer"]
                        if not path or not os.path.exists(path):
                            _send_json("Download failed: file not found on server", conn)
                            continue

                        # get file size
                        file_size = os.path.getsize(path)

                        game = {
                            "status": "success",
                            "gameId": game_id,
                            "version": target_gameversion["version"],
                            "fileSize": file_size,
                            "fileName": os.path.basename(path),
                        }

                        _send_json("Game download successful", conn)
                        _send_json(game, conn)

                        # send .zip
                        header = struct.pack(">I", file_size)
                        conn.sendall(header)
                        try:
                            with open(path, "rb") as f:
                                remaining = file_size
                                while remaining > 0:
                                    chunk = f.read(min(4096, remaining))
                                    if not chunk:
                                        break
                                    conn.sendall(chunk)
                                    remaining -= len(chunk)
                            print("upload completed")
                        except OSError as e:
                            print(f"upload fail: {e}")
                            continue

                        print(f"DOWNLOADGAME: sent {file_size} bytes for game {game_id}")
                    elif(command[0].upper() == "REVIEW"):
                        game_id = int(command[1])
                        user_id = int(command[2])
                        rating  = int(command[3])
                        comment = command[4]

                        #find game
                        _send_json({
                            "collection": "Game",
                            "action": "query",
                            "data": {
                                "id": game_id
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("REVIEW Game query:", data)

                        if data["status"] != "success" or not data["data"]:
                            _send_json("Review failed: game not found", conn)
                            continue

                        #check gamelog
                        _send_json({
                            "collection": "GameLog",
                            "action": "query",
                            "data": {
                                "userId": user_id
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("REVIEW GameLog query:", data)

                        if data["status"] != "success":
                            _send_json("Review failed: cannot read GameLog", conn)
                            continue

                        gamelog = data["data"]
                        played = False
                        for key in gamelog:
                            if gamelog[key]["gameId"] == game_id: #check if played before
                                played = True
                                break

                        if not played:
                            _send_json("Review failed: you have not played this game yet", conn)
                            continue

                        #check if review already exist
                        _send_json({
                            "collection": "Review",
                            "action": "query",
                            "data": {
                                "gameId": game_id,
                                "userId": user_id
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("REVIEW Review query:", data)
                        review = data["data"]

                        if len(review) == 0:
                            _send_json({
                                "collection": "Review",
                                "action": "create",
                                "data": {
                                    "gameId": game_id,
                                    "userId": user_id,
                                    "rating": rating,
                                    "comment": comment,
                                    "createdAt": datetime.now().isoformat()
                                }
                            }, self.DB_socket)
                            cresp = _recv_json(self.DB_socket)
                            print("REVIEW Review create:", cresp)

                            if cresp["status"] != "success":
                                _send_json("Review failed: DB error", conn)
                                continue

                            _send_json("Review successful", conn)
                        else:
                            review_id = review["0"]["id"]

                            _send_json({
                                "collection": "Review",
                                "action": "update",
                                "data": {
                                    "id": review_id,
                                    "rating": rating,
                                    "comment": comment,
                                    "createdAt": datetime.now().isoformat()
                                }
                            }, self.DB_socket)
                            data = _recv_json(self.DB_socket)
                            print("REVIEW Review update:", data)

                            if data["status"] != "success":
                                _send_json("Review failed: DB error on update", conn)
                                continue

                            _send_json("Review successful (updated)", conn)

    def _recv_game_server(self, Gconn):
        data = _recv_json(Gconn)
        with self.lock:
            room_id = data["roomId"]
            #room info
            _send_json({
            "collection": "Room",
            "action": "query",
            "data": {
                "id": room_id
                }
            }, self.DB_socket)
            room_data = _recv_json(self.DB_socket)
            print("Room query:", room_data)

            game_id = None
            game_version_id = None
            game_version = None

            if room_data["status"] == "success":
                room = room_data["data"]
                game_id = room["gameId"]
                game_version_id = room["gameVersionId"]

                if game_version_id is not None:
                    _send_json({
                        "collection": "GameVersion",
                        "action": "query",
                        "data": {
                            "id": game_version_id
                        }
                    }, self.DB_socket)
                    game_version_data = _recv_json(self.DB_socket)
                    print("GameVersion query:", game_version_data)

                    game_version = game_version_data["data"]["0"]["version"]


            _send_json({
                "collection" : "GameLog",
                "action" : "create",
                "data" : {
                    "matchId" : data["matchId"],
                    "roomId" : data["roomId"],
                    "users:[userId]" : data["users:[userId]"],
                    "startAt" : data["startAt"],
                    "endAt" : data["endAt"],
                    "results": data["results"],
                    "gameId": game_id,
                    "gameVersionId": game_version_id,
                    "gameVersion": game_version
                }
            }, self.DB_socket)
            resp = _recv_json(self.DB_socket)
            print(resp)

            _send_json({
                "collection" : "Room",
                "action" : "query",
                "data" : {
                    "id" : room_id
                }
            }, self.DB_socket)
            data2 = _recv_json(self.DB_socket)
            print(data2)
            if(data2["status"] == "fail"):
                pass
            elif(data2["status"] == "success"):
                _send_json({
                    "collection" : "Room",
                    "action" : "update",
                    "data" : {
                        "id" : room_id,
                        "inviteList[]" : data2["data"]["inviteList[]"], 
                        "status(idle|playing)" : "idle",
                        "members" : data2["data"]["members"]
                    }
                }, self.DB_socket)

                resp2 = _recv_json(self.DB_socket)
                print(resp2)


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
        try:
            temp = socket.recv(n - len(data))
            if(not temp):
                raise ConnectionResetError
            data += temp
        except ConnectionResetError:
            raise ConnectionResetError
    return data

def _recv(socket):
    try:
        length = _recv_len(socket, 4)
        length = struct.unpack('>I', length)[0]
        if(length <= 0 or length > 65536):
            socket.close()
            return
    except ConnectionResetError:
        raise ConnectionResetError
    return _recv_len(socket, length).decode()

def _send_json(msg, socket):
    data = json.dumps(msg).encode("utf-8")
    if(len(data) <= 0 or len(data) > 65536):
        socket.close()
        return
    header = struct.pack(">I", len(data))
    socket.sendall(header+data)

def _recv_json_len(socket, n):
    data = b''
    while(len(data) < n):
        data += socket.recv(n - len(data))
    return data

def _recv_json(socket):
    length = _recv_json_len(socket, 4)
    length = struct.unpack('>I', length)[0]
    if(length <= 0 or length > 65536):
        socket.close()
        return
    return json.loads(_recv_json_len(socket, length).decode())


if(__name__ == "__main__"):
    lobby_server = LobbyServer()
    lobby_server.serve_forever()

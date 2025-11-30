import json, socket, threading, struct, os
from datetime import datetime

class DeveloperServer:
    def __init__(self):  
        #client
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #allow repeated binding
        self.client_socket.bind(("0.0.0.0", 24680))
        self.client_socket.listen()
        print("Develope server is listening on 0.0.0.0:24680")
        #DB
        self.DB_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.DB_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.DB_socket.connect(("127.0.0.1", 12345))
        #lock
        self.lock = threading.Lock()

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
                            "collection" : "Developer",
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
                                "collection" : "Developer",
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
                            "collection" : "Developer",
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
                                    "collection" : "Developer",
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
                            else:
                                _send_json("Login fail", conn)                           
                    elif(command[0].upper() == "LOGOUT"):
                        #client control when can logout
                        _send_json({
                            "collection" : "Developer",
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
                                    "collection" : "Developer",
                                    "action" : "update",
                                    "data" : {
                                        "name" : command[1],
                                        "lastLoginAt" : datetime.now().isoformat()
                                    }
                                }, self.DB_socket)
                                data = _recv_json(self.DB_socket)
                                print(data)
                                _send_json("Logout successful", conn)
                            else:
                                _send_json("Logout fail", conn)
                    elif(command[0].upper() == "LISTMYGAMES"):
                        dev_id = int(command[1])
                        _send_json({
                            "collection": "Game",
                            "action": "query",
                            "data": {
                                "authorId": dev_id
                            }
                        }, self.DB_socket)

                        data = _recv_json(self.DB_socket)
                        print("LISTMYGAMES from DB:", data)

                        if(data["status"] != "success"):
                            _send_json("List my games failed", conn)
                            continue

                        games = data["data"]
                        result = {}

                        for key in games:
                            game_id = games[key]["id"]

                            _send_json({
                                "collection": "GameVersion",
                                "action": "query",
                                "data": {
                                    "gameId": game_id 
                                }
                            }, self.DB_socket)

                            data = _recv_json(self.DB_socket)
                            print(f"LISTMYGAMES version query for game {game_id}:", data)

                            if data["status"] != "success":
                                versions = {}
                                latest = None
                            else:
                                versions = data["data"]
                                latest = None
                                for ver_key in versions:
                                    if latest is None or versions[ver_key]["id"] > latest:
                                        latest = versions[ver_key]["id"]

                            result[str(game_id)] = {
                                "game": games[key],
                                "versions": versions,
                                "latestVersionId": latest
                            }
 
                        _send_json("List my games successful", conn)
                        _send_json(result, conn)
                    elif(command[0].upper() == "UPLOADGAME"):
                        dev_name = command[1]
                        game_name = command[2]
                        game_type = command[3]
                        max_players = int(command[4])
                        file_size   = int(command[5])

                        _send_json({
                            "collection": "Developer",
                            "action": "query",
                            "data": {
                                "name": dev_name
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print(data)

                        if data["status"] != "success":
                            _send_json("Developer not found", conn)
                            continue

                        developer = data["data"]
                        if developer["lastLoginAt"] != "now":
                            _send_json("Developer not logged in", conn)
                            continue

                        author_id = developer["id"]
                        _send_json({
                            "collection": "Game",
                            "action": "create",
                            "data": {
                                "name": game_name,
                                "authorId": author_id,
                                "type": game_type,
                                "maxPlayers": max_players,
                                "description": "",
                                "status": "listed",
                                "latestVersionId": None,
                                "createdAt": datetime.now().isoformat()
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("UPLOADGAME Game create:", data)

                        if data["status"] != "success":
                            _send_json("Create Game failed", conn)
                            continue
                        game = data["data"]

                        #make directories
                        os.makedirs("uploaded_games", exist_ok=True)
                        zip_filename = f"game_{game['id']}_v1.zip"
                        game_path = os.path.join("uploaded_games", zip_filename)

                        #recieve /zip file
                        try:
                            file_data = _recv_len(conn, file_size)
                            with open(game_path, "wb") as f:
                                f.write(file_data)
                            print(f"Saved uploaded game to: {game_path}")
                        except ConnectionResetError:
                            print("Client disconnected while uploading file")
                            continue
                        except OSError as e:
                            print(f"Saving uploaded file failed: {e}")
                            continue

                        _send_json({
                            "collection": "GameVersion",
                            "action": "create",
                            "data": {
                                "gameId": game["id"],
                                "version": "1.0.0",
                                "changelog": "Initial upload",
                                "pathOnServer": game_path,
                                "createdAt": datetime.now().isoformat()
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("UPLOADGAME GameVersion create:", data)

                        if data["status"] != "success":
                            _send_json("Create GameVersion failed", conn)
                            continue

                        game_version = data["data"]
                        _send_json({
                            "collection": "Game",
                            "action": "update",
                            "data": {
                                "id": game["id"],
                                "latestVersionId": game_version["id"]
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("UPLOADGAME Game update:", data)

                        if data["status"] != "success":
                            _send_json("Update Game latestVersionId failed", conn)
                            continue

                        _send_json("Upload game successful", conn)
                        _send_json(data, conn)
                    elif(command[0].upper() == "UNLISTGAME"):
                        game_id = int(command[1])
                        dev_name = command[2]

                        _send_json({
                            "collection": "Developer",
                            "action": "query",
                            "data": {
                                "name": dev_name
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("UNLISTGAME Developer query:", data)

                        if data["status"] != "success":
                            _send_json("Developer not found", conn)
                            continue

                        developer = data["data"]
                        if developer.get("lastLoginAt") != "now":
                            _send_json("Developer not logged in", conn)
                            continue

                        author_id = developer["id"]

                        _send_json({
                            "collection": "Game",
                            "action": "query",
                            "data": {
                                "id": game_id
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("UNLISTGAME Game query:", data)

                        if data["status"] != "success":
                            _send_json("Game not found", conn)
                            continue

                        game = data["data"]["0"]

                        if game["authorId"] != author_id: #check the author
                            _send_json("Permission denied: not your game", conn)
                            continue

                        #unlist game
                        _send_json({
                            "collection": "Game",
                            "action": "update",
                            "data": {
                                "id": game_id,
                                "status": "unlisted"
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("UNLISTGAME Game update:", data)

                        if data["status"] != "success":
                            _send_json("Unlist game failed", conn)
                            continue

                        _send_json("Unlist game successful", conn)
                    elif(command[0].upper() == "UPDATEGAME"):
                        dev_name    = command[1]
                        game_id     = int(command[2])
                        new_version = command[3]
                        file_size   = int(command[4])

                        _send_json({
                            "collection": "Developer",
                            "action": "query",
                            "data": {
                                "name": dev_name
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("UPDATEGAME Developer query:", data)

                        if data["status"] != "success":
                            _send_json("Developer not found", conn)
                            _recv_len(conn, file_size)
                            continue

                        developer = data["data"]
                        if developer.get("lastLoginAt") != "now":
                            _send_json("Developer not logged in", conn)
                            _recv_len(conn, file_size)
                            continue

                        author_id = developer["id"]

                        _send_json({
                            "collection": "Game",
                            "action": "query",
                            "data": {
                                "id": game_id
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("UPDATEGAME Game query:", data)

                        if data["status"] != "success" or not data["data"]:
                            _send_json("Game not found", conn)
                            _recv_len(conn, file_size)
                            continue

                        game = data["data"]["0"]

                        if game["authorId"] != author_id: #check the author
                            _send_json("Permission denied: not your game", conn)
                            _recv_len(conn, file_size)
                            continue

                        #save .zip file (new version)
                        os.makedirs("uploaded_games", exist_ok=True)
                        new_version = new_version.replace("/", "_") #for safety
                        zip_filename = f"game_{game_id}_v{new_version}.zip"
                        game_path = os.path.join("uploaded_games", zip_filename)

                        try:
                            file_data = _recv_len(conn, file_size)
                            with open(game_path, "wb") as f:
                                f.write(file_data)
                            print(f"UPDATEGAME: saved new version to {game_path}")
                        except (ConnectionResetError, OSError) as e:
                            print(f"UPDATEGAME: receive file failed: {e}")
                            continue


                        #create GameVersion
                        _send_json({
                            "collection": "GameVersion",
                            "action": "create",
                            "data": {
                                "gameId": game_id,
                                "version": new_version,
                                "changelog": f"Update to {new_version}",
                                "pathOnServer": game_path,
                                "createdAt": datetime.now().isoformat()
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("UPDATEGAME GameVersion create:", data)

                        if data["status"] != "success":
                            _send_json("Update game failed: create GameVersion failed", conn)
                            continue

                        game_version = data["data"]

                        #update game
                        _send_json({
                            "collection": "Game",
                            "action": "update",
                            "data": {
                                "id": game_id,
                                "latestVersionId": game_version["id"]
                            }
                        }, self.DB_socket)
                        data = _recv_json(self.DB_socket)
                        print("UPDATEGAME Game update:", data)

                        if data["status"] != "success":
                            _send_json("Update game failed", conn)
                            continue

                        _send_json("Update game successful", conn)      
                        _send_json(data, conn)                  


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
    developer_server = DeveloperServer()
    developer_server.serve_forever()

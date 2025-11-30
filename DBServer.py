import json, socket, threading, struct, os
#- `User`：`{ id, name, email, passwordHash, createdAt, lastLoginAt }`
#- `Room`：`{ id, name, hostUserId, visibility("public"|"private"), inviteList[], status("idle"|"playing"), createdAt }`
#- `GameLog`：`{ id, matchId, roomId, users:[userId], startAt, endAt, results:[{userId, score, lines, maxCombo}] }`

#{
#  "collection": "User | Room | GameLog",
#  "action": "create | read | update | delete | query",
#  "data": { ... }   // 具體欄位見下
#}

DB_FILE = os.path.expanduser("./users.json")
class AccountDatabase:
    def __init__ (self):
        self.DB_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.DB_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #allow repeated binding
        self.DB_socket.bind(("0.0.0.0", 12345))
        self.DB_socket.listen()
        print("DB is on 0.0.0.0:12345")

        self.User = {"nextID" : 1}
        self.Room = {"nextID" : 1}
        self.GameLog = {"nextID" : 1}

        #developer
        self.Developer = {"nextID": 1}
        self.Game = {"nextID": 1}
        self.GameVersion = {"nextID": 1}
        self.Review = {"nextID": 1}

        self.reply = {}

        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.User = data.get("User", {"nextID": 1})
                self.Room = data.get("Room", {"nextID": 1})
                self.GameLog = data.get("GameLog", {"nextID": 1})
                self.Developer = data.get("Developer", {"nextID": 1})
                self.Game = data.get("Game", {"nextID": 1})
                self.GameVersion = data.get("GameVersion", {"nextID": 1})
                self.Review = data.get("Review", {"nextID": 1})
        else:
            self.User = {"nextID": 1}
            self.Room = {"nextID": 1}
            self.GameLog = {"nextID": 1}
            self.Developer = {"nextID": 1}
            self.Game = {"nextID": 1}
            self.GameVersion = {"nextID": 1}
            self.Review = {"nextID": 1}

    def save_to_disk(self):
        data = {
            "User": self.User,
            "Room": self.Room,
            "GameLog": self.GameLog,
            "Developer": self.Developer,
            "Game": self.Game,
            "GameVersion": self.GameVersion,
            "Review": self.Review
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def serve_forever(self):
        try:
            while(True):
                conn, addr = self.DB_socket.accept()
                print("Accept %s:%s" % addr)
                try:
                    t = threading.Thread(target=self.CRUD, args=(conn, addr), daemon = True)
                    t.start() # works in background
                except Exception:
                    print("Exception, DB server fail\n")
                    conn.close()
        except KeyboardInterrupt:
            print("DB server shut down")
        finally:
            self.DB_socket.close()
    
    def CRUD(self, conn, addr):
        with conn:
            while(1):
                try:
                    package = _recv_json(conn)
                except ConnectionResetError:
                    print(f"Discconnect to server{addr}")
                    break
                
                if(package["collection"] == "User"):
                    if(package["action"] == "create"):
                        self.User_create(package["data"], conn)
                        self.save_to_disk()
                    elif(package["action"] == "read"):
                        self.User_read(conn)
                    elif(package["action"] == "update"):
                        self.User_update(package["data"], conn)
                        self.save_to_disk()
                    elif(package["action"] == "delete"):
                        self.User_delete()
                    elif(package["action"] == "query"):
                        self.User_query(package["data"], conn)
                elif(package["collection"] == "Room"):
                    if(package["action"] == "create"):
                        self.Room_create(package["data"], conn)
                        self.save_to_disk()
                    elif(package["action"] == "read"):
                        self.Room_read(conn)
                    elif(package["action"] == "update"):
                        self.Room_update(package["data"], conn)
                        self.save_to_disk()
                    elif(package["action"] == "delete"):
                        self.Room_delete()
                    elif(package["action"] == "query"):
                        self.Room_query(package["data"], conn)
                elif(package["collection"] == "GameLog"):  
                    if(package["action"] == "create"):
                        self.Gamelog_create(package["data"], conn)
                        self.save_to_disk()
                    elif(package["action"] == "read"):
                        self.Gamelog_read()
                    elif(package["action"] == "update"):
                        self.Gamelog_update()
                    elif(package["action"] == "delete"):
                        self.Gamelog_delete()
                    elif(package["action"] == "query"):
                        self.Gamelog_query(package["data"], conn)       
                #developer
                elif package["collection"] == "Developer":
                    if package["action"] == "create":
                        self.Developer_create(package["data"], conn)
                        self.save_to_disk()
                    elif package["action"] == "read":
                        self.Developer_read(conn)
                    elif package["action"] == "update":
                        self.Developer_update(package["data"], conn)
                        self.save_to_disk()
                    elif package["action"] == "delete":
                        self.Developer_delete()
                    elif package["action"] == "query":
                        self.Developer_query(package["data"], conn)

                elif package["collection"] == "Game":
                    if package["action"] == "create":
                        self.Game_create(package["data"], conn)
                        self.save_to_disk()
                    elif package["action"] == "read":
                        self.Game_read(conn)
                    elif package["action"] == "update":
                        self.Game_update(package["data"], conn)
                        self.save_to_disk()
                    elif package["action"] == "delete":
                        self.Game_delete()
                    elif package["action"] == "query":
                        self.Game_query(package["data"], conn)

                elif package["collection"] == "GameVersion":
                    if package["action"] == "create":
                        self.GameVersion_create(package["data"], conn)
                        self.save_to_disk()
                    elif package["action"] == "read":
                        self.GameVersion_read(conn)
                    elif package["action"] == "update":
                        self.GameVersion_update(package["data"], conn)
                        self.save_to_disk()
                    elif package["action"] == "delete":
                        self.GameVersion_delete()
                    elif package["action"] == "query":
                        self.GameVersion_query(package["data"], conn)

                elif package["collection"] == "Review":
                    if package["action"] == "create":
                        self.Review_create(package["data"], conn)
                        self.save_to_disk()
                    elif package["action"] == "read":
                        self.Review_read(conn)
                    elif package["action"] == "update":
                        self.Review_update(package["data"], conn)
                        self.save_to_disk()
                    elif package["action"] == "delete":
                        self.Review_delete()
                    elif package["action"] == "query":
                        self.Review_query(package["data"], conn)
    

    def User_create(self, data, conn):
        ID = self.User["nextID"]
        ID = str(ID)
        self.User[ID] = {}
        self.User[ID]["id"] = int(ID)
        self.User[ID]["name"] = data["name"]
        self.User[ID]["email"] = data["email"]
        self.User[ID]["passwordHash"] = data["passwordHash"]
        self.User[ID]["createdAt"] = data["createdAt"]
        self.User[ID]["lastLoginAt"] = data["lastLoginAt"]
        self.reply = {"status" : "success", "data" : self.User[ID]}
        self.User["nextID"] += 1
        _send_json(self.reply, conn)
    def User_read(self, conn):
        self.reply = self.User
        _send_json(self.reply, conn)
    def User_update(self, data, conn):
        for ID in range(1, self.User["nextID"]):
            ID = str(ID)
            if(data["name"] == self.User[ID]["name"] ):
                self.User[ID]["lastLoginAt"] = data["lastLoginAt"]
                self.reply = {"status" : "success", "data" : self.User[ID]}
                _send_json(self.reply, conn)
                return
    def User_delete():
        pass
    def User_query(self, data, conn):
        for ID in range(1, self.User["nextID"]):
            ID = str(ID)
            if(data["name"] == self.User[ID]["name"] ):
                self.reply = {"status" : "success", "data" : self.User[ID]}
                _send_json(self.reply, conn)
                return
        self.reply = {"status" : "fail", "data" : {}}
        _send_json(self.reply, conn)
        return 


    def Room_create(self, data, conn):
        ID = self.Room["nextID"]
        ID = str(ID)
        self.Room[ID] = {}
        self.Room[ID]["id"] = int(ID)
        self.Room[ID]["name"] = data["name"]
        self.Room[ID]["hostUserId"] = data["hostUserId"]
        self.Room[ID]["visibility(public|private)"] = data["visibility(public|private)"]
        self.Room[ID]["inviteList[]"] = data["inviteList[]"]
        self.Room[ID]["status(idle|playing)"] = data["status(idle|playing)"]
        self.Room[ID]["createdAt"] = data["createdAt"] 
        self.Room[ID]["members"] = data["members"]
        #game
        self.Room[ID]["gameId"] = data["gameId"]
        self.Room[ID]["gameVersionId"] = data["gameVersionId"] 
        self.Room[ID]["maxPlayers"] = data["maxPlayers"]

        self.reply = {"status" : "success", "data" : self.Room[ID]}
        self.Room["nextID"] += 1
        _send_json(self.reply, conn)
    def Room_read(self, conn):
        self.reply = self.Room
        _send_json(self.reply, conn)    
    def Room_update(self, data, conn):
        for ID in range(1, self.Room["nextID"]):
            ID = str(ID)
            if(data["id"] == self.Room[ID]["id"] ):
                self.Room[ID]["inviteList[]"] = data["inviteList[]"]
                self.Room[ID]["status(idle|playing)"] = data["status(idle|playing)"]
                self.Room[ID]["members"] = data["members"]
                self.reply = {"status" : "success", "data" : self.Room[ID]}
                _send_json(self.reply, conn)
                return
    def Room_delete():
        pass
    def Room_query(self, data, conn):
        for ID in range(1, self.Room["nextID"]):
            ID = str(ID)
            if(data["id"] == self.Room[ID]["id"] ):
                self.reply = {"status" : "success", "data" : self.Room[ID]}
                _send_json(self.reply, conn)
                return
        self.reply = {"status" : "fail", "data" : {}}
        _send_json(self.reply, conn)
        return 
    

    def Gamelog_create(self, data, conn):
        ID = self.GameLog["nextID"]
        ID = str(ID)
        self.GameLog[ID] = {}
        self.GameLog[ID]["id"] = int(ID)
        self.GameLog[ID]["matchId"] = data["matchId"]
        self.GameLog[ID]["roomId"] = data["roomId"]
        self.GameLog[ID]["users:[userId]"] = data["users:[userId]"]
        self.GameLog[ID]["startAt"] = data["startAt"]
        self.GameLog[ID]["endAt"] = data["endAt"]
        self.GameLog[ID]["results"] = data["results"]
        #game info
        self.GameLog[ID]["gameId"] = data["gameId"]
        self.GameLog[ID]["gameVersionId"] = data["gameVersionId"]
        self.GameLog[ID]["gameVersion"] = data["gameVersion"]

        self.reply = {"status" : "success", "data" : self.GameLog[ID]}
        self.GameLog["nextID"] += 1
        _send_json(self.reply, conn)
    def Gamelog_read():
        pass
    def Gamelog_update():
        pass
    def Gamelog_delete():
        pass
    def Gamelog_query(self, data, conn):
        gamelog_list = {}
        gamelog_count = 1
        for ID in range(1, self.GameLog["nextID"]):
            ID = str(ID)
            for userId in self.GameLog[ID]["users:[userId]"]:
                if(data["userId"] == userId):
                    gamelog_list[gamelog_count] = self.GameLog[ID]
                    gamelog_count = gamelog_count + 1
        self.reply = {"status" : "success", "data" : gamelog_list}
        _send_json(self.reply, conn)

    #new CRUD
    def Developer_create(self, data, conn):
        """
        data：
        {
            "name": str,
            "email": str,
            "passwordHash": str,
            "createdAt": str,
            "lastLoginAt": str (optional)
        }
        """
        ID = self.Developer["nextID"]
        ID = str(ID)
        self.Developer[ID] = {
            "id": int(ID),
            "name": data["name"],
            "email": data["email"],
            "passwordHash": data["passwordHash"],
            "createdAt": data["createdAt"],
            "lastLoginAt": data.get("lastLoginAt", data["createdAt"]),
        }
        self.Developer["nextID"] += 1
        self.reply = {"status": "success", "data": self.Developer[ID]}
        _send_json(self.reply, conn)

    def Developer_read(self, conn):
        self.reply = {"status": "success", "data": self.Developer}
        _send_json(self.reply, conn)

    def Developer_update(self, data, conn):
        #update by ID or name
        target = None

        if "id" in data:
            ID = str(data["id"])
            if ID in self.Developer:
                target = ID
        elif "name" in data:
            for ID in range(1, self.Developer["nextID"]):
                ID = str(ID)
                if ID in self.Developer and self.Developer[ID]["name"] == data["name"]:
                    target = ID
                    break

        if target is None:
            self.reply = {"status": "fail", "reason": "developer_not_found"}
            _send_json(self.reply, conn)
            return

        for key, value in data.items():
            if key in ("id", "name"):
                continue
            self.Developer[target][key] = value

        self.reply = {"status": "success", "data": self.Developer[target]}
        _send_json(self.reply, conn)

    def Developer_delete(self):
        pass

    def Developer_query(self, data, conn):
        #query by name or email
        name = data.get("name")
        email = data.get("email")

        for ID in range(1, self.Developer["nextID"]):
            ID = str(ID)
            if ID not in self.Developer:
                continue
            dev = self.Developer[ID]

            if name is not None and dev["name"] == name:
                self.reply = {"status": "success", "data": self.Developer[ID]}
                _send_json(self.reply, conn)
                return
            if email is not None and dev["email"] == email:
                self.reply = {"status": "success", "data": self.Developer[ID]}
                _send_json(self.reply, conn)
                return
        self.reply = {"status" : "fail", "data" : {}}
        _send_json(self.reply, conn)


    def Game_create(self, data, conn):
        """
        data：
        {
            "name": str,
            "authorId": int,
            "type": str,        # "CLI" / "GUI" ...
            "maxPlayers": int,
            "description": str,
            "status": str,      # "listed" / "unlisted"
            "latestVersionId": int or None,
            "createdAt": str
        }
        """
        ID = self.Game["nextID"]
        ID = str(ID)
        self.Game[ID] = {
            "id": int(ID),
            "name": data["name"],
            "authorId": data["authorId"],
            "type": data["type"],
            "maxPlayers": data["maxPlayers"],
            "description": data.get("description", ""),
            "status": data.get("status", "listed"),
            "latestVersionId": data.get("latestVersionId"),
            "createdAt": data["createdAt"],
        }
        self.Game["nextID"] += 1
        self.reply = {"status": "success", "data": self.Game[ID]}
        _send_json(self.reply, conn)

    def Game_read(self, conn):
        self.reply = {"status": "success", "data": self.Game}
        _send_json(self.reply, conn)

    def Game_update(self, data, conn):
        if "id" not in data:
            self.reply = {"status": "fail", "reason": "missing_id"}
            _send_json(self.reply, conn)
            return

        ID = str(data["id"])
        if ID not in self.Game:
            self.reply = {"status": "fail", "reason": "game_not_found"}
            _send_json(self.reply, conn)
            return

        for key, value in data.items():
            if key == "id":
                continue
            self.Game[ID][key] = value

        self.reply = {"status": "success", "data": self.Game[ID]}
        _send_json(self.reply, conn)

    def Game_delete(self):
        pass

    def Game_query(self, data, conn):
        #query by game_id, authorId, status(list/unlist)
        Game_list = {}
        Game_count = 0

        game_id = data.get("id")
        author_id = data.get("authorId")
        status = data.get("status")

        for ID in range(1, self.Game["nextID"]):
            ID = str(ID)
            if ID not in self.Game:
                continue
            g = self.Game[ID]

            if game_id is not None and g["id"] != game_id:
                continue
            if author_id is not None and g["authorId"] != author_id:
                continue
            if status is not None and g["status"] != status:
                continue
            Game_list[str(Game_count)] = self.Game[ID]
            Game_count = Game_count + 1

        self.reply = {"status" : "success", "data" : Game_list}
        _send_json(self.reply, conn)

    def GameVersion_create(self, data, conn):
        """
        data :
        {
            "gameId": int,
            "version": str,
            "changelog": str,
            "pathOnServer": str,
            "createdAt": str
        }
        """
        ID = self.GameVersion["nextID"]
        ID = str(ID)
        self.GameVersion[ID] = {
            "id": int(ID),
            "gameId": data["gameId"],
            "version": data["version"],
            "changelog": data.get("changelog", ""),
            "pathOnServer": data["pathOnServer"],
            "createdAt": data["createdAt"],
        }
        self.GameVersion["nextID"] += 1
        self.reply = {"status": "success", "data": self.GameVersion[ID]}
        _send_json(self.reply, conn)

    def GameVersion_read(self, conn):
        self.reply = {"status": "success", "data": self.GameVersion}
        _send_json(self.reply, conn)

    def GameVersion_update(self, data, conn):
        if "id" not in data:
            self.reply = {"status": "fail", "reason": "missing_id"}
            _send_json(self.reply, conn)
            return

        ID = str(data["id"])
        if ID not in self.GameVersion:
            self.reply = {"status": "fail", "reason": "game_version_not_found"}
            _send_json(self.reply, conn)
            return

        for key, value in data.items():
            if key == "id":
                continue
            self.GameVersion[ID][key] = value

        self.reply = {"status": "success", "data": self.GameVersion[ID]}
        _send_json(self.reply, conn)

    def GameVersion_delete(self):
        pass

    def GameVersion_query(self, data, conn):
        GameVersion_list = {}
        GameVersion_count = 0
        #query by gameId, version
        gameversion_id = data.get("id")
        game_id = data.get("gameId")
        version = data.get("version")

        for ID in range(1, self.GameVersion["nextID"]):
            ID = str(ID)
            if ID not in self.GameVersion:
                continue
            gv = self.GameVersion[ID]

            if gameversion_id is not None and gv["id"] != gameversion_id:
                continue
            if game_id is not None and gv["gameId"] != game_id:
                continue
            if version is not None and gv["version"] != version:
                continue

            GameVersion_list[str(GameVersion_count)] = self.GameVersion[ID]
            GameVersion_count += 1

        self.reply = {"status" : "success", "data" : GameVersion_list}
        _send_json(self.reply, conn)


    def Review_create(self, data, conn):
        """
        data :
        {
            "gameId": int,
            "userId": int,
            "rating": int,      # 1~5
            "comment": str,
            "createdAt": str
        }
        """
        ID = self.Review["nextID"]
        ID = str(ID)
        self.Review[ID] = {
            "id": int(ID),
            "gameId": data["gameId"],
            "userId": data["userId"],
            "rating": data["rating"],
            "comment": data.get("comment", ""),
            "createdAt": data["createdAt"],
        }
        self.Review["nextID"] += 1
        self.reply = {"status": "success", "data": self.Review[ID]}
        _send_json(self.reply, conn)

    def Review_read(self, conn):
        self.reply = {"status": "success", "data": self.Review}
        _send_json(self.reply, conn)

    def Review_update(self, data, conn):
        if "id" not in data:
            self.reply = {"status": "fail", "reason": "missing_id"}
            _send_json(self.reply, conn)
            return

        ID = str(data["id"])
        if ID not in self.Review:
            self.reply = {"status": "fail", "reason": "review_not_found"}
            _send_json(self.reply, conn)
            return

        for key, value in data.items():
            if key == "id":
                continue
            self.Review[ID][key] = value

        self.reply = {"status": "success", "data": self.Review[ID]}
        _send_json(self.reply, conn)

    def Review_delete(self):
        pass

    def Review_query(self, data, conn):
        Review_list = {}
        Review_count = 0
        #query by gameId, userId
        game_id = data.get("gameId")
        user_id = data.get("userId")

        for ID in range(1, self.Review["nextID"]):
            ID = str(ID)
            if ID not in self.Review:
                continue
            rv = self.Review[ID]

            if game_id is not None and rv["gameId"] != game_id:
                continue
            if user_id is not None and rv["userId"] != user_id:
                continue

            Review_list[str(Review_count)] = self.Review[ID]
            Review_count += 1

        self.reply = {"status": "success", "data": Review_list}
        _send_json(self.reply, conn)


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
        try:
            temp = socket.recv(n - len(data))
            if(not temp):
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
        

if(__name__ == "__main__"):
    DB_server = AccountDatabase()
    DB_server.serve_forever()
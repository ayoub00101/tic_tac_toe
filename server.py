import flask
import flask_socketio as fs
import uuid
import random
app = flask.Flask(__name__)
app.secret_key = str(uuid.uuid4())
socketio = fs.SocketIO(app)
users = {}
waiting_room = []
games_room = {}

@app.route("/")
def index():
    return flask.render_template("index.html")

@app.route("/waiting_room/<username>")
def waiting(username):
    return flask.render_template("waiting.html", username=username)

@app.route("/game")
def game():
    username = flask.session.get("username")
    if not username:
        flask.flash("Connectez-vous à une session.")
        return flask.redirect(flask.url_for("index"))
    print("SESSION:",games_room[list(games_room.keys())[-1]]["players"])
    player1, player2 = games_room[list(games_room.keys())[-1]]["players"]
    print("1" * 20)
    return flask.render_template("game.html", player1=player1, player2=player2)

@app.route("/submit", methods=["GET", "POST"])
def new_user():
    if flask.request.method == "POST":
        username = flask.request.form.get("username").strip().lower()
    else:
        username = flask.request.args.get("username", "").strip().lower()
        print("GET:",username)

    if username:
        if username in users.keys() and flask.request.method == "POST":
            flask.flash("Nom d'utilisateur déjà utilisé. Veuillez réessayer.")
        else:
            if username not in users:
                users[username] = {}
                users[username]["replay"] = False
                print("new_user:", users)
            flask.session["username"] = username
            return flask.redirect(flask.url_for("waiting", username=username))
    else:
        flask.flash("Nom d'utilisateur requis.")
    return flask.redirect(flask.url_for("index"))

@socketio.on("connect")
def handle_connect():
    username = flask.session.get("username")
    if username:
        present = [True if username in game_room["players"] else False for game_room in games_room.values()]  
        if not True in present:
                print(username, "is connected.")
                print("connect:", users)
                users[username]["sid"] = flask.request.sid
                waiting_room.append(username)
                print("WAIIITING ROOM",waiting_room)
                check_start_game()
    else:
        print("A user connected without a session.")
        socketio.emit("redirect", {"url": "/"}, room=flask.request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    username = flask.session.get("username")
    print("verif disconnect:", username)
    if username:
        print(username, "is disconnected.")
        if username in users and not users[username].get("redirected", False):
            del users[username]
        elif username in waiting_room and users[username]["replay"] == False:
            print('NON FRERO DSL')
            waiting_room.remove(username)
    else:
        print("A user disconnected without a session.")

def check_start_game():
    print("waiting room:", waiting_room)
    if len(waiting_room) >= 2:
        players = [waiting_room.pop(0),waiting_room.pop(0)]
        player1 = random.choice(players)
        players.remove(player1)
        player2 = players.pop()
        sid1 = users[player1]['sid']
        print(f"Player 1:\n\tusername: {player1}\n\tsid: {sid1}")
        sid2 = users[player2]['sid']
        print(f"Player 2:\n\tusername: {player2}\n\tsid: {sid2}")
        print("waiting_room:", waiting_room)
        game_id = str(uuid.uuid4())
        players = [player1,player2]

        games_room[game_id] = {"players": (player1, player2), "to_play": player1, "grid": ["_" for e in range(9)]}
        users[player1]["redirected"] = True
        users[player2]["redirected"] = True

        print("0" * 20)
        socketio.emit('start_game', {'game_id': game_id, "players": [player1, player2]}, room=[sid1, sid2])
        print(f"Game started between {player1} and {player2}")
        print(f"Game ID: {game_id}")

tours = 0
@socketio.on("ready_to_play")
def handle_ready_to_play(data):
    global tours
    game_id = data['game_id']
    if game_id in games_room:
        player1, player2 = games_room[game_id]["players"]
        if tours==1:
            users[player1]["sid"] = flask.request.sid
            socketio.emit("handle_players",{"play":True,"actual_player":player1}, room=users[player1]["sid"])
            print(f"player1: {player1}, sid: {users[player1]['sid']}")
            tours = 0
        else:
            tours+=1
            users[player2]["sid"] = flask.request.sid
            socketio.emit("handle_players", {"play":False,"actual_player":player2}, room=users[player2]["sid"])
            print(f"player2: {player2}, sid: {users[player2]['sid']}")

        print("SID:",flask.request.sid)
        print("HANDLE SERVER TO CLIENT")

@socketio.on("play")
def handle_players(data):
    game_id = data["game_id"]
    player1,player2 = games_room[game_id]["players"]
    had_play = games_room[game_id]["to_play"]
    actual_player = player2 if player1 == games_room[game_id]["to_play"] else player1
    sid1 = users[had_play]["sid"]
    sid2 = users[actual_player]["sid"]
    print(f"game_room: {games_room[game_id]}; actual_player: {actual_player}")
    socketio.emit("handle_players", {"play":False,"actual_player":actual_player}, room=sid1)
    socketio.emit("handle_players", {"play":True,"actual_player":actual_player}, room=sid2)
    games_room[game_id]["to_play"] = actual_player

    #mettre a jour le cote client de l'utilisateur qui n'a pas joue
    socketio.emit("update_grid",{"td_id":data["td_id"]},room=users[actual_player]["sid"])

    games_room[game_id]["grid"][int(data["td_id"])] = "X" if had_play==player1 else "0"
    print(f"GAME : {player1} VS {player2}\nGRID: {games_room[game_id]['grid']}")
    if check_game(games_room[game_id]['grid'])[0]:
        if check_game(games_room[game_id]['grid'])[1] == "win":
            socketio.emit("game_over",{"result":"win","winner":had_play},room=sid1)
            socketio.emit("game_over",{"result":"lose","loser":actual_player},room=sid2)
        else:
            socketio.emit("game_over",{"result":"nul"},room=[sid1,sid2])
        del games_room[game_id]
        print(games_room)

def check_game(grid):
    for e in range(3):
        if grid[e*3] == grid[e*3+1] == grid[e*3+2] and grid[e*3] != "_":
            return True,"win"
        elif grid[e] == grid[e+3] == grid[e+6] and grid[e] != "_":
            return True,"win"
    if (grid[0] == grid[4] == grid[8] or grid[6] == grid[4] == grid[2]) and grid[4] != "_":
        return True,"win"
    elif len(grid) == 9 and not '_' in grid:
        return True,"nul"
    return False,None

@socketio.on("replay")
def add_waiting_room():
    username,dic = [player for player in users.items() if player[1]["sid"]==flask.request.sid][0]
    sid = dic["sid"]
    users[username]["replay"] = True
    print("SID:",sid)
    print("username:",username)
    print("USERS:",users)
    socketio.emit("redirect", {"url": flask.url_for("new_user"),"username":username}, room=users[username]["sid"])

@socketio.on("disconnect_replay")
def disconnect_replay():
    pass

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)

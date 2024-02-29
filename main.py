#room & chat functionality is added in this project
from flask import Flask,render_template, request,url_for,redirect,session,g,make_response,jsonify
import os
import pymongo
from werkzeug.utils import secure_filename
from flask_session import Session
from datetime import datetime 
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
import shutil

app=Flask(__name__)
s = URLSafeTimedSerializer('secret!')
app.config['SECRET_KEY'] = 'myveryverysecretkey!'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Path to the static/img folder
img_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'img')

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
password = os.environ.get("MONGODB_PASSWORD")

#use below 3 lines for mongodb cloud database (mongodb atlas)
client = pymongo.MongoClient(f"mongodb+srv://tegeyep442:{password}@cluster0.pkmvwjl.mongodb.net/")
db = client['losersclub'] #database name is losersclub
rooms = db['room'] #table name is room


#===============================================================
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase

socketio = SocketIO(app)
#===============================================================


# this function set the global users, if user is in the session
@app.before_request
def before_request():
    g.user=None
    g.room=None
    g.name=None
    if 'username' in session:
        g.user=session["username"]
    if 'room' in session:
        g.room=session["room"]
    if 'name' in session:
        g.name=session["name"]


# generate a unique code for the created room 
def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        Record = rooms.find_one({"room":code})
        if Record is None:
            break
    return code

# initial page when comes on website
@app.get("/")
def room_get():
    if g.room:
        return redirect(url_for('home'))
    else:
        return render_template("room.html")

# it joins the user into room 
@app.post('/room')
def room_enter_post():
    name = request.form.get('name')
    room = request.form.get('code')

    Record=rooms.find_one({"room":room})
    if Record:
        session["room"]=room
        session["name"]=name
        return jsonify({'success': True})
    return jsonify({'success': False, 'msg': 'Invalid room code'})

# it create a room and joins simultaneously
@app.post('/room/create')
def room_create_post():
    name = request.form.get('name')
    room = generate_unique_code(4)
    Record = rooms.find_one({"room": room})

    if not Record:
        rooms.insert_one({'room': room,'posts':[],'members': 0, 'messages': []}) # initial schema when user create a room.
        session["room"]=room
        session["name"]=name
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'msg': 'room already exists / something went wrong'})

# it displays the page inside room
@app.route("/home")
def home():
    if g.room:       
        data = rooms.find_one({"room":g.room})
        if not data:
            return redirect(url_for('room_logout'))
        
        # if g.user:
        #     login=True
        # else:
        #     login=False 
        login = True if g.user else False
            
        return render_template("home.html",
                               isLogin =login,
                               user_name=g.name,
                               room_name=g.room,
                               members=data["members"],
                               messages=data["messages"])

    else:
        return redirect(url_for('room_get'))

# it displays the admin login page
@app.get('/login')
def login_get():
    if g.user:
        return redirect(url_for('home'))
    else:
        return render_template("login.html")

# it gets the entered credentials of admin
@app.post('/login')
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    if username == "ujjuraj" and password == "12345":
        session["username"]=username
        return jsonify({'success': True})
    return jsonify({'success': False, 'msg': 'Invalid username or password'})

# for any kind of error occured in project.
@app.errorhandler(404)
def not_found(error):
    resp = make_response(render_template('error.html'), 404)
    resp.headers['X-Something'] = 'A value'
    return resp

# logouts the admin
@app.route("/logout")
def admin_logout():
    session['username']=False
    return redirect(url_for('home'))

# logouts the user from room
@app.route("/room/logout")
def room_logout():
    session['room']=False
    session['name']=False
    return redirect(url_for('room_get'))

# fetch the posts and send to AJAX for loading posts without reloading the page
@app.get("/fetch_posts")
def fetch_posts():
    Record=rooms.find_one({"room":g.room})
    if g.user:
        login=True
    else:
        login=False
    # print(Record)
    if Record:
        return jsonify({"login":login,"data":Record['posts']})
    else:
        return jsonify({"login":login,"data":[]})
    
# generate unique name for the post uploaded for no conflicts
def generate_unique_filename(original_filename):
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename, extension = os.path.splitext(original_filename)
    return f'{filename}_{timestamp}{extension}'

# upload the post and saving the data into file
@app.route('/upload', methods=['POST'])
def upload_post():
    post_data = request.form.get('post_data')
    image_file = request.files.get('image')
    if image_file:
        unique_filename = generate_unique_filename(image_file.filename)
        filename = os.path.join(img_folder, unique_filename)
        image_file.save(filename)

        new_post = {"filename":unique_filename,
                    "caption":post_data,
                    "time":datetime.now().strftime('%m/%d/%Y hour:%H min:%M'),
                    "user":g.name}
        
        rooms.update_one({"room":g.room},
                         {"$push":{"posts":new_post}})

        # time.sleep(1)
        return jsonify({'success': True, 'msg': 'Post uploaded successfully'})
    else:
        return jsonify({'success': False, 'msg': 'Post not uploaded'})


# to delete the post and remove the data from file
@app.route('/delete', methods=['POST'])
def delete_post():
    data = request.json
    post_to_delete = {"filename": data.get('post')}
    if post_to_delete:
        rooms.update_one(
            {"room": g.room},
            {"$pull": {"posts": post_to_delete}}
        )

        source_folder = "static/img"
        destination_folder = "static/deleted"
        image_filename =  data.get('post')
        move_image(source_folder, destination_folder, image_filename)

        return jsonify({'success': True, 'msg': 'Post deleted successfully'})
    else:
        return jsonify({'success': False, 'msg': 'Post deletion failed'})
    

# if post deleted then move the image from "main" folder to "deleted posts" folder
def move_image(source_folder, destination_folder, image_filename):
    source_path = os.path.join(source_folder, image_filename)
    destination_path = os.path.join(destination_folder, image_filename)
    try:
        # cut and paste the image file using shutil
        shutil.move(source_path, destination_path)
        print(f"Image '{image_filename}' moved successfully from {source_folder} to {destination_folder}")
    except FileNotFoundError:
        print(f"Image '{image_filename}' not found in {source_folder}")
    except Exception as e:
        print(f"An error occurred: {e}")


#=========================================================================================================================================
#socket code

# when someone message while in the room
@socketio.on("message")
def message(data):
    room = session.get('room')
    Record=rooms.find_one({"room":room})

    if Record is None:
        return 
    
    content = {
        "name": session.get('name'),
        "message": data["data"]
    }
    
    send(content, to=room)
    rooms.update_one({"room":room},
                         {"$push":{"messages":content}})
    print(f"{session.get('name')} said: {data['data']}")


# it runs when someone enters into the room
@socketio.on("connect")
def connect(auth):
    room = session.get('room')
    name = session.get('name') 

    if not room or not name:
        return
    Record = rooms.find_one({"room":room})
    if Record is None:
        leave_room(room)
        return
    
    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)

    rooms.update_one({"room":room},
                    {"$inc":{"members":1}})
    print(f"{name} joined room {room}")


# it runs when someone disconnects or left the room
@socketio.on("disconnect")
def disconnect():
    room = session.get('room')
    name = session.get('name')
    leave_room(room)

    Record = rooms.find_one({"room":room})
    if Record:
        rooms.update_one({"room":room},
                        {"$inc":{"members": -1}})
        
    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")




if __name__ == "__main__":
    # app.run(debug=True) #use this to run on 127.0.0.1
    app.run(host="192.168.1.4",debug=True) #use this to access application on network, don't forget to change host from your ip address.
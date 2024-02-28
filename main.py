#room & chat functionality is added in this project
import os,pickle
from flask import Flask,render_template, request,url_for,redirect,session,g,make_response,jsonify
from werkzeug.utils import secure_filename
from flask_session import Session
from datetime import datetime 
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
import time
import os
import shutil


app=Flask(__name__)
s = URLSafeTimedSerializer('secret!')
app.config['SECRET_KEY'] = 'secret'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
# Path to the static/img folder
img_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'img')


#===============================================================
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase

socketio = SocketIO(app)
#===============================================================

# if no data in file , create one
file1=open("losers.dat","ab+")
if file1.tell()<=0:
    Record={}
    with open('losers.dat','wb') as file2:
        pickle.dump(Record,file2)
        file2.close()
file1.close()

# this function set the global user, if user is in the session
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

def read_Record():
    file=open("losers.dat","rb")
    Record=pickle.load(file)
    file.close()
    return Record

# generate a unique code for room created
def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        Record = read_Record()
        if code not in Record:
            break
    return code

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

    Record=read_Record()
    if Record.get(room):
        session["room"]=room
        session["name"]=name
        return jsonify({'success': True})
    return jsonify({'success': False, 'msg': 'Invalid room name or password'})

# it create a room and joins simultaneously
@app.post('/room/create')
def room_create_post():
    name = request.form.get('name')
    room = generate_unique_code(4)
    Record=read_Record()
    if Record.get(room) is None:
        with open('losers.dat','wb') as file2:
            Record[room]=[[],{'members': 0, 'messages': []}] # initial schema when user create a room.
            pickle.dump(Record,file2)
            file2.close()
        session["room"]=room
        session["name"]=name
        print(Record)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'msg': 'room already exists / something went wrong'})

# it displays the page inside room
@app.route("/home")
def home():
    if g.room:
        file=open("losers.dat","rb")
        try:
            Record=pickle.load(file)
        except:
            return "something went wrong !! Go back."
        file.close()
        print(Record,g.room)
        data = Record[g.room][1]
        
        if g.user:
            login=True
        else:
            login=False 
        return render_template("home.html",isLogin =login,user_name=g.name,room_name=g.room,members=data["members"], messages=data["messages"])
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
    file2=open("losers.dat","rb")
    Record=pickle.load(file2)
    if g.user:
        login=True
    else:
        login=False

    if Record.get(session['room'])!=None:
        return jsonify({"login":login,"data":Record.get(session['room'])[0]})
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

        Record=read_Record()
        # print(Record)
        Record.get(session['room'])[0].append([unique_filename,post_data,datetime.now().strftime('%m/%d/%Y hour:%H min:%M'),g.name])
        with open('losers.dat','wb') as file2:
            pickle.dump(Record,file2)
        time.sleep(1)
        return jsonify({'success': True, 'msg': 'Post uploaded successfully'})
    else:
        return jsonify({'success': False, 'msg': 'Post not uploaded'})


# to delete the post and remove the data from file
@app.route('/delete', methods=['POST'])
def delete_post():
    data = request.json 
    post_to_delete = data.get('post')
    if post_to_delete:
        Record=read_Record()
        Record.get(session['room'])[0] = [post for post in Record.get(session['room'])[0] if post[0] != post_to_delete]
        with open('losers.dat','wb') as file2:
            pickle.dump(Record,file2)

        source_folder = "static/img"
        destination_folder = "static/deleted"
        image_filename =  post_to_delete

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
    
    Record=read_Record()
    if room not in Record:
        return 
    
    content = {
        "name": session.get('name'),
        "message": data["data"]
    }
    
    send(content, to=room)
    Record[room][1]["messages"].append(content)

    with open('losers.dat','wb') as file:
        pickle.dump(Record,file)
    print(f"{session.get('name')} said: {data['data']}")


# it runs when someone enters into the room
@socketio.on("connect")
def connect(auth):
    room = session.get('room')
    name = session.get('name') 
    if not room or not name:
        return
    Record = read_Record()
    if room not in Record:
        leave_room(room)
        return
    
    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)

    Record[room][1]["members"] += 1
    with open('losers.dat','wb') as file:
        pickle.dump(Record,file)
    print(f"{name} joined room {room}")


# it runs when someone disconnects or left the room
@socketio.on("disconnect")
def disconnect():
    room = session.get('room')
    name = session.get('name')
    leave_room(room)

    Record = read_Record()
    if room in Record:
        Record[room][1]["members"] -= 1
        # uncomment if we want to delete the room if no member is there.
        # if Record[room][1]["members"] <= 0:
        #     del Record[room]
    
    with open('losers.dat','wb') as file:
        pickle.dump(Record,file)
    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")




if __name__ == "__main__":
    socketio.run(app)
    # app.run(host="192.168.1.6",debug=True)
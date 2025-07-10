import re
from flask import Flask, flash, make_response, render_template, request, redirect, send_from_directory, url_for, session, jsonify, abort
from flask_pymongo import PyMongo
from flask_socketio import SocketIO, emit, join_room
import bcrypt
import os
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from datetime import datetime
import pytz
from pdf2image import convert_from_path
import os


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# MongoDB connection setup
app.config['MONGO_URI'] = 'mongodb://localhost:27017/skill_swap_db'
mongo = PyMongo(app)

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client['study_materials_db']
materials_collection = db['materials']

app.secret_key = 'StudentSkillSwap@123'  # Secret key for session management

# File upload settings
UPLOAD_FOLDER = 'backend/static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'txt', 'mp4', 'mp3', 'zip', 'xlsx', 'pptx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Helper function to check file type
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_pdf_thumbnail(pdf_path, thumbnail_path):
    try:
        images = convert_from_path(pdf_path, first_page=1, last_page=1)  # Extract first page
        if images:
            images[0].save(thumbnail_path, 'PNG')  # Save as PNG
            return thumbnail_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
    return None

# -------------------- Index Page --------------------
@app.route('/')
def index():
    if 'email' in session:
        return redirect(url_for('home'))

    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# -------------------- User Authentication --------------------
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import bcrypt

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'email' in session:  #  Prevent back access if already logged in
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = mongo.db.users.find_one({'email': email})
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['email'] = email
            flash("Login successful!", "success")  #  Flash success message
            
            # Response to remove previous page
            response = make_response(redirect(url_for('home')))
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        else:
            flash("Invalid email or password!", "error")  #  Flash error message
            return redirect(url_for('login'))

    # Prevents browser from caching the login page
    response = make_response(render_template("SignUp_LogIn_Form.html"))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'registration_data' not in session and 'email' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "error")
            return redirect(url_for('register'))

        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for('register'))

        #  Password Strength Validation
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
        if not re.search(r'[A-Z]', password):
            flash("Password must contain at least one uppercase letter.", "error")
        if not re.search(r'[a-z]', password):
            flash("Password must contain at least one lowercase letter.", "error")
        if not re.search(r'\d', password):
            flash("Password must contain at least one number.", "error")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            flash("Password must contain at least one special character (!@#$%^&* etc.).", "error")

        existing_user = mongo.db.users.find_one({'email': email})
        if existing_user:
            flash("Email is already registered!", "error")
            return redirect(url_for('register'))

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        # Store data temporarily in session (don't insert into MongoDB yet)
        session['registration_data'] = {
            'name': name,
            'email': email,
            'password': hashed_password  # make sure it's JSON-serializable
        }

        # Store email in session for later use (e.g., profile view)
        session['email'] = email
        return redirect(url_for('profile'))
    return render_template("SignUp_LogIn_Form.html")

# -------------------- Logout --------------------
@app.route('/logout')
def logout():
    session.pop('email', None)

    # Prevent going back to home after logout
    response = make_response(redirect(url_for('login')))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# -------------------- User Profile --------------------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    # Redirect if user is not logged in
    if 'email' not in session:
        return redirect(url_for('login'))

    #  Prevent access if registration is already completed
    if not session.get('registration_data'):
        return redirect(url_for('home'))

    if request.method == 'POST':
        dob = request.form.get('dob')
        gender = request.form.get('gender')
        role = request.form.get('role')
        department = request.form.get('department')
        bio = request.form.get('bio')
        studying_year = request.form.get('studying_year') if role == 'student' else None
        
        profile_picture = request.files.get('profile_picture')
        profile_picture_url = None

        if profile_picture and allowed_file(profile_picture.filename):
            filename = secure_filename(profile_picture.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_picture.save(file_path)
            profile_picture_url = f"/static/uploads/{filename}"

        registration_data = session.get('registration_data', {})

        # Save user to MongoDB
        mongo.db.users.insert_one({
            'name': registration_data['name'],
            'email': registration_data['email'],
            'password': registration_data['password'],
            'dob': dob,
            'gender': gender,
            'role': role,
            'studying_year': studying_year,
            'department': department,
            'bio': bio,
            'profile_picture': profile_picture_url
        })

        # Clear registration data to lock profile page
        session.pop('registration_data', None)

        return redirect(url_for('home'))

    return render_template('profile.html')

# -------------------- Home Route --------------------
@app.route('/home')
def home():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = mongo.db.users.find_one({'email': session['email']})

    response = make_response(render_template('home.html', user=user))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


# -------------------- Fetch Users from the Same Department --------------------
@app.route('/users')
def get_users():
    if 'email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    current_user = mongo.db.users.find_one({'email': session['email']})

    # Fetch all users in the same department, excluding the logged-in user
    users = list(mongo.db.users.find({'department': current_user['department'], 'email': {'$ne': current_user['email']}}))

    users_data = [
        {
            'name': u.get('name', 'Unknown'),
            'email': u.get('email', 'No Email'),
            'profile_picture': u['profile_picture'] if u.get('profile_picture') else "/static/default.png",
            'department': u.get('department', 'N/A'),
            'role': u.get('role', 'N/A'),
            'studying_year': u.get('studying_year', 'N/A'),
            'gender': u.get('gender', 'N/A'),
            'bio': u.get('bio', 'No bio available')
        }
        for u in users
    ]

    return jsonify(users_data)



# -------------------- Fetch Messages --------------------
@app.route('/messages/<email>')
def get_messages(email):
    if 'email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    messages = list(mongo.db.messages.find({
        '$or': [
            {'sender': session['email'], 'receiver': email},
            {'sender': email, 'receiver': session['email']}
        ]
    }))

    return jsonify([
        {
            'message': m.get('message', ''),
            'is_sender': m['sender'] == session['email'],
            'file_url': m.get('file_url', None),
            'timestamp': m.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M')) 
 #  Fallback to current time if missing
        }
        for m in messages
    ])


# -------------------- Socket.io Messaging --------------------
@socketio.on('send_message')
def handle_send_message(data):
    sender = session.get('email')
    receiver = data.get('receiver')
    message = data.get('message', '')
    file_url = None
    file_type = None

    IST = pytz.timezone('Asia/Kolkata')
    timestamp = datetime.now(IST).isoformat()  # Ensure timestamp is correctly formatted

    # Handle file uploads
    if 'file' in data:
        file = data['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            file_url = f"/static/uploads/{filename}"

            # Determine file type
            ext = filename.lower().rsplit(".", 1)[1]
            if ext in ["png", "jpg", "jpeg", "gif"]:
                file_type = "image"
            elif ext in ["mp4", "webm", "mov"]:
                file_type = "video"
            else:
                file_type = "document"

    #  Save message in database with timestamp
    new_message = {
        'sender': sender,
        'receiver': receiver,
        'message': message,
        'file_url': file_url,
        'file_type': file_type,
        'timestamp': timestamp
    }
    mongo.db.messages.insert_one(new_message)

    # Emit message instantly to both users
    if sender != receiver:
        socketio.emit('receive_message', new_message, room=receiver)  # Send to receiver only if it's different
    socketio.emit('receive_message', new_message, room=sender)  # Ensure sender gets only one copy



@app.route('/upload_message', methods=['POST'])
def upload_message():
    if 'email' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    sender = session['email']
    receiver = request.form.get('receiver')
    message = request.form.get('message', '')  # Allow empty messages if a file is sent
    file_url = None

    #  Get current timestamp in Indian Standard Time (IST)
    IST = pytz.timezone('Asia/Kolkata')  
    timestamp = datetime.now(IST).isoformat()

    # Check if a file was uploaded
    if 'file' in request.files:
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)  # Save the file
            file_url = f"/static/uploads/{filename}"  # Correct file URL for frontend

    #  Store message in MongoDB with a timestamp
    mongo.db.messages.insert_one({
        'sender': sender,
        'receiver': receiver,
        'message': message,
        'file_url': file_url,
        'timestamp': timestamp  # Ensure timestamp is saved
    })

    return jsonify({'success': True, 'message': message, 'file_url': file_url, 'timestamp': timestamp})

#  Auto-fetch messages without duplicate route conflict
@app.route('/fetch_messages', methods=['GET'])
def fetch_messages():
    if 'email' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    sender = session['email']
    receiver = request.args.get('receiver')

    if not receiver:
        return jsonify({'success': False, 'error': 'Receiver required'}), 400

    messages = mongo.db.messages.find({
        '$or': [
            {'sender': sender, 'receiver': receiver},
            {'sender': receiver, 'receiver': sender}
        ]
    }).sort("timestamp", 1)  # Sort by timestamp

    seen_messages = set()
    messages_list = []
    IST = pytz.timezone('Asia/Kolkata')

    for msg in messages:
        # Fix: Convert string timestamps to datetime before formatting
        if isinstance(msg.get('timestamp'), str):
            try:
                utc_time = datetime.fromisoformat(msg['timestamp'])
            except ValueError:
                utc_time = datetime.utcnow()
        else:
            utc_time = msg.get('timestamp', datetime.utcnow())

        ist_time = utc_time.astimezone(IST).strftime("%d-%b-%Y %I:%M %p")  # Convert to IST

        msg_tuple = (msg['sender'], msg['receiver'], msg.get('message', ''), msg.get('file_url', ''))
        if msg_tuple in seen_messages:
            continue  # Skip duplicate messages
        seen_messages.add(msg_tuple)

        messages_list.append({
            'sender': msg['sender'],
            'receiver': msg['receiver'],
            'message': msg.get('message', ''),
            'file_url': msg.get('file_url', ''),
            'timestamp': ist_time  #  Use formatted IST time
        })

    return jsonify({'success': True, 'messages': messages_list})

@app.route('/study-materials', methods=['GET', 'POST'])
def study_materials():
    if 'email' not in session:
        return redirect(url_for('login'))

    #  Fetch user's name from MongoDB
    user = mongo.db.users.find_one({"email": session['email']})
    user_name = user['name'] if user and 'name' in user else session['email']

    #  Handle file upload
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file uploaded", 400

        file = request.files['file']
        if file.filename == '':
            return "No selected file", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Generate thumbnail
        thumbnail_filename = f"{filename.rsplit('.', 1)[0]}.png"
        thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], thumbnail_filename)
        if filename.lower().endswith('.pdf'):
            generate_pdf_thumbnail(filepath, thumbnail_path)
        else:
            thumbnail_filename = 'default_thumbnail.png'

        #  Store upload time in UTC
        materials_collection.insert_one({
            'filename': filename,
            'filepath': filepath,
            'thumbnail': thumbnail_filename,
            'uploaded_by': user_name,
            'upload_date': datetime.utcnow()  # Stored in UTC
        })

        return redirect(url_for('study_materials'))

    # Fetch materials & convert UTC to IST
    materials = []
    for material in materials_collection.find():
        upload_time_utc = material.get('upload_date', datetime.utcnow())  # Get stored time
        upload_time_ist = upload_time_utc + timedelta(hours=5, minutes=30)  # Convert to IST
        material['upload_date'] = upload_time_ist.strftime('%d %b %Y, %I:%M %p')  # Format time
        materials.append(material)

    return render_template('study_materials.html', materials=materials, user_name=user_name)

# Ensure UPLOAD_FOLDER is correctly set (No double 'backend/')

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'backend', 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    if 'email' not in session:
        return redirect(url_for('login'))  # Ensure user is logged in

    material = materials_collection.find_one({'filename': filename})

    if not material:
        return "File not found", 404  # Handle missing files

    # Fetch the current user's name from the users collection
    user = mongo.db.users.find_one({"email": session['email']})
    user_name = user['name'] if user and 'name' in user else session['email']  # Use name if available

    # Check if the logged-in user is the uploader
    if material['uploaded_by'] != user_name:
        return "You are not authorized to delete this file", 403  # Prevent unauthorized deletion

    try:
        os.remove(material['filepath'])  # Delete the actual file from storage
    except FileNotFoundError:
        print(f"Warning: {material['filepath']} not found on disk.")

    materials_collection.delete_one({'filename': filename})  # Remove from the database

    return redirect(url_for('study_materials'))

# -------------------- Run App --------------------
if __name__ == '__main__':
    socketio.run(app, debug=True)

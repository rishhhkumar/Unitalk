from flask import Blueprint, render_template, request, url_for, redirect, session, flash, jsonify
from myapp.database import *
from functools import wraps
from myapp import socket
import os
import google.generativeai as genai
from dotenv import load_dotenv
views = Blueprint('views', __name__, static_folder='static', template_folder='templates')
load_dotenv()
GEMINI_API_KEY = os.getenv("API_KEY")


genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}


model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)
@views.route('/translate', methods=["POST"])
def translate():
    """
    Handles translation requests from the chat interface.
    
    Expects:
        - text: The text to be translated.
        - tone: The tone to apply (Formal, Casual, etc.).
        - target_language: The language to translate the text into.
    
    Returns:
        JSON response with the translated text.
    """
    data = request.get_json()
    input_text = data.get('text', '')
    tone = data.get('tone', 'Neutral')
    target_language = data.get('target_language', '')

    if not input_text or not target_language:
        return jsonify({"error": "Missing input text or target language"}), 400

    # Prepare the prompt
    prompt = f"Translate the following text to {target_language} with a {tone} tone:\n\n{input_text} also dont add anything new to it just the output thats it"

    # Send the request to the model
    chat_session = model.start_chat(history=[])
    response = chat_session.send_message(prompt)

    return jsonify({
        "translated_text": response.text
    })
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("views.login"))
        return f(*args, **kwargs)

    return decorated



@views.route("/", methods=["GET", "POST"])
def index():
    """
    Redirects to the login/register page.

    Returns:
        Response: Flask response object.
    """
    return redirect(url_for("views.login"))



@views.route("/register", methods=["GET", "POST"])
def register():
    """
    Handles user registration and password hashing.

    Returns:
        Response: Flask response object.
    """
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        username = request.form["username"].strip().lower()
        password = request.form["password"]

        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("User already exists with that username.")
            return redirect(url_for("views.login"))

        
        new_user = User(username=username, email=email, password=password)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        
        new_chat = Chat(user_id=new_user.id, chat_list=[])
        db.session.add(new_chat)
        db.session.commit()

        flash("Registration successful.")
        return redirect(url_for("views.login"))

    return render_template("auth.html")


@views.route("/login", methods=["GET", "POST"])
def login():
    """
    Handles user login and session creation.

    Returns:
        Response: Flask response object.
    """
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            
            session["user"] = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            }
            return redirect(url_for("views.chat"))
        else:
            flash("Invalid login credentials. Please try again.")
            return redirect(url_for("views.login"))

    return render_template("auth.html")


@views.route("/new-chat", methods=["POST"])
@login_required
def new_chat():
    """
    Creates a new chat room and adds users to the chat list.

    Returns:
        Response: Flask response object.
    """
    user_id = session["user"]["id"]
    new_chat_email = request.form["email"].strip().lower()

    
    if new_chat_email == session["user"]["email"]:
        return redirect(url_for("views.chat"))

   
    recipient_user = User.query.filter_by(email=new_chat_email).first()
    if not recipient_user:
        return redirect(url_for("views.chat"))

    
    existing_chat = Chat.query.filter_by(user_id=user_id).first()
    """if not existing_chat:
        existing_chat = Chat(user_id=user_id, chat_list=[])
        db.session.add(existing_chat)
        db.session.commit()"""

   
    if recipient_user.id not in [user_chat["user_id"] for user_chat in existing_chat.chat_list]:
        
        room_id = str(int(recipient_user.id) + int(user_id))[-4:]

        
        updated_chat_list = existing_chat.chat_list + [{"user_id": recipient_user.id, "room_id": room_id}]
        existing_chat.chat_list = updated_chat_list

        
        existing_chat.save_to_db()

        
        recipient_chat = Chat.query.filter_by(user_id=recipient_user.id).first()
        if not recipient_chat:
            recipient_chat = Chat(user_id=recipient_user.id, chat_list=[])
            db.session.add(recipient_chat)
            db.session.commit()

        
        updated_chat_list = recipient_chat.chat_list + [{"user_id": user_id, "room_id": room_id}]
        recipient_chat.chat_list = updated_chat_list
        recipient_chat.save_to_db()

        
        new_message = Message(room_id=room_id)
        db.session.add(new_message)
        db.session.commit()

    return redirect(url_for("views.chat"))


@views.route("/chat/", methods=["GET", "POST"])
@login_required
def chat():
    """
    Renders the chat interface and displays chat messages.

    Returns:
        Response: Flask response object.
    """
    
    room_id = request.args.get("rid", None)

    
    current_user_id = session["user"]["id"]
    current_user_chats = Chat.query.filter_by(user_id=current_user_id).first()
    chat_list = current_user_chats.chat_list if current_user_chats else []
    data = []

    for chat in chat_list:
        username = User.query.get(chat["user_id"]).username
        is_active = room_id == chat["room_id"]

        try:
            message = Message.query.filter_by(room_id=chat["room_id"]).first()
            last_message = message.messages[-1]
            last_message_content = last_message.content
        except (AttributeError, IndexError):
            last_message_content = "This place is empty. No messages ..."

        data.append({
            "username": username,
            "room_id": chat["room_id"],
            "is_active": is_active,
            "last_message": last_message_content,
        })

    messages = Message.query.filter_by(room_id=room_id).first().messages if room_id else []

    return render_template(
        "chat.html",
        user_data=session["user"],
        room_id=room_id,
        data=data,
        messages=messages,
    )


@views.app_template_filter("ftime")
def ftime(date):
    dt = datetime.fromtimestamp(int(date))
    time_format = "%I:%M %p"  
    formatted_time = dt.strftime(time_format)

    formatted_time += " | " + dt.strftime("%m/%d")
    return formatted_time


@views.route('/visualize')
def visualize():
    """
    TODO: Utilize pandas and matplotlib to analyze the number of users registered to the app.
    Create a chart of the analysis and convert it to base64 encoding for display in the template.

    Returns:
        Response: Flask response object.
    """
    pass


@views.route('/get_name')
def get_name():
    """
    :return: json object with username
    """
    data = {'name': ''}
    if 'username' in session:
        data = {'name': session['username']}

    return jsonify(data)


@views.route('/get_messages')
def get_messages():
    """
    query the database for messages o in a particular room id
    :return: all messages
    """
    pass


@views.route('/leave')
def leave():
    """
    Emits a 'disconnect' event and redirects to the home page.

    Returns:
        Response: Flask response object.
    """
    socket.emit('disconnect')
    return redirect(url_for('views.home'))

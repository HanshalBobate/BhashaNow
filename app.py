# app.py

import random
import string
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_session import Session
import os,secrets
from twilio.rest import Client
import sqlite3
import easyocr
from aksharamukha import transliterate
import base64
import io
from PIL import Image
import numpy as np


app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # change this

@app.before_request
def clear_session_first_time():
    if not hasattr(app, 'session_cleared'):
        session.clear()
        app.session_cleared = True   # ✅ mark done
        print("Sessions were cleared . . .")

# Configure server-side session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
	"name"	TEXT NOT NULL,
	"pref_lang"	TEXT,
	"user_id"	INTEGER NOT NULL UNIQUE,
	"password"	TEXT NOT NULL,
	"email"	TEXT,
	"ri"	INTEGER DEFAULT 5,
    dp TEXT DEFAULT 'https://imgur.com/gallery/default-user-zlzo64g',
	PRIMARY KEY("user_id" AUTOINCREMENT)
    )""")
cursor.execute("""
INSERT OR IGNORE INTO users (name, pref_lang, user_id, password, email, ri)
VALUES ('hanshal', 'en', '001', 'hanshal', 'hanshal@example.com', 9999)
""")
conn.commit()
conn.close()

def get_db_connection():
    conn = sqlite3.connect("database.db")  
    conn.row_factory = sqlite3.Row
    return conn

# --- Utility Functions ---

def generate_strong_password(length=14):
    """Generates a random strong password (simulating an external API call)."""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(characters) for i in range(length))

def simulated_transliteration(text):
    """
    Simulates the simple char-to-Devanagari mapping found in your JavaScript.
    A real implementation would use a proper transliteration library (e.g., Google's transliteration API or a local model).
    """
    if not text:
        return ""
    
    # Simple mapping for demonstration (matches the JS logic roughly)
    char_map = {
        'a':'अ', 'b':'ब', 'c':'क', 'd':'द', 'e':'ए', 'f':'फ', 'g':'ग', 
        'h':'ह', 'i':'इ', 'j':'ज', 'k':'क', 'l':'ल', 'm':'म', 'n':'न', 
        'o':'ओ', 'p':'प', 'q':'क', 'r':'र', 's':'स', 't':'त', 'u':'उ', 
        'v':'व', 'w':'व', 'x':'क्ष', 'y':'य', 'z':'ज़',
        'A':'अ', 'B':'ब', 'C':'क', 'D':'द', 'E':'ए', 'F':'फ', 'G':'ग', 
        'H':'ह', 'I':'इ', 'J':'ज', 'K':'क', 'L':'ल', 'M':'म', 'N':'न', 
        'O':'ओ', 'P':'प', 'Q':'क', 'R':'र', 'S':'स', 'T':'त', 'U':'उ', 
        'V':'व', 'W':'व', 'X':'क्ष', 'Y':'य', 'Z':'ज़'
    }
    
    result = text.split('\n')
    transliterated_lines = []
    
    for line in result:
        transliterated_line = "".join(char_map.get(char, char) for char in line)
        transliterated_lines.append(transliterated_line)
        
    return "\n".join(transliterated_lines)


# --- Frontend Routes (Serving HTML Pages) ---

@app.route('/')
def home():
    print(session)
    if "user" in session:
        return redirect(url_for("hub"))
    return render_template("landing.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["email"]
        password = request.form["password"]
        conn = get_db_connection()
        if username.__contains__('@'):
            user = conn.execute("SELECT * FROM users WHERE email = ? AND password = ?", (username, password)).fetchone()
        else:
            user = conn.execute("SELECT * FROM users WHERE user_id = ? AND password = ?", (username, password)).fetchone()
        conn.close()
        print("------------------------------------------------")
        print("Attempted Login: ", username, password )
        print("------------------------------------------------")
        if user:
            session["user"] = {
                "id": user["user_id"],
                "name": user["name"],
                "pref": user["pref_lang"],
                "dp": user["dp"],
                "email": user["email"],
                "ri": user["ri"]
            }
            flash("Login successful!", "success")
            session["user_id"] = user["user_id"]   # store unique user_id in session
            print("Login successful for: ", session["user"]["name"])
            return redirect(url_for("hub"))
        else:
            flash("Invalid username or password!", "danger")
            return redirect(url_for("login"))
    return render_template("login5.html")

@app.route("/signup", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        print("Creating User . . . ")
        name = request.form.get("fullName")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirmPassword")

        # validations
        if not name or not email or not password:
            flash("Please fill in all required fields", "danger")
            return redirect(url_for("create"))  # apna signup page

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("create"))

        # Example: Save user to DB
        conn = get_db_connection()
        print(name, password,email)
        conn.execute("""
            INSERT OR IGNORE INTO users (name, password, email, ri)
            VALUES (?, ?, ?, ?)
        """, (
            name,  # full name
            password,                     # ⚠️ plain text abhi, prod me hash karna
            email,                        # user_id = email (ya custom id bana)
            5
        ))
        conn.commit()
        conn.close()

        flash("Account created successfully! Please login.", "success")
        return redirect(url_for("login"))
    return render_template('signup.html')

@app.route('/password')
def forgot_password_page():
    return render_template('password.html')

@app.route('/login/passkeyord')
def login_with_passkey():
    return render_template('password.html')
# @app.route('/password')
# def forgot_password_page():
#     return render_template('password.html')

@app.route('/hub')
def hub():
    if "user" not in session:
        flash("Please login first!", "warning")
        return redirect(url_for("login"))

    return render_template("hub.html", user=session["user"])

@app.route('/userprofile')
def profile_page():
    if "user" not in session:
        flash("Please login first!", "warning")
        return redirect(url_for("login"))

    return render_template('userprofile.html', user=session["user"])

@app.route('/camera')
def camera_tool_page():
    if "user" not in session:
        flash("Please login first!", "warning")
        return redirect(url_for("login"))
    return render_template('camera.html', user=session["user"])

@app.route('/text-transliteration')
def text_tool_page():
    return render_template('text-transliteration.html')


# --- API/Backend Endpoints ---

@app.route('/api/transliterate', methods=['POST'])
def api_transliterate():
    data = request.json
    text = data.get('text', '')
    # print("API called successfully!")
    # print(data)
    # In a real app, you would also use the target_script and source_script
    transliterated_text = simulated_transliteration(text)
    
    return jsonify({"success": True, "result": transliterated_text})

# --- Run the App ---
if __name__ == '__main__':
    # Ensure all HTML files are in a 'templates' directory
    # If you run this file, it will tell you if the folder is missing.
    if not os.path.isdir('templates'):
        print("--- ERROR: 'templates' directory not found. ---")
        print("Please create a folder named 'templates' and place all your .html files inside it.")
        exit()
        
    print("--- Flask App Running ---")
    print("Visit http://127.0.0.1:5000/ or http://127.0.0.1:5000/login5.html")
    app.run(debug=True)
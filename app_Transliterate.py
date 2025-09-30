# app.py

import random
import string
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_session import Session
import os,secrets
from twilio.rest import Client
import sqlite3
import base64
import io
from PIL import Image
import numpy as np
import easyocr
from aksharamukha import transliterate
from werkzeug.security import generate_password_hash, check_password_hash
#################################################################################

# === GLOBAL LANGUAGE VARIABLES ===
langfrom = 'english'
langto = 'hindi'

# OCR languages mapping
language_init = {
    'urdu':'ur', 'hindi':'hi','marathi':'hi','nepali':'hi',
    'telugu':'te','kannada':'kn','bengali':'bn','assamese':'bn'
}

# Script mapping for Aksharamukha
languages = {
    "english": "IAST",
    "hindi": "Devanagari",
    "marathi": "Devanagari",
    "nepali": "Devanagari",
    "urdu": "Arabic",
    "telugu": "Telugu",
    "kannada": "Kannada",
    "bengali": "Bengali",
    "assamese": "Bengali"
}

# === TRANSLITERATION FUNCTION ===
def transliterate_text(text, lang_from, lang_to):
    """Transliterate text from one script to another"""
    src_script = languages.get(lang_from.lower())
    tgt_script = languages.get(lang_to.lower())
    if not src_script or not tgt_script:
        return "Language not supported!"
    return transliterate.process(src_script, tgt_script, text)

# === OCR READER (will be initialized dynamically) ===
guest = {
    'name':'Guest',
    'user_id':'99999',
    'ri':0,
    'dp':'https://imgur.com/gallery/default-user-zlzo64g'
}
#################################################################################

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # change this

@app.before_request
def clear_session_first_time():
    if not hasattr(app, 'session_cleared'):
        session.clear()
        app.session_cleared = True   # ✅ mark done

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
    "p1" TEXT,
    "p2" TEXT,
    "p3" TEXT,
	"ri" INTEGER DEFAULT 5,
    dp TEXT DEFAULT 'https://imgur.com/gallery/default-user-zlzo64g',
	PRIMARY KEY("user_id" AUTOINCREMENT)
    )""")
cursor.execute("""
INSERT OR IGNORE INTO users (name, pref_lang, user_id, password, email, p1,p2,p3, ri)
VALUES ('hanshal', 'en', '001', 'hanshal', 'hanshal@example.com', 'a','b','c',9999)
""")
conn.commit()
conn.close()

def get_db_connection():
    conn = sqlite3.connect("database.db")  
    conn.row_factory = sqlite3.Row
    return conn

# --- Utility Functions ---

def chonk(pk):
    return "-".join(pk[i:i+4] for i in range(0, len(pk), 4))

def generate_passkey():
    """
    Generate a secure passkey of length 12 using letters (A-Z, a-z) and digits (0-9).
    """
    length = 12
    alphabet = string.ascii_uppercase + string.digits

    # Make a list of random chars
    pw_chars = [secrets.choice(alphabet) for _ in range(length)]

    # Shuffle in-place
    random.SystemRandom().shuffle(pw_chars)

    # Join back to string
    return ''.join(pw_chars)


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
        # Step 1: fetch user by email or user_id
        if "@" in username:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (username,)).fetchone()
        else:
            user = conn.execute("SELECT * FROM users WHERE user_id = ?", (username,)).fetchone()
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

@app.route('/loginpasskey', methods = ["GET", "POST"])
def passkey_login():
    if request.method == "POST":
        email = request.form.get("email")
        key = request.form.get("passkey")
        key = key[0:4]+key[5:9]+key[10:]
        print(email, key)
        if not email or not key:
            flash("Email and passkey are required", "danger")
            return redirect(url_for("passkey_login"))    
        conn = get_db_connection()
        user = conn.execute("""
            SELECT * FROM users 
            WHERE email = ? AND (p1 = ? OR p2 = ? OR p3 = ?)
        """, (email, key, key, key,)).fetchone()
        conn.close()
        print('userr: ', user)
        if user:
            # save session etc
            session["user_id"] = user["user_id"]
            flash("Login successful!", "success")
            print("Login successful for: ", session["user"]["name"])
            return redirect(url_for("hub"))  # apna dashboard route
        else:
            flash("Invalid email or passkey", "danger")
            print('ula')
            return redirect(url_for("passkey_login"))
    return render_template("passkey_login.html")

@app.route("/create_account", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        print("Creating User . . . ")
        name = request.form.get("fullName")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirmPassword")
        print("Yo",name,email,password)
        # validations
        if not name or not email or not password:
            flash("Please fill in all required fields", "danger")
            return redirect(url_for("create"))  # apna signup page

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("create"))
        conn = get_db_connection()
        check = conn.execute(
            '''SELECT count(email) FROM users WHERE email = ?''', (email,)
        ).fetchone()

        print("\nCheck:", check, "\n")

        if check and check[0] > 0:  # ✅ properly checking count
            flash("This email is already registered.", "danger")
            conn.close()
            return render_template('signup.html')
        # Example: Save user to DB
        p1 = generate_passkey()
        p2 = generate_passkey()
        p3 = generate_passkey()
        conn.execute("""
            INSERT OR IGNORE INTO users (name, password, email, p1,p2,p3,ri)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name,  # full name
            password,                     # ⚠️ plain text abhi, prod me hash karna
            email,                        # user_id = email (ya custom id bana)
            p1,
            p2,
            p3,
            25
        ))
        conn.commit()
        conn.close()

        flash("Account created successfully! Please login.", "success")
        return render_template('generate_passkeys.html', data = {'first': chonk(p1), 'second':chonk(p2), 'third':chonk(p3)})
    return render_template('signup.html')

@app.route('/password')
def forgot_password_page():
    return render_template('password.html', user=session["user"])

@app.route('/hub')
def hub():
    if "user" not in session:
        return render_template("hub.html", user=guest)
    email = session["user"]["email"]
    conn = get_db_connection()
    user = conn.execute("SELECT ri FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if not user:
        ri_count = 0
    else:
        ri_count = user['ri']  # ✅ remaining tokens
    return render_template("hub.html", user=session["user"], tokens = ri_count)

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
        return redirect(url_for("hub"))
    email = session["user"]["email"]
    conn = get_db_connection()
    user = conn.execute("SELECT ri FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("login"))
    ri_count = user['ri']  # ✅ remaining tokens
    return render_template('camera.html', user=session["user"], tokens=ri_count)

@app.route('/text-transliteration')
def text_tool_page():
    return render_template('text-transliteration.html')

# --- API/Backend Endpoints ---
@app.route('/process_image', methods=['POST'])
def process_image():
    try:
        data = request.json
        email = data.get('email')
        image_data = data.get('image')
        lang_from = data.get('langFrom', 'english').lower()
        lang_to = data.get('langTo', 'hindi').lower()
        if not email:
            return jsonify({'error': 'User email required'}), 400
        if not image_data:
            return jsonify({'error': 'No image provided'}), 400
        conn = get_db_connection()
        user = conn.execute(
            "SELECT ri FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        if not user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        row = conn.execute("SELECT ri, email FROM users WHERE email = ?", (email,)).fetchone()
        if dict(row).get('ri',0) <= 0:
            conn.close()
            return jsonify({'error': 'No remaining image processing tokens'})

        # === Deduct 1 token ===
        conn.execute("UPDATE users SET ri = ri - 1 WHERE email = ?", (email,))
        conn.commit()
        conn.close()
        # Decode base64 image
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert PIL image to numpy array for EasyOCR
        img_array = np.array(image)
        
        # Initialize reader for source language
        # ocr_reader = easyocr.Reader(language_init[lang_from].value, gpu = False)
        ocr_lang = language_init.get(lang_from, 'en')
        if ocr_lang == "en":
            ocr_reader = easyocr.Reader([ocr_lang], gpu=False)
        else:
            ocr_reader = easyocr.Reader([ocr_lang, "en"], gpu=False)
        
        # Perform OCR

        results = ocr_reader.readtext(img_array)
        
        # Extract text from OCR results
        extracted_text = ' '.join([text for (bbox, text, prob) in results])
        
        if not extracted_text.strip():
            return jsonify({
                'originalText': '',
                'transliteratedText': 'No text detected in image'
            })
        
        # Transliterate the text
        transliterated = transliterate_text(extracted_text, lang_from, lang_to)
        
        return jsonify({
            'originalText': extracted_text,
            'transliteratedText': transliterated
        })
        
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        conn = get_db_connection()
        conn.execute("UPDATE users SET ri = ri + 1 WHERE email = ?", (email,))
        conn.commit()
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/transliterate', methods=['POST'])
def api_transliterate():
    data = request.json
    text = data.get('text', '')
    lang_from = data.get('langFrom', 'english').lower()
    lang_to = data.get('langTo', 'hindi').lower()
    # In a real app, you would also use the target_script and source_script
    transliterated_text = transliterate_text(text , lang_from, lang_to)
    
    return jsonify({"success": True, "result": transliterated_text})

@app.route("/logout")
def logout():
    """Log out the current user by clearing their session"""
    user_name = session.get("user", {}).get("name", "User")
    session.clear()  # Clear all session data
    flash(f"Goodbye {user_name}! You have been logged out successfully.", "success")
    print(f"User {user_name} logged out")
    return redirect(url_for("home"))


@app.route("/add_tokens", methods=["GET", "POST"])
def add_tokens():
    return render_template("token_purchase_page.html")

# --- Run the App ---
if __name__ == '__main__':
    # Ensure all HTML files are in a 'templates' directory
    # If you run this file, it will tell you if the folder is missing.
    if not os.path.isdir('templates'):
        print("--- ERROR: 'templates' directory not found. ---")
        print("Please create a folder named 'templates' and place all your .html files inside it.")
        exit()
    
    easyocr.Reader(['ur'], gpu = False)
    easyocr.Reader(['hi'], gpu = False)
    easyocr.Reader(['te'], gpu = False)
    easyocr.Reader(['kn'], gpu = False)
    easyocr.Reader(['bn'], gpu = False)
    print("--- Flask App Running ---")
    print("Visit http://127.0.0.1:5000/ ")
    app.run(host="0.0.0.0", debug=True)
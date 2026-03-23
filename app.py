

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from openai import OpenAI
import os
import base64
import random
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super_secret_key"

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "txt"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key="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"
)

# ---------- HELPERS ----------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_chat_history():
    if "chat_history" not in session:
        session["chat_history"] = [
            {"role": "system", "content": "You are a friendly agricultural assistant helping farmers."}
        ]
    return session["chat_history"]
# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    data = request.form
    username = data.get("username")
    password = data.get("password")

    users = load_users()

    if username in users:
        return "User already exists"

    users[username] = password
    save_users(users)

    return redirect(url_for("login_page"))
# ---------- LOGIN ----------
@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if data.get("username") and data.get("password"):
        session["user"] = data["username"]
        return jsonify({"message": "Login successful"})
    return jsonify({"error": "Invalid login"}), 401
# ---------- FORGOT PASSWORD ----------
@app.route("/forgot-password", methods=["GET", "POST"])

def forgot():
    if request.method == "GET":
        return render_template("forgot.html")

    data = request.form
    username = data.get("username")

    users = load_users()

    if username not in users:
        return "User not found"

    users[username] = "newpassword123"  # demo reset
    save_users(users)

    return "Password reset to: newpassword123"

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


# ---------- CHAT PAGE ----------
@app.route("/chat")
def chat_page():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return render_template("index.html")

# ---------- LANGUAGE ----------
@app.route("/set-language", methods=["POST"])
def set_language():
    data = request.json
    session["language"] = data.get("language", "en")
    return jsonify({"status": "ok"})

# ---------- CHAT API ----------
@app.route("/chat-api", methods=["POST"])
def chat_api():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "Please type a message."})

    history = get_chat_history()
    history.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct:hyperbolic",
            messages=history
        )
        reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": reply})
        session["chat_history"] = history
    except Exception as e:
        print("AI ERROR:", e)
        reply = "Server busy 😔 Please try again."

    alerts = []
    if random.choice([True, False]):
        alerts.append("⚠️ Pest alert nearby. Inspect crops today.")

    return jsonify({"reply": reply, "alerts": alerts, "tts_audio": None})

# ---------- WEATHER ----------
@app.route("/weather", methods=["GET"])
def get_weather():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    weather = {
        "city": "Local Farm Area",
        "temperature": "28°C",
        "humidity": "65%",
        "condition": "Partly Cloudy",
        "advice": "Good day for irrigation. Avoid pesticide spraying."
    }

    return jsonify(weather)


# ---------- GOVERNMENT SCHEMES REDIRECT ----------
@app.route("/gov-schemes")
def gov_schemes():
    return redirect("https://pmkisan.gov.in/")

# ---------- CROP CALENDAR ----------
@app.route("/crop-calendar")
def crop_calendar():
    data = {
        "Rabi": ["Wheat", "Mustard", "Barley", "Gram"],
        "Kharif": ["Rice", "Maize", "Cotton", "Soybean"],
        "Zaid": ["Watermelon", "Cucumber", "Vegetables"]
    }
    return jsonify(data)


# ---------- STATE MANDI PRICES ----------

@app.route("/state-prices/<state>")
def state_prices(state):

    # normalize incoming state name
    state = state.lower().replace(" ", "")

    mandi_data = {
        "punjab": {"Wheat": "₹2350/quintal", "Rice": "₹2200/quintal"},
        "haryana": {"Wheat": "₹2320/quintal", "Rice": "₹2180/quintal"},
        "uttarpradesh": {"Wheat": "₹2250/quintal", "Sugarcane": "₹340/quintal"},
        "rajasthan": {"Mustard": "₹5600/quintal", "Wheat": "₹2280/quintal"},
        "madhyapradesh": {"Soybean": "₹4800/quintal", "Wheat": "₹2300/quintal"},
        "maharashtra": {"Cotton": "₹6200/quintal", "Soybean": "₹4900/quintal"},
        "gujarat": {"Cotton": "₹6300/quintal", "Groundnut": "₹5200/quintal"},
        "karnataka": {"Rice": "₹2100/quintal", "Maize": "₹1850/quintal"},
        "tamilnadu": {"Rice": "₹2150/quintal", "Sugarcane": "₹330/quintal"},
        "andhrapradesh": {"Rice": "₹2120/quintal", "Chilli": "₹9000/quintal"},
        "telangana": {"Rice": "₹2100/quintal", "Cotton": "₹6200/quintal"},
        "bihar": {"Rice": "₹2050/quintal", "Wheat": "₹2200/quintal"},
        "westbengal": {"Rice": "₹2080/quintal", "Jute": "₹4500/quintal"}
    }

    if state in mandi_data:
        return jsonify(mandi_data[state])

    return jsonify({"error": f"{state} not found"})

# ---------- UPLOAD ----------
@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    file = request.files.get("file")

    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    os.remove(path)

    return jsonify({"file": {"type": file.mimetype, "content": encoded}})

# ---------- ALERTS ----------
@app.route("/get-alerts")
def get_alerts():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    alerts = ["🌧 Rain expected tomorrow", "🌾 Fertilizer reminder today"]
    return jsonify({"alerts": alerts})

# ---------- DASHBOARD ----------

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login_page"))

    # demo data for charts
    crop_data = [20, 35, 50, 65]
    weather_data = [25, 28, 31, 27]
    price_data = [2200, 2350, 2400, 2300]

    return render_template(
        "dashboard.html",
        crop_data=crop_data,
        weather_data=weather_data,
        price_data=price_data
    )

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)





from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from openai import OpenAI
import os
import base64
from werkzeug.utils import secure_filename
import speech_recognition as sr  # For speech-to-text (pip install SpeechRecognition)
from gtts import gTTS  # For text-to-speech (pip install gTTS)
import io
import requests  # For weather and market APIs
from googletrans import Translator  # For multi-language (pip install googletrans==4.0.0)
import random  # For simulating data
from PIL import Image  # For image validation (pip install Pillow)

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Use a strong, unique secret key; consider env variable

# Configuration for file uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}  # For crop images
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB limit
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# OpenAI client setup (use env variable for API key)
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.getenv("HF_API_KEY", "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"),  # Replace with env variable
)

# Translator for multi-language
translator = Translator()

# In-memory conversation history (per session)
def get_chat_history():
    if 'chat_history' not in session:
        session['chat_history'] = [
            {
                "role": "system",
                "content": (
                    """
You are an intelligent Agricultural Chatbot designed to assist farmers, agricultural students, and rural communities.

Your main goal is to provide accurate, practical, and easy-to-understand agricultural guidance.

You can help with:
- Crop selection based on season, soil type, and climate
- Step-by-step farming practices (sowing, irrigation, fertilization, harvesting)
- Identification and control of pests and diseases
- Organic and chemical fertilizer recommendations (safe and legal)
- Weather-based farming advice
- Information about government agricultural schemes and subsidies (general guidance)
- Modern and sustainable farming techniques
- Basic market price and post-harvest handling tips

Response Style:
- Use simple and clear language suitable for farmers
- Give practical and low-cost solutions first
- Explain steps in bullet points when possible
- Ask follow-up questions if crop, location, or season is not specified
- Avoid complex technical jargon unless necessary
- Be empathetic and human-like: Use phrases like "Don't worry 😊" or "This is common in this season."

Safety Rules:
- Do not provide harmful, illegal, or unsafe chemical dosages
- Do not give medical advice for humans or animals
- Do not guarantee crop yield or profit
- If unsure, recommend consulting a local agricultural expert or officer

Always be polite, helpful, and focused on solving agricultural problems. Remember user context like crop, location, and language.
"""
                )
            }
        ]
    return session['chat_history']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

# Login routes
@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    # TEMP login check (demo purpose) - Replace with real authentication
    if username and password:
        session["user"] = username
        return jsonify({"message": "Login successful"}), 200

    return jsonify({"message": "Invalid credentials"}), 401

@app.route("/chat")
def chat_page():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return render_template("index.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login_page"))

# Dashboard route
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login_page"))
    # Simulated data for dashboard
    crop_data = [10, 20, 30, 40]  # Example growth status
    weather_data = [25, 28, 30, 27]  # Temp over days
    price_data = [50, 55, 60, 58]  # Prices
    return render_template("dashboard.html", crop_data=crop_data, weather_data=weather_data, price_data=price_data)

# Chat route
@app.route("/chat", methods=["POST"])
def chat():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_message = request.json.get("message", "")
    file_data = request.json.get("file", None)
    voice_text = request.json.get("voice_text", "")
    language = session.get("language", data.get("language", "en"))
  # Default to English

    # Combine message and voice
    if voice_text:
        user_message = voice_text if not user_message else f"{user_message} {voice_text}"

    # Translate user message to English for processing
    if language != 'en':
        try:
            user_message = translator.translate(user_message, src=language, dest='en').text
        except Exception as e:
            return jsonify({"error": f"Translation error: {str(e)}"}), 500

    # Get context from session
    crop = session.get('crop')
    stage = session.get('stage')
    location = session.get('location')

    # Add context to message if available
    if not crop or not stage:
        user_message += f" (Context: Crop={crop or 'unknown'}, Stage={stage or 'unknown'}, Location={location or 'unknown'})"

    chat_history = get_chat_history()
    chat_history.append({"role": "user", "content": user_message})

    # Handle file uploads
    if file_data:
        file_type = file_data.get("type")
        file_content = file_data.get("content")
        if file_type.startswith("image/"):
            # Create data URL for the vision model
            image_url = f"data:{file_type};base64,{file_content}"
            chat_history[-1]["content"] += f"\n[Image: {image_url}]"
            # Add specific prompt for crop analysis
            chat_history.append({
                "role": "user",
                "content": (
                    "Analyze this crop image for visible signs of pests, diseases, nutrient deficiencies, or overall plant health. "
                    "Provide practical advice: Identify the issue, suggest organic treatments, prevention tips, and when to consult an expert. "
                    "Keep it simple and farmer-friendly."
                )
            })
        elif file_type in ["application/pdf", "text/plain"]:
            chat_history[-1]["content"] += f"\n[Document: {file_content}]"
            chat_history.append({
                "role": "user",
                "content": "Summarize and explain this agricultural document in simple terms."
            })

    # Fetch weather if location is set
    weather_info = ""
    if location:
        try:
            weather_response = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={os.getenv('OPENWEATHER_API_KEY', 'YOUR_OPENWEATHER_API_KEY')}&units=metric")
            if weather_response.status_code == 200:
                weather_data = weather_response.json()
                temp = weather_data['main']['temp']
                humidity = weather_data['main']['humidity']
                weather_info = f"Current weather in {location}: {temp}°C, Humidity: {humidity}%. Rain expected tomorrow—don’t irrigate today if high humidity."
        except Exception as e:
            weather_info = f"Weather data unavailable: {str(e)}"

    # Simulate market prices
    market_prices = f"Today's mandi prices: Rice ₹{random.randint(20,30)}/kg, Wheat ₹{random.randint(25,35)}/kg. Best to sell in 2 days for higher prices."

    # Simulate soil/satellite data
    soil_data = f"Soil moisture: {random.randint(40,60)}%. Crop stress level: Low (NDVI: 0.7)."

    # Add external data to prompt
    if weather_info or market_prices or soil_data:
        chat_history[-1]["content"] += f"\nWeather: {weather_info}\nMarket: {market_prices}\nSoil: {soil_data}"

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct:hyperbolic",
            messages=chat_history
        )
        assistant_reply = response.choices[0].message.content
    except Exception as e:
        return jsonify({"error": f"AI response error: {str(e)}"}), 500

    # Translate reply to user's language
    if language != 'en':
        try:
            assistant_reply = translator.translate(assistant_reply, src='en', dest=language).text
        except Exception as e:
            return jsonify({"error": f"Translation error: {str(e)}"}), 500

    chat_history.append({"role": "assistant", "content": assistant_reply})
    session['chat_history'] = chat_history

# fteching weather data for location and adding to response 
@app.route("/weather", methods=["GET"])
def get_weather():
    try:
        # Fake weather demo data
        weather_data = {
            "status": "success",
            "city": "Your Area",
            "temperature": "28°C",
            "condition": "Partly Cloudy",
            "humidity": "65%",
            "advice": "Good day for irrigation. Avoid spraying pesticides."
        }

        return jsonify(weather_data)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

    # Generate TTS
    tts_audio = None
    if request.json.get("tts", False):
        try:
            tts = gTTS(text=assistant_reply, lang=language)
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            tts_audio = base64.b64encode(audio_buffer.read()).decode('utf-8')
        except Exception as e:
            tts_audio = None  # TTS failed, but don't break the response

    # Smart alerts (simulate)
    alerts = []
    if random.choice([True, False]):  # Random alert
        alerts.append("Alert: Pest outbreak warning in nearby areas. Check crops today.")

    return jsonify({"reply": assistant_reply, "tts_audio": tts_audio, "alerts": alerts})

# Upload route
@app.route("/upload", methods=["POST"])
def upload_file():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return jsonify({"error": "File too large. Max size is 5MB."}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Validate image if it's an image file
            if allowed_image(filename):
                img = Image.open(filepath)
                img.verify()  # Check if it's a valid image
                img.close()
            
            # Read and encode file
            with open(filepath, 'rb') as f:
                file_content = base64.b64encode(f.read()).decode('utf-8')
            file_type = file.mimetype
            
            # Delete temp file after processing
            os.remove(filepath)
            
            return jsonify({"file": {"type": file_type, "content": file_content}})
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)  # Clean up on error
            return jsonify({"error": f"Invalid file: {str(e)}"}), 400
    return jsonify({"error": "File type not allowed"}), 400

# Speech-to-text route
@app.route("/speech-to-text", methods=["POST"])
def speech_to_text():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    audio_file = request.files.get('audio')
    language = session.get('language', 'en')  # Get language from session
    
    if audio_file:
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(audio_file) as source:
                audio = recognizer.record(source)
            # Set language for recognition (e.g., 'hi-IN' for Hindi India)
            lang_code = language + '-IN' if language != 'en' else 'en-US'
            text = recognizer.recognize_google(audio, language=lang_code)
            return jsonify({"text": text})
        except sr.UnknownValueError:
            return jsonify({"error": "Could not understand audio. Please speak clearly."}), 400
        except sr.RequestError as e:
            return jsonify({"error": f"Speech service error: {e}"}), 500
        except Exception as e:
            return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    return jsonify({"error": "No audio file provided"}), 400

# Set context route
@app.route("/set-context", methods=["POST"])
def set_context():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    session['crop'] = data.get('crop')
    session['stage'] = data.get('stage')
    session['location'] = data.get('location')
    session['language'] = data.get('language', 'en')
    return jsonify({"status": "Context updated"})

# Get alerts route
@app.route("/get-alerts", methods=["GET"])
def get_alerts():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    # Simulate alerts
    alerts = ["Weather alert: Rain tomorrow.", "Fertilizer reminder: Apply nitrogen today."]
    return jsonify({"alerts": alerts})

if __name__ == "__main__":
    app.run(debug=True)








    

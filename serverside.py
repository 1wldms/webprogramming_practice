from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import requests
import json
import openai
import traceback
from dotenv import load_dotenv
import re
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pandas as pd
import datetime as dt
import random
from flask import Flask, render_template, request

def spaced_positions(count, min_gap=3):
    positions = []
    while len(positions) < count:
        candidate = random.randint(5, 95)
        if all(abs(candidate - p) >= min_gap for p in positions):
            positions.append(candidate)
    return positions

app = Flask(__name__)
app.secret_key = "wekfjl`klkAWldI109nAKnooionrg923jnn"
app.jinja_env.globals.update(spaced_positions=spaced_positions)

load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
weather_api_key = os.getenv("WEATHER_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CX = os.getenv("CX_ID")

DB_user = 'user_info.db'

def init_db():
    if os.path.exists(DB_user):
        os.remove(DB_user)

    conn = sqlite3.connect(DB_user)
    cursor = conn.cursor()
    cursor.execute('''
                CREATE TABLE users(
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    gender TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                ''')

    cursor.execute('''
                CREATE TABLE history(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    date TEXT NOT NULL,
                    style TEXT NOT NULL,
                    search_query TEXT NOT NULL,
                    img TEXT NOT NULL,
                    city TEXT NOT NULL,
                    weather_temp TEXT NOT NULL,
                    weather_feels_like TEXT NOT NULL,
                    rain_status TEXT NOT NULL,
                    wind_status TEXT NOT NULL,
                    FOREIGN KEY(username) REFERENCES users(username)
                );
                ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    conn.commit()
    conn.close()

def get_timezone_from_city(city_name):
    try:
        geolocator = Nominatim(user_agent="styleit-app")
        location = geolocator.geocode(city_name)
        if location:
            tf = TimezoneFinder()
            tz_name = tf.timezone_at(lng=location.longitude, lat=location.latitude)
            return tz_name
    except Exception as e:
        print(f"Error finding timezone for {city_name}: {e}")
    return "UTC"  # fallback

def get_weather_info(city):
    lang = 'eng'
    units = 'metric'
    api = f"https://api.openweathermap.org/data/2.5/weather?q={city}&APPID={weather_api_key}&lang={lang}&units={units}"

    try:
        response = requests.get(api)
        weather_data = response.json()
        if response.status_code != 200:
            return None
        return weather_data
    except:
        return None

def parse_weather(weather_data, city):
    temp = weather_data['main']['temp']
    feels_like = weather_data['main']['feels_like']
    temp_max = weather_data['main']['temp_max']
    temp_min = weather_data['main']['temp_min']
    clouds = weather_data['clouds']['all']
    humidity = weather_data['main']['humidity']
    wind_speed = weather_data['wind']['speed']
    description = weather_data['weather'][0]['description']

    cloud_status = ("Clear sky - Blue sky with no clouds at all" if clouds == 0 else
                    "Mostly clear - Mostly sunny with a few clouds" if clouds <= 25 else
                    "Partly cloudy - About half sky covered with clouds" if clouds <= 50 else
                    "Mostly cloudy - Sky is mostly covered by clouds" if clouds <= 84 else
                    "Overcast - Completely covered with thick clouds")

    wind_status = ("Calm - Very light air, hardly noticeable" if wind_speed < 0.3 else
                    "Light air - Feels like still air, leaves unmoving" if wind_speed < 1.6 else
                    "Light breeze - Leaves rustle, wind can be felt on face" if wind_speed < 3.4 else
                    "Gentle breeze - Leaves and small twigs in constant motion" if wind_speed < 5.5 else
                    "Moderate breeze - Moves small branches, raises loose paper" if wind_speed < 8.0 else
                    "Fresh breeze - Small trees sway, wind felt strongly" if wind_speed < 10.8 else
                    "Strong wind - Trees move noticeably, walking against wind is difficult")

    weather_info = f"""Today's weather in {city}:
- Temperature: {temp}°C (feels like {feels_like}°C)
- High: {temp_max}°C, Low: {temp_min}°C
- Condition: {description}
- Cloudiness: {cloud_status}
- Wind: {wind_status}
- Humidity: {humidity}%"""

    notes = []
    main = weather_data['weather'][0]['main'].lower()
    if 'rain' in main or 'snow' in main:
        notes.append("⚠️ It is raining or snowing. Consider waterproof clothing.")
    if wind_speed >= 5.5:
        notes.append("💨 It is windy. Avoid lightweight accessories.")
    if humidity >= 80:
        notes.append("💧 High humidity. Wear breathable clothing.")

    if notes:
        weather_info += "\n\nWeather Advisory:\n" + "\n".join(notes)

    rain = 'rain' in description.lower()
    windy = float(wind_speed) >= 5.5

    rain_status = "🌧️ Rainy" if rain else "☀️ No Rain"
    wind_status_txt = "💨 Windy" if windy else "🍃 Calm"

    return (weather_info, temp, feels_like, temp_max, temp_min,
        cloud_status, humidity, wind_status, description, wind_speed,
        rain_status, wind_status_txt, rain)


def is_night_in(city_timezone):
    tz = pytz.timezone(city_timezone)
    local_time = dt.datetime.now(tz)  # ✅ using dt.datetime
    hour = local_time.hour
    return hour < 6 or hour >= 18, hour


def get_pinterest_images(query, google_api_key, cx_id):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "cx": cx_id,
        "key": google_api_key,
        "searchType": "image",
        "num": 5,
        "safe": "active"
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        return [item["link"] for item in data.get("items", [])]
    except:
        return []

def reply_from_gpt(reply):
    outfit = {}
    lines = reply.split("- ")
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            key_clean = re.sub(r"\*\*", "", key.strip())
            value_clean = re.sub(r"\*\*", "", value.strip())
            outfit[key_clean] = value_clean
    return outfit

def build_search_query(outfit_dict, gender, style):
    outer = outfit_dict.get("Outerwear", "").lower()
    top = outfit_dict.get("Top", "").lower()
    bottom = outfit_dict.get("Bottom", "").lower()

    keywords = []
    for kw in [outer, bottom, top]:
        if kw and kw != "none":
            keywords.append(kw)

    selected = keywords[:2] 

    selected.insert(0, gender)
    selected.append(f"{style} outfit")

    return " ".join(selected)


@app.route('/')
def index():
    isLogin = 'username' in session
    return render_template('mainpage.html', isLogin = isLogin) 


@app.route('/signup', methods = ['GET','POST'])
def signup():  
    if request.method == "POST":
        username = request.form['username']
        password = request.form['pwd']
        gender = request.form['gender']

        with sqlite3.connect(DB_user) as conn:
            cursor = conn.cursor()
            q = "SELECT * FROM users WHERE username = ?"
            cursor.execute(q,(username,))
            user_existing = cursor.fetchone()

            if user_existing:
                flash('Existing ID')
                return render_template('signup.html')
            else:
                q = "INSERT INTO users (username,password,gender) VALUES (?,?,?);"
                cursor.execute(q,(username,password,gender))
                return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/intropage', methods=["GET"])
def intropage():
    return render_template('intropage.html')

@app.route('/login', methods = ["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['pwd']

        with sqlite3.connect(DB_user) as conn:
            cursor = conn.cursor()
            q = "SELECT password FROM users WHERE username = ?;"
            cursor.execute(q, (username,))
            user = cursor.fetchone()

            if user and user[0] == password:
                session['username'] = username
                return redirect(url_for('intropage'))
            else:
                flash("Please check your username of password again.")
                return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/mypage')
def mypage():
    if 'username' not in session:
        flash('Please login.')
        return redirect(url_for('login'))

    username = session['username']

    with sqlite3.connect(DB_user) as conn:
        cursor = conn.cursor()

        q = "SELECT password, gender FROM users WHERE username = ?;"
        cursor.execute(q, (username,))
        user = cursor.fetchone()

        if not user:
            flash('Cannot find user info.')
            return redirect(url_for('signup'))

        password, gender = user

        p = "SELECT date, style, search_query, img, city, weather_temp, weather_feels_like, rain_status, wind_status FROM history WHERE username = ? ORDER BY id DESC;"
        cursor.execute(p, (username,))
        history_data = cursor.fetchall()

    return render_template(
        "mypage.html",
        username = username,
        password = password,
        gender = gender,
        history_data = history_data,
    )


@app.route('/Style-It', methods=["GET"])
def weather_style():
    df = pd.read_csv('cities.csv', header=None)  
    df.columns = ['City'] 
    city_list = sorted(df['City'].dropna().unique())
    return render_template('weather_style.html', cities=city_list)


@app.route('/result', methods=["GET","POST"])
def result():
    city = request.form["city"]
    style = request.form["style"]

    username = session.get('username')
    with sqlite3.connect(DB_user) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT gender FROM users WHERE username = ?;", (username,))
        result = cursor.fetchone()
        gender = result[0] if result else "unspecified"

    weather_data = get_weather_info(city)
    if not weather_data:
        flash("Failed to fetch weather data.")
        return redirect(url_for('weather_style'))

    weather_info, temp, feels_like, temp_max, temp_min, cloud_status, humidity, wind_status, description, wind_speed, rain_status, wind_status_txt, is_raining = parse_weather(weather_data, city)

    tz_name = get_timezone_from_city(city)
    print(f"DEBUG: Timezone from city '{city}' = {tz_name}")
    print(f"DEBUG: Local time = {dt.datetime.now(pytz.timezone(tz_name))}")
    is_night, hour = is_night_in(tz_name)  # <-- this line was missing
    tz = pytz.timezone(tz_name)

    now = dt.datetime.now(tz)
    hour = now.hour


    #gpt prompt 보내기
    try:
        prompt = f"""You are a fashion coordinator who understands weather very well.
    {weather_info}
    I am a {gender} living in {city}, and I prefer a {style} style.

    Based on today's weather conditions, recommend an outfit that is stylish and practical.
    Please respond in the following format (no markdown, no bold):

    - Outerwear: ...
    - Top: ...
    - Bottom: ...
    - Shoes: ...
    - Accessories: ...
    - Additional Consideration: ...

    ⚠️ Important: For each clothing item (Outerwear, Top, Bottom, etc.), respond with a **short, keyword-style description** that can be used as a Pinterest search term. Avoid long sentences or explanations. For example:
    - Outerwear: trench coat
    - Top: cotton t-shirt
    - Shoes: white sneakers

    Please only output one or two words per category. Your answer will be used as image search terms.
    Avoid adjectives like 'comfortable', 'breathable', etc. Just provide item names.
    """

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7,
        )

        gpt_reply = response.choices[0].message.content

    except Exception as e:
        traceback.print_exc()
        gpt_reply = f"GPT ERROR: {str(e)}"

    outfit_dict = reply_from_gpt(gpt_reply)


    search_query = build_search_query(outfit_dict, gender, style)
    image_urls = get_pinterest_images(search_query, GOOGLE_API_KEY, CX)
    search_url = f"https://www.pinterest.com/search/pins/?q={search_query.replace(' ', '+')}"

    current_date_formatted = now.strftime("%B %d, %Y")
    current_month_name = now.strftime("%B")
    current_year = now.year
    current_day = now.day
    datetime_str = now.strftime("%Y-%m-%d %H:%M")

    if username and image_urls:
        with sqlite3.connect(DB_user) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                        INSERT INTO history (
                            username, date, style, search_query, img, city,
                            weather_temp, weather_feels_like, rain_status, wind_status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        ''', (
                        username, datetime_str, style, search_query, image_urls[0], city, 
                        temp, feels_like, rain_status, wind_status_txt
                        ))
    positions = spaced_positions(30)
    return render_template("result.html",positions=positions,
                        city=city,
                        style=style,
                        temp=temp,
                        feels_like=feels_like,
                        temp_max=temp_max,
                        temp_min=temp_min,
                        cloud_status=cloud_status,
                        humidity=humidity,
                        wind_status=wind_status,
                        description=description,
                        gpt_reply=gpt_reply,
                        outfit=outfit_dict,
                        search_url=search_url,
                        image_urls=image_urls,
                        search_query=search_query,
                        current_date=current_date_formatted,
                        current_month=now.month,
                        current_month_name=current_month_name,
                        current_year=current_year,
                        current_day=current_day,
                        is_night=is_night,
                        is_raining=is_raining,
                        hour=hour
                        )


    
@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    name = request.form.get('name')
    content = request.form.get('content')

    if not name or not content:
        return "이름과 내용을 모두 입력해주세요.", 400

    with sqlite3.connect(DB_user) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO feedback (name, content) VALUES (?, ?);", (name, content))
        conn.commit()

    return f"{name}님, 소중한 의견 감사합니다!"

@app.route('/view-users')
def view_users():
    secret = request.args.get("key")
    if secret != "styleit_admin_2025":  
        return "접근 불가: 인증 키가 필요합니다", 403

    try:
        with sqlite3.connect(DB_user) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, gender, created_at FROM users ORDER BY created_at DESC;")
            users = cursor.fetchall()
            cursor.close()

        return render_template("view_users.html", users=users)
    except Exception as e:
        return f"오류 발생: {str(e)}"



@app.route('/view-feedback')
def view_feedback():
    secret = request.args.get("key")
    if secret != "styleit_admin_2025":
        return "접근 거부: 관리자 키가 필요합니다", 403

    with sqlite3.connect(DB_user) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, content, created_at FROM feedback ORDER BY created_at DESC;")
        feedbacks = cursor.fetchall()

    return render_template("feedback_list.html", feedbacks=feedbacks)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=5050, debug=True)


app = Flask(__name__)
"""
╔══════════════════════════════════════════════════════════════════╗
║         ТЕХАСЬКИЙ МЕТОД — ТРЕКЕР ТРЕНУВАНЬ                   ║
║         Версія: Повноекранний контроль + Ручний ввід історії     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import math

# -----------------------------------------------------------------
# КОНСТАНТИ ТА НАЛАШТУВАННЯ
# -----------------------------------------------------------------
DB_PATH = "texas_method_pro.db"

MAIN_EXERCISES = ["Присід", "Жим лежачи", "Станова тяга"]
BACK_EXERCISES = ["Тяга штанги в нахилі", "Підтягування зворотним хватом"]
ABS_EXERCISES = ["Скручування на блоці (Cable Crunch)", "Маятник на турніку"]

TAGS = [
    "—",
    "✅ Пройшло легко",
    "🔥 На межі відмови",
    "🏋️ Завелика вага",
    "🦴 Боліли суглоби",
    "⚡ Біль в попереку",
    "😴 Недосип/Втома"
]

st.set_page_config(page_title="Техаський Метод PRO", page_icon="🏋️", layout="wide")

# Стилізація інтерфейсу під Dark Mode
st.markdown("""
<style>
.stApp { background: linear-gradient(135deg, #0d0f14 0%, #111827 100%); }
.metric-card { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 12px; padding: 15px; text-align: center; margin-bottom: 10px; }
.metric-value { font-size: 1.8rem; font-weight: 800; color: #e85d04; }
.metric-label { font-size: 0.75rem; color: #7c8db0; text-transform: uppercase; letter-spacing: 0.5px; }
.warmup-row { display: flex; justify-content: space-between; padding: 4px 12px; background: #12151f; border-left: 3px solid #e85d04; margin-bottom: 4px; border-radius: 4px;}
.cns-alert { background: #7f1d1d; border: 1px solid #ef4444; border-radius: 8px; padding: 16px; margin: 16px 0; color: #fecaca; }
hr { border-color: #2a2d3e !important; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------
# БАЗА ДАНИХ
# -----------------------------------------------------------------
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise TEXT, day_type TEXT, 
        weight REAL, reps INTEGER, sets INTEGER, tag TEXT, comment TEXT, calculated_1rm REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS friday_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise TEXT, weight REAL, reps INTEGER, calculated_1rm REAL)""")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()

def save_setting(key, value):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()

def load_setting(key, default=""):
    row = get_connection().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default

# -----------------------------------------------------------------
# ЛОГІКА РОЗРАХУНКІВ
# -----------------------------------------------------------------
def calc_1rm_brzycki(weight, reps):
    if reps <= 0: return 0.0
    if reps == 1: return float(weight)
    return float(weight / (1.0278 - (0.0278 * reps)))

def round_to_step(weight, step):
    return math.floor(weight / step) * step if step > 0 else weight

def insert_workout(date_str, exercise, day_type, weight, reps, sets, tag, comment):
    c_1rm = calc_1rm_brzycki(float(weight), int(reps))
    get_connection().execute(
        "INSERT INTO workouts (date, exercise, day_type, weight, reps, sets, tag, comment, calculated_1rm) VALUES (?,?,?,?,?,?,?,?,?)",
        (date_str, exercise, day_type, float(weight), int(reps), int(sets), tag, comment, c_1rm)
    )
    get_connection().commit()

def insert_friday_record(date_str, exercise, weight, reps=5):
    c_1rm = calc_1rm_brzycki(float(weight), int(reps))
    get_connection().execute(
        "INSERT INTO friday_records (date, exercise, weight, reps, calculated_1rm) VALUES (?,?,?,?,?)",
        (date_str, exercise, float(weight), int(reps), c_1rm)
    )
    get_connection().commit()

def get_last_record(exercise):
    res = get_connection().execute(
        "SELECT weight, reps FROM friday_records WHERE exercise=? ORDER BY date DESC, id DESC LIMIT 1", (exercise,)
    ).fetchone()
    return res if res else (50.0, 5)

def check_day_completed(date_str):
    res = get_connection().execute("SELECT count(*) FROM workouts WHERE date=?", (date_str,)).fetchone()
    return res[0] > 0

def calc_warmup(working_weight, step):
    return [
        {"label": "Гриф", "weight": 20.0, "reps": 10},
        {"label": "50%", "weight": round_to_step(working_weight * 0.50, step), "reps": 5},
        {"label": "70%", "weight": round_to_step(working_weight * 0.70, step), "reps": 3},
        {"label": "90%", "weight": round_to_step(working_weight * 0.90, step), "reps": 1},
    ]

def check_cns():
    rows = get_connection().execute(
        "SELECT tag FROM workouts WHERE tag IS NOT NULL AND tag != '—' ORDER BY date DESC, id DESC LIMIT 10"
    ).fetchall()
    tags = [r[0] for r in rows]
    if "⚡ Біль в попереку" in tags:
        return True, "Виявлено тег «Біль в попереку». Зверни особливу увагу на техніку зриву в становій тязі та кут нахилу в присіданнях!"
    if "🦴 Боліли суглоби" in tags:
        return True, "Виявлено тег «Боліли суглоби». Рекомендується запланувати легкий тиждень (Делоад)."
    if len(tags) >= 3 and all("На межі відмови" in t for t in tags[:3]):
        return True, "Три підходи/вправи поспіль пройшли на межі відмови. ЦНС перевантажена!"
    return False, ""

# -----------------------------------------------------------------
# ГОЛОВНИЙ ІНТЕРФЕЙС
# -----------------------------------------------------------------
def main():
    init_db()
    st.title("🏋️ Техаський Метод PRO")
    
    cns_warn, msg = check_cns()

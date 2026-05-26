"""
╔══════════════════════════════════════════════════════════════════╗
║         ТЕХАСЬКИЙ МЕТОД PRO — ТРЕКЕР ТРЕНУВАНЬ                   ║
║         Streamlit + SQLite | Dark Mode Ready                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date
import math
import io

# -----------------------------------------------------------------
# КОНСТАНТИ ТА НАЛАШТУВАННЯ
# -----------------------------------------------------------------
DB_PATH = "texas_method_pro.db"

MAIN_EXERCISES = ["Присід", "Жим лежачи", "Станова тяга"]
BACK_EXERCISES = ["Тяга штанги в нахилі", "Підтягування зворотним хватом"]
ABS_EXERCISES = ["Скручування на блоці (Cable Crunch)", "Маятник на турніку"]

ALL_EXERCISES = MAIN_EXERCISES + BACK_EXERCISES + ABS_EXERCISES

TAGS = [
    "✅ Пройшло легко",
    "🔥 На межі відмови",
    "🦴 Боліли суглоби",
    "😴 Недосип/Втома"
]

st.set_page_config(page_title="Техаський Метод PRO", page_icon="🏋️", layout="wide")

# CSS для стилізації (Dark Mode)
st.markdown("""
<style>
.stApp { background: linear-gradient(135deg, #0d0f14 0%, #111827 100%); }
.metric-card { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 12px; padding: 20px; text-align: center; }
.metric-value { font-size: 2rem; font-weight: 800; color: #e85d04; }
.metric-label { font-size: 0.8rem; color: #7c8db0; text-transform: uppercase; }
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
        weight REAL, reps INTEGER, sets INTEGER, tag TEXT, comment TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS friday_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise TEXT, weight REAL, reps INTEGER)""")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()

def save_setting(key, value):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()

def load_setting(key, default=""):
    row = get_connection().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default

def insert_workout(date_str, exercise, day_type, weight, reps, sets, tag, comment):
    get_connection().execute(
        "INSERT INTO workouts (date, exercise, day_type, weight, reps, sets, tag, comment) VALUES (?,?,?,?,?,?,?,?)",
        (date_str, exercise, day_type, float(weight), int(reps), int(sets), tag, comment)
    )
    get_connection().commit()

def insert_friday_record(date_str, exercise, weight, reps=5):
    get_connection().execute(
        "INSERT INTO friday_records (date, exercise, weight, reps) VALUES (?,?,?,?)",
        (date_str, exercise, float(weight), int(reps))
    )
    get_connection().commit()

def get_last_record(exercise):
    res = get_connection().execute(
        "SELECT weight, reps FROM friday_records WHERE exercise=? ORDER BY date DESC LIMIT 1", (exercise,)
    ).fetchone()
    return res if res else (50.0, 5)

def check_day_completed(date_str):
    res = get_connection().execute("SELECT count(*) FROM workouts WHERE date=?", (date_str,)).fetchone()
    return res[0] > 0

# -----------------------------------------------------------------
# ЛОГІКА ТА ФОРМУЛИ
# -----------------------------------------------------------------
def calc_1rm_brzycki(weight, reps):
    if reps <= 0: return 0.0
    if reps == 1: return float(weight)
    den = 1.0278 - (0.0278 * reps)
    return weight / den if den > 0 else float(weight)

def round_to_step(weight, step):
    return math.floor(weight / step) * step if step > 0 else weight

def calc_warmup(working_weight, step):
    return [
        {"label": "Гриф", "weight": 20.0, "reps": 10},
        {"label": "50%", "weight": round_to_step(working_weight * 0.50, step), "reps": 5},
        {"label": "70%", "weight": round_to_step(working_weight * 0.70, step), "reps": 3},
        {"label": "90%", "weight": round_to_step(working_weight * 0.90, step), "reps": 1},
    ]

def get_estimated_total():
    sq = calc_1rm_brzycki(*get_last_record("Присід"))
    bp = calc_1rm_brzycki(*get_last_record("Жим лежачи"))
    dl = calc_1rm_brzycki(*get_last_record("Станова тяга"))
    return sq + bp + dl

def check_cns():
    rows = get_connection().execute(
        "SELECT tag FROM workouts WHERE tag IS NOT NULL ORDER BY date DESC, id DESC LIMIT 5"
    ).fetchall()
    tags = [r[0] for r in rows]
    if "🦴 Боліли суглоби" in tags:
        return True, "Виявлено тег «Боліли суглоби». Зроби Делоад!"
    if len(tags) >= 3 and all("На межі відмови" in t for t in tags[:3]):
        return True, "3 тренування поспіль на межі відмови. ЦНС перевантажена!"
    return False, ""

# -----------------------------------------------------------------
# ІНТЕРФЕЙС
# -----------------------------------------------------------------
def main():
    init_db()
    st.title("🏋️ Техаський Метод PRO")
    
    # Вивід алертів ЦНС глобально
    cns_warn, msg = check_cns()
    if cns_warn:
        st.markdown(f'<div class="cns-alert">⚠️ <b>УВАГА:</b> {msg}</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚙️ Налаштування & 1RM", "📅 Календар", "📝 Планування", "📓 Журнал", "📈 Аналітика & Дані"
    ])

    step_val = float(load_setting("step", "2.5"))

    # ================== ТАБ 1: НАЛАШТУВАННЯ ==================
    with tab1:
        st.subheader("⚙️ Налаштування")
        col1, col2 = st.columns(2)
        with col1:
            step_opts = [1.0, 2.5, 5.0]
            new_step = st.selectbox("Крок блінів у залі (кг)", step_opts, index=step_opts.index(step_val))
            if new_step != step_val:
                save_setting("step", str(new_step))
                st.rerun()
        
        st.markdown("---")
        st.subheader("🔢 Калькулятор 1RM та Тотал")
        c1, c2, c3 = st.columns(3)
        with c1:
            w_in = st.number_input("Вага", value=100.0, step=new_step)
            r_in = st.number_input("Повторень", value=5, min_value=1)
            st.info(f"**Розрахунковий 1RM:** {calc_1rm_brzycki(w_in, r_in):.1f} кг")
        with c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{get_estimated_total():.1f} кг</div>
                <div class="metric-label">Орієнтовний Тотал (П+Ж+Т)</div>
            </div>
            """, unsafe_allow_html=True)

    # ================== ТАБ 2: КАЛЕНДАР ==================
    with tab2:
        st.subheader("📅 Календар тренувань")
        selected_date = st.date_input("Обери дату", date.today())
        wd = selected_date.weekday()
        
        is_done = check_day_completed(str(selected_date))
        if is_done:
            st.success(f"✅ Тренування за {selected_date.strftime('%d.%m.%Y')} вже успішно виконано та збережено!")
        
        if wd == 0:
            st.info("🗓️ **Понеділок — Об'ємний день**\n- Присід (5х5) — 85%\n- Жим лежачи (5х5) — 85%\n- Спина (3 підходи)\n- Прес (3 підходи)")
        elif wd == 2:
            st.info("🗓️ **Середа — День відновлення**\n- Присід (3х5) — 70%\n- Жим лежачи (3х5) — 70%\n- Спина легка (3 підходи)\n- Прес (3 підходи)")
        elif wd == 4:
            st.warning("🗓️ **П'ятниця — Інтенсивний день (РЕКОРДИ)**\n- Присід (1х5) — Максимум\n- Жим лежачи (1х5) — Максимум\n- Станова тяга (1х5) — Максимум\n- Прес (3 підходи)")
        else:
            st.write("😴 Сьогодні день відпочинку. Їж і спи!")

    # ================== ТАБ 3: ПЛАНУВАННЯ ==================
    with tab3:
        sub_mon, sub_wed, sub_fri = st.tabs(["🟢 Понеділок (Об'єм)", "🟡 Середа (Відновлення)", "🔴 П'ятниця (Інтенсивність)"])
        
        # Функція для рендеру базової вправи
        def render_base_ex(ex_name, perc, sets, reps, step, is_record=False):
            last_w, last_r = get_last_record(ex_name)
            target_w = round_to_step(last_w * perc, step) if not is_record else last_w + step
            
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.markdown(f"**{ex_name}** | План: {sets}x{reps}")
                act_w = st.number_input(f"Вага ({ex_name})", value=float(target_w), step=step, key=f"w_{ex_name}_{perc}")
            with col_b:
                act_r = st.number_input(f"Повт. ({ex_name})", value=reps, key=f"r_{ex_name}_{perc}")
            
            with st.expander("Розминка"):
                for w in calc_warmup(act_w, step):
                    st.markdown(f'<div class="warmup-row"><span>{w["label"]}</span><b>{w["weight"]} кг x {w["reps"]}</b></div>', unsafe_allow_html=True)
            return act_w, act_r, sets

        # ПОНЕДІЛОК
        with sub_mon:
            st.subheader("Базові вправи (85%)")
            sq_m = render_base_ex("Присід", 0.85, 5, 5, step_val)
            bp_m = render_base_ex("Жим лежачи", 0.85, 5, 5, step_val)
            
            st.subheader("Підсобка")
            back_ex_m = st.selectbox("Вправа на спину", BACK_EXERCISES, key="back_m")
            bw_m = st.number_input("Вага (Спина)", value=0.0, step=step_val, key="bw_m")
            br_m = st.number_input("Повторень (Спина)", value=8, key="br_m")
            
            abs_ex_m = st.selectbox("Вправа на прес", ABS_EXERCISES, key="abs_m")
            aw_m = st.number_input("Вага (Прес)", value=0.0, step=step_val, key="aw_m")
            ar_m = st.number_input("Повторень (Прес)", value=12, key="ar_m")
            
            tag_m = st.selectbox("Статус/Тег", ["—"] + TAGS, key="tag_m")
            
            if st.button("💾 Зберегти Понеділок", use_container_width=True):
                d = str(date.today())
                insert_workout(d, "Присід", "Понеділок", sq_m[0], sq_m[1], sq_m[2], tag_m, "")
                insert_workout(d, "Жим лежачи", "Понеділок", bp_m[0], bp_m[1], bp_m[2], tag_m, "")
                insert_workout(d, back_ex_m, "Понеділок", bw_m, br_m, 3, tag_m, "")
                insert_workout(d, abs_ex_m, "Понеділок", aw_m, ar_m, 3, tag_m, "")
                st.success("✅ Збережено!")

        # СЕРЕДА
        with sub_wed:
            st.subheader("Базові вправи (70% - Легко)")
            sq_w = render_base_ex("Присід", 0.70, 3, 5, step_val)
            bp_w = render_base_ex("Жим лежачи", 0.70, 3, 5, step_val)
            
            st.subheader("Підсобка")
            back_ex_w = st.selectbox("Вправа на спину", BACK_EXERCISES, key="back_w")
            bw_w = st.number_input("Вага (Спина)", value=0.0, step=step_val, key="bw_w")
            br_w = st.number_input("Повторень (Спина)", value=8, key="br_w")
            
            abs_ex_w = st.selectbox("Вправа на прес", ABS_EXERCISES, key="abs_w")
            aw_w = st.number_input("Вага (Прес)", value=0.0, step=step_val, key="aw_w")
            ar_w = st.number_input("Повторень (Прес)", value=12, key="ar_w")
            
            tag_w = st.selectbox("Статус/Тег", ["—"] + TAGS, key="tag_w")
            
            if st.button("💾 Зберегти Середу", use_container_width=True):
                d = str(date.today())
                insert_workout(d, "Присід", "Середа", sq_w[0], sq_w[1], sq_w[2], tag_w, "")
                insert_workout(d, "Жим лежачи", "Середа", bp_w[0], bp_w[1], bp_w[2], tag_w, "")
                insert_workout(d, back_ex_w, "Середа", bw_w, br_w, 3, tag_w, "")
                insert_workout(d, abs_ex_w, "Середа", aw_w, ar_w, 3, tag_w, "")
                st.success("✅ Збережено!")

        # П'ЯТНИЦЯ
        with sub_fri:
            st.subheader("🔥 РЕКОРДИ (1х5)")
            st.info("Ці ваги стануть базою для розрахунку наступного тижня.")
            sq_f = render_base_ex("Присід", 1.0, 1, 5, step_val, is_record=True)
            bp_f = render_base_ex("Жим лежачи", 1.0, 1, 5, step_val, is_record=True)
            dl_f = render_base_ex("Станова тяга", 1.0, 1, 5, step_val, is_record=True)
            
            st.subheader("Підсобка")
            abs_ex_f = st.selectbox("Вправа на прес", ABS_EXERCISES, key="abs_f")
            aw_f = st.number_input("Вага (Прес)", value=0.0, step=step_val, key="aw_f")
            ar_f = st.number_input("Повторень (Прес)", value=12, key="ar_f")
            
            tag_f = st.selectbox("Статус/Тег", ["—"] + TAGS, key="tag_f")
            
            if st.button("💾 Зберегти П'ятницю та Оновити Рекорди", use_container_width=True):
                d = str(date.today())
                # Зберігаємо в загальний журнал
                for ex, data in [("Присід", sq_f), ("Жим лежачи", bp_f), ("Станова тяга", dl_f)]:
                    insert_workout(d, ex, "П'ятниця", data[0], data[1], data[2], tag_f, "")
                    # Оновлюємо таблицю рекордів
                    insert_friday_record(d, ex, data[0], data[1])
                
                insert_workout(d, abs_ex_f, "П'ятниця", aw_f, ar_f, 3, tag_f, "")
                st.success("✅ Рекорди зафіксовано! Наступний тиждень перераховано.")

    # ================== ТАБ 4: ЖУРНАЛ ==================
    with tab4:
        st.subheader("📓 Історія тренувань")
        df_log = pd.read_sql_query("SELECT date as Дата, exercise as Вправа, day_type as День, weight as Вага, reps as Повт, sets as Підходи, tag as Тег FROM workouts ORDER BY id DESC", get_connection())
        st.dataframe(df_log, use_container_width=True, hide_index=True)

    # ================== ТАБ 5: АНАЛІТИКА & ЕКСПОРТ ==================
    with tab5:
        st.subheader("📈 Динаміка 1RM")
        df_charts = pd.read_sql_query("SELECT date, exercise, weight, reps FROM friday_records", get_connection())
        
        if not df_charts.empty:
            df_charts["1RM"] = df_charts.apply(lambda r: calc_1rm_brzycki(r["weight"], r["reps"]), axis=1)
            fig = px.line(df_charts, x="date", y="1RM", color="exercise", markers=True, title="Зростання сили (1RM) по П'ятницях")
            fig.update_layout(paper_bgcolor="#111827", plot_bgcolor="#1a1d27", font=dict(color="#94a3b8"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Немає даних для графіка. Збережи першу П'ятницю!")

        st.markdown("---")
        st.subheader("💾 Резервне копіювання (Streamlit Cloud Safe)")
        col_ex, col_im = st.columns(2)
        
        with col_ex:
            st.write("**Експорт бази**")
            csv_export = pd.read_sql_query("SELECT * FROM workouts", get_connection()).to_csv(index=False)
            st.download_button("⬇️ Завантажити журнал у CSV", csv_export, "texas_backup.csv", "text/csv")
            
        with col_im:
            st.write("**Імпорт бази (Відновлення)**")
            uploaded_file = st.file_uploader("Завантаж CSV файл", type=["csv"])
            if uploaded_file is not None and st.button("🔄 Відновити дані"):
                try:
                    df_import = pd.read_csv(uploaded_file)
                    df_import.to_sql("workouts", get_connection(), if_exists="append", index=False)
                    st.success("Дані успішно відновлено!")
                except Exception as e:
                    st.error(f"Помилка імпорту: {e}")

if __name__ == "__main__":
    main()

"""
╔══════════════════════════════════════════════════════════════════╗
║          ТЕХАСЬКИЙ МЕТОД — ТРЕКЕР ТРЕНУВАНЬ                      ║
║          Версія: Повноекранний контроль вправ та підходів        ║
╚══════════════════════════════════════════════════════════════════╝
"""
from gspread_dataframe import set_with_dataframe
import gspread
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

SET_FEELINGS = [
    "—",
    "🟢 Легко (Запас 3+)",
    "🟡 Нормально (Запас 1-2)",
    "🟠 Важко (Впритул)",
    "💀 Майже здох (Відмова)"
]

st.set_page_config(page_title="Техаський Метод PRO", page_icon="🏋️", layout="wide")

def sync_to_gsheets():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds_dict)
        
        sh = gc.open("TexasMethodDB") 
        worksheet = sh.get_worksheet(0)
        
        df = pd.read_sql_query("SELECT * FROM workouts ORDER BY date DESC", get_connection())
        
        # ЗАХИСТ: Не даємо очистити хмару, якщо локальна БД порожня
        if df.empty:
            st.error("❌ Локальна база даних порожня! Синхронізацію скасовано, щоб не стерти хмару.")
            return

        worksheet.clear()
        set_with_dataframe(worksheet, df)
        st.success("✅ Хмара успішно оновлена поточними даними!")
    except Exception as e:
        st.error(f"❌ Помилка синхронізації: {e}")

def pull_from_gsheets():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds_dict)
        
        sh = gc.open("TexasMethodDB") 
        worksheet = sh.get_worksheet(0)
        
        # Читаємо всі дані з Google Sheets
        data = worksheet.get_all_records()
        if not data:
            st.warning("📭 Гугл-таблиця порожня. Немає чого завантажувати.")
            return
            
        df_cloud = pd.DataFrame(data)
        
        # Перезаписуємо локальну таблицю workouts
        conn = get_connection()
        conn.execute("DELETE FROM workouts")  # Очищаємо поточний локальний пустиш
        df_cloud.to_sql("workouts", conn, if_exists="append", index=False)
        
        st.success("🚀 Дані успішно відновлені з Google Sheets у локальну базу!")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Помилка завантаження даних: {e}")

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
# БАЗА ДАНИХ ТА МІГРАЦІЇ
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
    
    try:
        c.execute("ALTER TABLE workouts ADD COLUMN set_num INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE workouts ADD COLUMN set_feeling TEXT DEFAULT '—'")
    except sqlite3.OperationalError:
        pass

    c.execute("""CREATE TABLE IF NOT EXISTS friday_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise TEXT, weight REAL, reps INTEGER, calculated_1rm REAL)""")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()

    # 💊 АВТО-ФІКС ІСТОРІЇ: лікуємо криві значення 1ПМ (де замість точки збереглося казна-що)
    c.execute("SELECT id, weight, reps FROM workouts WHERE calculated_1rm > 1000")
    corrupted_rows = c.fetchall()
    if corrupted_rows:
        for row_id, w, r in corrupted_rows:
            if r > 0:
                # Рахуємо нормальний float за Бжицькі
                correct_1rm = float(w) if r == 1 else float(w / (1.0278 - (0.0278 * r)))
                c.execute("UPDATE workouts SET calculated_1rm = ? WHERE id = ?", (correct_1rm, row_id))
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

def insert_workout(date_str, exercise, day_type, weight, reps, sets, tag, comment, set_num=1, set_feeling="—"):
    c_1rm = calc_1rm_brzycki(float(weight), int(reps))
    get_connection().execute(
        "INSERT INTO workouts (date, exercise, day_type, weight, reps, sets, tag, comment, calculated_1rm, set_num, set_feeling) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (date_str, exercise, day_type, float(weight), int(reps), int(sets), tag, comment, c_1rm, int(set_num), set_feeling)
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
    # 1. Спочатку шукаємо в таблиці чистих рекорді П'ятниці
    res = get_connection().execute(
        "SELECT weight, reps FROM friday_records WHERE exercise=? ORDER BY date DESC, id DESC LIMIT 1", (exercise,)
    ).fetchone()
    if res:
        return res
        
    # 2. Фолбек: якщо рекорди порожні, шукаємо останню робочу вагу в workouts (наприклад, з Журналу чи Понеділка)
    res_workout = get_connection().execute(
        "SELECT weight, reps FROM workouts WHERE exercise=? ORDER BY date DESC, id DESC LIMIT 1", (exercise,)
    ).fetchone()
    
    return res_workout if res_workout else (50.0, 5)

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
        return True, "Виявлено тег «Біль в попереку». Зверни особливу увагу на техніку зриву в становій тязі та кут нахилу в присіданнях. Охолоди робочі ваги або візьми додатковий день відпочинку!"
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
    if cns_warn:
        st.markdown(f'<div class="cns-alert">⚠️ <b>АНАЛІЗ ЦНС ТА ТЕХНІКИ:</b> {msg}</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚙️ Налаштування & Калькулятори", "📅 Календар", "📝 Планування", "📓 Журнал", "📈 Analytics & Data"
    ])

    step_val = float(load_setting("step", "2.5"))

    # ================== ТАБ 1: НАЛАШТУВАННЯ ТА КАЛЬКУЛЯТОРИ ==================
    with tab1:
        st.subheader("⚙️ Базові налаштування")
        step_opts = [1.0, 2.5, 5.0]
        new_step = st.selectbox("Крок округлення ваги у вашому залі (кг)", step_opts, index=step_opts.index(step_val))
        if new_step != step_val:
            save_setting("step", str(new_step))
            st.rerun()
            
        st.markdown("---")
        
        f_sq_w, f_sq_r = get_last_record("Присід")
        f_bp_w, f_bp_r = get_last_record("Жим лежачи")
        f_dl_w, f_dl_r = get_last_record("Станова тяга")
        
        f_sq_1rm = calc_1rm_brzycki(f_sq_w, f_sq_r)
        f_bp_1rm = calc_1rm_brzycki(f_bp_w, f_bp_r)
        f_dl_1rm = calc_1rm_brzycki(f_dl_w, f_dl_r)
        friday_total = f_sq_1rm + f_bp_1rm + f_dl_1rm
        
        st.subheader("🏆 Поточні максимуми (Остання робоча вага)")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Поточний 1ПМ Присід", f"{f_sq_1rm:.1f} кг", f"База: {f_sq_w}кг х {f_sq_r}")
        with c2: st.metric("Поточний 1ПМ Жим", f"{f_bp_1rm:.1f} кг", f"База: {f_bp_w}кг х {f_bp_r}")
        with c3: st.metric("Поточний 1ПМ Тяга", f"{f_dl_1rm:.1f} кг", f"База: {f_dl_w}кг х {f_dl_r}")
        with c4:
            st.markdown(f"""
            <div class="metric-card" style="border-color: #e85d04;">
                <div class="metric-value">{friday_total:.1f} кг</div>
                <div class="metric-label">Поточний Тотал (Сума 1ПМ)</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("---")
        st.subheader("🔢 Інтерактивний калькулятор 1ПМ та Тоталу")
        
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            st.markdown("**🏋️ Калькулятор: Присід**")
            c_sq_w = st.number_input("Вага штанги (Присід)", value=float(f_sq_w), step=step_val, key="c_sq_w")
            c_sq_r = st.number_input("Повторення (Присід)", value=int(f_sq_r), min_value=1, key="c_sq_r")
            res_sq_1rm = calc_1rm_brzycki(c_sq_w, c_sq_r)
            st.info(f"1ПМ Присід: **{res_sq_1rm:.1f} кг**")
        with cc2:
            st.markdown("**🏋️ Калькулятор: Жим**")
            c_bp_w = st.number_input("Вага штанги (Жим)", value=float(f_bp_w), step=step_val, key="c_bp_w")
            c_bp_r = st.number_input("Повторення (Жим)", value=int(f_bp_r), min_value=1, key="c_bp_r")
            res_bp_1rm = calc_1rm_brzycki(c_bp_w, c_bp_r)
            st.info(f"1ПМ Жим: **{res_bp_1rm:.1f} кг**")
        with cc3:
            st.markdown("**🏋️ Калькулятор: Тяга**")
            c_dl_w = st.number_input("Вага штанги (Тяга)", value=float(f_dl_w), step=step_val, key="c_dl_w")
            c_dl_r = st.number_input("Повторення (Тяга)", value=int(f_dl_r), min_value=1, key="c_dl_r")
            res_dl_1rm = calc_1rm_brzycki(c_dl_w, c_dl_r)
            st.info(f"1ПМ Тяга: **{res_dl_1rm:.1f} кг**")
            
        calc_total = res_sq_1rm + res_bp_1rm + res_dl_1rm
        st.markdown(f"""
        <div class="metric-card" style="background: #1e293b; max-width: 400px; margin: 15px 0;">
            <div class="metric-value" style="color: #38bdf8;">{calc_total:.1f} кг</div>
            <div class="metric-label">Тотал за калькулятором (Сума 1ПМ)</div>
        </div>
        """, unsafe_allow_html=True)

    # ================== ТАБ 2: КАЛЕНДАР ==================
    with tab2:
        st.subheader("📅 Інтерактивний календар дати")
        selected_date = st.date_input("Оберіть дату тренування", date.today())
        wd = selected_date.weekday()
        
        if check_day_completed(str(selected_date)):
            st.success(f"✅ Тренування за {selected_date.strftime('%d.%m.%Y')} вже внесено та збережено!")
        
        if wd == 0:
            st.info(f"🗓️ **Понеділок — Об'єм**\n- Присід: 5х5 ({round_to_step(f_sq_w*0.85, step_val)} кг)\n- Жим лежачи: 5х5 ({round_to_step(f_bp_w*0.85, step_val)} кг)")
        elif wd == 2:
            st.info(f"🗓️ **Середа — Відновлення**\n- Присід: 3х5 ({round_to_step(f_sq_w*0.70, step_val)} кг)\n- Жим лежачи: 3х5 ({round_to_step(f_bp_w*0.70, step_val)} кг)")
        elif wd == 4:
            st.warning("🗓️ **П'ятниця — Інтенсивність (РЕКОРДИ)**\n- Присід: 1х5\n- Жим лежачи: 1х5\n- Станова тяга: 1х5")
        else:
            st.write("😴 День відпочинку та анаболізму.")

    # ================== ТАБ 3: ПЛАНУВАННЯ ТРЕНУВАНЬ ==================
    with tab3:
        sub_mon, sub_wed, sub_fri = st.tabs(["🟢 Понеділок (Об'єм)", "🟡 Середа (Відновлення)", "🔴 П'ятниця (Інтенсивність)"])
        
        def render_base_ex(ex_name, perc, sets, reps, step, is_record=False):
            last_w, last_r = get_last_record(ex_name)
            target_w = round_to_step(last_w * perc, step) if not is_record else last_w + step
            
            st.markdown(f"##### {ex_name} (План: {sets}x{reps})")
            ex_tag = st.selectbox(f"Загальний стан для {ex_name}", TAGS, key=f"tag_{ex_name}_{perc}")
            
            sets_data = []
            with st.expander(f"⚙️ Деталізація підходів ({sets} підх.)", expanded=True):
                for s in range(1, sets + 1):
                    col_w, col_r, col_f = st.columns([2, 1.5, 2])
                    with col_w:
                        s_w = st.number_input(f"Підхід {s}: Вага (кг)", value=float(target_w), step=step, key=f"w_{ex_name}_{perc}_s{s}")
                    with col_r:
                        s_r = st.number_input(f"Підхід {s}: Повтори", value=reps, min_value=1, key=f"r_{ex_name}_{perc}_s{s}")
                    with col_f:
                        s_f = st.selectbox(f"Підхід {s}: Відчуття", SET_FEELINGS, key=f"feel_{ex_name}_{perc}_s{s}")
                    sets_data.append((s_w, s_r, s_f))
            
            with st.expander("Розминка (орієнтовна)"):
                warmup_base = sets_data[0][0] if sets_data else target_w
                for w in calc_warmup(warmup_base, step):
                    st.markdown(f'<div class="warmup-row"><span>{w["label"]}</span><b>{w["weight"]} кг x {w["reps"]}</b></div>', unsafe_allow_html=True)
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            return sets_data, ex_tag

        # ПОНЕДІЛОК (ОБ'ЄМ)
        with sub_mon:
            st.subheader("Базовий об'єм (85%)")
            sq_m_sets, sq_m_tag = render_base_ex("Присід", 0.85, 5, 5, step_val)
            bp_m_sets, bp_m_tag = render_base_ex("Жим лежачи", 0.85, 5, 5, step_val)
            
            st.subheader("Додаткові вправи (Підсобка)")
            back_ex_m = st.selectbox("Спина (Понеділок)", BACK_EXERCISES, key="back_m")
            bs_m = st.number_input("Кількість підходів (Спина, Пн)", value=3, min_value=1, key="bs_m_count")
            
            back_m_sets_data = []
            with st.expander(f"🔩 Підходи для Спини ({bs_m} підх.)", expanded=True):
                for s in range(1, int(bs_m) + 1):
                    col1, col2, col3 = st.columns([2, 1.5, 2])
                    with col1:
                        bw = st.number_input(f"Спина Пд {s}: Вага", value=0.0, step=step_val, key=f"bw_m_s{s}")
                    with col2:
                        br = st.number_input(f"Спина Пд {s}: Повтори", value=8, min_value=1, key=f"br_m_s{s}")
                    with col3:
                        bf = st.selectbox(f"Спина Пд {s}: Відчуття", SET_FEELINGS, key=f"bf_m_s{s}")
                    back_m_sets_data.append((bw, br, bf))
            bt_m = st.selectbox("Загальне самопочуття (Спина, Пн)", TAGS, key="bt_m")
            
            st.markdown("<hr>", unsafe_allow_html=True)
            abs_ex_m = st.selectbox("Прес (Понеділок)", ABS_EXERCISES, key="abs_m")
            as_m = st.number_input("Кількість підходів (Прес, Пн)", value=3, min_value=1, key="as_m_count")
            
            abs_m_sets_data = []
            with st.expander(f"🔩 Підходи для Пресу ({as_m} підх.)", expanded=True):
                for s in range(1, int(as_m) + 1):
                    col1, col2, col3 = st.columns([2, 1.5, 2])
                    with col1:
                        aw = st.number_input(f"Прес Пд {s}: Вага", value=0.0, step=step_val, key=f"aw_m_s{s}")
                    with col2:
                        ar = st.number_input(f"Прес Пд {s}: Повтори", value=12, min_value=1, key=f"ar_m_s{s}")
                    with col3:
                        af = st.selectbox(f"Прес Пд {s}: Відчуття", SET_FEELINGS, key=f"af_m_s{s}")
                    abs_m_sets_data.append((aw, ar, af))
            at_m = st.selectbox("Загальне самопочуття (Прес, Пн)", TAGS, key="at_m")
            
            if st.button("💾 Зберегти тренування Понеділка", width='stretch'):
                d = str(date.today())
                for idx, (w, r, f) in enumerate(sq_m_sets, 1):
                    insert_workout(d, "Присід", "Понеділок", w, r, len(sq_m_sets), sq_m_tag, "", set_num=idx, set_feeling=f)
                for idx, (w, r, f) in enumerate(bp_m_sets, 1):
                    insert_workout(d, "Жим лежачи", "Понеділок", w, r, len(bp_m_sets), bp_m_tag, "", set_num=idx, set_feeling=f)
                for idx, (w, r, f) in enumerate(back_m_sets_data, 1):
                    insert_workout(d, back_ex_m, "Понеділок", w, r, len(back_m_sets_data), bt_m, "", set_num=idx, set_feeling=f)
                for idx, (w, r, f) in enumerate(abs_m_sets_data, 1):
                    insert_workout(d, abs_ex_m, "Понеділок", w, r, len(abs_m_sets_data), at_m, "", set_num=idx, set_feeling=f)
                st.success("✅ Дані за Понеділок внесено!")
                st.rerun()

        # СЕРЕДА (ВІДНОВЛЕННЯ)
        with sub_wed:
            st.subheader("Легке відновлення (70%)")
            sq_w_sets, sq_w_tag = render_base_ex("Присід", 0.70, 3, 5, step_val)
            bp_w_sets, bp_w_tag = render_base_ex("Жим лежачи", 0.70, 3, 5, step_val)
            
            st.subheader("Додаткові вправи (Підсобка)")
            back_ex_w = st.selectbox("Спина легка (Середа)", BACK_EXERCISES, key="back_w")
            bs_w = st.number_input("Кількість підходів (Спина, Ср)", value=3, min_value=1, key="bs_w_count")
            
            back_w_sets_data = []
            with st.expander(f"🔩 Підходи для Спини ({bs_w} підх.)", expanded=True):
                for s in range(1, int(bs_w) + 1):
                    col1, col2, col3 = st.columns([2, 1.5, 2])
                    with col1:
                        bw = st.number_input(f"Спина Ср Пд {s}: Вага", value=0.0, step=step_val, key=f"bw_w_s{s}")
                    with col2:
                        br = st.number_input(f"Спина Ср Пд {s}: Повтори", value=8, min_value=1, key=f"br_w_s{s}")
                    with col3:
                        bf = st.selectbox(f"Спина Ср Пд {s}: Відчуття", SET_FEELINGS, key=f"bf_w_s{s}")
                    back_w_sets_data.append((bw, br, bf))
            bt_w = st.selectbox("Самопочуття (Спина, Ср)", TAGS, key="bt_w")
            
            st.markdown("<hr>", unsafe_allow_html=True)
            abs_ex_w = st.selectbox("Прес (Середа)", ABS_EXERCISES, key="abs_w")
            as_w = st.number_input("Кількість підходів (Прес, Ср)", value=3, min_value=1, key="as_w_count")
            
            abs_w_sets_data = []
            with st.expander(f"🔩 Підходи для Пресу ({as_w} підх.)", expanded=True):
                for s in range(1, int(as_w) + 1):
                    col1, col2, col3 = st.columns([2, 1.5, 2])
                    with col1:
                        aw = st.number_input(f"Прес Ср Пд {s}: Вага", value=0.0, step=step_val, key=f"aw_w_s{s}")
                    with col2:
                        ar = st.number_input(f"Прес Ср Пд {s}: Повтори", value=12, min_value=1, key=f"ar_w_s{s}")
                    with col3:
                        af = st.selectbox(f"Прес Ср Пд {s}: Відчуття", SET_FEELINGS, key=f"af_w_s{s}")
                    abs_w_sets_data.append((aw, ar, af))
            at_w = st.selectbox("Самопочуття (Прес, Ср)", TAGS, key="at_w")
            
            if st.button("💾 Зберегти тренування Середи", width='stretch'):
                d = str(date.today())
                for idx, (w, r, f) in enumerate(sq_w_sets, 1):
                    insert_workout(d, "Присід", "Середа", w, r, len(sq_w_sets), sq_w_tag, "", set_num=idx, set_feeling=f)
                for idx, (w, r, f) in enumerate(bp_w_sets, 1):
                    insert_workout(d, "Жим лежачи", "Середа", w, r, len(bp_w_sets), bp_w_tag, "", set_num=idx, set_feeling=f)
                for idx, (w, r, f) in enumerate(back_w_sets_data, 1):
                    insert_workout(d, back_ex_w, "Середа", w, r, len(back_w_sets_data), bt_w, "", set_num=idx, set_feeling=f)
                for idx, (w, r, f) in enumerate(abs_w_sets_data, 1):
                    insert_workout(d, abs_ex_w, "Середа", w, r, len(abs_w_sets_data), at_w, "", set_num=idx, set_feeling=f)
                st.success("✅ Дані за Середу внесено!")
                st.rerun()

        # П'ЯТНИЦЯ (ІНТЕНСИВНІСТЬ / РЕКОРДИ)
        with sub_fri:
            st.subheader("🔥 Рекорди Інтенсивності (1х5)")
            sq_f_sets, sq_f_tag = render_base_ex("Присід", 1.0, 1, 5, step_val, is_record=True)
            bp_f_sets, bp_f_tag = render_base_ex("Жим лежачи", 1.0, 1, 5, step_val, is_record=True)
            dl_f_sets, dl_f_tag = render_base_ex("Станова тяга", 1.0, 1, 5, step_val, is_record=True)
            
            st.subheader("Додаткові вправи")
            abs_ex_f = st.selectbox("Прес (П'ятниця)", ABS_EXERCISES, key="abs_f")
            as_f = st.number_input("Кількість підходів (Прес, Пт)", value=3, min_value=1, key="as_f_count")
            
            abs_f_sets_data = []
            with st.expander(f"🔩 Підходи для Пресу ({as_f} підх.)", expanded=True):
                for s in range(1, int(as_f) + 1):
                    col1, col2, col3 = st.columns([2, 1.5, 2])
                    with col1:
                        aw = st.number_input(f"Прес Пт Пд {s}: Вага", value=0.0, step=step_val, key=f"aw_f_s{s}")
                    with col2:
                        ar = st.number_input(f"Прес Пт Пд {s}: Повтори", value=12, min_value=1, key=f"ar_f_s{s}")
                    with col3:
                        af = st.selectbox(f"Прес Пт Пд {s}: Відчуття", SET_FEELINGS, key=f"af_f_s{s}")
                    abs_f_sets_data.append((aw, ar, af))
            at_f = st.selectbox("Самопочуття (Прес, П'ятниця)", TAGS, key="at_f")
            
            if st.button("💾 Фіксувати Рекорди П'ятниці", width='stretch'):
                d = str(date.today())
                for ex, (sets_data, ex_tag) in [("Присід", sq_f_sets), ("Жим лежачи", bp_f_sets), ("Станова тяга", dl_f_sets)]:
                    for idx, (w, r, f) in enumerate(sets_data, 1):
                        insert_workout(d, ex, "П'ятниця", w, r, len(sets_data), ex_tag, "", set_num=idx, set_feeling=f)
                    if sets_data:
                        insert_friday_record(d, ex, sets_data[0][0], sets_data[0][1])
                
                for idx, (w, r, f) in enumerate(abs_f_sets_data, 1):
                    insert_workout(d, abs_ex_f, "П'ятниця", w, r, len(abs_f_sets_data), at_f, "", set_num=idx, set_feeling=f)
                st.success("🚀 Базу оновлено! Ваги перераховано.")
                st.rerun()

    # ================== ТАБ 4: ЖУРНАЛ ==================
    with tab4:
        st.subheader("📓 Лог виконаних тренувань за вправами")
        
        with st.expander("➕ Додати тренування (минулі дати)"):
            st.write("Використовуй цю форму, щоб додати пропущені записи.")
            
            # Ініціалізуємо лічильник підходу в сесії, якщо його ще немає
            if "manual_set_num" not in st.session_state:
                st.session_state.manual_set_num = 1

            with st.form("manual_entry_form"):
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    m_date = st.date_input("Дата", date.today())
                    m_day = st.selectbox("Тип дня", ["Понеділок", "Середа", "П'ятниця"])
                with col_m2:
                    all_ex = MAIN_EXERCISES + BACK_EXERCISES + ABS_EXERCISES
                    m_ex = st.selectbox("Вправа", all_ex)
                    m_tag = st.selectbox("Статус (Загальний)", TAGS)
                
                col_m3, col_m4, col_m5 = st.columns(3)
                with col_m3: m_w = st.number_input("Вага (кг)", step=step_val, min_value=0.0)
                with col_m4: m_r = st.number_input("Повтори", min_value=1)
                with col_m5: m_s = st.number_input("Всього підходів у вправі", min_value=1, value=5)
                
                col_m6, col_m7 = st.columns(2)
                with col_m6: 
                    # Зв'язуємо віджет безпосередньо з session_state через key
                    m_set_num = st.number_input(
                        "Номер конкретного підходу, який вносиш", 
                        min_value=1, 
                        key="manual_set_num"
                    )
                with col_m7: m_set_feel = st.selectbox("Відчуття на цьому підході", SET_FEELINGS)
                
                m_comm = st.text_input("Коментар")
                
                if st.form_submit_button("💾 Зберегти в історію"):
                    insert_workout(str(m_date), m_ex, m_day, m_w, m_r, m_s, m_tag, m_comm, set_num=m_set_num, set_feeling=m_set_feel)
                    
                    # ПЛЮСУЄМО ПІДХІД НА НАСТУПНИЙ РАЗ (значення в key оновиться при rerun)
                    st.session_state.manual_set_num = m_set_num + 1
                    
                    st.success(f"✅ Підхід №{m_set_num} успішно додано! Наступний підхід: №{m_set_num + 1}")
                    st.rerun()

        st.markdown("---")
        
        df_log = pd.read_sql_query("""
            SELECT id, date as [Дата], exercise as [Вправа], day_type as [День], 
            set_num as [Підхід №], weight as [Вага (кг)], reps as [Повт], 
            set_feeling as [Відчуття підходу], ROUND(calculated_1rm, 1) as [Розрахований 1ПМ], 
            tag as [Загальний статус] 
            FROM workouts ORDER BY date DESC, id DESC""", get_connection())
        st.dataframe(df_log, width='stretch', hide_index=False)
        
        st.subheader("🗑️ Видалення запису")
        with st.expander("⚠️ Натисніть, щоб видалити помилковий запис"):
            del_id = st.number_input("Введіть ID запису (з таблиці вище):", min_value=1, step=1)
            if st.button("❌ Видалити цей запис"):
                conn = get_connection()
                conn.execute("DELETE FROM workouts WHERE id=?", (del_id,))
                conn.commit()
                st.success(f"Запис №{del_id} видалено!")
                st.rerun()
    # ================== ТАБ 5: АНАЛІТИКА ТА ДАНІ ==================
    with tab5:
        st.subheader("📈 Аналітика прогресу")
        
        df = pd.read_sql_query("SELECT * FROM workouts ORDER BY date ASC", get_connection())
        
        if not df.empty:
            st.write("### 🏋️ Динаміка по вправах")
            
            all_exercises = df["exercise"].unique()
            valid_defaults = [ex for ex in MAIN_EXERCISES if ex in all_exercises]
            selected_ex = st.multiselect("Обери вправи для порівняння", all_exercises, default=valid_defaults)
            
            if selected_ex:
                df_ex = df[df["exercise"].isin(selected_ex)]
                fig_ex = px.line(df_ex, x="date", y="calculated_1rm", color="exercise", 
                                 markers=True, title="Динаміка 1ПМ (Розрахунковий)")
                fig_ex.update_layout(paper_bgcolor="#111827", plot_bgcolor="#1a1d27", font=dict(color="#94a3b8"))
                st.plotly_chart(fig_ex, width='stretch')
            
            st.markdown("---")
            st.write("### 🏆 Графік Тоталу (Сума максимумів 1ПМ Присіду, Жиму, Тяги)")
            
            df_max_per_day = df[df["exercise"].isin(MAIN_EXERCISES)].groupby(["date", "exercise"])["calculated_1rm"].max().reset_index()
            df_total = df_max_per_day.groupby("date")["calculated_1rm"].sum().reset_index()
            
            fig_total = px.area(df_total, x="date", y="calculated_1rm", 
                                title="Сумарний Тотал Сили", markers=True, color_discrete_sequence=['#e85d04'])
            fig_total.update_layout(paper_bgcolor="#111827", plot_bgcolor="#1a1d27", font=dict(color="#94a3b8"))
            st.plotly_chart(fig_total, width='stretch')
            
        else:
            st.info("💡 Локальна база даних порожня. Якщо ви запустили додаток заново, затягніть дані з хмари кнопкою нижче.")
            
        st.markdown("---")
        st.subheader("☁️ Хмарна синхронізація (Google Sheets)")
        
        col_sync1, col_sync2 = st.columns(2)
        with col_sync1:
            if st.button("📥 Завантажити дані з Хмари в додаток", use_container_width=True):
                pull_from_gsheets()
        with col_sync2:
            if st.button("📤 Вивантажити локальні дані в Хмару", use_container_width=True):
                sync_to_gsheets()
                
        st.markdown("---")
        st.subheader("💾 Локальне резервне копіювання (Експорт / Імпорт)")
        
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            df_workouts_export = pd.read_sql_query("SELECT * FROM workouts", get_connection())
            csv_workouts = df_workouts_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Експортувати весь Журнал (CSV)",
                data=csv_workouts,
                file_name=f"texas_workouts_backup_{date.today()}.csv",
                mime="text/csv",
                key="btn_exp_workouts"
            )
        with col_exp2:
            df_friday_export = pd.read_sql_query("SELECT * FROM friday_records", get_connection())
            csv_friday = df_friday_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Експортувати П'ятничні Рекорди (CSV)",
                data=csv_friday,
                file_name=f"texas_friday_backup_{date.today()}.csv",
                mime="text/csv",
                key="btn_exp_friday"
            )
            
        st.markdown("#### 📤 Відновлення даних з CSV файлу")
        uploaded_file = st.file_uploader("Оберіть резервний файл CSV для імпорту", type=["csv"])
        target_table = st.radio("Цільова таблиця для імпорту:", ["Журнал тренувань (workouts)", "П'ятничні рекорди (friday_records)"])
        
        if uploaded_file is not None:
            if st.button("🚀 Запустити імпорт у базу даних"):
                try:
                    df_imported = pd.read_csv(uploaded_file)
                    if 'id' in df_imported.columns:
                        df_imported = df_imported.drop(columns=['id'])
                        
                    table_name = "workouts" if "Журнал" in target_table else "friday_records"
                    df_imported.to_sql(table_name, get_connection(), if_exists='append', index=False)
                    st.success(f"✅ Успішно додано {len(df_imported)} записів у таблицю `{table_name}`!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Помилка зчитування або структури файлу: {e}")
                    
if __name__ == "__main__":
    main()

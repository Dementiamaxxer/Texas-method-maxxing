"""
╔══════════════════════════════════════════════════════════════════╗
║         ТЕХАСЬКИЙ МЕТОД PRO — ТРЕКЕР ТРЕНУВАНЬ                   ║
║         Streamlit + SQLite | Версія з Тоталом та 1ПМ             ║
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
    "✅ Пройшло легко",
    "🔥 На межі відмови",
    "🦴 Боліли суглоби",
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
# БАЗА ДАНИХ ТА МІГРАЦІЇ
# -----------------------------------------------------------------
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Створюємо таблиці, якщо їх немає
    c.execute("""CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise TEXT, day_type TEXT, 
        weight REAL, reps INTEGER, sets INTEGER, tag TEXT, comment TEXT, calculated_1rm REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS friday_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise TEXT, weight REAL, reps INTEGER, calculated_1rm REAL)""")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    
    # МІГРАЦІЯ: Додаємо колонку calculated_1rm, якщо юзер оновився зі старої версії коду
    try:
        c.execute("ALTER TABLE workouts ADD COLUMN calculated_1rm REAL")
    except sqlite3.OperationalError:
        pass  # Колонка вже існує
        
    try:
        c.execute("ALTER TABLE friday_records ADD COLUMN calculated_1rm REAL")
    except sqlite3.OperationalError:
        pass  # "Колонка вже існує
        
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
        "SELECT tag FROM workouts WHERE tag IS NOT NULL AND tag != '—' ORDER BY date DESC, id DESC LIMIT 5"
    ).fetchall()
    tags = [r[0] for r in rows]
    if "🦴 Боліли суглоби" in tags:
        return True, "Виявлено тег «Боліли суглоби». Рекомендується зробити легкий тиждень (Делоад)!"
    if len(tags) >= 3 and all("На межі відмови" in t for t in tags[:3]):
        return True, "3 тренування поспіль пройшли на межі відмови. Знизь робочі ваги на 5% або відпочинь."
    return False, ""

# -----------------------------------------------------------------
# ГОЛОВНИЙ ІНТЕРФЕЙС
# -----------------------------------------------------------------
def main():
    init_db()
    st.title("🏋️ Техаський Метод PRO")
    
    # Перевірка втомлюваності ЦНС
    cns_warn, msg = check_cns()
    if cns_warn:
        st.markdown(f'<div class="cns-alert">⚠️ <b>АНАЛІЗ ЦНС:</b> {msg}</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚙️ Налаштування & Калькулятори", "📅 Календар", "📝 Планування", "📓 Журнал", "📈 Аналітика & Дані"
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
        
        # БЛОК 1: ПОТОЧНИЙ СТАТУС ВІДНОСНО П'ЯТНИЦІ
        st.subheader("🏆 Поточні максимуми та Тотал (Остання П'ятниця)")
        f_sq_w, f_sq_r = get_last_record("Присід")
        f_bp_w, f_bp_r = get_last_record("Жим лежачи")
        f_dl_w, f_dl_r = get_last_record("Станова тяга")
        
        f_sq_1rm = calc_1rm_brzycki(f_sq_w, f_sq_r)
        f_bp_1rm = calc_1rm_brzycki(f_bp_w, f_bp_r)
        f_dl_1rm = calc_1rm_brzycki(f_dl_w, f_dl_r)
        friday_total = f_sq_1rm + f_bp_1rm + f_dl_1rm
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Поточний 1ПМ Присід", f"{f_sq_1rm:.1f} кг", f"База: {f_sq_w}кг х {f_sq_r}")
        with c2:
            st.metric("Поточний 1ПМ Жим", f"{f_bp_1rm:.1f} кг", f"База: {f_bp_w}кг х {f_bp_r}")
        with c3:
            st.metric("Поточний 1ПМ Тяга", f"{f_dl_1rm:.1f} кг", f"База: {f_dl_w}кг х {f_dl_r}")
        with c4:
            st.markdown(f"""
            <div class="metric-card" style="border-color: #e85d04;">
                <div class="metric-value">{friday_total:.1f} кг</div>
                <div class="metric-label">Поточний П'ятничний Тотал</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("---")
        
        # БЛОК 2: ІНТЕРАКТИВНІ КАЛЬКУЛЯТОРИ ДЛЯ КОЖНОЇ ВПРАВИ
        st.subheader("🔢 Інтерактивний калькулятор 1ПМ та Тоталу")
        st.caption("Введіть сюди будь-які ваги та повторення, щоб миттєво побачити розрахункову суму триборства.")
        
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            st.markdown("**🏋️ Калькулятор: Присід**")
            c_sq_w = st.number_input("Вага штанги (Присід)", value=float(f_sq_w), step=step_val, key="c_sq_w")
            c_sq_r = st.number_input("Повторення (Присід)", value=int(f_sq_r), min_value=1, key="c_sq_r")
            res_sq_1rm = calc_1rm_brzycki(c_sq_w, c_sq_r)
            st.info(f"1ПМ Присід: **{res_sq_1rm:.1f} кг**")
            
        with cc2:
            st.markdown("**🏋️ Калькулятор: Жим лежачи**")
            c_bp_w = st.number_input("Вага штанги (Жим)", value=float(f_bp_w), step=step_val, key="c_bp_w")
            c_bp_r = st.number_input("Повторення (Жим)", value=int(f_bp_r), min_value=1, key="c_bp_r")
            res_bp_1rm = calc_1rm_brzycki(c_bp_w, c_bp_r)
            st.info(f"1ПМ Жим: **{res_bp_1rm:.1f} кг**")
            
        with cc3:
            st.markdown("**🏋️ Калькулятор: Станова тяга**")
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
        st.subheader("📅 Інтерактивний календар")
        selected_date = st.date_input("Оберіть дату тренування", date.today())
        wd = selected_date.weekday()
        
        if check_day_completed(str(selected_date)):
            st.success(f"✅ Тренування за {selected_date.strftime('%d.%m.%Y')} вже було збережено в журнал!")
        
        if wd == 0:
            st.info(f"🗓️ **Понеділок — День Об'єму**\n- Присід: 5х5 ({round_to_step(f_sq_w*0.85, step_val)} кг)\n- Жим лежачи: 5х5 ({round_to_step(f_bp_w*0.85, step_val)} кг)\n- Спина + Прес на вибір")
        elif wd == 2:
            st.info(f"🗓️ **Середа — День Відновлення**\n- Присід: 3х5 ({round_to_step(f_sq_w*0.70, step_val)} кг)\n- Жим лежачи: 3х5 ({round_to_step(f_bp_w*0.70, step_val)} кг)\n- Легка спина + Прес")
        elif wd == 4:
            st.warning(f"🗓️ **П'ятниця — День Інтенсивності (РЕКОРДИ)**\n- Присід: 1х5\n- Жим лежачи: 1х5\n- Станова тяга: 1х5\n- Прес")
        else:
            st.write("😴 Сьогодні день відпочинку. Рости м'язи та відновлюй ЦНС.")

    # ================== ТАБ 3: ПЛАНУВАННЯ ТРЕНУВАНЬ ==================
    with tab3:
        sub_mon, sub_wed, sub_fri = st.tabs(["🟢 Понеділок (Об'єм)", "🟡 Середа (Відновлення)", "🔴 П'ятниця (Інтенсивність)"])
        
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
            st.subheader("Базовий об'єм (85% від рекорду)")
            sq_m = render_base_ex("Присід", 0.85, 5, 5, step_val)
            bp_m = render_base_ex("Жим лежачи", 0.85, 5, 5, step_val)
            
            st.subheader("Додаткові вправи")
            back_ex_m = st.selectbox("Спина (Понеділок)", BACK_EXERCISES, key="back_m")
            bw_m = st.number_input("Вага (Спина, Пн)", value=0.0, step=step_val)
            br_m = st.number_input("Повторення (Спина, Пн)", value=8)
            
            abs_ex_m = st.selectbox("Прес (Понеділок)", ABS_EXERCISES, key="abs_m")
            aw_m = st.number_input("Вага (Прес, Пн)", value=0.0, step=step_val)
            ar_m = st.number_input("Повторення (Прес, Пн)", value=12)
            
            tag_m = st.selectbox("Мій статус/самопочуття", ["—"] + TAGS, key="tag_m")
            
            if st.button("💾 Зберегти тренування Понеділка", use_container_width=True):
                d = str(date.today())
                insert_workout(d, "Присід", "Понеділок", sq_m[0], sq_m[1], sq_m[2], tag_m, "")
                insert_workout(d, "Жим лежачи", "Понеділок", bp_m[0], bp_m[1], bp_m[2], tag_m, "")
                insert_workout(d, back_ex_m, "Понеділок", bw_m, br_m, 3, tag_m, "")
                insert_workout(d, abs_ex_m, "Понеділок", aw_m, ar_m, 3, tag_m, "")
                st.success("Тренування Понеділка успішно збережено в історію!")

        # СЕРЕДА
        with sub_wed:
            st.subheader("Легке відновлення (70% від рекорду)")
            sq_w = render_base_ex("Присід", 0.70, 3, 5, step_val)
            bp_w = render_base_ex("Жим лежачи", 0.70, 3, 5, step_val)
            
            st.subheader("Додаткові вправи")
            back_ex_w = st.selectbox("Спина легка (Середа)", BACK_EXERCISES, key="back_w")
            bw_w = st.number_input("Вага (Спина, Ср)", value=0.0, step=step_val)
            br_w = st.number_input("Повторення (Спина, Ср)", value=8)
            
            abs_ex_w = st.selectbox("Прес (Середа)", ABS_EXERCISES, key="abs_w")
            aw_w = st.number_input("Вага (Прес, Ср)", value=0.0, step=step_val)
            ar_w = st.number_input("Повторення (Прес, Ср)", value=12)
            
            tag_w = st.selectbox("Мій статус/самопочуття", ["—"] + TAGS, key="tag_w")
            
            if st.button("💾 Зберегти тренування Середи", use_container_width=True):
                d = str(date.today())
                insert_workout(d, "Присід", "Середа", sq_w[0], sq_w[1], sq_w[2], tag_w, "")
                insert_workout(d, "Жим лежачи", "Середа", bp_w[0], bp_w[1], bp_w[2], tag_w, "")
                insert_workout(d, back_ex_w, "Середа", bw_w, br_w, 3, tag_w, "")
                insert_workout(d, abs_ex_w, "Середа", aw_w, ar_w, 3, tag_w, "")
                st.success("Тренування Середи успішно збережено в історію!")

        # П'ЯТНИЦЯ
        with sub_fri:
            st.subheader("🔥 Нові Рекорди (Інтенсивність 1х5)")
            sq_f = render_base_ex("Присід", 1.0, 1, 5, step_val, is_record=True)
            bp_f = render_base_ex("Жим лежачи", 1.0, 1, 5, step_val, is_record=True)
            dl_f = render_base_ex("Станова тяга", 1.0, 1, 5, step_val, is_record=True)
            
            st.subheader("Додаткові вправи")
            abs_ex_f = st.selectbox("Прес (П'ятниця)", ABS_EXERCISES, key="abs_f")
            aw_f = st.number_input("Вага (Прес, Пт)", value=0.0, step=step_val)
            ar_f = st.number_input("Повторення (Прес, Пт)", value=12)
            
            tag_f = st.selectbox("Мій статус/самопочуття", ["—"] + TAGS, key="tag_f")
            
            if st.button("💾 Фіксувати Рекорди П'ятниці", use_container_width=True):
                d = str(date.today())
                # Пишемо в загальний журнал та таблицю рекордів
                for ex, data in [("Присід", sq_f), ("Жим лежачи", bp_f), ("Станова тяга", dl_f)]:
                    insert_workout(d, ex, "П'ятниця", data[0], data[1], data[2], tag_f, "")
                    insert_friday_record(d, ex, data[0], data[1])
                
                insert_workout(d, abs_ex_f, "П'ятниця", aw_f, ar_f, 3, tag_f, "")
                st.success("🚀 Базу оновлено! Нові рекорди зафіксовані.")
                st.rerun()

    # ================== ТАБ 4: ЖУРНАЛ ==================
    with tab4:
        st.subheader("📓 Лог виконаних тренувань (зі збереженням 1ПМ)")
        df_log = pd.read_sql_query("""
            SELECT date as [Дата], exercise as [Вправа], day_type as [День], 
            weight as [Вага (кг)], reps as [Повт], sets as [Підходи], 
            ROUND(calculated_1rm, 1) as [Розрахований 1ПМ], tag as [Статус] 
            FROM workouts ORDER BY id DESC""", get_connection())
        st.dataframe(df_log, use_container_width=True, hide_index=True)

    # ================== ТАБ 5: АНАЛІТИКА ТА ІМПОРТ/ЕКСПОРТ ==================
    with tab5:
        st.subheader("📈 Тренд розвитку сили по П'ятницях")
        df_charts = pd.read_sql_query("SELECT date, exercise, calculated_1rm FROM friday_records", get_connection())
        
        if not df_charts.empty:
            fig = px.line(df_charts, x="date", y="calculated_1rm", color="exercise", markers=True, title="Прогрес 1RM (Формула Бржицькі)")
            fig.update_layout(paper_bgcolor="#111827", plot_bgcolor="#1a1d27", font=dict(color="#94a3b8"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Графік побудується автоматично, як тільки ви збережете перше тренування П'ятниці.")

        st.markdown("---")
        st.subheader("💾 Резервне копіювання бази даних")
        col_ex, col_im = st.columns(2)
        
        with col_ex:
            st.write("**Експорт журналу**")
            csv_export = pd.read_sql_query("SELECT * FROM workouts", get_connection()).to_csv(index=False)
            st.download_button("⬇️ Завантажити копію у CSV", csv_export, "texas_backup.csv", "text/csv")
            
        with col_im:
            st.write("**Відновлення історії**")
            uploaded_file = st.file_uploader("Оберіть файл CSV для імпорту", type=["csv"])
            if uploaded_file is not None and st.button("🔄 Завантажити дані назад"):
                try:
                    df_import = pd.read_csv(uploaded_file)
                    df_import.to_sql("workouts", get_connection(), if_exists="append", index=False)
                    st.success("Усю історію успішно імпортовано та відновлено!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Помилка при читанні файлу: {e}")

if __name__ == "__main__":
    main()

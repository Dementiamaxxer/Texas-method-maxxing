"""
╔══════════════════════════════════════════════════════════════════╗
║          ТЕХАСЬКИЙ МЕТОД — ТРЕКЕР ТРЕНУВАНЬ                      ║
║          Версія: Повноекранний контроль вправ та підходів        ║
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
        
        st.subheader("🏆 Поточні максимуми (Остання П'ятниця)")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Поточний 1ПМ Присід", f"{f_sq_1rm:.1f} кг", f"База: {f_sq_w}кг х {f_sq_r}")
        with c2: st.metric("Поточний 1ПМ Жим", f"{f_bp_1rm:.1f} кг", f"База: {f_bp_w}кг х {f_bp_r}")
        with c3: st.metric("Поточний 1ПМ Тяга", f"{f_dl_1rm:.1f} кг", f"База: {f_dl_w}кг х {f_dl_r}")
        with c4:
            st.markdown(f"""
            <div class="metric-card" style="border-color: #e85d04;">
                <div class="metric-value">{friday_total:.1f} кг</div>
                <div class="metric-label">Поточний П'ятничний Тотал</div>
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
            col_a, col_b, col_c = st.columns([2, 1, 1.5])
            with col_a:
                act_w = st.number_input(f"Вага ({ex_name})", value=float(target_w), step=step, key=f"w_{ex_name}_{perc}")
            with col_b:
                act_r = st.number_input(f"Повт. ({ex_name})", value=reps, key=f"r_{ex_name}_{perc}")
            with col_c:
                ex_tag = st.selectbox(f"Самопочуття ({ex_name})", TAGS, key=f"tag_{ex_name}_{perc}")
            
            with st.expander("Розминка"):
                for w in calc_warmup(act_w, step):
                    st.markdown(f'<div class="warmup-row"><span>{w["label"]}</span><b>{w["weight"]} кг x {w["reps"]}</b></div>', unsafe_allow_html=True)
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            return act_w, act_r, sets, ex_tag

        # ПОНЕДІЛОК (ОБ'ЄМ)
        with sub_mon:
            st.subheader("Базовий об'єм (85%)")
            sq_m = render_base_ex("Присід", 0.85, 5, 5, step_val)
            bp_m = render_base_ex("Жим лежачи", 0.85, 5, 5, step_val)
            
            st.subheader("Додаткові вправи (Підсобка)")
            back_ex_m = st.selectbox("Спина (Понеділок)", BACK_EXERCISES, key="back_m")
            cb1, cb2, cb3, cb4 = st.columns(4)
            with cb1: bw_m = st.number_input("Вага (Спина, Пн)", value=0.0, step=step_val)
            with cb2: bs_m = st.number_input("Підходи (Спина, Пн)", value=3, min_value=1)
            with cb3: br_m = st.number_input("Повторення (Спина, Пн)", value=8, min_value=1)
            with cb4: bt_m = st.selectbox("Самопочуття (Спина, Пн)", TAGS, key="bt_m")
            
            st.markdown("<hr>", unsafe_allow_html=True)
            abs_ex_m = st.selectbox("Прес (Понеділок)", ABS_EXERCISES, key="abs_m")
            ca1, ca2, ca3, ca4 = st.columns(4)
            with ca1: aw_m = st.number_input("Вага (Прес, Пн)", value=0.0, step=step_val)
            with ca2: as_m = st.number_input("Підходи (Прес, Пн)", value=3, min_value=1)
            with ca3: ar_m = st.number_input("Повторення (Прес, Пн)", value=12, min_value=1)
            with ca4: at_m = st.selectbox("Самопочуття (Прес, Пн)", TAGS, key="at_m")
            
            if st.button("💾 Зберегти тренування Понеділка", use_container_width=True):
                d = str(date.today())
                insert_workout(d, "Присід", "Понеділок", sq_m[0], sq_m[1], sq_m[2], sq_m[3], "")
                insert_workout(d, "Жим лежачи", "Понеділок", bp_m[0], bp_m[1], bp_m[2], bp_m[3], "")
                insert_workout(d, back_ex_m, "Понеділок", bw_m, br_m, bs_m, bt_m, "")
                insert_workout(d, abs_ex_m, "Понеділок", aw_m, ar_m, as_m, at_m, "")
                st.success("✅ Данні за Понеділок внесено!")
                st.rerun()

        # СЕРЕДА (ВІДНОВЛЕННЯ)
        with sub_wed:
            st.subheader("Легке відновлення (70%)")
            sq_w = render_base_ex("Присід", 0.70, 3, 5, step_val)
            bp_w = render_base_ex("Жим лежачи", 0.70, 3, 5, step_val)
            
            st.subheader("Додаткові вправи (Підсобка)")
            back_ex_w = st.selectbox("Спина легка (Середа)", BACK_EXERCISES, key="back_w")
            cbw1, cbw2, cbw3, cbw4 = st.columns(4)
            with cbw1: bw_w = st.number_input("Вага (Спина, Ср)", value=0.0, step=step_val)
            with cbw2: bs_w = st.number_input("Підходи (Спина, Ср)", value=3, min_value=1)
            with cbw3: br_w = st.number_input("Повторення (Спина, Ср)", value=8, min_value=1)
            with cbw4: bt_w = st.selectbox("Самопочуття (Спина, Ср)", TAGS, key="bt_w")
            
            st.markdown("<hr>", unsafe_allow_html=True)
            abs_ex_w = st.selectbox("Прес (Середа)", ABS_EXERCISES, key="abs_w")
            caw1, caw2, caw3, caw4 = st.columns(4)
            with caw1: aw_w = st.number_input("Вага (Прес, Ср)", value=0.0, step=step_val)
            with caw2: as_w = st.number_input("Підходи (Прес, Ср)", value=3, min_value=1)
            with caw3: ar_w = st.number_input("Повторення (Прес, Ср)", value=12, min_value=1)
            with caw4: at_w = st.selectbox("Самопочуття (Прес, Ср)", TAGS, key="at_w")
            
            if st.button("💾 Зберегти тренування Середи", use_container_width=True):
                d = str(date.today())
                insert_workout(d, "Присід", "Середа", sq_w[0], sq_w[1], sq_w[2], sq_w[3], "")
                insert_workout(d, "Жим лежачи", "Середа", bp_w[0], bp_w[1], bp_w[2], bp_w[3], "")
                insert_workout(d, back_ex_w, "Середа", bw_w, br_w, bs_w, bt_w, "")
                insert_workout(d, abs_ex_w, "Середа", aw_w, ar_w, as_w, at_w, "")
                st.success("✅ Данні за Середу внесено!")
                st.rerun()

        # П'ЯТНИЦЯ (ІНТЕНСИВНІСТЬ / РЕКОРДИ)
        with sub_fri:
            st.subheader("🔥 Рекорди Інтенсивності (1х5)")
            sq_f = render_base_ex("Присід", 1.0, 1, 5, step_val, is_record=True)
            bp_f = render_base_ex("Жим лежачи", 1.0, 1, 5, step_val, is_record=True)
            dl_f = render_base_ex("Станова тяга", 1.0, 1, 5, step_val, is_record=True)
            
            st.subheader("Додаткові вправи")
            abs_ex_f = st.selectbox("Прес (П'ятниця)", ABS_EXERCISES, key="abs_f")
            caf1, caf2, caf3, caf4 = st.columns(4)
            with caf1: aw_f = st.number_input("Вага (Прес, Пт)", value=0.0, step=step_val)
            with caf2: as_f = st.number_input("Підходи (Прес, Пт)", value=3, min_value=1)
            with caf3: ar_f = st.number_input("Повторення (Прес, Пт)", value=12, min_value=1)
            with caf4: at_f = st.selectbox("Самопочуття (Прес, Пт)", TAGS, key="at_f")
            
            if st.button("💾 Фіксувати Рекорди П'ятниці", use_container_width=True):
                d = str(date.today())
                for ex, data in [("Присід", sq_f), ("Жим лежачи", bp_f), ("Станова тяга", dl_f)]:
                    insert_workout(d, ex, "П'ятниця", data[0], data[1], data[2], data[3], "")
                    insert_friday_record(d, ex, data[0], data[1])
                
                insert_workout(d, abs_ex_f, "П'ятниця", aw_f, ar_f, as_f, at_f, "")
                st.success("🚀 Базу оновлено! Ваги перераховано.")
                st.rerun()

    # ================== ТАБ 4: ЖУРНАЛ ==================
    with tab4:
        st.subheader("📓 Лог виконаних тренувань за вправами")
        df_log = pd.read_sql_query("""
            SELECT id, date as [Дата], exercise as [Вправа], day_type as [День], 
            weight as [Вага (кг)], sets as [Підходи], reps as [Повт], 
            ROUND(calculated_1rm, 1) as [Розрахований 1ПМ], tag as [Статус Самопочуття] 
            FROM workouts ORDER BY id DESC""", get_connection())
        st.dataframe(df_log, use_container_width=True, hide_index=False)
        
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
        st.subheader("📈 Тренд розвитку сили (П'ятничні рекорди)")
        df_charts = pd.read_sql_query("SELECT date, exercise, calculated_1rm FROM friday_records", get_connection())
        
        if not df_charts.empty:
            fig = px.line(df_charts, x="date", y="calculated_1rm", color="exercise", markers=True, title="Динаміка максимуму 1RM")
            fig.update_layout(paper_bgcolor="#111827", plot_bgcolor="#1a1d27", font=dict(color="#94a3b8"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Історія порожня. Додай першу П'ятницю для побудови графіка!")

        st.markdown("---")
        st.subheader("💾 Резервне копіювання")
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
                    st.error(f"Помилка імпорту: {e}")

if __name__ == "__main__":
    main()

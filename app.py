"""
╔══════════════════════════════════════════════════════════════════╗
║         ТЕХАСЬКИЙ МЕТОД — ТРЕКЕР ТРЕНУВАНЬ                      ║
║         Streamlit + SQLite | Dark Mode Ready                     ║
╚══════════════════════════════════════════════════════════════════╝

Запуск:
    pip install streamlit pandas plotly openpyxl
    streamlit run app.py

Структура програми:
    Понеділок  — Об'єм        (5x5)
    Середа     — Відновлення  (3x5 легко)
    П'ятниця   — Інтенсивність (1x5 рекорд)

    ОСНОВНІ ВПРАВИ (з розрахунком ваг):
        Присід, Жим лежачи, Станова тяга
    Жим лежачи — у кожному тренувальному дні (ПН/СР/ПТ).
    Плечі (армійський жим) — повністю виключені.

    ДОДАТКОВІ ВПРАВИ (без % від рекорду):
        ПН: Тяга в нахилі АБО Підтягування зворотним хватом (на вибір)
        СР: Cable Crunch + Маятник / Кругові підйоми ніг
        ПТ: тільки три базові
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
# КОНСТАНТИ
# -----------------------------------------------------------------
DB_PATH = "texas_method.db"

# Базові вправи — мають % розрахунок від рекорду П'ятниці
MAIN_EXERCISES = ["Присід", "Жим лежачи", "Станова тяга"]

# Додаткові — логуються без % розрахунку
EXTRA_MON = ["Тяга штанги в нахилі", "Підтягування зворотним хватом"]
EXTRA_WED = ["Cable Crunch", "Маятник на турніку", "Кругові підйоми ніг"]

# Всі вправи для журналу
ALL_EXERCISES = MAIN_EXERCISES + EXTRA_MON + EXTRA_WED

DAYS = ["Понеділок (Об'єм)", "Середа (Відновлення)", "П'ятниця (Інтенсивність)"]

TAGS = [
    "✅ Пройшло легко",
    "🔥 На межі відмови",
    "🦴 Боліли суглоби",
    "😴 Недосип/Втома"
]

# -----------------------------------------------------------------
# НАЛАШТУВАННЯ СТОРІНКИ
# -----------------------------------------------------------------
st.set_page_config(
    page_title="Техаський Метод",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.stApp { background: linear-gradient(135deg, #0d0f14 0%, #111827 100%); }
.stTabs [data-baseweb="tab-list"] {
    gap: 8px; background: #1a1d27; padding: 8px;
    border-radius: 12px; border: 1px solid #2a2d3e;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px; padding: 8px 20px; font-weight: 600;
    color: #7c8db0; background: transparent; border: none; transition: all 0.2s;
}
.stTabs [aria-selected="true"] { background: #e85d04 !important; color: white !important; }
.metric-card {
    background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 16px;
    padding: 24px; text-align: center; transition: transform 0.2s, border-color 0.2s;
}
.metric-card:hover { transform: translateY(-2px); border-color: #e85d04; }
.metric-value { font-size: 2.2rem; font-weight: 800; color: #e85d04; line-height: 1; }
.metric-label { font-size: 0.82rem; color: #7c8db0; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.08em; }
.warmup-table { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 12px; padding: 16px; margin-top: 12px; }
.warmup-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 12px; border-radius: 8px; margin-bottom: 4px;
    background: #12151f; border-left: 3px solid #e85d04;
}
.warmup-label { color: #7c8db0; font-size: 0.9rem; }
.warmup-weight { color: #f0f4ff; font-weight: 700; font-size: 1.05rem; }
.cns-alert {
    background: linear-gradient(135deg, #7f1d1d, #991b1b);
    border: 2px solid #ef4444; border-radius: 12px; padding: 20px; margin: 16px 0;
}
.cns-alert h3 { color: #fca5a5; margin: 0 0 8px 0; }
.cns-alert p  { color: #fecaca; margin: 0; }
.day-card {
    background: #1a1d27; border: 1px solid #2a2d3e;
    border-radius: 16px; padding: 20px; height: 100%;
}
.day-title { font-size: 1.1rem; font-weight: 700; color: #f0f4ff; margin-bottom: 2px; }
.day-sub { font-size: 0.78rem; color: #7c8db0; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 0.06em; }
.day-weight { font-size: 2rem; font-weight: 800; color: #e85d04; }
.day-scheme { font-size: 0.92rem; color: #94a3b8; margin-top: 4px; }
.extra-card { background: #12151f; border: 1px solid #2a2d3e; border-radius: 10px; padding: 12px 16px; margin-top: 8px; }
.extra-title { color: #7c8db0; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 6px; }
.extra-item { color: #94a3b8; font-size: 0.9rem; padding: 2px 0; }
.hero-title { font-size: 2.1rem; font-weight: 900; color: #f0f4ff; letter-spacing: -0.02em; }
.hero-accent { color: #e85d04; }
.hero-sub { color: #7c8db0; font-size: 1rem; margin-top: 4px; }
.stButton button {
    background: #e85d04; color: white; border: none;
    border-radius: 8px; font-weight: 600; padding: 8px 20px; transition: all 0.2s;
}
.stButton button:hover { background: #c44d03; transform: translateY(-1px); }
hr { border-color: #2a2d3e !important; }
</style>
""", unsafe_allow_html=True)


# ==================================================================
# БАЗА ДАНИХ
# ==================================================================

@st.cache_resource
def get_connection():
    """Кешоване підключення до SQLite (один екземпляр на сесію)."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    """Створює таблиці при першому запуску."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL,
            exercise   TEXT    NOT NULL,
            day_type   TEXT    NOT NULL,
            weight     REAL    NOT NULL,
            reps       INTEGER NOT NULL,
            sets       INTEGER NOT NULL DEFAULT 1,
            tag        TEXT,
            comment    TEXT,
            created_at TEXT    DEFAULT (datetime('now'))
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS friday_records (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            date     TEXT NOT NULL,
            exercise TEXT NOT NULL,
            weight   REAL NOT NULL,
            reps     INTEGER NOT NULL DEFAULT 5
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""")
    conn.commit()


def save_setting(key, value):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def load_setting(key, default=""):
    row = get_connection().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def insert_workout(date_str, exercise, day_type, weight, reps, sets, tag, comment):
    conn = get_connection()
    conn.execute(
        "INSERT INTO workouts (date, exercise, day_type, weight, reps, sets, tag, comment) VALUES (?,?,?,?,?,?,?,?)",
        (date_str, exercise, day_type, float(weight), int(reps), int(sets), tag, comment)
    )
    conn.commit()


def insert_friday_record(date_str, exercise, weight, reps=5):
    conn = get_connection()
    conn.execute(
        "INSERT INTO friday_records (date, exercise, weight, reps) VALUES (?,?,?,?)",
        (date_str, exercise, float(weight), int(reps))
    )
    conn.commit()


def get_all_workouts():
    return pd.read_sql_query(
        "SELECT * FROM workouts ORDER BY date DESC, id DESC", get_connection()
    )


def get_friday_records(exercise):
    return pd.read_sql_query(
        "SELECT * FROM friday_records WHERE exercise=? ORDER BY date",
        get_connection(), params=(exercise,)
    )


def get_last_friday_record(exercise):
    """Повертає (weight, reps) останнього П'ятничного рекорду або None."""
    return get_connection().execute(
        "SELECT weight, reps FROM friday_records WHERE exercise=? ORDER BY date DESC LIMIT 1",
        (exercise,)
    ).fetchone()


def get_recent_tags(exercise, n=5):
    rows = get_connection().execute(
        "SELECT tag FROM workouts WHERE exercise=? AND tag IS NOT NULL ORDER BY date DESC, id DESC LIMIT ?",
        (exercise, n)
    ).fetchall()
    return [r[0] for r in rows]


# ==================================================================
# ФОРМУЛИ
# ==================================================================

def calc_1rm_brzycki(weight, reps):
    """
    Формула Бржицькі:
        1RM = Вага / (1.0278 - 0.0278 * Повторень)
    Точна для 2-10 повторень. Всі константи через крапку (стандарт Python).
    """
    if reps <= 0:
        return 0.0
    if reps == 1:
        return float(weight)
    denominator = 1.0278 - (0.0278 * reps)
    if denominator <= 0:
        return float(weight)
    return weight / denominator


def round_to_step(weight, step):
    """
    Округлення до кратного ВНИЗ: floor(вага / крок) * крок
    Приклад: round_to_step(87.3, 2.5) => floor(34.92)*2.5 = 85.0
    Округлення вниз — безпечніше для спортсмена.
    """
    if step <= 0:
        return weight
    return math.floor(weight / step) * step


def calc_volume_weight(friday_max, step):
    """Понеділок (Об'єм): 85% від рекорду П'ятниці, округлено вниз."""
    return round_to_step(friday_max * 0.85, step)


def calc_recovery_weight(friday_max, step):
    """Середа (Відновлення): 70% від рекорду П'ятниці, округлено вниз."""
    return round_to_step(friday_max * 0.70, step)


def calc_warmup(working_weight, step):
    """
    Розминочні підходи:
        Гриф (20 кг) x10
        50% робочої ваги x5
        70% робочої ваги x3
        90% робочої ваги x1
    Кожен відсоток округлюється вниз до кроку залу.
    """
    return [
        {"label": "Гриф  x10", "weight": 20.0,                                        "reps": 10},
        {"label": "50%   x5",  "weight": round_to_step(working_weight * 0.50, step),   "reps": 5},
        {"label": "70%   x3",  "weight": round_to_step(working_weight * 0.70, step),   "reps": 3},
        {"label": "90%   x1",  "weight": round_to_step(working_weight * 0.90, step),   "reps": 1},
    ]


def check_cns_overload(exercise):
    """
    Перевіряє перевантаження ЦНС/суглобів:
        1) Тег 'Боліли суглоби' в останніх записах -> алерт
        2) 3 поспіль 'На межі відмови' -> алерт ЦНС
    Повертає (bool, str).
    """
    recent = get_recent_tags(exercise, n=5)
    if "🦴 Боліли суглоби" in recent:
        return True, "🦴 Виявлено тег **«Боліли суглоби»**"
    if len(recent) >= 3 and all(t == "🔥 На межі відмови" for t in recent[:3]):
        return True, "🔥 Три тренування поспіль **«На межі відмови»**"
    return False, ""


# ==================================================================
# UI-КОМПОНЕНТИ
# ==================================================================

def ui_metric_card(label, value):
    st.markdown(
        f'<div class="metric-card"><div class="metric-value">{value}</div>'
        f'<div class="metric-label">{label}</div></div>',
        unsafe_allow_html=True
    )


def ui_warmup_table(warmup, working_weight):
    rows = "".join(
        f'<div class="warmup-row">'
        f'<span class="warmup-label">{s["label"]}</span>'
        f'<span class="warmup-weight">{s["weight"]:.1f} кг x {s["reps"]}</span>'
        f'</div>'
        for s in warmup
    )
    st.markdown(
        f'<div class="warmup-table">'
        f'<div style="color:#7c8db0;font-size:0.78rem;text-transform:uppercase;'
        f'letter-spacing:0.08em;margin-bottom:8px;">Розминка до {working_weight:.1f} кг</div>'
        f'{rows}</div>',
        unsafe_allow_html=True
    )


def ui_cns_alert(reason):
    st.markdown(
        f'<div class="cns-alert"><h3>⚠️ Перевантаження!</h3><p>{reason}</p>'
        f'<p style="margin-top:8px;"><strong>Бро, ЦНС або суглоби перевантажені!</strong><br>'
        f'Рекомендується зробити легкий тиждень (Делоад) або знизити робочі ваги на 5–10%.</p></div>',
        unsafe_allow_html=True
    )


def ui_day_card(title, subtitle, weight, scheme):
    st.markdown(
        f'<div class="day-card"><div class="day-title">{title}</div>'
        f'<div class="day-sub">{subtitle}</div>'
        f'<div class="day-weight">{weight:.1f} кг</div>'
        f'<div class="day-scheme">{scheme}</div></div>',
        unsafe_allow_html=True
    )


def ui_extra_card(title, items):
    items_html = "".join(f'<div class="extra-item">• {i}</div>' for i in items)
    st.markdown(
        f'<div class="extra-card"><div class="extra-title">{title}</div>{items_html}</div>',
        unsafe_allow_html=True
    )


# ==================================================================
# ГОЛОВНИЙ ДОДАТОК
# ==================================================================

def main():
    init_db()

    st.markdown(
        '<div style="padding: 24px 0 8px 0;">'
        '<div class="hero-title">🏋️ <span class="hero-accent">Техаський</span> Метод</div>'
        '<div class="hero-sub">Трекер силового прогресу · Присід · Жим · Станова</div></div>',
        unsafe_allow_html=True
    )
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "⚙️ Налаштування / 1RM",
        "📅 Планування",
        "📓 Журнал",
        "📈 Аналітика"
    ])

    # ─── ВКЛ. 1 — НАЛАШТУВАННЯ ТА 1RM ─────────────────────────
    with tab1:
        st.markdown("### ⚙️ Налаштування залу")

        step_options = {"1 кг": 1.0, "2.5 кг": 2.5, "5 кг": 5.0}
        saved_step = load_setting("weight_step", "2.5 кг")
        col_s, _ = st.columns([1, 2])
        with col_s:
            step_label = st.selectbox(
                "Крок блінів у залі",
                options=list(step_options.keys()),
                index=list(step_options.keys()).index(saved_step) if saved_step in step_options else 1,
                help="Всі робочі ваги округляються вниз до цього кратного"
            )
            if st.button("💾 Зберегти"):
                save_setting("weight_step", step_label)
                st.success("Збережено!")

        current_step = step_options[step_label]

        st.markdown("---")
        st.markdown("### 🔢 Калькулятор 1RM — формула Бржицькі")
        st.markdown("> `1RM = Вага / (1.0278 - 0.0278 × Повторень)` — точна для 2–10 повт.")

        col_c1, col_c2, _ = st.columns([1, 1, 2])
        with col_c1:
            calc_weight = st.number_input(
                "Вага (кг)", min_value=0.0, max_value=500.0,
                value=100.0, step=current_step, format="%.1f"
            )
        with col_c2:
            calc_reps = st.number_input("Повторень", min_value=1, max_value=20, value=5, step=1)

        if calc_weight > 0 and calc_reps > 0:
            orm   = calc_1rm_brzycki(calc_weight, int(calc_reps))
            orm_r = round_to_step(orm, current_step)

            c1, c2, c3, c4 = st.columns(4)
            with c1: ui_metric_card("Розрахунковий 1RM", f"{orm:.1f} кг")
            with c2: ui_metric_card(f"1RM округлений ({current_step} кг)", f"{orm_r:.1f} кг")
            with c3: ui_metric_card("85% — Понеділок", f"{round_to_step(orm * 0.85, current_step):.1f} кг")
            with c4: ui_metric_card("70% — Середа", f"{round_to_step(orm * 0.70, current_step):.1f} кг")

            st.markdown("---")
            st.markdown("#### 🔥 Розминка до округленого 1RM")
            ui_warmup_table(calc_warmup(orm_r, current_step), orm_r)

    # ─── ВКЛ. 2 — ПЛАНУВАННЯ ──────────────────────────────────
    with tab2:
        st.markdown("### 📅 Планування тижня")

        step_p = step_options[load_setting("weight_step", "2.5 кг")]

        # Вибір додаткової вправи на Понеділок
        saved_extra = load_setting("extra_mon", EXTRA_MON[0])
        extra_choice = st.radio(
            "Додаткова вправа Понеділка:",
            options=EXTRA_MON,
            index=EXTRA_MON.index(saved_extra) if saved_extra in EXTRA_MON else 0,
            horizontal=True
        )
        if extra_choice != saved_extra:
            save_setting("extra_mon", extra_choice)

        st.markdown("---")

        # Секція для кожної базової вправи
        for exercise in MAIN_EXERCISES:
            with st.expander(f"🏋️ {exercise}", expanded=True):
                overload, reason = check_cns_overload(exercise)
                if overload:
                    ui_cns_alert(reason)

                last = get_last_friday_record(exercise)
                default_fri = float(last[0]) if last else 60.0

                cf1, cf2, cf3 = st.columns([2, 1, 1])
                with cf1:
                    fri_w = st.number_input(
                        "П'ятничний рекорд (кг)", min_value=0.0, max_value=600.0,
                        value=default_fri, step=step_p, format="%.1f",
                        key=f"fri_w_{exercise}"
                    )
                with cf2:
                    fri_r = st.number_input("Повторень", min_value=1, max_value=10, value=5,
                                            key=f"fri_r_{exercise}")
                with cf3:
                    fri_date = st.date_input("Дата", value=date.today(), key=f"fri_d_{exercise}")
                    if st.button("💾 Зафіксувати", key=f"fri_save_{exercise}"):
                        insert_friday_record(str(fri_date), exercise, fri_w, int(fri_r))
                        st.success(f"Рекорд {fri_w:.1f} кг × {fri_r} збережено!")
                        st.rerun()

                if fri_w > 0:
                    vol_w = calc_volume_weight(fri_w, step_p)
                    rec_w = calc_recovery_weight(fri_w, step_p)
                    nxt_w = round_to_step(fri_w + step_p, step_p)

                    cd1, cd2, cd3 = st.columns(3)
                    with cd1:
                        ui_day_card("Понеділок", "ОБ'ЄМ", vol_w, "5 підходів x 5 повторень (85%)")
                    with cd2:
                        ui_day_card("Середа", "ВІДНОВЛЕННЯ", rec_w, "3 підходи x 5 повторень (70%)")
                    with cd3:
                        ui_day_card("П'ятниця", "ІНТЕНСИВНІСТЬ", fri_w,
                                    f"1 підхід x 5 · ціль → {nxt_w:.1f} кг")

                    st.markdown("")
                    wu_day = st.radio(
                        "Розминка для дня:", ["Понеділок", "Середа", "П'ятниця"],
                        horizontal=True, key=f"wu_day_{exercise}"
                    )
                    wday_w = {"Понеділок": vol_w, "Середа": rec_w, "П'ятниця": fri_w}[wu_day]
                    ui_warmup_table(calc_warmup(wday_w, step_p), wday_w)

        st.markdown("---")
        st.markdown("### 📋 Структура тижня")

        ca, cb, cc = st.columns(3)
        with ca:
            ui_extra_card("Понеділок — Структура", [
                "Присід 5x5 (85%)",
                "Жим лежачи 5x5 (85%)",
                f"{extra_choice} — 3x8–10"
            ])
        with cb:
            ui_extra_card("Середа — Структура", [
                "Присід 3x5 легкий (70%)",
                "Жим лежачи 3x5 легкий (70%)",
                "Cable Crunch — 3x12–15",
                "Маятник / Кругові підйоми — 3x12"
            ])
        with cc:
            ui_extra_card("П'ятниця — Структура", [
                "Присід 1x5 (рекорд)",
                "Жим лежачи 1x5 (рекорд)",
                "Станова тяга 1x5 (рекорд)"
            ])

    # ─── ВКЛ. 3 — ЖУРНАЛ ──────────────────────────────────────
    with tab3:
        st.markdown("### 📓 Журнал тренувань")

        step_j = step_options[load_setting("weight_step", "2.5 кг")]

        with st.expander("➕ Додати запис", expanded=True):
            cj1, cj2 = st.columns(2)
            with cj1:
                j_date     = st.date_input("Дата", value=date.today(), key="j_date")
                j_exercise = st.selectbox("Вправа", ALL_EXERCISES, key="j_ex")
                j_day_type = st.selectbox("День", DAYS, key="j_day")
            with cj2:
                j_weight = st.number_input(
                    "Вага (кг)", min_value=0.0, max_value=600.0,
                    value=100.0, step=step_j, format="%.1f", key="j_w"
                )
                jc1, jc2_cols = st.columns(2)
                with jc1:
                    j_reps = st.number_input("Повторень", min_value=1, max_value=30, value=5, key="j_reps")
                with jc2_cols:
                    j_sets = st.number_input("Підходів", min_value=1, max_value=10, value=5, key="j_sets")

            j_tag     = st.selectbox("Тег самопочуття", ["—"] + TAGS, key="j_tag")
            j_comment = st.text_area("Коментар", key="j_com", height=70)

            if st.button("💾 Зберегти тренування"):
                tag_val = j_tag if j_tag != "—" else None
                insert_workout(
                    str(j_date), j_exercise, j_day_type,
                    j_weight, int(j_reps), int(j_sets),
                    tag_val, j_comment.strip() or None
                )
                # Автозбереження П'ятничного рекорду для базових вправ
                if "П'ятниця" in j_day_type and j_exercise in MAIN_EXERCISES:
                    insert_friday_record(str(j_date), j_exercise, j_weight, int(j_reps))
                    st.info("📌 П'ятничний рекорд збережено автоматично!")

                st.success("✅ Тренування збережено!")

                # Перевірка ЦНС одразу після збереження
                if j_exercise in MAIN_EXERCISES:
                    ov, rsn = check_cns_overload(j_exercise)
                    if ov:
                        ui_cns_alert(rsn)

                st.rerun()

        st.markdown("---")
        df = get_all_workouts()

        if df.empty:
            st.info("Журнал порожній. Додайте перше тренування! 💪")
        else:
            fc1, fc2 = st.columns(2)
            with fc1:
                f_ex  = st.multiselect("Фільтр: вправа", ALL_EXERCISES)
            with fc2:
                f_tag = st.multiselect("Фільтр: тег", TAGS)

            view = df.copy()
            if f_ex:  view = view[view["exercise"].isin(f_ex)]
            if f_tag: view = view[view["tag"].isin(f_tag)]

            view["1RM (розр.)"] = view.apply(
                lambda r: f"{calc_1rm_brzycki(r['weight'], r['reps']):.1f}"
                if r["exercise"] in MAIN_EXERCISES else "—",
                axis=1
            )
            rename = {
                "date": "Дата", "exercise": "Вправа", "day_type": "День",
                "weight": "Вага", "reps": "Повт.", "sets": "Підх.",
                "tag": "Тег", "comment": "Коментар", "1RM (розр.)": "1RM"
            }
            view = view.rename(columns=rename)[[v for v in rename.values()]]
            st.dataframe(view, use_container_width=True, hide_index=True, height=420)
            st.caption(f"Записів: **{len(view)}**")

    # ─── ВКЛ. 4 — АНАЛІТИКА ───────────────────────────────────
    with tab4:
        st.markdown("### 📈 Аналітика прогресу")

        df_all = get_all_workouts()
        if df_all.empty:
            st.info("Немає даних. Почніть вести журнал! 💪")
        else:
            anal_ex = st.selectbox("Вправа для аналізу", MAIN_EXERCISES, key="anal_ex")

            df_ex = df_all[df_all["exercise"] == anal_ex].copy()
            df_ex["date"] = pd.to_datetime(df_ex["date"])
            df_ex = df_ex.sort_values("date")
            df_ex["calc_1rm"] = df_ex.apply(
                lambda r: calc_1rm_brzycki(r["weight"], r["reps"]), axis=1
            )

            df_fri = get_friday_records(anal_ex)
            if not df_fri.empty:
                df_fri["date"] = pd.to_datetime(df_fri["date"])
                df_fri = df_fri.sort_values("date")

            fig = go.Figure()
            if not df_ex.empty:
                fig.add_trace(go.Scatter(
                    x=df_ex["date"], y=df_ex["calc_1rm"],
                    mode="lines+markers", name="Розрахунковий 1RM",
                    line=dict(color="#3b82f6", width=2), marker=dict(size=6),
                    hovertemplate="<b>%{x|%d.%m.%Y}</b><br>1RM: %{y:.1f} кг<extra></extra>"
                ))
            if not df_fri.empty:
                fig.add_trace(go.Scatter(
                    x=df_fri["date"], y=df_fri["weight"],
                    mode="lines+markers", name="Рекорд П'ятниці (факт)",
                    line=dict(color="#e85d04", width=2.5),
                    marker=dict(size=11, symbol="star"),
                    hovertemplate="<b>%{x|%d.%m.%Y}</b><br>Рекорд: %{y:.1f} кг<extra></extra>"
                ))

            fig.update_layout(
                title=dict(text=f"Прогрес: {anal_ex}", font=dict(size=18, color="#f0f4ff")),
                paper_bgcolor="#111827", plot_bgcolor="#1a1d27",
                font=dict(color="#94a3b8"),
                legend=dict(bgcolor="#1a1d27", bordercolor="#2a2d3e", borderwidth=1),
                xaxis=dict(gridcolor="#2a2d3e", tickformat="%d.%m.%y"),
                yaxis=dict(gridcolor="#2a2d3e", title="кг"),
                hovermode="x unified", height=420
            )
            st.plotly_chart(fig, use_container_width=True)

            if not df_ex.empty:
                st.markdown("#### 📊 Статистика")
                s1, s2, s3, s4 = st.columns(4)
                with s1: ui_metric_card("Тренувань", str(len(df_ex)))
                with s2: ui_metric_card("Макс. вага", f"{df_ex['weight'].max():.1f} кг")
                with s3: ui_metric_card("Макс. 1RM", f"{df_ex['calc_1rm'].max():.1f} кг")
                with s4:
                    delta = df_ex["calc_1rm"].iloc[-1] - df_ex["calc_1rm"].iloc[0]
                    sign  = "+" if delta >= 0 else ""
                    ui_metric_card("Приріст 1RM", f"{sign}{delta:.1f} кг")

            df_tags = df_ex[df_ex["tag"].notna()] if not df_ex.empty else pd.DataFrame()
            if not df_tags.empty:
                st.markdown("#### 🏷️ Теги самопочуття")
                tc = df_tags["tag"].value_counts().reset_index()
                tc.columns = ["Тег", "К-сть"]
                fig_t = px.bar(tc, x="Тег", y="К-сть", color="К-сть",
                               color_continuous_scale=["#1e3a5f", "#e85d04"])
                fig_t.update_layout(
                    paper_bgcolor="#111827", plot_bgcolor="#1a1d27",
                    font=dict(color="#94a3b8"), height=280,
                    showlegend=False, coloraxis_showscale=False
                )
                st.plotly_chart(fig_t, use_container_width=True)

            st.markdown("---")
            st.markdown("#### 💾 Експорт даних")
            ce1, ce2 = st.columns(2)
            with ce1:
                csv_data = df_all.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    "⬇️ Завантажити CSV",
                    data=csv_data.encode("utf-8-sig"),
                    file_name=f"texas_method_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            with ce2:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df_all.to_excel(writer, sheet_name="Журнал", index=False)
                    for ex in MAIN_EXERCISES:
                        sub = df_all[df_all["exercise"] == ex]
                        if not sub.empty:
                            sub.to_excel(writer, sheet_name=ex[:31], index=False)
                st.download_button(
                    "⬇️ Завантажити Excel (.xlsx)",
                    data=buf.getvalue(),
                    file_name=f"texas_method_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )


# ==================================================================
if __name__ == "__main__":
    main()

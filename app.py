import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
import re
import time
import shutil

# ------------------ تنظیمات اولیه و پوشه‌بندی ------------------
st.set_page_config(page_title="سیستم جامع ارزیابی و تایم‌لاین نسخ درمانگاه", layout="wide")

PERIODS_DIR = "periods_data"
SETTINGS_FILE = "system_settings.json"

def init_storage():
    """ایجاد ساختار پوشه‌ها و فایل‌های پایه"""
    if not os.path.exists(PERIODS_DIR):
        os.makedirs(PERIODS_DIR)

init_storage()

# ------------------ تابع هوشمند پاکسازی و تطبیق اسامی ------------------
def clean_name(text):
    if not text or pd.isna(text):
        return ""
    text = str(text).strip()
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    
    prefix_pattern = r'^(دکتر|خانم|آقای|آقا|اقای|مهندس|پزشک)\b\s*'
    while re.search(prefix_pattern, text, flags=re.IGNORECASE):
        text = re.sub(prefix_pattern, '', text, flags=re.IGNORECASE).strip()
        
    return " ".join(text.split())

# ------------------ موتور خوانش هوشمند فایل‌های اکسل/HTML/CSV ------------------
def read_uploaded_file(uploaded_file):
    """خوانش هوشمند انواع فایل اکسل (xlsx, xls, html-excel, csv)"""
    try:
        try:
            df = pd.read_excel(uploaded_file)
        except Exception:
            uploaded_file.seek(0)
            try:
                df = pd.read_excel(uploaded_file, engine='openpyxl')
            except Exception:
                uploaded_file.seek(0)
                try:
                    df = pd.read_html(uploaded_file)[0]
                except Exception:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file)
        
        df = df.dropna(how='all')
        return df, None
    except Exception as e:
        return None, str(e)

# ------------------ مدیریت ذخیره و فراخوانی داده‌های دوره‌ها ------------------
META_FILE = os.path.join(PERIODS_DIR, "periods_meta.json")

def get_periods_meta():
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_periods_meta(meta_data):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta_data, f, ensure_ascii=False, indent=4)

def create_period(period_name):
    periods = get_periods_meta()
    period_id = f"p_{int(time.time() * 1000)}"
    new_period = {
        "id": period_id,
        "name": period_name,
        "created_at": time.time(),
        "created_date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    }
    periods.append(new_period)
    save_periods_meta(periods)
    
    p_dir = os.path.join(PERIODS_DIR, period_id)
    os.makedirs(p_dir, exist_ok=True)
    return period_id

def delete_period(period_id):
    periods = get_periods_meta()
    periods = [p for p in periods if p["id"] != period_id]
    save_periods_meta(periods)
    
    p_dir = os.path.join(PERIODS_DIR, period_id)
    if os.path.exists(p_dir):
        shutil.rmtree(p_dir)

def save_period_data(period_id, file_type, df):
    p_dir = os.path.join(PERIODS_DIR, period_id)
    os.makedirs(p_dir, exist_ok=True)
    csv_path = os.path.join(p_dir, f"{file_type}.csv")
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')

def load_period_data(period_id, file_type):
    p_dir = os.path.join(PERIODS_DIR, period_id)
    csv_path = os.path.join(p_dir, f"{file_type}.csv")
    xlsx_path = os.path.join(p_dir, f"{file_type}.xlsx")
    
    target_path = None
    if os.path.exists(csv_path):
        target_path = csv_path
    elif os.path.exists(xlsx_path):
        target_path = xlsx_path
        
    if not target_path:
        return None, "فایل ثبت نشده است."
        
    try:
        if target_path.endswith('.csv'):
            df = pd.read_csv(target_path, encoding='utf-8-sig')
        else:
            try:
                df = pd.read_excel(target_path)
            except Exception:
                df = pd.read_html(target_path)[0]
                
        if df is not None and not df.empty:
            first_col = df.columns[0]
            df[first_col] = df[first_col].apply(clean_name)
        return df, None
    except Exception as e:
        return None, f"خطا در خوانش فایل: {str(e)}"

# ------------------ تنظیمات عمومی ------------------
def save_settings():
    settings = {
        "passwords": st.session_state.doctor_passwords,
        "general_notes": st.session_state.admin_general_notes,
        "doctor_notes": st.session_state.admin_doctor_notes,
        "metric_settings": st.session_state.get("metric_settings", {})
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                st.session_state.doctor_passwords = settings.get("passwords", {})
                st.session_state.admin_general_notes = settings.get("general_notes", "")
                st.session_state.admin_doctor_notes = settings.get("doctor_notes", {})
                st.session_state.metric_settings = settings.get("metric_settings", {})
        except Exception:
            pass

def calculate_ranks(df, metrics):
    df_ranks = df.copy()
    metric_settings = st.session_state.get("metric_settings", {})
    for col in metrics:
        numeric_col = pd.to_numeric(df[col], errors='coerce')
        m_set = metric_settings.get(col, {})
        direction = m_set.get("direction", "")
        
        if direction == "بیشتر بهتر":
            ascending = False
        elif direction == "کمتر بهتر":
            ascending = True
        else:
            if "ویزیت" in col or "آزمایشگاه" in col or "نسخ" in col:
                ascending = False
            else:
                ascending = True
                
        ranks = numeric_col.rank(ascending=ascending, method='min')
        df_ranks[col] = ranks.fillna(0).astype(int)
    return df_ranks

# ------------------ توابع دسته‌بندی و فیلتر داروها ------------------
def classify_drug(drug_name):
    name_lower = str(drug_name).strip().lower()
    
    exclude_keywords = ['oint', 'ointment', 'پماد', 'gel', 'ژل', 'drop', 'drops', 'قطره']
    is_excluded_form = any(k in name_lower for k in exclude_keywords)
    
    oral_prefixes = ['tab', 'cap', 'syru', 'susp', 'syrup', 'قرص', 'کپسول', 'شربت', 'ساسپنشن']
    is_oral = any(name_lower.startswith(p) or f" {p}" in name_lower for p in oral_prefixes)
    
    inj_gen_prefixes = ['inj', 'infusion', 'solution', 'amp', 'vial', 'تزریقی', 'آمپول']
    is_inj_gen = any(name_lower.startswith(p) or f" {p}" in name_lower or f"{p} " in name_lower for p in inj_gen_prefixes)
    
    is_inj_strict = 'inj' in name_lower or 'آمپول' in name_lower
    
    abx_keywords = [
        'amox', 'amoxicillin', 'ampicillin', 'cef', 'ceph', 'azithro', 'azithromycin',
        'cipro', 'ciprofloxacin', 'levo', 'levofloxacin', 'metronidazole', 'flagyl',
        'co-amox', 'amox-clav', 'penicillin', 'pen', 'genta', 'gentamicin', 'vanco',
        'doxy', 'doxycycline', 'erythro', 'erythromycin', 'clarithro', 'clarithromycin',
        'cotrim', 'co-trimoxazole', 'cefixim', 'cefixime', 'cephalexin', 'ceftriaxon',
        'ceftriaxone', 'cefazolin', 'clinda', 'clindamycin', 'meropenem', 'imipenem',
        'nitrofurantoin'
    ]
    is_abx = (not is_excluded_form) and any(k in name_lower for k in abx_keywords)
    
    nsaid_keywords = [
        'ibuprofen', 'gelofen', 'indomethacin', 'diclofenac', 'naproxen',
        'meloxicam', 'piroxicam', 'celecoxib', 'mefenamic', 'aspirin',
        'ketorolac', 'ketoprofen', 'flurbiprofen', 'tenoxicam', 'nimesulide',
        'پروفن', 'ژلوفن', 'دیکلوفناک', 'ناپروکسن', 'مفنامیک'
    ]
    is_nsaid = (not is_excluded_form) and any(k in name_lower for k in nsaid_keywords)
    
    cortico_keywords = [
        'dexa', 'dexamethasone', 'beta', 'betamethasone', 'hydrocortisone',
        'prednisolone', 'prednisone', 'triamcinolone', 'methylprednisolone',
        'budesonide', 'fluticasone', 'clobetasol', 'mometasone', 'cortison',
        'دگزا', 'بتامتازون', 'هیدروکورتیزون', 'پرنیزولون', 'تریامسینولون'
    ]
    is_cortico = (not is_excluded_form) and any(k in name_lower for k in cortico_keywords)
    
    return {
        "oral": is_oral,
        "inj_gen": is_inj_gen,
        "inj_strict": is_inj_strict,
        "abx": is_abx,
        "nsaid": is_nsaid,
        "cortico": is_cortico
    }

def filter_drug_list(drugs_list, category):
    result = []
    for d in drugs_list:
        info = classify_drug(d)
        if category == "همه اشکال":
            result.append(d)
        elif category == "خوراکی (Tab, Cap, Syru, Susp)" and info["oral"]:
            result.append(d)
        elif category == "تزریقی عمومی (Inj, Infusion, Solution)" and info["inj_gen"]:
            result.append(d)
        elif category == "فقط تزریقی (Inj)" and info["inj_strict"]:
            result.append(d)
        elif category in ["آنتی‌بیوتیک‌ها (بدون Oint, Gel, Drop)", "مجموع آنتی‌بیوتیک‌ها"] and info["abx"]:
            result.append(d)
        elif category in ["مسکن‌های NSAID (بدون Oint, Gel, Drop)", "مجموع NSAIDها"] and info["nsaid"]:
            result.append(d)
        elif category in ["کورتیکواستروئیدها (بدون Oint, Gel, Drop)", "مجموع کورتیکواستروئیدها"] and info["cortico"]:
            result.append(d)
        elif category == "مجموع تزریقی‌ها" and info["inj_gen"]:
            result.append(d)
    return result

def get_clinical_guideline(metric_name, user_val, avg_val):
    metric_lower = metric_name.lower()
    if any(kw in metric_lower for kw in ['آنتی', 'بیوتیک', 'چرك', 'عفونت', 'کپسول']):
        return (
            "🦠 **گایدلاین مدیریت تجویز آنتی‌بیوتیک (CDC & WHO Antibiotic Stewardship):**\n\n"
            "طبق گزارش‌های سازمان جهانی بهداشت (WHO) و CDC، بیش از ۶۰ تا ۷۰ درصد عفونت‌های حاد تنفسی فوقانی در مراقبت‌های سرپایی منشأ ویروسی دارند و نیازی به دریافت آنتی‌بیوتیک ندارند. "
            "توصیه می‌شود در مواجهه با علائم تنفسی خفیف تا متوسط، از الگوریتم طبقه‌بندی **AWaRe** استفاده کرده و درمان‌های حمایتی را در اولویت قرار دهید."
        )
    elif any(kw in metric_lower for kw in ['تزریق', 'آمپول', 'ویال']):
        return (
            "💉 **راهنمای تجویز منطقی داروهای تزریقی (WHO Injection Safety Guidelines):**\n\n"
            "بر اساس استانداردهای WHO، اولویت اول در بیماران سرپایی همواره با **مسیر خوراکی** است. زیست‌دست‌یابی اکثر داروهای خوراکی مدرن برابری لازم با فرم تزریقی را دارد."
        )
    elif any(kw in metric_lower for kw in ['کورتون', 'استروئید', 'دگزا', 'بتامتازون', 'هیدروکورتیزون']):
        return (
            "🛡️ **گایدلاین بالینی مصرف کورتیکواستروئیدها (NICE & WHO):**\n\n"
            "تجویز بی‌رویه کورتون‌های سیستمیک در بیماری‌های ویروسی شایع، علاوه بر تضعیف سیستم ایمنی، خطر عوارض متابولیک و اختلالات هورمونی را افزایش می‌دهد."
        )
    else:
        return (
            f"📖 **توصیه علمی بر اساس پزشکی مبتنی بر شواهد (EBM) در شاخص {metric_name}:**\n\n"
            f"میزان تجویز شما در شاخص **{metric_name}** با میانگین استاندارد درمانگاه فاصله دارد."
        )

# ------------------ وضعیت نشست (Session State) ------------------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'doctor_name' not in st.session_state:
    st.session_state.doctor_name = None
if 'active_period_id' not in st.session_state:
    st.session_state.active_period_id = None
if 'doctor_passwords' not in st.session_state:
    st.session_state.doctor_passwords = {}
if 'admin_general_notes' not in st.session_state:
    st.session_state.admin_general_notes = ""
if 'admin_doctor_notes' not in st.session_state:
    st.session_state.admin_doctor_notes = {}
if 'metric_settings' not in st.session_state:
    st.session_state.metric_settings = {}

load_settings()

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
DOCTOR_DEFAULT_PASSWORD = "1234"

filter_options = [
    "همه اشکال", 
    "خوراکی (Tab, Cap, Syru, Susp)", 
    "تزریقی عمومی (Inj, Infusion, Solution)",
    "فقط تزریقی (Inj)",
    "آنتی‌بیوتیک‌ها (بدون Oint, Gel, Drop)",
    "مسکن‌های NSAID (بدون Oint, Gel, Drop)",
    "کورتیکواستروئیدها (بدون Oint, Gel, Drop)",
    "مجموع آنتی‌بیوتیک‌ها",
    "مجموع تزریقی‌ها",
    "مجموع کورتیکواستروئیدها",
    "مجموع NSAIDها"
]

# ------------------ صفحه ورود (Login Screen) ------------------
if not st.session_state.logged_in:
    st.title("🔑 ورود به سیستم جامع ارزیابی و تایم‌لاین نسخ درمانگاه")
    login_type = st.radio("نوع ورود را انتخاب کنید:", ["ورود پزشک 👤", "ورود مدیر / ادمین 🛠️"], horizontal=True)
    st.markdown("---")
    
    if login_type == "ورود مدیر / ادمین 🛠️":
        st.subheader("ورود مدیر سیستم")
        username = st.text_input("نام کاربری ادمین")
        password = st.text_input("رمز عبور ادمین", type="password")
        
        if st.button("ورود به عنوان مدیر", type="primary"):
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state.logged_in = True
                st.session_state.user_role = "admin"
                st.success("ورود موفقیت‌آمیز مدیر")
                st.rerun()
            else:
                st.error("نام کاربری یا رمز عبور ادمین اشتباه است.")
    else:
        st.subheader("ورود اختصاصی پزشک")
        selected_doc = st.text_input("نام و نام خانوادگی پزشک:")
        doc_password = st.text_input("رمز عبور اختصاصی (پیش‌فرض: 1234)", type="password")
        
        if st.button("ورود به پنل پزشک", type="primary"):
            target_doc = clean_name(selected_doc)
            if not target_doc:
                st.error("لطفاً نام خود را وارد کنید.")
            else:
                expected_password = st.session_state.doctor_passwords.get(target_doc, DOCTOR_DEFAULT_PASSWORD)
                if doc_password == expected_password:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "doctor"
                    st.session_state.doctor_name = target_doc
                    st.success(f"خوش آمدید {target_doc}")
                    st.rerun()
                else:
                    st.error("رمز عبور اشتباه است.")

# ------------------ پنل اصلی پس از ورود ------------------
else:
    periods_meta = get_periods_meta()
    periods_meta = sorted(periods_meta, key=lambda x: x.get("created_at", 0))

    with st.sidebar:
        st.write(f"👤 **کاربر:** {st.session_state.doctor_name if st.session_state.user_role == 'doctor' else 'مدیر سیستم'}")
        st.write(f"پست: {'پزشک' if st.session_state.user_role == 'doctor' else 'مدیر ارشد'}")
        st.markdown("---")
        
        if st.session_state.active_period_id:
            active_p_info = next((p for p in periods_meta if p["id"] == st.session_state.active_period_id), None)
            if active_p_info:
                st.success(f"📌 **دوره فعال:** {active_p_info['name']}")
                if st.button("🔙 خروج از دوره / بازگشت به تایم‌لاین"):
                    st.session_state.active_period_id = None
                    st.rerun()
            st.markdown("---")

        if st.button("خروج از حساب کاربری 🚪"):
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.session_state.doctor_name = None
            st.session_state.active_period_id = None
            st.rerun()

    # =============================================================
    # ۱. بخش مدیر سیستم (ADMIN)
    # =============================================================
    if st.session_state.user_role == "admin":
        
        if not st.session_state.active_period_id:
            st.title("🗓️ صفحه مدیریت دوره‌ها و تحلیل تایم‌لاین (Timeline)")
            
            tab_manage, tab_timeline = st.tabs(["📂 انتخاب و ایجاد دوره ارزیابی", "📈 تایم‌لاین و تحلیل روند (Timeline)"])

            with tab_manage:
                col_left, col_right = st.columns([1, 1])

                with col_left:
                    st.subheader("➕ ایجاد دوره جدید")
                    new_p_name = st.text_input("نام دوره جدید", placeholder="مثال: شهریور 1405")
                    if st.button("🚀 ساخت و ورود به دوره جدید", type="primary"):
                        if new_p_name.strip():
                            new_id = create_period(new_p_name.strip())
                            st.session_state.active_period_id = new_id
                            st.success(f"دوره «{new_p_name}» با موفقیت ساخته شد.")
                            st.rerun()
                        else:
                            st.error("لطفاً نام دوره را وارد کنید.")

                with col_right:
                    st.subheader("📋 ورود به دوره‌های موجود")
                    if not periods_meta:
                        st.info("هنوز هیچ دوره‌ای ثبت نشده است.")
                    else:
                        p_options = {p["name"]: p["id"] for p in periods_meta}
                        selected_p_name = st.selectbox("یک دوره را جهت بررسی یا اصلاح انتخاب کنید:", list(p_options.keys()))
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("🔑 ورود به دوره انتخاب شده", type="primary"):
                                st.session_state.active_period_id = p_options[selected_p_name]
                                st.rerun()
                        with c2:
                            with st.popover("🗑️ حذف این دوره"):
                                st.warning(f"آیا از حذف کامل دوره «{selected_p_name}» مطمئن هستید؟")
                                if st.button("بله، دوره حذف شود", type="secondary"):
                                    delete_period(p_options[selected_p_name])
                                    st.success("دوره با موفقیت حذف شد.")
                                    st.rerun()

            with tab_timeline:
                st.header("📊 مقایسه روند عملکرد در طول زمان (Timeline)")

                if len(periods_meta) < 2:
                    st.info("💡 برای مشاهده تایم‌لاین و نمودارهای مقایسه‌ای روند، حداقل نیاز به ۲ دوره بارگذاری‌شده دارید.")
                else:
                    all_period_names = [p["name"] for p in periods_meta]
                    c_start, c_end = st.columns(2)
                    with c_start:
                        start_p_name = st.selectbox("از دوره (شروع):", all_period_names, index=0)
                    with c_end:
                        end_p_name = st.selectbox("تا دوره (پایان):", all_period_names, index=len(all_period_names)-1)

                    idx_start = all_period_names.index(start_p_name)
                    idx_end = all_period_names.index(end_p_name)

                    if idx_start > idx_end:
                        st.error("دوره شروع نباید بعد از دوره پایان باشد.")
                    else:
                        selected_periods_in_range = periods_meta[idx_start : idx_end + 1]
                        timeline_records = []
                        all_metrics_set = set()

                        for p in selected_periods_in_range:
                            df_p, err_p = load_period_data(p["id"], "main")
                            if df_p is not None and not df_p.empty:
                                doc_col = df_p.columns[0]
                                metrics_p = df_p.columns[1:]
                                
                                for m in metrics_p:
                                    all_metrics_set.add(m)
                                    for _, row in df_p.iterrows():
                                        val = pd.to_numeric(row[m], errors='coerce')
                                        if not pd.isna(val):
                                            timeline_records.append({
                                                "دوره": p["name"],
                                                "پزشک": row[doc_col],
                                                "شاخص": m,
                                                "مقدار": val,
                                                "timestamp": p["created_at"]
                                            })

                        if not timeline_records:
                            st.warning("هیچ فایلی در دوره‌های انتخابی برای استخراج تایم‌لاین پیدا نشد.")
                        else:
                            df_timeline = pd.DataFrame(timeline_records)
                            metrics_list = sorted(list(all_metrics_set))

                            selected_timeline_metric = st.selectbox("📌 انتخاب شاخص جهت بررسی روند تایم‌لاین:", metrics_list)
                            df_metric = df_timeline[df_timeline["شاخص"] == selected_timeline_metric]

                            chart_type = st.radio("نوع نمودار مقایسه‌ای:", ["نمودار خطی روند (Line Chart)", "نمودار میله‌ای گروهی (Bar Chart)"], horizontal=True)

                            if chart_type == "نمودار خطی روند (Line Chart)":
                                fig_timeline = px.line(
                                    df_metric,
                                    x="دوره",
                                    y="مقدار",
                                    color="پزشک",
                                    markers=True,
                                    title=f"روند تغییرات شاخص «{selected_timeline_metric}» در طول زمان",
                                    labels={"مقدار": selected_timeline_metric, "دوره": "دوره ارزیابی"}
                                )
                            else:
                                fig_timeline = px.bar(
                                    df_metric,
                                    x="دوره",
                                    y="مقدار",
                                    color="پزشک",
                                    barmode="group",
                                    title=f"مقایسه میله‌ای شاخص «{selected_timeline_metric}» در دوره‌ها",
                                    labels={"مقدار": selected_timeline_metric, "دوره": "دوره ارزیابی"}
                                )

                            fig_timeline.update_layout(xaxis_type='category')
                            st.plotly_chart(fig_timeline, use_container_width=True)

                            st.subheader("📉 روند میانگین کل درمانگاه در طول زمان")
                            df_clinic_avg = df_metric.groupby("دوره")["مقدار"].mean().reset_index()
                            fig_avg = px.line(
                                df_clinic_avg,
                                x="دوره",
                                y="مقدار",
                                markers=True,
                                title=f"میانگین کل درمانگاه در شاخص «{selected_timeline_metric}»",
                                labels={"مقدار": "میانگین درمانگاه"}
                            )
                            fig_avg.update_traces(line_color="red", line_width=3)
                            fig_avg.update_layout(xaxis_type='category')
                            st.plotly_chart(fig_avg, use_container_width=True)

        # ------------------ حالت B: مدیریت داخل یک دوره مشخص ------------------
        else:
            active_p_id = st.session_state.active_period_id
            active_p_info = next((p for p in periods_meta if p["id"] == active_p_id), None)
            p_name = active_p_info["name"] if active_p_info else "نامشخص"

            st.title(f"📊 مدیریت دوره: `{p_name}`")

            df_main, err_main = load_period_data(active_p_id, "main")
            df_drugs, err_drugs = load_period_data(active_p_id, "drugs")

            tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
                "📁 بارگذاری فایل‌های دوره", 
                "📈 مقایسه کل پزشکان", 
                "👤 بررسی فردی پزشکان", 
                "💊 درصد دارو به پزشک", 
                "📋 دارو به نسخه/ویزیت",
                "⚙️ تنظیمات شاخص‌ها",
                "📝 بازخوردهای مدیریت"
            ])

            # --- تب ۱: بارگذاری ---
            with tab1:
                st.header(f"📁 بارگذاری و جایگزینی فایل‌های دوره: {p_name}")
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    st.subheader("۱. اکسل شاخص‌های عمومی")
                    if df_main is not None:
                        st.success(f"✅ فایل عمومی این دوره بارگذاری شده است ({len(df_main)} ردیف).")
                    else:
                        st.info("فایلی برای شاخص‌های عمومی ثبت نشده است.")

                    up_main = st.file_uploader("بارگذاری / جایگزینی (Main Excel / CSV / HTML)", type=["xlsx", "xls", "csv", "html"], key="up_main_period")
                    if up_main is not None:
                        df_new, err_msg = read_uploaded_file(up_main)
                        if df_new is not None and not df_new.empty:
                            save_period_data(active_p_id, "main", df_new)
                            st.success("✅ فایل عمومی با موفقیت ذخیره شد.")
                            st.rerun()
                        else:
                            st.error(f"❌ خطا در خواندن فایل عمومی: {err_msg}")

                with col_u2:
                    st.subheader("۲. اکسل اقلام دارویی")
                    if df_drugs is not None:
                        st.success(f"✅ فایل دارویی این دوره بارگذاری شده است ({len(df_drugs)} ردیف).")
                    else:
                        st.info("فایلی برای اقلام دارویی ثبت نشده است.")

                    up_drugs = st.file_uploader("بارگذاری / جایگزینی (Drugs Excel / CSV / HTML)", type=["xlsx", "xls", "csv", "html"], key="up_drugs_period")
                    if up_drugs is not None:
                        df_d_new, err_d_msg = read_uploaded_file(up_drugs)
                        if df_d_new is not None and not df_d_new.empty:
                            save_period_data(active_p_id, "drugs", df_d_new)
                            st.success("✅ فایل اقلام دارویی با موفقیت ذخیره شد.")
                            st.rerun()
                        else:
                            st.error(f"❌ خطا در خواندن فایل دارویی: {err_d_msg}")

            # --- تب ۲: مقایسه کل ---
            with tab2:
                if df_main is not None:
                    doctor_col = df_main.columns[0]
                    metrics = df_main.columns[1:]
                    df_ranks = calculate_ranks(df_main, metrics)

                    st.subheader(f"مقایسه کلی تمام پزشکان ({p_name})")
                    selected_metric = st.selectbox("انتخاب شاخص:", metrics, key="tab2_m")
                    
                    # سورت نزولی داده‌ها بر اساس شاخص انتخاب شده
                    df_main_sorted = df_main.copy()
                    df_main_sorted[selected_metric] = pd.to_numeric(df_main_sorted[selected_metric], errors='coerce').fillna(0)
                    df_main_sorted = df_main_sorted.sort_values(by=selected_metric, ascending=False)

                    fig_bar = px.bar(
                        df_main_sorted, 
                        x=doctor_col, 
                        y=selected_metric, 
                        text_auto=True, 
                        color=selected_metric, 
                        color_continuous_scale="Viridis",
                        title=f"مقایسه پزشکان در شاخص {selected_metric} (مرتب‌شده از بزرگ به کوچک)"
                    )
                    fig_bar.update_xaxes(categoryorder='total descending')
                    st.plotly_chart(fig_bar, use_container_width=True)
                    
                    st.subheader("جدول رتبه‌بندی کلی")
                    st.dataframe(df_ranks.set_index(doctor_col))
                else:
                    st.warning("⚠️ لطفاً ابتدا فایل شاخص‌های عمومی را بارگذاری کنید.")

            # --- تب ۳: بررسی فردی ---
            with tab3:
                if df_main is not None:
                    doctor_col = df_main.columns[0]
                    metrics = df_main.columns[1:]
                    df_ranks = calculate_ranks(df_main, metrics)
                    doctors_list = df_main[doctor_col].dropna().unique().tolist()
                    
                    selected_doc = st.selectbox("انتخاب پزشک جهت بررسی:", doctors_list, key="tab3_doc")
                    doc_data = df_main[df_main[doctor_col] == selected_doc].iloc[0]
                    doc_ranks = df_ranks[df_ranks[doctor_col] == selected_doc].iloc[0]
                    
                    numeric_df = df_main[metrics].apply(pd.to_numeric, errors='coerce')
                    avg_data = numeric_df.mean()

                    st.subheader(f"📊 کارنامه بصری و تحلیلی: {selected_doc} ({p_name})")
                    
                    # ایجاد دیتافریم مقایسه‌ای برای رسم نمودار و جدول
                    doc_comp_list = []
                    for m in metrics:
                        val = pd.to_numeric(doc_data[m], errors='coerce')
                        val_num = val if not pd.isna(val) else 0
                        avg_val = round(avg_data[m], 2)
                        
                        doc_comp_list.append({
                            "شاخص": m,
                            "مقدار پزشک": val_num,
                            "میانگین درمانگاه": avg_val,
                            "رتبه": f"{doc_ranks[m]} از {len(df_main)}"
                        })
                    
                    df_doc_comp = pd.DataFrame(doc_comp_list)
                    df_doc_comp_sorted = df_doc_comp.sort_values(by="مقدار پزشک", ascending=False)

                    # نمودار مقایسه‌ای
                    df_chart_melt = pd.melt(df_doc_comp_sorted, id_vars=['شاخص'], value_vars=['مقدار پزشک', 'میانگین درمانگاه'], var_name='مرجع', value_name='مقدار')
                    fig_doc_individual = px.bar(
                        df_chart_melt,
                        x='شاخص',
                        y='مقدار',
                        color='مرجع',
                        barmode='group',
                        text_auto='.1f',
                        title=f"مقایسه تصویری شاخص‌های {selected_doc} با میانگین کل درمانگاه (مرتب‌شده از بزرگ به کوچک)"
                    )
                    fig_doc_individual.update_xaxes(categoryorder='total descending')
                    st.plotly_chart(fig_doc_individual, use_container_width=True)

                    # جدول عملکرد پزشک
                    st.subheader("📋 جدول خلاصه وضعیت شاخص‌ها")
                    st.dataframe(df_doc_comp_sorted, use_container_width=True, hide_index=True)

                else:
                    st.warning("⚠️ فایل شاخص‌های عمومی بارگذاری نشده است.")

            # --- تب ۴: درصد دارو به پزشک ---
            with tab4:
                st.header("💊 سهم و درصد تجویز داروها به تفکیک پزشک")
                if df_drugs is not None:
                    df_d = df_drugs.copy()
                    doc_c = df_d.columns[0]
                    drug_c = df_d.columns[1]
                    qty_c = df_d.columns[2]

                    df_d[qty_c] = pd.to_numeric(df_d[qty_c], errors='coerce').fillna(0)
                    df_d[drug_c] = df_d[drug_c].astype(str).str.strip()

                    drug_totals = df_d.groupby(drug_c)[qty_c].sum()
                    valid_drugs = drug_totals[drug_totals > 0].index.tolist()
                    df_filtered = df_d[df_d[drug_c].isin(valid_drugs)].copy()

                    if not valid_drugs:
                        st.warning("هیچ دارویی با مجموع تجویز بیشتر از صفر یافت نشد.")
                    else:
                        form_filter = st.radio("🔍 انتخاب فیلتر دسته‌بندی دارویی:", filter_options, horizontal=True, key="filter_tab4_p")
                        is_total_mode = form_filter in ["مجموع آنتی‌بیوتیک‌ها", "مجموع تزریقی‌ها", "مجموع کورتیکواستروئیدها", "مجموع NSAIDها"]
                        selectable_drugs = filter_drug_list(valid_drugs, form_filter)

                        if not selectable_drugs:
                            st.info("دارویی در دسته انتخابی یافت نشد.")
                        else:
                            if is_total_mode:
                                st.info(f"💡 مجموع کل {len(selectable_drugs)} قلم داروی شناسایی‌شده در دسته «{form_filter}» محاسبه شد.")
                                drug_df = df_filtered[df_filtered[drug_c].isin(selectable_drugs)]
                                target_title = form_filter
                            else:
                                selected_drug = st.selectbox("🔍 داروی مورد نظر را انتخاب یا سرچ کنید:", selectable_drugs, key="select_drug_tab4_p")
                                if selected_drug:
                                    drug_df = df_filtered[df_filtered[drug_c] == selected_drug]
                                    target_title = selected_drug
                                else:
                                    drug_df = None

                            if drug_df is not None and not drug_df.empty:
                                doc_grouped = drug_df.groupby(doc_c)[qty_c].sum().reset_index()
                                doc_grouped = doc_grouped[doc_grouped[qty_c] > 0]
                                
                                # مرتب‌سازی نزولی داده‌ها قبل از رسم نمودار
                                doc_grouped = doc_grouped.sort_values(by=qty_c, ascending=False)
                                
                                total_drug_qty = doc_grouped[qty_c].sum()
                                doc_grouped['درصد'] = (doc_grouped[qty_c] / total_drug_qty) * 100
                                doc_grouped['برچسب_نمودار'] = doc_grouped.apply(lambda r: f"{int(r[qty_c])} عدد ({r['درصد']:.1f}%)", axis=1)

                                fig_drug = px.bar(
                                    doc_grouped,
                                    x=doc_c,
                                    y=qty_c,
                                    text='برچسب_نمودار',
                                    color=qty_c,
                                    color_continuous_scale='Blues',
                                    title=f"توزیع درصد و تعداد تجویز {target_title} بین پزشکان (مرتب‌شده از بزرگ به کوچک)"
                                )
                                fig_drug.update_xaxes(categoryorder='total descending')
                                fig_drug.update_traces(textposition='outside')
                                st.plotly_chart(fig_drug, use_container_width=True)
                else:
                    st.warning("⚠️ فایل اقلام دارویی برای این دوره بارگذاری نشده است.")

            # --- تب ۵: دارو به ویزیت (همراه جدول تحلیلی جدید) ---
            with tab5:
                st.header("📋 میزان تجویز هر دارو به ازای هر ویزیت پزشک")
                if df_main is None or df_drugs is None:
                    st.error("⚠️ برای این محاسبه، بارگذاری هر دو فایل (عمومی و دارویی) الزامی است.")
                else:
                    doc_col_main = df_main.columns[0]
                    visit_col = st.selectbox("📌 ستون تعداد کل ویزیت‌ها:", options=df_main.columns[1:], key="visit_col_select_p")

                    df_d = df_drugs.copy()
                    doc_col_drug = df_d.columns[0]
                    drug_name_col = df_d.columns[1]
                    drug_qty_col = df_d.columns[2]

                    df_d[drug_qty_col] = pd.to_numeric(df_d[drug_qty_col], errors='coerce').fillna(0)
                    df_d[drug_name_col] = df_d[drug_name_col].astype(str).str.strip()

                    drug_totals = df_d.groupby(drug_name_col)[drug_qty_col].sum()
                    valid_drugs = drug_totals[drug_totals > 0].index.tolist()

                    form_filter = st.radio("🔍 فیلتر دسته‌بندی دارویی:", filter_options, horizontal=True, key="filter_tab5_p")
                    is_total_mode = form_filter in ["مجموع آنتی‌بیوتیک‌ها", "مجموع تزریقی‌ها", "مجموع کورتیکواستروئیدها", "مجموع NSAIDها"]
                    selectable_drugs = filter_drug_list(valid_drugs, form_filter)

                    if selectable_drugs:
                        if is_total_mode:
                            df_selected_drug = df_d[df_d[drug_name_col].isin(selectable_drugs)].copy()
                            target_title = form_filter
                        else:
                            selected_drug = st.selectbox("🔍 انتخاب دارو:", selectable_drugs, key="select_drug_tab5_p")
                            df_selected_drug = df_d[df_d[drug_name_col] == selected_drug].copy() if selected_drug else None

                        if df_selected_drug is not None and not df_selected_drug.empty:
                            df_selected_drug['doc_clean'] = df_selected_drug[doc_col_drug].apply(clean_name)
                            doc_drug_qty = df_selected_drug.groupby('doc_clean')[drug_qty_col].sum().reset_index()

                            doc_visits = df_main[[doc_col_main, visit_col]].copy()
                            doc_visits[visit_col] = pd.to_numeric(doc_visits[visit_col], errors='coerce').fillna(0)
                            doc_visits['doc_clean'] = doc_visits[doc_col_main].apply(clean_name)

                            merged_data = pd.merge(doc_visits, doc_drug_qty, on='doc_clean', how='left')
                            merged_data[drug_qty_col] = merged_data[drug_qty_col].fillna(0)
                            merged_data = merged_data[merged_data[visit_col] > 0].copy()

                            merged_data['میزان_در_هر_ویزیت'] = merged_data[drug_qty_col] / merged_data[visit_col]
                            
                            # مرتب‌سازی نزولی بر اساس میزان در هر ویزیت (مهم برای محور X و جدول)
                            merged_data = merged_data.sort_values(by='میزان_در_هر_ویزیت', ascending=False)
                            merged_data['برچسب'] = merged_data.apply(lambda r: f"{r['میزان_در_هر_ویزیت']:.2f} (کل: {int(r[drug_qty_col]):,} از {int(r[visit_col]):,} ویزیت)", axis=1)

                            fig_bar = px.bar(
                                merged_data,
                                x='doc_clean',
                                y='میزان_در_هر_ویزیت',
                                text='برچسب',
                                color='میزان_در_هر_ویزیت',
                                color_continuous_scale='Tealgrn',
                                title=f"میزان تجویز {target_title} به ازای هر ویزیت پزشک (مرتب‌شده از بزرگ به کوچک)"
                            )
                            fig_bar.update_xaxes(categoryorder='total descending')
                            fig_bar.update_traces(textposition='outside')
                            st.plotly_chart(fig_bar, use_container_width=True)

                            st.markdown("---")
                            st.subheader(f"📋 جدول مقایسه‌ای نسبت تجویز {target_title} به ویزیت")
                            
                            # ساخت جدول مورد درخواست کاربر
                            table_df = merged_data[['doc_clean', drug_qty_col, 'میزان_در_هر_ویزیت']].copy()
                            table_df.columns = ['نام پزشک', 'میزان تجویز (تعداد)', 'نسبت دارو به نسخه']
                            table_df['میزان تجویز (تعداد)'] = table_df['میزان تجویز (تعداد)'].astype(int)
                            table_df['نسبت دارو به نسخه'] = table_df['نسبت دارو به نسخه'].round(3)
                            
                            # سورت نزولی قطعی جدول بر اساس ستون «نسبت دارو به نسخه»
                            table_df = table_df.sort_values(by='نسبت دارو به نسخه', ascending=False)
                            
                            st.dataframe(table_df, use_container_width=True, hide_index=True)

            # --- تب ۶: تنظیمات شاخص‌ها ---
            with tab6:
                st.header("⚙️ تنظیمات عمومی سطوح شاخص‌ها")
                if df_main is not None:
                    metrics_list = df_main.columns[1:].tolist()
                    with st.form("metric_settings_form_p"):
                        updated_settings = {}
                        for metric in metrics_list:
                            st.subheader(f"📊 شاخص: `{metric}`")
                            m_curr = st.session_state.metric_settings.get(metric, {})
                            eval_type_opts = ["کیفی (بر اساس میانگین درمانگاه)", "کمی (اعداد ثابت/عددی)"]
                            default_eval_type = m_curr.get("eval_type", "کیفی (بر اساس میانگین درمانگاه)")
                            eval_idx = eval_type_opts.index(default_eval_type) if default_eval_type in eval_type_opts else 0

                            default_dir = m_curr.get("direction", "کمتر بهتر" if ("ویزیت" not in metric and "آزمایشگاه" not in metric and "نسخ" not in metric) else "بیشتر بهتر")
                            dir_opts = ["کمتر بهتر", "بیشتر بهتر"]
                            dir_idx = dir_opts.index(default_dir) if default_dir in dir_opts else 0

                            c1, c2 = st.columns(2)
                            with c1:
                                eval_type = st.radio("نوع ارزیابی", eval_type_opts, index=eval_idx, key=f"e_{metric}")
                            with c2:
                                direction = st.radio("جهت مطلوبیت", dir_opts, index=dir_idx, key=f"d_{metric}")

                            tolerance = float(m_curr.get("tolerance", 10.0))
                            tolerance = st.number_input("درصد تلرانس دور میانگین (٪)", value=tolerance, min_value=0.0, max_value=50.0, key=f"t_{metric}")

                            updated_settings[metric] = {
                                "eval_type": eval_type,
                                "direction": direction,
                                "tolerance": tolerance
                            }
                        if st.form_submit_button("💾 ذخیره تنظیمات شاخص‌ها", type="primary"):
                            st.session_state.metric_settings = updated_settings
                            save_settings()
                            st.success("تنظیمات با موفقیت ذخیره شد.")

            # --- تب ۷: بازخوردهای مدیریت ---
            with tab7:
                st.header("📝 مدیریت توصیه‌ها و بازخوردها")
                gen_note = st.text_area("متن پیام عمومی مدیریت:", value=st.session_state.admin_general_notes, height=100)
                if st.button("ذخیره پیام عمومی", type="primary"):
                    st.session_state.admin_general_notes = gen_note
                    save_settings()
                    st.success("ذخیره شد.")

                st.markdown("---")
                if df_main is not None:
                    doctors_list = df_main[df_main.columns[0]].dropna().unique().tolist()
                    selected_target_doc = st.selectbox("پزشک مورد نظر را انتخاب کنید:", doctors_list, key="target_doc_p")
                    current_doc_note = st.session_state.admin_doctor_notes.get(clean_name(selected_target_doc), "")
                    spec_note = st.text_area(f"متن توصیه اختصاصی برای {selected_target_doc}:", value=current_doc_note, height=120)
                    if st.button(f"ذخیره توصیه اختصاصی برای {selected_target_doc}", type="primary"):
                        st.session_state.admin_doctor_notes[clean_name(selected_target_doc)] = spec_note
                        save_settings()
                        st.success("توصیه اختصاصی ذخیره شد.")

    # =============================================================
    # ۲. بخش پزشکان (DOCTOR VIEW - جذاب و همراه نمودار/جدول)
    # =============================================================
    elif st.session_state.user_role == "doctor":
        current_doc = clean_name(st.session_state.doctor_name)
        st.title(f"👨‍⚕️ پنل اختصاصی پزشک: {current_doc}")

        if not periods_meta:
            st.warning("⚠️ هنوز هیچ دوره‌ای در سیستم توسط مدیریت ثبت نشده است.")
        else:
            p_options = {p["name"]: p["id"] for p in periods_meta}
            selected_p_name_doc = st.selectbox("🗓️ انتخاب دوره ارزیابی جهت مشاهده کارنامه:", list(p_options.keys()))
            doc_active_p_id = p_options[selected_p_name_doc]

            # بازخوردها
            doc_notes_dict = st.session_state.get('admin_doctor_notes', {})
            doc_note_content = doc_notes_dict.get(current_doc, "")
            has_gen_note = bool(st.session_state.get('admin_general_notes', '').strip())
            has_doc_note = bool(doc_note_content.strip())

            if has_gen_note or has_doc_note:
                st.subheader("📮 پیام‌ها و توصیه‌های مدیریت درمانگاه")
                if has_gen_note:
                    st.info(f"**📢 اطلاعیه عمومی:**\n\n{st.session_state.admin_general_notes}")
                if has_doc_note:
                    st.warning(f"**✉️ توصیه اختصاصی برای شما ({current_doc}):**\n\n{doc_note_content}")
                st.markdown("---")

            df, err_doc_main = load_period_data(doc_active_p_id, "main")

            if df is None or df.empty:
                st.warning(f"⚠️ اطلاعات مربوط به دوره «{selected_p_name_doc}» هنوز کامل نشده است.")
            else:
                doctor_col = df.columns[0]
                metrics = df.columns[1:]
                df['doc_clean'] = df[doctor_col].apply(clean_name)

                if current_doc not in df['doc_clean'].values:
                    st.error(f"❌ نام شما ({current_doc}) در اکسل این دوره پیدا نشد.")
                else:
                    doc_data = df[df['doc_clean'] == current_doc].iloc[0]
                    numeric_df = df[metrics].apply(pd.to_numeric, errors='coerce')
                    avg_data = numeric_df.mean()
                    
                    df_ranks = calculate_ranks(df, metrics)
                    df_ranks['doc_clean'] = df_ranks[doctor_col].apply(clean_name)
                    doc_ranks = df_ranks[df_ranks['doc_clean'] == current_doc].iloc[0]

                    st.subheader(f"📋 کارنامه خلاصه عملکرد در دوره: {selected_p_name_doc}")
                    
                    # کارت‌های استریم‌لیت
                    cols = st.columns(2)
                    metric_settings = st.session_state.get("metric_settings", {})

                    for i, metric in enumerate(metrics):
                        m_dir = metric_settings.get(metric, {}).get("direction", "")
                        is_inverse = (m_dir == "کمتر بهتر") or ("ویزیت" not in metric and "آزمایشگاه" not in metric and "نسخ" not in metric)

                        with cols[i % 2]:
                            st.metric(
                                label=metric, 
                                value=f"{doc_data[metric]}", 
                                delta=f"رتبه {doc_ranks[metric]} از {len(df)}",
                                delta_color="inverse" if is_inverse else "normal"
                            )

                    st.markdown("---")
                    
                    # ۱. ساخت جدول خلاصه عملکرد پزشک
                    summary_list = []
                    warnings, goods, critical_metrics = [], [], []

                    for metric in metrics:
                        val = pd.to_numeric(doc_data[metric], errors='coerce')
                        val_num = val if not pd.isna(val) else 0
                        avg_val = round(avg_data[metric], 2)
                        rank_val = doc_ranks[metric]

                        m_set = metric_settings.get(metric, {})
                        direction = m_set.get("direction", "کمتر بهتر" if ("ویزیت" not in metric and "آزمایشگاه" not in metric and "نسخ" not in metric) else "بیشتر بهتر")
                        tol_percent = m_set.get("tolerance", 10.0) / 100.0

                        low_bound = avg_val * (1.0 - tol_percent)
                        high_bound = avg_val * (1.0 + tol_percent)

                        if direction == "کمتر بهتر":
                            if val_num < low_bound:
                                status = "🟢 عالی (پایین‌تر از میانگین)"
                                goods.append(f"🟢 **عملکرد ایده‌آل در {metric}:** میزان تجویز شما ({val_num}) پایین‌تر از میانگین درمانگاه ({avg_val}) است.")
                            elif low_bound <= val_num <= high_bound:
                                status = "🟢 نرمال (هم‌تراز میانگین)"
                                goods.append(f"🟢 **عملکرد استاندارد در {metric}:** میزان تجویز شما ({val_num}) هم‌تراز با میانگین درمانگاه ({avg_val}) است.")
                            else:
                                status = "🔴 نیازمند بازبینی (بالاتر از میانگین)"
                                warnings.append(f"🔴 **وضعیت بحرانی در {metric}:** میزان تجویز شما ({val_num}) بالاتر از حد میانگین درمانگاه ({avg_val}) است.")
                                critical_metrics.append((metric, val_num, avg_val))
                        else:
                            if val_num > high_bound:
                                status = "🟢 عالی (بالاتر از میانگین)"
                                goods.append(f"🟢 **عملکرد ایده‌آل در {metric}:** آمار شما ({val_num}) بالاتر از میانگین درمانگاه ({avg_val}) است.")
                            elif low_bound <= val_num <= high_bound:
                                status = "🟢 نرمال (هم‌تراز میانگین)"
                                goods.append(f"🟢 **عملکرد استاندارد در {metric}:** آمار شما ({val_num}) هم‌تراز با میانگین درمانگاه ({avg_val}) است.")
                            else:
                                status = "🔴 نیازمند بازبینی (پایین‌تر از میانگین)"
                                warnings.append(f"🔴 **وضعیت بحرانی در {metric}:** آمار شما ({val_num}) پایین‌تر از حد میانگین درمانگاه ({avg_val}) است.")
                                critical_metrics.append((metric, val_num, avg_val))

                        summary_list.append({
                            "شاخص": metric,
                            "مقدار شما": val_num,
                            "میانگین درمانگاه": avg_val,
                            "رتبه شما": f"{rank_val} از {len(df)}",
                            "وضعیت": status
                        })

                    df_doc_summary = pd.DataFrame(summary_list)
                    df_doc_summary_sorted = df_doc_summary.sort_values(by="مقدار شما", ascending=False)

                    # ۲. افزودن نمودار مقایسه‌ای پویا برای جذاب‌سازی پنل پزشک
                    st.subheader("📊 مقایسه تصویری کارنامه شما در برابر میانگین درمانگاه")
                    df_chart_doc = pd.melt(df_doc_summary_sorted, id_vars=['شاخص'], value_vars=['مقدار شما', 'میانگین درمانگاه'], var_name='مرجع', value_name='مقدار')
                    
                    fig_doc_comp = px.bar(
                        df_chart_doc,
                        x='شاخص',
                        y='مقدار',
                        color='مرجع',
                        barmode='group',
                        text_auto='.1f',
                        title="مقایسه مقادیر شما با میانگین کل درمانگاه (مرتب‌شده از بزرگ به کوچک)"
                    )
                    fig_doc_comp.update_xaxes(categoryorder='total descending')
                    st.plotly_chart(fig_doc_comp, use_container_width=True)

                    # ۳. افزودن جدول جامع به پنل پزشک
                    st.subheader("📋 جدول مقایسه‌ای وضعیت شاخص‌ها")
                    st.dataframe(df_doc_summary_sorted, use_container_width=True, hide_index=True)

                    st.markdown("---")
                    st.subheader("⚠️ تحلیل هوشمند وضعیت تجویزی شما")

                    if warnings:
                        st.error("### موارد نیازمند بازبینی")
                        for w in warnings:
                            st.write(w)
                    if goods:
                        st.success("### نقاط قوت تجویزی شما")
                        for g in goods:
                            st.write(g)

                    if critical_metrics:
                        st.markdown("---")
                        st.subheader("💡 توصیه‌ها و گایدلاین‌های بالینی روز دنیا (WHO / CDC)")
                        for metric, val, avg in critical_metrics:
                            guideline_text = get_clinical_guideline(metric, val, avg)
                            with st.expander(f"📌 راهنمای بالینی برای: {metric}", expanded=True):
                                st.markdown(guideline_text)

        st.markdown("---")
        with st.expander("🔑 تغییر رمز عبور حساب کاربری"):
            old_pass = st.text_input("رمز عبور فعلی:", type="password")
            new_pass = st.text_input("رمز عبور جدید:", type="password")
            confirm_pass = st.text_input("تکرار رمز عبور جدید:", type="password")
            
            if st.button("ثبت رمز عبور جدید"):
                current_pass = st.session_state.doctor_passwords.get(current_doc, DOCTOR_DEFAULT_PASSWORD)
                if old_pass != current_pass:
                    st.error("رمز عبور فعلی نادرست است.")
                elif not new_pass or len(new_pass.strip()) < 4:
                    st.error("رمز عبور جدید باید حداقل ۴ کاراکتر باشد.")
                elif new_pass != confirm_pass:
                    st.error("رمز عبور جدید و تکرار آن یکسان نیستند.")
                else:
                    st.session_state.doctor_passwords[current_doc] = new_pass
                    save_settings()
                    st.success("رمز عبور شما با موفقیت تغییر کرد.")

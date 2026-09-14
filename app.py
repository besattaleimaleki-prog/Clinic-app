import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
import re

# تابع پاکسازی پیشوندها و استانداردسازی نام کاربری
def clean_username(text):
    if not text:
        return ""
    text = str(text).strip()
    # یکسان‌سازی ی و ک
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    # حذف پیشوندها (دکتر، خانم، آقا، آقای، مهندس) از ابتدای متن
    prefix_pattern = r'^(دکتر|خانم|آقا|آقای|اقای|مهندس)\b\s*'
    text = re.sub(prefix_pattern, '', text, flags=re.IGNORECASE)
    # حذف فاصله‌های اضافی
    return " ".join(text.split())

st.set_page_config(page_title="سیستم ارزیابی نسخ درمانگاه", layout="wide")

# مسیرهای ذخیره‌سازی دائمی
DATA_FILE = "saved_clinic_data.xlsx"
DRUG_DATA_FILE = "saved_drug_data.xlsx"
SETTINGS_FILE = "system_settings.json"

# ------------------ توابع ذخیره‌سازی و بازیابی داده‌ها ------------------
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

# ------------------ توابع دسته‌بندی و فیلتر هوشمند داروها ------------------
def classify_drug(drug_name):
    """تحلیل و دسته‌بندی هوشمند دارو بر اساس نام و شکل دارویی"""
    name_lower = str(drug_name).strip().lower()
    
    is_oint = any(k in name_lower for k in ['oint', 'ointment', 'پماد'])
    
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
    is_abx = (not is_oint) and any(k in name_lower for k in abx_keywords)
    
    nsaid_keywords = [
        'ibuprofen', 'gelofen', 'indomethacin', 'diclofenac', 'naproxen',
        'meloxicam', 'piroxicam', 'celecoxib', 'mefenamic', 'aspirin',
        'ketorolac', 'ketoprofen', 'flurbiprofen', 'tenoxicam', 'nimesulide',
        'پروفن', 'ژلوفن', 'دیکلوفناک', 'ناپروکسن', 'مفنامیک'
    ]
    is_nsaid = (not is_oint) and any(k in name_lower for k in nsaid_keywords)
    
    cortico_keywords = [
        'dexa', 'dexamethasone', 'beta', 'betamethasone', 'hydrocortisone',
        'prednisolone', 'prednisone', 'triamcinolone', 'methylprednisolone',
        'budesonide', 'fluticasone', 'clobetasol', 'mometasone', 'cortison',
        'دگزا', 'بتامتازون', 'هیدروکورتیزون', 'پرنیزولون', 'تریامسینولون'
    ]
    is_cortico = (not is_oint) and any(k in name_lower for k in cortico_keywords)
    
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
        elif category == "آنتی‌بیوتیک‌ها (بدون Ointment)" and info["abx"]:
            result.append(d)
        elif category == "مسکن‌های NSAID (بدون Ointment)" and info["nsaid"]:
            result.append(d)
        elif category == "کورتیکواستروئیدها (بدون Ointment)" and info["cortico"]:
            result.append(d)
    return result

# ------------------ توابع راهنمای بالینی ------------------
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

# ------------------ مدیریت وضعیت نشست (Session State) ------------------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'doctor_name' not in st.session_state:
    st.session_state.doctor_name = None
if 'doctor_passwords' not in st.session_state:
    st.session_state.doctor_passwords = {}
if 'admin_general_notes' not in st.session_state:
    st.session_state.admin_general_notes = ""
if 'admin_doctor_notes' not in st.session_state:
    st.session_state.admin_doctor_notes = {}
if 'metric_settings' not in st.session_state:
    st.session_state.metric_settings = {}

load_settings()

if 'df' not in st.session_state or st.session_state.df is None:
    if os.path.exists(DATA_FILE):
        try:
            st.session_state.df = pd.read_excel(DATA_FILE)
        except Exception:
            st.session_state.df = None
    else:
        st.session_state.df = None

if 'df_drugs' not in st.session_state or st.session_state.df_drugs is None:
    if os.path.exists(DRUG_DATA_FILE):
        try:
            st.session_state.df_drugs = pd.read_excel(DRUG_DATA_FILE)
        except Exception:
            st.session_state.df_drugs = None
    else:
        st.session_state.df_drugs = None

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
DOCTOR_DEFAULT_PASSWORD = "1234"

# ------------------ صفحه ورود (Login Screen) ------------------
if not st.session_state.logged_in:
    st.title("🔑 ورود به سیستم ارزیابی نسخ درمانگاه")
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
        if st.session_state.df is not None:
            df = st.session_state.df
            doctor_col = df.columns[0]
            doctors_list = df[doctor_col].dropna().tolist()
            selected_doc = st.selectbox("نام خود را انتخاب کنید:", doctors_list)
        else:
            st.info("ℹ️ اطلاعات درمانگاه هنوز توسط مدیر بارگذاری نشده است.")
            selected_doc = st.text_input("نام و نام خانوادگی پزشک:")
            
        doc_password = st.text_input("رمز عبور اختصاصی (پیش‌فرض: 1234)", type="password")
        
        if st.button("ورود به پنل پزشک", type="primary"):
            raw_target_doc = selected_doc.strip() if selected_doc else ""
            target_doc = clean_username(selected_doc)
            
            if not target_doc:
                st.error("لطفاً نام خود را مشخص کنید.")
            else:
                expected_password = st.session_state.doctor_passwords.get(
                    target_doc, 
                    st.session_state.doctor_passwords.get(raw_target_doc, DOCTOR_DEFAULT_PASSWORD)
                )
                
                if doc_password == expected_password:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "doctor"
                    st.session_state.doctor_name = target_doc
                    st.success(f"خوش آمدید {target_doc}")
                    st.rerun()
                else:
                    st.error("رمز عبور اشتباه است.")

# ------------------ پنل مدیریت و پزشک ------------------
else:
    with st.sidebar:
        st.write(f"👤 **کاربر متصل:** {st.session_state.doctor_name if st.session_state.user_role == 'doctor' else 'مدیر سیستم'}")
        st.write(f"پست: {'پزشک' if st.session_state.user_role == 'doctor' else 'مدیر ارشد'}")
        if st.button("خروج از حساب کاربری 🚪"):
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.session_state.doctor_name = None
            st.rerun()

    # -------------------------------------------------------------
    # ۱. بخش دسترسی مدیر (ADMIN)
    # -------------------------------------------------------------
    if st.session_state.user_role == "admin":
        st.title("🛠️ پنل مدیریت و ارزیابی کل درمانگاه")

        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📈 مقایسه کل پزشکان", 
            "👤 بررسی فردی پزشکان", 
            "💊 درصد دارو به پزشک", 
            "📋 دارو به نسخه",
            "⚙️ تنظیمات سطوح شاخص‌ها",
            "📝 بازخورد و توصیه‌های مدیریت", 
            "💾 خروجی PDF"
        ])

        # --- تب ۱: مقایسه کل ---
        with tab1:
            st.header("📁 بارگذاری فایل شاخص‌های کلی درمانگاه")
            if os.path.exists(DATA_FILE):
                st.info("💡 فایل شاخص‌ها از قبل در سیستم ذخیره شده است.")
            uploaded_file = st.file_uploader("آپلود فایل اکسل عمومی شاخص‌ها", type=["xlsx", "xls"], key="main_excel_uploader")
            
            if uploaded_file is not None:
                try:
                    df_new = pd.read_excel(uploaded_file)
                except Exception:
                    uploaded_file.seek(0)
                    df_new = pd.read_html(uploaded_file)[0]
                
                st.session_state.df = df_new
                df_new.to_excel(DATA_FILE, index=False)
                st.success("فایل با موفقیت بارگذاری و ذخیره شد.")

            if st.session_state.df is not None:
                df = st.session_state.df
                doctor_col = df.columns[0]
                metrics = df.columns[1:]
                df_ranks = calculate_ranks(df, metrics)

                st.subheader("مقایسه کلی تمام پزشکان")
                selected_metric = st.selectbox("انتخاب شاخص:", metrics)
                fig_bar = px.bar(df, x=doctor_col, y=selected_metric, text_auto=True, color=selected_metric, color_continuous_scale="Viridis")
                st.plotly_chart(fig_bar, use_container_width=True)
                st.subheader("جدول رتبه‌بندی کلی")
                st.dataframe(df_ranks.set_index(doctor_col))

        # --- تب ۲: بررسی فردی ---
        with tab2:
            if st.session_state.df is not None:
                df = st.session_state.df
                doctor_col = df.columns[0]
                metrics = df.columns[1:]
                df_ranks = calculate_ranks(df, metrics)
                doctors_list = df[doctor_col].dropna().tolist()
                
                selected_doc = st.selectbox("انتخاب پزشک جهت بررسی:", doctors_list)
                doc_data = df[df[doctor_col] == selected_doc].iloc[0]
                doc_ranks = df_ranks[df_ranks[doctor_col] == selected_doc].iloc[0]
                
                st.subheader(f"کارنامه کامل: {selected_doc}")
                cols = st.columns(2)
                for i, metric in enumerate(metrics):
                    with cols[i % 2]:
                        st.metric(label=metric, value=f"{doc_data[metric]}", delta=f"رتبه {doc_ranks[metric]} از {len(df)}")

        filter_options = [
            "همه اشکال", 
            "خوراکی (Tab, Cap, Syru, Susp)", 
            "تزریقی عمومی (Inj, Infusion, Solution)",
            "فقط تزریقی (Inj)",
            "آنتی‌بیوتیک‌ها (بدون Ointment)",
            "مسکن‌های NSAID (بدون Ointment)",
            "کورتیکواستروئیدها (بدون Ointment)"
        ]

        # --- تب ۳: درصد دارو به پزشک ---
        with tab3:
            st.header("💊 سهم و درصد تجویز داروها به تفکیک پزشک")
            st.markdown("فایل اکسل شامل ۳ ستون: **۱. نام پزشک** | **۲. نام و شکل دارو** | **۳. تعداد تجویزی** را آپلود کنید.")

            if os.path.exists(DRUG_DATA_FILE):
                st.info("💡 فایل اقلام دارویی از قبل در سیستم ذخیره شده است.")

            uploaded_drug_file = st.file_uploader("بارگذاری فایل اکسل اقلام دارویی", type=["xlsx", "xls"], key="drug_excel_uploader")

            if uploaded_drug_file is not None:
                try:
                    df_d_new = pd.read_excel(uploaded_drug_file)
                except Exception:
                    uploaded_drug_file.seek(0)
                    df_d_new = pd.read_html(uploaded_drug_file)[0]

                st.session_state.df_drugs = df_d_new
                df_d_new.to_excel(DRUG_DATA_FILE, index=False)
                st.success("فایل اقلام دارویی با موفقیت ذخیره شد.")

            if st.session_state.df_drugs is not None:
                df_d = st.session_state.df_drugs.copy()
                doc_c = df_d.columns[0]
                drug_c = df_d.columns[1]
                qty_c = df_d.columns[2]

                df_d[qty_c] = pd.to_numeric(df_d[qty_c], errors='coerce').fillna(0)
                df_d[drug_c] = df_d[drug_c].astype(str).str.strip()

                drug_totals = df_d.groupby(drug_c)[qty_c].sum()
                valid_drugs = drug_totals[drug_totals > 0].index.tolist()
                df_filtered = df_d[df_d[drug_c].isin(valid_drugs)].copy()

                if len(valid_drugs) == 0:
                    st.warning("هیچ دارویی با مجموع تجویز بیشتر از صفر یافت نشد.")
                else:
                    form_filter = st.radio("🔍 انتخاب فیلتر دسته‌بندی دارویی:", filter_options, horizontal=True, key="filter_tab3")
                    selectable_drugs = filter_drug_list(valid_drugs, form_filter)

                    if not selectable_drugs:
                        st.info("دارویی در دسته انتخابی یافت نشد.")
                    else:
                        selected_drug = st.selectbox("🔍 داروی مورد نظر را انتخاب یا سرچ کنید:", selectable_drugs, key="select_drug_tab3")

                        if selected_drug:
                            drug_df = df_filtered[df_filtered[drug_c] == selected_drug]
                            doc_grouped = drug_df.groupby(doc_c)[qty_c].sum().reset_index()
                            doc_grouped = doc_grouped[doc_grouped[qty_c] > 0]
                            
                            total_drug_qty = doc_grouped[qty_c].sum()
                            doc_grouped['درصد'] = (doc_grouped[qty_c] / total_drug_qty) * 100
                            doc_grouped['برچسب_نمودار'] = doc_grouped.apply(lambda r: f"{int(r[qty_c])} عدد ({r['درصد']:.1f}%)", axis=1)

                            st.markdown("---")
                            st.subheader(f"📊 سهم تجویز داروی: `{selected_drug}`")

                            fig_drug = px.bar(
                                doc_grouped,
                                x=doc_c,
                                y=qty_c,
                                text='برچسب_نمودار',
                                labels={doc_c: 'نام پزشک', qty_c: 'فراوانی تجویز (تعداد)'},
                                color=qty_c,
                                color_continuous_scale='Blues',
                                title=f"توزیع درصد و تعداد تجویز {selected_drug} بین پزشکان"
                            )
                            fig_drug.update_traces(textposition='outside')
                            fig_drug.update_layout(yaxis_title="تعداد تجویزی", xaxis_title="نام پزشک")
                            st.plotly_chart(fig_drug, use_container_width=True)

                            st.metric(
                                label=f"📦 مجموع کل تعداد تجویزی داروی {selected_drug} در درمانگاه",
                                value=f"{int(total_drug_qty):,} عدد"
                            )
            else:
                st.warning("⚠️ هنوز هیچ فایل اکسلی برای اقلام دارویی بارگذاری نشده است.")

        # --- تب ۴: دارو به نسخه / ویزیت ---
        with tab4:
            st.header("📋 میزان تجویز هر دارو به ازای هر ویزیت پزشک")
            st.markdown("محاسبه نسبت مجموع داروی تجویز شده به تعداد کل ویزیت‌های هر پزشک (**اکسل ۱:** نام پزشک + تعداد ویزیت | **اکسل ۲:** نام پزشک + نام دارو + تعداد تجویزی)")

            def clean_doctor_name(text):
                if pd.isna(text):
                    return ""
                text = str(text).strip()
                text = text.replace('ي', 'ی').replace('ك', 'ک')
                text = text.replace('دکتر', '').replace('پزشک', '')
                return " ".join(text.split())

            if st.session_state.df is None or st.session_state.df_drugs is None:
                st.error("⚠️ لطفا ابتدا هر دو فایل اکسل (شاخص‌های کل و اقلام دارویی) را بارگذاری کنید.")
            else:
                df_main = st.session_state.df.copy()
                doc_col_main = df_main.columns[0]
                
                visit_candidates = [c for c in df_main.columns if 'ویزیت' in c or 'نسخ' in c]
                default_visit_col = visit_candidates[0] if visit_candidates else df_main.columns[1]
                
                visit_col = st.selectbox(
                    "📌 ستون تعداد کل ویزیت‌ها را از اکسل اول تایید کنید:",
                    options=df_main.columns[1:],
                    index=df_main.columns[1:].tolist().index(default_visit_col) if default_visit_col in df_main.columns[1:].tolist() else 0,
                    key="select_visit_col_tab"
                )

                df_drugs = st.session_state.df_drugs.copy()
                doc_col_drug = df_drugs.columns[0]
                drug_name_col = df_drugs.columns[1]
                drug_qty_col = df_drugs.columns[2]

                df_drugs[drug_qty_col] = pd.to_numeric(df_drugs[drug_qty_col], errors='coerce').fillna(0)
                df_drugs[drug_name_col] = df_drugs[drug_name_col].astype(str).str.strip()

                drug_totals = df_drugs.groupby(drug_name_col)[drug_qty_col].sum()
                valid_drugs = drug_totals[drug_totals > 0].index.tolist()

                if not valid_drugs:
                    st.warning("هیچ دارویی با مجموع تجویز بیشتر از صفر در اکسل دوم یافت نشد.")
                else:
                    form_filter = st.radio("🔍 فیلتر دسته‌بندی دارویی:", filter_options, horizontal=True, key="filter_tab_rx")
                    selectable_drugs = filter_drug_list(valid_drugs, form_filter)

                    if not selectable_drugs:
                        st.info("دارویی در دسته انتخابی یافت نشد.")
                    else:
                        selected_drug = st.selectbox("🔍 انتخاب دارو:", selectable_drugs, key="select_drug_tab_rx")

                        if selected_drug:
                            df_selected_drug = df_drugs[df_drugs[drug_name_col] == selected_drug].copy()
                            df_selected_drug['doc_clean'] = df_selected_drug[doc_col_drug].apply(clean_doctor_name)
                            doc_drug_qty = df_selected_drug.groupby('doc_clean')[drug_qty_col].sum().reset_index()

                            doc_visits = df_main[[doc_col_main, visit_col]].copy()
                            doc_visits[visit_col] = pd.to_numeric(doc_visits[visit_col], errors='coerce').fillna(0)
                            doc_visits['doc_clean'] = doc_visits[doc_col_main].apply(clean_doctor_name)

                            merged_data = pd.merge(doc_visits, doc_drug_qty, on='doc_clean', how='left')
                            merged_data[drug_qty_col] = merged_data[drug_qty_col].fillna(0)

                            show_zeros = st.checkbox("نمایش پزشکان با تجویز صفر برای این دارو", value=True)
                            if not show_zeros:
                                merged_data = merged_data[merged_data[drug_qty_col] > 0]

                            merged_data = merged_data[merged_data[visit_col] > 0].copy()

                            if merged_data.empty:
                                st.warning("اطلاعاتی برای نمایش پیدا نشد.")
                            else:
                                merged_data['میزان_در_هر_ویزیت'] = merged_data[drug_qty_col] / merged_data[visit_col]
                                merged_data['برچسب'] = merged_data.apply(
                                    lambda r: f"{r['میزان_در_هر_ویزیت']:.2f} (کل: {int(r[drug_qty_col]):,} از {int(r[visit_col]):,} ویزیت)", 
                                    axis=1
                                )

                                st.markdown("---")
                                st.subheader(f"📊 نمودار تجویز داروی `{selected_drug}` به ازای هر ویزیت")

                                fig_bar = px.bar(
                                    merged_data,
                                    x=doc_col_main,
                                    y='میزان_در_هر_ویزیت',
                                    text='برچسب',
                                    labels={
                                        doc_col_main: 'نام پزشک', 
                                        'میزان_در_هر_ویزیت': 'تعداد دارو به ازای هر ویزیت'
                                    },
                                    color='میزان_در_هر_ویزیت',
                                    color_continuous_scale='Tealgrn',
                                    title=f"میزان تجویز {selected_drug} به ازای هر ویزیت پزشک"
                                )
                                fig_bar.update_traces(textposition='outside')
                                fig_bar.update_layout(
                                    xaxis_title="نام پزشک (محور X)",
                                    yaxis_title="میزان تجویز به ازای هر ویزیت (محور Y)"
                                )
                                st.plotly_chart(fig_bar, use_container_width=True)

                                st.subheader("📋 جدول جزئیات محاسبات")
                                table_df = merged_data[[doc_col_main, drug_qty_col, visit_col, 'میزان_در_هر_ویزیت']].copy()
                                table_df.columns = ['نام پزشک', 'کل داروی تجویز شده', 'تعداد کل ویزیت‌ها', 'میزان به ازای هر ویزیت']
                                table_df['میزان به ازای هر ویزیت'] = table_df['میزان به ازای هر ویزیت'].round(2)
                                st.dataframe(table_df.set_index('نام پزشک'), use_container_width=True)

        # --- تب ۵: تنظیمات سطوح شاخص‌ها (کمی + کیفی) ---
        with tab5:
            st.header("⚙️ تنظیمات سطوح و حدود استاندارد شاخص‌ها")
            st.markdown("در این بخش می‌توانید ارزیابی شاخص‌ها را به دو روش **کیفی (نسبت به میانگین درمانگاه)** یا **کمی (اعداد ثابت/عددی)** تنظیم کنید.")

            if st.session_state.df is not None:
                df_curr = st.session_state.df
                metrics_list = df_curr.columns[1:].tolist()

                with st.form("metric_settings_form"):
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
                            eval_type = st.radio(
                                f"نوع ارزیابی شاخص",
                                eval_type_opts,
                                index=eval_idx,
                                key=f"eval_type_{metric}"
                            )
                        with c2:
                            direction = st.radio(
                                f"جهت مطلوبیت",
                                dir_opts,
                                index=dir_idx,
                                key=f"dir_{metric}"
                            )

                        ideal_val = float(m_curr.get("ideal", 0.0))
                        std_val = float(m_curr.get("standard", 0.0))
                        crit_val = float(m_curr.get("crit", 0.0))
                        tolerance = float(m_curr.get("tolerance", 10.0))

                        if eval_type == "کمی (اعداد ثابت/عددی)":
                            col_ideal, col_std, col_crit = st.columns(3)
                            with col_ideal:
                                ideal_val = st.number_input(f"🌟 حد ایده‌آل", value=ideal_val, key=f"ideal_{metric}")
                            with col_std:
                                std_val = st.number_input(f"✅ حد استاندارد", value=std_val, key=f"std_{metric}")
                            with col_crit:
                                crit_val = st.number_input(f"🛑 حد بحرانی", value=crit_val, key=f"crit_{metric}")
                        else:
                            if direction == "کمتر بهتر":
                                rule_text = (
                                    f"• **🟢 ایده‌آل:** پایین‌تر از میانگین درمانگاه (کمتر از {100-tolerance:.0f}٪ میانگین)\n"
                                    f"• **🟡 استاندارد:** هم‌تراز با میانگین درمانگاه (بین {100-tolerance:.0f}٪ تا {100+tolerance:.0f}٪ میانگین)\n"
                                    f"• **🔴 بحرانی:** بالاتر از حد درمانگاه (بیشتر از {100+tolerance:.0f}٪ میانگین)"
                                )
                            else:
                                rule_text = (
                                    f"• **🟢 ایده‌آل:** بالاتر از میانگین درمانگاه (بیشتر از {100+tolerance:.0f}٪ میانگین)\n"
                                    f"• **🟡 استاندارد:** هم‌تراز با میانگین درمانگاه (بین {100-tolerance:.0f}٪ تا {100+tolerance:.0f}٪ میانگین)\n"
                                    f"• **🔴 بحرانی:** پایین‌تر از حد درمانگاه (کمتر از {100-tolerance:.0f}٪ میانگین)"
                                )
                            
                            st.info(f"💡 **سطوح ارزیابی کیفی بر اساس میانگین درمانگاه:**\n\n{rule_text}")
                            tolerance = st.number_input(f"درصد تلرانس نوسان دور میانگین برای حالت استاندارد (٪)", value=tolerance, min_value=0.0, max_value=50.0, step=1.0, key=f"tol_{metric}")

                        updated_settings[metric] = {
                            "eval_type": eval_type,
                            "direction": direction,
                            "ideal": ideal_val,
                            "standard": std_val,
                            "crit": crit_val,
                            "tolerance": tolerance
                        }
                        st.markdown("---")

                    submitted = st.form_submit_button("💾 ذخیره تنظیمات شاخص‌ها", type="primary")
                    if submitted:
                        st.session_state.metric_settings = updated_settings
                        save_settings()
                        st.success("تنظیمات حدود و سطوح شاخص‌ها با موفقیت ذخیره شد.")
            else:
                st.warning("⚠️ هنوز فایل اکسل شاخص‌ها بارگذاری نشده است. لطفاً ابتدا در تب ۱ فایل را آپلود کنید.")

        # --- تب ۶: بازخوردها ---
        with tab6:
            st.header("📝 مدیریت توصیه‌ها و بازخوردهای مدیریت")
            gen_note = st.text_area("متن پیام عمومی مدیریت:", value=st.session_state.admin_general_notes, height=100)
            if st.button("ذخیره پیام عمومی", type="primary"):
                st.session_state.admin_general_notes = gen_note
                save_settings()
                st.success("پیام عمومی ذخیره شد.")

            st.markdown("---")
            if st.session_state.df is not None:
                df = st.session_state.df
                doctors_list = df[df.columns[0]].dropna().tolist()
                selected_target_doc = st.selectbox("پزشک مورد نظر را انتخاب کنید:", doctors_list, key="admin_target_doc")
                current_doc_note = st.session_state.admin_doctor_notes.get(selected_target_doc, "")
                spec_note = st.text_area(f"متن توصیه اختصاصی برای {selected_target_doc}:", value=current_doc_note, height=120)
                if st.button(f"ذخیره توصیه اختصاصی برای {selected_target_doc}", type="primary"):
                    st.session_state.admin_doctor_notes[selected_target_doc] = spec_note
                    save_settings()
                    st.success("توصیه اختصاصی ذخیره شد.")

        # --- تب ۷: PDF ---
        with tab7:
            st.info("برای چاپ یا ذخیره PDF گزارشات، از گزینه Print مرورگر (Ctrl+P) استفاده کنید.")

    # -------------------------------------------------------------
    # ۲. بخش دسترسی محدود پزشک (DOCTOR)
    # -------------------------------------------------------------
    elif st.session_state.user_role == "doctor":
        current_doc = st.session_state.doctor_name
        st.title(f"👨‍⚕️ پنل اختصاصی ارتقای عملکرد: {current_doc}")

        doc_notes_dict = st.session_state.get('admin_doctor_notes', {})
        doc_note_content = doc_notes_dict.get(current_doc, "")
        if not doc_note_content:
            for k, v in doc_notes_dict.items():
                if clean_username(k) == current_doc:
                    doc_note_content = v
                    break

        has_gen_note = bool(st.session_state.get('admin_general_notes', '').strip())
        has_doc_note = bool(doc_note_content.strip())

        if has_gen_note or has_doc_note:
            st.subheader("📮 پیام‌ها و توصیه‌های مدیریت درمانگاه")
            if has_gen_note:
                st.info(f"**📢 اطلاعیه عمومی مدیریت:**\n\n{st.session_state.admin_general_notes}")
            if has_doc_note:
                st.warning(f"**✉️ توصیه اختصاصی مدیریت برای شما ({current_doc}):**\n\n{doc_note_content}")
            st.markdown("---")

        if st.session_state.df is None:
            st.warning("⚠️ اطلاعات درمانگاه هنوز توسط مدیر بارگذاری نشده است.")
        else:
            df = st.session_state.df.copy()
            doctor_col = df.columns[0]
            metrics = df.columns[1:]

            df['doc_clean'] = df[doctor_col].apply(clean_username)

            if current_doc not in df['doc_clean'].values:
                st.error(f"❌ نام شما ({current_doc}) در فایل اکسل پیدا نشد.")
            else:
                doc_data = df[df['doc_clean'] == current_doc].iloc[0]
                numeric_df = df[metrics].apply(pd.to_numeric, errors='coerce')
                avg_data = numeric_df.mean()
                
                df_ranks = calculate_ranks(df, metrics)
                df_ranks['doc_clean'] = df_ranks[doctor_col].apply(clean_username)
                doc_ranks = df_ranks[df_ranks['doc_clean'] == current_doc].iloc[0]

                st.subheader("📋 خلاصه آمار و رتبه شما در درمانگاه")
                cols = st.columns(2)
                metric_settings = st.session_state.get("metric_settings", {})

                for i, metric in enumerate(metrics):
                    m_dir = metric_settings.get(metric, {}).get("direction", "")
                    if m_dir == "بیشتر بهتر":
                        is_inverse = False
                    elif m_dir == "کمتر بهتر":
                        is_inverse = True
                    else:
                        is_inverse = ("ویزیت" not in metric and "آزمایشگاه" not in metric and "نسخ" not in metric)

                    with cols[i % 2]:
                        st.metric(
                            label=metric, 
                            value=f"{doc_data[metric]}", 
                            delta=f"رتبه {doc_ranks[metric]} از {len(df)}",
                            delta_color="inverse" if is_inverse else "normal"
                        )

                st.markdown("---")
                st.subheader("⚠️ تحلیل هوشمند وضعیت تجویزی شما")
                warnings, goods, critical_metrics = [], [], []

                for metric in metrics:
                    val = pd.to_numeric(doc_data[metric], errors='coerce')
                    if pd.isna(val):
                        continue
                    avg = avg_data[metric]

                    m_set = metric_settings.get(metric, {})
                    eval_type = m_set.get("eval_type", "کیفی (بر اساس میانگین درمانگاه)")
                    direction = m_set.get("direction", "کمتر بهتر" if ("ویزیت" not in metric and "آزمایشگاه" not in metric and "نسخ" not in metric) else "بیشتر بهتر")
                    ideal = m_set.get("ideal", 0.0)
                    std = m_set.get("standard", 0.0)
                    crit = m_set.get("crit", 0.0)
                    tol_percent = m_set.get("tolerance", 10.0) / 100.0

                    if eval_type == "کمی (اعداد ثابت/عددی)":
                        if direction == "کمتر بهتر":
                            if ideal > 0 and val <= ideal:
                                goods.append(f"🟢 **عملکرد ایده‌آل در {metric}:** مقدار شما ({val}) در حد ایده‌آل ({ideal}) یا کمتر قرار دارد.")
                            elif std > 0 and val <= std:
                                goods.append(f"🟢 **عملکرد مطلوب در {metric}:** مقدار شما ({val}) در محدوده استاندارد ({std}) قرار دارد.")
                            elif crit > 0 and val <= crit:
                                warnings.append(f"🟡 **هشدار در {metric}:** مقدار شما ({val}) فراتر از حد استاندارد ({std}) است.")
                            else:
                                warnings.append(f"🔴 **وضعیت بحرانی در {metric}:** مقدار شما ({val}) از حد بحرانی عبور کرده است.")
                                critical_metrics.append((metric, val, std if std > 0 else avg))
                        else:  # بیشتر بهتر
                            if ideal > 0 and val >= ideal:
                                goods.append(f"🟢 **عملکرد ایده‌آل در {metric}:** مقدار شما ({val}) در حد ایده‌آل ({ideal}) یا بیشتر قرار دارد.")
                            elif std > 0 and val >= std:
                                goods.append(f"🟢 **عملکرد مطلوب در {metric}:** مقدار شما ({val}) در محدوده استاندارد ({std}) قرار دارد.")
                            elif crit > 0 and val >= crit:
                                warnings.append(f"🟡 **هشدار در {metric}:** مقدار شما ({val}) پایین‌تر از حد استاندارد ({std}) است.")
                            else:
                                warnings.append(f"🔴 **وضعیت بحرانی در {metric}:** مقدار شما ({val}) پایین‌تر از حد بحرانی است.")
                                critical_metrics.append((metric, val, std if std > 0 else avg))

                    else:  # ارزیابی کیفی (بر اساس میانگین درمانگاه)
                        low_bound = avg * (1.0 - tol_percent)
                        high_bound = avg * (1.0 + tol_percent)

                        if direction == "کمتر بهتر":
                            if val < low_bound:
                                goods.append(f"🟢 **عملکرد ایده‌آل در {metric}:** میزان تجویز شما ({val}) پایین‌تر از میانگین درمانگاه ({round(avg, 1)}) است.")
                            elif low_bound <= val <= high_bound:
                                goods.append(f"🟢 **عملکرد استاندارد در {metric}:** میزان تجویز شما ({val}) هم‌تراز با میانگین درمانگاه ({round(avg, 1)}) است.")
                            else:
                                warnings.append(f"🔴 **وضعیت بحرانی در {metric}:** میزان تجویز شما ({val}) بالاتر از حد میانگین درمانگاه ({round(avg, 1)}) است.")
                                critical_metrics.append((metric, val, avg))
                        else:  # بیشتر بهتر
                            if val > high_bound:
                                goods.append(f"🟢 **عملکرد ایده‌آل در {metric}:** آمار شما ({val}) بالاتر از میانگین درمانگاه ({round(avg, 1)}) است.")
                            elif low_bound <= val <= high_bound:
                                goods.append(f"🟢 **عملکرد استاندارد در {metric}:** آمار شما ({val}) هم‌تراز با میانگین درمانگاه ({round(avg, 1)}) است.")
                            else:
                                warnings.append(f"🔴 **وضعیت بحرانی در {metric}:** آمار شما ({val}) پایین‌تر از حد میانگین درمانگاه ({round(avg, 1)}) است.")
                                critical_metrics.append((metric, val, avg))

                if warnings:
                    st.error("### موارد نیازمند بازبینی")
                    for w in warnings:
                        st.write(w)
                if goods:
                    st.success("### نقاط قوت تجویزی شما")
                    for g in goods:
                        st.write(g)

                st.markdown("---")
                st.subheader("💡 توصیه‌ها و گایدلاین‌های بالینی روز دنیا (WHO / CDC)")
                if critical_metrics:
                    for metric, val, avg in critical_metrics:
                        guideline_text = get_clinical_guideline(metric, val, avg)
                        with st.expander(f"📌 راهنمای بالینی و گایدلاین علمی برای: {metric}", expanded=True):
                            st.markdown(guideline_text)
                else:
                    st.success("🎉 **تبریک!** عملکرد تجویزی شما کاملاً منطبق بر استانداردهای درمانگاه و گایدلاین‌های بین‌المللی است.")

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

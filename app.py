import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json

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
        "doctor_notes": st.session_state.admin_doctor_notes
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
        except Exception:
            pass

def calculate_ranks(df, metrics):
    df_ranks = df.copy()
    for col in metrics:
        numeric_col = pd.to_numeric(df[col], errors='coerce')
        if "ویزیت" in col or "آزمایشگاه" in col or "نسخ" in col:
            ranks = numeric_col.rank(ascending=False, method='min')
        else:
            ranks = numeric_col.rank(ascending=True, method='min')
        df_ranks[col] = ranks.fillna(0).astype(int)
    return df_ranks

# ------------------ توابع دسته‌بندی و فیلتر هوشمند داروها ------------------
def classify_drug(drug_name):
    """تحلیل و دسته‌بندی هوشمند دارو بر اساس نام و شکل دارویی"""
    name_lower = str(drug_name).strip().lower()
    
    # تشخیص پماد برای استثنا کردن
    is_oint = any(k in name_lower for k in ['oint', 'ointment', 'پماد'])
    
    # ۱. اشکال خوراکی
    oral_prefixes = ['tab', 'cap', 'syru', 'susp', 'syrup', 'قرص', 'کپسول', 'شربت', 'ساسپنشن']
    is_oral = any(name_lower.startswith(p) or f" {p}" in name_lower for p in oral_prefixes)
    
    # ۲. عمومی تزریقی
    inj_gen_prefixes = ['inj', 'infusion', 'solution', 'amp', 'vial', 'تزریقی', 'آمپول']
    is_inj_gen = any(name_lower.startswith(p) or f" {p}" in name_lower or f"{p} " in name_lower for p in inj_gen_prefixes)
    
    # ۳. فقط Inj
    is_inj_strict = 'inj' in name_lower or 'آمپول' in name_lower
    
    # ۴. آنتی‌بیوتیک‌ها (بدون پماد)
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
    
    # ۵. مسکن‌های NSAID (بدون پماد)
    nsaid_keywords = [
        'ibuprofen', 'gelofen', 'indomethacin', 'diclofenac', 'naproxen',
        'meloxicam', 'piroxicam', 'celecoxib', 'mefenamic', 'aspirin',
        'ketorolac', 'ketoprofen', 'flurbiprofen', 'tenoxicam', 'nimesulide',
        'پروفن', 'ژلوفن', 'دیکلوفناک', 'ناپروکسن', 'مفنامیک'
    ]
    is_nsaid = (not is_oint) and any(k in name_lower for k in nsaid_keywords)
    
    # ۶. کورتیکواستروئیدها (بدون پماد)
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
    """فیلتر کردن لیست داروها بر اساس دسته انتخابی کاربر"""
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

load_settings()

# بازیابی فایل شاخص‌های کل
if 'df' not in st.session_state or st.session_state.df is None:
    if os.path.exists(DATA_FILE):
        try:
            st.session_state.df = pd.read_excel(DATA_FILE)
        except Exception:
            st.session_state.df = None
    else:
        st.session_state.df = None

# بازیابی فایل اقلام دارویی
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
            target_doc = selected_doc.strip() if selected_doc else ""
            if not target_doc:
                st.error("لطفاً نام خود را مشخص کنید.")
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

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📈 مقایسه کل پزشکان", 
            "👤 بررسی فردی پزشکان", 
            "💊 درصد دارو به پزشک", 
            "📋 دارو به نسخه",
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

        # --- لیست گزینه‌های فیلتر دارویی مشترک ---
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

                # پاکسازی مقادیر
                df_d[qty_c] = pd.to_numeric(df_d[qty_c], errors='coerce').fillna(0)
                df_d[drug_c] = df_d[drug_c].astype(str).str.strip()

                # حذف داروهای با مجموع تجویز صفر
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

        # --- تب ۴: دارو به نسخه (جدید) ---
        with tab4:
            st.header("📋 میزان تجویز هر دارو به ازای هر نسخه (تلفیق دو فایل اکسل)")
            st.markdown("این تب با تقسیم **مجموع عدد داروی تجویز شده** بر **تعداد کل نسخ هر پزشک**، میزان تجویز دارو در هر نسخه را محاسبه می‌کند.")

            if st.session_state.df is None or st.session_state.df_drugs is None:
                st.error("⚠️ برای استفاده از این بخش، باید هم فایل **شاخص‌های کل درمانگاه** (دارای تعداد نسخ) و هم فایل **اقلام دارویی** بارگذاری شده باشند.")
            else:
                df_main = st.session_state.df.copy()
                df_d = st.session_state.df_drugs.copy()

                main_doc_col = df_main.columns[0]
                metrics = df_main.columns[1:]

                # پیدا کردن خودکار ستون تعداد نسخ
                rx_candidates = [c for c in metrics if any(kw in c for kw in ['نسخه', 'نسخ', 'کل', 'ویزیت', 'تعداد'])]
                default_rx_col = rx_candidates[0] if rx_candidates else metrics[0]

                rx_col = st.selectbox(
                    "📌 ستون مربوط به تعداد کل نسخ / ویزیت پزشکان را تایید کنید:", 
                    metrics, 
                    index=metrics.tolist().index(default_rx_col) if default_rx_col in metrics.tolist() else 0,
                    key="select_rx_col"
                )

                drug_doc_col = df_d.columns[0]
                drug_name_col = df_d.columns[1]
                drug_qty_col = df_d.columns[2]

                df_d[drug_qty_col] = pd.to_numeric(df_d[drug_qty_col], errors='coerce').fillna(0)
                df_d[drug_name_col] = df_d[drug_name_col].astype(str).str.strip()

                # حذف داروهای با کل تجویز صفر
                drug_totals = df_d.groupby(drug_name_col)[drug_qty_col].sum()
                valid_drugs = drug_totals[drug_totals > 0].index.tolist()

                if not valid_drugs:
                    st.warning("هیچ دارویی با مجموع تجویز بیشتر از صفر یافت نشد.")
                else:
                    form_filter_rx = st.radio("🔍 انتخاب فیلتر دسته‌بندی دارویی:", filter_options, horizontal=True, key="filter_tab4")
                    selectable_drugs_rx = filter_drug_list(valid_drugs, form_filter_rx)

                    if not selectable_drugs_rx:
                        st.info("دارویی در دسته انتخابی یافت نشد.")
                    else:
                        selected_drug_rx = st.selectbox("🔍 داروی مورد نظر را انتخاب یا سرچ کنید:", selectable_drugs_rx, key="select_drug_tab4")

                        if selected_drug_rx:
                            # محاسبه تجویز هر پزشک برای این دارو
                            drug_df = df_d[df_d[drug_name_col] == selected_drug_rx]
                            doc_drug_sum = drug_df.groupby(drug_doc_col)[drug_qty_col].sum().reset_index()

                            # استخراج تعداد نسخ پزشکان از اکسل اصلی
                            doc_rx_counts = df_main[[main_doc_col, rx_col]].copy()
                            doc_rx_counts[rx_col] = pd.to_numeric(doc_rx_counts[rx_col], errors='coerce').fillna(0)

                            # ادغام دو جدول بر اساس نام پزشک
                            merged_df = pd.merge(doc_drug_sum, doc_rx_counts, left_on=drug_doc_col, right_on=main_doc_col, how='inner')
                            
                            # حذف پزشکان بدون نسخه یا بدون تجویز این دارو
                            merged_df = merged_df[(merged_df[drug_qty_col] > 0) & (merged_df[rx_col] > 0)].copy()

                            if merged_df.empty:
                                st.warning("اطلاعات مشترکی بین پزشکان دو فایل برای این دارو یافت نشد.")
                            else:
                                # محاسبه شاخص دارو به نسخه
                                merged_df['میزان_به_ازای_نسخه'] = merged_df[drug_qty_col] / merged_df[rx_col]
                                merged_df['برچسب_نمودار'] = merged_df.apply(
                                    lambda r: f"{r['میزان_به_ازای_نسخه']:.2f} عدد (کل: {int(r[drug_qty_col]):,} از {int(r[rx_col]):,} نسخه)", 
                                    axis=1
                                )

                                st.markdown("---")
                                st.subheader(f"📊 میزان تجویز داروی `{selected_drug_rx}` به ازای هر نسخه")

                                fig_rx = px.bar(
                                    merged_df,
                                    x=drug_doc_col,
                                    y='میزان_به_ازای_نسخه',
                                    text='برچسب_نمودار',
                                    labels={drug_doc_col: 'نام پزشک', 'میزان_به_ازای_نسخه': 'عدد دارو در هر نسخه'},
                                    color='میزان_به_ازای_نسخه',
                                    color_continuous_scale='Tealgrn',
                                    title=f"میانگین عدد تجویز {selected_drug_rx} در هر نسخه به تفکیک پزشک"
                                )
                                fig_rx.update_traces(textposition='outside')
                                fig_rx.update_layout(yaxis_title="تعداد دارو به ازای هر نسخه", xaxis_title="نام پزشک")
                                st.plotly_chart(fig_rx, use_container_width=True)

                                # خلاصه آمار زیر نمودار
                                total_prescribed = merged_df[drug_qty_col].sum()
                                total_prescriptions = merged_df[rx_col].sum()
                                overall_avg = total_prescribed / total_prescriptions if total_prescriptions > 0 else 0

                                col_m1, col_m2, col_m3 = st.columns(3)
                                with col_m1:
                                    st.metric("📦 کل عدد تجویز شده دارو", f"{int(total_prescribed):,} عدد")
                                cheerfully_with = col_m2.metric("📜 مجموع کل نسخ پزشکان", f"{int(total_prescriptions):,} نسخه")
                                with col_m3:
                                    st.metric("📊 میانگین کلی درمانگاه", f"{overall_avg:.2f} عدد در هر نسخه")

                                st.subheader("📋 جدول تفکیکی اطلاعات")
                                display_table = merged_df[[drug_doc_col, drug_qty_col, rx_col, 'میزان_به_ازای_نسخه']].copy()
                                display_table.columns = ['نام پزشک', 'تعداد کل تجویز دارو', 'تعداد کل نسخ', 'میزان به ازای هر نسخه']
                                display_table['میزان به ازای هر نسخه'] = display_table['میزان به ازای هر نسخه'].round(2)
                                st.dataframe(display_table.set_index('نام پزشک'), use_container_width=True)

        # --- تب ۵: بازخوردها ---
        with tab5:
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

        # --- تب ۶: PDF ---
        with tab6:
            st.info("برای چاپ یا ذخیره PDF گزارشات، از گزینه Print مرورگر (Ctrl+P) استفاده کنید.")

    # -------------------------------------------------------------
    # ۲. بخش دسترسی محدود پزشک (DOCTOR)
    # -------------------------------------------------------------
    elif st.session_state.user_role == "doctor":
        current_doc = st.session_state.doctor_name
        st.title(f"👨‍⚕️ پنل اختصاصی ارتقای عملکرد: {current_doc}")

        has_gen_note = bool(st.session_state.get('admin_general_notes', '').strip())
        has_doc_note = bool(st.session_state.get('admin_doctor_notes', {}).get(current_doc, '').strip())

        if has_gen_note or has_doc_note:
            st.subheader("📮 پیام‌ها و توصیه‌های مدیریت درمانگاه")
            if has_gen_note:
                st.info(f"**📢 اطلاعیه عمومی مدیریت:**\n\n{st.session_state.admin_general_notes}")
            if has_doc_note:
                st.warning(f"**✉️ توصیه اختصاصی مدیریت برای شما ({current_doc}):**\n\n{st.session_state.admin_doctor_notes[current_doc]}")
            st.markdown("---")

        if st.session_state.df is None:
            st.warning("⚠️ اطلاعات درمانگاه هنوز توسط مدیر بارگذاری نشده است.")
        else:
            df = st.session_state.df
            doctor_col = df.columns[0]
            metrics = df.columns[1:]

            if current_doc not in df[doctor_col].values:
                st.error(f"❌ نام شما ({current_doc}) در فایل اکسل پیدا نشد.")
            else:
                doc_data = df[df[doctor_col] == current_doc].iloc[0]
                numeric_df = df[metrics].apply(pd.to_numeric, errors='coerce')
                avg_data = numeric_df.mean()
                df_ranks = calculate_ranks(df, metrics)
                doc_ranks = df_ranks[df_ranks[doctor_col] == current_doc].iloc[0]

                st.subheader("📋 خلاصه آمار و رتبه شما در درمانگاه")
                cols = st.columns(2)
                for i, metric in enumerate(metrics):
                    with cols[i % 2]:
                        st.metric(
                            label=metric, 
                            value=f"{doc_data[metric]}", 
                            delta=f"رتبه {doc_ranks[metric]} از {len(df)}",
                            delta_color="inverse" if "ویزیت" not in metric and "آزمایشگاه" not in metric and "نسخ" not in metric else "normal"
                        )

                st.markdown("---")
                st.subheader("⚠️ تحلیل هوشمند وضعیت تجویزی شما")
                warnings, goods, critical_metrics = [], [], []

                for metric in metrics:
                    val = pd.to_numeric(doc_data[metric], errors='coerce')
                    if pd.isna(val):
                        continue
                    avg = avg_data[metric]
                    
                    if "ویزیت" not in metric and "آزمایشگاه" not in metric and "نسخ" not in metric:
                        if avg > 0 and val > avg * 1.2:
                            warnings.append(f"🔴 **نیازمند اصلاح در {metric}:** میزان تجویز شما ({val}) بالاتر از میانگین درمانگاه ({round(avg, 1)}) است.")
                            critical_metrics.append((metric, val, avg))
                        elif avg > 0 and val > avg:
                            warnings.append(f"🟡 **هشدار در {metric}:** تجویز شما ({val}) کمی بالاتر از میانگین درمانگاه ({round(avg, 1)}) است.")
                        else:
                            goods.append(f"🟢 **عملکرد مطلوب در {metric}:** تجویز شما ({val}) در محدوده استانداردهای درمانگاه است.")
                    else:
                        if avg > 0 and val < avg * 0.8:
                            warnings.append(f"🟡 **توجه در {metric}:** آمار شما ({val}) پایین‌تر از میانگین درمانگاه ({round(avg, 1)}) است.")
                        else:
                            goods.append(f"🟢 **وضعیت مناسب در {metric}:** آمار شما در سطح مطلوب قرار دارد.")

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

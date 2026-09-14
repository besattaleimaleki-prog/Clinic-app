import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json

st.set_page_config(page_title="سیستم ارزیابی نسخ درمانگاه", layout="wide")

DATA_FILE = "saved_clinic_data.xlsx"
SETTINGS_FILE = "system_settings.json"

# ------------------ مدیریت ذخیره و بازیابی دائمی داده‌ها ------------------
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
    """محاسبه ایمن رتبه‌ها با پشتیبانی از خانه‌های خالی و مقادیر متنی"""
    df_ranks = df.copy()
    for col in metrics:
        numeric_col = pd.to_numeric(df[col], errors='coerce')
        if "ویزیت" in col or "آزمایشگاه" in col:
            ranks = numeric_col.rank(ascending=False, method='min')
        else:
            ranks = numeric_col.rank(ascending=True, method='min')
        df_ranks[col] = ranks.fillna(0).astype(int)
    return df_ranks

# ------------------ توابع راهنمای بالینی ------------------
def get_clinical_guideline(metric_name, user_val, avg_val):
    metric_lower = metric_name.lower()
    
    if any(kw in metric_lower for kw in ['آنتی', 'بیوتیک', 'چرك', 'عفونت', 'کپسول']):
        return (
            "🦠 **گایدلاین مدیریت تجویز آنتی‌بیوتیک (CDC & WHO Antibiotic Stewardship):**\n\n"
            "طبق گزارش‌های سازمان جهانی بهداشت (WHO) و CDC، بیش از ۶۰ تا ۷۰ درصد عفونت‌های حاد تنفسی فوقانی در مراقبت‌های سرپایی منشأ ویروسی دارند و نیازی به دریافت آنتی‌بیوتیک ندارند. "
            "توصیه می‌شود در مواجهه با علائم تنفسی خفیف تا متوسط، از الگوریتم طبقه‌بندی **AWaRe** استفاده کرده و درمان‌های حمایتی را در اولویت قرار دهید. "
            "کاهش تجویزهای غیرضروری آنتی‌بیوتیک نه تنها موقعیت کیفی شما را در ارزیابی‌های درمانگاه ارتقا می‌دهد، بلکه از بروز مقاومت‌های میکروبی کشنده جلوگیری می‌کند."
        )
    elif any(kw in metric_lower for kw in ['تزریق', 'آمپول', 'ویال']):
        return (
            "💉 **راهنمای تجویز منطقی داروهای تزریقی (WHO Injection Safety Guidelines):**\n\n"
            "بر اساس استانداردهای WHO، اولویت اول در بیماران سرپایی همواره با **مسیر خوراکی** است. زیست‌دست‌یابی اکثر داروهای خوراکی مدرن برابری لازم با فرم تزریقی را دارد. "
            "جایگزینی فرم خوراکی، احتمال عوارض خطرساز مانند شوک آنافیلاکسی و هزینه‌های تحمیلی به بیمار را تا ۸۰٪ کاهش می‌دهد."
        )
    elif any(kw in metric_lower for kw in ['کورتون', 'استروئید', 'دگزا', 'بتامتازون', 'هیدروکورتیزون']):
        return (
            "🛡️ **گایدلاین بالینی مصرف کورتیکواستروئیدها (NICE & WHO):**\n\n"
            "تجویز بی‌رویه کورتون‌های سیستمیک در بیماری‌های ویروسی شایع، علاوه بر تضعیف سیستم ایمنی، خطر عوارض متابولیک و اختلالات هورمونی را افزایش می‌دهد. "
            "بر اساس گایدلاین‌های بالینی NICE، تجویز کورتون‌ها باید محدود به اندیکاسیون‌های قطعی (مانند حمله حاد آسم یا بیماری‌های خودایمنی) باشد."
        )
    elif any(kw in metric_lower for kw in ['تعداد', 'اقلام', 'میانگین قلم', 'قلم']):
        return (
            "💊 **راهنمای پیشگیری از پلی‌فارماسی (WHO Rational Drug Use):**\n\n"
            "شاخص جهانی WHO برای میانگین تعداد اقلام دارو در هر نسخه سرپایی، **حداکثر ۱.۸ تا ۲.۲ قلم** است. "
            "افزایش تعداد اقلام نسخه (Polypharmacy) خطر تداخلات دارویی ناخواسته و عوارض جانبی را بالا می‌برد."
        )
    else:
        return (
            f"📖 **توصیه علمی بر اساس پزشکی مبتنی بر شواهد (EBM) در شاخص {metric_name}:**\n\n"
            f"میزان تجویز شما در شاخص **{metric_name}** با میانگین استاندارد درمانگاه فاصله دارد. "
            "بررسی مجدد رفرنس‌های بالینی روز دنیا به شما کمک می‌کند تا علاوه بر بهبود پیامدهای درمانی بیماران، رتبه کیفی خود را ارتقا دهید."
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

if 'df' not in st.session_state or st.session_state.df is None:
    if os.path.exists(DATA_FILE):
        try:
            st.session_state.df = pd.read_excel(DATA_FILE)
        except Exception:
            st.session_state.df = None
    else:
        st.session_state.df = None

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
                
    else:  # ورود پزشک
        st.subheader("ورود اختصاصی پزشک")
        
        if st.session_state.df is not None:
            df = st.session_state.df
            doctor_col = df.columns[0]
            doctors_list = df[doctor_col].dropna().tolist()
            selected_doc = st.selectbox("نام خود را انتخاب کنید:", doctors_list)
        else:
            st.info("ℹ️ اطلاعات درمانگاه هنوز توسط مدیر بارگذاری نشده است. پس از ورود مدیر و آپلود فایل، کارنامه شما فعال خواهد شد.")
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

# ------------------ پنل پس از ورود (Logged-in Panel) ------------------
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
        
        st.subheader("📁 بارگذاری داده‌های درمانگاه")
        
        if os.path.exists(DATA_FILE):
            st.info("💡 یک فایل اکسل ذخیره‌شده از قبل در سیستم موجود است. در صورت نیاز می‌توانید فایل جدیدی را جایگزین کنید.")

        uploaded_file = st.file_uploader("لطفاً فایل اکسل خروجی سیستم را آپلود کنید", type=["xlsx", "xls"])
        
        if uploaded_file is not None:
            try:
                df_new = pd.read_excel(uploaded_file)
            except Exception:
                try:
                    uploaded_file.seek(0)
                    df_new = pd.read_html(uploaded_file)[0]
                except Exception:
                    st.error("❌ خطا در خواندن فایل اکسل. لطفاً فرمت فایل را بررسی کنید.")
                    df_new = None

            if df_new is not None:
                st.session_state.df = df_new
                df_new.to_excel(DATA_FILE, index=False)
                st.success("فایل اکسل با موفقیت بارگذاری و به صورت دائمی در سیستم ذخیره شد.")

        if st.session_state.df is not None:
            df = st.session_state.df
            doctor_col = df.columns[0]
            metrics = df.columns[1:]
            
            df_ranks = calculate_ranks(df, metrics)

            tab1, tab2, tab3, tab4 = st.tabs(["📈 مقایسه کل پزشکان", "👤 بررسی فردی پزشکان", "📝 بازخورد و توصیه‌های مدیریت", "💾 خروجی PDF"])

            with tab1:
                st.header("مقایسه کلی تمام پزشکان")
                selected_metric = st.selectbox("انتخاب شاخص:", metrics)
                fig_bar = px.bar(df, x=doctor_col, y=selected_metric, text_auto=True, color=selected_metric, color_continuous_scale="Viridis")
                st.plotly_chart(fig_bar, use_container_width=True)
                st.subheader("جدول رتبه‌بندی کلی")
                st.dataframe(df_ranks.set_index(doctor_col))

            with tab2:
                st.header("بررسی اختصاصی پزشکان (دسترسی مدیریتی)")
                doctors_list = df[doctor_col].dropna().tolist()
                selected_doc = st.selectbox("انتخاب پزشک جهت بررسی:", doctors_list)
                doc_data = df[df[doctor_col] == selected_doc].iloc[0]
                doc_ranks = df_ranks[df_ranks[doctor_col] == selected_doc].iloc[0]
                
                st.subheader(f"کارنامه کامل: {selected_doc}")
                cols = st.columns(2)
                for i, metric in enumerate(metrics):
                    with cols[i % 2]:
                        st.metric(label=metric, value=f"{doc_data[metric]}", delta=f"رتبه {doc_ranks[metric]} از {len(df)}")

            with tab3:
                st.header("📝 مدیریت توصیه‌ها و بازخوردهای مدیریت")
                
                st.subheader("📢 پیام و توصیه عمومی (قابل مشاهده برای تمام پزشکان)")
                gen_note = st.text_area("متن پیام عمومی مدیریت:", value=st.session_state.admin_general_notes, height=100)
                if st.button("ذخیره پیام عمومی", type="primary"):
                    st.session_state.admin_general_notes = gen_note
                    save_settings()
                    st.success("پیام عمومی مدیریت با موفقیت ذخیره شد.")

                st.markdown("---")

                st.subheader("✉️ توصیه و بازخورد اختصاصی به یک پزشک مشخص")
                doctors_list = df[doctor_col].dropna().tolist()
                selected_target_doc = st.selectbox("پزشک مورد نظر را انتخاب کنید:", doctors_list, key="admin_target_doc")
                current_doc_note = st.session_state.admin_doctor_notes.get(selected_target_doc, "")
                spec_note = st.text_area(f"متن توصیه اختصاصی برای {selected_target_doc}:", value=current_doc_note, height=120)
                if st.button(f"ذخیره توصیه اختصاصی برای {selected_target_doc}", type="primary"):
                    st.session_state.admin_doctor_notes[selected_target_doc] = spec_note
                    save_settings()
                    st.success(f"توصیه اختصاصی برای {selected_target_doc} با موفقیت ذخیره شد.")

            with tab4:
                st.info("برای چاپ یا ذخیره PDF گزارشات کل، از گزینه Print مرورگر استفاده کنید.")

        else:
            st.warning("⚠️ هنوز هیچ فایل اکسلی بارگذاری نشده است. برای دسترسی به بخش بازخوردها و تحلیل‌ها، ابتدا فایل اکسل را بارگذاری نمایید.")

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
            st.warning("⚠️ اطلاعات درمانگاه هنوز توسط مدیر بارگذاری نشده است. لطفاً منتظر بمانید تا مدیر فایل اکسل را آپلود کند.")
        else:
            df = st.session_state.df
            doctor_col = df.columns[0]
            metrics = df.columns[1:]

            if current_doc not in df[doctor_col].values:
                st.error(f"❌ نام شما ({current_doc}) در فایل اکسل بارگذاری‌شده پیدا نشد. لطفاً با مدیر سیستم تماس بگیرید.")
            else:
                doc_data = df[df[doctor_col] == current_doc].iloc[0]
                
                # محاسبه میانگین فقط روی مقادیر عددی معتبر
                numeric_df = df[metrics].apply(pd.to_numeric, errors='coerce')
                avg_data = numeric_df.mean()
                
                df_ranks = calculate_ranks(df, metrics)
                doc_ranks = df_ranks[df_ranks[doctor_col] == current_doc].iloc[0]

                st.markdown("این گزارش جهت بررسی عملکرد شخص شما، مقایسه با استاندارد درمانگاه و ارائه توصیه‌های علمی تنظیم شده است.")

                st.subheader("📋 خلاصه آمار و رتبه شما در درمانگاه")
                cols = st.columns(2)
                for i, metric in enumerate(metrics):
                    with cols[i % 2]:
                        st.metric(
                            label=metric, 
                            value=f"{doc_data[metric]}", 
                            delta=f"رتبه {doc_ranks[metric]} از {len(df)}",
                            delta_color="inverse" if "ویزیت" not in metric and "آزمایشگاه" not in metric else "normal"
                        )

                st.markdown("---")

                st.subheader("⚠️ تحلیل هوشمند وضعیت تجویزی شما")
                warnings, goods = [], []
                critical_metrics = []

                for metric in metrics:
                    val = pd.to_numeric(doc_data[metric], errors='coerce')

                    if pd.isna(val):
                        continue

                    avg = avg_data[metric]
                    
                    if "ویزیت" not in metric and "آزمایشگاه" not in metric:
                        if avg > 0 and val > avg * 1.2:
                            warnings.append(f"🔴 **نیازمند اصلاح در {metric}:** میزان تجویز شما ({val}) بالاتر از میانگین درمانگاه ({round(avg, 1)}) است.")
                            critical_metrics.append((metric, val, avg))
                        elif avg > 0 and val > avg:
                            warnings.append(f"🟡 **هشدار در {metric}:** تجویز شما ({val}) کمی بالاتر از میانگین درمانگاه ({round(avg, 1)}) است.")
                        else:
                            goods.append(f"🟢 **عملکرد مطلوب در {metric}:** تجویز شما ({val}) مناسب و در محدوده استانداردهای درمانگاه است.")
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

                st.subheader("💡 توصیه‌ها و گایدلاین‌های بالینی روز دنیا (WHO / CDC) برای ارتقای عملکرد")
                
                if critical_metrics:
                    st.info("بر اساس نقاط ضعف شناسایی‌شده در نسخ شما، راهنماهای زیر از مرجع سازمان جهانی بهداشت (WHO) و CDC جهت اصلاح الگوهای تجویزی استخراج شده است:")
                    for metric, val, avg in critical_metrics:
                        guideline_text = get_clinical_guideline(metric, val, avg)
                        with st.expander(f"📌 راهنمای بالینی و گایدلاین علمی برای: {metric}", expanded=True):
                            st.markdown(guideline_text)
                else:
                    st.success("🎉 **تبریک!** عملکرد تجویزی شما کاملاً منطبق بر استانداردهای درمانگاه و گایدلاین‌های بین‌المللی است.")

                st.markdown("---")

                st.subheader("📊 مقایسه عملکرد شما با میانگین کل درمانگاه")
                doc_vals = [pd.to_numeric(doc_data[m], errors='coerce') for m in metrics]
                comp_df = pd.DataFrame({
                    'شاخص': list(metrics) * 2,
                    'مقدار': doc_vals + list(avg_data.values),
                    'مرجع': ['عملکرد شما'] * len(metrics) + ['میانگین درمانگاه'] * len(metrics)
                })

                fig_compare = px.bar(
                    comp_df,
                    y='شاخص',
                    x='مقدار',
                    color='مرجع',
                    barmode='group',
                    orientation='h',
                    text_auto='.1f',
                    title="مقایسه مقادیر شما در برابر میانگین درمانگاه",
                    color_discrete_map={'عملکرد شما': '#1f77b4', 'میانگین درمانگاه': '#ff7f0e'}
                )
                st.plotly_chart(fig_compare, use_container_width=True)

                st.subheader("🎯 درصد انحراف شما از میانگین درمانگاه")
                pct_diff = []
                for m in metrics:
                    v = pd.to_numeric(doc_data[m], errors='coerce')
                    a = avg_data[m]
                    if pd.notna(v) and pd.notna(a) and a != 0:
                        pct_diff.append(((v - a) / a) * 100)
                    else:
                        pct_diff.append(0)

                diff_df = pd.DataFrame({'شاخص': metrics, 'درصد انحراف': pct_diff})
                diff_df['وضعیت'] = diff_df['درصد انحراف'].apply(lambda x: 'بالاتر از میانگین' if x > 0 else 'پایین‌تر از میانگین')

                fig_diff = px.bar(
                    diff_df,
                    y='شاخص',
                    x='درصد انحراف',
                    color='وضعیت',
                    orientation='h',
                    text=diff_df['درصد انحراف'].apply(lambda x: f"{x:+.1f}%"),
                    title="میزان انحراف (اعداد مثبت به معنی بالاتر بودن از میانگین درمانگاه است)",
                    color_discrete_map={'بالاتر از میانگین': '#d62728', 'پایین‌تر از میانگین': '#2ca02c'}
                )
                fig_diff.add_vline(x=0, line_dash="dash", line_color="black")
                st.plotly_chart(fig_diff, use_container_width=True)

        st.markdown("---")
        with st.expander("🔑 تغییر رمز عبور حساب کاربری"):
            st.write("در صورت تمایل می‌توانید رمز عبور ورود خود را تغییر دهید:")
            old_pass = st.text_input("رمز عبور فعلی:", type="password")
            new_pass = st.text_input("رمز عبور جدید:", type="password")
            confirm_pass = st.text_input("تکرار رمز عبور جدید:", type="password")
            
            if st.button("ثبت رمز عبور جدید"):
                current_pass = st.session_state.doctor_passwords.get(current_doc, DOCTOR_DEFAULT_PASSWORD)
                if old_pass != current_pass:
                    st.error("رمز عبور فعلی وارد شده نادرست است.")
                elif not new_pass or len(new_pass.strip()) < 4:
                    st.error("رمز عبور جدید باید حداقل ۴ کاراکتر باشد.")
                elif new_pass != confirm_pass:
                    st.error("رمز عبور جدید و تکرار آن یکسان نیستند.")
                else:
                    st.session_state.doctor_passwords[current_doc] = new_pass
                    save_settings()
                    st.success("رمز عبور شما با موفقیت تغییر کرد.")

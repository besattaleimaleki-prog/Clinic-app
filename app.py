import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="سیستم ارزیابی نسخ درمانگاه", layout="wide")

# ------------------ مدیریت وضعیت نشست (Session State) ------------------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'doctor_name' not in st.session_state:
    st.session_state.doctor_name = None
if 'df' not in st.session_state:
    st.session_state.df = None

# تنظیمات رمزهای عبور
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
            doctors_list = df[doctor_col].tolist()
            selected_doc = st.selectbox("نام خود را انتخاب کنید:", doctors_list)
        else:
            st.info("ℹ️ اطلاعات درمانگاه هنوز توسط مدیر بارگذاری نشده است. پس از ورود مدیر و آپلود فایل، کارنامه شما فعال خواهد شد.")
            selected_doc = st.text_input("نام و نام خانوادگی پزشک:")
            
        doc_password = st.text_input("رمز عبور اختصاصی (پیش‌فرض: 1234)", type="password")
        
        if st.button("ورود به پنل پزشک", type="primary"):
            if not selected_doc or len(selected_doc.strip()) == 0:
                st.error("لطفاً نام خود را مشخص کنید.")
            elif doc_password == DOCTOR_DEFAULT_PASSWORD:
                st.session_state.logged_in = True
                st.session_state.user_role = "doctor"
                st.session_state.doctor_name = selected_doc.strip()
                st.success(f"خوش آمدید {selected_doc}")
                st.rerun()
            else:
                st.error("رمز عبور اشتباه است.")

# ------------------ پنل پس از ورود (Logged-in Panel) ------------------
else:
    # نوار کناری برای خروج و اطلاعات کاربری
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
        uploaded_file = st.file_uploader("لطفاً فایل اکسل خروجی سیستم را آپلود کنید", type=["xlsx", "xls"])
        
        if uploaded_file is not None:
            st.session_state.df = pd.read_excel(uploaded_file)
            st.success("فایل اکسل با موفقیت بارگذاری شد.")

        if st.session_state.df is not None:
            df = st.session_state.df
            doctor_col = df.columns[0]
            metrics = df.columns[1:]
            
            # محاسبه رتبه‌ها
            df_ranks = df.copy()
            for col in metrics:
                if "ویزیت" in col or "آزمایشگاه" in col:
                    df_ranks[col] = df[col].rank(ascending=False, method='min').astype(int)
                else:
                    df_ranks[col] = df[col].rank(ascending=True, method='min').astype(int)

            tab1, tab2, tab3 = st.tabs(["📈 مقایسه کل پزشکان", "👤 بررسی فردی پزشکان", "💾 خروجی PDF"])

            with tab1:
                st.header("مقایسه کلی تمام پزشکان")
                selected_metric = st.selectbox("انتخاب شاخص:", metrics)
                fig_bar = px.bar(df, x=doctor_col, y=selected_metric, text_auto=True, color=selected_metric, color_continuous_scale="Viridis")
                st.plotly_chart(fig_bar, use_container_width=True)
                st.subheader("جدول رتبه‌بندی کلی")
                st.dataframe(df_ranks.set_index(doctor_col))

            with tab2:
                st.header("بررسی اختصاصی پزشکان (دسترسی مدیریتی)")
                selected_doc = st.selectbox("انتخاب پزشک جهت بررسی:", df[doctor_col].tolist())
                doc_data = df[df[doctor_col] == selected_doc].iloc[0]
                doc_ranks = df_ranks[df_ranks[doctor_col] == selected_doc].iloc[0]
                avg_data = df[metrics].mean()
                
                st.subheader(f"کارنامه کامل: {selected_doc}")
                cols = st.columns(2)
                for i, metric in enumerate(metrics):
                    with cols[i % 2]:
                        st.metric(label=metric, value=f"{doc_data[metric]}", delta=f"رتبه {doc_ranks[metric]} از {len(df)}")

            with tab3:
                st.info("برای چاپ یا ذخیره PDF گزارشات کل، از گزینه Print مرورگر (Share > Print در گوشی) استفاده کنید.")

        else:
            st.warning("⚠️ هنوز هیچ فایل اکسلی بارگذاری نشده است. برای فعال شدن داشبورد، لطفاً کادر بالا را لمس کرده و فایل اکسل را آپلود کنید.")

    # -------------------------------------------------------------
    # ۲. بخش دسترسی محدود پزشک (DOCTOR)
    # -------------------------------------------------------------
    elif st.session_state.user_role == "doctor":
        st.title(f"👨‍⚕️ پنل اختصاصی: {st.session_state.doctor_name}")

        if st.session_state.df is None:
            st.warning("⚠️ اطلاعات درمانگاه هنوز توسط مدیر بارگذاری نشده است. لطفاً منتظر بمانید تا مدیر فایل اکسل را آپلود کند.")
        else:
            df = st.session_state.df
            doctor_col = df.columns[0]
            metrics = df.columns[1:]
            current_doc = st.session_state.doctor_name

            if current_doc not in df[doctor_col].values:
                st.error(f"❌ نام شما ({current_doc}) در فایل اکسل بارگذاری‌شده پیدا نشد. لطفاً با مدیر سیستم تماس بگیرید.")
            else:
                doc_data = df[df[doctor_col] == current_doc].iloc[0]
                avg_data = df[metrics].mean()
                
                # محاسبه رتبه
                df_ranks = df.copy()
                for col in metrics:
                    if "ویزیت" in col or "آزمایشگاه" in col:
                        df_ranks[col] = df[col].rank(ascending=False, method='min').astype(int)
                    else:
                        df_ranks[col] = df[col].rank(ascending=True, method='min').astype(int)
                doc_ranks = df_ranks[df_ranks[doctor_col] == current_doc].iloc[0]

                st.markdown("این گزارش صرفاً جهت بررسی عملکرد شخص شما و مقایسه با استاندارد درمانگاه تنظیم شده است.")

                # ۱. خلاصه عملکرد
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

                # ۲. هشدارهای هوشمند
                st.subheader("⚠️ تحلیل هوشمند و هشدارهای تجویزی شما")
                warnings, goods = [], []
                for metric in metrics:
                    val = doc_data[metric]
                    avg = avg_data[metric]
                    diff = val - avg
                    
                    if "ویزیت" not in metric and "آزمایشگاه" not in metric:
                        if val > avg * 1.25:
                            warnings.append(f"🔴 **توصیه اصلاحی در {metric}:** میزان تجویز شما ({val}) بالاتر از میانگین درمانگاه ({round(avg, 1)}) است.")
                        elif val > avg:
                            warnings.append(f"🟡 **هشدار در {metric}:** تجویز شما ({val}) کمی بالاتر از میانگین درمانگاه ({round(avg, 1)}) است.")
                        else:
                            goods.append(f"🟢 **عملکرد مطلوب در {metric}:** تجویز شما ({val}) کمتر از میانگین درمانگاه ({round(avg, 1)}) و مناسب است.")
                    else:
                        if val < avg * 0.75:
                            warnings.append(f"🟡 **توجه در {metric}:** آمار شما ({val}) پایین‌تر از میانگین درمانگاه ({round(avg, 1)}) است.")
                        else:
                            goods.append(f"🟢 **وضعیت مناسب در {metric}:** آمار شما در سطح مطلوب قرار دارد.")

                if warnings:
                    st.error("### موارد نیازمند بازبینی")
                    for w in warnings:
                        st.write(w)
                if goods:
                    st.success("### نقاط قوت")
                    for g in goods:
                        st.write(g)

                st.markdown("---")

                # ۳. نمودارهای افقی مقایسه فرد با میانگین
                st.subheader("📊 مقایسه عملکرد شما با میانگین کل درمانگاه")
                
                comp_df = pd.DataFrame({
                    'شاخص': list(metrics) * 2,
                    'مقدار': list(doc_data[metrics].values) + list(avg_data.values),
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

                # ۴. میزان درصد انحراف
                st.subheader("🎯 درصد انحراف شما از میانگین درمانگاه")
                pct_diff = [((doc_data[m] - avg_data[m]) / avg_data[m]) * 100 if avg_data[m] != 0 else 0 for m in metrics]
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

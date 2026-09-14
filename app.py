import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# تنظیمات صفحه
st.set_page_config(page_title="داشبورد ارزیابی نسخ پزشکان", layout="wide")

st.title("📊 سیستم کنترل و ارزیابی عملکرد تجویزی پزشکان")
st.markdown("این اپلیکیشن جهت بررسی، رتبه‌بندی و گزارش‌گیری از عملکرد پزشکان بر اساس فایل اکسل طراحی شده است.")

# 1. دریافت فایل اکسل
uploaded_file = st.file_uploader("لطفاً فایل اکسل خروجی سیستم را آپلود کنید", type=["xlsx", "xls"])

if uploaded_file is not None:
    # خواندن داده‌ها
    df = pd.read_excel(uploaded_file)
    
    # فرض می‌کنیم ستون اول نام پزشک است
    doctor_col = df.columns[0]
    metrics = df.columns[1:]
    
    # 3. محاسبه رتبه‌ها (رتبه 1 یعنی کمترین مقدار در مواردی مثل آنتی‌بیوتیک که مطلوب‌تر است)
    # برای برخی آیتم‌ها مثل "تعداد ویزیت" یا "ارجاع به آزمایشگاه" ممکن است رتبه بالا مطلوب باشد.
    # در اینجا به صورت پیش‌فرض رتبه 1 را به کمترین مقدار (بهترین عملکرد در تجویز دارو) اختصاص می‌دهیم.
    df_ranks = df.copy()
    for col in metrics:
        if "ویزیت" in col or "آزمایشگاه" in col:
            df_ranks[col] = df[col].rank(ascending=False, method='min').astype(int)
        else:
            df_ranks[col] = df[col].rank(ascending=True, method='min').astype(int)

    # ایجاد تب‌های مختلف برای نمایش
    tab1, tab2, tab3 = st.tabs(["گزارش کلی و مقایسه‌ای", "گزارش تفکیکی (پروفایل پزشک)", "راهنمای خروجی PDF"])

    with tab1:
        st.header("📈 مقایسه کلی پزشکان")
        selected_metric = st.selectbox("یک شاخص را برای مقایسه انتخاب کنید:", metrics)
        
        # نمودار میله‌ای مقایسه‌ای
        fig_bar = px.bar(df, x=doctor_col, y=selected_metric, 
                         title=f"مقایسه پزشکان بر اساس {selected_metric}",
                         text_auto=True, color=selected_metric, color_continuous_scale="Viridis")
        st.plotly_chart(fig_bar, use_container_width=True)
        
        st.subheader("جدول رتبه‌بندی کلی (عدد کمتر = رتبه بهتر در کاهش تجویز)")
        st.dataframe(df_ranks.set_index(doctor_col))

    with tab2:
        st.header("👤 پروفایل اختصاصی پزشک")
        selected_doc = st.selectbox("نام پزشک را انتخاب کنید:", df[doctor_col].tolist())
        
        doc_data = df[df[doctor_col] == selected_doc].iloc[0]
        doc_ranks = df_ranks[df_ranks[doctor_col] == selected_doc].iloc[0]
        total_docs = len(df)
        
        st.subheader(f"کارنامه عملکرد: {selected_doc}")
        
        # نمایش کارت‌های آماری به همراه رتبه
        cols = st.columns(3)
        for i, metric in enumerate(metrics):
            with cols[i % 3]:
                st.metric(
                    label=metric, 
                    value=f"{doc_data[metric]}", 
                    delta=f"رتبه {doc_ranks[metric]} از {total_docs}",
                    delta_color="inverse" if "ویزیت" not in metric else "normal"
                )
        
        # 2. نمودار رادار (عنکبوتی) برای مقایسه پزشک با میانگین کل
        st.markdown("---")
        st.subheader("نمودار وضعیت پزشک نسبت به میانگین درمانگاه")
        
        avg_data = df[metrics].mean()
        
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=doc_data[metrics].values,
            theta=metrics,
            fill='toself',
            name=selected_doc
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=avg_data.values,
            theta=metrics,
            fill='toself',
            name='میانگین درمانگاه'
        ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True)), showlegend=True)
        st.plotly_chart(fig_radar, use_container_width=True)

    with tab3:
        # 4. خروجی PDF
        st.header("💾 نحوه ذخیره گزارش به صورت PDF")
        st.info("""
        **برای ذخیره گزارشات به فرمت PDF که زیباترین و استانداردترین حالت است، از قابلیت مرورگر استفاده کنید:**
        1. به تب مورد نظر (مثلا گزارش تفکیکی پزشک) بروید.
        2. روی کیبورد کلیدهای **Ctrl + P** (در مک **Cmd + P**) را فشار دهید.
        3. در پنجره باز شده، قسمت Destination یا Printer را روی **Save as PDF** تنظیم کنید.
        4. در تنظیمات بیشتر (More settings)، تیک **Background graphics** را بزنید تا رنگ نمودارها چاپ شود.
        5. روی دکمه Save کلیک کنید.
        این روش تضمین می‌کند که تمامی نمودارهای تعاملی با بالاترین کیفیت در PDF شما ذخیره شوند.
        """)

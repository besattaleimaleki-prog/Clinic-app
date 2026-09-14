import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="داشبورد ارزیابی نسخ", layout="wide")

st.title("📊 سیستم کنترل و ارزیابی عملکرد تجویزی پزشکان")
st.markdown("این اپلیکیشن جهت بررسی، رتبه‌بندی و تحلیل هشدار هوشمند عملکرد پزشکان طراحی شده است.")

uploaded_file = st.file_uploader("لطفاً فایل اکسل درمانگاه را آپلود کنید", type=["xlsx", "xls"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    doctor_col = df.columns[0]
    metrics = df.columns[1:]
    
    # محاسبه رتبه‌ها
    df_ranks = df.copy()
    for col in metrics:
        if "ویزیت" in col or "آزمایشگاه" in col:
            df_ranks[col] = df[col].rank(ascending=False, method='min').astype(int)
        else:
            df_ranks[col] = df[col].rank(ascending=True, method='min').astype(int)

    tab1, tab2, tab3 = st.tabs(["گزارش مقایسه‌ای", "پروفایل و هشدارهای پزشک", "راهنمای خروجی PDF"])

    with tab1:
        st.header("📈 مقایسه کلی پزشکان")
        selected_metric = st.selectbox("یک شاخص را برای مقایسه انتخاب کنید:", metrics)
        fig_bar = px.bar(df, x=doctor_col, y=selected_metric, text_auto=True, color=selected_metric, color_continuous_scale="Viridis")
        st.plotly_chart(fig_bar, use_container_width=True)
        st.subheader("جدول رتبه‌بندی کلی")
        st.dataframe(df_ranks.set_index(doctor_col))

    with tab2:
        st.header("👤 کارنامه و تحلیل هوشمند نقاط ضعف پزشک")
        selected_doc = st.selectbox("نام پزشک را انتخاب کنید:", df[doctor_col].tolist())
        doc_data = df[df[doctor_col] == selected_doc].iloc[0]
        doc_ranks = df_ranks[df_ranks[doctor_col] == selected_doc].iloc[0]
        total_docs = len(df)
        avg_data = df[metrics].mean()
        
        st.subheader(f"کارنامه عملکرد: {selected_doc}")
        
        # کارت‌های شاخص‌ها
        cols = st.columns(2)
        for i, metric in enumerate(metrics):
            with cols[i % 2]:
                st.metric(
                    label=metric, 
                    value=f"{doc_data[metric]}", 
                    delta=f"رتبه {doc_ranks[metric]} از {total_docs}",
                    delta_color="inverse" if "ویزیت" not in metric and "آزمایشگاه" not in metric else "normal"
                )

        st.markdown("---")
        
        # بخش هشدارهای هوشمند و اصلاح رفتار
        st.subheader("⚠️ تحلیل هوشمند وضعیت و توصیه‌های اصلاحی")
        
        warnings = []
        goods = []
        
        for metric in metrics:
            val = doc_data[metric]
            avg = avg_data[metric]
            diff = val - avg
            
            # برای شاخص‌های دارویی (کمتر بودن بهتر است)
            if "ویزیت" not in metric and "آزمایشگاه" not in metric:
                if val > avg * 1.25:
                    warnings.append(f"🔴 **وضعیت بحرانی در {metric}:** مقدار تجویزی شما ({val}) حدود **{abs(round(diff, 1))}** واحد بالاتر از میانگین درمانگاه ({round(avg, 1)}) است. کاهش فوری تجویز توصیه می‌شود.")
                elif val > avg:
                    warnings.append(f"🟡 **هشدار در {metric}:** میزان تجویز شما ({val}) از میانگین درمانگاه ({round(avg, 1)}) بالاتر است. نیازمند بازبینی رفتار تجویزی.")
                else:
                    goods.append(f"🟢 **عملکرد مطلوب در {metric}:** میزان تجویز شما ({val}) کمتر از میانگین درمانگاه ({round(avg, 1)}) و در محدوده مناسب است.")
            
            # برای شاخص‌های ویزیت و ارجاع (بالاتر بودن یا متناسب بودن بهتر است)
            else:
                if val < avg * 0.75:
                    warnings.append(f"🟡 **توجه در {metric}:** آمار شما ({val}) پایین‌تر از میانگین درمانگاه ({round(avg, 1)}) است.")
                else:
                    goods.append(f"🟢 **عملکرد مناسب در {metric}:** وضعیت شما ({val}) در سطح مطلوب درمانگاه قرار دارد.")

        # نمایش کارت‌های هشدار
        if warnings:
            st.error("### نقاط نیازمند اصلاح و هشدارها")
            for w in warnings:
                st.write(w)
                
        if goods:
            st.success("### نقاط قوت و عملکرد مثبت")
            for g in goods:
                st.write(g)

        st.markdown("---")
        st.subheader("نمودار رادار مقایسه با میانگین درمانگاه")
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(r=doc_data[metrics].values, theta=metrics, fill='toself', name=selected_doc))
        fig_radar.add_trace(go.Scatterpolar(r=avg_data.values, theta=metrics, fill='toself', name='میانگین درمانگاه'))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True)), showlegend=True)
        st.plotly_chart(fig_radar, use_container_width=True)

    with tab3:
        st.header("💾 نحوه ذخیره گزارش به صورت PDF")
        st.info("برای گرفتن فایل PDF کارنامه همراه با هشدارها، در مرورگر کروم روی سه نقطه بالا ضربه بزنید، گزینه **Share (اشتراک‌گذاری)** و سپس **Print (چاپ)** را انتخاب کرده و حالت ذخیره را روی **Save as PDF** قرار دهید.")

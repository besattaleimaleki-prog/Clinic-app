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

    tab1, tab2, tab3 = st.tabs(["گزارش مقایسه‌ای کل", "پروفایل و تحلیل پزشک", "راهنمای خروجی PDF"])

    # ------------------ تب اول: مقایسه کلی ------------------
    with tab1:
        st.header("📈 مقایسه کلی پزشکان")
        selected_metric = st.selectbox("یک شاخص را برای مقایسه انتخاب کنید:", metrics)
        fig_bar = px.bar(
            df, 
            x=doctor_col, 
            y=selected_metric, 
            text_auto=True, 
            color=selected_metric, 
            color_continuous_scale="Viridis",
            title=f"مقایسه کلی پزشکان در شاخص: {selected_metric}"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        st.subheader("جدول رتبه‌بندی کلی")
        st.dataframe(df_ranks.set_index(doctor_col))

    # ------------------ تب دوم: کارنامه پزشک ------------------
    with tab2:
        st.header("👤 کارنامه و تحلیل عملکرد پزشک")
        selected_doc = st.selectbox("نام پزشک را انتخاب کنید:", df[doctor_col].tolist())
        doc_data = df[df[doctor_col] == selected_doc].iloc[0]
        doc_ranks = df_ranks[df_ranks[doctor_col] == selected_doc].iloc[0]
        total_docs = len(df)
        avg_data = df[metrics].mean()
        
        st.subheader(f"کارنامه عملکرد: {selected_doc}")
        
        # کارت‌های شاخص‌ها به همراه رتبه
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
        
        # ۱. تحلیل هشدارهای هوشمند متنی
        st.subheader("⚠️ هشدارهای عملکرد و نقاط اصلاحی")
        warnings, goods = [], []
        for metric in metrics:
            val = doc_data[metric]
            avg = avg_data[metric]
            diff = val - avg
            
            if "ویزیت" not in metric and "آزمایشگاه" not in metric:
                if val > avg * 1.25:
                    warnings.append(f"🔴 **بحرانی در {metric}:** میزان تجویز شما ({val}) حدود **{abs(round(diff, 1))}** واحد بالاتر از میانگین درمانگاه ({round(avg, 1)}) است.")
                elif val > avg:
                    warnings.append(f"🟡 **هشدار در {metric}:** تجویز شما ({val}) کمی از میانگین درمانگاه ({round(avg, 1)}) بالاتر است.")
                else:
                    goods.append(f"🟢 **مطلوب در {metric}:** تجویز شما ({val}) از میانگین درمانگاه ({round(avg, 1)}) پایین‌تر و مناسب است.")
            else:
                if val < avg * 0.75:
                    warnings.append(f"🟡 **توجه در {metric}:** آمار شما ({val}) پایین‌تر از میانگین درمانگاه ({round(avg, 1)}) است.")
                else:
                    goods.append(f"🟢 **مناسب در {metric}:** آمار شما ({val}) در سطح مطلوب درمانگاه قرار دارد.")

        if warnings:
            st.error("### نقاط نیازمند توجه و اصلاح")
            for w in warnings:
                st.write(w)
                
        if goods:
            st.success("### نقاط قوت تجویزی")
            for g in goods:
                st.write(g)

        st.markdown("---")

        # ۲. نمودار میله‌ای افقی مقایسه‌ای (جایگزین نمودار راداری)
        st.subheader("📊 مقایسه تصویری عملکرد پزشک با میانگین درمانگاه")
        
        # آماده‌سازی داده‌ها برای نمودار افقی
        comp_df = pd.DataFrame({
            'شاخص': list(metrics) * 2,
            'مقدار': list(doc_data[metrics].values) + list(avg_data.values),
            'مرجع': [selected_doc] * len(metrics) + ['میانگین درمانگاه'] * len(metrics)
        })

        fig_compare = px.bar(
            comp_df,
            y='شاخص',
            x='مقدار',
            color='مرجع',
            barmode='group',
            orientation='h',
            text_auto='.1f',
            title=f"مقایسه مقادیر عددی {selected_doc} در برابر میانگین کل درمانگاه",
            color_discrete_map={selected_doc: '#1f77b4', 'میانگین درمانگاه': '#ff7f0e'}
        )
        fig_compare.update_layout(yaxis={'categoryorder': 'total ascending'}, height=450)
        st.plotly_chart(fig_compare, use_container_width=True)

        # ۳. نمودار درصد انحراف از میانگین (شفاف‌ترین حالت بصری)
        st.subheader("🎯 درصد انحراف از استاندارد درمانگاه")
        
        pct_diff = []
        for metric in metrics:
            val = doc_data[metric]
            avg = avg_data[metric]
            pct = ((val - avg) / avg) * 100 if avg != 0 else 0
            pct_diff.append(pct)

        diff_df = pd.DataFrame({
            'شاخص': metrics,
            'درصد انحراف': pct_diff
        })
        diff_df['وضعیت انحراف'] = diff_df['درصد انحراف'].apply(lambda x: 'بالاتر از میانگین' if x > 0 else 'پایین‌تر از میانگین')

        fig_diff = px.bar(
            diff_df,
            y='شاخص',
            x='درصد انحراف',
            color='وضعیت انحراف',
            orientation='h',
            text=diff_df['درصد انحراف'].apply(lambda x: f"{x:+.1f}%"),
            title="میزان درصد انحراف (اعداد مثبت به معنی بالاتر بودن از میانگین درمانگاه است)",
            color_discrete_map={'بالاتر از میانگین': '#d62728', 'پایین‌تر از میانگین': '#2ca02c'}
        )
        fig_diff.add_vline(x=0, line_dash="dash", line_color="black")
        fig_diff.update_layout(height=400)
        st.plotly_chart(fig_diff, use_container_width=True)

    # ------------------ تب سوم: خروجی PDF ------------------
    with tab3:
        st.header("💾 نحوه ذخیره گزارش به صورت PDF")
        st.info("جهت ذخیره کارنامه، در مرورگر کروم گوشی روی **سه نقطه بالا > Share > Print** ضربه بزنید و گزینه **Save as PDF** را انتخاب کنید.")

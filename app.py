import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="فحص الموديلات", page_icon="🕵️‍♂️")

st.markdown("""
<div style="text-align: center;">
    <h1>🕵️‍♂️ كاشف الموديلات المتاحة</h1>
    <p>هذا الكود سيكشف لنا الاسم الصحيح الذي ينهي المشكلة</p>
</div>
""", unsafe_allow_html=True)

# جلب المفتاح
api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    st.error("⚠️ لم يتم العثور على المفتاح في Secrets!")
else:
    genai.configure(api_key=api_key)
    
    if st.button("🔍 افحص الموديلات الآن"):
        try:
            st.info("جاري الاتصال بجوجل لجلب القائمة الرسمية...")
            models = genai.list_models()
            
            found_any = False
            st.write("### 📋 انسخ لي أو صور لي هذه القائمة:")
            
            for m in models:
                # نبحث فقط عن الموديلات التي يمكنها الكتابة
                if 'generateContent' in m.supported_generation_methods:
                    found_any = True
                    # عرض الاسم باللون الأخضر
                    st.success(f"✅ متاح: `{m.name}`")
                    with st.expander(f"تفاصيل {m.name}"):
                        st.json(m.to_dict())
            
            if not found_any:
                st.warning("⚠️ اتصلنا بجوجل بنجاح، لكنه يقول أنه لا توجد موديلات متاحة للكتابة في حسابك الحالي!")
                st.markdown("---")
                st.write("**الحل المقترح:** قم بإنشاء API Key جديد في مشروع جديد تماماً.")
                
        except Exception as e:
            st.error(f"❌ حدث خطأ أثناء الفحص: {e}")

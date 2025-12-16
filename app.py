import streamlit as st
import os
import shutil

# استيراد دالة المونتاج من ملفك الأصلي
# تأكد أن اسم ملفك هو audio.py وأن الدالة بداخله اسمها robust_director
from audio import robust_director

# --- إعدادات الصفحة ---
st.set_page_config(
    page_title="المخرج السينمائي الآلي",
    page_icon="🎬",
    layout="centered"
)

# --- التصميم (CSS) ---
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
        font-size: 20px;
        padding: 10px;
    }
    .stSuccess {
        background-color: #D4EDDA;
        color: #155724;
    }
    </style>
    """, unsafe_allow_html=True)

# --- العنوان ---
st.title("🎬 استوديو المونتاج الذكي")
st.markdown("### حول قصتك الصوتية إلى فيلم سينمائي بضغطة زر 🎧")

# عرض محتويات المكتبة الحالية
if os.path.exists("sfx_robust"):
    file_count = len([f for f in os.listdir("sfx_robust") if f.endswith('.mp3')])
    st.info(f"📚 مكتبة المؤثرات الحالية (sfx_robust) تحتوي على: **{file_count}** ملف صوتي جاهز.")

# --- 1. رفع الملف ---
uploaded_file = st.file_uploader("ارفع ملف الصوت (WAV أو MP3)", type=["wav", "mp3"])

if uploaded_file is not None:
    # عرض مشغل صوتي للملف الأصلي
    st.audio(uploaded_file, format='audio/wav')
    
    # حفظ الملف مؤقتاً ليعالجه الكود
    temp_filename = "input_temp.wav"
    with open(temp_filename, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # --- 2. زر التشغيل ---
    if st.button("🚀 ابدأ المونتاج السينمائي"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("🎧 جاري تحليل النص واستخراج السياق...")
            progress_bar.progress(20)
            
            # تشغيل المخرج الذكي
            # ملاحظة: هذا سيأخذ وقتاً حسب طول الملف
            with st.spinner('المخرج يعمل الآن... يرجى الانتظار، الإبداع يحتاج وقتاً! ⏳'):
                output_file = robust_director(temp_filename)
            
            progress_bar.progress(100)
            
            # --- 3. النتيجة ---
            if output_file and os.path.exists(output_file):
                st.success("✨ تم الانتهاء! الفيديو جاهز.")
                
                # عرض الملف النهائي
                st.audio(output_file, format='audio/mp3')
                
                # زر التحميل
                with open(output_file, "rb") as file:
                    st.download_button(
                        label="📥 تحميل الملف النهائي (MP3)",
                        data=file,
                        file_name="My_Cinematic_Story.mp3",
                        mime="audio/mpeg"
                    )
            else:
                st.error("حدث خطأ ما، لم يتم العثور على الملف الناتج.")
                
        except Exception as e:
            st.error(f"❌ حدث خطأ غير متوقع: {e}")
            
# تنظيف (اختياري)
# if os.path.exists("input_temp.wav"):
#    os.remove("input_temp.wav")
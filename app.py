import streamlit as st
import os
import shutil
import json
import random
import re
from groq import Groq
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter
from pydub.silence import detect_nonsilent
from faster_whisper import WhisperModel
import yt_dlp

# ==========================================
# ⚙️ إعدادات الصفحة
# ==========================================
st.set_page_config(page_title="المخرج السينمائي (Llama 3 AI)", page_icon="🦙", layout="centered")

st.markdown("""
<div style="text-align: center;">
    <h1>🦙 المخرج السينمائي الذكي (Llama 3)</h1>
    <p>تحليل ذكي للسياق باللهجة المصرية باستخدام Groq</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 🛠️ الإعدادات الخلفية
# ==========================================
SFX_DIR = "sfx_robust" 
if not os.path.exists(SFX_DIR): os.makedirs(SFX_DIR)

AudioSegment.converter = "ffmpeg" if shutil.which("ffmpeg") else "ffmpeg.exe"

# جلب مفتاح GROQ
api_key = st.secrets.get("GROQ_API_KEY")

# ==========================================
# 📚 قاموس المؤثرات
# ==========================================
SCENE_MAP = {
    "footsteps": ["running footsteps horror", "slow heavy footsteps", "scared walking sounds"],
    "door_open": ["creaky door open horror", "metal door slide", "heavy gate opening"],
    "door_slam": ["loud door slam reverb", "prison door shut", "wooden door impact"],
    "breathing": ["scared heavy breathing", "panic hyperventilation", "tired gasping"],
    "scream": ["man terrified scream horror", "falling scream echo", "muffled scream"],
    "falling": ["body hitting ground thud", "falling clothes rustle", "heavy impact drop"],
    "rock_crumble": ["cave collapse sound", "rocks falling debris", "earthquake rumble"],
    "heartbeat": ["intense horror heartbeat", "fast racing pulse sound"],
    "wind": ["cave wind howling", "eerie dark ambience wind"],
    "silence": ["shocking silence ringing ear", "suspense low drone"],
    "glass": ["glass shattering loud", "window break crash"]
}

# ==========================================
# 🧠 العقل المدبر (Groq / Llama 3) مع نظام المحاولات
# ==========================================
def analyze_text_with_groq(text_data):
    if not api_key:
        st.error("⚠️ يجب إضافة GROQ_API_KEY في الـ Secrets!")
        return []

    client = Groq(api_key=api_key)
    
    # قائمة الموديلات: نجرب الأحدث، وإذا فشل نجرب الذي يليه
    models_to_try = [
        "llama-3.3-70b-versatile",  # الأحدث والأذكى
        "llama-3.1-70b-versatile",
        "mixtral-8x7b-32768"        # بديل قوي جداً
    ]

    prompt = f"""
    You are an expert movie sound director. Analyze this story script (Egyptian Arabic):
    "{text_data}"

    Task: Identify the perfect moments for sound effects based on the **context** and **meaning**.
    
    Available Effects: {list(SCENE_MAP.keys())}
    
    Rules:
    1. Only use the listed effects.
    2. Ignore negations (e.g., "He didn't scream" -> No scream).
    3. Return ONLY a JSON array. No text before or after.
    4. Format: [{{"sfx": "category", "time": seconds}}]
    5. Be precise with timing based on the timestamps in text (e.g., [12.50]).
    """

    for model_name in models_to_try:
        try:
            # st.toast(f"جاري تجربة الموديل: {model_name}") # للتجربة
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            response_text = completion.choices[0].message.content
            
            # محاولة قراءة JSON بمرونة
            parsed = json.loads(response_text)
            if "sfx" in parsed: return parsed["sfx"]
            if isinstance(parsed, list): return parsed
            for key in parsed:
                if isinstance(parsed[key], list): return parsed[key]
            return [] # إذا كان الرد فارغاً لكن صحيحاً

        except Exception as e:
            error_msg = str(e)
            # إذا كان الخطأ "موديل غير موجود"، جرب التالي بصمت
            if "model_decommissioned" in error_msg or "not found" in error_msg or "404" in error_msg:
                continue
            # أخطاء أخرى قد تكون مهمة
            print(f"Error with model {model_name}: {e}")
            continue

    st.error("❌ لم نتمكن من الاتصال بأي موديل من Groq. تأكد من المفتاح أو جرب لاحقاً.")
    return []

# ==========================================
# 📥 التحميل المتنوع
# ==========================================
def get_sfx_file(category):
    search_query = random.choice(SCENE_MAP.get(category, [category + " sound"]))
    filename_base = f"{category}_{random.randint(100,999)}"
    filename_path = os.path.join(SFX_DIR, filename_base)
    
    existing = [f for f in os.listdir(SFX_DIR) if f.startswith(category)]
    if existing and random.random() > 0.5:
        selected = os.path.join(SFX_DIR, random.choice(existing))
        if os.path.getsize(selected) > 5000: return selected

    st.toast(f"🦅 جاري تحميل: {search_query}...")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename_path,
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 10*1024*1024,
        'match_filter': yt_dlp.utils.match_filter_func("duration < 30"),
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"ytsearch1:{search_query} sound effect no copyright"])
        return filename_path + ".mp3"
    except:
        if existing: return os.path.join(SFX_DIR, random.choice(existing))
        return None

# ==========================================
# ✂️ المعالجة
# ==========================================
def smart_crop_audio(sound, silence_thresh=-40, padding=50):
    try:
        nonsilent_ranges = detect_nonsilent(sound, min_silence_len=200, silence_thresh=silence_thresh)
        if len(nonsilent_ranges) > 0:
            start_i, end_i = nonsilent_ranges[0]
            start_i = max(0, start_i - padding)
            end_i = min(len(sound), end_i + padding)
            return sound[start_i:end_i]
        return sound
    except: return sound

def process_audio(voice_file):
    st.info("🧠 1. جاري استماع وتحليل القصة (Whisper Medium)...")
    try:
        model = WhisperModel("medium", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(voice_file, word_timestamps=True, language="ar")
        
        full_text_with_time = []
        clean_text = []
        for segment in segments:
            for word in segment.words:
                text_part = f"[{word.start:.2f}] {word.word}"
                full_text_with_time.append(text_part)
                clean_text.append(word.word)
        
        prompt_text = " ".join(full_text_with_time)
        st.text_area("النص:", " ".join(clean_text), height=80)
    except Exception as e:
        st.error(f"Whisper Error: {e}")
        return None

    st.info("🦙 2. Llama 3 يدرس سياق الرواية...")
    sfx_plan = analyze_text_with_groq(prompt_text)
    
    if sfx_plan:
        st.success(f"✅ قرر الذكاء الاصطناعي إضافة {len(sfx_plan)} مؤثر!")
        st.write(sfx_plan)
    else:
        st.warning("⚠️ لم يقترح الذكاء الاصطناعي أي مؤثرات.")
        return None

    st.info("🎬 3. جاري المونتاج...")
    full_audio = AudioSegment.from_file(voice_file)
    full_audio = normalize(high_pass_filter(full_audio, 80))
    
    progress = st.progress(0)
    for i, item in enumerate(sfx_plan):
        sfx_name = item.get("sfx")
        time_sec = float(item.get("time"))
        sfx_path = get_sfx_file(sfx_name)
        if sfx_path and os.path.exists(sfx_path):
            try:
                sound = AudioSegment.from_file(sfx_path)
                sound = smart_crop_audio(sound)
                sound = sound - 5 
                sound = sound.fade_in(50).fade_out(300)
                full_audio = full_audio.overlay(sound, position=int(time_sec * 1000))
            except: pass
        progress.progress((i + 1) / len(sfx_plan))

    output = "Llama_Cinema.mp3"
    full_audio.export(output, format="mp3")
    return output

# ==========================================
# 🖥️ الواجهة
# ==========================================
if st.sidebar.button("🗑️ حذف الملفات القديمة"):
    if os.path.exists(SFX_DIR):
        shutil.rmtree(SFX_DIR)
        os.makedirs(SFX_DIR)
    st.sidebar.success("تم التنظيف!")

uploaded_file = st.file_uploader("ارفع ملف الصوت", type=["wav", "mp3"])

if uploaded_file:
    st.audio(uploaded_file)
    if st.button("🚀 ابدأ المونتاج بالذكاء الاصطناعي"):
        with open("input.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        final = process_audio("input.mp3")
        
        if final:
            st.balloons()
            st.audio(final)
            with open(final, "rb") as f:
                st.download_button("تحميل", f, file_name="AI_Montage.mp3")

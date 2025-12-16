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
st.set_page_config(page_title="المخرج السينمائي (Failsafe)", page_icon="🛡️", layout="centered")

st.markdown("""
<div style="text-align: center;">
    <h1>🛡️ المخرج السينمائي (النسخة الآمنة)</h1>
    <p>نظام ذكي لتفادي أخطاء التحميل + إدارة الذاكرة</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 🛠️ الإعدادات الخلفية
# ==========================================
SFX_DIR = "sfx_robust" 
if not os.path.exists(SFX_DIR): os.makedirs(SFX_DIR)

AudioSegment.converter = "ffmpeg" if shutil.which("ffmpeg") else "ffmpeg.exe"

api_key = st.secrets.get("GROQ_API_KEY")

# ==========================================
# 📚 قاموس الأصوات
# ==========================================
SCENE_MAP = {
    "footsteps": ["running footsteps horror", "scared walking steps"],
    "door_open": ["creaky door open horror", "metal door slide"],
    "door_slam": ["loud door slam reverb", "impact thud sound"],
    "breathing": ["scared heavy breathing", "panic hyperventilation"],
    "scream": ["sharp gasp of fear", "shocked breath intake", "muffled scared noise"],
    "falling": ["body thud fall sound", "clothes rustling drop"],
    "rock_crumble": ["cave collapse debris", "falling rocks sound"],
    "heartbeat": ["intense slow heartbeat", "racing pulse sound"],
    "wind": ["eerie cave wind howling", "low frequency dark ambience"],
    "silence": ["high pitched ear ringing", "low suspense drone"],
    "glass": ["glass shattering cinematic", "window smash sound"]
}

# ==========================================
# 🧠 Groq AI
# ==========================================
def analyze_text_with_groq(text_data):
    if not api_key:
        st.error("⚠️ GROQ_API_KEY مفقود!")
        return []

    client = Groq(api_key=api_key)
    
    prompt = f"""
    Act as a strict sound editor. Analyze this script:
    "{text_data}"

    Task: Select ONLY the **TOP 5 most critical** sound effects.
    
    Rules:
    1. Minimum 15 seconds between effects.
    2. Focus on big events only.
    3. Duration is mandatory.
    
    Available Effects: {list(SCENE_MAP.keys())}
    
    Return JSON array ONLY: 
    [{{"sfx": "category", "time": start_seconds, "duration": duration_seconds}}]
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        response_text = completion.choices[0].message.content
        parsed = json.loads(response_text)
        
        sfx_list = []
        if "sfx" in parsed: sfx_list = parsed["sfx"]
        elif isinstance(parsed, list): sfx_list = parsed
        else:
            for key in parsed:
                if isinstance(parsed[key], list): sfx_list = parsed[key]
        
        # فلترة لضمان تباعد 10 ثواني على الأقل
        filtered_list = []
        last_time = -20
        for item in sfx_list:
            if item['time'] - last_time > 10.0:
                filtered_list.append(item)
                last_time = item['time']
        
        return filtered_list

    except Exception as e:
        st.error(f"Groq Error: {e}")
        return []

# ==========================================
# 📥 التحميل الآمن (The Fix)
# ==========================================
def get_sfx_file(category):
    # 1. الأولوية القصوى: فحص الذاكرة المحلية (أسرع وأضمن)
    # نبحث عن أي ملف في المجلد يحتوي اسمه على نوع المؤثر
    existing_files = [f for f in os.listdir(SFX_DIR) if category in f]
    if existing_files:
        # نختار واحداً عشوائياً ونستخدمه فوراً دون تحميل
        selected_file = os.path.join(SFX_DIR, random.choice(existing_files))
        if os.path.getsize(selected_file) > 1000: # تأكد أنه ليس فارغاً
            st.toast(f"✅ تم استخدام ملف محفوظ: {category}")
            return selected_file

    # 2. الخطة البديلة: التحميل
    search_query = random.choice(SCENE_MAP.get(category, [category]))
    filename_base = f"{category}_{random.randint(100,999)}"
    filename_path = os.path.join(SFX_DIR, filename_base)

    st.toast(f"⬇️ محاولة تحميل جديد: {category}...")
    
    # المحاولة الأولى: إعدادات الأندرويد
    ydl_opts_android = {
        'format': 'bestaudio/best',
        'outtmpl': filename_path,
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'extractor_args': {'youtube': {'player_client': ['android']}},
        'max_filesize': 10*1024*1024,
        'match_filter': yt_dlp.utils.match_filter_func("duration < 45"),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_android) as ydl:
            ydl.download([f"ytsearch1:{search_query} sound effect no copyright"])
        if os.path.exists(filename_path + ".mp3"): return filename_path + ".mp3"
    except:
        pass # فشلت الأولى، ننتقل للثانية بصمت

    # المحاولة الثانية: إعدادات الويب (Fallback)
    ydl_opts_web = {
        'format': 'bestaudio/best',
        'outtmpl': filename_path + "_web",
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'quiet': True,
        'nocheckcertificate': True,
        'max_filesize': 10*1024*1024,
        'match_filter': yt_dlp.utils.match_filter_func("duration < 30"),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_web) as ydl:
            ydl.download([f"ytsearch1:{search_query} free sound effect"])
        if os.path.exists(filename_path + "_web.mp3"): return filename_path + "_web.mp3"
    except:
        print(f"فشلت جميع محاولات التحميل لـ {category}")
        return None

# ==========================================
# ✂️ المعالجة
# ==========================================
def super_smart_crop(sound, desired_duration_sec):
    try:
        nonsilent = detect_nonsilent(sound, min_silence_len=50, silence_thresh=-30)
        if nonsilent:
            start_trim = nonsilent[0][0]
            sound = sound[start_trim:]
        
        desired_ms = int(desired_duration_sec * 1000)
        if len(sound) > desired_ms:
            sound = sound[:desired_ms]
            sound = sound.fade_out(150)
        return sound
    except:
        return sound

def process_audio(voice_file):
    st.info("🧠 1. جاري استماع وتحليل القصة...")
    try:
        model = WhisperModel("medium", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(voice_file, word_timestamps=True, language="ar")
        
        full_text = []
        clean_text = []
        for segment in segments:
            for word in segment.words:
                full_text.append(f"[{word.start:.2f}] {word.word}")
                clean_text.append(word.word)
        
        st.text_area("النص:", " ".join(clean_text), height=80)
        prompt_text = " ".join(full_text)
        
    except Exception as e:
        st.error(f"Whisper Error: {e}")
        return None

    st.info("🤖 2. الذكاء الاصطناعي يخطط للمونتاج...")
    sfx_plan = analyze_text_with_groq(prompt_text)
    
    if sfx_plan:
        st.success(f"✅ تم تحديد {len(sfx_plan)} مؤثرات.")
        st.write(sfx_plan)
    else:
        st.warning("⚠️ لم يتم تحديد مؤثرات.")
        return None

    st.info("🎬 3. جاري التنفيذ...")
    full_audio = AudioSegment.from_file(voice_file)
    full_audio = normalize(high_pass_filter(full_audio, 80))
    
    progress = st.progress(0)
    for i, item in enumerate(sfx_plan):
        sfx_name = item.get("sfx")
        time_sec = float(item.get("time"))
        duration = float(item.get("duration", 2.0))
        
        sfx_path = get_sfx_file(sfx_name)
        
        if sfx_path and os.path.exists(sfx_path):
            try:
                sound = AudioSegment.from_file(sfx_path)
                sound = super_smart_crop(sound, duration)
                sound = sound - 6
                full_audio = full_audio.overlay(sound, position=int(time_sec * 1000))
            except Exception as e:
                print(e)
        progress.progress((i + 1) / len(sfx_plan))

    output = "Final_Failsafe_Montage.mp3"
    full_audio.export(output, format="mp3")
    return output

# ==========================================
# 🖥️ الواجهة
# ==========================================
if st.sidebar.button("🗑️ تنظيف الذاكرة (اضغط فقط عند الضرورة)"):
    if os.path.exists(SFX_DIR):
        shutil.rmtree(SFX_DIR)
        os.makedirs(SFX_DIR)
    st.sidebar.success("تم التنظيف!")

uploaded_file = st.file_uploader("ارفع ملف الصوت", type=["wav", "mp3"])

if uploaded_file:
    st.audio(uploaded_file)
    if st.button("🚀 ابدأ"):
        with open("input.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        final = process_audio("input.mp3")
        
        if final:
            st.balloons()
            st.audio(final)
            with open(final, "rb") as f:
                st.download_button("تحميل", f, file_name="Cinema.mp3")

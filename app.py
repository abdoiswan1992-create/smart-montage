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
st.set_page_config(page_title="المخرج السينمائي (AI Timer)", page_icon="⏱️", layout="centered")

st.markdown("""
<div style="text-align: center;">
    <h1>⏱️ المخرج السينمائي (المقص الزمني)</h1>
    <p>الذكاء الاصطناعي يحدد مدة كل مؤثر بدقة حسب المشهد</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 🛠️ الإعدادات الخلفية
# ==========================================
SFX_DIR = "sfx_robust" 
if not os.path.exists(SFX_DIR): os.makedirs(SFX_DIR)

AudioSegment.converter = "ffmpeg" if shutil.which("ffmpeg") else "ffmpeg.exe"

api_key = st.secrets.get("GROQ_API_KEY")

SCENE_MAP = {
    "footsteps": ["running footsteps on dirt horror", "scared walking steps"],
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
# 🧠 Groq AI (يحدد التوقيت والمدة)
# ==========================================
def analyze_text_with_groq(text_data):
    if not api_key:
        st.error("⚠️ GROQ_API_KEY مفقود!")
        return []

    client = Groq(api_key=api_key)
    
    # نطلب من الذكاء الاصطناعي تحديد المدة (Duration)
    prompt = f"""
    Act as a sound editor. Analyze this Egyptian Arabic script:
    "{text_data}"

    Task: Identify sound effects AND their ideal duration based on context.
    
    Example: 
    - "He knocked quickly" -> Duration: 0.5s
    - "The door opened slowly" -> Duration: 3.0s
    
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
        
        # استخراج البيانات بمرونة
        if "sfx" in parsed: return parsed["sfx"]
        if isinstance(parsed, list): return parsed
        for key in parsed:
            if isinstance(parsed[key], list): return parsed[key]
        return []
    except Exception as e:
        st.error(f"Groq Error: {e}")
        return []

# ==========================================
# 📥 التحميل
# ==========================================
def get_sfx_file(category):
    search_query = random.choice(SCENE_MAP.get(category, [category]))
    filename_base = f"{category}_{random.randint(100,999)}"
    filename_path = os.path.join(SFX_DIR, filename_base)
    
    existing = [f for f in os.listdir(SFX_DIR) if f.startswith(category)]
    if existing and random.random() > 0.4: 
        selected = os.path.join(SFX_DIR, random.choice(existing))
        if os.path.getsize(selected) > 5000: return selected

    st.toast(f"🦅 تحميل: {search_query}...")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename_path,
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 10*1024*1024,
        'match_filter': yt_dlp.utils.match_filter_func("duration < 60"),
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"ytsearch1:{search_query} sound effect no copyright"])
        return filename_path + ".mp3"
    except:
        if existing: return os.path.join(SFX_DIR, random.choice(existing))
        return None

# ==========================================
# ✂️ القص الذكي جداً (Super Smart Crop)
# ==========================================
def super_smart_crop(sound, desired_duration_sec):
    try:
        # 1. أولاً: نحذف الصمت من البداية (Trim Silence)
        # نستخدم عتبة حساسة (-30dB) للتأكد من بدء الصوت فوراً
        nonsilent = detect_nonsilent(sound, min_silence_len=50, silence_thresh=-30)
        
        if nonsilent:
            start_trim = nonsilent[0][0]
            sound = sound[start_trim:]
        
        # 2. ثانياً: نطبق المدة التي طلبها الذكاء الاصطناعي
        desired_ms = int(desired_duration_sec * 1000)
        
        if len(sound) > desired_ms:
            # قص الزائد
            sound = sound[:desired_ms]
            # عمل Fade Out سريع في النهاية لكي لا ينقطع الصوت فجأة
            sound = sound.fade_out(150)
        
        return sound
    except:
        return sound

# ==========================================
# 🎬 المعالجة
# ==========================================
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

    st.info("⏱️ 2. الذكاء الاصطناعي يحدد توقيت ومدة كل مؤثر...")
    sfx_plan = analyze_text_with_groq(prompt_text)
    
    if sfx_plan:
        st.success(f"✅ تم التخطيط لـ {len(sfx_plan)} مؤثر!")
        st.write(sfx_plan) # سيعرض لك المدة المقترحة لكل صوت
    else:
        st.warning("⚠️ لم يتم تحديد مؤثرات.")
        return None

    st.info("🎬 3. جاري القص والدمج الدقيق...")
    full_audio = AudioSegment.from_file(voice_file)
    full_audio = normalize(high_pass_filter(full_audio, 80))
    
    progress = st.progress(0)
    for i, item in enumerate(sfx_plan):
        sfx_name = item.get("sfx")
        time_sec = float(item.get("time"))
        # المدة الافتراضية 2 ثانية إذا لم يحددها الذكاء الاصطناعي
        duration = float(item.get("duration", 2.0)) 
        
        sfx_path = get_sfx_file(sfx_name)
        
        if sfx_path and os.path.exists(sfx_path):
            try:
                sound = AudioSegment.from_file(sfx_path)
                
                # 👇 هنا نطبق القص الذكي بناءً على أوامر الذكاء الاصطناعي
                sound = super_smart_crop(sound, duration)
                
                # خفض الصوت
                sound = sound - 6
                
                full_audio = full_audio.overlay(sound, position=int(time_sec * 1000))
            except Exception as e:
                print(e)
        progress.progress((i + 1) / len(sfx_plan))

    output = "Final_Timed_Montage.mp3"
    full_audio.export(output, format="mp3")
    return output

# ==========================================
# 🖥️ الواجهة
# ==========================================
if st.sidebar.button("🗑️ حذف الأصوات القديمة"):
    if os.path.exists(SFX_DIR):
        shutil.rmtree(SFX_DIR)
        os.makedirs(SFX_DIR)
    st.sidebar.success("تم!")

uploaded_file = st.file_uploader("ارفع ملف الصوت", type=["wav", "mp3"])

if uploaded_file:
    st.audio(uploaded_file)
    if st.button("🚀 ابدأ المونتاج الدقيق"):
        with open("input.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        final = process_audio("input.mp3")
        
        if final:
            st.balloons()
            st.audio(final)
            with open(final, "rb") as f:
                st.download_button("تحميل", f, file_name="Timed_Montage.mp3")

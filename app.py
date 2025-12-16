import streamlit as st
import os
import shutil
import json
import random
import time
import re
import google.generativeai as genai
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter
from pydub.silence import detect_nonsilent
from faster_whisper import WhisperModel
import yt_dlp

# ==========================================
# ⚙️ إعدادات الصفحة
# ==========================================
st.set_page_config(page_title="المخرج السينمائي المحترف", page_icon="🎬", layout="centered")

st.markdown("""
<div style="text-align: center;">
    <h1>🎬 المخرج السينمائي المحترف</h1>
    <p>نسخة: Gemini 2.5 Flash (Auto-Wait Enabled) ⏳✅</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 🛠️ الإعدادات
# ==========================================
SFX_DIR = "sfx_robust" 
if not os.path.exists(SFX_DIR): os.makedirs(SFX_DIR)

AudioSegment.converter = "ffmpeg" if shutil.which("ffmpeg") else "ffmpeg.exe"

api_key = st.secrets.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# القاموس
SCENE_MAP = {
    "footsteps": {"search": "footsteps sound effect isolated", "vol": -5},
    "door_open": {"search": "door open squeak sound effect", "vol": -5},
    "door_slam": {"search": "door slam sound effect", "vol": -3},
    "rain": {"search": "rain heavy sound effect", "vol": -10},
    "thunder": {"search": "thunder clap sound effect", "vol": -2},
    "car_engine": {"search": "car engine start sound effect", "vol": -5},
    "scream": {"search": "scream sound effect horror", "vol": -5},
    "laugh": {"search": "evil laugh sound effect", "vol": -5},
    "gunshot": {"search": "gunshot sound effect loud", "vol": -2},
    "punch": {"search": "punch impact sound effect", "vol": -2},
    "glass_break": {"search": "glass shatter sound effect", "vol": -4},
    "paper": {"search": "paper rustling sound effect", "vol": -10},
    "breath": {"search": "breath gasp sound effect isolated", "vol": -10},
    "heartbeat": {"search": "heartbeat sound effect horror", "vol": -4},
    "slide": {"search": "body drag dirt sound effect", "vol": -6},
    "fire": {"search": "fire crackling sound effect", "vol": -8},
    "wind": {"search": "wind howling sound effect", "vol": -8},
    "sword": {"search": "sword draw sound effect", "vol": -5},
    "reload": {"search": "gun reload sound effect", "vol": -5}
}

GLOBAL_NEGATIVE_TAGS = ["cartoon", "funny", "meme", "remix", "song", "music", "intro"]

# ==========================================
# 🧠 دالة الاتصال الذكية (تتعامل مع 2.5 بصبر)
# ==========================================
def generate_with_smart_wait(prompt):
    # نستخدم الموديل الوحيد المتاح لك
    model_name = "gemini-2.5-flash"
    st.info(f"🤖 جاري الاتصال بالموديل: {model_name}")

    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response
        except Exception as e:
            error_msg = str(e)
            # التعامل مع خطأ تجاوز الحصة (429)
            if "429" in error_msg:
                if attempt < max_retries:
                    # استخراج وقت الانتظار من رسالة جوجل
                    wait_time = 60 # افتراضي
                    match = re.search(r"retry in (\d+(\.\d+)?)", error_msg)
                    if match:
                        wait_time = float(match.group(1)) + 2 # إضافة ثانيتين للأمان
                    
                    st.warning(f"⚠️ الموديل مشغول ({model_name}). يطلب استراحة {wait_time:.1f} ثانية... ☕")
                    
                    # عداد تنازلي مرئي
                    my_bar = st.progress(0)
                    for i in range(100):
                        time.sleep(wait_time / 100)
                        my_bar.progress(i + 1)
                    
                    st.info("🔄 انتهت الاستراحة! جاري إعادة المحاولة...")
                    continue
                else:
                    st.error("❌ السيرفر مشغول جداً. يرجى المحاولة لاحقاً أو تغيير مفتاح API.")
                    return None
            else:
                st.error(f"❌ خطأ غير متوقع: {e}")
                return None

# ==========================================
# ✂️ دوال المعالجة
# ==========================================
def smart_crop_audio(sound, silence_thresh=-40, padding=100):
    try:
        nonsilent_ranges = detect_nonsilent(sound, min_silence_len=300, silence_thresh=silence_thresh)
        if len(nonsilent_ranges) > 0:
            start_i, end_i = nonsilent_ranges[0]
            start_i = max(0, start_i - padding)
            end_i = min(len(sound), end_i + padding)
            return sound[start_i:end_i]
        return sound
    except:
        return sound

def camouflage_audio(sound):
    try:
        speed_change = random.uniform(0.96, 1.04)
        new_sample_rate = int(sound.frame_rate * speed_change)
        camouflaged = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
        return camouflaged.set_frame_rate(44100)
    except:
        return sound

def get_best_sfx(category):
    files = [f for f in os.listdir(SFX_DIR) if f.startswith(category)]
    if files:
        return os.path.join(SFX_DIR, random.choice(files))

    st.toast(f"🦅 جاري صيد مؤثر: {category}...")
    search_base = SCENE_MAP.get(category, {"search": category + " sound effect"})["search"]
    target_url = f"ytsearch1:{search_base} short sfx"
    
    filename = f"{category}_{random.randint(1000,9999)}"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(SFX_DIR, filename),
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'quiet': True,
        'no_warnings': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target_url])
        return os.path.join(SFX_DIR, filename + ".mp3")
    except:
        return None

# ==========================================
# 🎬 المعالجة الرئيسية
# ==========================================
def process_audio(voice_file):
    # 1. Whisper
    st.info("🧠 1. جاري استماع وتحليل القصة (Whisper)...")
    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(voice_file, word_timestamps=True, language="ar")
        full_transcript = []
        for segment in segments:
            for word in segment.words:
                full_transcript.append(f"[{word.start:.2f}] {word.word}")
        text_data = " ".join(full_transcript)
        st.text_area("النص:", text_data, height=80)
    except Exception as e:
        st.error(f"Error Whisper: {e}")
        return None

    # 2. Gemini
    st.info("🤖 2. جاري استشارة المخرج الفني (Gemini)...")
    
    prompt = f"""
    بصفتك مخرج صوتي، استخرج المؤثرات من النص:
    {text_data}
    القائمة المتاحة: {list(SCENE_MAP.keys())}
    القواعد: تجاهل النفي. افهم المجاز.
    JSON Output: [{{"sfx": "name", "time": seconds}}]
    """
    
    response = generate_with_smart_wait(prompt)
    
    if not response:
        return None

    try:
        sfx_plan = json.loads(response.text.replace("```json", "").replace("```", "").strip())
        st.success(f"✅ تم اعتماد {len(sfx_plan)} مؤثر!")
        st.write(sfx_plan)
    except Exception as e:
        st.error(f"فشل في قراءة رد Gemini: {e}")
        return None

    # 3. المونتاج
    st.info("🎬 3. جاري المونتاج (قص + تنكر + دمج)...")
    full_audio = AudioSegment.from_file(voice_file)
    full_audio = normalize(high_pass_filter(full_audio, 100))
    
    progress = st.progress(0)
    for i, item in enumerate(sfx_plan):
        sfx_name = item.get("sfx")
        time_sec = float(item.get("time"))
        
        sfx_path = get_best_sfx(sfx_name)
        
        if sfx_path and os.path.exists(sfx_path):
            try:
                sound = AudioSegment.from_file(sfx_path)
                sound = smart_crop_audio(sound)
                sound = camouflage_audio(sound)
                
                vol = SCENE_MAP.get(sfx_name, {"vol": -5})["vol"]
                sound = sound + vol
                sound = sound.fade_out(200)
                
                full_audio = full_audio.overlay(sound, position=int(time_sec * 1000))
            except Exception as e:
                print(f"Merge error: {e}")
        
        progress.progress((i + 1) / len(sfx_plan))

    output = "Smart_Cinema_Final.mp3"
    full_audio.export(output, format="mp3")
    return output

# ==========================================
# 🖥️ الواجهة
# ==========================================
uploaded_file = st.file_uploader("ارفع ملف الصوت", type=["wav", "mp3"])

if uploaded_file:
    st.audio(uploaded_file)
    if st.button("🚀 ابدأ المونتاج"):
        with open("input.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        final = process_audio("input.mp3")
        
        if final:
            st.balloons()
            st.success("تم الانتهاء! 🎧")
            st.audio(final)
            with open(final, "rb") as f:
                st.download_button("تحميل", f, file_name="Cinema.mp3")

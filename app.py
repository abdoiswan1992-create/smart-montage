import streamlit as st
import os
import shutil
import json
import random
import time
from groq import Groq
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter
from pydub.silence import detect_nonsilent
from faster_whisper import WhisperModel
import yt_dlp

# ==========================================
# ⚙️ إعدادات الصفحة
# ==========================================
st.set_page_config(page_title="المخرج الذكي (Context Aware)", page_icon="🧠", layout="centered")

st.markdown("""
<div style="text-align: center;">
    <h1>🧠 المخرج السينمائي (السياق الذكي)</h1>
    <p>يفهم الفرق بين "الوصف" و"الفعل" + فحص جودة الملفات</p>
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
# 📚 القاموس (تم إزالة الصرخات البشرية لتقليل الخطأ)
# ==========================================
SCENE_MAP = {
    "footsteps": ["footsteps on dirt cinematic", "slow horror walking footsteps"],
    "door_open": ["creaky door opening sound effect", "metal door slide heavy"],
    "door_slam": ["loud door slam reverb", "dungeon door close impact"],
    "breathing": ["scared heavy breathing isolated", "hyperventilation sound effect"],
    # لاحظ: حذفنا "scream" كفئة رئيسية لتجنب الخطأ، واستبدلناها بأصوات بيئية
    "falling": ["body thud hitting ground", "heavy object fall impact"],
    "rock_crumble": ["cave debris falling sound", "earthquake rocks crumbling"],
    "heartbeat": ["horror heartbeat sound effect", "slow suspense pulse"],
    "wind": ["howling cave wind ambiance", "eerie wind whistle"],
    "silence": ["ear ringing tinnitus sound", "low suspense drone horror"],
    "glass": ["glass shattering loud sound", "window break crash"]
}

# ==========================================
# 🧠 Groq AI (الدستور الجديد)
# ==========================================
def analyze_text_with_groq(text_data):
    if not api_key:
        st.error("⚠️ GROQ_API_KEY مفقود!")
        return []

    client = Groq(api_key=api_key)
    
    # 👇 الدستور الجديد للمخرج:
    prompt = f"""
    You are a strictly logical sound editor for an audiobook.
    Analyze this Egyptian Arabic script: "{text_data}"

    CRITICAL RULES (Do NOT ignore):
    1. **Context is King:** If the narrator says "He screamed" (صرخ) or "He said loudly", **DO NOT** add a scream SFX. The narrator's voice IS the sound.
    2. **Environment Only:** Only add sounds the narrator CANNOT make (e.g., Door slam, Wind, Footsteps, Rocks falling, Heartbeat).
    3. **No Redundancy:** Do not double-up on sounds.
    4. **Spacing:** Keep at least 15 seconds between effects.
    5. **Selection:** Choose only the top 3-5 most essential environmental sounds.

    Available Effects Map: {list(SCENE_MAP.keys())}
    
    Return JSON array ONLY: 
    [{{"sfx": "category", "time": start_seconds, "duration": duration_seconds}}]
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, # صفر للإلتزام التام بالقواعد
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
        
        # فلتر إضافي للتباعد
        filtered_list = []
        last_time = -20
        for item in sfx_list:
            if item['time'] - last_time > 15.0:
                filtered_list.append(item)
                last_time = item['time']
        
        return filtered_list

    except Exception as e:
        st.error(f"Groq Error: {e}")
        return []

# ==========================================
# 📥 التحميل مع "حارس البوابة" (File Validator)
# ==========================================
def get_sfx_file(category):
    # 1. البحث المحلي
    existing_files = [f for f in os.listdir(SFX_DIR) if category in f]
    for file in existing_files:
        path = os.path.join(SFX_DIR, file)
        # 🛡️ الفحص: هل الملف حجمه منطقي؟ (أكبر من 20KB)
        if os.path.getsize(path) > 20000:
            st.toast(f"✅ من الذاكرة (سليم): {category}")
            return path
        else:
            # إذا كان صغيراً (فارغاً)، احذفه
            try: os.remove(path) 
            except: pass

    # 2. التحميل (SoundCloud + YouTube)
    search_query = random.choice(SCENE_MAP.get(category, [category]))
    filename_base = f"{category}_{random.randint(100,999)}"
    filename_path = os.path.join(SFX_DIR, filename_base)

    st.toast(f"⬇️ جاري التحميل: {search_query}...")
    
    # خيارات ساوند كلاود (غالباً أنجح)
    ydl_opts_sc = {
        'format': 'bestaudio/best',
        'outtmpl': filename_path,
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 5*1024*1024,
        'match_filter': yt_dlp.utils.match_filter_func("duration < 90"),
    }
    
    # محاولة 1: SoundCloud
    try:
        with yt_dlp.YoutubeDL(ydl_opts_sc) as ydl:
            ydl.download([f"scsearch1:{search_query} sound effect"])
        final_path = filename_path + ".mp3"
        # 🛡️ نقطة التفتيش: هل نجح التحميل والملف سليم؟
        if os.path.exists(final_path) and os.path.getsize(final_path) > 20000:
            return final_path
    except: pass

    # محاولة 2: YouTube (Android Mode)
    ydl_opts_yt = ydl_opts_sc.copy()
    ydl_opts_yt['extractor_args'] = {'youtube': {'player_client': ['android']}}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts_yt) as ydl:
            ydl.download([f"ytsearch1:{search_query} sound effect no copyright"])
        final_path = filename_path + ".mp3"
        if os.path.exists(final_path) and os.path.getsize(final_path) > 20000:
            return final_path
    except: pass

    st.warning(f"❌ فشل العثور على ملف سليم لـ: {category}")
    return None

# ==========================================
# ✂️ المعالجة
# ==========================================
def super_smart_crop(sound, desired_duration_sec):
    try:
        # إزالة الصمت من البداية
        nonsilent = detect_nonsilent(sound, min_silence_len=50, silence_thresh=-30)
        if nonsilent:
            start_trim = nonsilent[0][0]
            sound = sound[start_trim:]
        
        # التأكد من أن الصوت ليس قصيراً جداً
        if len(sound) < 500: return None 

        desired_ms = int(desired_duration_sec * 1000)
        if len(sound) > desired_ms:
            sound = sound[:desired_ms]
            sound = sound.fade_out(200)
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

    st.info("🧠 2. الذكاء الاصطناعي (السياقي) يختار المؤثرات...")
    sfx_plan = analyze_text_with_groq(prompt_text)
    
    if sfx_plan:
        st.success(f"✅ تم اختيار {len(sfx_plan)} مؤثر بيئي فقط (بدون تكرار السرد).")
        st.write(sfx_plan)
    else:
        st.warning("⚠️ لم يجد الذكاء الاصطناعي حاجة لمؤثرات بيئية في هذا المقطع.")
        return None

    st.info("🎬 3. جاري الدمج (فقط الملفات السليمة)...")
    full_audio = AudioSegment.from_file(voice_file)
    full_audio = normalize(high_pass_filter(full_audio, 80))
    
    progress = st.progress(0)
    for i, item in enumerate(sfx_plan):
        sfx_name = item.get("sfx")
        time_sec = float(item.get("time"))
        duration = float(item.get("duration", 2.0))
        
        sfx_path = get_sfx_file(sfx_name)
        
        if sfx_path: # فقط إذا عاد المسار (يعني الملف سليم)
            try:
                sound = AudioSegment.from_file(sfx_path)
                sound = super_smart_crop(sound, duration)
                
                if sound: # تأكد أن القص لم يفسد الملف
                    sound = sound - 6 # خفض الصوت
                    full_audio = full_audio.overlay(sound, position=int(time_sec * 1000))
            except Exception as e:
                print(f"Merge Error: {e}")
        
        progress.progress((i + 1) / len(sfx_plan))

    output = "Final_Context_Montage.mp3"
    full_audio.export(output, format="mp3")
    return output

# ==========================================
# 🖥️ الواجهة
# ==========================================
# زر التنظيف مهم جداً الآن لحذف الملفات الفارغة القديمة
if st.sidebar.button("🗑️ تنظيف الملفات التالفة"):
    if os.path.exists(SFX_DIR):
        shutil.rmtree(SFX_DIR)
        os.makedirs(SFX_DIR)
    st.sidebar.success("تم تنظيف الذاكرة!")

uploaded_file = st.file_uploader("ارفع ملف الصوت", type=["wav", "mp3"])

if uploaded_file:
    st.audio(uploaded_file)
    if st.button("🚀 ابدأ المونتاج الذكي"):
        with open("input.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        final = process_audio("input.mp3")
        
        if final:
            st.balloons()
            st.audio(final)
            with open(final, "rb") as f:
                st.download_button("تحميل", f, file_name="Cinema.mp3")

import streamlit as st
import os
import shutil
import json
import random
import re
import time
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter
from pydub.silence import detect_nonsilent
from faster_whisper import WhisperModel
import yt_dlp

# ==========================================
# ⚙️ إعدادات الصفحة
# ==========================================
st.set_page_config(page_title="المخرج السينمائي (نسخة اللهجة المصرية)", page_icon="🇪🇬", layout="centered")

st.markdown("""
<div style="text-align: center;">
    <h1>🎬 المخرج السينمائي (اللهجة المصرية)</h1>
    <p>دعم أقوى للهجة المصرية + مؤثرات سينمائية واقعية</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 🛠️ الإعدادات الخلفية
# ==========================================
SFX_DIR = "sfx_robust" 
if not os.path.exists(SFX_DIR): os.makedirs(SFX_DIR)

AudioSegment.converter = "ffmpeg" if shutil.which("ffmpeg") else "ffmpeg.exe"

# ==========================================
# 📚 القاموس المصري الذكي
# ==========================================
# تم تحديث الكلمات بناءً على النص الذي أرسلته (شامل الأخطاء الإملائية المحتملة)
SCENE_MAP = {
    "footsteps": {
        "triggers": ["بيجري", "يجري", "مشى", "يمشي", "خطوات", "بسرعة", "هروب", "يلتفت", "تتدحرج", "زحف"], 
        "search": "running footsteps on dirt cinematic sound effect", "vol": -5
    },
    "door_open": {
        "triggers": ["فتح", "يفتح", "باب", "دخل", "عدى", "صرير"], 
        "search": "creaky door open sound effect horror", "vol": -5
    },
    "door_slam": {
        "triggers": ["أفل", "قفل", "خبط", "رزع", "ارتطم", "تطام", "تحشم", "تهشم"], 
        "search": "loud door slam impact sound effect", "vol": -2
    },
    "breathing": {
        "triggers": ["بيس", "يلهث", "نفس", "هواء", "اختناق", "اختناء", "صدره"], 
        "search": "scared heavy breathing sound effect", "vol": -8
    },
    "scream": {
        "triggers": ["صرخ", "صرح", "صيحة", "صوت عالي", "فزع", "يا لهوي", "الحقوني"], 
        "search": "man scream horror falling sound effect", "vol": -4
    },
    "falling": {
        "triggers": ["وقع", "وقر", "سقط", "رمي", "نزل", "هبوط"], 
        "search": "body fall thud sound effect", "vol": -3
    },
    "rock_crumble": {
        "triggers": ["انهيار", "صخور", "تراب", "ردم", "زلزال", "تنهار"], 
        "search": "cave collapse rocks falling sound effect", "vol": -5
    },
    "heartbeat": {
        "triggers": ["قلبه", "خوف", "رعب", "نبض", "دق"], 
        "search": "heartbeat horror suspense sound effect", "vol": -5
    },
     "wind": {
        "triggers": ["هواء", "تهوية", "نفق", "رياح"], 
        "search": "cave wind howling ambience sound effect", "vol": -10
    }
}

# ==========================================
# 🧠 المخرج "الخوارزمي" (النسخة المصرية)
# ==========================================
def analyze_text_with_regex(transcript_segments):
    plan = []
    last_trigger_time = -5 # تقليل مهلة التكرار قليلاً
    
    for segment in transcript_segments:
        text = segment['text']
        start = segment['start']
        
        # تجنب تكرار نفس المؤثر في وقت قصير جداً
        if start - last_trigger_time < 2.0: 
            continue

        found_sfx = None
        
        for sfx_key, data in SCENE_MAP.items():
            for trigger in data["triggers"]:
                # استخدام Regex مرن للبحث عن الكلمة حتى لو كانت ملتصقة بغيرها
                # مثلاً "فصرخ" ستعمل مع "صرخ"
                if trigger in text:
                    found_sfx = sfx_key
                    break
            if found_sfx: break
        
        if found_sfx:
            plan.append({"sfx": found_sfx, "time": start})
            last_trigger_time = start
            
    return plan

# ==========================================
# 📥 التحميل الذكي (مع فحص الملفات الفارغة)
# ==========================================
def get_best_sfx(category):
    # 1. البحث المحلي أولاً
    files = [f for f in os.listdir(SFX_DIR) if f.startswith(category)]
    if files:
        # تأكد أن الملف ليس تالفاً (أكبر من 10 كيلو بايت)
        selected = os.path.join(SFX_DIR, random.choice(files))
        if os.path.getsize(selected) > 10000:
            return selected
        else:
            os.remove(selected) # احذف الملف التالف

    # 2. التحميل من يوتيوب
    st.toast(f"🦅 جاري تحميل مؤثر سينمائي: {category}...")
    search_query = SCENE_MAP.get(category, {"search": category})["search"]
    
    # تحسين البحث: نطلب فيديوهات قصيرة وعالية الجودة
    target_url = f"ytsearch3:{search_query} no copyright sound effect"
    
    filename_base = f"{category}_{random.randint(1000,9999)}"
    filename_path = os.path.join(SFX_DIR, filename_base)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename_path,
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 10 * 1024 * 1024, # لا تحمل ملفات أكبر من 10 ميجا
        'match_filter': yt_dlp.utils.match_filter_func("duration < 60"), # فقط أقل من دقيقة
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target_url])
        
        # البحث عن الملف الناتج (قد يكون mp3)
        final_path = filename_path + ".mp3"
        if os.path.exists(final_path) and os.path.getsize(final_path) > 5000:
            return final_path
        
    except Exception as e:
        print(f"Error downloading {category}: {e}")
        
    return None

# ==========================================
# ✂️ دوال المعالجة الصوتية
# ==========================================
def smart_crop_audio(sound, silence_thresh=-40, padding=50):
    try:
        # قص الصمت بدقة أكبر
        nonsilent_ranges = detect_nonsilent(sound, min_silence_len=200, silence_thresh=silence_thresh)
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
        # تغيير طفيف جداً للسرعة لتجنب الحقوق
        speed_change = random.uniform(0.98, 1.02)
        new_sample_rate = int(sound.frame_rate * speed_change)
        camouflaged = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
        return camouflaged.set_frame_rate(44100)
    except:
        return sound

# ==========================================
# 🎬 المعالجة الرئيسية
# ==========================================
def process_audio(voice_file):
    # 1. Whisper (موديل Medium)
    st.info("🧠 1. جاري التحليل بموديل (Medium) لفهم اللهجة المصرية... (قد يستغرق دقيقة)")
    try:
        # 👇 التغيير هنا: استخدام medium بدلاً من base
        model = WhisperModel("medium", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(voice_file, word_timestamps=True, language="ar")
        
        detailed_words = []
        full_text = []
        
        for segment in segments:
            for word in segment.words:
                cleaned_word = word.word.strip()
                # تنظيف الكلمة من التشكيل لسهولة البحث
                cleaned_word = re.sub(r'[\u064B-\u065F]', '', cleaned_word) 
                detailed_words.append({'text': cleaned_word, 'start': word.start})
                full_text.append(cleaned_word)
                
        text_data = " ".join(full_text)
        st.text_area("النص المستخرج (أدق الآن):", text_data, height=100)
        
    except Exception as e:
        st.error(f"Error Whisper: {e}")
        return None

    # 2. المخرج المصري
    st.info("⚡ 2. جاري تحديد أماكن المؤثرات...")
    sfx_plan = analyze_text_with_regex(detailed_words)
    
    if not sfx_plan:
        st.warning("⚠️ لم يتم العثور على كلمات مفتاحية. تأكد من وضوح الصوت.")
    else:
        st.success(f"✅ تم العثور على {len(sfx_plan)} مؤثر!")
        # عرض الخطة بشكل جميل
        st.dataframe(sfx_plan)

    # 3. المونتاج
    st.info("🎬 3. جاري المونتاج ودمج الأصوات...")
    full_audio = AudioSegment.from_file(voice_file)
    # تحسين جودة صوت الراوي
    full_audio = normalize(high_pass_filter(full_audio, 80)) 
    
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
                
                # ضبط مستوى الصوت بناءً على نوع المؤثر
                vol_adj = SCENE_MAP.get(sfx_name, {"vol": -5})["vol"]
                sound = sound + vol_adj
                
                # Fade in/out لنعومة الصوت
                sound = sound.fade_in(50).fade_out(300)
                
                # الدمج
                full_audio = full_audio.overlay(sound, position=int(time_sec * 1000))
            except Exception as e:
                print(f"Merge error: {e}")
        
        progress.progress((i + 1) / len(sfx_plan))

    output = "Final_Cinema_Egy.mp3"
    full_audio.export(output, format="mp3")
    return output

# ==========================================
# 🖥️ الواجهة
# ==========================================
uploaded_file = st.file_uploader("ارفع ملف الرواية (WAV/MP3)", type=["wav", "mp3"])

if uploaded_file:
    st.audio(uploaded_file)
    if st.button("🚀 ابدأ المونتاج (النسخة المحسنة)"):
        with open("input.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        final = process_audio("input.mp3")
        
        if final:
            st.balloons()
            st.success("🎉 المونتاج جاهز يا بطل!")
            st.audio(final)
            with open(final, "rb") as f:
                st.download_button("📥 تحميل الملف النهائي", f, file_name="Cinema_Montage.mp3")

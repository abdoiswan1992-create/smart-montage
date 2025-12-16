import streamlit as st
import os
import shutil
import json
import random
import re  # 👈 بطل الحلقة (مكتبة النصوص الدقيقة)
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter
from pydub.silence import detect_nonsilent
from faster_whisper import WhisperModel
import yt_dlp

# ==========================================
# ⚙️ إعدادات الصفحة
# ==========================================
st.set_page_config(page_title="المخرج السريع (بدون إنترنت)", page_icon="⚡", layout="centered")

st.markdown("""
<div style="text-align: center;">
    <h1>⚡ المخرج السريع (Offline Mode)</h1>
    <p>مونتاج فوري باستخدام خوارزميات اللغة الدقيقة (بدون ذكاء اصطناعي)</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 🛠️ الإعدادات
# ==========================================
SFX_DIR = "sfx_robust" 
if not os.path.exists(SFX_DIR): os.makedirs(SFX_DIR)

AudioSegment.converter = "ffmpeg" if shutil.which("ffmpeg") else "ffmpeg.exe"

# ==========================================
# 📚 القاموس الذكي (كلمات دلالية دقيقة)
# ==========================================
# لاحظ: نضع الكلمات بدقة (الجذر اللغوي)
SCENE_MAP = {
    "footsteps": {
        "triggers": ["مشى", "يمشي", "ركض", "خطوات", "أقدام", "يجري", "هروب"], 
        "search": "footsteps sound effect isolated", "vol": -5
    },
    "door_open": {
        "triggers": ["فتح الباب", "يفتح الباب", "صرير باب", "فتح"], 
        "search": "door open squeak sound effect", "vol": -5
    },
    "door_slam": {
        "triggers": ["أغلق الباب", "قفل الباب", "صفق الباب", "ارتطم"], 
        "search": "door slam sound effect", "vol": -3
    },
    "rain": {
        "triggers": ["مطر", "تمطر", "عاصفة", "غيوم", "شتاء"], 
        "search": "rain heavy sound effect", "vol": -10
    },
    "thunder": {
        "triggers": ["رعد", "برق", "صاعقة"], 
        "search": "thunder clap sound effect", "vol": -2
    },
    "car_engine": {
        "triggers": ["سيارة", "شاحنة", "محرك", "قيادة"], 
        "search": "car engine start sound effect", "vol": -5
    },
    "scream": {
        "triggers": ["صرخ", "يصرخ", "صراخ", "فزع", "رعب"], 
        "search": "scream sound effect horror", "vol": -5
    },
    "laugh": {
        "triggers": ["ضحك", "يضحك", "قهقهة", "سخرية"], 
        "search": "evil laugh sound effect", "vol": -5
    },
    "gunshot": {
        "triggers": ["أطلق النار", "رصاص", "مسدس", "بندقية", "سلاح"], 
        "search": "gunshot sound effect loud", "vol": -2
    },
    "sword": {
        "triggers": ["سيف", "نصل", "خنجر", "سل سيفه"], # لن يخلط مع "سنة" بعد الآن
        "search": "sword draw sound effect", "vol": -5
    },
    "heartbeat": {
        "triggers": ["قلبه", "خوف", "توتر", "رعب", "نبض"], 
        "search": "heartbeat sound effect horror", "vol": -4
    },
    "punch": {
        "triggers": ["لكم", "ضرب", "صفع", "هجوم"], 
        "search": "punch impact sound effect", "vol": -2
    }
}

GLOBAL_NEGATIVE_TAGS = ["cartoon", "funny", "meme", "remix", "song", "music", "intro"]

# ==========================================
# 🧠 المخرج "الخوارزمي" (بديل Gemini)
# ==========================================
def analyze_text_with_regex(transcript_segments):
    """
    يقوم هذا المخرج بتحليل النص كلمة بكلمة باستخدام Regex
    لضمان أن الكلمة هي كلمة كاملة وليست جزءاً من كلمة أخرى.
    """
    plan = []
    # تجميع كل الكلمات التي تم العثور عليها لتجنب التكرار القريب
    last_trigger_time = -10
    
    for segment in transcript_segments:
        text = segment['text'] # الكلمة
        start = segment['start'] # التوقيت
        
        # إذا كان الفاصل الزمني قصير جداً عن المؤثر السابق، تجاهل (لمنع الازدحام)
        if start - last_trigger_time < 3.0: 
            continue

        found_sfx = None
        
        for sfx_key, data in SCENE_MAP.items():
            for trigger in data["triggers"]:
                # 🛡️ السحر هنا: نستخدم \b للتأكد من حدود الكلمة
                # هذا يمنع "سن" من التفعيل داخل "سنة"
                # ويسمح بـ "الـ" التعريف (اختياري)
                pattern = f"\\b{trigger}\\b" 
                
                if re.search(pattern, text, re.UNICODE):
                    found_sfx = sfx_key
                    break
            if found_sfx: break
        
        if found_sfx:
            plan.append({"sfx": found_sfx, "time": start})
            last_trigger_time = start
            
    return plan

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

def calculate_relevance_score(video_info, search_term):
    title = video_info.get('title', '').lower()
    duration = video_info.get('duration', 0)
    score = 0
    if search_term.split()[0] in title: score += 20
    if "original" in title or "hq" in title or "sfx" in title: score += 10
    if 1 <= duration <= 15: score += 20
    for tag in GLOBAL_NEGATIVE_TAGS:
        if tag in title: score -= 100
    if duration > 60: score -= 50
    return score

def get_best_sfx(category):
    files = [f for f in os.listdir(SFX_DIR) if f.startswith(category)]
    if files:
        return os.path.join(SFX_DIR, random.choice(files))

    st.toast(f"🦅 جاري صيد مؤثر: {category}...")
    search_base = SCENE_MAP.get(category, {"search": category + " sound effect"})["search"]
    
    ydl_opts_search = {
        'quiet': True, 'default_search': 'ytsearch5', 'extract_flat': True,
        'nocheckcertificate': True, 'ignoreerrors': True,
    }

    best_url = None
    best_score = -9999
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
            result = ydl.extract_info(f"{search_base} no copyright", download=False)
            if 'entries' in result:
                for entry in result['entries']:
                    score = calculate_relevance_score(entry, search_base)
                    if score > best_score:
                        best_score = score
                        best_url = entry['url']
    except:
        pass

    target_url = best_url if best_url else f"ytsearch1:{search_base} short sfx"
    
    filename = f"{category}_{random.randint(1000,9999)}"
    ydl_opts_download = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(SFX_DIR, filename),
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            ydl.download([target_url])
        return os.path.join(SFX_DIR, filename + ".mp3")
    except:
        return None

# ==========================================
# 🎬 المعالجة الرئيسية
# ==========================================
def process_audio(voice_file):
    # 1. Whisper (استخراج النص)
    st.info("🧠 1. جاري استخراج النص والكلمات (Whisper)...")
    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(voice_file, word_timestamps=True, language="ar")
        
        # نحتاج قائمة مفصلة للتحليل
        detailed_words = []
        full_text = []
        
        for segment in segments:
            for word in segment.words:
                cleaned_word = word.word.strip()
                detailed_words.append({'text': cleaned_word, 'start': word.start})
                full_text.append(cleaned_word)
                
        st.text_area("النص:", " ".join(full_text), height=80)
        
    except Exception as e:
        st.error(f"Error Whisper: {e}")
        return None

    # 2. المخرج الخوارزمي (بديل Gemini)
    st.info("⚡ 2. المخرج السريع يقوم بتحليل الكلمات الدلالية...")
    
    # استدعاء الدالة المحلية بدلاً من API
    sfx_plan = analyze_text_with_regex(detailed_words)
    
    if not sfx_plan:
        st.warning("⚠️ لم يجد المخرج أي كلمات دلالية (مثل: باب، ركض، سيارة...) في النص.")
    else:
        st.success(f"✅ تم العثور على {len(sfx_plan)} مؤثر!")
        st.write(sfx_plan)

    # 3. المونتاج
    st.info("🎬 3. جاري المونتاج...")
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

    output = "Fast_Montage_Result.mp3"
    full_audio.export(output, format="mp3")
    return output

# ==========================================
# 🖥️ الواجهة
# ==========================================
uploaded_file = st.file_uploader("ارفع ملف الصوت", type=["wav", "mp3"])

if uploaded_file:
    st.audio(uploaded_file)
    if st.button("🚀 ابدأ المونتاج السريع"):
        with open("input.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        final = process_audio("input.mp3")
        
        if final:
            st.balloons()
            st.success("تم الانتهاء! 🎧")
            st.audio(final)
            with open(final, "rb") as f:
                st.download_button("تحميل", f, file_name="Montage.mp3")

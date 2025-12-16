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
st.set_page_config(page_title="المخرج السينمائي (نسخة التنويع)", page_icon="🎭", layout="centered")

st.markdown("""
<div style="text-align: center;">
    <h1>🎭 المخرج السينمائي (نسخة التنويع الواقعي)</h1>
    <p>أصوات لا تتكرر + مؤثرات رعب مدروسة</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 🛠️ الإعدادات الخلفية
# ==========================================
SFX_DIR = "sfx_robust" 
if not os.path.exists(SFX_DIR): os.makedirs(SFX_DIR)

AudioSegment.converter = "ffmpeg" if shutil.which("ffmpeg") else "ffmpeg.exe"

# ==========================================
# 📚 القاموس المتنوع (قوائم بحث متعددة لكل مؤثر)
# ==========================================
SCENE_MAP = {
    "footsteps": {
        "triggers": ["بيجري", "يجري", "مشى", "يمشي", "خطوات", "بسرعة", "هروب", "يلتفت", "تتدحرج", "زحف"], 
        # تنويع بين الركض والمشي والزحف
        "searches": [
            "running footsteps on dirt horror sound effect",
            "fast breathing and running footsteps sound effect",
            "slow heavy footsteps echo horror",
            "dragging body on floor sound effect"
        ],
        "vol": -4
    },
    "door_open": {
        "triggers": ["فتح", "يفتح", "باب", "دخل", "عدى", "صرير"], 
        "searches": [
            "slow creaky wooden door open sound effect",
            "heavy metal door opening horror sound effect",
            "old dungeon door squeak sound effect"
        ],
        "vol": -5
    },
    "door_slam": {
        "triggers": ["أفل", "قفل", "خبط", "رزع", "ارتطم", "تطام", "تحشم", "تهشم", "سد"], 
        # تنويع طرق إغلاق الباب
        "searches": [
            "heavy wooden door slam reverb sound effect",
            "loud metal door slam prison sound effect",
            "distant door slam echo horror",
            "impact thud sound effect cinematic"
        ],
        "vol": -2
    },
    "breathing": {
        "triggers": ["بيس", "يلهث", "نفس", "هواء", "اختناق", "اختناء", "صدره", "تعب"], 
        "searches": [
            "scared man hyperventilating sound effect",
            "heavy tired breathing after running sound effect",
            "choking gasping for air sound effect"
        ],
        "vol": -8
    },
    "scream": {
        "triggers": ["صرخ", "صرح", "صيحة", "صوت عالي", "فزع", "يا لهوي", "الحقوني"], 
        # صرخات واقعية وليست كرتونية
        "searches": [
            "short gasp of terror sound effect",
            "man terrifying scream horror realistic",
            "muffled scream horror sound effect",
            "falling scream with echo cinematic"
        ],
        "vol": -6 # خفضنا الصوت ليكون أقل إزعاجاً
    },
    "rock_crumble": {
        "triggers": ["انهيار", "صخور", "تراب", "ردم", "زلزال", "تنهار", "السرداب"], 
        "searches": [
            "cave ceiling collapse sound effect",
            "falling rocks and debris sound effect",
            "earthquake rumble sound effect low frequency"
        ],
        "vol": -4
    },
    "heartbeat": {
        "triggers": ["قلبه", "خوف", "رعب", "نبض", "دق"], 
        "searches": [
            "slow intense heartbeat horror sound effect",
            "fast racing heartbeat sound effect"
        ],
        "vol": -5
    },
     "wind": {
        "triggers": ["هواء", "تهوية", "نفق", "رياح", "ظلام"], 
        "searches": [
            "eerie cave wind howling sound effect",
            "low dark drone ambience horror"
        ],
        "vol": -12
    }
}

# ==========================================
# 🧠 المخرج "الخوارزمي"
# ==========================================
def analyze_text_with_regex(transcript_segments):
    plan = []
    last_trigger_time = -5
    
    for segment in transcript_segments:
        text = segment['text']
        start = segment['start']
        
        if start - last_trigger_time < 3.0: # زيادة الفاصل الزمني لمنع الازدحام
            continue

        found_sfx = None
        
        for sfx_key, data in SCENE_MAP.items():
            for trigger in data["triggers"]:
                if trigger in text:
                    found_sfx = sfx_key
                    break
            if found_sfx: break
        
        if found_sfx:
            plan.append({"sfx": found_sfx, "time": start})
            last_trigger_time = start
            
    return plan

# ==========================================
# 📥 التحميل المتنوع (Random Picker)
# ==========================================
def get_diverse_sfx(category):
    # نختار جملة بحث عشوائية من القائمة لضمان التنوع
    search_query = random.choice(SCENE_MAP.get(category)["searches"])
    
    # اسم الملف يحتوي على جزء من جملة البحث لكي لا نخلط بين الأنواع
    safe_search_name = re.sub(r'\W+', '', search_query)[:10]
    filename_base = f"{category}_{safe_search_name}_{random.randint(100,999)}"
    filename_path = os.path.join(SFX_DIR, filename_base)
    
    # 1. هل لدينا ملف مشابه سابقاً؟ (نحاول استخدامه بنسبة 50% لتوفير الوقت، ونحمل جديد بنسبة 50%)
    existing_files = [f for f in os.listdir(SFX_DIR) if f.startswith(category)]
    if existing_files and random.random() > 0.6: # 40% فرصة تحميل صوت جديد تماماً
        selected = os.path.join(SFX_DIR, random.choice(existing_files))
        if os.path.getsize(selected) > 5000:
            return selected

    # 2. التحميل من يوتيوب (البحث عن الجديد)
    st.toast(f"🦅 جاري البحث عن صوت جديد: {search_query}...")
    
    target_url = f"ytsearch1:{search_query} no copyright sound effect"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename_path,
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 10 * 1024 * 1024,
        'match_filter': yt_dlp.utils.match_filter_func("duration < 30"), # مؤثرات قصيرة فقط
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target_url])
        
        final_path = filename_path + ".mp3"
        if os.path.exists(final_path) and os.path.getsize(final_path) > 5000:
            return final_path
        
    except Exception as e:
        print(f"Error downloading {category}: {e}")
        # في حالة الفشل، نعود لأي ملف قديم
        if existing_files:
             return os.path.join(SFX_DIR, random.choice(existing_files))
        
    return None

# ==========================================
# ✂️ دوال المعالجة
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
    except:
        return sound

def camouflage_audio(sound):
    try:
        speed_change = random.uniform(0.95, 1.05)
        new_sample_rate = int(sound.frame_rate * speed_change)
        camouflaged = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
        return camouflaged.set_frame_rate(44100)
    except:
        return sound

# ==========================================
# 🎬 المعالجة الرئيسية
# ==========================================
def process_audio(voice_file):
    # 1. Whisper
    st.info("🧠 1. جاري تحليل اللهجة المصرية (Medium)...")
    try:
        model = WhisperModel("medium", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(voice_file, word_timestamps=True, language="ar")
        
        detailed_words = []
        full_text = []
        
        for segment in segments:
            for word in segment.words:
                cleaned_word = word.word.strip()
                cleaned_word = re.sub(r'[\u064B-\u065F]', '', cleaned_word) 
                detailed_words.append({'text': cleaned_word, 'start': word.start})
                full_text.append(cleaned_word)
                
        text_data = " ".join(full_text)
        st.text_area("النص:", text_data, height=80)
        
    except Exception as e:
        st.error(f"Error Whisper: {e}")
        return None

    # 2. المخرج
    st.info("⚡ 2. المخرج يختار الأصوات المناسبة...")
    sfx_plan = analyze_text_with_regex(detailed_words)
    
    if sfx_plan:
        st.success(f"✅ تم تحديد {len(sfx_plan)} نقطة صوتية.")
        st.dataframe(sfx_plan)
    else:
        st.warning("⚠️ لم يتم العثور على مؤثرات.")

    # 3. المونتاج
    st.info("🎬 3. جاري تركيب الأصوات بتنويع سينمائي...")
    full_audio = AudioSegment.from_file(voice_file)
    full_audio = normalize(high_pass_filter(full_audio, 80)) 
    
    progress = st.progress(0)
    for i, item in enumerate(sfx_plan):
        sfx_name = item.get("sfx")
        time_sec = float(item.get("time"))
        
        # نستخدم دالة التنويع الجديدة
        sfx_path = get_diverse_sfx(sfx_name)
        
        if sfx_path and os.path.exists(sfx_path):
            try:
                sound = AudioSegment.from_file(sfx_path)
                sound = smart_crop_audio(sound)
                sound = camouflage_audio(sound)
                
                vol_adj = SCENE_MAP.get(sfx_name, {"vol": -5})["vol"]
                sound = sound + vol_adj
                sound = sound.fade_in(20).fade_out(400)
                
                full_audio = full_audio.overlay(sound, position=int(time_sec * 1000))
            except Exception as e:
                print(f"Merge error: {e}")
        
        progress.progress((i + 1) / len(sfx_plan))

    output = "Diverse_Montage.mp3"
    full_audio.export(output, format="mp3")
    return output

# ==========================================
# 🖥️ الواجهة
# ==========================================
# زر لتنظيف الذاكرة
if st.sidebar.button("🗑️ حذف الأصوات القديمة (لتجديد المكتبة)"):
    try:
        shutil.rmtree(SFX_DIR)
        os.makedirs(SFX_DIR)
        st.sidebar.success("تم الحذف! المونتاج القادم سيستخدم أصواتاً جديدة.")
    except Exception as e:
        st.sidebar.error(f"خطأ: {e}")

uploaded_file = st.file_uploader("ارفع ملف الصوت", type=["wav", "mp3"])

if uploaded_file:
    st.audio(uploaded_file)
    if st.button("🚀 ابدأ المونتاج السينمائي"):
        with open("input.mp3", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        final = process_audio("input.mp3")
        
        if final:
            st.balloons()
            st.success("🎉 المونتاج جاهز!")
            st.audio(final)
            with open(final, "rb") as f:
                st.download_button("📥 تحميل", f, file_name="Cinema_Montage.mp3")

import os
import random
import time
import json
import shutil
import streamlit as st  # 👈 ضروري لقراءة المفتاح السري
import google.generativeai as genai # 👈 مكتبة الذكاء الاصطناعي
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter
from pydub.silence import detect_nonsilent
import yt_dlp
from faster_whisper import WhisperModel

# ==========================================
# 🛠️ الإعدادات والمسارات
# ==========================================
current_dir = os.getcwd()

# تهيئة Gemini (سيحاول قراءة المفتاح من أسرار Streamlit)
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        print("✅ تم تفعيل Gemini بنجاح!")
    else:
        print("⚠️ لم يتم العثور على GEMINI_API_KEY في الـ Secrets.")
except Exception as e:
    print(f"⚠️ ملاحظة: نحن نعمل محلياً أو لا يوجد مفتاح ({e})")

# الفحص الذكي لـ FFMPEG
if shutil.which("ffmpeg"):
    AudioSegment.converter = "ffmpeg"
else:
    path_ffmpeg = os.path.join(current_dir, "ffmpeg.exe")
    if os.path.exists(path_ffmpeg):
        AudioSegment.converter = path_ffmpeg
        os.environ["PATH"] += os.pathsep + current_dir
    else:
        print("⚠️ تحذير: لم يتم العثور على FFMPEG!")

SFX_DIR = "sfx_robust" 
if not os.path.exists(SFX_DIR): os.makedirs(SFX_DIR)

# ==========================================
# 🧠 القاموس الموسوعي (كما هو - سنستخدمه كمرجع للبحث)
# ==========================================
SCENE_MAP = {
    "slide": { 
        "triggers": ["زحف", "انزلق"], "search": "body drag dirt sound effect",
        "positive": ["dragging", "floor"], "vol": -6, "cooldown": 15
    },
    "breath": {
        "triggers": ["أنفاس", "تنهد"], "search": "breath gasp sound effect isolated",
        "positive": ["scared", "heavy"], "vol": -12, "cooldown": 20
    },
    "heartbeat": {
        "triggers": ["قلبه", "خوف"], "search": "heartbeat sound effect horror",
        "positive": ["thump", "fast"], "vol": -4, "cooldown": 40
    },
    "body_fall": {
        "triggers": ["سقط", "وقع"], "search": "body fall impact sound effect",
        "positive": ["thud", "ground"], "vol": -2, "cooldown": 30
    },
    "clothes": {
        "triggers": ["ملابس", "جيب"], "search": "clothes rustle sound effect",
        "positive": ["fabric", "movement"], "vol": -12, "cooldown": 15
    },
    "punch": {
        "triggers": ["لكم", "ضرب"], "search": "punch impact sound effect",
        "positive": ["hit", "face"], "vol": -2, "cooldown": 10
    },
    "sword_draw": {
        "triggers": ["سيف", "نصل"], "search": "sword draw sound effect",
        "positive": ["metal", "sharp"], "vol": -5, "cooldown": 20
    },
    "gunshot": {
        "triggers": ["رصاص", "سلاح"], "search": "gunshot sound effect",
        "positive": ["loud", "pistol"], "vol": -2, "cooldown": 20
    },
    "reload": {
        "triggers": ["ذخيرة", "عمر"], "search": "gun reload sound effect",
        "positive": ["click", "magazine"], "vol": -5, "cooldown": 30
    },
    "wood_break": {
        "triggers": ["انكسار", "تكسر"], "search": "wood snap break sound effect",
        "positive": ["crack", "plank"], "vol": -4, "cooldown": 40
    },
    "wood_creak": {
        "triggers": ["خشب", "أرضية"], "search": "wood floor creak sound effect",
        "positive": ["step", "house"], "vol": -8, "cooldown": 15
    },
    "rocks": {
        "triggers": ["صخور", "حجارة"], "search": "rock debris falling sound effect",
        "positive": ["rumble", "cave"], "vol": -4, "cooldown": 50
    },
    "glass": {
        "triggers": ["زجاج", "تهشم"], "search": "glass shatter sound effect",
        "positive": ["break", "window"], "vol": -4, "cooldown": 60
    },
    "metal_bang": {
        "triggers": ["حديد", "معدن"], "search": "metal impact sound effect",
        "positive": ["clang", "hit"], "vol": -3, "cooldown": 30
    },
    "thunder": {
        "triggers": ["رعد", "برق"], "search": "thunder clap sound effect",
        "positive": ["loud", "rumble"], "vol": -1, "cooldown": 60
    },
    "rain": {
        "triggers": ["مطر", "تمطر"], "search": "rain heavy sound effect",
        "positive": ["storm", "water"], "vol": -10, "cooldown": 80
    },
    "car_engine": {
        "triggers": ["سيارة", "محرك"], "search": "car engine start sound effect",
        "positive": ["rev", "driving"], "vol": -5, "cooldown": 60
    },
    "phone": {
        "triggers": ["هاتف", "رن"], "search": "smartphone vibration sound effect",
        "positive": ["ringtone", "buzz"], "vol": -8, "cooldown": 50
    },
    "paper": {
        "triggers": ["ورق", "كتاب"], "search": "paper rustling sound effect",
        "positive": ["turning", "page"], "vol": -10, "cooldown": 20
    },
    "door_open": {
        "triggers": ["باب", "فتح"], "search": "door open squeak sound effect",
        "positive": ["handle", "creak"], "vol": -5, "cooldown": 30
    },
    "door_slam": {
        "triggers": ["أغلق", "قفل"], "search": "door slam sound effect",
        "positive": ["shut", "bang"], "vol": -3, "cooldown": 30
    },
    "lock": {
        "triggers": ["مفتاح", "قفل"], "search": "door lock sound effect",
        "positive": ["click", "key"], "vol": -6, "cooldown": 20
    }
}

GLOBAL_NEGATIVE_TAGS = ["cartoon", "funny", "meme", "remix", "song", "music", "intro", "compilation", "lofi", "beat", "voice", "talking"]

available_files_cache = {} 
last_used_file_index = {}
last_triggered_time = {}
global_last_event_time = -100

# ==========================================
# ⚖️ الدوال المساعدة (كما هي للحفاظ على الميزات)
# ==========================================
def calculate_relevance_score(video_info, positive_tags):
    title = video_info.get('title', '').lower()
    duration = video_info.get('duration', 0)
    score = 0
    for tag in positive_tags:
        if tag in title: score += 20
    for tag in GLOBAL_NEGATIVE_TAGS:
        if tag in title: score -= 100
    if "original" in title or "hq" in title or "high quality" in title: score += 10
    if "isolated" in title or "foley" in title or "sfx" in title: score += 30
    if 1 <= duration <= 15: score += 20
    elif duration > 60: score -= 50
    elif duration < 0.5: score -= 100
    return score

def smart_crop_audio(sound, silence_thresh=-40, padding=100):
    try:
        nonsilent_ranges = detect_nonsilent(sound, min_silence_len=300, silence_thresh=silence_thresh)
        if len(nonsilent_ranges) > 0:
            start_i, end_i = nonsilent_ranges[0]
            start_i = max(0, start_i - padding)
            end_i = min(len(sound), end_i + padding)
            return sound[start_i:end_i]
        return sound
    except: return sound

def camouflage_audio(filepath):
    try:
        sound = AudioSegment.from_file(filepath)
        speed_change = random.uniform(0.96, 1.04)
        new_sample_rate = int(sound.frame_rate * speed_change)
        camouflaged = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
        camouflaged = camouflaged.set_frame_rate(44100)
        camouflaged.export(filepath, format="mp3")
        return True
    except: return False

def check_audio_quality(filepath):
    try:
        sound = AudioSegment.from_file(filepath)
        duration_sec = len(sound) / 1000.0
        if duration_sec > 120: 
            os.remove(filepath)
            return False
        if duration_sec < 0.2:
            os.remove(filepath)
            return False
        return True
    except: return False

def get_best_variation(category, data_map):
    # 1. التدوير المحلي
    existing_files = []
    for f in os.listdir(SFX_DIR):
        if f.startswith(f"{category}_") and f.endswith(".mp3"):
            existing_files.append(os.path.join(SFX_DIR, f))
    
    available_files_cache[category] = sorted(existing_files)
    files = available_files_cache.get(category, [])
    last_idx = last_used_file_index.get(category, -1)
    
    if len(files) > 0:
        if len(files) > 1:
            next_idx = (last_idx + 1) % len(files)
            file_to_use = files[next_idx]
            last_used_file_index[category] = next_idx
            print(f"      📦 استخدام ملف مخزن: {os.path.basename(file_to_use)}")
            return file_to_use

    # 2. البحث الذكي (يوتيوب)
    print(f"      🦅 جاري البحث في يوتيوب عن '{category}'...")
    search_base = data_map["search"]
    positive_tags = data_map["positive"]
    
    ydl_opts_search = {
        'quiet': True, 'default_search': 'ytsearch5', 'extract_flat': True,
        'nocheckcertificate': True, 'ignoreerrors': True,
    }

    best_url = None
    best_score = -9999
    best_title = ""
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
            search_query = f"{search_base} sound effect no copyright"
            result = ydl.extract_info(search_query, download=False)
            if 'entries' in result:
                for entry in result['entries']:
                    if not entry: continue
                    score = calculate_relevance_score(entry, positive_tags)
                    if score > best_score:
                        best_score = score
                        best_url = entry['url']
                        best_title = entry['title']
    except Exception as e:
        print(f"      ⚠️ تعذر التقييم: {e}")

    target_download = best_url
    if not target_download:
        print(f"      ⚠️ لم نجد فائزاً مثالياً، تفعيل التحميل الإجباري...")
        target_download = f"ytsearch1:{search_base} sound effect short no copyright"
    else:
        print(f"      🏆 الفائز: {best_title} ({best_score})")

    new_id = len(files) + 1
    filename = f"{category}_{new_id}.mp3"
    filepath = os.path.join(SFX_DIR, filename)
    
    ydl_opts_download = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(SFX_DIR, f"{category}_{new_id}"),
        'noplaylist': True, 'quiet': True,
        'max_filesize': 20*1024*1024,
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'nocheckcertificate': True, 'ignoreerrors': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            ydl.download([target_download])
        if os.path.exists(filepath):
            if check_audio_quality(filepath):
                camouflage_audio(filepath)
                last_used_file_index[category] = new_id - 1
                return filepath
    except Exception as e:
        print(f"      ❌ فشل التحميل: {e}")
    
    return None

# ==========================================
# 🎬 المخرج الذكي (Hybrid: Gemini Brain + YT-DLP Muscle)
# ==========================================
def robust_director(voice_file):
    print("🧠 جاري تحميل Whisper لاستخراج النص والتوقيت...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    
    # 1. تحويل الصوت لنص مع توقيت دقيق
    segments, info = model.transcribe(voice_file, beam_size=5, word_timestamps=True, language="ar")
    
    full_transcript = []
    print("📝 جاري بناء النص الزمني...")
    
    for segment in segments:
        for word in segment.words:
            # نخزن الكلمة وتوقيتها بدقة [ثانية] كلمة
            full_transcript.append(f"[{word.start:.2f}] {word.word}")
    
    transcript_text = " ".join(full_transcript)
    
    # 2. استشارة Gemini (المخرج)
    print("🤖 جاري إرسال السيناريو إلى Gemini للتحليل...")
    
    # نجهز قائمة المؤثرات التي لدينا تعريف لها في القاموس
    available_sfx_list = list(SCENE_MAP.keys())
    
    prompt = f"""
    أنت مخرج صوتي سينمائي محترف وخبير في اللهجة المصرية.
    لديك نص لقصة مع التوقيت الزمني لكل كلمة بالتنسيق [ثانية] كلمة.
    
    المطلوب:
    استخرج المؤثرات الصوتية المناسبة للسياق بدقة.
    القاعدة الذهبية: تجاهل الجمل المنفية تماماً (مثال: "لم يفتح الباب" -> لا تضع صوت باب).
    افهم المجاز: "قلبي وقع في رجلي" -> تعني خوف (heartbeat).
    
    النص:
    {transcript_text}
    
    قائمة المؤثرات المسموح لك استخدامها فقط:
    {available_sfx_list}
    
    أخرج النتيجة بصيغة JSON فقط مصفوفة تحتوي على:
    "sfx": اسم المؤثر من القائمة أعلاه.
    "time": وقت بداية المؤثر بالثواني (رقم).
    
    مثال للرد الصحيح:
    [
      {{"sfx": "footsteps", "time": 12.5}},
      {{"sfx": "door_open", "time": 15.2}}
    ]
    """
    
    sfx_plan = []
    try:
        model_gemini = genai.GenerativeModel('gemini-1.5-flash')
        response = model_gemini.generate_content(prompt)
        
        # تنظيف الرد للحصول على JSON فقط
        response_text = response.text.replace("```json", "").replace("```", "").strip()
        sfx_plan = json.loads(response_text)
        
        print("✅ الخطة الإخراجية من Gemini جاهزة:")
        print(sfx_plan)
        
    except Exception as e:
        print(f"❌ تعذر استخدام Gemini ({e})، سنستمر بدون مؤثرات جديدة لهذه المرة.")
        # هنا يمكن وضع كود احتياطي (Fallback) إذا أردت

    # 3. التنفيذ (باستخدام عضلات الكود القديم للتحميل والدمج)
    full_audio = AudioSegment.from_file(voice_file)
    full_audio = normalize(high_pass_filter(full_audio, 100))
    
    print(f"\n🎬 جاري دمج {len(sfx_plan)} مؤثر...")

    for item in sfx_plan:
        try:
            category = item["sfx"]
            start_time_sec = float(item["time"])
            
            # نتأكد أن المؤثر موجود في قاموسنا لنجلب بيانات البحث
            if category in SCENE_MAP:
                data_map = SCENE_MAP[category]
                
                # 👇 هنا نستخدم دالة التحميل القديمة القوية!
                sfx_file = get_best_variation(category, data_map)
                
                if sfx_file:
                    sfx_sound = AudioSegment.from_file(sfx_file)
                    sfx_sound = smart_crop_audio(sfx_sound) # قص الصمت
                    
                    # ضبط الصوت والمكان
                    sfx_sound = sfx_sound + data_map["vol"]
                    sfx_sound = sfx_sound.fade_out(400)
                    
                    full_audio = full_audio.overlay(sfx_sound, position=int(start_time_sec * 1000))
                    print(f"   ➕ تم دمج {category} في {start_time_sec}s")
            
        except Exception as e:
            print(f"   ⚠️ تجاوز مؤثر بسبب خطأ: {e}")

    output_file = "Final_AI_Story.mp3"
    full_audio.export(output_file, format="mp3")
    print(f"\n🎉 تم الإنتاج! {output_file}")
    
    return output_file

if __name__ == "__main__":
    # للاختبار المباشر
    robust_director("test.wav")

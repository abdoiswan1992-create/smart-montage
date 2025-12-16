import os
import random
import time
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter
from pydub.silence import detect_nonsilent
import yt_dlp
from faster_whisper import WhisperModel  # 👈 البطل الجديد

import shutil  # 👈 تأكد من إضافة هذا السطر الجديد لأنه ضروري للفحص

# ==========================================
# 🛠️ الإعدادات والمسارات (معدلة للعمل أونلاين + محلياً)
# ==========================================
current_dir = os.getcwd()

# الفحص الذكي: هل FFMPEG مثبت في النظام (للسيرفر) أم نستخدم الملف المحلي (لك)؟
if shutil.which("ffmpeg"):
    # حالة السيرفر (Linux/Streamlit Cloud)
    AudioSegment.converter = "ffmpeg"
else:
    # حالة جهازك الشخصي (Windows)
    path_ffmpeg = os.path.join(current_dir, "ffmpeg.exe")
    if os.path.exists(path_ffmpeg):
        AudioSegment.converter = path_ffmpeg
        os.environ["PATH"] += os.pathsep + current_dir
    else:
        print("⚠️ تحذير: لم يتم العثور على FFMPEG! تأكد من وجود ملف ffmpeg.exe")

# إعداد مجلد المؤثرات (نحافظ على sfx_robust)
SFX_DIR = "sfx_robust" 
if not os.path.exists(SFX_DIR): os.makedirs(SFX_DIR)

# ==========================================
# 🧠 القاموس الموسوعي (كما هو)
# ==========================================
# ==========================================
# 🧠 القاموس الموسوعي (فصحى + مصري 🇪🇬)
# ==========================================
SCENE_MAP = {
    # -----------------------------------
    # 🏃 حركات الجسم (Foley)
    # -----------------------------------
    "slide": { 
        # مصري: اتسحب، بيجرجر، بيزحف
        "triggers": ["زحف", "انزلق", "يجر", "زاحف", "تدحرج", "احتكاك", "اتسحب", "بيجر", "بيسحف"],
        "search": "body drag dirt sound effect",
        "positive": ["dragging", "floor", "heavy", "fabric", "sliding"],
        "vol": -6, "cooldown": 15
    },
    "breath": {
        # مصري: بينهج، نفسه مقطوع، بيموت
        "triggers": ["أنفاس", "تنهد", "شهيق", "زفير", "يلهث", "خائف", "يستريح", "بينهج", "كرشة نفس", "نفسه", "شهق"],
        "search": "breath gasp sound effect isolated",
        "positive": ["scared", "heavy", "running", "female", "male"],
        "vol": -12, "cooldown": 20
    },
    "heartbeat": {
        # مصري: قلبي هيقف، مرعوب، مخضوض
        "triggers": ["قلبه", "خوف", "توتر", "رعب", "نبض", "خفقان", "ادرينالين", "مرعوب", "هيموت", "خضة", "مخضوض"],
        "search": "heartbeat sound effect horror",
        "positive": ["thump", "fast", "tension", "cinematic", "loud"],
        "vol": -4, "cooldown": 40
    },
    "body_fall": {
        # مصري: اتكعبل، اترمى، دِب، وقع من طوله
        "triggers": ["سقط", "وقع", "أغمي", "أرضا", "رماه", "هوى", "تعثر", "اتكعبل", "اترمى", "طب ساكت", "دب", "هبد"],
        "search": "body fall impact sound effect",
        "positive": ["thud", "ground", "hit", "collapse", "bone"],
        "vol": -2, "cooldown": 30
    },
    "clothes": {
        # مصري: هدوم، جاكيت، بيظبط
        "triggers": ["ملابس", "جيب", "ارتدى", "نفض", "كم", "سترة", "هدوم", "جاكيت", "بنطلون", "بيعدل"],
        "search": "clothes rustle sound effect",
        "positive": ["fabric", "movement", "jacket", "pants"],
        "vol": -12, "cooldown": 15
    },

    # -----------------------------------
    # ⚔️ القتال والأكشن (Action)
    # -----------------------------------
    "punch": {
        # مصري: إداله، علقة، خناقة، بوكس، لطش
        "triggers": ["لكم", "ضرب", "صفع", "هجم", "اشتبك", "بوكس", "خناقة", "علقة", "لطش", "إداله", "شلوت"],
        "search": "punch impact sound effect",
        "positive": ["hit", "face", "fight", "heavy", "combat"],
        "vol": -2, "cooldown": 10
    },
    "sword_draw": {
        # مصري: سحب السكينة، مطوة
        "triggers": ["سيف", "نصل", "استل", "خنجر", "سكين", "معدن", "مطوة", "سحب", "سن", "بيسن"],
        "search": "sword draw sound effect",
        "positive": ["metal", "sharp", "sheath", "knife", "blade"],
        "vol": -5, "cooldown": 20
    },
    "gunshot": {
        # مصري: طبنجة، ضرب نار، آلي
        "triggers": ["رصاص", "سلاح", "مسدس", "أطلق", "نار", "بندقية", "زناد", "طبنجة", "خرطوش", "آلي", "ضرب"],
        "search": "gunshot sound effect",
        "positive": ["loud", "pistol", "blast", "fire", "9mm"],
        "vol": -2, "cooldown": 20
    },
    "reload": {
        # مصري: بيعمر، خزنة
        "triggers": ["ذخيرة", "عمر", "لقم", "مخزن", "رصاصات", "خزنة", "بيعمر", "تعمير"],
        "search": "gun reload sound effect",
        "positive": ["click", "magazine", "clip", "weapon"],
        "vol": -5, "cooldown": 30
    },

    # -----------------------------------
    # 🏚️ البيئة والمواد (Environment)
    # -----------------------------------
    "wood_break": {
        # مصري: دغدغ، كسر، اتخلع
        "triggers": ["انكسار", "تكسر", "هشم", "تحطم", "خلع", "دغدغ", "اتكسر", "فرتك"],
        "search": "wood snap break sound effect",
        "positive": ["crack", "plank", "smash", "tree", "destruction"],
        "vol": -4, "cooldown": 40
    },
    "wood_creak": {
        # مصري: تزييق، باركيه
        "triggers": ["خشب", "أرضية", "صرير", "ألواح", "قديم", "تزييق", "بيزيق", "باركيه"],
        "search": "wood floor creak sound effect",
        "positive": ["step", "house", "spooky", "slow"],
        "vol": -8, "cooldown": 15
    },
    "rocks": {
        # مصري: طوب، ردم، حصى
        "triggers": ["صخور", "حجارة", "انهيار", "ردم", "طريق", "صخرة", "ارتطام", "زلزال", "طوب", "دبش", "حصى"],
        "search": "rock debris falling sound effect",
        "positive": ["rumble", "cave", "collapse", "heavy", "earth"],
        "vol": -4, "cooldown": 50
    },
    "glass": {
        # مصري: دشدش، فتافيت، إزاز
        "triggers": ["زجاج", "نافذة", "شظايا", "تهشم", "كأس", "مرآة", "إزاز", "دشيش", "دشدش", "فتافيت"],
        "search": "glass shatter sound effect",
        "positive": ["break", "window", "smash", "crash", "sharp"],
        "vol": -4, "cooldown": 60
    },
    "metal_bang": {
        # مصري: صاج، خبط في حديد
        "triggers": ["حديد", "معدن", "طرق", "صفيح", "بوابة حديد", "صاج", "رزع حديد", "جرس"],
        "search": "metal impact sound effect",
        "positive": ["clang", "hit", "heavy", "pipe", "door"],
        "vol": -3, "cooldown": 30
    },

    # -----------------------------------
    # 🚪 الأبواب والمداخل
    # -----------------------------------
    "door_open": {
        # مصري: وارب، زق الباب
        "triggers": ["باب", "فتح", "وارب", "أوكرة", "زق"],
        "search": "door open squeak sound effect",
        "positive": ["handle", "creak", "room", "slow", "old"],
        "vol": -5, "cooldown": 30
    },
    "door_slam": {
        # مصري: رزع، هبد، تربس
        "triggers": ["أغلق", "قفل", "أوصد", "سد", "حبس", "صفق", "رزع", "هبد", "تربس"],
        "search": "door slam sound effect",
        "positive": ["shut", "bang", "close", "angry", "heavy"],
        "vol": -3, "cooldown": 30
    },
    "lock": {
        # مصري: ترباس، طق
        "triggers": ["مفتاح", "قفل", "مزلاج", "ترباس", "تكة", "طق"],
        "search": "door lock sound effect",
        "positive": ["click", "key", "turn", "unlock"],
        "vol": -6, "cooldown": 20
    },

    # -----------------------------------
    # ⛈️ الطقس (مختصر)
    # -----------------------------------
    "thunder": {
        "triggers": ["رعد", "برق", "سماء", "عاصفة", "غيوم", "بترعد", "بتبرق"],
        "search": "thunder clap sound effect",
        "positive": ["loud", "rumble", "storm", "strike"],
        "vol": -1, "cooldown": 60
    },
    "rain": {
        "triggers": ["مطر", "تمطر", "غيث", "بلل", "مياه", "سيول", "بتشتي", "غرقانة"],
        "search": "rain heavy sound effect",
        "positive": ["storm", "water", "falling", "roof"],
        "vol": -10, "cooldown": 80
    },
    
    # -----------------------------------
    # 🚗 متنوع
    # -----------------------------------
    "car_engine": {
        "triggers": ["سيارة", "محرك", "قيادة", "شغل", "انطلق", "عربية", "موتور", "دور"],
        "search": "car engine start sound effect",
        "positive": ["rev", "driving", "interior", "vehicle"],
        "vol": -5, "cooldown": 60
    },
    "phone": {
        "triggers": ["هاتف", "رن", "جوال", "اتصال", "رسالة", "موبايل", "بيرن"],
        "search": "smartphone vibration sound effect",
        "positive": ["ringtone", "buzz", "iphone", "call"],
        "vol": -8, "cooldown": 50
    },
    "paper": {
        "triggers": ["ورق", "رسالة", "صفحة", "خريطة", "كتاب", "بيقلب", "جواب"],
        "search": "paper rustling sound effect",
        "positive": ["turning", "page", "handling", "book"],
        "vol": -10, "cooldown": 20
    }
}

# كلمات محظورة
GLOBAL_NEGATIVE_TAGS = ["cartoon", "funny", "meme", "remix", "song", "music", "intro", "compilation", "lofi", "beat", "voice", "talking"]

available_files_cache = {} 
last_used_file_index = {}
last_triggered_time = {}
global_last_event_time = -100

# ==========================================
# ⚖️ نظام التحكيم
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

# ==========================================
# ✂️ القص الذكي
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
    except: return sound

# ==========================================
# 🕵️‍♂️ التمويه
# ==========================================
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

# ==========================================
# 🗑️ فلتر الجودة
# ==========================================
def check_audio_quality(filepath):
    try:
        sound = AudioSegment.from_file(filepath)
        duration_sec = len(sound) / 1000.0
        if duration_sec > 120: 
            print(f"         🗑️ مرفوض: طويل جداً ({duration_sec}s).")
            os.remove(filepath)
            return False
        if duration_sec < 0.2:
            os.remove(filepath)
            return False
        return True
    except: return False

# ==========================================
# 🦅 البحث والتحميل (النسخة الصامدة)
# ==========================================
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

    # 2. البحث الذكي
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

    # 3. الخطة البديلة
    target_download = best_url
    if not target_download:
        print(f"      ⚠️ لم نجد فائزاً مثالياً، تفعيل التحميل الإجباري...")
        target_download = f"ytsearch1:{search_base} sound effect short no copyright"
    else:
        print(f"      🏆 الفائز: {best_title} ({best_score})")

    # 4. تحميل
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
# 🌪️ محرك Whisper الجديد (الذكاء الخارق)
# ==========================================
# ==========================================
# 🌪️ محرك Whisper الجديد (مع فلتر الذكاء اللغوي)
# ==========================================
def robust_director(voice_file):
    # ==========================================
    # 👇👇 أضف هذه السطور لتصفير الذاكرة 👇👇
    global global_last_event_time, last_triggered_time
    print("🔄 جاري تصفير العدادات لبدء ملف جديد...")
    global_last_event_time = -100
    last_triggered_time = {}
    # ==========================================
    
    print("🧠 جاري تحميل نموذج Whisper (المرة الأولى قد تأخذ دقيقة)...")
    # ... (باقي الكود يبقى كما هو دون تغيير)
    model = WhisperModel("base", device="cpu", compute_type="int8")

    print(f"🎧 المخرج (Whisper): جاري تحليل '{voice_file}' بدقة عالية...")
    
    full_audio = AudioSegment.from_file(voice_file)
    full_audio = normalize(high_pass_filter(full_audio, 100))
    
    segments, info = model.transcribe(voice_file, beam_size=5, word_timestamps=True, language="ar")

    timeline = []
    
    print("   ...جاري مسح الكلمات واستخراج المؤثرات (الفلتر الذكي V2)...")
    
    for segment in segments:
        for word in segment.words:
            word_text = word.word.strip()
            # إزالة التشكيل (الفتحة والضمة...)
            word_text = "".join([c for c in word_text if c not in ["َ", "ً", "ُ", "ٌ", "ِ", "ٍ", "ْ", "ّ"]])
            
            start_time_sec = word.start
            
            # 🛑 المسافة الآمنة (4 ثواني)
            if start_time_sec - global_last_event_time < 4:
                continue

            for category, data in SCENE_MAP.items():
                
                # --- 🧠 الفلتر الذكي المعدل (يقبل الزوائد في النهاية) ---
                is_match = False
                
                # تنظيف الكلمة المنطوقة من البادئات (ال، و، ف، ب، ل)
                clean_spoken = word_text
                for prefix in ["ال", "و", "ف", "ب", "ل", "لل"]:
                    if clean_spoken.startswith(prefix):
                        clean_spoken = clean_spoken[len(prefix):]
                
                for trigger in data["triggers"]:
                    # 1. إذا كان المحفز طويلاً (4 أحرف أو أكثر) -> نقبل وجوده في أي مكان
                    if len(trigger) >= 4 and trigger in word_text:
                        is_match = True
                        break
                    
                    # 2. إذا كان قصيراً -> يجب أن تبدأ الكلمة به
                    # مثال: "بابها" تبدأ بـ "باب" (مقبول)
                    # مثال: "أسماء" لا تبدأ بـ "سماء" (مرفوض)
                    elif clean_spoken.startswith(trigger):
                        # شرط إضافي: ألا تكون الكلمة أطول بكثير من المحفز (لتجنب "كما" -> "كم")
                        if len(clean_spoken) <= len(trigger) + 3:
                            is_match = True
                            break
                # -----------------------------------------------------

                if is_match:
                    last_time = last_triggered_time.get(category, -100)
                    if start_time_sec - last_time < data["cooldown"]:
                        continue

                    print(f"   💡 {start_time_sec:.2f}s: الكلمة '{word_text}' -> سياق '{category}'")
                    
                    sfx_file = get_best_variation(category, data)
                    
                    if sfx_file:
                        timeline.append({
                            "file": sfx_file, 
                            "start": int(start_time_sec * 1000), 
                            "vol": data["vol"]
                        })
                        last_triggered_time[category] = start_time_sec
                        global_last_event_time = start_time_sec
                        break 

    print(f"\n🎬 جاري دمج {len(timeline)} مؤثر في أماكنها الدقيقة...")
    final_mix = full_audio
    
    for event in timeline:
        try:
            sfx = AudioSegment.from_file(event["file"])
            sfx = smart_crop_audio(sfx)
            sfx = sfx + event["vol"]
            sfx = sfx.fade_out(400)
            final_mix = final_mix.overlay(sfx, position=event["start"])
        except Exception as e:
            print(f"   ❌ خطأ دمج: {e}")

    output_file = "Final_Robust_Story.mp3"
    final_mix.export(output_file, format="mp3")
    print(f"\n🎉 تم الإنتاج! {output_file}")
    
    return output_file

if __name__ == "__main__":
    # للاختبار المباشر
    robust_director("téléchargé (3).wav")
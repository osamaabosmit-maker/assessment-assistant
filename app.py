import streamlit as st
import fitz  # PyMuPDF
from docx import Document
import random
import arabic_reshaper
from bidi.algorithm import get_display
import re
import qrcode
from PIL import Image
import io

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Edu-AI | مساعد التقييم الذكي", page_icon="💻", layout="wide")

# --- 2. كود CSS المطور (تركيز على ثبات النص العربي) ---
st.markdown("""
    <style>
    /* إجبار التطبيق بالكامل على اتجاه اليمين */
    [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main { 
        direction: rtl !important; 
        text-align: right !important; 
    }

    [data-testid="stSidebar"] { 
        direction: rtl !important; 
        text-align: right !important; 
    }

    .main-header { text-align: center; color: #1E3A8A; font-family: 'Arial'; }
    .right-title { text-align: right !important; font-size: 24px; font-weight: bold; color: #333; margin-top: 15px; }

    /* صناديق السؤال والإجابة - أصبحت أكثر استقراراً بعد حذف الرموز */
    .q-container { 
        background-color: #e3f2fd; border-right: 12px solid #1565c0; padding: 20px; 
        border-radius: 10px; color: #0d47a1; font-weight: bold; margin-bottom: 10px;
        direction: rtl !important; text-align: right !important;
    }
    .a-container { 
        background-color: #f1f8e9; border-right: 12px solid #2e7d32; padding: 18px; 
        border-radius: 10px; color: #1b5e20; margin-bottom: 15px;
        direction: rtl !important; text-align: right !important;
    }

    .stButton>button { width: 100%; border-radius: 20px; background-color: #2E7D32; color: white; height: 45px; font-size: 17px; }

    .stTextArea textarea { 
        direction: rtl !important; 
        text-align: right !important; 
        font-size: 16px !important; 
    }

    .report-box {
        text-align: right !important; 
        direction: rtl !important; 
        border-right: 5px solid #1E3A8A; 
        padding-right: 15px; 
        background-color: #f8f9fa; 
        border-radius: 10px; 
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)


# --- 3. وظائف معالجة النصوص ---
def fix_visuals(text, is_rev):
    if not text: return ""
    try:
        # ملاحظة: تم إزالة منطق إضافة علامة الاستفهام نهائياً لضمان استقرار النص
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped) if is_rev else reshaped
    except:
        return text


def clean_for_match(text):
    if not text: return set()
    text = text.lower()
    text = re.sub(r'[\u064B-\u0652]', '', text)
    text = re.sub(r'[أإآ]', 'ا', text).replace('ة', 'ه').replace('ى', 'ي')
    text = re.sub(r'[^\w\s]', ' ', text)
    stop_words = {"في", "من", "على", "عن", "الى", "هو", "هي", "تم", "التي", "الذي", "ان", "هذا", "بانه", "عباره"}
    return set(text.split()) - stop_words


def get_file_content(file):
    text = ""
    try:
        if file.name.endswith('.pdf'):
            with fitz.open(stream=file.read(), filetype="pdf") as doc:
                for page in doc: text += page.get_text() + " "
        else:
            doc = Document(file)
            text = "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        st.error(f"خطأ في قراءة الملف: {e}")
    return text


# --- 4. تهيئة الجلسة ---
if 'qa_pairs' not in st.session_state: st.session_state['qa_pairs'] = []
if 'student_answers' not in st.session_state: st.session_state['student_answers'] = {}
if 'current_file' not in st.session_state: st.session_state['current_file'] = ""

# --- 5. الهيدر ---
st.markdown("<h1 class='main-header'>🏆 مبادرة Edu-AI: مساعد التقييم الذكي</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>الجامعة الأسمرية الإسلامية | كلية التربية - قسم الحاسوب</p>",
            unsafe_allow_html=True)
st.divider()

# --- 6. القائمة الجانبية (Sidebar) ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>⚙️ لوحة التحكم</h2>", unsafe_allow_html=True)
    f = st.file_uploader("ارفع ملف المادة العلمية", type=['pdf', 'docx'])

    diff_level = st.selectbox("🎯 مستوى صعوبة الأسئلة:", ["سهل (تعاريف)", "متوسط (شرح وتوضيح)", "عالي (تحليل دقيق)"])

    if f and f.name != st.session_state['current_file']:
        st.session_state['qa_pairs'] = []
        st.session_state['student_answers'] = {}
        st.session_state['current_file'] = f.name

    if f and st.button("توليد الأسئلة ذكياً ✨"):
        with st.spinner('جاري تحليل المحتوى...'):
            content = get_file_content(f)
            paragraphs = [p.strip() for p in re.split(r'[\n.]', content) if len(p.strip()) > 35]
            extracted = []
            forbidden = ["مثال", "ملاحظة", "تنبيه", "فيما يلي", "خلاصة", "قائمة"]

            for i, p in enumerate(paragraphs):
                if ":" in p:
                    parts = p.split(":", 1)
                    subj = parts[0].strip()
                    ans = parts[1].strip()
                    if any(word in subj for word in forbidden) or len(subj) > 55 or len(subj) < 3: continue

                    ans_len = len(ans)
                    is_match = False
                    prefix = "وضح مفهوم"

                    if diff_level.startswith("سهل") and ans_len < 70:
                        prefix = "عرف الآتي:"
                        is_match = True
                    elif diff_level.startswith("متوسط") and 70 <= ans_len <= 160:
                        prefix = "وضح بالتفصيل مفهوم"
                        is_match = True
                    elif diff_level.startswith("عالي") and ans_len > 160:
                        prefix = "حلل واشرح باستفاضة"
                        is_match = True

                    if is_match:
                        # تم حذف علامة الاستفهام نهائياً لضمان استقرار العرض
                        extracted.append({"q": f"{prefix} ({subj})", "a": ans})

            if extracted:
                st.session_state['qa_pairs'] = random.sample(extracted, min(5, len(extracted)))
                st.session_state['student_answers'] = {}
                st.success(f"✅ تم توليد الأسئلة بنجاح")

    st.divider()
    if st.button("🗑️ مسح الجلسة"):
        st.session_state.clear()
        st.rerun()

    app_url = "https://edu-ai-app.streamlit.app"
    qr = qrcode.make(app_url)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    st.image(buf, use_container_width=True, caption="الركن التفاعلي Edu-AI")

# --- 7. عرض الأسئلة والتفاعل ---
if not st.session_state['qa_pairs']:
    st.info("💡 يرجى رفع ملف المادة العلمية من القائمة الجانبية للبدء.")
else:
    for i, item in enumerate(st.session_state['qa_pairs']):
        col_r, col_l = st.columns([3, 1])
        with col_r:
            st.markdown(
                f'<div style="text-align: right; direction: rtl;"><p class="right-title">السؤال رقم ({i + 1})</p></div>',
                unsafe_allow_html=True)
        with col_l: is_rev = st.toggle("إصلاح الاتجاه", key=f"rev_{i}")

        st.markdown(f"<div class='q-container'>📖 {fix_visuals(item['q'], is_rev)}</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='a-container'>📘 النموذج الأصلي: {fix_visuals(item['a'], is_rev)}</div>",
                    unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<p style='text-align: right; font-weight: bold;'>✍️ تعديل النموذج:</p>", unsafe_allow_html=True)
            st.session_state['qa_pairs'][i]['a'] = st.text_area("", value=item['a'], key=f"m_{i}", height=100, label_visibility="collapsed")
        with c2:
            st.markdown("<p style='text-align: right; font-weight: bold;'>📝 إجابة الطالب:</p>", unsafe_allow_html=True)
            st.session_state['student_answers'][i] = st.text_area("", placeholder="أدخل الإجابة هنا...", key=f"s_{i}", height=100, label_visibility="collapsed")
        st.divider()

    # --- 8. التقرير النهائي ---
    if st.button("🚀 إصدار التقرير النهائي"):
        st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>📊 التقييم الذكي</h2>", unsafe_allow_html=True)
        total_score = 0
        num_q = len(st.session_state['qa_pairs'])

        for i, item in enumerate(st.session_state['qa_pairs']):
            student_ans = st.session_state['student_answers'].get(i, "").strip()
            model_ans = st.session_state['qa_pairs'][i]['a']

            score = 0
            if student_ans:
                s_words = clean_for_match(student_ans)
                m_words = clean_for_match(model_ans)
                found = s_words.intersection({w for w in m_words if len(w) > 2})
                if len(found) >= 3: score = 100
                elif len(found) == 2: score = 85
                elif len(found) >= 1: score = 70

            total_score += score

            st.markdown(f"""
                <div class="report-box">
                    <h4 style="margin-bottom: 5px;">🔍 تحليل السؤال ({i + 1}):</h4>
                    <p style="color: #1565c0; font-weight: bold; margin: 0;">🔹 درجة المطابقة: {score}%</p>
                </div>
            """, unsafe_allow_html=True)

            if student_ans:
                if score >= 70: st.success("✅ إجابة جيدة.")
                else: st.error("❌ تحتاج لمزيد من التفاصيل.")
            else: st.error("🚫 لم يتم إدخال إجابة.")

        avg = total_score / num_q
        st.markdown(f"<div style='text-align: center;'><h2 style='color: #2E7D32;'>المعدل العام: {int(avg)}%</h2></div>", unsafe_allow_html=True)
        if avg >= 50: st.balloons()
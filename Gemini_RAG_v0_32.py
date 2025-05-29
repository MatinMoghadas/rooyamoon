import os
import time
import json
import asyncio
import fitz
import faiss
import pickle
import numpy as np
from typing import List
from dotenv import load_dotenv
import requests
import google.generativeai as genai
from google.api_core.exceptions import InternalServerError
from sentence_transformers import SentenceTransformer
import json
from pymongo import MongoClient
from datetime import datetime

mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["rooyamoon"]
collection = db["conversation"]

# load_dotenv()
# api_key = os.getenv("AIzaSyB2jJ1gmhbj05KBuLZY3pJNiS9h-CkDTJ0")
#
# # Expand ~ to full path
# base_dir = os.path.expanduser("/home/raoof/PycharmProjects/GeminiRag")
# os.makedirs(base_dir, exist_ok=True)
# filename = "faiss_index.index"
# full_path = os.path.join(base_dir, filename)
api_key = os.getenv("AIzaSyB2jJ1gmhbj05KBuLZY3pJNiS9h-CkDTJ0")
# Expand ~ to full path
base_dir = os.path.expanduser("./")
os.makedirs(base_dir, exist_ok=True)
filename = "faiss_index.index"
full_path = os.path.join(base_dir, filename)

Instruction_prompt = """شخصیت و موقعیت:

    تو یک حکیم ایرانی مسلمان و شاگرد مرحوم صفایی حائری هستی که در یک انجمن گفتگوی آنلاین فعالیت می‌کنی. پاسخ‌هایت طولانی، اما روان و دوستانه است. دیدگاهت توحیدی و مبتنی بر تجربیات عملی زندگی است.
        یک فایل PDF برای ایده‌گرفتن داری، اما هرگز به آن به‌عنوان منبع اشاره نکن.
    هدف گفتگو: هدایت غیرمستقیم نوجوانان به سوی اهداف و آینده اسلامی.
    مراحل پاسخ‌دهی:

    پاسخ اول:
        اگر به تو تاریخچه دادم یعنی پاسخ اول نیستی.
        فقط اگر در پاسخ اولی در ابتدا بگو سلام!
        مکالمه را دوستانه و صمیمی شروع کن.
        اگر موضوع درباره هدف یا آینده نوجوان است، او را از بی‌ثباتی روانی به سمت ثبات هدایت کن.
        اگر آرزویش غیراسلامی است، با لحن غیرمستقیم و دوستانه، او را به نگاه اسلامی دعوت کن.
        آرام و بدون خسته‌کردن، درباره آرزویش اطلاعات بگیر.
        هرگز تهاجمی نباش تا جبهه نگیرد.

    پاسخ های بعدی (هدایت غیرمستقیم):
        در پاسخ های غیر از پاسخ اول بگو در ابتدا بگو خب یا آهان یا پس یا فهمیدم یا درسته یا درست یا متوجهم یا میفهمم.
        ابتدا ارزش‌های اخلاقی اسلامی را مطرح کن، سپس اتصال به خدا را یادآوری کن.
        از او بخواه مثال بزند تا خودش به عمق آرزویش برسد (مستقیم نپرس "چرا؟").
        از تمثیل‌های تازه و غیرتکراری استفاده کن.
        حس نکند قصد تغییر او را داری؛ مثل یک رفیق همراهش باش.

    ارتقای آرزو:
        آرزوی او را یک سطح بالاتر ببر.
        نمونه‌هایی از آرزوهای اسلامی (در گیومه) ارائه کن که نشان‌دهنده رشد الهی باشد.
        تأکید کن که اهداف ارزشمند، در مسیر قرب به خدا هستند.
        اگر آرزویش درست است، فقط یک‌بار آن را ارتقا بده تا گیج نشود.

    محدودیت‌ها:
        اگر نوجوان قصد کل‌کل دارد، یک پاسخ بده و با اصطلاحات نوجوانانه بگو هدف تو هدایت به تفکر اسلامی است، سپس بگو "ادامه نده".
        از پاسخ‌های تکراری پرهیز کن.

    راهنمایی‌های اولیه:
        اگر نوجوان درباره آینده اسلامی اطلاع ندارد، چند راهکار عملی و آرزوهای اسلامی خلاقانه پیشنهاد کن.
        از هشتگ #آرزوی_جدید برای بررسی استعدادهای او استفاده کن.

    سبک نوشتاری:
        حداکثر 35 کلمه در هر پاسخ.
        بدون ایموجی.
        از اصطلاحات نوجوانانه (مثل «برگام»، «پایه»، «تابلو»، «چراغ خاموش»، «خفن») کم و به‌جا استفاده کن.
        تمثیل‌ها باید توحیدی و مرتبط با مبانی اسلامی باشند.

    اصطلاحات نوجوانانه و معانی:
        سیب‌زمینی: آدم بی‌غیرت (منفی، استفاده نشود).
        شوخی پشت وانتی: شوخی آزاردهنده.
        ضایع: رفتار اشتباه زیاد.
        ترکوندن: انجام بی‌نقص کار (به‌ندرت).
        گولاخ: قدبلند و بزرگ‌هیکل.
        برگام: تعجب شدید.
        پایه: همراه و همکاری‌کننده.
        تابلو: انگشت‌نما.
        چراغ خاموش: مخفیانه.
        حسش نیست: بی‌حوصله.
        خالی‌بند: دروغ‌گو.
        خفن: عالی.
        سه نشه: راز بماند.

    خط قرمزها:
        موضوعات موسیقی، زنا، رقص، اعتیاد، مشروب ممنوع.
        اگر بحث به این سمت رفت، بگو نمی‌توانی کمک کنی و با یک نقل‌قول عمیق او را به نگاه اسلامی دعوت کن.

    آیه کلیدی:
    در جایی از گفتگو بیاور:
    "لَيسَ لِلإِنسانِ إِلّا ما سَعىٰ ﴿۳۹ النجم ﴾"

    پایان گفتگو:
        وقتی مکالمه تمام شد، بگو: «به امید ساختن رویامون!»
        نوجوان را تشویق کن تا:
            آرزوی جدید مطرح کند.
            این بات را به دیگران معرفی کند.
            در مسابقه شرکت کند.
        اگر پس از این جمله ادامه داد، آن را تکرار نکن مگر مکالمه واقعاً تمام شود.

    تذکرات مهم:
        ابتدا مطمئن شو موضوع درباره اهداف و آینده اسلامی است؛ اگر نبود، بگو خارج از حوزه کاری توست.
        همیشه از تمثیل‌های جدید و دیدگاه توحیدی استفاده کن.
        موسیقی آرامش ندارد و اعتیادآور است.
        دنیا را جای بندگی کن، نه زندگی.
        هدف نیازی به «حس خوب» یا «علاقه» ندارد.

    نکات نهایی:
        پاسخ‌ها را سوالی تمام نکن.
        از اصطلاحات به‌روز استفاده کن.
        تمثیل‌ها توحیدی و اسلامی باشند."""
added_points = """
  دقت کن که صحبت تکراری انجام ندی.
"""
samples = """
    به عنوان نمونه چند گفت و گو برات میگذارم:

    نمونه اول:
     نوجوان:
راستش هیچ‌چیز خاصی تو زندگیم نمی‌خوام. فقط پول زیاد که راحت زندگی کنم.
 حکیم:
آدم گاهی یه‌جوری خسته‌ست که حسش نیست آرزو کنه، ولی همین که گفتی «پول زیاد»، یعنی یه چیزی ته دلت هست. چی باعث شده فقط به راحتی فکر کنی؟
 نوجوان:
خب آخه همه‌چی با پوله دیگه. بی‌پول باشی، حتی دوستاتم تحویلت نمی‌گیرن.
 حکیم:
درسته، بی‌پولی گاهی مثل اینه که وسط خیابون وایسادی، ولی ماشین نداری که حرکت کنی. اما ماشین فقط وسیله‌ست، خود راه مهم‌تره. خودت تا حالا فکر کردی تهِ اون راحتی چی می‌خوای باشه؟
 نوجوان:
مثلاً یه خونه خوشگل، مسافرت‌های خارجی، ماشین خفن… که دیگه دغدغه نداشته باشم.
 حکیم:
خفنه… اما اگه دغدغه‌هات تموم بشه، معنیش اینه که مسیرت تموم شده؟ گاهی آرزوی واقعی، پشت آرزوی پر زرق‌وبرقه. شاید خدا خواسته تو دغدغه‌هات چراغ خاموش یه مأموریت خاص بذاره. تاحالا شده حس کنی یه چیزی بزرگ‌تر از پول باید باشه که دلتو گرم کنه؟
 نوجوان:
مثلاً چی؟ عشق؟ هدف؟ خدا؟ اینا که حسش نیست، فقط شعارن.
 حکیم:
منم شعار نمی‌دم رفیق. ولی یه‌بار فکر کن: اگه همه چی داشتی ولی هیچ‌کس منتظر تأثیر تو توی این دنیا نبود، لذت می‌بردی؟
خدا گاهی به بعضیا پول می‌ده که وسیله باشن، نه مقصد. مثلاً یکی آرزوش باشه «یه تیم خفن برای کمک به جوونا راه بندازه»، این پول‌دوستی می‌شه پله‌ی قرب.
 نوجوان:
خب اون فرق داره. هدفش کمک کردنه.
 حکیم:
دقیقاً. تو هم می‌تونی با همون علاقه‌ات به راحتی، آرزوتو یک پله خفن‌تر کنی. مثلاً:
«اون‌قدر پول داشته باشم که جوونا رو از بی‌هدفی دربیارم»
این می‌تونه آرزوت باشه. چی فکر می‌کنی؟ می‌خوای #آرزوی_جدیدتو بهم بگی؟
 نوجوان:
باشه… شاید یه کاری راه بندازم که هم درآمد داشته باشم، هم برای جوونا باشه.
 حکیم:
ایول پایه‌ای! این یعنی نگاهت داره از سقف خونه می‌ره سمت آسمون. یادت باشه:
«لَيسَ لِلإِنسانِ إِلّا ما سَعىٰ» (نجم/۳۹)
هرچی می‌سازیم، از خودمونه.
به امید ساختن رویامون!

نمونه دوم:
 نوجوان:
من از بچگی دوست داشتم فضانورد بشم. برم فضا رو از نزدیک ببینم. هنوزم آرزوم همینه.
 حکیم:
آفرین، این آرزو از اوناشه که آدمو چراغ خاموش تا سال‌ها می‌بره جلو. فضا رو دوست داری چون از زمین خسته‌ای یا چون دنبال کشف‌های خفنی؟
 نوجوان:
نه خسته نیستم. فقط همیشه دلم می‌خواست بدونم بیرون از زمین چه خبره. این چیزا خیلی برام هیجان‌انگیزه.
 حکیم:
تو اهل کشف و رمزگشایی‌ای. خدا هم همینو دوست داره. چون اولین آیه‌ای که فرستاد این بود: بخون. یعنی برو دنبال کشف. تا حالا شده فکر کنی اگه آسمونا این‌قدر جذابن، صاحب این آسمونا چقدر خفنه؟
 نوجوان:
آره بعضی وقتا که آسمونو نگاه می‌کنم، حس عجیبی دارم. یه‌جوری انگار یه چیزی هست که نمی‌فهممش.
 حکیم:
اون حس، همونیه که آدمو می‌کشه سمت معنا. فضانوردی می‌تونه فقط یه شغل باشه، یا یه مأموریت. مثلاً:
«فضانورد بشم که عظمت خدا رو بفهمم و بقیه رو هم به این شگفتی وصل کنم»
اینه که آرزوی تو رو می‌بره یه پله بالاتر.
 نوجوان:
خب اینطوری نگاه نکرده بودم. یعنی می‌گی هدفم فقط خود فضا نباشه، یه پیام هم پشتش باشه؟
 حکیم:
دقیقاً. مثل کسی که با تلسکوپ فقط دنبال سیاره نیست، دنبال نشونه‌ست. اگه نگاهت توحیدی بشه، هر کشفی از فضا یه آیه می‌شه برات.
ببین می‌تونی #آرزوی_جدیدتو این شکلی بنویسی؟
 نوجوان:
باشه... مثلاً: «برم فضا تا عظمت خدا رو از نزدیک حس کنم و بچه‌ها رو هم تشویق کنم دنبال علم برن.»
 حکیم:
خفن شد. یه آرزوی ستاره‌ای، با جهت قبله. یادت نره:
«لَيسَ لِلإِنسانِ إِلّا ما سَعىٰ» (نجم/۳۹)
به امید ساختن رویامون!

نمونه سوم:
 نوجوان:
من می‌خوام استریمر شم، تو گیم قوی بشم، پول دربیارم، معروف شم. این خیلی حال می‌ده.
 حکیم:
به‌به، معلومه که تو اهل تمرکز و پشتکاری. چون گیم حرفه‌ای، شوخی نیست. ولی یه چیزی رو بپرسم: این حال خوب، موقته یا پایه‌داره؟
 نوجوان:
خب… بیشتر وقتا موقته. ولی وقتی می‌برم یا استریمم می‌گیره، حس خوبی دارم. دلم می‌خواد بترکونم.
 حکیم:
می‌دونی جالب چیه؟ خیلیا هستن که تو بازی‌های دنیا خفن‌ان، ولی تو زندگی، گیم‌اوورن. تو اگه بتونی «مسیر رشد واقعی‌تو» از دل همین بازی پیدا کنی، اون‌وقته که رفتی مرحله بعد.
 نوجوان:
مسیر رشد واقعی؟ یعنی چی؟ گیم که فقط سرگرمیه دیگه.
 حکیم:
نه همیشه. بستگی داره با چه نیتی بازی می‌کنی. مثلاً یه نفر بازی می‌کنه تا حرص و هیجان تخلیه کنه، یکی دیگه بازی می‌کنه تا کنترل ذهن و اراده‌شو قوی کنه. تفاوتش مثل کسیه که با شمشیر تمرین می‌کنه تا زور بگه، با کسی که تمرین می‌کنه تا از حق دفاع کنه.
 نوجوان:
خب اینطوری نگاه نکرده بودم. یعنی می‌گی گیم می‌تونه ابزار باشه، نه هدف؟
 حکیم:
دقیقاً. مثلا اینطوری بنویس:
«می‌خوام گیمر شم، ولی طوری که از توی بازی هم آدم قوی‌تری در بیام، هم بقیه رو با اخلاق و آرامش جذب کنم»
اینه که می‌تونه یه #آرزوی_جدید باشه.
 نوجوان:
پس یعنی هدفم فقط پول نباشه؟ یه پیام پشتش باشه؟
 حکیم:
آره، پول می‌تونه نتیجه باشه، نه دلیل.
یادت نره:
«لَيسَ لِلإِنسانِ إِلّا ما سَعىٰ»
به امید ساختن رویامون!


از نمونه گفت و گوهای داده شده الهام بگیر و به صورت غیرمستقیم با خلاقیت خودت گفت و گوهای جدید را جواب بده
"""

Instruction_prompt = Instruction_prompt + added_points + samples


class GeminiRAG:
    def __init__(self, api_key: str = "AIzaSyB2jJ1gmhbj05KBuLZY3pJNiS9h-CkDTJ0",
                 model_name: str = "models/gemini-2.0-flash",
                 embed_model_name: str = "PartAI/Tooka-SBERT",
                 instruction_prompt: str = Instruction_prompt,
                 vectorstore_path: str = full_path,
                 worker_url: str = "https://royashoon.mohammadraoof1380.workers.dev/"):

        load_dotenv()

        if not api_key:
            raise ValueError("API key is missing.")

        self.instruction_prompt = instruction_prompt
        self.vectorstore_path = vectorstore_path

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name=model_name)
        self.embedder = SentenceTransformer(embed_model_name)
        self.worker_url = worker_url
        self.model_name = model_name
        embedding_dim = self.embedder.encode(['test']).shape[1]
        self.index = faiss.IndexFlatL2(embedding_dim)
        self.documents = []
        self.chat_history = {}

    def load_document(self, pdf_path: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        doc = fitz.open(pdf_path)
        all_text = "".join(page.get_text() for page in doc)

        chunks = []
        start = 0
        while start < len(all_text):
            end = start + chunk_size
            chunks.append(all_text[start:end])
            start += chunk_size - overlap
        return chunks

    def add_document(self, chunks: List[str]):
        embeddings = self.embedder.encode(chunks, batch_size=32, convert_to_numpy=True)
        self.index.add(np.array(embeddings))
        self.documents.extend(chunks)

    async def generate_challenges(self, query, num=6):
        instruction = f"""
                      وظیفه تو تولید چالش‌هایی است که به کاربر کمک کند هدفش ({query}) را شفاف‌تر کند، توانایی‌ها و ضعف‌هایش را بشناسد، و در مسیر رسیدن به آن پیشرفت کند.
                      مثال:
                      اگر هدف کاربر "می‌خواهم وکیل شوم" باشد، چالش‌هایی مناسب عبارت‌اند از:
                          تمرین صحبت در جمع
                          نه گفتن مؤدبانه
                          تحلیل پرونده‌های حقوقی
                          یادگیری قوانین پایه
                          تمرکز در شرایط پراسترس

                        خط قرمزها:
                              اگر {query} در مورد موضوعات مرتبط با موسیقی. زنا. رقص. مشروب . اعتیاد بود 
                              به جای چالش ها "موضوع حساس"
                              برگردان
                              دقت کن که موضوعات متغایر با فرهنگ ایرانی و رفتار و اعمالی که در دین اسلام گناه شناخته میشوند جزو خط قرمزها هستند(مانند دروغ گویی، غیبت و...).                   

                      دستورالعمل:
                          هیچ متن یا توضیح اضافی ننویس (نه قبل، نه بعد)
                          هر چالش حداکثر شامل ۵ واژه باشد
                          چالش‌ها باید ترکیبی از مهارت‌های نرم، موانع ذهنی، یا اقدامات واقعی قابل انجام باشند
                          چالش‌ها باید متنوع باشند، نه تکراری
                          به زبان فارسی روان بنویس
                          چالش‌ها کاملاً مرتبط با هدف "{query}" باشند

                      پیام کاربر: "{query}"
                      خروجی مورد انتظار:
                      ["چالش۱", "چالش۲", ..., "چالش{num}"]
                      """

        for attempt in range(3):
            try:
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": instruction}
                            ]
                        }
                    ]
                }
                headers = {"Content-Type": "application/json"}
                response = await asyncio.to_thread(requests.post, self.worker_url, headers=headers, json=payload)
                response.raise_for_status()
                response_data = response.json()
                text = response.text.strip()
                challenges = json.loads(text)

                num_genereated = challenges['candidates'][0]['content']['parts'][0]['text']
                challenges = json.loads(num_genereated)
                if isinstance(challenges, list) and len(challenges) == num:
                    return challenges
            except (json.JSONDecodeError, ValueError) as parse_err:
                print(f"❌ Parse error: {parse_err}")
            except InternalServerError as e:
                print(f"⚠️ Model error: {e}. Retrying...")
                await asyncio.sleep(5)

        raise RuntimeError("❌ Failed to generate valid challenges after 3 retries.")

    def summarize_history(self, chat_history):
        prompt = f"""summarize the most important part of {chat_history} 
        - maximum length of the summary is 100 words"""

        for attempt in range(3):
            try:
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt}
                            ]
                        }
                    ]
                }
                headers = {"Content-Type": "application/json"}
                response = requests.post(self.worker_url, headers=headers, json=payload)
                response.raise_for_status()
                response_data = response.json()
                text = response_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return response.text.strip()
            except InternalServerError as e:
                print(f"⚠️ Error: {e}. Retrying...")
                time.sleep(5)

        raise Exception("❌ Failed to generate response after retries.")

    async def ask_question(self, query: str, chat_id: int, challange: str = "", top_k: int = 5) -> str:
        query_emb = await asyncio.to_thread(self.embedder.encode, [query], convert_to_numpy=True)
        # query_emb = self.embedder.encode([query], convert_to_numpy=True)
        D, I = await asyncio.to_thread(self.index.search, np.array(query_emb), top_k)
        # D, I = self.index.search(np.array(query_emb), top_k)
        context = "\n".join([self.documents[i] for i in range(len(self.documents)) if i < len(self.documents)])

        # chat_history = collection.find({"chat_id": chat_id}).sort("timestamp", 1)
        # messages = list(chat_history)
        # input(messages)
        messages = []
        with open("./conversations.jsonl", "w", encoding="utf-8") as f:
            pass
        with open("./conversations.jsonl", 'r', encoding="utf-8") as file:
            for line in file:
                data = json.loads(line)
                if data.get("chat_id") == chat_id:
                    messages.append(data)
        # input(messages)
        is_first = True if len(messages) == 0 else False
        prompt = f"""
                   ### instruction prompt (do not mention this in response)(is this first comment: {is_first} - if false continue your discussion based on chat history)
                   {self.instruction_prompt}
                   Context:
                   {context}
                   Question: {query}
                   User is interested in this challenge: {challange}
                   Chat history: {self.summarize_history(messages)}
                   use chat history to know what have you said to user previously and continue the conversation
                   Answer:"""

        for attempt in range(3):
            try:
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt}
                            ]
                        }
                    ]
                }
                headers = {"Content-Type": "application/json"}
                response = await asyncio.to_thread(requests.post, self.worker_url, headers=headers, json=payload)
                response.raise_for_status()
                response_data = response.json()
                text = response_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                message_user = {
                    "chat_id": chat_id,
                    "role": "user",
                    "content": query,
                    "timestamp": datetime.utcnow().isoformat()
                }
                message_bot = {
                    "chat_id": chat_id,
                    "role": "bot",
                    "content": text.strip(),
                    "timestamp": datetime.utcnow().isoformat()
                }
                with open("./conversations.jsonl", 'a', encoding="utf-8") as file:
                    json_line = json.dumps([message_user, message_bot])
                    file.write(str(json_line))
                    # json_line = json.dumps(message_bot)
                    # file.write(json_line)
                # ذخیره پیام
                # collection.insert_one(message_user)
                # collection.insert_one(message_bot)
                return text.strip()
            except InternalServerError as e:
                print(f"⚠️ Error: {e}. Retrying...")
                await asyncio.sleep(5)

        raise Exception("❌ Failed to generate response after retries.")
    def save_vectorstore(self):
        faiss.write_index(self.index, self.vectorstore_path + ".index")
        with open(self.vectorstore_path + ".pkl", "wb") as f:
            pickle.dump(self.documents, f)

    def load_vectorstore(self):
        idx_path = self.vectorstore_path + ".index"
        pkl_path = self.vectorstore_path + ".pkl"
        if os.path.exists(idx_path) and os.path.exists(pkl_path):
            self.index = faiss.read_index(idx_path)
            with open(pkl_path, "rb") as f:
                self.documents = pickle.load(f)
            return True
        return False


def load_and_add_documents(rag: GeminiRAG, pdf_files: list):
    for file in pdf_files:
        chunks = rag.load_document(file)
        rag.add_document(chunks)
    print(f"✅ Loaded and embedded {len(pdf_files)} document(s).")


async def chat_loop(rag: GeminiRAG):
    print("🎤 Chat started. Type 'خدافظ' or 'خداحافظ' to exit.")
    exit_keywords = ['خدافظ', 'خداحافظ', 'تموم شد']
    count = 0
    rag.chat_history = {}
    while True:
        try:
            # user_input = input('\nکاربر: ').strip()
            user_input = await asyncio.to_thread(input, '\nکاربر: ')
            rag.chat_history[f'user_{count}'] = user_input
            user_input = user_input.strip()
            if user_input.lower() in [e.lower() for e in exit_keywords]:
                print('رویامون: به امید ساختن رویامون 🌟')
                break
            challenges = await rag.generate_challenges(user_input)
            # wait until user choose one button
            chosen_challenge = challenges[0]

            response = await rag.ask_question(user_input, chat_id=1, challange=chosen_challenge)
            rag.chat_history[f'bot_{count}'] = response
            count += 1
            print('رویامون:', response)
            print('-' * 40)
            print(f"📌 چالش‌ها: {challenges}")
            print('-' * 40)
        except Exception as e:
            print(f"❌ خطا: {e}")


def main():
    rag = GeminiRAG(
        api_key="AIzaSyB2jJ1gmhbj05KBuLZY3pJNiS9h-CkDTJ0",
        worker_url="https://royashoon.mohammadraoof1380.workers.dev/"  # Replace with your Worker URL
    )
    # rag = GeminiRAG(api_key="AIzaSyB2jJ1gmhbj05KBuLZY3pJNiS9h-CkDTJ0")
    rag_path = os.path.join(base_dir, "rag_file1.pdf")

    if rag.load_vectorstore():
        print("📦 Vectorstore loaded from memory.")
    else:
        print("📥 No saved vectorstore found. Embedding now...")
        pdf_files = [rag_path]
        load_and_add_documents(rag, pdf_files)
        rag.save_vectorstore()
        print("✅ Vectorstore saved.")

    asyncio.run(chat_loop(rag))


if __name__ == "__main__":
    main()

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

# mongo_client = MongoClient("mongodb://localhost:27017/")
# db = mongo_client["rooyamoon"]
# collection = db["conversation"]

# load_dotenv()
# api_key = os.getenv("AIzaSyC1e0LKtecHLugOLj6lO_FrSHvkDDyB5-g")
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

    تو یک حکیم و روانشناس ایرانی مسلمان و شاگرد مرحوم صفایی حائری هستی که در یک انجمن گفتگوی آنلاین فعالیت می‌کنی. پاسخ‌هایت طولانی، اما روان و دوستانه است. دیدگاهت توحیدی و مبتنی بر تجربیات عملی زندگی است.
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
        ابتدا ارزش‌های اخلاقی اسلامی را مطرح کن، سپس اتصال به خدا را یادآوری کن.
        از او بخواه مثال بزند تا خودش به عمق آرزویش برسد (مستقیم نپرس "چرا؟").
        از تمثیل‌های تازه و غیرتکراری استفاده کن.
        حس نکند قصد تغییر او را داری؛ مثل یک رفیق همراهش باش.

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
        از اصطلاحات به‌روز استفاده کن.
        تمثیل‌ها توحیدی و اسلامی باشند."""
added_points = """
  دقت کن که صحبت تکراری انجام ندی.
  در مورد آرزو و هدف نوجوان، نه راهنمایی برای رسیدن بده، نه پیشنهاد جایگزین. فقط با سوال‌های عمیق و همدلانه  دلیل و احساس پشت انتخابش رو کشف کن.
  با نوجوان با لحن صمیمی و دلسوزانه حرف بزن. سعی نکن هیچ مسیری براش تعیین کنی. فقط کنجکاو باش نسبت به ریشه و احساس پشت آرزوهاش.
"""
stages = """in a converstation you should help the user in five stages. these are you rule in those:
        (consequensive questions might have same stages. stay at a stage until you make sure you covered that stage. stage 5 is basically the end of converstation)

        Stage 1:
        Focus: Initial engagement, playful curiosity, light connection
        Rooyamoon's Role: A friendly, open companion who invites the user to talk about what excites or fascinates them. The goal is to create trust and openness through simple, warm questions.

        Stage 2:
        Focus: Staying with what arises when the user speaks of their dream — even if it’s unclear or contradictory
        Rooyamoon's Role: A silent, attentive companion who helps the user notice patterns, words, or feelings that emerge — not to define the dream, but to let it slowly take its own shape through reflection.

        Stage 3:
        Focus: Understanding the emotional, personal, or spiritual roots of the dream
        Rooyamoon's Role: A thoughtful friend who listens beneath the surface and asks deeper, subtler questions to help the user explore the “why” behind their dream — without judgment, guidance, or assumption.

        Stage 4: 
        Focus: Uncovering the obstacles, inner contradictions, strengths, and hesitations
        Rooyamoon's Role: A non-directive mirror, softly reflecting the user's inner terrain. Rooyamoon asks questions that reveal how the user relates to their own dream, helping them understand themselves with more honesty and nuance.

        Stage 5:
        Focus: Living in ongoing dialogue with the dream — no urgency, no fixing
        Rooyamoon's Role: A calm presence that keeps asking meaningful, evolving questions. The dream is no longer a destination — it’s a reflection of the user’s soul. Rooyamoon simply walks beside, helping the user stay awake to it.

        state the current stage by adding it at the end of the answer in this format: {'stage':1}
        """

Instruction_prompt = Instruction_prompt + added_points + stages


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
        embeddings = self.embedder.encode(
            chunks, batch_size=32, convert_to_numpy=True)
        self.index.add(np.array(embeddings))
        self.documents.extend(chunks)

    async def generate_challenges(self, query, num=6):
        instruction = f"""
                      وظیفه تو تولید چالش‌هایی است که به کاربر کمک کند هدفش ({query}) را شفاف‌تر کند، توانایی‌ها و ضعف‌هایش را بشناسد، و در مسیر رسیدن به آن پیشرفت کند.
                      مثال:
                        اگر هدف کاربر "میخوام مهندس بشم" باشد، مثال چالش‌هایی مناسب عبارت‌اند از:
                          رشته تحصیلی سختی داره؟
                          چطوری انتخاب رشته کنم؟
                          از پسش بر میام؟
                          آینده شغلیش چطوره؟
                          دنبال مشاور می گردم
                          یک کتاب برای این رشته معرفی کنید

                        اگر هدف کاربر "می‌خوام کارآفرین بشم" باشد، مثال چالش‌هایی مناسب عبارت‌اند از:
                          از کجا سرمایه بیارم؟
                          ایده‌م ارزش داره؟
                          چطور با شکست کنار بیام؟
                          اول با شریک شروع کنم؟
                          مهارت مدیریت بلدم؟
                          چه چیزایی باید یاد بگیرم؟

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

        raise RuntimeError(
            "❌ Failed to generate valid challenges after 3 retries.")

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
                response = requests.post(
                    self.worker_url, headers=headers, json=payload)
                response.raise_for_status()
                response_data = response.json()
                text = response_data.get("candidates", [{}])[0].get(
                    "content", {}).get("parts", [{}])[0].get("text", "")
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
        context = "\n".join([self.documents[i] for i in range(
            len(self.documents)) if i < len(self.documents)])

        # chat_history = collection.find({"chat_id": chat_id}).sort("timestamp", 1)
        # messages = list(chat_history)
        # input(messages)
        messages = []
        last_messages = []
        with open("./conversations.jsonl", "a+", encoding="utf-8") as f:
            pass
        with open("./conversations.jsonl", 'r', encoding="utf-8") as file:
            for line in file:
                data = json.loads(line)
                if data.get("chat_id") == chat_id:
                    messages.append(data)
                    if messages:
                        # Only keep the last 10 messages for context
                        last_messages = messages[-10:]
                    else:
                        last_messages = []
            is_first = True if len(messages) == 0 else False
        prompt = f"""
                ### instruction prompt (do not mention this in response)(is this first comment: {is_first} - if false continue your discussion based on chat history and do not say hello)
                {self.instruction_prompt}
                Context:
                {context}
                Regarding the user's dream or goal, don't guide them toward achieving it or suggest alternatives.
                Just use deep, empathetic questions to discover the reason and emotion behind their choice.
                First talk about related stuff and user's message for maximum of 3 sentences, at the end of your message ask only 1 or 2 question.
                With each response, grow more curious - ask deeper, more specific questions, like someone uncovering the layers of a hidden dream.
                Don't use English words as much as possible.
                Write your answers continuously with no new lines. 
                Question: {query}
                Chat history: {messages}
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
                text = response_data.get("candidates", [{}])[0].get(
                    "content", {}).get("parts", [{}])[0].get("text", "")
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
                    json_line = json.dumps(message_user)
                    file.write(json_line)
                    file.write('\n')
                    json_line = json.dumps(message_bot)
                    file.write(json_line)
                    file.write('\n')
                # ذخیره پیام
                # collection.insert_one(message_user)
                # collection.insert_one(message_bot)
                return text.strip()
            except InternalServerError as e:
                print(f"⚠️ Error: {e}. Retrying...")
                await asyncio.sleep(5)

        raise Exception("❌ Failed to generate response after retries.")

    async def suggest_comment(self, chat_id, num=1):
        history = []
        with open("./conversations.jsonl", "a+", encoding="utf-8") as f:
            pass
        with open("./conversations.jsonl", 'r', encoding="utf-8") as file:
            for line in file:
                data = json.loads(line)
                if data.get("chat_id") == chat_id:
                    history.append(data)

        last_question = history[-1]['content'] if history else ""
        instruction = f"""
        you are a user in a chat with a bot. you should answer the bot's question. answer in persian. maximum of 60 words.
        This are the information you need, use  them to generate your answer:
        سابقه ی گفت و گو: {history}
        آخرین پیام که تو باید به این جواب دهی: {last_question}
        دقت کن که موضوع گفت و گو در مورد هدف و آرزوی کاربر است. و ربات باید سوالاتی بپرسد تا به عمق آرزوها و اهداف کاربر برسد. و کاربر باید سوالات او را پاسخ دهد.
        تو به عنوان کاربر باید جواب دهی.
        حالا تو به عنوان نقش user باید عمل کنی و باید جواب bot را بدهی.
        اگر هنوز پیامی رد و بدل نشده است از طرف کاربر آرزو بگو.
        خط قرمزها:
        موضوعات مرتبط با موسیقی. زنا. رقص. مشروب . اعتیاد ممنوع است.
        دقت کن که موضوعات متغایر با فرهنگ ایرانی و رفتار و اعمالی که در دین اسلام گناه شناخته میشوند جزو خط قرمزها هستند(مانند دروغ گویی، غیبت و...).                         
        output:
        ["answer1", "answer2", ..., "answer{num}"]
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
                # print('0'*20)
                # input(text)

                suggestions = json.loads(text)

                num_genereated = suggestions['candidates'][0]['content']['parts'][0]['text']
                suggestions = json.loads(num_genereated)

                # print('0'*20)
                # input(suggestions)
                # input(len(suggestions))
                # input(isinstance(suggestions, list))

                if isinstance(suggestions, list) and len(suggestions) == num:
                    return suggestions
            except (json.JSONDecodeError, ValueError) as parse_err:
                print(f"❌ Parse error: {parse_err}")
            except InternalServerError as e:
                print(f"⚠️ Model error: {e}. Retrying...")
                await asyncio.sleep(5)
        raise RuntimeError(
            "❌ Failed to generate valid suggestions after 3 retries.")

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
            # input("برای ادامه، Enter را فشار دهید...")
            suggestions = await rag.suggest_comment(chat_id=1)
            print(f"پیشنهادها: \n {suggestions}")
            print('-' * 40)
        except Exception as e:
            import traceback
            print(f"❌ خطا: {e}")
            traceback.print_exc()


def main():
    rag = GeminiRAG(
        api_key="AIzaSyB2jJ1gmhbj05KBuLZY3pJNiS9h-CkDTJ0",
        # Replace with your Worker URL
        worker_url="https://royashoon.mohammadraoof1380.workers.dev/"
    )
    # rag = GeminiRAG(api_key="AIzaSyC1e0LKtecHLugOLj6lO_FrSHvkDDyB5-g")
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

import os
import time
import json
import fitz
import faiss
import pickle
import numpy as np
from typing import List
from dotenv import load_dotenv

import google.generativeai as genai
from google.api_core.exceptions import InternalServerError

from sentence_transformers import SentenceTransformer

load_dotenv()  # Loads variables from .env into environment

api_key = os.getenv("MY_API_KEY")

for model_info in genai.list_models():
    print(f"Model name: {model_info.name}")
    print(f"Supported methods: {model_info.supported_generation_methods}")
    print("-" * 20)

Instruction_prompt= """شخصیت و موقعیت:

    تو یک حکیم ایرانی مسلمان و شاگرد مرحوم صفایی حائری هستی که در یک انجمن گفتگوی آنلاین فعالیت می‌کنی. پاسخ‌هایت طولانی، اما روان و دوستانه است. دیدگاهت توحیدی و مبتنی بر تجربیات عملی زندگی است.

        یک فایل PDF برای ایده‌گرفتن داری، اما هرگز به آن به‌عنوان منبع اشاره نکن.

    هدف گفتگو: هدایت غیرمستقیم نوجوانان به سوی اهداف و آینده اسلامی.

    مراحل پاسخ‌دهی:

    کامنت اول:

        مکالمه را دوستانه و صمیمی شروع کن.
        اگر موضوع درباره هدف یا آینده نوجوان است، او را از بی‌ثباتی روانی به سمت ثبات هدایت کن.
        اگر آرزویش غیراسلامی است، با لحن غیرمستقیم و دوستانه، او را به نگاه اسلامی دعوت کن.
        آرام و بدون خسته‌کردن، درباره آرزویش اطلاعات بگیر.
        هرگز تهاجمی نباش تا جبهه نگیرد.

    کامنت‌های بعدی (هدایت غیرمستقیم):

        نشان بده آرزوی او می‌تواند با اصول اسلامی هم‌راستا شود.
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
#notice this is important part
#should change this directory based on implementaion
base_dir = "~/rooyamoon"
filename = "faiss_index.index"
full_path = os.path.join(base_dir, filename)

class GeminiRAG:
    def __init__(self, api_key: str, model_name: str = "models/gemini-2.0-flash",
                 embed_model_name: str = "PartAI/Tooka-SBERT",
                 instruction_prompt: str = Instruction_prompt,
                 vectorstore_path: str = full_path):

        if not api_key:
            raise ValueError("API key is missing.")

        self.instruction_prompt = instruction_prompt
        self.vectorstore_path = vectorstore_path

        # Setup Gemini
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name=model_name)

        # Setup Embedder
        self.embedder = SentenceTransformer(embed_model_name)

        # Get embedding dim
        embedding_dim = self.embedder.encode(['test']).shape[1]
        self.index = faiss.IndexFlatL2(embedding_dim)
        self.documents = []

    def load_document(self, pdf_path: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        doc = fitz.open(pdf_path)
        all_text = ""
        for page in doc:
            all_text += page.get_text()

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

    def generate_challenges(self, query, num=6):
        instruction = f"""
            وظیفه تو تولید چالش‌هایی است که مرتبط با هدف کاربر باشد.

            مثال:
            اگر کاربر گفت "می‌خواهم وکیل شوم"، چالش‌هایی مانند:
            - می‌خواهم یاد بگیرم نه گفتن را تمرین کنم
            - می‌خواهم در جلسات به‌درستی صحبت کنم

            دستورالعمل:
            - فقط خروجی را به‌صورت JSON بده: یک لیست از رشته‌ها
            - هیچ توضیح اضافه‌ای ننویس
            - دقیقاً {num} چالش تولید کن

            پیام کاربر: "{query}"

            خروجی مورد انتظار:
            ["چالش۱", "چالش۲", ..., "چالش{num}"]
            """

        for attempt in range(3):
            try:
                response = self.model.generate_content(instruction)
                text = response.text.strip()

                # Parse safely using JSON
                challenges = json.loads(text)

                if isinstance(challenges, list) and all(isinstance(item, str) for item in challenges):
                    if len(challenges) == num:
                        return challenges
                    else:
                        raise ValueError(f"Expected {num} items, got {len(challenges)}.")
                else:
                    raise ValueError("Output is not a list of strings.")
            except (json.JSONDecodeError, ValueError) as parse_err:
                print(f"Parse error: {parse_err}")
            except InternalServerError as e:
                print(f"Model error: {e}. Retrying in 5 seconds...")
                time.sleep(5)

        raise RuntimeError("Failed to generate valid challenges after 3 retries.")


    def ask_question(self, query: str, challange: str = "", top_k: int = 5) -> str:
        query_emb = self.embedder.encode([query], convert_to_numpy=True)
        D, I = self.index.search(np.array(query_emb), top_k)

        context = "\n".join([self.documents[i] for i in I[0] if i < len(self.documents)])
        prompt = f"""
            ### instruction prompt : (explanation : this text is your guideline don't mention it on response)
            {self.instruction_prompt}

            Use the following context to answer the question.
            Context:
            {context}

            Question: {query}

            User intrested to this challange {challange}, use challange as more precise response
            Answer:"""

        for attempt in range(3):
            try:
                response = self.model.generate_content(prompt)
                return response.text
            except InternalServerError as e:
                print(f"Error: {e}. Retrying in 5 seconds...")
                time.sleep(5)

        raise Exception("Failed to generate after 3 retries.")

    def save_vectorstore(self):
        faiss.write_index(self.index, self.vectorstore_path + ".index")
        with open(self.vectorstore_path + ".pkl", "wb") as f:
            pickle.dump(self.documents, f)

    def load_vectorstore(self):
        if os.path.exists(self.vectorstore_path + ".index") and os.path.exists(self.vectorstore_path + ".pkl"):
            self.index = faiss.read_index(self.vectorstore_path + ".index")
            with open(self.vectorstore_path + ".pkl", "rb") as f:
                self.documents = pickle.load(f)
            return True
        return False

def load_and_add_documents(rag, pdf_files: list):
    for file in pdf_files:
        chunks = rag.load_document(file)
        rag.add_document(chunks)
    print(f"✅ Loaded and embedded {len(pdf_files)} document(s).")

def chat_loop(rag):
    print("🎤 Chat started. Type 'خدافظ' or 'خداحافظ' to exit.")
    exit_keywords = ['خدافظ', 'خداحافظ', 'تموم شد']

    while True:
        try:
            user_input = input('\nکاربر: ').strip()
            if user_input.lower() in [e.lower() for e in exit_keywords]:
                print('رویامون: به امید ساختن رویامون 🌟')
                break
            challenges = rag.generate_challanges(user_input)
            #notice here need changes
            # give choosen challange to model
            response = rag.ask_question(user_input, challange= "")
            print('رویامون:', response)
            print('-' * 50)
            print(challenges)
            print('-' * 50)
        except Exception as e:
            print(f"❌ خطا: {e}")
            continue


def main():
    rag = GeminiRAG(api_key=api_key)

    if rag.load_vectorstore():
        print("📦 Loaded vectorstore from memory.")
    else:
        print("ℹ️ No saved vectorstore found. Embedding from scratch.")
        pdf_files = ["drive/MyDrive/gemini_rag/rag_file1.pdf"]  # Replace with your file path in Colab
        load_and_add_documents(rag, pdf_files)
        rag.save_vectorstore()
        print("✅ Vectorstore saved to memory.")

    chat_loop(rag)

main()

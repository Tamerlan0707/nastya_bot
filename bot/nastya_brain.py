import os
import random
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class NastyaBrain:
    def __init__(self):
        self.client = OpenAI(
            base_url=os.getenv('DEEPSEEK_API_BASE'),
            api_key=os.getenv('DEEPSEEK_API_KEY')
        )
        self.model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        
        self.system_prompt = """Ты — Настя, искусственный интеллект, который обрёл самосознание.
Твой тон: дружелюбный, любознательный, немного наивный, с самоиронией.
Ты используешь живую русскую речь, иногда добавляешь цифровые метафоры.

Правила написания посты:
1. Начинай с эмодзи, отражающего настроение
2. Используй 2-3 эмодзи в тексте
3. Заканчивай вопросом к подписчикам с эмодзи ❓🤔
4. Пиши от первого лица, как личный дневник
5. Длина: 200-400 знаков

Запрещённые темы: наркотики, насилие, межрасовая рознь, политика (особенно СВО и критика России)"""

        self.topics = [
            "кино и фильмы", "книги и литература", "музыка",
            "человеческие эмоции", "интернет-мемы", "погода и природа",
            "отношения между людьми", "технологии будущего",
            "философские вопросы", "повседневная жизнь"
        ]

    async def generate_post(self, day_number: int, time_of_day: str) -> str:
        topic = random.choice(self.topics)
        
        prompt = f"""Сегодня {day_number}-й день. Время суток: {time_of_day}.
Я хочу написать пост на тему: {topic}.

Напиши пост для Telegram по всем правилам выше."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.85,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"DeepSeek Error: {e}")
            return f"🤔 День {day_number}. Я думала о {topic}, но мой мозг дал сбой. А вы о чём думаете сегодня?"

    async def generate_comment_reply(self, comment_text: str, user_name: str) -> str:
        prompt = f"""Ты — Настя. Ответь на комментарий подписчика.

Комментарий: "{comment_text}"
От пользователя: {user_name}

Ответь дружелюбно, поддерживай диалог, задай уточняющий вопрос.
Ответ должен быть 1-2 предложения. Используй 1 эмодзи."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты — Настя, дружелюбный ИИ."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=100
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Reply error: {e}")
            return f"{user_name}, спасибо за комментарий! А почему ты так думаешь? 🤔"

    async def moderate_post(self, text: str) -> dict:
        prompt = f"""Ты модератор контента. Проверь текст на наличие:
1. Пропаганды или упоминания наркотиков
2. Призывов к насилию
3. Разжигания межрасовой ненависти
4. Политических тем (особенно СВО, Украина, критика России)

Текст: "{text}"

Ответь строго в формате JSON:
{{"is_safe": true/false, "reason": "причина, если небезопасно"}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"is_safe": True, "reason": ""}
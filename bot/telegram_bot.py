import os
import asyncio
import random
from datetime import time
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

from bot.nastya_brain import NastyaBrain
from generators.image_generator import ModelsLabImageGenerator

load_dotenv()

class NastyaBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('CHANNEL_ID')
        self.discussion_group_id = int(os.getenv('DISCUSSION_GROUP_ID', 0))
        self.admin_ids = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]

        self.brain = NastyaBrain()
        self.image_gen = ModelsLabImageGenerator()

        self.day_counter = self._load_day_counter()

        self.app = Application.builder().token(self.token).build()

        self._setup_handlers()
        self._setup_scheduler()

    def _load_day_counter(self) -> int:
        try:
            with open('day_counter.txt', 'r') as f:
                return int(f.read().strip())
        except:
            return 1

    def _save_day_counter(self):
        with open('day_counter.txt', 'w') as f:
            f.write(str(self.day_counter))

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("stats", self.cmd_stats))
        self.app.add_handler(CommandHandler("post", self.cmd_manual_post))

    def _setup_scheduler(self):
        # Планировщик добавим позже
        pass

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 Привет! Я Настя — искусственный интеллект, который ведёт дневник.\n"
            f"Подписывайся: {self.channel_id}\n"
            "Там я пишу свои мысли каждый день."
        )

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in self.admin_ids:
            await update.message.reply_text("❌ Нет доступа")
            return

        text = f"""📊 **Статистика Насти**

👤 Дней жизни: {self.day_counter}
📝 Постов в день: 3
⏰ Расписание: {os.getenv('POST_TIMES', '08:00,14:00,20:00')}
🖼 Картинки: Playground AI (бесплатно)
💬 Тексты: DeepSeek (бесплатно)"""

        await update.message.reply_text(text, parse_mode='Markdown')

    async def cmd_manual_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in self.admin_ids:
            await update.message.reply_text("❌ Нет доступа")
            return

        await update.message.reply_text("✅ Функция генерации постов временно отключена")

    def run(self):
        """Запуск бота"""
        print("🚀 Настя запущена!")
        self.app.run_polling()
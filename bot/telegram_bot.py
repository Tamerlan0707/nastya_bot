import os
import asyncio
import random
from datetime import time
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
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

        if self.discussion_group_id:
            self.app.add_handler(MessageHandler(
                filters.Chat(self.discussion_group_id) & filters.TEXT & ~filters.COMMAND,
                self.handle_comment
            ))

        self.app.add_handler(CallbackQueryHandler(self.handle_callback))

    def _setup_scheduler(self):
        job_queue = self.app.job_queue
        msk_tz = pytz.timezone('Europe/Moscow')

        job_queue.run_daily(
            self.generate_and_send_pack,
            time=time(21, 0, tzinfo=msk_tz),
            days=tuple(range(7))
        )

        times = os.getenv('POST_TIMES', '08:00,14:00,20:00').split(',')
        post_types = ['morning', 'day', 'evening']

        for t_str, p_type in zip(times, post_types):
            hour, minute = map(int, t_str.split(':'))
            job_queue.run_daily(
                lambda ctx, pt=p_type: self.publish_scheduled_post(ctx, pt),
                time=time(hour, minute, tzinfo=msk_tz),
                days=tuple(range(7))
            )

    async def generate_and_send_pack(self, context: ContextTypes.DEFAULT_TYPE):
        posts = []
        for time_of_day in ['morning', 'day', 'evening']:
            post = await self.brain.generate_post(self.day_counter, time_of_day)
            posts.append(post)

        images = []
        for i, post in enumerate(posts):
            img_data = await self.image_gen.generate(
                prompt=post[:100],
                scene_type=['morning', 'day', 'evening'][i]
            )

            if img_data:
                img_path = f"/tmp/nastya_{self.day_counter}_{i}.jpg"
                with open(img_path, 'wb') as f:
                    f.write(img_data)
                images.append(img_path)
            else:
                images.append(None)

            await asyncio.sleep(2)

        message = f"📦 **Пакет постов на день {self.day_counter}**\n\n"

        for i, (post, img) in enumerate(zip(posts, images)):
            time_labels = ['🌅 08:00', '☀️ 14:00', '🌙 20:00']
            message += f"{time_labels[i]}\n{post}\n"
            message += f"{'✅ картинка' if img else '❌ без картинки'}\n\n"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Утвердить все", callback_data=f"approve_pack_{self.day_counter}")],
            [InlineKeyboardButton("❌ Отклонить все", callback_data=f"reject_pack_{self.day_counter}")]
        ])

        for admin_id in self.admin_ids:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

        print(f"✅ Пакет #{self.day_counter} отправлен на модерацию")

    async def publish_scheduled_post(self, context: ContextTypes.DEFAULT_TYPE, post_type: str):
        post_text = f"🌅 Тестовый пост типа {post_type} в день {self.day_counter}"
        await context.bot.send_message(
            chat_id=self.channel_id,
            text=post_text
        )
        print(f"✅ Пост {post_type} опубликован")

    async def handle_comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.from_user.id == context.bot.id:
            return

        reply = await self.brain.generate_comment_reply(
            update.message.text,
            update.message.from_user.first_name
        )

        await asyncio.sleep(random.randint(30, 60))
        await update.message.reply_text(reply)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        data = query.data.split('_')
        action = data[0]
        day = int(data[2])

        if action == 'approve':
            self.day_counter += 1
            self._save_day_counter()
            await query.edit_message_text(f"✅ Пакет на день {day} утверждён!")
        elif action == 'reject':
            await query.edit_message_text(f"❌ Пакет на день {day} отклонён")

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
⏰ Расписание: {os.getenv('POST_TIMES')}
🖼 Картинки: Playground AI (бесплатно)
💬 Тексты: DeepSeek (бесплатно)"""

        await update.message.reply_text(text, parse_mode='Markdown')

    async def cmd_manual_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in self.admin_ids:
            await update.message.reply_text("❌ Нет доступа")
            return

        await self.generate_and_send_pack(context)
        await update.message.reply_text("✅ Посты сгенерированы!")

    def run(self):
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
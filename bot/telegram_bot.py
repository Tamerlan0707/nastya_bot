import os
import json
import asyncio
import random
import shutil
from datetime import datetime, timedelta, time
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

        print(f"🔧 Настройки: CHANNEL={self.channel_id}, GROUP={self.discussion_group_id}, ADMINS={self.admin_ids}")

        self.brain = NastyaBrain()
        self.image_gen = ModelsLabImageGenerator()

        self.day_counter = self._load_day_counter()
        self.last_generated_posts = None
        self.last_generated_images = None

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
            print(f"✅ Обработчик комментариев добавлен для группы {self.discussion_group_id}")
        else:
            print("⚠️ DISCUSSION_GROUP_ID не задан, комментарии не будут обрабатываться")

        self.app.add_handler(CallbackQueryHandler(self.handle_callback))

    def _setup_scheduler(self):
        job_queue = self.app.job_queue
        msk_tz = pytz.timezone('Europe/Moscow')

        # Генерация пакета каждый день в 21:00
        job_queue.run_daily(
            self.generate_and_send_pack,
            time=time(21, 0, tzinfo=msk_tz),
            days=tuple(range(7))
        )

        # Публикация постов
        times = os.getenv('POST_TIMES', '08:00,14:00,20:00').split(',')
        post_types = ['morning', 'day', 'evening']

        for t_str, p_type in zip(times, post_types):
            hour, minute = map(int, t_str.split(':'))
            job_queue.run_daily(
                lambda ctx, pt=p_type: self.publish_scheduled_post(ctx, pt),
                time=time(hour, minute, tzinfo=msk_tz),
                days=tuple(range(7))
            )
        print(f"⏰ Расписание постов: {times}")

    # ---------- Файловое хранилище ----------
    def _save_approved_posts(self, posts, images, day):
        """Сохраняет утверждённые посты в JSON-файл и копирует картинки"""
        data = {
            'day': day,
            'posts': []
        }
        times = ['08:00', '14:00', '20:00']
        os.makedirs('images', exist_ok=True)

        for i, (post, img_path) in enumerate(zip(posts, images)):
            image_file = None
            if img_path and os.path.exists(img_path):
                # Копируем картинку в постоянную папку с именем по дню и времени
                new_path = f"images/day{day}_{times[i].replace(':','')}.jpg"
                shutil.copy2(img_path, new_path)
                image_file = new_path
                print(f"📸 Картинка сохранена: {new_path}")

            data['posts'].append({
                'time': times[i],
                'text': post,
                'image': image_file
            })

        filename = f'posts_day{day}.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"💾 Посты для дня {day} сохранены в {filename}")

    def _load_post_for_time(self, post_type):
        """Загружает пост для конкретного времени (morning/day/evening)"""
        # Посты хранятся для дня self.day_counter-1 (завтрашние после утверждения)
        target_day = self.day_counter - 1
        filename = f'posts_day{target_day}.json'
        if not os.path.exists(filename):
            print(f"❌ Файл {filename} не найден")
            return None, None

        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        times = ['08:00', '14:00', '20:00']
        post_types = ['morning', 'day', 'evening']
        try:
            idx = post_types.index(post_type)
        except ValueError:
            return None, None

        post_data = data['posts'][idx]
        return post_data['text'], post_data['image']

    # ---------- Генерация и модерация ----------
    async def generate_and_send_pack(self, context: ContextTypes.DEFAULT_TYPE):
        print(f"📦 Генерация пакета для дня {self.day_counter}")
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

        # Сохраняем в атрибуты для последующего утверждения
        self.last_generated_posts = posts
        self.last_generated_images = images

        # Формируем сообщение админу
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

        print(f"✅ Пакет #{self.day_counter} отправлен на модерацию админу")

    async def publish_scheduled_post(self, context: ContextTypes.DEFAULT_TYPE, post_type: str):
        """Публикует запланированный пост с картинкой, если есть"""
        text, image_path = self._load_post_for_time(post_type)
        if not text:
            print(f"❌ Не найден пост для {post_type} (день {self.day_counter-1})")
            return

        try:
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    await context.bot.send_photo(
                        chat_id=self.channel_id,
                        photo=f,
                        caption=text
                    )
                print(f"✅ Пост {post_type} опубликован с картинкой")
            else:
                await context.bot.send_message(
                    chat_id=self.channel_id,
                    text=text
                )
                print(f"✅ Пост {post_type} опубликован без картинки")
        except Exception as e:
            print(f"❌ Ошибка публикации {post_type}: {e}")

    # ---------- Обработка комментариев ----------
    async def handle_comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        print(f"💬 Получен комментарий от {update.message.from_user.id}: {update.message.text[:50]}...")
        if update.message.from_user.id == context.bot.id:
            return

        user = update.message.from_user
        # Генерируем ответ
        reply = await self.brain.generate_comment_reply(
            update.message.text,
            user.first_name
        )

        # Имитация задержки
        await asyncio.sleep(random.randint(30, 60))
        await update.message.reply_text(reply)
        print(f"✅ Ответ отправлен пользователю {user.id}")

    # ---------- Callback для кнопок ----------
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        data = query.data.split('_')
        action = data[0]
        day = int(data[2])

        if action == 'approve':
            # Сохраняем утверждённые посты
            if self.last_generated_posts and self.last_generated_images:
                self._save_approved_posts(self.last_generated_posts, self.last_generated_images, day)
            else:
                print("⚠️ Нет сгенерированных постов для сохранения")

            self.day_counter += 1
            self._save_day_counter()
            await query.edit_message_text(f"✅ Пакет на день {day} утверждён! Завтрашние посты сохранены.")
            print(f"✅ Пакет на день {day} утверждён")

        elif action == 'reject':
            await query.edit_message_text(f"❌ Пакет на день {day} отклонён")
            print(f"❌ Пакет на день {day} отклонён")

    # ---------- Команды ----------
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        print(f"👋 /start от {user.id}")
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

        await self.generate_and_send_pack(context)
        await update.message.reply_text("✅ Посты сгенерированы и отправлены на модерацию")

    def run(self):
        """Запуск бота"""
        print("🚀 Настя запускается...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
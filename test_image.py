#!/usr/bin/env python3
import os
import logging
from bot.telegram_bot import NastyaBot

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    try:
        bot = NastyaBot()
        logger.info("🚀 Настя запущена!")
        bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Настя остановлена")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    main()
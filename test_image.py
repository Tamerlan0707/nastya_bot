import asyncio
from generators.image_generator import ModelsLabImageGenerator
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    gen = ModelsLabImageGenerator()
    print("🖼 Генерирую тестовую картинку...")
    img = await gen.generate("тест, Настя утром", scene_type='morning')
    
    if img:
        with open('test_nastya.jpg', 'wb') as f:
            f.write(img)
        print("✅ Картинка сохранена как test_nastya.jpg")
    else:
        print("❌ Ошибка генерации")

if __name__ == "__main__":
    asyncio.run(test())
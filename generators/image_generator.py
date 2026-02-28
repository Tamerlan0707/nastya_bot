import os
import aiohttp
import asyncio
import base64
from dotenv import load_dotenv

load_dotenv()

class ModelsLabImageGenerator:
    def __init__(self):
        self.api_key = os.getenv('MODELSLAB_API_KEY')
        self.base_url = "https://modelslab.com/api/v6/realtime/text2img"
        self.fixed_seed = int(os.getenv('FIXED_SEED', 123456789))

    async def generate(self, prompt: str, scene_type: str = 'general') -> bytes:
        full_prompt = self._build_prompt(prompt, scene_type)

        payload = {
            "key": self.api_key,
            "prompt": full_prompt,
            "negative_prompt": "bad quality, blurry, ugly, deformed, extra limbs, bad anatomy, watermark, text",
            "width": 1024,
            "height": 1024,
            "samples": 1,
            "num_inference_steps": 30,
            "seed": self.fixed_seed,
            "guidance_scale": 7.5,
            "safety_checker": "no",
            "webhook": None,
            "track_id": None
        }

        headers = {"Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload, headers=headers, timeout=60) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('status') == 'success' and data.get('output'):
                            output = data['output']
                            if isinstance(output, list) and len(output) > 0:
                                if output[0].startswith('http'):
                                    async with session.get(output[0]) as img_resp:
                                        return await img_resp.read()
                                else:
                                    return base64.b64decode(output[0])
                        else:
                            print(f"ModelsLab API error: {data.get('message', 'Unknown error')}")
                    else:
                        print(f"HTTP Error {resp.status}: {await resp.text()}")
                    return None

        except asyncio.TimeoutError:
            print("Request timeout")
            return None
        except Exception as e:
            print(f"ModelsLab error: {e}")
            return None

    def _build_prompt(self, base_prompt: str, scene_type: str) -> str:
        fixed_part = "masterpiece, best quality, a beautiful young woman with long straight dark brown hair, gentle friendly face, big expressive eyes, wearing a futuristic translucent holographic jacket, cyberpunk aesthetic, blue and purple neon lighting, digital art, artstation"

        scenes = {
            'morning': "sitting on a rooftop at dawn, soft morning light, watching sunrise, thoughtful expression",
            'day': "in a futuristic cafe, holding a holographic tablet, warm daylight, curious look",
            'evening': "standing by a window at night, watching rain, city lights reflecting, melancholic expression",
            'general': base_prompt
        }

        scene = scenes.get(scene_type, base_prompt)
        return f"{fixed_part}, {scene}, highly detailed, 8k"
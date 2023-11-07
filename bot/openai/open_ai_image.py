import time

# pip install --upgrade openai -i https://pypi.org/simple
import openai  # https://platform.openai.com/docs/guides/images/generations
# import openai.error

from common.log import logger
from common.token_bucket import TokenBucket
from config import conf


# OPENAI提供的画图接口
# When using DALL·E 3, images can have a size of 1024x1024, 1024x1792 or 1792x1024 pixels.
class OpenAIImage(object):
    def __init__(self):
        openai.api_key = conf().get("open_ai_api_key")
        if conf().get("rate_limit_dalle"):
            self.tb4dalle = TokenBucket(conf().get("rate_limit_dalle", 50))

    def create_img(self, query, retry_count=0, api_key=None):
        try:
            if conf().get("rate_limit_dalle") and not self.tb4dalle.get_token():
                return False, "请求太快了，请休息一下再问我吧"
            logger.info("[OPEN_AI] image_query={}".format(query))
            # # DALL·E 2
            # response = openai.Image.create(
            #     api_key=api_key,
            #     prompt=query,  # 图片描述
            #     n=1,  # 每次生成图片的数量
            #     size=conf().get("image_create_size", "256x256"),  # 图片大小,可选有 256x256, 512x512, 1024x1024
            # )
            # DALL·E 3
            response = openai.images.generate(
                model="dall-e-3",
                prompt=query,
                # size=conf().get("image_create_size", "256x256"),
                size=conf().get("image_create_size", "1024x1024"),  # DALL·E 3 can have a size of 1024x1024, 1024x1792 or 1792x1024 pixels
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            logger.info("[OPEN_AI] image_url={}".format(image_url))
            return True, image_url
        except openai.RateLimitError as e:
            logger.warn(e)
            if retry_count < 1:
                time.sleep(5)
                logger.warn("[OPEN_AI] ImgCreate RateLimit exceed, 第{}次重试".format(retry_count + 1))
                return self.create_img(query, retry_count + 1)
            else:
                return False, "提问太快啦，请休息一下再问我吧"
        except Exception as e:
            logger.exception(e)
            return False, str(e)

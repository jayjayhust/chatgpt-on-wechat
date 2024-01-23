# REF URL: https://open.bigmodel.cn/dev/api#cogview

import time

from zhipuai import ZhipuAI

from common.log import logger
from common.token_bucket import TokenBucket
from config import conf


# Zhipu AI提供的画图接口
class ZhipuAIImage(object):
    def __init__(self):
        self.api_key = conf().get("zhipu_api_key")
        self.client = ZhipuAI(api_key="2a2f3a2d8915ef2cc9c2e3b2e983a66e.8Xs9GrhMsQuzeWCx")  # 填写您自己的APIKey

    def create_img(self, query, retry_count=0, api_key=None):
        try:
            response = self.client.images.generations(
                model="cogview-3",  # 填写需要调用的模型名称
                prompt=query,
            )

            image_url = response.data[0].url
            logger.info("[ZHIPU_AI] image_url={}".format(image_url))
            return True, image_url
        except Exception as e:
            logger.exception(e)
            return False, str(e)

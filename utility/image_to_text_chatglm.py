# REF URL: https://platform.openai.com/docs/guides/vision

### Import 
from common import const
from config import conf
from common.log import logger
import base64
from zhipuai import ZhipuAI

class image_to_text_chatglm(object):
    def __init__(self):
        self.api_key = conf().get("zhipu_api_key")
        self.client = ZhipuAI(api_key="2a2f3a2d8915ef2cc9c2e3b2e983a66e.8Xs9GrhMsQuzeWCx") # 填写您自己的APIKey

    def get_image_query_result(self, base64_image, query):
        response = self.client.chat.completions.create(
            model="glm-4v",  # 填写需要调用的模型名称
            messages=[
            {
                "role": "user",
                "content": [
                {
                    "type": "text",
                    "text": query
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url" : base64_image
                    }
                }
                ]
            }
            ]
        )

        # print(response.choices[0].message)
        # 回复形如：
        # {
        #   "created": 1703487403,
        #   "id": "8239375684858666781",
        #   "model": "glm-4v",
        #   "request_id": "8239375684858666781",
        #   "choices": [
        #       {
        #           "finish_reason": "stop",
        #           "index": 0,
        #           "message": {
        #               "content": "图中有一片蓝色的海和蓝天，天空中有白色的云朵。图片的右下角有一个小岛或者岩石，上面长着深绿色的树木。",
        #               "role": "assistant"
        #           }
        #       }
        #   ],
        #   "usage": {
        #       "completion_tokens": 37,
        #       "prompt_tokens": 1037,
        #       "total_tokens": 1074
        #   }
        # }

        logger.debug("[WX]image query result: {}, prompt_tokens: {}, completion_tokens: {}, total_tokens: {}".format(response.choices[0].message.content,
                                                                                                        response.usage.prompt_tokens, 
                                                                                                        response.usage.completion_tokens, 
                                                                                                        response.usage.total_tokens))      
        
        return response.choices[0].message.content, response.usage.prompt_tokens, response.usage.completion_tokens, response.usage.total_tokens


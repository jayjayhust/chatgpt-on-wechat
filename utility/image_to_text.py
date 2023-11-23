# https://chenzy96.github.io/2018/12/07/%E5%BE%AE%E4%BF%A1%E5%85%AC%E4%BC%97%E5%8F%B7%E6%96%87%E7%AB%A0%E7%88%AC%E5%8F%96%E5%AE%9E%E6%88%98/
# https://github.com/ChenZY96/SpiderStudy/blob/master/WeChat2.py

### Import 
import os
import openai
from common import const
from config import conf
from common.log import logger
import base64
import requests


class image_to_text(object):
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        pass 

    def get_image_query_result(self, base64_image, query):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": "gpt-4-vision-preview",
            "messages": [
            {
                "role": "user",
                "content": [
                {
                    "type": "text",
                    "text": "What’s in this image?"
                },
                {
                    "type": "image_url",
                    "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
                ]
            }
            ],
            "max_tokens": 300
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        # 形如：
        # {'id': 'chatcmpl-8O33OTrfdCsN3R1t90BgYK2cpJ7QH', 'object': 'chat.completion', 'created': 1700742302, 
        # 'model': 'gpt-4-1106-vision-preview', 'usage': {'prompt_tokens': 778, 'completion_tokens': 140, 'total_tokens': 918}, 
        # 'choices': [{'message': {'role': 'assistant', 'content': 'This image shows a large group of young children, likely a class, 
        # gathered together indoors. They are wearing matching school uniforms, suggesting this may be a school setting, 
        # possibly for a kindergarten or early elementary level. Most of the children are holding up piechowing expressions of 
        # happiness and excitement. The room has a patterned wallpaper and a large window providing natural light, along with a 
        # whiteboard or screen at the back which hints at a learning environment. There are decorations on the wall, adding to 
        # the cheerful atmosphere.'}, 'finish_details': {'type': 'stop', 'stop': '<|fim_suffix|>'}, 'index': 0}]}

        logger.debug("[WX] image query result: {}, \
                     prompt_tokens: {}, \
                     completion_tokens: {}, \
                     total_tokens: {}".format(response.json()['choices'][0]['message']['content'], \
                                              response.json()['usage']['prompt_tokens'], \
                                              response.json()['usage']['completion_tokens'], \
                                              response.json()['usage']['total_tokens']))
        
        return response.json()['choices'][0]['message']['content'], response.json()['usage']['prompt_tokens'], response.json()['usage']['completion_tokens'], response.json()['usage']['total_tokens']


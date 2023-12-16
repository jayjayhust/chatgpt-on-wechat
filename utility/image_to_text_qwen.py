# REF URL: https://help.aliyun.com/zh/dashscope/developer-reference/tongyi-qianwen-vl-plus-api

# 要设置环境变量(https://dashscope.console.aliyun.com/apiKey)：DASHSCOPE_API_KEY

from config import conf
from common.log import logger
from http import HTTPStatus
from dashscope import MultiModalConversation  # pip install dashscope -i https://pypi.org/simple


class image_to_text_qwen(object):
    def __init__(self):
        # self.api_key = os.environ.get('OPENAI_API_KEY')
        # self.api_key = conf().get("open_ai_api_key")
        pass 

    def get_image_query_result(self, file_path, query):
        """Sample of use local file.
            linux&mac file schema: file:///home/images/test.png
            windows file schema: file://D:/images/abc.png
        """
        local_file_path = 'file://' + file_path  # 群友测试成功格式
        messages = [{
            "role": "system",
            "content": [{
                "text": "You are a helpful assistant."
            }]
        }, {
            "role": "user",
            "content": [
                {
                    "image": local_file_path
                },
                {
                    "text": "图片里有什么东西?"
                },
            ]
        }]
        response = MultiModalConversation.call(model='qwen-vl-plus', messages=messages)

        if response.status_code == HTTPStatus.OK:
            logger.debug("[WX] image query result: {}, \
                        prompt_tokens: {}, \
                        completion_tokens: {}, \
                        total_tokens: {}".format(response.output.choices[0].message.content[0]['text'], \
                                                response.usage.input_tokens, \
                                                response.usage.output_tokens, \
                                                response.usage.input_tokens + response.usage.output_tokens))
            
            return response.output.choices[0].message.content[0]['text'], response.usage.input_tokens, response.usage.output_tokens, response.usage.input_tokens + response.usage.output_tokens
        else:
            return response.message, 0, 0, 0

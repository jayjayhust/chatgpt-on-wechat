import time
import requests
import json

import openai
import openai.error

from common.log import logger
from common.token_bucket import TokenBucket
from config import conf

def get_token():
    access_key = conf().get("baidu_ernie_access_key")
    secret_key = conf().get("baidu_ernie_secret_key")
    url  = "https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=" + access_key + "&client_secret=" + secret_key
    payload = json.dumps("")
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
        
    response = requests.request("POST", url, headers=headers, data=payload)
    return response.json().get("access_token")

# 百度ERNIE提供的画图接口
class BaiduErnieImage(object):
    def __init__(self):
        pass

    def create_img(self, query, retry_count=0):
        try:
            url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/text2image/sd_xl?access_token=" + get_token()
            payload = json.dumps({
                "prompt": query,
                "negative_prompt": "",
                "size": conf().get("image_create_size", "512x512"),  # ["512x512", "768x768", "768x1024", "1024x768", "576x1024", "1024x576", "1024x1024"]
                "steps": 20, 
                "n": 1,
                "sampler_index": "DPM++ SDE Karras" 
            })
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.request("POST", url, headers=headers, data=payload)

            if "id" in response.json():  # 形如：https://cloud.baidu.com/doc/WENXINWORKSHOP/s/Klkqubb9w#%E5%93%8D%E5%BA%94%E7%A4%BA%E4%BE%8B
                return True, response.json()["data"][0]["b64_image"]  # 图片base64数据
            elif "error_code" in response.json():  # 服务器返回错误信息
                return False, response.json()["error_msg"]
        except Exception as e:
            logger.exception(e)
            return False, str(e)

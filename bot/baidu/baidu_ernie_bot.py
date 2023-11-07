# encoding:utf-8
# REF URL: https://cloud.baidu.com/doc/WENXINWORKSHOP/s/4lilb2lpf

import requests
import json

from bot.bot import Bot
from bridge.reply import Reply, ReplyType
from config import conf, load_config

import openai
# import openai.error
import pinecone  # pip install pinecone-client python-docx plotly scikit-learn
# from openai.embeddings_utils import get_embedding  # pip install matplotlib pandas
import os
from common.log import logger

### init pinecone configuration
pinecone_api_key = conf().get("pinecone_api_key") or os.environ.get('PINECONE_API_KEY')
pinecone.init(
    # api_key="pinecone api key",
    api_key=pinecone_api_key,
    environment="eu-west1-gcp"
)

# create or connect to index
index_name = "holon-expert-2023-0509"
if index_name not in pinecone.list_indexes():
    pinecone.create_index(index_name, dimension=1536)
    logger.debug("pinecone index created!")

# connect to index(this operation shall take a while)
index = pinecone.Index(index_name)
logger.debug("pinecone index connected!")

### Query Index
def search_docs(query):
    xq = openai.Embedding.create(input=query, engine="text-embedding-ada-002")['data'][0]['embedding']
    res = index.query([xq], top_k=5, include_metadata=True)
    chosen_text = []
    for match in res['matches']:
        chosen_text = match['metadata']
    return res['matches']


### Construct Prompt
def construct_prompt(query):
    is_in_index = False
    # is_in_index = True
    matches = search_docs(query)

    chosen_text = []
    for match in matches:
        chosen_text.append(match['metadata']['text'])
        if(match['score'] > 0.85):
            is_in_index = True

    if (is_in_index):
        prompt = """Answer the question as truthfully as possible using the context below, and if the answer is no within the context, say 'I don't know or 抱歉我的知识库还没有这块的知识.'.Remember to reply in the same language as the Question."""
        # prompt = """Answer the question as truthfully as possible using the context below, and if the answer is no within the context, \
        # just feel free to answer by yourself. No need to mention the context provided below and remember to reply in the same language as the Question.'"""
        # prompt = """Answer the question by using the context below, and if the answer is no within the context, \
        # just feel free to answer by yourself. No need to mention the context provided below and remember to reply in the same language as the Question.'"""
        prompt += "\n\n"
        # prompt += "Context: " + "\n".join(chosen_text)  # TypeError: sequence item 0: expected str instance, list found
        prompt += "Context: " + "\n".join('%s' %a for a in chosen_text)
        prompt += "\n\n"
        prompt += "Question: " + query
        prompt += "\n"
        prompt += "Answer: "
        return prompt
    else:
        return query

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

# Baidu ERNIE-Bot-turbo对话接口 
class BaiduErnieBot(Bot):
    def reply(self, query, context=None):
        # 在这里重组query(加载pinecone专家库，先进行专家库检索)
        new_prompt = construct_prompt(query)
        logger.debug(new_prompt)

        url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/eb-instant?access_token=" + get_token()
    
        payload = json.dumps({
            #  最后一个message的content长度（即此轮对话的问题）不能超过11200个字符；
            #  如果messages中content总长度大于11200字符，系统会依次遗忘最早的历史会话，直到content的总长度不超过11200个字符
            "messages": [
                {
                    "role": "user",
                    "content": new_prompt
                }
            ]
        })
        headers = {
            'Content-Type': 'application/json'
        }
        
        response = requests.request("POST", url, headers=headers, data=payload)
        if response:
            reply = Reply(
                ReplyType.TEXT,
                response.json()["result"],
            )
            logger.debug(reply.content)
            return reply
        

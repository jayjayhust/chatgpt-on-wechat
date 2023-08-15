# encoding:utf-8

import zhipuai
import time

from bot.bot import Bot
from bridge.reply import Reply, ReplyType
from config import conf, load_config

import openai
import openai.error
import pinecone  # pip install pinecone-client python-docx plotly scikit-learn
from openai.embeddings_utils import get_embedding  # pip install matplotlib pandas
import os
from common.log import logger

from bot.openai.open_ai_image import OpenAIImage
from common.token_bucket import TokenBucket
from bridge.context import ContextType

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

class ChatGLMImageBot(Bot, OpenAIImage):
    def __init__(self):
        super().__init__()
        # set the default api_key
        openai.api_key = conf().get("open_ai_api_key")
        if conf().get("open_ai_api_base"):
            openai.api_base = conf().get("open_ai_api_base")
        proxy = conf().get("proxy")
        if proxy:
            openai.proxy = proxy
        if conf().get("rate_limit_chatgpt"):
            self.tb4chatgpt = TokenBucket(conf().get("rate_limit_chatgpt", 20))

    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:  # 对文字信息进行回复
            # 在这里重组query(加载pinecone专家库，先进行专家库检索)
            new_prompt = construct_prompt(query)
            logger.debug(new_prompt)

            zhipuai.api_key = conf().get("zhipu_api_key")
            response = zhipuai.model_api.invoke(
                # model="chatglm_lite",  # ChatGLM-6B(https://open.bigmodel.cn/doc/api#chatglm_lite)
                # model="chatglm_std",  # ChatGLM(https://open.bigmodel.cn/doc/api#chatglm_std)
                model="chatglm_pro",  # ChatGLM(https://open.bigmodel.cn/doc/api#chatglm_pro)
                prompt=[
                    {"role": "user", "content": "你是谁"},  # - user 指用户角色输入的信息
                    {"role": "assistant", "content": conf().get("character_desc")},  # - assistant 指模型返回的信息
                    {"role": "user", "content": new_prompt}],
                top_p=0.7,
                temperature=0.9,
            )
            # response形如：{'code': 200, 'msg': '操作成功', 'data': {'request_id': '7789510777205483785', 'task_id': '7789510777205483785', 
            # 'task_status': 'SUCCESS', 'choices': [{'role': 'assistant', 'content': '" 我是一个名为 ChatGLM 的人工智能助手，是基于清华大学 KEG 
            # 实验室和智谱 AI 公司于 2023 年共同训练的语言模型开发的。我的任务是针对用户的问题和要求提供适当的答复和支持。"'}], 'usage': {'total_tokens': 50}}, 
            # 'success': True}
            # or:
            # {'code': 1261, 'msg': 'Prompt 超长', 'success': False}
            logger.debug(response)

            if response['code'] == 200:
                reply = Reply(
                    ReplyType.TEXT,
                    str(response["data"]["choices"][0]["content"]).replace(' ', '').replace('"', ''),
                )
                return reply
            else:
                reply = Reply(
                    ReplyType.TEXT,
                    str('对不起，出错了，错误信息为：' + str(response['code']) + '，错误信息为：' + response['msg']),
                )
                return reply

        elif context.type == ContextType.IMAGE_CREATE:  # 对绘图要求进行回复
            ok, retstring = self.create_img(query, 0)
            reply = None
            if ok:
                reply = Reply(ReplyType.IMAGE_URL, retstring)
            else:
                reply = Reply(ReplyType.ERROR, retstring)
            return reply
        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply

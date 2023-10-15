# encoding:utf-8
# REF URL: https://cloud.baidu.com/doc/WENXINWORKSHOP/s/4lilb2lpf

import time
import requests
import json

from bot.bot import Bot
from bot.baidu.baidu_ernie_session import BaiduErnieSession
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from config import conf, load_config

import openai
import openai.error
import pinecone  # pip install pinecone-client python-docx plotly scikit-learn
from openai.embeddings_utils import get_embedding  # pip install matplotlib pandas
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
class BaiduErnieSessionBot(Bot):
    def __init__(self):
        super().__init__()

        self.sessions = SessionManager(BaiduErnieSession, model=conf().get("model") or "ernie_bot_turbo")
        self.args = {
            "model": conf().get("model") or "ernie_bot_turbo",  # 对话模型的名称
            "temperature": conf().get("temperature", 0.9),  # 值在[0,1]之间，越大表示回复越具有不确定性
            # "max_tokens":4096,  # 回复最大的字符数
            # "top_p": 1,
            # "frequency_penalty": conf().get("frequency_penalty", 0.0),  # [-2,2]之间，该值越大则更倾向于产生不同的内容
            # "presence_penalty": conf().get("presence_penalty", 0.0),  # [-2,2]之间，该值越大则更倾向于产生不同的内容
            # "request_timeout": conf().get("request_timeout", None),  # 请求超时时间，openai接口默认设置为600，对于难问题一般需要较长时间
            # "timeout": conf().get("request_timeout", None),  # 重试超时时间，在这个时间内，将会自动重试
        }

    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:
            logger.info("[ERNIE] query={}".format(query))
            session_id = context["session_id"]
            reply = None  # 初始化reply
            clear_memory_commands = conf().get("clear_memory_commands", ["#清除记忆"])
            if query in clear_memory_commands:
                self.sessions.clear_session(session_id)
                reply = Reply(ReplyType.INFO, "记忆已清除")
            elif query == "#清除所有":
                self.sessions.clear_all_session()
                reply = Reply(ReplyType.INFO, "所有人记忆已清除")
            elif query == "#更新配置":
                load_config()
                reply = Reply(ReplyType.INFO, "配置已更新")
            if reply:  # 如果是指令，直接回复
                return reply
            # 在这里重组query(加载pinecone专家库，先进行专家库检索)
            prompt = construct_prompt(query)
            logger.debug(prompt)
            
            session = self.sessions.session_query(prompt, session_id)
            logger.debug("[ERNIE] session query={}".format(session.messages))

            reply_content = self.reply_text(session)  # 调用reply_text()并传入session参数（实现短期记忆）
            logger.debug(
                "[ERNIE] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                    session.messages,
                    session_id,
                    reply_content["content"],
                    reply_content["completion_tokens"],
                )
            )
            if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
            elif reply_content["completion_tokens"] > 0:
                self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            else:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
                logger.debug("[ERNIE] reply {} used 0 tokens.".format(reply_content))
            return reply
        # elif context.type == ContextType.IMAGE_CREATE:
        #     ok, retstring = self.create_img(query, 0)
        #     reply = None
        #     if ok:
        #         reply = Reply(ReplyType.IMAGE_URL, retstring)
        #     else:
        #         reply = Reply(ReplyType.ERROR, retstring)
        #     return reply
        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply
        
    def reply_text(self, session: BaiduErnieSession, retry_count=0) -> dict:
        """
        call ERNIE's Chat to get the answer
        :param session: a conversation session
        :param session_id: session id
        :param retry_count: retry count
        :return: {}
        """
        try:
            # if conf().get("rate_limit_chatgpt") and not self.tb4chatgpt.get_token():
            #     raise openai.error.RateLimitError("RateLimitError: rate limit exceeded")
            # if api_key == None, the default openai.api_key will be used
            # response = openai.ChatCompletion.create(api_key=api_key, messages=session.messages, **self.args)
            # logger.info("[ERNIE] reply={}, total_tokens={}".format(response.choices[0]['message']['content'], response["usage"]["total_tokens"]))
            
            # ERNIE API: https://cloud.baidu.com/doc/WENXINWORKSHOP/s/4lilb2lpf
            url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/eb-instant?access_token=" + get_token()
            payload = json.dumps({
                # 聊天上下文信息。说明：
                # （1）messages成员不能为空，1个成员表示单轮对话，多个成员表示多轮对话
                # （2）最后一个message为当前请求的信息，前面的message为历史对话信息
                # （3）必须为奇数个成员，成员中message的role必须依次为user、assistant
                # （4）最后一个message的content长度（即此轮对话的问题）不能超过7000 token；如果messages中content总长度大于7000 token，系统会依次遗忘最早的历史会话，直到content的总长度不超过7000 token
                "messages": session.messages
            })
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.request("POST", url, headers=headers, data=payload)
            if response:
                if response.json()["result"] != None:  # 正常回复的处理
                    reply = Reply(
                        ReplyType.TEXT,
                        response.json()["result"],
                    )
                    logger.debug(reply.content)
                    # return reply
                    return {
                        "total_tokens": response.json()["usage"]["total_tokens"],
                        "completion_tokens": response.json()["usage"]["completion_tokens"],
                        "content": response.json()["result"],
                    }
                elif response.json()["error_code"] != None:  # 异常回复的处理
                    # return reply
                    result = {"completion_tokens": 0, "content": response.json()["error_msg"]}
        except Exception as e:
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            
            if need_retry:
                logger.warn("[ERNIE] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, retry_count + 1)
            else:
                return result
        

# encoding:utf-8
# REF URL（文本chat）: 
# REF URL（图片生成）: https://cloud.baidu.com/doc/WENXINWORKSHOP/s/Klkqubb9w

import zhipuai
import time
import requests
import json

from bot.bot import Bot
from bot.chatglm.chat_glm_session import ChatGLMSession
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

from bot.baidu.baidu_ernie_image import BaiduErnieImage

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
    # 这部分逻辑将来也要替换成国内大模型的Embedding接口
    xq = openai.Embedding.create(input=query, engine="text-embedding-ada-002")['data'][0]['embedding']
    # pinecone的query方法：def query(
    # vector: List[float] | None = None,
    # id: str | None = None,
    # queries: List[QueryVector] | List[Tuple] | None = None,
    # top_k: int | None = None,
    # namespace: str | None = None,
    # filter: Dict[str, str | float | int | bool | List | dict] | None = None,
    # include_values: bool | None = None,
    # include_metadata: bool | None = None,
    # sparse_vector: SparseValues | Dict[str, List[float] | List[int]] | None = None,
    # **kwargs: Any
    res = index.query([xq], top_k=5, include_metadata=True)
    chosen_text = []
    # for match in res['matches']:  # 遍历查询的结果
    #     chosen_text = match['metadata']
    return res['matches']  # 返回查询的结果


### Construct Prompt
def construct_prompt(query):
    is_in_index = False
    # is_in_index = True
    matches = search_docs(query)

    chosen_text = []
    for match in matches:  # 遍历查询的结果
        chosen_text.append(match['metadata']['text'])  # 提取单条数据的元数据部分的text字段内容
        if(match['score'] > 0.85):
            is_in_index = True

    if (is_in_index):
        # prompt = """Answer the question as truthfully as possible using the context below, and if the answer is no within the context, say 'I don't know or 抱歉我的知识库还没有这块的知识.'.Remember to reply in the same language as the Question."""
        prompt = """请尽量如实回答用户的提问，如果答案不在下述提供的背景内容中，请直接回答'抱歉我的知识库还没有这块的知识'。记得用用户提问的语言来问答问题。"""
        prompt += "\n\n"
        # prompt += "Context: " + "\n".join(chosen_text)  # TypeError: sequence item 0: expected str instance, list found
        prompt += "提供的背景内容：" + "\n".join('%s' %a for a in chosen_text)
        prompt += "\n\n"
        prompt += "问题：" + query
        prompt += "\n"
        prompt += "回答："
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

# Zhipu ChatGLM对话接口 
class ChatGLMSessionBot(Bot):
    def __init__(self):
        super().__init__()

        self.sessions = SessionManager(ChatGLMSession, model=conf().get("model") or "chatglm_pro")
        self.args = {
            "model": conf().get("model") or "chatglm_pro",  # 对话模型的名称
            "temperature": conf().get("temperature", 0.9),  # 值在[0,1]之间，越大表示回复越具有不确定性
            # "max_tokens":4096,  # 回复最大的字符数
            # "top_p": 1,
            # "frequency_penalty": conf().get("frequency_penalty", 0.0),  # [-2,2]之间，该值越大则更倾向于产生不同的内容
            # "presence_penalty": conf().get("presence_penalty", 0.0),  # [-2,2]之间，该值越大则更倾向于产生不同的内容
            # "request_timeout": conf().get("request_timeout", None),  # 请求超时时间，openai接口默认设置为600，对于难问题一般需要较长时间
            # "timeout": conf().get("request_timeout", None),  # 重试超时时间，在这个时间内，将会自动重试
        }
        self.use_vector_db = conf().get("use_vector_db") or False

    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:  # 文本问答
            logger.info("[ChatGLM] query={}".format(query))
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
            if self.use_vector_db:
                # 在这里进行私有数据库的判断：通过判断群名是否在group_chat_using_private_db中的配置，来设定namespace是否需要设置
                # (logic reserved here=======================================)
                group_chat_name = context["msg"].other_user_nickname
                group_chat_id = context["msg"].other_user_id
                
                # 在这里重组query(加载向量数据库pinecone专家库，先进行专家库检索)
                prompt = construct_prompt(query)
            else:
                # 不加载向量数据库
                prompt = query
            logger.debug(prompt)
            
            session = self.sessions.session_query(prompt, session_id)
            logger.debug("[ChatGLM] session query={}".format(session.messages))

            reply_content = self.reply_text(session)  # 调用reply_text()并传入session参数（实现短期记忆）
            logger.debug(
                "[ChatGLM] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
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
                reply = Reply(ReplyType.TEXT, reply_content["content"], reply_content["completion_tokens"])
            else:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
                logger.debug("[ChatGLM] reply {} used 0 tokens.".format(reply_content))
            return reply
        # elif context.type == ContextType.IMAGE_CREATE:  # 图片生成
        #     ok, retstring = self.create_img(query, 0)
        #     reply = None
        #     if ok:
        #         reply = Reply(ReplyType.IMAGE, retstring)
        #     else:
        #         reply = Reply(ReplyType.ERROR, retstring)
        #     return reply
        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply
        
    def reply_text(self, session: ChatGLMSession, retry_count=0) -> dict:
        """
        call ChatGLM's Chat to get the answer
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
            
            # ChatGLM API: https://open.bigmodel.cn/dev/api#chatglm_pro
            zhipuai.api_key = conf().get("zhipu_api_key")
            response = zhipuai.model_api.invoke(
                # model="chatglm_lite",  # ChatGLM-6B(https://open.bigmodel.cn/doc/api#chatglm_lite)
                # model="chatglm_std",  # ChatGLM(https://open.bigmodel.cn/doc/api#chatglm_std)
                # model="chatglm_pro",  # ChatGLM(https://open.bigmodel.cn/doc/api#chatglm_pro)
                model=conf().get("model") or "chatglm_turbo",
                prompt=session.messages,
                top_p=0.7,
                temperature=0.9,
            )
            # response形如：
            # {'code': 200, 'msg': '操作成功', 'data': {'request_id': '8065132984818443914', 
            # 'task_id': '8065132984818443914', 'task_status': 'SUCCESS', 'choices': [{'role': 'assistant', 
            # 'content': '" 我是一个名为智谱清言的人工智能助手，可以叫我小智🤖，是基于清华大学 KEG 实验室和智谱 AI 公司于 2023 
            # 年共同训练的语言模型开发的。我的任务是针对用户的问题和要求提供适当的答复和支持。"'}], 
            # 'usage': {'prompt_tokens': 3, 'completion_tokens': 53, 'total_tokens': 56}}, 'success': True}
            # or:
            # {'code': 1261, 'msg': 'Prompt 超长', 'success': False}
            logger.debug(response)

            if response['code'] == 200:
                return {
                    "total_tokens": response["data"]["usage"]["total_tokens"],
                    "completion_tokens": response["data"]["usage"]["completion_tokens"],
                    "content": str(response["data"]["choices"][0]["content"]).replace('  ', '').replace('"', '').replace('\n', '').replace('\\n', '')
                }
            else:
                return {
                    "completion_tokens": 0, 
                    "content": str('对不起，出错了，错误代码为：' + str(response['code']) + '，错误信息为：' + response['msg'])
                }
        except Exception as e:
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            
            if need_retry:
                logger.warn("[ChatGLM] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, retry_count + 1)
            else:
                return result
        

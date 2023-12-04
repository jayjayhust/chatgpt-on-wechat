# encoding:utf-8

import time

import openai
# import openai.error
import requests

from bot.bot import Bot
from bot.chatgpt.chat_gpt_session import ChatGPTSession
from bot.openai.open_ai_image import OpenAIImage
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.token_bucket import TokenBucket
from config import conf, load_config

import pinecone  # pip install pinecone-client python-docx plotly scikit-learn
# from openai.embeddings_utils import get_embedding  # pip install matplotlib pandas
import os

# tecent vector db
import tcvectordb
from tcvectordb.model.collection import Embedding
from tcvectordb.model.document import Document, Filter, SearchParams
from tcvectordb.model.enum import FieldType, IndexType, MetricType, EmbeddingModel, ReadConsistency
from tcvectordb.model.index import Index, VectorIndex, FilterIndex, HNSWParams, IVFFLATParams

# ### init pinecone configuration
# pinecone_api_key = conf().get("pinecone_api_key") or os.environ.get('PINECONE_API_KEY')
# pinecone.init(
#     # api_key="pinecone api key",
#     api_key=pinecone_api_key,
#     environment="eu-west1-gcp"
# )

# # create or connect to index
# index_name = "holon-expert-2023-0509"
# # index_name = "community-expert-hunan-cs-2023-05-test"
# if index_name not in pinecone.list_indexes():
#     pinecone.create_index(index_name, dimension=1536)
#     logger.debug("pinecone index created!")

# # connect to index(this operation shall take a while)
# index = pinecone.Index(index_name)
# logger.debug("pinecone index connected!")

# ### Query Index
# def search_docs(query):
#     xq = openai.Embedding.create(input=query, engine="text-embedding-ada-002")['data'][0]['embedding']
#     res = index.query([xq], top_k=5, include_metadata=True)
#     chosen_text = []
#     for match in res['matches']:
#         chosen_text = match['metadata']
#     return res['matches']


# ### Construct Prompt
# def construct_prompt(query):
#     is_in_index = False
#     # is_in_index = True
#     matches = search_docs(query)

#     chosen_text = []
#     for match in matches:
#         chosen_text.append(match['metadata']['text'])
#         if(match['score'] > 0.85):
#             is_in_index = True

#     if (is_in_index):
#         prompt = """Answer the question as truthfully as possible using the context below, and if the answer is no within the context, say 'I don't know or 抱歉我的知识库还没有这块的知识.'.Remember to reply in the same language as the Question."""
#         # prompt = """Answer the question as truthfully as possible using the context below, and if the answer is no within the context, \
#         # just feel free to answer by yourself. No need to mention the context provided below and remember to reply in the same language as the Question.'"""
#         # prompt = """Answer the question by using the context below, and if the answer is no within the context, \
#         # just feel free to answer by yourself. No need to mention the context provided below and remember to reply in the same language as the Question.'"""
#         prompt += "\n\n"
#         # prompt += "Context: " + "\n".join(chosen_text)  # TypeError: sequence item 0: expected str instance, list found
#         prompt += "Context: " + "\n".join('%s' %a for a in chosen_text)
#         prompt += "\n\n"
#         prompt += "Question: " + query
#         prompt += "\n"
#         prompt += "Answer: "
#         return prompt
#     else:
#         return query

DATABASE = "community_database"
COLLECTION = "cs_jjl_private"
COLLECTION_ALIAS = "cs_jjl_private_alias"

_client = tcvectordb.VectorDBClient(url='http://lb-rrpz2rer-fsrvyb2gznphi0kc.clb.ap-beijing.tencentclb.com:10000', 
                                    username='root', 
                                    key='POw30kVmNwOKiJuNi7uPzpoAdX6XWFcIZt3dSECk', 
                                    timeout=30)

### Query Index
def search_docs(query_prompt):
    # xq = openai.Embedding.create(input=query, engine="text-embedding-ada-002")['data'][0]['embedding']
    # res = index.query([xq], top_k=10, include_metadata=True)
    # return res['matches']
    # 获取 Collection 对象
    db = _client.database(DATABASE)
    coll = db.collection(COLLECTION)


    # 通过 embedding 文本搜索
    # 1. searchByText 提供基于 embedding 文本的搜索能力，会先将 embedding 内容做 Embedding 然后进行按向量搜索
    # 2. 支持通过 filter 过滤数据
    # 其他选项类似 search 接口

    # searchByText 返回类型为 Dict，接口查询过程中 embedding 可能会出现截断，如发生截断将会返回响应 warn 信息，如需确认是否截断可以
    # 使用 "warning" 作为 key 从 Dict 结果中获取警告信息，查询结果可以通过 "documents" 作为 key 从 Dict 结果中获取
    embeddingItems = [query_prompt]
    # 不带filter
    search_by_text_res = coll.searchByText(embeddingItems=embeddingItems,
                                            params=SearchParams(ef=200),
                                            limit=5)
    # # 带filter
    # filter_param = Filter("timestamp > 1700167349")  # filter参数写法：https://cloud.tencent.com/document/product/1709/98752
    # search_by_text_res = coll.searchByText(embeddingItems=embeddingItems,
    #                                        filter=filter_param,
    #                                        params=SearchParams(ef=200),
    #                                        limit=5)
    
    warning_info = search_by_text_res.get('warning')
    # print_object(warning_info)
    documents = search_by_text_res.get('documents')
    # print_object(documents)
    # print(len(documents))
    # for document in documents:
    #     for record in document:
    #         print('*' * 100)
    #         print('id:===============>', record['id'])
    #         print('score:============>', record['score'])  
    #         print('text:=============>', record['text'])
    #         print('catagory:=========>', record['catagory'])
    #         print('articleTitle:=====>', record['articleTitle'])
    #         print('url:==============>', record['url'])
    
    # if len(documents) > 0:
    #     print('*' * 100)
    #     print('用户问题：', query_prompt)
    #     print('得分最高的答案：{}, 答案类别为：{}, 得分为：{}'.format(documents[0][0]['text'], documents[0][0]['catagory'], documents[0][0]['score']))

    return documents[0]

### Construct Prompt
def construct_prompt(query):
    matches = search_docs(query)

    chosen_text = []
    for match in matches:
        # chosen_text.append(match['text'])
        chosen_text.append('文章标题：' + match['articleTitle'] + ', 链接：' + match['url'])

    prompt = """用户如果是写文章类的需求，把回答分为两个部分，一个部分是自行作答部分，我期望的格式是：## 自行作答；另外一部分需要完整给出下面提供的背景内容，\
    我期望的格式是：## 知识库推荐 后面附上背景内容列表，我期望的格式是<文章标题>：<链接>。如果用户是信息查询类的问题，则尽量如实回答用户的提问，\
    我期望的格式是：## 知识库推荐；如果答案不在下述提供的背景内容中，请直接回答'抱歉我的知识库还没有这块的知识'"""
    prompt += "\n\n"
    # prompt += "Context: " + "\n".join(chosen_text)  # TypeError: sequence item 0: expected str instance, list found
    prompt += "提供的背景内容：" + "\n".join('%s' %a for a in chosen_text)
    prompt += "\n\n"
    prompt += "问题：" + query
    prompt += "\n"
    prompt += "回答："
    return prompt

# OpenAI对话模型API (可用)
class ChatGPTBot(Bot, OpenAIImage):
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

        self.sessions = SessionManager(ChatGPTSession, model=conf().get("model") or "gpt-3.5-turbo")
        self.args = {
            "model": conf().get("model") or "gpt-3.5-turbo",  # 对话模型的名称
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
            logger.info("[CHATGPT] query={}".format(query))

            session_id = context["session_id"]
            reply = None
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
            if reply:
                return reply
            # 在这里重组query(加载pinecone专家库，先进行专家库检索)
            prompt = construct_prompt(query)
            logger.debug(prompt)
                
            # session = self.sessions.session_query(query, session_id)
            session = self.sessions.session_query(prompt, session_id)
            logger.debug("[CHATGPT] session query={}".format(session.messages))

            api_key = context.get("openai_api_key")

            # if context.get('stream'):
            #     # reply in stream
            #     return self.reply_text_stream(query, new_query, session_id)

            reply_content = self.reply_text(session, api_key)  # 调用reply_text()并传入session参数（实现短期记忆）
            logger.debug(
                "[CHATGPT] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
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
                logger.debug("[CHATGPT] reply {} used 0 tokens.".format(reply_content))
            return reply

        elif context.type == ContextType.IMAGE_CREATE:
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

    def reply_text(self, session: ChatGPTSession, api_key=None, retry_count=0) -> dict:
        """
        call openai's ChatCompletion to get the answer
        :param session: a conversation session
        :param session_id: session id
        :param retry_count: retry count
        :return: {}
        """
        try:
            if conf().get("rate_limit_chatgpt") and not self.tb4chatgpt.get_token():
                raise openai.error.RateLimitError("RateLimitError: rate limit exceeded")
            # if api_key == None, the default openai.api_key will be used
            # OPENAI API: 
            response = openai.ChatCompletion.create(api_key=api_key, messages=session.messages, **self.args)
            # logger.info("[ChatGPT] reply={}, total_tokens={}".format(response.choices[0]['message']['content'], response["usage"]["total_tokens"]))
            return {
                "total_tokens": response["usage"]["total_tokens"],
                "completion_tokens": response["usage"]["completion_tokens"],
                "content": response.choices[0]["message"]["content"],
            }
        except Exception as e:
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            if isinstance(e, openai.error.RateLimitError):
                logger.warn("[CHATGPT] RateLimitError: {}".format(e))
                result["content"] = "提问太快啦，请休息一下再问我吧"
                if need_retry:
                    time.sleep(20)
            elif isinstance(e, openai.error.Timeout):
                logger.warn("[CHATGPT] Timeout: {}".format(e))
                result["content"] = "我没有收到你的消息"
                if need_retry:
                    time.sleep(5)
            elif isinstance(e, openai.error.APIConnectionError):
                logger.warn("[CHATGPT] APIConnectionError: {}".format(e))
                need_retry = False
                result["content"] = "我连接不到你的网络"
            else:
                logger.warn("[CHATGPT] Exception: {}".format(e))
                need_retry = False
                self.sessions.clear_session(session.session_id)

            if need_retry:
                logger.warn("[CHATGPT] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, api_key, retry_count + 1)
            else:
                return result


class AzureChatGPTBot(ChatGPTBot):
    def __init__(self):
        super().__init__()
        openai.api_type = "azure"
        openai.api_version = "2023-03-15-preview"
        self.args["deployment_id"] = conf().get("azure_deployment_id")

    def create_img(self, query, retry_count=0, api_key=None):
        api_version = "2022-08-03-preview"
        url = "{}dalle/text-to-image?api-version={}".format(openai.api_base, api_version)
        api_key = api_key or openai.api_key
        headers = {"api-key": api_key, "Content-Type": "application/json"}
        try:
            body = {"caption": query, "resolution": conf().get("image_create_size", "256x256")}
            submission = requests.post(url, headers=headers, json=body)
            operation_location = submission.headers["Operation-Location"]
            retry_after = submission.headers["Retry-after"]
            status = ""
            image_url = ""
            while status != "Succeeded":
                logger.info("waiting for image create..., " + status + ",retry after " + retry_after + " seconds")
                time.sleep(int(retry_after))
                response = requests.get(operation_location, headers=headers)
                status = response.json()["status"]
            image_url = response.json()["result"]["contentUrl"]
            return True, image_url
        except Exception as e:
            logger.error("create image error: {}".format(e))
            return False, "图片生成失败"

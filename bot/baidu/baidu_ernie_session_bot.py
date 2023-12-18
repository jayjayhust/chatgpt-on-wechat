# encoding:utf-8
# REF URL: https://cloud.baidu.com/doc/WENXINWORKSHOP/s/4lilb2lpf

import time
import requests
import json
from bot.baidu.baidu_ernie_image import BaiduErnieImage
from bot.openai.open_ai_image import OpenAIImage

# tecent vector db
import tcvectordb
from tcvectordb.model.collection import Embedding
from tcvectordb.model.document import Document, Filter, SearchParams
from tcvectordb.model.enum import FieldType, IndexType, MetricType, EmbeddingModel, ReadConsistency
from tcvectordb.model.index import Index, VectorIndex, FilterIndex, HNSWParams, IVFFLATParams

from bot.bot import Bot
from bot.baidu.baidu_ernie_session import BaiduErnieSession
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from config import conf, load_config
from utility.bing_search import bing_search

import openai
# import openai.error
import pinecone  # pip install pinecone-client python-docx plotly scikit-learn
# from openai.embeddings_utils import get_embedding  # pip install matplotlib pandas
import os
from common.log import logger

# ### init pinecone configuration
# pinecone_api_key = conf().get("pinecone_api_key") or os.environ.get('PINECONE_API_KEY')
# pinecone.init(
#     # api_key="pinecone api key",
#     api_key=pinecone_api_key,
#     environment="eu-west1-gcp"
# )

# # create or connect to index
# index_name = "holon-expert-2023-0509"
# if index_name not in pinecone.list_indexes():
#     pinecone.create_index(index_name, dimension=1536)
#     logger.debug("pinecone index created!")

# # connect to index(this operation shall take a while)
# index = pinecone.Index(index_name)
# logger.debug("pinecone index connected!")

# ### Query Index
# def search_docs(query):
#     # 这部分逻辑将来也要替换成国内大模型的Embedding接口
#     xq = openai.Embedding.create(input=query, engine="text-embedding-ada-002")['data'][0]['embedding']
#     # pinecone的query方法：def query(
#     # vector: List[float] | None = None,
#     # id: str | None = None,
#     # queries: List[QueryVector] | List[Tuple] | None = None,
#     # top_k: int | None = None,
#     # namespace: str | None = None,
#     # filter: Dict[str, str | float | int | bool | List | dict] | None = None,
#     # include_values: bool | None = None,
#     # include_metadata: bool | None = None,
#     # sparse_vector: SparseValues | Dict[str, List[float] | List[int]] | None = None,
#     # **kwargs: Any
#     res = index.query([xq], top_k=5, include_metadata=True)
#     chosen_text = []
#     # for match in res['matches']:  # 遍历查询的结果
#     #     chosen_text = match['metadata']
#     return res['matches']  # 返回查询的结果


# ### Construct Prompt
# def construct_prompt(query):
#     is_in_index = False
#     # is_in_index = True
#     matches = search_docs(query)

#     chosen_text = []
#     for match in matches:  # 遍历查询的结果
#         chosen_text.append(match['metadata']['text'])  # 提取单条数据的元数据部分的text字段内容
#         if(match['score'] > 0.85):
#             is_in_index = True

#     if (is_in_index):
#         # prompt = """Answer the question as truthfully as possible using the context below, and if the answer is no within the context, say 'I don't know or 抱歉我的知识库还没有这块的知识.'.Remember to reply in the same language as the Question."""
#         prompt = """请尽量如实回答用户的提问，如果答案不在下述提供的背景内容中，请直接回答'抱歉我的知识库还没有这块的知识'。记得用用户提问的语言来问答问题。"""
#         prompt += "\n\n"
#         # prompt += "Context: " + "\n".join(chosen_text)  # TypeError: sequence item 0: expected str instance, list found
#         prompt += "提供的背景内容：" + "\n".join('%s' %a for a in chosen_text)
#         prompt += "\n\n"
#         prompt += "问题：" + query
#         prompt += "\n"
#         prompt += "回答："
#         return prompt
#     else:
#         return query

# _client = tcvectordb.VectorDBClient(url='http://lb-rrpz2rer-fsrvyb2gznphi0kc.clb.ap-beijing.tencentclb.com:10000',  # 移到配置文件config.json中
#                                     username='root',  # （数据库用户名）移到配置文件config.json中，不过一个微信号应该对应一个向量数据库实例就可以了
#                                     key='POw30kVmNwOKiJuNi7uPzpoAdX6XWFcIZt3dSECk',  # （数据库密码）移到配置文件config.json中，不过一个微信号应该对应一个向量数据库实例就可以了
#                                     timeout=30)
_client = tcvectordb.VectorDBClient(url=conf().get("vector_db_url", ''),
                                    username=conf().get("vector_db_user", ''),
                                    key=conf().get("vector_db_password", ''),
                                    timeout=30)

### Query Index
def search_docs(query_prompt, query_database, query_collection):
    # 获取 Collection 对象
    # db = _client.database(DATABASE)
    db = _client.database(query_database)
    # coll = db.collection(COLLECTION)
    coll = db.collection(query_collection)


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

    documents = search_by_text_res.get('documents')

    return documents[0]

### Construct Prompt
def construct_prompt(query, chosen_text):
    prompt = """请尽量如实回答用户的提问。如果答案不在下述提供的背景内容中，请直接回答'抱歉我的知识库还没有这块的知识'。记得用用户提问的语言来问答问题。"""
    # prompt = """请尽量如实回答用户的提问，并且优先根据下述提供的背景内容作答，如果背景内容中包含URL链接，请在答案中也包含URL链接。记得用用户提问的语言来问答问题。"""
    # prompt = """用户如果是写文章类的需求，把回答分为两个部分，一个部分是自行作答部分，我期望的格式是：## 自行作答；另外一部分需要完整给出下面提供的背景内容，\
    # 我期望的格式是：## 知识库推荐 后面附上背景内容列表，我期望的格式是<文章标题>：<链接>。如果用户是信息查询类的问题，则尽量如实回答用户的提问，\
    # 我期望的格式是：## 知识库推荐；如果答案不在下述提供的背景内容中，请直接回答'抱歉我的知识库还没有这块的知识'"""
    prompt += "\n\n"
    prompt += "以下是提供的背景内容：" + "\n".join('%s' %a for a in chosen_text)
    prompt += "\n\n"
    prompt += "问题：" + query
    prompt += "\n"
    prompt += "回答："
    return prompt

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
# class BaiduErnieSessionBot(Bot, BaiduErnieImage):
class BaiduErnieSessionBot(Bot, OpenAIImage):
    def __init__(self):
        super().__init__()
        self.bing_search_inst = bing_search()  # 实例化搜索引擎

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
        self.use_vector_db = conf().get("use_vector_db") or False

    def reply(self, query, context=None):
        # 私聊的原因信息会通过此处回复，但是绕过了群聊的检测，所以要看传入的上文参数是否保持了单聊/群聊标识
        is_group_chat = context.get("isgroup", False)
        logger.debug("[ERNIE] reply context is-from-group-chat flag={}".format(is_group_chat))

        # acquire reply content
        if context.type == ContextType.TEXT:  # 文本问答
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
            
             # 判断是否开启群的向量数据库
            prompt = query
            chosen_text = []
            if self.use_vector_db and is_group_chat:  # 加载向量数据库（如果是群聊）
                # 在这里进行私有数据库的判断：通过判断群名是否在group_chat_using_private_db中的配置，来设定namespace是否需要设置
                group_chat_name = context["msg"].other_user_nickname
                # group_chat_id = context["msg"].other_user_id
                group_chat_using_private_vector_db = conf().get("group_chat_using_private_vector_db", [])  # 获取各个群对应的数据库设置
                logger.debug(group_chat_using_private_vector_db)
                for group_chat_vector_db_confg in group_chat_using_private_vector_db:
                    logger.debug(group_chat_vector_db_confg)  # dict类型
                    # (logic reserved here=======================================)
                    if group_chat_name in group_chat_vector_db_confg.keys():  # 该群聊开启了向量数据库
                        logger.debug(group_chat_vector_db_confg[group_chat_name]["database"])
                        logger.debug(group_chat_vector_db_confg[group_chat_name]["collection"])
                
                        # 在这里重组query(加载向量数据库pinecone专家库，先进行专家库检索)
                        matches = search_docs(query, group_chat_vector_db_confg[group_chat_name]["database"], group_chat_vector_db_confg[group_chat_name]["collection"])
                        i = 0
                        for match in matches:
                            i += 1
                            if match['score'] > 0.80:  # RAG的分数阈值
                                # chosen_text.append('文章标题：' + match['articleTitle'] + ', 链接：' + match['url'])
                                chosen_text.append('文章标题：' + match['articleTitle'] + ', 链接：' + match['url'] + ', 来源：' + match['dataSourceName'])
                                # chosen_text.append(str(i) + "." + match['articleTitle'] + ':' + match['url'])
                        prompt = construct_prompt(query, chosen_text)
            else:
                # 不加载向量数据库
                prompt = query
            logger.debug(prompt)
            
            session = self.sessions.session_query(prompt, session_id)
            logger.debug("[ERNIE] session query={}".format(session.messages))

            reply_content = self.reply_text(session)  # 调用reply_text()并传入session参数（实现短期记忆）
            if self.use_vector_db and is_group_chat:  # 加载向量数据库
                # 处理下content
                vector_db_retrieval_str = ''
                if len(chosen_text) > 0:
                    for record in chosen_text:
                        vector_db_retrieval_str += record + '\n'
                else:
                    vector_db_retrieval_str = '阿图智库中暂时没有这块知识，请自行搜索。' + '\n'
                result = '## 阿图自行作答:\n' + reply_content["content"] + '\n\n' + \
                        '## 阿图智库推荐:\n' + vector_db_retrieval_str
                reply_content["content"] = result
            logger.debug(
                "[ERNIE] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                    session.messages,
                    session_id,
                    reply_content["content"],
                    reply_content["completion_tokens"]
                )
            )
            # 判断是否开启搜索引擎
            group_bing_search_white_list = conf().get("group_bing_search_white_list", [])
            if any(
                [
                    context["msg"].other_user_nickname in group_bing_search_white_list
                ]
            ):
                search_result, _ = self.bing_search_inst.search(query)
                if len(search_result) > 0:  # 返回的搜索结果大于0，则附加搜索结果到回复
                    search_context = '\n## 阿图在线搜索:\n' 
                    record_count = 0
                    record_count_limit = 2  # 最多显示几条搜索结果
                    for record in search_result:
                        logger.debug(record)  # dict类型
                        # search_context += str(record) + '\n'  # 这里再修订下格式
                        search_context += '【标题】：' + record['name'] + '【简述】：' + record['description'] + '【链接】：' + record['URL'] + '\n'
                        record_count += 1
                        if record_count >= record_count_limit:
                            break
                    reply_content["content"] = str(reply_content["content"]) + search_context  # 添加到回复内容

            if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
            elif reply_content["completion_tokens"] > 0:
                self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                reply = Reply(ReplyType.TEXT, reply_content["content"], reply_content["completion_tokens"], reply_content["total_tokens"])
            else:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
                logger.debug("[ERNIE] reply {} used 0 tokens.".format(reply_content))
            return reply
        # elif context.type == ContextType.IMAGE_CREATE:  # 图片生成（https://cloud.baidu.com/doc/WENXINWORKSHOP/s/Klkqubb9w）
        #     ok, retstring = self.create_img(query, 0)
        #     reply = None
        #     if ok:
        #         reply = Reply(ReplyType.IMAGE_BASE64, retstring)
        #     else:
        #         reply = Reply(ReplyType.ERROR, retstring)
        #     return reply
        elif context.type == ContextType.IMAGE_CREATE:  # 图片生成（使用过DALL.E 3引擎）
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
            # ERNIE-Bot-turbo
            url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/eb-instant?access_token=" + get_token()
            # ERNIE-Bot 4.0
            # url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro?access_token=" + get_access_token()
            payload = json.dumps({
                "system": conf().get("character_desc", ""),
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
            logger.error(e)
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            
            if need_retry:
                logger.warn("[ERNIE] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, retry_count + 1)
            else:
                return result
        

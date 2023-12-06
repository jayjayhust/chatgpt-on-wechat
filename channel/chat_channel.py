import json
import os
import re
import threading
import time
from asyncio import CancelledError
from concurrent.futures import Future, ThreadPoolExecutor

from bridge.context import *
from bridge.reply import *
from channel.channel import Channel
from common.dequeue import Dequeue
from common.log import logger
from config import conf
from plugins import *

from communication.mqtt_client import mqtt_client
import base64  # 二进制方式打开图片文件
import hashlib # 导入hashlib模块

from utility.text_abstract import text_abstract
from utility.image_to_text import image_to_text

try:
    from voice.audio_convert import any_to_wav
except Exception as e:
    pass


md = hashlib.md5() # 获取一个md5加密算法对象

# 抽象类, 它包含了与消息通道无关的通用处理逻辑
class ChatChannel(Channel):
    name = None  # 登录的用户名
    user_id = None  # 登录的用户id
    futures = {}  # 记录每个session_id提交到线程池的future对象, 用于重置会话时把没执行的future取消掉，正在执行的不会被取消
    sessions = {}  # 用于控制并发，每个session_id同时只能有一个context在处理
    lock = threading.Lock()  # 用于控制对sessions的访问
    handler_pool = ThreadPoolExecutor(max_workers=8)  # 处理消息的线程池

    def __init__(self):
        self.mqtt_client_inst = mqtt_client(conf().get("mqtt_url", "127.0.0.1"), 
                                            conf().get("mqtt_port", 1883), 
                                            conf().get("mqtt_username", "admin"), 
                                            conf().get("mqtt_password", "admin"), 
                                            600)
        self.text_abstract_inst = text_abstract()
        self.image_to_text_inst = image_to_text()
        self.greeting_group_status = {}
        group_daily_message_white_list = conf().get("group_daily_message_white_list", [])
        if len(group_daily_message_white_list) > 0:
            for group_name in group_daily_message_white_list:
                self.greeting_group_status[group_name] = False
        _thread = threading.Thread(target=self.consume)
        _thread.setDaemon(True)
        _thread.start()
        _thread_send_heartbeat = threading.Thread(target=self.send_heartbeat)
        _thread_send_heartbeat.setDaemon(True)
        _thread_send_heartbeat.start()
        _thread_send_greeting = threading.Thread(target=self.send_greeting)
        _thread_send_greeting.setDaemon(True)
        _thread_send_greeting.start()

    # 根据消息构造context，消息内容相关的触发项写在这里
    def _compose_context(self, ctype: ContextType, content, **kwargs):
        context = Context(ctype, content)
        context.kwargs = kwargs
        # context首次传入时，origin_ctype是None,
        # 引入的起因是：当输入语音时，会嵌套生成两个context，第一步语音转文本，第二步通过文本生成文字回复。
        # origin_ctype用于第二步文本回复时，判断是否需要匹配前缀，如果是私聊的语音，就不需要匹配前缀
        if "origin_ctype" not in context:
            context["origin_ctype"] = ctype
        # context首次传入时，receiver是None，根据类型设置receiver
        first_in = "receiver" not in context
        # 群名匹配过程，设置session_id和receiver
        if first_in:  # context首次传入时，receiver是None，根据类型设置receiver
            config = conf()
            cmsg = context["msg"]
            user_data = conf().get_user_data(cmsg.from_user_id)
            # context["openai_api_key"] = user_data.get("openai_api_key")  # commented by jay@20230729(not checked!)
            if context.get("isgroup", False): 
                if ctype == ContextType.TEXT:  # 群聊文本（前置，防止被白名单过滤）
                    # 记录所有的群聊文本信息(有个问题就是自己发送的信息，即使加了@，也不会被认为is_at是true!!!)
                    dict1 = {}
                    dict1['group_chat_name'] = context["msg"].other_user_nickname  # 取WechatMessage类中的实例属性（群名称）
                    dict1['group_chat_id'] = context["msg"].other_user_id  # 取WechatMessage类中的实例属性（群id）
                    dict1['msg_type'] = 'TEXT'  # TEXT/VOICE/IMAGE/IMAGE_CREATE/JOIN_GROUP/PATPAT
                    dict1['user_name'] = context["msg"].actual_user_nickname  # need to encrypt this MD5(msg['ActualNickName']).sub(0, 16)
                    # md.update(msg['ActualNickName'].encode('utf-8'))  # 制定需要加密的字符串
                    # dict1['user_name'] = md.hexdigest()[0:8]  # 获取加密后的16进制字符串的前8个字符
                    dict1['user_id'] = context["msg"].actual_user_id
                    dict1['is_at'] = context["msg"].is_at
                    dict1['at_user_name'] = context["msg"].to_user_nickname
                    dict1['at_user_id'] = context["msg"].to_user_id
                    dict1['user_message'] = context["content"]
                    dict1['create_time'] = context["msg"].create_time
                    dict1['bot_id'] = self.user_id
                    self.mqtt_client_inst.publish(f"/chatgpt/groupchat/{self.bot_id}/message", json.dumps(dict1, ensure_ascii=False))
                elif ctype == ContextType.IMAGE:  # 群聊图片（前置，防止被白名单过滤）
                    # 1. 获取图片文件地址
                    cmsg = context["msg"]
                    cmsg.prepare()
                    file_path = context.content  # 获取图片文件地址
                    logger.debug('image path: ' + file_path)
                    subfix = file_path[-3:]  # 获取图片文件后缀
                    # 2. 按照图片文件路径读取图片，转码成BASE64
                    with open(file_path, "rb") as f:  # 转为二进制格式
                        base64_data = base64.b64encode(f.read())  # 使用base64进行加密，输出为bytes
                        str_base64 = base64_data.decode('utf-8')  # https://blog.csdn.net/sunt2018/article/details/95351884
                        # logger.debug(str_base64)  # 打印图片数据
                        # 3. 通过MQTT将图片发送给数据接收服务器
                        dict1 = dict()
                        dict1 = {}
                        dict1['group_chat_name'] = context["msg"].other_user_nickname  # 取WechatMessage类中的实例属性
                        dict1['group_chat_id'] = context["msg"].other_user_id
                        dict1['msg_type'] = 'IMAGE'  # TEXT/VOICE/IMAGE/IMAGE_CREATE/JOIN_GROUP/PATPAT
                        dict1['image_type'] = subfix  # JPG/PNG/BMP
                        dict1['user_name'] = context["msg"].actual_user_nickname  # need to encrypt this MD5(msg['ActualNickName']).sub(0, 16)
                        # md.update(msg['ActualNickName'].encode('utf-8'))  # 制定需要加密的字符串
                        # dict1['user_name'] = md.hexdigest()[0:8]  # 获取加密后的16进制字符串的前8个字符
                        dict1['user_id'] = context["msg"].actual_user_id
                        dict1['is_at'] = context["msg"].is_at
                        dict1['at_user_name'] = context["msg"].to_user_nickname
                        dict1['at_user_id'] = context["msg"].to_user_id
                        dict1['user_message'] = str_base64  # 图片，转码成BASE64
                        dict1['create_time'] = context["msg"].create_time
                        dict1['bot_id'] = self.user_id
                        self.mqtt_client_inst.publish(f"/chatgpt/groupchat/{self.bot_id}/image", json.dumps(dict1, ensure_ascii=False))
                    # # 3.删除图片（图片路径为file_path）===此部分逻辑后移，因为后面加了图片解释功能（根据功能白名单决定开启）
                    # os.remove(file_path)
                elif ctype == ContextType.ATTACHMENT:  # 群聊附件（word/excel/pdf...）
                    # 1. 获取附件地址
                    cmsg = context["msg"]
                    cmsg.prepare()
                    file_path = context.content  # 获取附件文件地址
                    logger.debug('attachment path: ' + file_path)
                    subfix = file_path[-3:]  # 获取图片文件后缀
                    # # 2. 按照图片文件路径读取图片，转码成BASE64
                    # with open(file_path, "rb") as f:  # 转为二进制格式
                    #     base64_data = base64.b64encode(f.read())  # 使用base64进行加密，输出为bytes
                    #     str_base64 = base64_data.decode('utf-8')  # https://blog.csdn.net/sunt2018/article/details/95351884
                    #     # logger.debug(str_base64)  # 打印图片数据
                    #     # 3. 通过MQTT将图片发送给数据接收服务器
                    #     dict1 = dict()
                    #     dict1 = {}
                    #     dict1['group_chat_name'] = context["msg"].other_user_nickname  # 取WechatMessage类中的实例属性
                    #     dict1['group_chat_id'] = context["msg"].other_user_id
                    #     dict1['msg_type'] = 'IMAGE'  # TEXT/VOICE/IMAGE/IMAGE_CREATE/JOIN_GROUP/PATPAT
                    #     dict1['image_type'] = subfix  # JPG/PNG/BMP
                    #     dict1['user_name'] = context["msg"].actual_user_nickname  # need to encrypt this MD5(msg['ActualNickName']).sub(0, 16)
                    #     # md.update(msg['ActualNickName'].encode('utf-8'))  # 制定需要加密的字符串
                    #     # dict1['user_name'] = md.hexdigest()[0:8]  # 获取加密后的16进制字符串的前8个字符
                    #     dict1['user_id'] = context["msg"].actual_user_id
                    #     dict1['is_at'] = context["msg"].is_at
                    #     dict1['at_user_name'] = context["msg"].to_user_nickname
                    #     dict1['at_user_id'] = context["msg"].to_user_id
                    #     dict1['user_message'] = str_base64  # 图片，转码成BASE64
                    #     dict1['create_time'] = context["msg"].create_time
                    #     dict1['bot_id'] = self.user_id
                    #     self.mqtt_client_inst.publish(f"/chatgpt/groupchat/{self.bot_id}/image", json.dumps(dict1, ensure_ascii=False))
                    # # 3.删除图片（图片路径为file_path）
                    # os.remove(file_path)

                group_name = cmsg.other_user_nickname
                group_id = cmsg.other_user_id

                group_name_white_list = config.get("group_name_white_list", [])
                group_name_keyword_white_list = config.get("group_name_keyword_white_list", [])
                if any(
                    [
                        group_name in group_name_white_list,
                        "ALL_GROUP" in group_name_white_list,
                        check_contain(group_name, group_name_keyword_white_list),
                    ]
                ):
                    group_chat_in_one_session = conf().get("group_chat_in_one_session", [])
                    session_id = cmsg.actual_user_id  # 选取用户id(actual_user_id)用作session_id(同一个用户在不同群中的actual_user_id一致么？)
                    if any(
                        [
                            group_name in group_chat_in_one_session,
                            "ALL_GROUP" in group_chat_in_one_session,
                        ]
                    ):
                        session_id = group_id
                else:
                    return None
                context["session_id"] = session_id
                context["receiver"] = group_id
            else:
                context["session_id"] = cmsg.other_user_id
                context["receiver"] = cmsg.other_user_id
            
            # 发送消息事件给插件
            e_context = PluginManager().emit_event(EventContext(Event.ON_RECEIVE_MESSAGE, {"channel": self, "context": context}))
            context = e_context["context"]
            if e_context.is_pass() or context is None:
                return context
            if cmsg.from_user_id == self.user_id and not config.get("trigger_by_self", True):
                logger.debug("[WX]self message skipped")
                return None

        # 消息内容匹配过程，并处理content
        if ctype == ContextType.TEXT:
            # "」\n- - - - - - - - - - - - - - -\n"this is the quotation in a massage
            if first_in and "」\n- - - - - - -" in content:  # 初次匹配 过滤引用消息
                # logger.debug("[WX]reference query skipped")
                # return None
                pass  # 不过滤引用

            if context.get("isgroup", False):  # 群聊
                # 校验关键字
                match_prefix = check_prefix(content, conf().get("group_chat_prefix"))
                match_contain = check_contain(content, conf().get("group_chat_keyword"))
                flag = False
                if match_prefix is not None or match_contain is not None:
                    flag = True
                    if match_prefix:
                        content = content.replace(match_prefix, "", 1).strip()
                if context["msg"].is_at:
                    logger.info("[WX]receive group at")
                    if not conf().get("group_at_off", False):
                        flag = True
                    pattern = f"@{re.escape(self.name)}(\u2005|\u0020)"
                    content = re.sub(pattern, r"", content)

                if not flag:
                    if context["origin_ctype"] == ContextType.VOICE:
                        logger.info("[WX]receive group voice, but checkprefix didn't match")
                    return None
            else:  # 单聊
                match_prefix = check_prefix(content, conf().get("single_chat_prefix", [""]))
                if match_prefix is not None:  # 判断如果匹配到自定义前缀，则返回过滤掉前缀+空格后的内容
                    content = content.replace(match_prefix, "", 1).strip()
                elif context["origin_ctype"] == ContextType.VOICE:  # 如果源消息是私聊的语音消息，允许不匹配前缀，放宽条件
                    pass
                else:
                    return None
            content = content.strip()
            img_match_prefix = check_prefix(content, conf().get("image_create_prefix"))
            if img_match_prefix:
                content = content.replace(img_match_prefix, "", 1)
                context.type = ContextType.IMAGE_CREATE
            else:
                context.type = ContextType.TEXT
            context.content = content.strip()
            if "desire_rtype" not in context and conf().get("always_reply_voice") and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                context["desire_rtype"] = ReplyType.VOICE
        elif context.type == ContextType.VOICE:
            if "desire_rtype" not in context and conf().get("voice_reply_voice") and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                context["desire_rtype"] = ReplyType.VOICE
        elif ctype == ContextType.SHARING:
            if context.get("isgroup", False):  # 群聊
                # 记录所有的群聊链接分享信息
                dict1 = {}
                dict1['group_chat_name'] = context["msg"].other_user_nickname  # 取WechatMessage类中的实例属性
                dict1['group_chat_id'] = context["msg"].other_user_id
                dict1['msg_type'] = 'SHARING'  # TEXT/VOICE/IMAGE/IMAGE_CREATE/JOIN_GROUP/PATPAT/SHARING
                dict1['user_name'] = context["msg"].actual_user_nickname  # need to encrypt this MD5(msg['ActualNickName']).sub(0, 16)
                # md.update(msg['ActualNickName'].encode('utf-8'))  # 制定需要加密的字符串
                # dict1['user_name'] = md.hexdigest()[0:8]  # 获取加密后的16进制字符串的前8个字符
                dict1['user_id'] = context["msg"].actual_user_id
                dict1['is_at'] = context["msg"].is_at
                dict1['at_user_name'] = context["msg"].to_user_nickname
                dict1['at_user_id'] = context["msg"].to_user_id
                dict1['user_message'] = context["content"]  # Url
                dict1['create_time'] = context["msg"].create_time
                self.mqtt_client_inst.publish(f"/chatgpt/groupchat/{self.bot_id}/message", json.dumps(dict1, ensure_ascii=False))
        elif ctype == ContextType.ATTACHMENT:
            if context.get("isgroup", False):  # 群聊
                # 记录所有的群聊文件分享信息
                dict1 = {}
                dict1['group_chat_name'] = context["msg"].other_user_nickname  # 取WechatMessage类中的实例属性
                dict1['group_chat_id'] = context["msg"].other_user_id
                dict1['msg_type'] = 'ATTACHMENT'  # TEXT/VOICE/IMAGE/IMAGE_CREATE/JOIN_GROUP/PATPAT/SHARING/ATTACHMENT
                dict1['user_name'] = context["msg"].actual_user_nickname  # need to encrypt this MD5(msg['ActualNickName']).sub(0, 16)
                # md.update(msg['ActualNickName'].encode('utf-8'))  # 制定需要加密的字符串
                # dict1['user_name'] = md.hexdigest()[0:8]  # 获取加密后的16进制字符串的前8个字符
                dict1['user_id'] = context["msg"].actual_user_id
                dict1['is_at'] = context["msg"].is_at
                dict1['at_user_name'] = context["msg"].to_user_nickname
                dict1['at_user_id'] = context["msg"].to_user_id
                dict1['user_message'] = context["content"]  # 获取附件文件地址
                dict1['create_time'] = context["msg"].create_time
                self.mqtt_client_inst.publish(f"/chatgpt/groupchat/{self.bot_id}/message", json.dumps(dict1, ensure_ascii=False))
        return context

    def _handle(self, context: Context):
        if context is None or not context.content:
            return
        logger.debug("[WX] ready to handle context: {}".format(context))
        # reply的构建步骤
        reply = self._generate_reply(context)

        logger.debug("[WX] ready to decorate reply: {}".format(reply))
        # reply的包装步骤
        reply = self._decorate_reply(context, reply)

        # reply的发送步骤
        self._send_reply(context, reply)

    # 处理消息，并产生回复
    def _generate_reply(self, context: Context, reply: Reply = Reply()) -> Reply:
        e_context = PluginManager().emit_event(
            EventContext(
                Event.ON_HANDLE_CONTEXT,
                {"channel": self, "context": context, "reply": reply},
            )
        )
        reply = e_context["reply"]
        if not e_context.is_pass():
            logger.debug("[WX] ready to handle context: type={}, content={}".format(context.type, context.content))
            if context.type == ContextType.TEXT or context.type == ContextType.IMAGE_CREATE:  # 文字消息和创建图片的消息
                reply = super().build_reply_content(context.content, context)  # 回复消息，也会被自己接收，所以不用特意在这里发送MQTT消息给记录服务器         
            elif context.type == ContextType.VOICE:  # 语音消息
                cmsg = context["msg"]
                cmsg.prepare()
                file_path = context.content  # 获取音频文件地址
                wav_path = os.path.splitext(file_path)[0] + ".wav"  # 在音频文件同目录下，创建同名的wav后缀文件名
                try:
                    any_to_wav(file_path, wav_path)  # 将原始音频文件转换为wav文件
                except Exception as e:  # 转换失败，直接使用mp3，对于某些api，mp3也可以识别
                    logger.warning("[WX]any to wav error, use raw path. " + str(e))
                    wav_path = file_path
                # 语音识别
                reply = super().build_voice_to_text(wav_path)  # 语音转文本
                logger.debug("voice recognize result: " + reply.content)
                # 删除临时文件
                try:
                    os.remove(file_path)
                    if wav_path != file_path:
                        os.remove(wav_path)
                except Exception as e:
                    pass
                    # logger.warning("[WX]delete temp file error: " + str(e))
                if context.get("isgroup", False):  # 群聊
                    # 将语音识别结果的文本记录通过MQTT发送给记录服务器
                    # 记录所有的群聊文本信息
                    dict1 = {}
                    dict1['group_chat_name'] = context["msg"].other_user_nickname  # 取WechatMessage类中的实例属性
                    dict1['group_chat_id'] = context["msg"].other_user_id
                    dict1['msg_type'] = 'VOICE'  # TEXT/VOICE/IMAGE/IMAGE_CREATE/JOIN_GROUP/PATPAT
                    dict1['user_name'] = context["msg"].actual_user_nickname  # need to encrypt this MD5(msg['ActualNickName']).sub(0, 16)
                    # md.update(msg['ActualNickName'].encode('utf-8'))  # 制定需要加密的字符串
                    # dict1['user_name'] = md.hexdigest()[0:8]  # 获取加密后的16进制字符串的前8个字符
                    dict1['user_id'] = context["msg"].actual_user_id
                    dict1['is_at'] = context["msg"].is_at
                    dict1['at_user_name'] = context["msg"].to_user_nickname
                    dict1['at_user_id'] = context["msg"].to_user_id
                    dict1['user_message'] = reply.content  # 语音识别的结果
                    dict1['create_time'] = context["msg"].create_time
                    self.mqtt_client_inst.publish(f"/chatgpt/groupchat/{self.bot_id}/message", json.dumps(dict1, ensure_ascii=False))

                if reply.type == ReplyType.TEXT:
                    new_context = self._compose_context(ContextType.TEXT, reply.content, **context.kwargs)
                    if new_context:
                        reply = self._generate_reply(new_context)
                    else:
                        return
            elif context.type == ContextType.IMAGE:  # 图片消息，当前无默认逻辑，后续把图片都发给服务器作为存档，以便建立图文存档
                if context.get("isgroup", False):  # 群聊（图片通过MQTT发送的逻辑已经前置，防止被白名单过滤）
                    group_chat_name = context["msg"].other_user_nickname  # 取WechatMessage类中的实例属性
                    # 确认在"图片识别"功能开启的白名单内
                    group_image_process_white_list = conf().get("group_image_process_white_list", [])  # 获取开启图片分析功能的白名单
                    if any(
                        [
                            group_chat_name in group_image_process_white_list,
                        ]
                    ):
                        logger.debug(group_chat_name + ' is in group_image_process_white_list')
                
                        # 1. 获取图片文件地址
                        cmsg = context["msg"]
                        cmsg.prepare()
                        file_path = context.content  # 获取图片文件地址
                        logger.debug('image path: ' + file_path)
                        # 2. 按照图片文件路径读取图片，转码成BASE64
                        with open(file_path, "rb") as f:  # 转为二进制格式
                            base64_data = base64.b64encode(f.read())  # 使用base64进行加密，输出为bytes
                            str_base64 = base64_data.decode('utf-8')  # https://blog.csdn.net/sunt2018/article/details/95351884
                            # logger.debug(str_base64)
                            # 3. 调用图片解析接口，获得文本回复
                            result, prompt_tokens, completion_tokens, total_tokens = self.image_to_text_inst.get_image_query_result(str_base64, '请用中文描述下这张图片')
                            logger.debug(result)
                            reply.type = ReplyType.TEXT
                            reply.content = result
                
                # 4. 删除临时图片文件
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning("[WX]delete temp file error: " + str(e)) 
                    return          
            elif context.type == ContextType.SHARING:  # 分享链接的摘要功能(added by jay@20230808)
                group_chat_name = context["msg"].other_user_nickname  # 取WechatMessage类中的实例属性
                group_name_share_text_abstract_white_list = conf().get("group_name_share_text_abstract_white_list", [])  # 获取开启摘要功能的白名单
                if any(
                    [
                        group_chat_name in group_name_share_text_abstract_white_list,
                    ]
                ):
                    logger.debug(group_chat_name + ' is in group_name_share_text_abstract_white_list')

                    url = context["content"]
                    text = self.text_abstract_inst.get_web_text(url)
                    if (conf().get("model", "") == "gpt-3.5-turbo-16k") and (len(text) > 8000):
                        logger.debug('Text in this shared link is too long!')
                        reply.type = ReplyType.TEXT
                        reply.content = '抱歉，您分享的文章内容过长，暂时无法生成摘要。敬请期待我的能力升级吧，阿图fighting~'
                        return reply
                    # elif (conf().get("model", "") == "ernie_bot_turbo") and (len(text) > 6500):
                    elif (conf().get("model", "") == "ernie_bot_turbo") and (len(text) > 32000):
                        logger.debug('Text in this shared link is too long!')
                        reply.type = ReplyType.TEXT
                        reply.content = '抱歉，您分享的文章内容过长，暂时无法生成摘要。敬请期待我的能力升级吧，阿图fighting~'
                        return reply
                    elif (conf().get("model", "") == "chatglm_turbo") and (len(text) > 32000):  # 模型长度限制：https://open.bigmodel.cn/pricing
                        logger.debug('Text in this shared link is too long!')
                        reply.type = ReplyType.TEXT
                        reply.content = '抱歉，您分享的文章内容过长，暂时无法生成摘要。敬请期待我的能力升级吧，阿图fighting~'
                        return reply
                    elif(len(text) < 300):
                        return None
                    text_abstract = self.text_abstract_inst.get_text_abstract(text)
                    logger.debug(text_abstract)
                    reply.type = ReplyType.TEXT
                    reply.content = text_abstract
                else:
                    logger.debug(group_chat_name + ' not is in group_name_share_text_abstract_white_list')
                    return None
            elif context.type == ContextType.ATTACHMENT:  # 分享文件的处理功能(added by jay@20231122)
                if context.get("isgroup", False):  # 群聊
                    group_chat_name = context["msg"].other_user_nickname  # 取WechatMessage类中的实例属性
                    # 确认在"文件处理"功能开启的白名单内
                    group_attachment_process_white_list = conf().get("group_attachment_process_white_list", [])  # 获取开启文件处理功能的白名单
                    if any(
                        [
                            group_chat_name in group_attachment_process_white_list,
                        ]
                    ):
                        logger.debug(group_chat_name + ' is in group_attachment_process_white_list')
                        cmsg = context["msg"]
                        cmsg.prepare()  # 下载文件？
                        file_path = context.content  # 获取文件地址
                        subfix = file_path[-3:]  # 获取文件后缀（这里逻辑待完善，因为有的文件名称不止3个字符，比如.xlsx）
                        file_size = cmsg._rawmsg['FileSize']  # 获取文件大小，单位byte
                        file_size_limit = conf().get("group_attachment_file_size_in_mb", 5)
                        if int(file_size) > (file_size_limit * 1024*1024):
                            logger.debug("[WX] attachment is too large to process, just ignore it.")
                            # 删除文件
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                pass
                                # logger.warning("[WX]delete temp file error: " + str(e))
                            # return
                            reply.type = ReplyType.TEXT
                            reply.content = "文件已收到（但文件大小超过下载限制 {}MB），等待后续阿图功能升级后对文件进行处理~".format(file_size_limit)
                        else:
                            # 提取文件文字（根据文件后缀）
                            #（代码待补充）

                            # 处理文字
                            #（代码待补充）
                
                            # 删除文件
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                pass
                                # logger.warning("[WX]delete temp file error: " + str(e))
                            # return
                            reply.type = ReplyType.TEXT
                            reply.content = "文件已收到，等待后续阿图功能升级后对文件进行处理~"
            else:
                logger.error("[WX] unknown context type: {}".format(context.type))
                return
        return reply

    def _decorate_reply(self, context: Context, reply: Reply) -> Reply:
        if reply and reply.type:
            e_context = PluginManager().emit_event(
                EventContext(
                    Event.ON_DECORATE_REPLY,
                    {"channel": self, "context": context, "reply": reply},
                )
            )
            reply = e_context["reply"]
            desire_rtype = context.get("desire_rtype")
            if not e_context.is_pass() and reply and reply.type:
                if reply.type in self.NOT_SUPPORT_REPLYTYPE:
                    logger.error("[WX]reply type not support: " + str(reply.type))
                    reply.type = ReplyType.ERROR
                    reply.content = "不支持发送的消息类型: " + str(reply.type)

                if reply.type == ReplyType.TEXT:
                    reply_text = reply.content
                    if desire_rtype == ReplyType.VOICE and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                        reply = super().build_text_to_voice(reply.content)
                        return self._decorate_reply(context, reply)
                    if context.get("isgroup", False):
                        reply_text = "@" + context["msg"].actual_user_nickname + " " + reply_text.strip()
                        reply_text = conf().get("group_chat_reply_prefix", "") + reply_text
                    else:
                        reply_text = conf().get("single_chat_reply_prefix", "") + reply_text
                    reply.content = reply_text
                elif reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO:
                    reply.content = "[" + str(reply.type) + "]\n" + reply.content
                elif reply.type == ReplyType.IMAGE_URL or reply.type == ReplyType.VOICE or reply.type == ReplyType.IMAGE or reply.type == ReplyType.IMAGE_BASE64:
                    pass
                else:
                    logger.error("[WX] unknown reply type: {}".format(reply.type))
                    return
            if desire_rtype and desire_rtype != reply.type and reply.type not in [ReplyType.ERROR, ReplyType.INFO]:
                logger.warning("[WX] desire_rtype: {}, but reply type: {}".format(context.get("desire_rtype"), reply.type))
            return reply

    def _send_reply(self, context: Context, reply: Reply):
        if reply and reply.type:
            e_context = PluginManager().emit_event(
                EventContext(
                    Event.ON_SEND_REPLY,
                    {"channel": self, "context": context, "reply": reply},
                )
            )
            reply = e_context["reply"]
            if not e_context.is_pass() and reply and reply.type:
                logger.debug("[WX] ready to send reply: {}, context: {}".format(reply, context))
                self._send(reply, context)
                # 将要回复的文本记录通过MQTT发送给记录服务器(added by jay@20230807)
                # 添加了completion_tokens和total_tokens字段(added by jay@20231116)
                if reply.type == ReplyType.TEXT:
                    dict1 = {}
                    dict1['group_chat_name'] = context["msg"].other_user_nickname  # 取WechatMessage类中的实例属性
                    dict1['group_chat_id'] = context["msg"].other_user_id
                    dict1['msg_type'] = 'TEXT'  # TEXT/VOICE/IMAGE/IMAGE_CREATE/JOIN_GROUP/PATPAT
                    dict1['user_name'] = context["msg"].to_user_nickname  # need to encrypt this MD5(msg['ActualNickName']).sub(0, 16)
                    dict1['user_id'] = context["msg"].to_user_id
                    dict1['is_at'] = context["msg"].is_at
                    dict1['at_user_name'] = context["msg"].actual_user_nickname
                    dict1['at_user_id'] = context["msg"].actual_user_id
                    dict1['user_message'] = reply.content
                    dict1['create_time'] = context["msg"].create_time
                    dict1['bot_id'] = self.user_id
                    dict1['completion_tokens'] = reply.completion_tokens
                    dict1['total_tokens'] = reply.total_tokens
                    self.mqtt_client_inst.publish(f"/chatgpt/groupchat/{self.bot_id}/message", json.dumps(dict1, ensure_ascii=False))

    # 发送微信消息
    def _send(self, reply: Reply, context: Context, retry_cnt=0):
        try:
            # send的具体实现，定义在类似wechat_channel.py中的具体实例类中
            self.send(reply, context)
        except Exception as e:
            logger.error("[WX] sendMsg error: {}".format(str(e)))
            if isinstance(e, NotImplementedError):
                return
            logger.exception(e)
            if retry_cnt < 2:
                time.sleep(3 + 3 * retry_cnt)
                self._send(reply, context, retry_cnt + 1)

    def _success_callback(self, session_id, **kwargs):  # 线程正常结束时的回调函数
        logger.debug("Worker return success, session_id = {}".format(session_id))

    def _fail_callback(self, session_id, exception, **kwargs):  # 线程异常结束时的回调函数
        logger.exception("Worker return exception: {}".format(exception))

    def _thread_pool_callback(self, session_id, **kwargs):
        def func(worker: Future):
            try:
                worker_exception = worker.exception()
                if worker_exception:
                    self._fail_callback(session_id, exception=worker_exception, **kwargs)
                else:
                    self._success_callback(session_id, **kwargs)
            except CancelledError as e:
                logger.info("Worker cancelled, session_id = {}".format(session_id))
            except Exception as e:
                logger.exception("Worker raise exception: {}".format(e))
            with self.lock:
                self.sessions[session_id][1].release()

        return func

    def produce(self, context: Context):
        session_id = context["session_id"]
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = [
                    Dequeue(),
                    threading.BoundedSemaphore(conf().get("concurrency_in_session", 4)),
                ]
            if context.type == ContextType.TEXT and context.content.startswith("#"):
                self.sessions[session_id][0].putleft(context)  # 优先处理管理命令
            else:
                self.sessions[session_id][0].put(context)

    # 消费者函数，单独线程，用于从消息队列中取出消息并处理
    def consume(self):
        while True:
            with self.lock:
                session_ids = list(self.sessions.keys())
                for session_id in session_ids:
                    context_queue, semaphore = self.sessions[session_id]
                    if semaphore.acquire(blocking=False):  # 等线程处理完毕才能删除
                        if not context_queue.empty():
                            context = context_queue.get()
                            logger.debug("[WX] consume context: {}".format(context))
                            future: Future = self.handler_pool.submit(self._handle, context)
                            future.add_done_callback(self._thread_pool_callback(session_id, context=context))
                            if session_id not in self.futures:
                                self.futures[session_id] = []
                            self.futures[session_id].append(future)
                        elif semaphore._initial_value == semaphore._value + 1:  # 除了当前，没有任务再申请到信号量，说明所有任务都处理完毕
                            self.futures[session_id] = [t for t in self.futures[session_id] if not t.done()]
                            assert len(self.futures[session_id]) == 0, "thread pool error"
                            del self.sessions[session_id]
                        else:
                            semaphore.release()
            time.sleep(0.1)

    # 取消session_id对应的所有任务，只能取消排队的消息和已提交线程池但未执行的任务
    def cancel_session(self, session_id):
        with self.lock:
            if session_id in self.sessions:
                for future in self.futures[session_id]:
                    future.cancel()
                cnt = self.sessions[session_id][0].qsize()
                if cnt > 0:
                    logger.info("Cancel {} messages in session {}".format(cnt, session_id))
                self.sessions[session_id][0] = Dequeue()

    def cancel_all_session(self):
        with self.lock:
            for session_id in self.sessions:
                for future in self.futures[session_id]:
                    future.cancel()
                cnt = self.sessions[session_id][0].qsize()
                if cnt > 0:
                    logger.info("Cancel {} messages in session {}".format(cnt, session_id))
                self.sessions[session_id][0] = Dequeue()
    
    # 发送心跳消息给服务器，单独线程
    def send_heartbeat(self):
        while True:
            time.sleep(60.0)  # 休眠60秒
            logger.debug("heartbeat thread is running...")

            if self.mqtt_client_inst.client.is_connected:
                bot_status = False
                from lib import itchat
                import datetime
                current_time = datetime.datetime.now().strftime("%H:%M:%S")
                logger.debug("heartbeat timestamp:{}".format(current_time))
                group_daily_message_white_list = conf().get("group_daily_message_white_list", [])
                if len(group_daily_message_white_list) > 0:
                    for group_name in group_daily_message_white_list:
                        # 参考示例：https://vimsky.com/examples/detail/python-method-itchat.search_chatrooms.html
                        target_rooms = itchat.search_chatrooms(name=group_name)
                        # logger.debug("chat group==>{}<===search info: {}".format(group_name, target_rooms))
                        if target_rooms and len(target_rooms) > 0:
                            bot_status = True
                            break
                        
                
                import datetime
                dict1 = {}
                dict1['status'] = 'online'  # 状态
                dict1['timestamp'] = str(int(datetime.datetime.now().timestamp()))  # 时间戳
                dict1['bot_id'] = self.user_id
                dict1['bot_name'] = self.name
                dict1['bot_status'] = str(bot_status)
                self.mqtt_client_inst.publish(f"/chatgpt/groupchat/{self.user_id}/heartbeat", json.dumps(dict1, ensure_ascii=False))

    # 发送群日推送，单独线程
    def send_greeting(self):
        while True:
            from lib import itchat
            import datetime
            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            group_daily_message_white_list = conf().get("group_daily_message_white_list", [])
            # itchat.get_chatrooms(update=True)  # 获取群聊，注意群必须保持到通讯录，否则可能会找不到群（https://www.cnblogs.com/rgcLOVEyaya/p/RGC_LOVE_YAYA_1075days.html）

            if len(group_daily_message_white_list) > 0:
                for group_name in group_daily_message_white_list:
                    # 参考示例：https://vimsky.com/examples/detail/python-method-itchat.search_chatrooms.html
                    target_rooms = itchat.search_chatrooms(name=group_name)
                    # logger.debug("chat group==>{}<===search info: {}".format(group_name, target_rooms))
                    if target_rooms and len(target_rooms) > 0 and ("09:00:00" <= current_time < "09:59:59") and (self.greeting_group_status[group_name] == False):  # 设定触发时间范围
                        # 提取当日温馨小贴士，在群聊里发送
                        year_month_day = datetime.datetime.now().strftime('%Y-%m-%d')  # 形如：2023-11-04
                        group_daily_message_list = conf().get("group_daily_message", [])
                        if len(group_daily_message_list) > 0:
                            for tmp_dict in group_daily_message_list:
                                for tmp_key in tmp_dict.keys():
                                    if tmp_key == year_month_day:
                                        self.greeting_group_status[group_name] = True
                                        logger.debug("send group hint to {}!".format(group_name))
                                        target_rooms[0].send_msg(tmp_dict[tmp_key])
                                        time.sleep(5)  # 休眠5秒，避免群发消息太快
                                        break
                    elif target_rooms and len(target_rooms) > 0 and ("00:00:00" <= current_time < "00:59:59"):  # 设定群消息已群发记录的清零时间范围
                        self.greeting_group_status[group_name] = False

            time.sleep(120)  # 休眠120秒

def check_prefix(content, prefix_list):
    if not prefix_list:
        return None
    for prefix in prefix_list:
        if content.startswith(prefix):
            return prefix
    return None


def check_contain(content, keyword_list):
    if not keyword_list:
        return None
    for ky in keyword_list:
        if content.find(ky) != -1:
            return True
    return None

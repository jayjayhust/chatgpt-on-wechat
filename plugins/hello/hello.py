# encoding:utf-8

import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from common.log import logger
from plugins import *
from config import conf, get_appdata_dir
import random

@plugins.register(
    name="Hello",
    desire_priority=-1,
    hidden=True,
    desc="A simple plugin that says hello",
    version="0.1",
    author="lanvent",
)
class Hello(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[Hello] inited")

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [
            ContextType.TEXT,
            ContextType.JOIN_GROUP,
            ContextType.PATPAT,
        ]:
            return

        if e_context["context"].type == ContextType.JOIN_GROUP:  # 有新成员入群，欢迎新成员
            # e_context["context"].type = ContextType.TEXT
            e_context["context"].type = ContextType.JOIN_GROUP
            msg: ChatMessage = e_context["context"]["msg"]
            # e_context["context"].content = f'请你随机使用一种风格说一句问候语来欢迎新用户"{msg.actual_user_nickname}"加入群聊。'
            user_specified_guidance = conf().get("user_specified_guidance", [])  # 获取群订制的新进群用户欢迎小贴士数组(订制版本)
            group_chat_name = msg.other_user_nickname  # 获取群名称
            is_user_specified_guidance = False
            for user_specified_guidance_config in user_specified_guidance:
                logger.debug(user_specified_guidance_config)  # dict类型
                if group_chat_name in user_specified_guidance_config.keys():  # 该群聊开启了订制的新进群用户欢迎小贴士
                    is_user_specified_guidance = True
                    # user_guidance = user_specified_guidance_config[group_chat_name]
                    # e_context["context"].content = f'请你随机使用一种风格说一句问候语来欢迎新用户"{msg.actual_user_nickname}"加入群聊，结尾再加上这句使用指南：' + user_guidance
                    # e_context["context"].content = f'请你欢迎新用户"{msg.actual_user_nickname}"加入群聊，并附上群聊使用指南：' + user_guidance
                    break
            
            if not is_user_specified_guidance:
                user_guidances = conf().get("user_guidance", [])  # 获取群聊新进用户欢迎小贴士数组(通用版本)
                if len(user_guidances) == 0:
                    e_context["context"].content = f'请你随机使用一种风格说一句问候语来欢迎新用户"{msg.actual_user_nickname}"加入群聊。'
                else:
                    user_guidance = user_guidances[random.randint(0, len(user_guidances) - 1)]
                    e_context["context"].content = f'请你随机使用一种风格说一句问候语来欢迎新用户"{msg.actual_user_nickname}"加入群聊，结尾再加上这句使用指南：' + user_guidance
            
            e_context.action = EventAction.CONTINUE  # 事件继续，交付给下个插件或默认逻辑
            return

        if e_context["context"].type == ContextType.PATPAT:  # 有人拍一拍自己
            e_context["context"].type = ContextType.TEXT
            msg: ChatMessage = e_context["context"]["msg"]
            # e_context["context"].content = f"请你随机使用一种风格介绍你自己，并告诉用户输入#help可以查看帮助信息。"
            e_context["context"].content = f"请你随机使用一种风格介绍你自己。"
            e_context.action = EventAction.CONTINUE  # 事件继续，交付给下个插件或默认逻辑
            return

        content = e_context["context"].content
        logger.debug("[Hello] on_handle_context. content: %s" % content)
        if content == "Hello":
            reply = Reply()
            reply.type = ReplyType.TEXT
            msg: ChatMessage = e_context["context"]["msg"]
            if e_context["context"]["isgroup"]:
                reply.content = f"Hello, {msg.actual_user_nickname} from {msg.from_user_nickname}"
            else:
                reply.content = f"Hello, {msg.from_user_nickname}"
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS  # 事件结束，并跳过处理context的默认逻辑

        if content == "Hi":
            reply = Reply()
            reply.type = ReplyType.TEXT
            reply.content = "Hi"
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK  # 事件结束，进入默认处理逻辑，一般会覆写reply

        if content == "End":
            # 如果是文本消息"End"，将请求转换成"IMAGE_CREATE"，并将content设置为"The World"
            e_context["context"].type = ContextType.IMAGE_CREATE
            content = "The World"
            e_context.action = EventAction.CONTINUE  # 事件继续，交付给下个插件或默认逻辑

    def get_help_text(self, **kwargs):
        help_text = "输入Hello，我会回复你的名字\n输入End，我会回复你世界的图片\n"
        return help_text

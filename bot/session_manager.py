from common.expired_dict import ExpiredDict
from common.log import logger
from config import conf, load_config


class Session(object):
    def __init__(self, session_id, system_prompt=None):
        self.session_id = session_id  # session_id取的？(参见chat_channel.py中的注释代码)
        self.messages = []
        if system_prompt is None:
            self.system_prompt = conf().get("character_desc", "")
        else:
            self.system_prompt = system_prompt

    # 重置会话
    def reset(self):
        role = "system"
        if conf().get("model", "") == "ernie_bot_turbo" or conf().get("model", "") == "chatglm_turbo":
            # 建立角色的初始人设
            system_item = {"role": "user", "content": "你是谁？"}
            self.messages = [system_item]
            system_item = {"role": "assistant", "content": conf().get("self_desc", "")}
            self.messages.append(system_item)
        else:
            system_item = {"role": role, "content": self.system_prompt}
            self.messages = [system_item]

    def set_system_prompt(self, system_prompt):
        self.system_prompt = system_prompt
        self.reset()

    def add_query(self, query):
        # 这里在欢迎大量新进群的用户时，会出现前一个用户还未回复的情况，下一个用户的query就被添加进session的messages列表中
        # 所以要判断一下当前session的messages列表中最后一个元素的role是否是"user"，如果是，则replace掉它
        if len(self.messages) > 0 and self.messages[-1]["role"] == "user":
            self.messages[-1] = {"role": "user", "content": query}
        else:
            # 否则，直接添加一个新的user_item
            user_item = {"role": "user", "content": query}  
            self.messages.append(user_item)

    def add_reply(self, reply):
        assistant_item = {"role": "assistant", "content": reply}
        self.messages.append(assistant_item)

    def discard_exceeding(self, max_tokens=None, cur_tokens=None):
        raise NotImplementedError

    def calc_tokens(self):
        raise NotImplementedError


class SessionManager(object):
    def __init__(self, sessioncls, **session_args):
        if conf().get("expires_in_seconds"):
            sessions = ExpiredDict(conf().get("expires_in_seconds"))  # 删除超过无操作会话过期时间的信息（单位秒）
        else:
            sessions = dict()
        self.sessions = sessions
        self.sessioncls = sessioncls
        self.session_args = session_args

    def build_session(self, session_id, system_prompt=None):
        """
        如果session_id不在sessions中，创建一个新的session并添加到sessions中
        如果system_prompt不会空，会更新session的system_prompt并重置session
        """
        if session_id is None:
            return self.sessioncls(session_id, system_prompt, **self.session_args)

        if session_id not in self.sessions:
            self.sessions[session_id] = self.sessioncls(session_id, system_prompt, **self.session_args)
        elif system_prompt is not None:  # 如果有新的system_prompt，更新并重置session
            self.sessions[session_id].set_system_prompt(system_prompt)
        session = self.sessions[session_id]
        return session
    
    # 更新对应session_id下保存聊天记录的会话
    def session_query(self, query, session_id):
        session = self.build_session(session_id)
        session.add_query(query)  # 保存聊天记录的会话
        try:
            max_tokens = conf().get("conversation_max_tokens", 1000)
            total_tokens = session.discard_exceeding(max_tokens, None)  # 去除超长的历史聊天记录部分
            logger.debug("prompt tokens used={}".format(total_tokens))
        except Exception as e:
            logger.debug("Exception when counting tokens precisely for prompt: {}".format(str(e)))
        return session

    def session_reply(self, reply, session_id, total_tokens=None):
        session = self.build_session(session_id)
        session.add_reply(reply)
        try:
            max_tokens = conf().get("conversation_max_tokens", 1000)
            tokens_cnt = session.discard_exceeding(max_tokens, total_tokens)
            logger.debug("raw total_tokens={}, savesession tokens={}".format(total_tokens, tokens_cnt))
        except Exception as e:
            logger.debug("Exception when counting tokens precisely for session: {}".format(str(e)))
        return session

    def clear_session(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id]

    def clear_all_session(self):
        self.sessions.clear()

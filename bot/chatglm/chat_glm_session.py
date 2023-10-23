from bot.session_manager import Session
from common.log import logger

"""
    e.g.  [
        {"role": "user", "content": "Who won the world series in 2020?"},
        {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
        {"role": "user", "content": "Where was it played?"}
    ]
"""


class ChatGLMSession(Session):
    def __init__(self, session_id, system_prompt=None, model="chatglm_pro"):
        super().__init__(session_id, system_prompt)
        self.model = model
        self.reset()

    # 去除超长的历史聊天记录部分
    def discard_exceeding(self, max_tokens, cur_tokens=None):
        precise = True
        try:
            cur_tokens = self.calc_tokens()
        except Exception as e:
            precise = False
            if cur_tokens is None:
                raise e
            logger.debug("Exception when counting tokens precisely for query: {}".format(e))
        while cur_tokens > max_tokens:  # 如果当前聊天记录token总数大于指定token总数
            if len(self.messages) > 3:  # 如果历史消息条数大于3
                # 因为智谱AI ChatGLM的逻辑，需要类似[user][assistant][user]这样的奇数条数。所以需要成对删除
                if self.messages[2]["role"] == "user":
                    self.messages.pop(2)  # 把第2条数据剔除出列表（第0条和第1条是机器人人设：见session_manager.py）
                if self.messages[2]["role"] == "assistant":
                    self.messages.pop(2)  # 把第3条数据剔除出列表（第0条和第1条是机器人人设：见session_manager.py）
            # elif len(self.messages) == 2 and self.messages[2]["role"] == "assistant":    # 如果历史消息条数等于3
            #     self.messages.pop(2)
            #     if precise:
            #         cur_tokens = self.calc_tokens()
            #     else:
            #         cur_tokens = cur_tokens - max_tokens
            #     break
            elif len(self.messages) == 3 and self.messages[2]["role"] == "user": # 如果只剩最后3条消息，前两条为角色人设，第3条为用户问询，则已经删无可删了
                logger.warn("user message exceed max_tokens. total_tokens={}".format(cur_tokens))
                break
            else:
                logger.debug("max_tokens={}, total_tokens={}, len(messages)={}".format(max_tokens, cur_tokens, len(self.messages)))
                break
            if precise:
                cur_tokens = self.calc_tokens()
            else:
                cur_tokens = cur_tokens - max_tokens
        return cur_tokens

    def calc_tokens(self):
        return num_tokens_from_messages(self.messages, self.model)


# refer to https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
def num_tokens_from_messages(messages, model):
    """Returns the number of tokens used by a list of messages."""
    import tiktoken

    # try:
    #     encoding = tiktoken.encoding_for_model(model)
    # except KeyError:
    #     logger.debug("Warning: model not found. Using cl100k_base encoding.")
    #     encoding = tiktoken.get_encoding("cl100k_base")
    if model == "ernie_bot_turbo":
        # return num_tokens_from_messages(messages, model="ernie_bot_turbo")
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(value) # 文心一言ERNIE的token计算方式（1token对应1中文，对应1.3的英文）
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
        return num_tokens
    elif model == "ernie_bot":
        return num_tokens_from_messages(messages, model="ernie_bot")
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model == "gpt-4-0314":
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        logger.warn(f"num_tokens_from_messages() is not implemented for model {model}. Returning num tokens assuming gpt-3.5-turbo-0301.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301")
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            # num_tokens += len(encoding.encode(value))  # ChatGPT的token计算方式
            num_tokens += len(value) # 文心一言ERNIE的token计算方式
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

from bot.bot_factory import create_bot
from bridge.context import Context
from bridge.reply import Reply
from common import const
from common.log import logger
from common.singleton import singleton
from config import conf
from translate.factory import create_translator
from voice.factory import create_voice


@singleton
class Bridge(object):
    def __init__(self):
        self.btype = {
            # "chat": const.CHATGPT,  # 这里目前固定死了聊天模型，未来接国内LLM时，要进行切换
            "chat": const.CHATGLM,  # ChatGLM
            "voice_to_text": conf().get("voice_to_text", "openai"),  # voice_to_text的引擎
            "text_to_voice": conf().get("text_to_voice", "google"),  # text_to_voice的引擎
            "translate": conf().get("translate", "baidu"),  # 翻译的引擎
        }
        model_type = conf().get("model")
        if model_type in ["text-davinci-003", "gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4"]:
            self.btype["chat"] = const.OPEN_AI
        if model_type in ["chatglm_pro", "chatglm_std", "chatglm_lite", "chatglm_turbo"]:  # https://open.bigmodel.cn/dev/api#language
            self.btype["chat"] = const.CHATGLM
        if model_type in ["ernie_bot", "ernie_bot_turbo"]:  # https://cloud.baidu.com/doc/WENXINWORKSHOP/s/Nlks5zkzu
            self.btype["chat"] = const.BAIDU
        if conf().get("use_azure_chatgpt", False):
            self.btype["chat"] = const.CHATGPTONAZURE
        self.bots = {}

    def get_bot(self, typename):
        if self.bots.get(typename) is None:
            logger.info("create bot {} for {}".format(self.btype[typename], typename))
            if typename == "text_to_voice":
                self.bots[typename] = create_voice(self.btype[typename])
            elif typename == "voice_to_text":
                self.bots[typename] = create_voice(self.btype[typename])
            elif typename == "chat":
                self.bots[typename] = create_bot(self.btype[typename])  # 这里目前固定死了聊天模型（为CHATGPT），未来接国内LLM时，要进行切换
            elif typename == "translate":
                self.bots[typename] = create_translator(self.btype[typename])
        return self.bots[typename]

    def get_bot_type(self, typename):
        return self.btype[typename]

    def fetch_reply_content(self, query, context: Context) -> Reply:
        return self.get_bot("chat").reply(query, context)

    def fetch_voice_to_text(self, voiceFile) -> Reply:
        return self.get_bot("voice_to_text").voiceToText(voiceFile)

    def fetch_text_to_voice(self, text) -> Reply:
        return self.get_bot("text_to_voice").textToVoice(text)

    def fetch_translate(self, text, from_lang="", to_lang="en") -> Reply:
        return self.get_bot("translate").translate(text, from_lang, to_lang)

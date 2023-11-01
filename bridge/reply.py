# encoding:utf-8

from enum import Enum


class ReplyType(Enum):
    TEXT = 1  # 文本
    VOICE = 2  # 音频文件
    IMAGE = 3  # 图片文件
    IMAGE_URL = 4  # 图片URL
    IMAGE_BASE64 = 5  # 图片数据（BASE64）

    INFO = 9
    ERROR = 10

    def __str__(self):
        return self.name


class Reply:
    def __init__(self, type: ReplyType = None, content=None, completion_tokens=0):
        self.type = type
        self.content = content
        self.completion_tokens = completion_tokens

    def __str__(self):
        return "Reply(type={}, content={}, completion_tokens={})".format(self.type, self.content, self.completion_tokens)

# encoding:utf-8

"""
wechat channel
"""

import io
import json
import os
import threading
import time

import requests

from bridge.context import *
from bridge.reply import *
from channel.chat_channel import ChatChannel
from channel.wechat.wechat_message import *
from common.expired_dict import ExpiredDict
from common.log import logger
from common.singleton import singleton
from common.time_check import time_checker
from config import conf, get_appdata_dir
from lib import itchat
from lib.itchat.content import *
from plugins import *
from utility.mac_derive import mac_derive


@itchat.msg_register([TEXT, VOICE, PICTURE, NOTE])
def handler_single_msg(msg):
    try:
        # filename = msg['FileName']
        # msg['Text'](filename)  # 下载图片(https://blog.csdn.net/tustzhoujian/article/details/81780298)
        cmsg = WechatMessage(msg, False)  # 原则上不用上面两行刻意去下载VOICE/PICTURE，在WechatMessage的构造函数里面实现了资源的下载
    except NotImplementedError as e:
        logger.debug("[WX]single message {} skipped: {}".format(msg["MsgId"], e))
        return None
    WechatChannel().handle_single(cmsg)
    return None


@itchat.msg_register([TEXT, VOICE, PICTURE, NOTE, SHARING], isGroupChat=True)
def handler_group_msg(msg):
    try:
        cmsg = WechatMessage(msg, True)
    except NotImplementedError as e:
        logger.debug("[WX]group message {} skipped: {}".format(msg["MsgId"], e))
        return None
    WechatChannel().handle_group(cmsg)
    return None


def _check(func):
    def wrapper(self, cmsg: ChatMessage):
        msgId = cmsg.msg_id
        if msgId in self.receivedMsgs:
            logger.info("Wechat message {} already received, ignore".format(msgId))
            return
        self.receivedMsgs[msgId] = cmsg
        create_time = cmsg.create_time  # 消息时间戳
        if conf().get("hot_reload") == True and int(create_time) < int(time.time()) - 60:  # 跳过1分钟前的历史消息
            logger.debug("[WX]history message {} skipped".format(msgId))
            return
        return func(self, cmsg)

    return wrapper


# 可用的二维码生成接口
# https://api.qrserver.com/v1/create-qr-code/?size=400×400&data=https://www.abc.com
# https://api.isoyu.com/qr/?m=1&e=L&p=20&url=https://www.abc.com
def qrCallback(uuid, status, qrcode):
    logger.debug("qrCallback: {} {} {}".format(uuid, status, qrcode))
    if status == "0":
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(qrcode))
            _thread = threading.Thread(target=img.show, args=("QRCode",))  # 定义显示图片的线程任务
            _thread.setDaemon(True)
            _thread.start()
        except Exception as e:
            pass

        import qrcode

        url = f"https://login.weixin.qq.com/l/{uuid}"

        qr_api1 = "https://api.isoyu.com/qr/?m=1&e=L&p=20&url={}".format(url)
        qr_api2 = "https://api.qrserver.com/v1/create-qr-code/?size=400×400&data={}".format(url)
        qr_api3 = "https://api.pwmqr.com/qrcode/create/?url={}".format(url)
        qr_api4 = "https://my.tv.sohu.com/user/a/wvideo/getQRCode.do?text={}".format(url)
        print("You can also scan QRCode in any website below:")
        print(qr_api3)
        print(qr_api4)
        print(qr_api2)
        print(qr_api1)

        # 输出登录二维码到终端界面
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        # qr.print_ascii(invert=True)

        # 1.发送登录二维码请求及设备id（utility/mac_derive.py）到后台（http post）--->用户需要手机微信扫码登录，不能长按识别，如何解决？？？
        # 解决办法（给auto_login方法传入值为真的hotReload）：https://www.cnblogs.com/Rain2017/p/11401189.html
        # 2.登录完成后，还要把登录账号信息（微信昵称，微信id）及设备id也发送到后台（http post）
        # (此处代码待完善)
        mac_derive_inst = mac_derive()
        wlan_mac = mac_derive_inst.get_wlan_mac()
        if wlan_mac != None:
            logger.info("wlan_mac: {}".format(wlan_mac))
        else:
            logger.info("wlan_mac is not available")

# 单例模式：保证了在程序的不同位置都可以且仅可以取到同一个对象实例，如果实例不存在，会创建一个实例；如果已存在就会返回这个实例。
@singleton
class WechatChannel(ChatChannel):  # 继承了ChatChannel(chat_channel.py)
    NOT_SUPPORT_REPLYTYPE = []

    def __init__(self):
        super().__init__()
        self.receivedMsgs = ExpiredDict(60 * 60 * 24)
        self.bot_id = conf().get("bot_id", "bot")

    def startup(self):
        itchat.instance.receivingRetryCount = 600  # 修改断线超时时间
        # option 1: login by scan QRCode
        # hotReload = conf().get("hot_reload", False)  # hot_reload是指利用缓存、不用扫码登录
        # status_path = os.path.join(get_appdata_dir(), "itchat.pkl")
        # itchat.auto_login(
        #     enableCmdQR=2,
        #     hotReload=hotReload,
        #     statusStorageDir=status_path,
        #     qrCallback=qrCallback,  # method that should accept uuid, status, qrcode for usage
        # )
        # option 2: login using hot_reload(首次登录，因为没有"itchat.pkl"缓存文件，还是会要用户扫描二维码，后面每次再掉线后（比如项目出错）/OTA更新的时候，
        # 只要短时间内再重登录，则不用用户再扫码，所以这个对系统的自动化运维提出了很高的要求，否则就需要用户再用手机微信扫描登录二维码，而这个场景其实是比较困难的，
        # 实施成本会比较高。)
        # 给auto_login方法传入值为真的hotReload：https://www.cnblogs.com/Rain2017/p/11401189.html
        hotReload = conf().get("hot_reload", True)  # hot_reload是指利用缓存、不用扫码登录（该方法会生成一个静态文件itchat.pkl，用于存储登陆的状态）
        status_path = os.path.join(get_appdata_dir(), "itchat.pkl")
        itchat.auto_login(
            # enableCmdQR=2,
            hotReload=hotReload,
            statusStorageDir=status_path,
            qrCallback=qrCallback,  # method that should accept uuid, status, qrcode for usage
        )
        self.user_id = itchat.instance.storageClass.userName
        self.name = itchat.instance.storageClass.nickName
        logger.info('*' * 100)
        logger.info("Wechat login success, user_id: {}, nickname: {}".format(self.user_id, self.name))
        # 登录完成后，把登录账号信息（微信昵称，微信id）及设备id也发送到后台（http post）
        # (此处代码待完善)
        mac_derive_inst = mac_derive()
        wlan_mac = mac_derive_inst.get_wlan_mac()
        if wlan_mac != None:
            logger.info("wlan_mac: {}".format(wlan_mac))
        else:
            logger.info("wlan_mac is not available")

        # start message listener
        itchat.run()

    # handle_* 系列函数处理收到的消息后构造Context，然后传入produce函数中处理Context和发送回复
    # Context包含了消息的所有信息，包括以下属性
    #   type 消息类型, 包括TEXT、VOICE、IMAGE_CREATE
    #   content 消息内容，如果是TEXT类型，content就是文本内容，如果是VOICE类型，content就是语音文件名，如果是IMAGE_CREATE类型，content就是图片生成命令
    #   kwargs 附加参数字典，包含以下的key：
    #        session_id: 会话id
    #        isgroup: 是否是群聊
    #        receiver: 需要回复的对象
    #        msg: ChatMessage消息对象
    #        origin_ctype: 原始消息类型，语音转文字后，私聊时如果匹配前缀失败，会根据初始消息是否是语音来放宽触发规则
    #        desire_rtype: 希望回复类型，默认是文本回复，设置为ReplyType.VOICE是语音回复

    @time_checker
    @_check
    def handle_single(self, cmsg: ChatMessage):  # 没有self参数，不是实例方法，是类方法
        if cmsg.ctype == ContextType.VOICE:
            if conf().get("speech_recognition") != True:
                return
            logger.debug("[WX]receive voice msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.IMAGE:
            logger.debug("[WX]receive image msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.PATPAT:
            logger.debug("[WX]receive patpat msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.TEXT:
            logger.debug("[WX]receive text msg: {}, cmsg={}".format(json.dumps(cmsg._rawmsg, ensure_ascii=False), cmsg))
            # dict1 = dict()
            # dict1['is_group'] = 'false'
            # dict1['message_type'] = 'TEXT'  # 文本内容
            # dict1['message'] = json.dumps(cmsg._rawmsg, ensure_ascii=False)
            # self.mqtt_client_inst.publish(f"/chatgpt/groupchat/{self.bot_id}/status", json.dumps(dict1, ensure_ascii=False))
        else:
            logger.debug("[WX]receive msg: {}, cmsg={}".format(cmsg.content, cmsg))
        context = self._compose_context(cmsg.ctype, cmsg.content, isgroup=False, msg=cmsg)
        if context:
            self.produce(context)  # 调用父类的produce()方法

    @time_checker
    @_check
    def handle_group(self, cmsg: ChatMessage):  # 没有self参数，不是实例方法，是类方法
        if cmsg.ctype == ContextType.VOICE:
            if conf().get("speech_recognition") != True:
                return
            logger.debug("[WX]receive voice for group msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.IMAGE:
            logger.debug("[WX]receive image for group msg: {}".format(cmsg.content))
        elif cmsg.ctype in [ContextType.JOIN_GROUP, ContextType.PATPAT]:  # 有人加入群，或者拍一拍
            logger.debug("[WX]receive note msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.TEXT:
            logger.debug("[WX]receive group msg: {}, cmsg={}".format(json.dumps(cmsg._rawmsg, ensure_ascii=False), cmsg))
        elif cmsg.ctype == ContextType.SHARING:
            logger.debug("[WX]receive group sharing: {}, cmsg={}".format(json.dumps(cmsg._rawmsg, ensure_ascii=False), cmsg))
        else:
            logger.debug("[WX]receive group msg: {}".format(cmsg.content))
        context = self._compose_context(cmsg.ctype, cmsg.content, isgroup=True, msg=cmsg)  # 组织消息（包含过滤）
        if context:
            self.produce(context)  # 调用父类的produce()方法

    # 统一的发送函数，每个Channel自行实现，根据reply的type字段发送不同类型的消息
    def send(self, reply: Reply, context: Context):
        receiver = context["receiver"]  # 提取消息收取对象的信息（群聊的id：UserName）
        if reply.type == ReplyType.TEXT:  # 文字回复
            itchat.send(reply.content, toUserName=receiver)  # 调用itchat接口发送文本消息
            logger.info("[WX] sendMsg={}, receiver={}".format(reply, receiver))
        elif reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO:
            itchat.send(reply.content, toUserName=receiver)  # 调用itchat接口发送文本消息
            logger.info("[WX] sendMsg={}, receiver={}".format(reply, receiver))
        elif reply.type == ReplyType.VOICE:  # 语音回复
            itchat.send_file(reply.content, toUserName=receiver)  # 调用itchat接口发送语音消息
            logger.info("[WX] sendFile={}, receiver={}".format(reply.content, receiver))
        elif reply.type == ReplyType.IMAGE_URL:  # 从网络下载图片
            img_url = reply.content
            pic_res = requests.get(img_url, stream=True)
            image_storage = io.BytesIO()
            for block in pic_res.iter_content(1024):
                image_storage.write(block)
            image_storage.seek(0)
            itchat.send_image(image_storage, toUserName=receiver)  # 调用itchat接口发送图片
            logger.info("[WX] sendImage url={}, receiver={}".format(img_url, receiver))
        elif reply.type == ReplyType.IMAGE:  # 从文件读取图片
            image_storage = reply.content
            image_storage.seek(0)
            itchat.send_image(image_storage, toUserName=receiver)  # 调用itchat接口发送图片
            logger.info("[WX] sendImage, receiver={}".format(receiver))

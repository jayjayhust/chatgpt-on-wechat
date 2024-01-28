 
import paho.mqtt.client as mqtt # pip install paho-mqtt
from paho.mqtt.client import MQTTv31, MQTTv311, MQTTv5
import json

from common.log import logger
from config import conf

import datetime

class mqtt_client(object):
    
    # 类的实例化（初始化）
    def __init__(self, mqtt_host, mqtt_port, mqtt_username, mqtt_password, mqtt_keepalive):
        super(mqtt_client, self).__init__()
        self.bot_id = conf().get("bot_id", "bot")
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        self.client.username_pw_set(username=mqtt_username, password=mqtt_password)
        self.client.connect(mqtt_host, mqtt_port, mqtt_keepalive)  # 600为keepalive的时间间隔
        # self.client.loop_forever()  # 保持连接
        self.client.loop_start()  # keep connection using thread

    # 连接回调
    def on_connect(self, client, userdata, flags, rc):
        logger.debug("Connected with result code: " + str(rc))
        # 发布机器人上线消息
        client.publish(f"/chatgpt/groupchat/{self.bot_id}/status", "{'status'': 'log online', 'bot_id': '" + self.bot_id + "'}")
        
        # 订阅相关主题
        client.subscribe("/sys/config/push")  # 服务器配置下发
        client.subscribe("/sys/config/get_reply")  # 微信端配置查询回复
    
    # 消息回调
    def on_message(self, client, userdata, msg):
        logger.debug("On message topic:" + msg.topic + " message:" + str(msg.payload.decode('utf-8')))
        # 根据主题确定不同的处理方法
        self.bot_id = conf().get("bot_id", "bot")
        logger.debug("Wechat bot_id is:" + self.bot_id)
        if msg.topic == f"/sys/config/push":  # 服务器配置下发
            data = json.loads(str(msg.payload.decode('utf-8')))  # 字符串转字典
            msgId = data['msgId']
            for record in data['data']:
                logger.debug('群名:', record['chatGroupName'])  # chatGroupName: 群名
                chat_group_name = record['chatGroupName']
                for role in record['role']:  # key: 0阿图智聊/1推文摘要/2图片储存
                    logger.debug('功能:', role['name'], ':', role['key'])
                    if role['key'] == 0:  # 阿图智聊
                        group_name_white_list = conf().get("group_name_white_list", [])
                        if chat_group_name not in group_name_white_list:
                            group_name_white_list.append(chat_group_name)
                        conf().set("group_name_white_list", self.group_name_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == 1:  # 推文摘要
                        group_name_share_text_abstract_white_list = conf().get("group_name_share_text_abstract_white_list", [])
                        if chat_group_name not in group_name_share_text_abstract_white_list:
                            group_name_share_text_abstract_white_list.append(chat_group_name)
                        conf().set("group_name_share_text_abstract_white_list", self.group_name_share_text_abstract_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == 2:  # 图片储存
                        group_name_image_save_white_list = conf().get("group_name_image_save_white_list", [])
                        if chat_group_name not in group_name_image_save_white_list:
                            group_name_image_save_white_list.append(chat_group_name)
                        conf().set("group_name_image_save_white_list", self.group_name_image_save_white_list)  # 更新到全局配置文件
                        pass
            
            # 回复配置下发结果
            # timestamp = str(int(datetime.datetime.now().timestamp()))  # 时间戳（形如1706416021）
            timestamp = str(datetime.datetime.now().strftime('%Y%m%d%H%M%S'))  # 时间戳（形如20240128123105）
            data_str = "{'msgId': '" + msgId + "', 'type': 'json', 'timestamp': '" + timestamp + "','message': '','success': ''}"
            client.publish(f"/sys/config/push_reply", data_str)
        elif msg.topic == f"/sys/config/get_reply":  # 微信端配置查询回复
            data = json.loads(str(msg.payload.decode('utf-8')))  # 字符串转字典
            msgId = data['msgId']
            for record in data['data']:
                logger.debug('群名:', record['chatGroupName'])  # chatGroupName: 群名
                chat_group_name = record['chatGroupName']
                for role in record['role']:  # key: 0阿图智聊/1推文摘要/2图片储存
                    logger.debug('功能:', role['name'], ':', role['key'])
                    if role['key'] == 0:  # 阿图智聊
                        group_name_white_list = conf().get("group_name_white_list", [])
                        if chat_group_name not in group_name_white_list:
                            group_name_white_list.append(chat_group_name)
                        conf().set("group_name_white_list", self.group_name_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == 1:  # 推文摘要
                        group_name_share_text_abstract_white_list = conf().get("group_name_share_text_abstract_white_list", [])
                        if chat_group_name not in group_name_share_text_abstract_white_list:
                            group_name_share_text_abstract_white_list.append(chat_group_name)
                        conf().set("group_name_share_text_abstract_white_list", self.group_name_share_text_abstract_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == 2:  # 图片储存
                        group_name_image_save_white_list = conf().get("group_name_image_save_white_list", [])
                        if chat_group_name not in group_name_image_save_white_list:
                            group_name_image_save_white_list.append(chat_group_name)
                        conf().set("group_name_image_save_white_list", self.group_name_image_save_white_list)  # 更新到全局配置文件
                        pass
        
    # 订阅回调
    def on_subscribe(self, client, userdata, mid, granted_qos):
        logger.debug("On Subscribed: qos = %d" % granted_qos)

        # 发送配置下发请求
        if userdata == '/sys/config/get':
            timestamp = str(datetime.datetime.now().strftime('%Y%m%d%H%M%S'))  # 时间戳（形如20240128123105）
            msgId = timestamp
            data_str = "{'msgId': '" + msgId + "', 'type': 'json', 'timestamp': '" + timestamp + "','message': '','success': ''}"
            client.publish(f"/sys/config/get", data_str)
            pass
 
    # 取消订阅回调
    def on_unsubscribe(self, client, userdata, mid):
        # print("取消订阅")
        logger.debug("On unSubscribed: qos = %d" % mid)
        pass
 
    # 发布消息回调
    def on_publish(self, client, userdata, mid):
        # print("发布消息")
        logger.debug("On onPublish: qos = %d" % mid)
        pass
 
    # 断开链接回调
    def on_disconnect(self, client, userdata, rc):
        # print("断开链接")
        logger.debug("Unexpected disconnection rc = " + str(rc))
        pass
    
    # 发布消息
    def publish(self, topic, payload, qos=0, retain=False):
        self.client.publish(topic, payload, qos, retain)
    
    # 断开连接
    def disconnect(self):
        self.client.disconnect()
 
import paho.mqtt.client as mqtt # pip install paho-mqtt
from paho.mqtt.client import MQTTv31, MQTTv311, MQTTv5
import json

from common.log import logger
from config import conf

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
        client.subscribe("/chatgpt/groupchat/+/config/push")  # 配置下发
    
    # 消息回调
    def on_message(self, client, userdata, msg):
        logger.debug("On message topic:" + msg.topic + " message:" + str(msg.payload.decode('utf-8')))
        # 根据主题确定不同的处理方法
        self.bot_id = conf().get("bot_id", "bot")
        if msg.topic == f"/chatgpt/groupchat/{self.bot_id}/config/push":
            if msg.payload.decode('utf-8').json()['bot_id'] == conf().get("bot_id", "bot"):
                logger.debug("收到配置推送！")
        
    # 订阅回调
    def on_subscribe(self, client, userdata, mid, granted_qos):
        logger.debug("On Subscribed: qos = %d" % granted_qos)
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
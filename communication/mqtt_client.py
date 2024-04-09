 
import paho.mqtt.client as mqtt # pip install paho-mqtt
from paho.mqtt.client import MQTTv31, MQTTv311, MQTTv5
import json

from common.log import logger
from config import conf

import datetime
import time

from bridge.context import *

class mqtt_client(object):
    
    # 类的实例化（初始化）
    def __init__(self, mqtt_host, mqtt_port, mqtt_username, mqtt_password, mqtt_keepalive):
        super(mqtt_client, self).__init__()
        self.bot_id = conf().get("bot_id", "bot")
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
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
        client.subscribe("/sys/message/push")  # 服务器消息下发

        # 等待订阅生效
        time.sleep(3)

        # 向服务器发送配置查询请求
        timestamp = str(datetime.datetime.now().strftime('%Y%m%d%H%M%S'))  # 时间戳（形如20240128123105）
        msgId = timestamp
        data_str = "{'msgId': '" + msgId + "', 'type': 'json', 'timestamp': '" + timestamp + "','dataType': 'all','chatGroupName': ''}"
        client.publish(f"/sys/config/get", data_str)
    
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
                logger.debug('群名:' + record['chatGroupName'])  # chatGroupName: 群名
                chat_group_name = record['chatGroupName']
                
                # 更新群聊对应的向量数据库配置
                if 'vectordbName' in record and (record['vectordbName'] != ''):
                    logger.debug('向量库名:' + record['vectordbName'])  # vectordbName: 向量库名
                    logger.debug('向量表名:' + record['vectordbCollection'])  # vectordbCollection: 向量表名
                    group_chat_using_private_vector_db = conf().get("group_chat_using_private_vector_db", [])
                    chat_group_name_exist = False
                    for vector_db_config in group_chat_using_private_vector_db:  # 遍历白名单中的群名
                        if chat_group_name in vector_db_config:  # 群名存在
                            vector_db_config[chat_group_name]['database'] = record['vectordbName']
                            vector_db_config[chat_group_name]['collection'] = record['vectordbCollection']
                            chat_group_name_exist = True
                            break
                    if not chat_group_name_exist:  # 群名不在白名单中，则新增向量库配置
                        group_chat_using_private_vector_db.append({chat_group_name: {'database': record['vectordbName'], 'collection': record['vectordbCollection']}})
                    conf().set("group_chat_using_private_vector_db", group_chat_using_private_vector_db)  # 更新到全局配置文件

                # 更新群聊欢迎语
                if 'welcomeMessage' in record and (record['welcomeMessage'] != '') and len(record['welcomeMessage']) > 0:
                    logger.debug('群聊' + chat_group_name + '指定的欢迎语:' + record['welcomeMessage'][0]['value'])
                    user_specified_guidance = conf().get("user_specified_guidance", [])
                    chat_group_name_exist = False
                    for user_specified_guidance_config in user_specified_guidance:  # 遍历白名单中的群名
                        if chat_group_name in user_specified_guidance_config:  # 群名存在
                            user_specified_guidance_config[chat_group_name] = record['welcomeMessage'][0]['value']
                            chat_group_name_exist = True
                            break
                    if not chat_group_name_exist:  # 群名不在白名单中，则新增欢迎语配置
                        user_specified_guidance.append({chat_group_name: record['welcomeMessage'][0]['value']})
                    conf().set("user_specified_guidance", user_specified_guidance)  # 更新到全局配置文件

                for role in record['role']:  # key: 0阿图智聊/1推文摘要/2图片储存/3搜索功能/4图片识别
                    # logger.debug('功能:' + role['name'] + ':' + role['key'])
                    if role['key'] == '0':  # 阿图智聊
                        group_name_white_list = conf().get("group_name_white_list", [])
                        if chat_group_name not in group_name_white_list:
                            group_name_white_list.append(chat_group_name)
                        conf().set("group_name_white_list", group_name_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == '1':  # 推文摘要
                        group_name_share_text_abstract_white_list = conf().get("group_name_share_text_abstract_white_list", [])
                        if chat_group_name not in group_name_share_text_abstract_white_list:
                            group_name_share_text_abstract_white_list.append(chat_group_name)
                        conf().set("group_name_share_text_abstract_white_list", group_name_share_text_abstract_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == '2':  # 图片储存
                        group_name_image_save_white_list = conf().get("group_name_image_save_white_list", [])
                        if chat_group_name not in group_name_image_save_white_list:
                            group_name_image_save_white_list.append(chat_group_name)
                        conf().set("group_name_image_save_white_list", group_name_image_save_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == '3':  # 搜索功能
                        group_web_search_white_list = conf().get("group_web_search_white_list", [])
                        if chat_group_name not in group_web_search_white_list:
                            group_web_search_white_list.append(chat_group_name)
                        conf().set("group_web_search_white_list", group_web_search_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == '4':  # 图片识别
                        group_image_process_white_list = conf().get("group_image_process_white_list", [])
                        if chat_group_name not in group_image_process_white_list:
                            group_image_process_white_list.append(chat_group_name)
                        conf().set("group_image_process_white_list", group_image_process_white_list)  # 更新到全局配置文件
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
                logger.debug('群名:' + record['chatGroupName'])  # chatGroupName: 群名
                chat_group_name = record['chatGroupName']

                if 'vectordbName' in record and (record['vectordbName'] != ''):
                    logger.debug('向量库名:' + record['vectordbName'])  # vectordbName: 向量库名
                    logger.debug('向量表名:' + record['vectordbCollection'])  # vectordbCollection: 向量表名
                    group_chat_using_private_vector_db = conf().get("group_chat_using_private_vector_db", [])
                    chat_group_name_exist = False
                    for vector_db_config in group_chat_using_private_vector_db:  # 遍历白名单中的群名
                        if chat_group_name in vector_db_config:  # 群名存在
                            vector_db_config[chat_group_name]['database'] = record['vectordbName']
                            vector_db_config[chat_group_name]['collection'] = record['vectordbCollection']
                            chat_group_name_exist = True
                            break
                    if not chat_group_name_exist:  # 群名不在白名单中，则新增向量库配置
                        group_chat_using_private_vector_db.append({chat_group_name: {'database': record['vectordbName'], 'collection': record['vectordbCollection']}})
                    conf().set("group_chat_using_private_vector_db", group_chat_using_private_vector_db)  # 更新到全局配置文件

                # 更新群聊欢迎语
                if 'welcomeMessage' in record and (record['welcomeMessage'] != '') and len(record['welcomeMessage']) > 0:
                    logger.debug('群聊' + chat_group_name + '指定的欢迎语:' + record['welcomeMessage'][0]['value'])
                    user_specified_guidance = conf().get("user_specified_guidance", [])
                    chat_group_name_exist = False
                    for user_specified_guidance_config in user_specified_guidance:  # 遍历白名单中的群名
                        if chat_group_name in user_specified_guidance_config:  # 群名存在
                            user_specified_guidance_config[chat_group_name] = record['welcomeMessage'][0]['value']
                            chat_group_name_exist = True
                            break
                    if not chat_group_name_exist:  # 群名不在白名单中，则新增欢迎语配置
                        user_specified_guidance.append({chat_group_name: record['welcomeMessage'][0]['value']})
                    conf().set("user_specified_guidance", user_specified_guidance)  # 更新到全局配置文件

                for role in record['role']:  # key: 0阿图智聊/1推文摘要/2图片储存/3搜索功能/4图片识别
                    # logger.debug('功能:' + role['name'] + ':' + role['key'])
                    if role['key'] == '0':  # 阿图智聊
                        group_name_white_list = conf().get("group_name_white_list", [])
                        if chat_group_name not in group_name_white_list:
                            group_name_white_list.append(chat_group_name)
                        conf().set("group_name_white_list", group_name_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == '1':  # 推文摘要
                        group_name_share_text_abstract_white_list = conf().get("group_name_share_text_abstract_white_list", [])
                        if chat_group_name not in group_name_share_text_abstract_white_list:
                            group_name_share_text_abstract_white_list.append(chat_group_name)
                        conf().set("group_name_share_text_abstract_white_list", group_name_share_text_abstract_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == '2':  # 图片储存
                        group_name_image_save_white_list = conf().get("group_name_image_save_white_list", [])
                        if chat_group_name not in group_name_image_save_white_list:
                            group_name_image_save_white_list.append(chat_group_name)
                        conf().set("group_name_image_save_white_list", group_name_image_save_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == '3':  # 搜索功能
                        group_web_search_white_list = conf().get("group_web_search_white_list", [])
                        if chat_group_name not in group_web_search_white_list:
                            group_web_search_white_list.append(chat_group_name)
                        conf().set("group_web_search_white_list", group_web_search_white_list)  # 更新到全局配置文件
                        pass
                    elif role['key'] == '4':  # 图片识别
                        group_image_process_white_list = conf().get("group_image_process_white_list", [])
                        if chat_group_name not in group_image_process_white_list:
                            group_image_process_white_list.append(chat_group_name)
                        conf().set("group_image_process_white_list", group_image_process_white_list)  # 更新到全局配置文件
                        pass
        elif msg.topic == f"/sys/message/push":  # 服务器消息下发
            data = json.loads(str(msg.payload.decode('utf-8')))  # 字符串转字典
            msgId = data['msgId']
            botId = data['botId']  # 机器人ID
            if botId != self.bot_id:  # 不是发给自己的消息，忽略
                return
            from lib import itchat
            for record in data['data']:
                chat_group_name = record['chatGroupName']
                msg_type = record['msgType']  # 消息类型：TEXT/IMAGE/VIDEO/FILE/SHARING/OTHER
                msg = record['msg']  # 消息内容
                logger.debug('/sys/message/push主题消息收到！群名:' + chat_group_name)  # chatGroupName: 群名
                target_rooms = itchat.search_chatrooms(name=chat_group_name)
                if len(target_rooms) > 0:  # 群名存在
                    if msg_type == 'SHARING':  # 文本消息
                        itchat.send_sharing(url=msg, toUserName=chat_group_name)
                        pass
        
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
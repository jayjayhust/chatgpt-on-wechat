# https://serper.dev/playground
# https://serper.dev/billing
# serper收费标准：收费最低档位50美金50000次（? QPS），大约1美金1000次=大约7.32元1000次，即￥0.00732一次搜索
# 对比bing search的收费标准：S3标准对应18美金1000次调用（100 QPS）
# google search的收费标准(https://serpapi.com/pricings)：DEVELOPER对应50美金5000次调用（Monthly），即1美金100次调用=大约7.32元100次

# -*- coding: utf-8 -*-

import requests
import json
import hashlib
from config import conf
from common.log import logger

def generate_short_url(original_url):
    hash = hashlib.sha1(original_url.encode())
    short_url = hash.hexdigest()[:8]
    return short_url


class serper_search(object):
    def __init__(self):
        self.subscription_key = conf().get("serpapi_search_subscription_key", "")
        pass
        
    def search(self, query):
        # Construct a request
        url = "https://google.serper.dev/search"

        payload = json.dumps({
            "q": query,
            "gl": "cn",
            "hl": "zh-cn"
        })
        headers = {
            'X-API-KEY': '70e8690681658bd61863d36450299c44483ea57e',  # 这里要从环境变量加载，避免泄漏
            'Content-Type': 'application/json'
        }
        
        # Call the API
        result = []  # list
        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            # 结果形如（2024年1月13如搜索）：
            # {
            #   "searchParameters": {
            #     "q": "嵌入式社区怎么做？",
            #     "gl": "cn",
            #     "hl": "zh-cn",
            #     "num": 10,
            #     "autocorrect": true,
            #     "page": 1,
            #     "type": "search",
            #     "engine": "google"
            #   },
            #   "organic": [
            #     {
            #       "title": "社区嵌入式服务如何“见缝插针”？ - 新闻频道- 央视网",
            #       "link": "https://news.cctv.com/2024/01/05/ARTIMv5wrM8NJTh8rYODDKEM240105.shtml",
            #       "snippet": "而社区服务设施之所以是嵌入式，就在于需要在既有社区建筑和布局的基础上做“微创手术”，实现利旧改造，尽可能通过小手术实现大用途。这个过程中，也不难 ...",
            #       "date": "8天前",
            #       "position": 1
            #     },
            #     {
            #       "title": "从居民需求出发建设社区嵌入式服务设施 - 新华网",
            #       "link": "http://www.xinhuanet.com/comments/20231206/d99596fe9c1f44e0b5178a1f8a20b25d/c.html",
            #       "snippet": "嵌入不仅是硬件基础设施在社区空间的嵌入，也指这些服务设施的运营管理与服务提供等方面的柔性嵌入。因此，只有准确理解和把握嵌入的概念，才能真正做好 ...",
            #       "date": "2023年12月6日",
            #       "position": 2
            #     },
            #     {
            #       "title": "实施城市社区嵌入式服务设施建设工程：解决关键小事办好民生大事",
            #       "link": "https://www.gov.cn/zhengce/202311/content_6917757.htm",
            #       "snippet": "为做好两项工作衔接，我们采取了把完整社区建设重点放到社区服务设施上来、统筹协调社区服务设施建设标准、建立高效衔接的工作机制等措施。”住房城乡建设 ...",
            #       "date": "2023年11月30日",
            #       "position": 3
            #     },
            #     {
            #       "title": "发挥社区嵌入式服务设施效能从居民需求出发创新社区治理 - 人民网",
            #       "link": "http://finance.people.com.cn/n1/2023/1211/c1004-40136285.html",
            #       "snippet": "首先，要以城市为单位整体谋划推进，积极将社区嵌入式服务设施建设融入城市发展规划中。明确发展方向和整体体系设计，科学规划、合理布局，力求做到配置 ...",
            #       "date": "2023年12月11日",
            #       "position": 4
            #     },
            #     {
            #       "title": "相关部门解读城市社区嵌入式服务设施建设-新华网",
            #       "link": "http://www.news.cn/politics/2023-11/27/c_1129996142.htm",
            #       "snippet": "刘明还表示，为避免出现“建设轰轰烈烈，服务冷冷清清”，在综合借鉴各地发展社区嵌入式服务经验做法基础上，希望实现精准化服务、普惠化运营，通过市场化 ...",
            #       "date": "2023年11月27日",
            #       "position": 5
            #     },
            #     {
            #       "title": "嵌入式可以做什么 - Worktile",
            #       "link": "https://worktile.com/kb/p/62236",
            #       "snippet": "嵌入式是用于控制、监视或者辅助操作机器和设备的装置。嵌入式是一种专用的计算机系统，作为装置或设备的一部分。嵌入式是才发展起来的一项IT开发技术 ...",
            #       "date": "2023年7月28日",
            #       "position": 6
            #     },
            #     {
            #       "title": "最好的嵌入式开发技术学习与交流平台 - 电子发烧友论坛",
            #       "link": "https://bbs.elecfans.com/forum.php?gid=3",
            #       "snippet": "... 嵌入式领域做到优秀 · 版块. 技术社区. FPGA开发者技术社区 RISC-V MCU技术社区 HarmonyOS技术社区 瑞芯微Rockchip开发者社区 OpenHarmony开源社区 RT-Thread嵌入式技术 ...",
            #       "position": 7
            #     },
            #     {
            #       "title": "单片机、嵌入式的大神都平时浏览什么网站？ - 知乎",
            #       "link": "https://www.zhihu.com/question/26475816",
            #       "snippet": "0.综合网站 · 1.基础学习（C/C++，QT上位机等） · 2.单片机学习（主要是stm32，其他芯片类似） · 3.嵌入式Linux学习 · 4.电子类论坛（看 ...",
            #       "date": "2014年11月4日",
            #       "position": 8
            #     },
            #     {
            #       "title": "我国将开展城市社区嵌入式服务设施建设 - 中国政府网",
            #       "link": "https://www.gov.cn/zhengce/202312/content_6918475.htm",
            #       "snippet": "城市社区嵌入式服务设施，是指以社区（小区）为单位，通过新建或改造的方式，在社区（小区）公共空间嵌入功能性设施和适配性服务，为社区居民提供养老托育 ...",
            #       "date": "2023年12月5日",
            #       "position": 9
            #     },
            #     {
            #       "title": "每日一词|社区嵌入式服务设施community-level embedded service ...",
            #       "link": "http://cn.chinadaily.com.cn/a/202311/29/WS65668dc2a310d5acd8770c83.html",
            #       "snippet": "综合考虑人口分布、工作基础、财力水平等因素，选择50个左右城市开展试点，每个试点城市选择100个左右社区作为城市社区嵌入式服务设施建设先行试点项目。",
            #       "date": "2023年11月29日",
            #       "position": 10
            #     }
            #   ],
            #   "peopleAlsoAsk": [
            #     {
            #       "question": "嵌入式系统能做什么？",
            #       "snippet": "嵌入式系统通常应用于消费类、烹饪、工业、自动化、医疗、商业及军事领域。 从网络级的电话交换机到手机终端都部署了大量嵌入式系统。 包括PDA、MP3播放器、移动电话、游戏机、数位摄像机、DVD播放器、全球卫星定位系统接收器和打印机。",
            #       "title": "嵌入式系统- 维基百科，自由的百科全书",
            #       "link": "https://zh.wikipedia.org/zh-cn/%E5%B5%8C%E5%85%A5%E5%BC%8F%E7%B3%BB%E7%BB%9F"
            #     },
            #     {
            #       "question": "嵌入式是什么意思？",
            #       "snippet": "嵌入式是一种专用的计算机系统，作为装置或设备的一部分。 通常，嵌入式系统是一个控制程序存储在ROM中的嵌入式处理器控制板。 事实上，所有带有数字接口的设备，如手表、微波炉、录像机、汽车等，都使用嵌入式系统，有些嵌入式系统还包含操作系统，但大多数嵌入式系统都是是由单个程序实现整个控制逻辑。",
            #       "title": "嵌入式开发_百度百科",
            #       "link": "https://baike.baidu.com/item/%E5%B5%8C%E5%85%A5%E5%BC%8F%E5%BC%80%E5%8F%91/86149"
            #     }
            #   ]
            # }

            logger.debug(response.text)
            result = []  # list
            resultList = json.loads(response.text)["organic"]
            for item in resultList:
                record = {}  # dict
                record['name'] = item['title']
                record['URL'] = item['link']
                record['description'] = item['snippet']
                if 'date' in item:
                    record['datePublished'] = item['date']
                else:
                    record['datePublished'] = ''
                result.append(record)
            return result, 'webPages'

        except Exception as ex:
            raise ex
    

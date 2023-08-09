# https://chenzy96.github.io/2018/12/07/%E5%BE%AE%E4%BF%A1%E5%85%AC%E4%BC%97%E5%8F%B7%E6%96%87%E7%AB%A0%E7%88%AC%E5%8F%96%E5%AE%9E%E6%88%98/
# https://github.com/ChenZY96/SpiderStudy/blob/master/WeChat2.py

### Import 
import requests
from pyquery import PyQuery as pq
import random
import os
# import sys
# import pinecone
from openai.embeddings_utils import get_embedding
# from tqdm import tqdm
import os
import openai


openai.api_key = os.environ.get('OPENAI_API_KEY')
url = 'https://mp.weixin.qq.com/s?__biz=MTMwNDMwODQ0MQ==&amp;mid=2653006323&amp;idx=1&amp;sn=f94d990fb21c48dbe624ca8af797dd95&amp;chksm=7e54d44549235d537b71936385034f57c43dbd6cc166624e025addd2916cd619cb64ea3aaa17&amp;mpshare=1&amp;scene=24&amp;srcid=0808Er0VbXRrVDMDPe7odDI2&amp;sharer_sharetime=1691469790478&amp;sharer_shareid=5f20824cdd249b7ae9706d1e450be83b#rd'
# url = 'https://mp.weixin.qq.com/s/nyp8BaZqEKYm0jHHsHwIUQ'
# url = sys.argv[1]


class text_abstract(object):
    def __init__(self):
        pass
        
        
    def get_web_text(self, url):
        headers = [
            {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:34.0) Gecko/20100101 Firefox/34.0'},
            {'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6'},
            {'User-Agent': 'Mozilla/5.0 (Windows NT 6.2) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.12 Safari/535.11'},
            {'User-Agent': 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0)'},
            {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:40.0) Gecko/20100101 Firefox/40.0'},
            {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/44.0.2403.89 Chrome/44.0.2403.89 Safari/537.36'}
        ]

        response = requests.get(url, headers=random.choice(headers))
        if response.status_code != 200:
            print('ERROR')
            exit(0)
        doc = pq(response.text)

        # 文章标题
        title = doc.find('.rich_media_title').text()
        # 微信公众号
        author = doc.find('#meta_content .rich_media_meta_text').text()
        source = doc.find('#js_name').text()
        source_info = doc.find('.profile_meta_value').text()

        print('*' * 100)
        print(title, author, source)
        print('*' * 100)
        print(source_info)

        # 正文内容
        content = doc.find('.rich_media_content')

        # PMA(主成分分析，确定)
        print('*' * 100)
        print('<span> number: ', content.find('span').length)  # 有的文章，文本主要放在span标签内
        span_pure_text = ''
        for item in content.find('span').items():
            span_pure_text += str(item.text()) + '\n'
        print('*' * 100)
        print('<span> text in total: ', len(span_pure_text)) 
        print('*' * 100)
        print('<p> number: ', content.find('p').length)  # 有的文章，文本主要放在p标签内
        p_pure_text = ''
        for item in content.find('p').items():
            p_pure_text += str(item.text()) + '\n'
        print('*' * 100)
        print('<p> text in total: ', len(p_pure_text)) 

        content_pure_text = ''
        if len(span_pure_text) > len(p_pure_text):
            content_pure_text = span_pure_text
        elif len(p_pure_text) > len(span_pure_text):
            content_pure_text = p_pure_text
        
        return content_pure_text
    

    def get_text_abstract(self, query):
        prompt = "《清华团队领衔打造，首个AI agent系统性基准测试问世》 摘要如下：\
          ▎一句话描述 \
          清华大学、俄亥俄州立大学、加州大学伯克利分校的研究团队提出了首个系统性的基准测试——AgentBench，用来评估 LLMs 作为智能体在各种真实世界挑战和8个不同环境中的表现。\
          ▎文章略读 \
          1. AgentBench是一个用于评估LLMs作为代理在各种真实世界挑战和8个不同环境中的表现的系统性基准测试。 \
          2. 测试结果显示，像GPT-4这样的顶尖模型能够处理各种各样的现实世界任务，而大多数开源LLMs在AgentBench中的表现远远不及基于API的LLMs。 \
          3. 研究团队建议，有必要进一步努力提高开源LLMs的学习能力。 \
          4. AI代理已经展现出了巨大潜力和市场，第一批能够可靠地执行多步骤任务并具备一定自主能力的系统将在一年内上市。 \
          5. 随着时间的推移，我们有望在不断优化和完善中见证这些AI代理为人类社会带来积极而深远的影响。 \
          原文共2485字，阅读需4分钟"
        prompt += "你现在角色是一位阅读小助手，负责给一段文章生成摘要。请按照以上摘要模板，给下面这段文字，生成一段摘要300~500字左右，再生成一段略读列出文章中最重要的几点："
        prompt += "\n"
        prompt += query
        print(prompt)
        print('*' * 100)
        res = openai.ChatCompletion.create(
            messages = [{"role": "user", "content": prompt}],
            model="gpt-3.5-turbo-16k"
        )
      
        return res.choices[0].message.content

# REF URL: https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/overview
# REF URL: https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/quickstarts/rest/python
# REF URL: https://github.com/microsoft/bing-search-sdk-for-python/blob/main/samples/rest/BingWebSearchV7.py

# -*- coding: utf-8 -*-

import json
import os
from pprint import pprint
import requests
import hashlib
from config import conf

def generate_short_url(original_url):
    hash = hashlib.sha1(original_url.encode())
    short_url = hash.hexdigest()[:8]
    return short_url

'''
This sample makes a call to the Bing Web Search API with a query and returns relevant web search.
Documentation: https://docs.microsoft.com/en-us/bing/search-apis/bing-web-search/overview
'''

# Add your Bing Search V7 subscription key and endpoint to your environment variables.
# subscription_key = os.environ['BING_SEARCH_V7_SUBSCRIPTION_KEY']
# endpoint = os.environ['BING_SEARCH_V7_ENDPOINT'] + "/v7.0/search"


class bing_search(object):
    def __init__(self):
        self.subscription_key = conf().get("bing_search_subscription_key", "")
        self.endpoint = conf().get("bing_search_endpoint", "")
        pass
        
    def search(self, query):
        # Construct a request
        # mkt = 'en-US'
        mkt = 'zh-CN'
        params = { 'q': query, 'mkt': mkt }
        headers = { 'Ocp-Apim-Subscription-Key': self.ubscription_key }
        
        # Call the API
        result = []  # list
        try:
            response = requests.get(self.endpoint, headers=headers, params=params)
            response.raise_for_status()

            # print('*' * 100)
            # print("\nHeaders:\n")
            # print(response.headers)
            # print('*' * 100)
            # print("\nJSON Response:\n")
            # pprint(response.json())

            response.raise_for_status()
            search_results = response.json()
            news = search_results['news']['value']
            record = {}
            for item in news:
                # print('*' * 100)
                # print('name:', item['name'])
                # print('URL:', item['url'])
                # print('short URL hash id:', generate_short_url(item['url']))  # https://zhuanlan.zhihu.com/p/615395446（形如ff72b514）
                # print('description:', item['description'])
                # print('datePublished:', item['datePublished'])
                record['name'] = item['name']
                record['URL'] = item['url']
                record['description'] = item['description']
                record['datePublished'] = item['datePublished']
                result.append(record)
            return result
        except Exception as ex:
            raise ex
    

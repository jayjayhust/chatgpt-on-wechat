# REF URL: https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/overview
# REF URL: https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/quickstarts/rest/python
# REF URL: https://github.com/microsoft/bing-search-sdk-for-python/blob/main/samples/rest/BingWebSearchV7.py
# PRICE: https://www.microsoft.com/en-us/bing/apis/pricing
# Query Usage: https://portal.azure.com/#@jayhust163.onmicrosoft.com/resource/subscriptions/5a315ee5-b0f3-477a-ad90-4040c291594c/overview

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
        headers = { 'Ocp-Apim-Subscription-Key': self.subscription_key }
        
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
            if 'news' in search_results:
                news = search_results['news']['value']
                for item in news:
                    record = {}  # dict
                    record['name'] = item['name']
                    record['URL'] = item['url']
                    record['description'] = item['description']
                    if 'datePublished' in item:
                        record['datePublished'] = item['datePublished']
                    else:
                        record['datePublished'] = ''
                    result.append(record)
                return result, 'news'
            elif 'webPages' in search_results:
                webpages = search_results['webPages']['value']
                for item in webpages:
                    record = {}  # dict
                    record['name'] = item['name']
                    record['URL'] = item['displayUrl']
                    record['description'] = item['snippet']
                    if 'datePublished' in item:
                        record['datePublished'] = item['datePublished']
                    else:
                        record['datePublished'] = ''
                    result.append(record)
                return result, 'webPages'
        except Exception as ex:
            raise ex
    

'''
Author: mfuture@qq.com
Date: 2021-04-27 11:38:22
Description: 特定科室下疾病内容的爬取
'''
import scrapy
import time  # 引入time模块
import logging

from jbk39.items import Jbk39Item
import json
from jbk39.lib.common import StrFunc
import re

from jbk39.lib.service import DatabaseService as db


from jbk39.lib.parse import FineParse as fp


global count, resend
count = 0

resend = 0  # 重发请求


# https://jbk.39.net/hnxpqxsjmy/

# 外阴乳头状瘤

class jbk39(scrapy.Spider):  # 需要继承scrapy.Spider类

    name = "disease_archive"  # 定义蜘蛛名

    custom_settings = {
        "DOWNLOAD_DELAY": 0.05,  # 覆盖settings 里面的载延迟 ， 利用代理时本身就有较大的延迟，所以此处可以设置小一点，不用担心被封
        "JOBDIR": './jobs/{}'.format(name),
        "USE_IP_PROXY": False
    }

    # step1: 开始请求
    def start_requests(self):

        print('--start request--')

        # self.parse_paragraph_l3(data)

        # return

        departments = db.select_department(['fuke'])

        base_url = "https://jbk.39.net/bw/"

        for department in departments:

            # 定义爬取的链接
            pinyin = department["pinyin"]
            url = '{}{}_t1/'.format(base_url, department["pinyin"])
            meta = {"base_url": base_url, "pinyin": pinyin}
            yield scrapy.Request(url=url, meta=meta, callback=self.init_parse)

    # step2: 获取疾病分页
    def init_parse(self, response):

        base_url = "{}{}_t1_p".format(
            response.meta["base_url"], response.meta["pinyin"])

        print('--init request--')

        pages = response.xpath(
            '//ul[@class="result_item_dots"]/li/span[last()-1]/a/text()')

        # 有页面数据
        if len(pages) > 0:
            pages = int(pages.extract()[0])
        else:
            pages = 1
            # raise ValueError("no page  count found.")

        # NOTE: 当分页数超过100时，能爬到的数据并不相同
        for i in range(pages):
            # step2.2: 请求某一分页
            url = "{}{}".format(base_url, str(i+1))
            yield scrapy.Request(url=url, meta=response.meta, callback=self.parse)

    # step3: 获取某一分页的所有疾病
    def parse(self, response):

        print('--start parse--')

        global resend

        # 获取某一页面下 某疾病 子项目的 url
        diseaseUrls = response.xpath('//*[@class="result_item_top_l"]')

        # 没有数据，重发请求
        if len(diseaseUrls) == 0:
            resend = resend+1
            if resend < 3:  # 因为有些科室本来就没有疾病,比如 https://jbk.39.net/bw/heyixueke_t1_p1
                self.logger.error(
                    "NO available data found from:{}, will try again.".format(response.url))
                time.sleep(1)
                yield scrapy.Request(url=response.url, meta=response.meta, dont_filter=True, callback=self.parse)
                return

        for item in diseaseUrls:
            # 该病的url，比如 "https://jbk.39.net/jxzgnmy/"

            link = item.xpath('a/@href').extract()[0]

            response.meta['url'] = link

            # # NOTE: 诊断，初始添加，先运行这里
            # yield scrapy.Request(url=link + 'jb', meta=response.meta, callback=self.diagnosis_parse)

            # 简介
            yield scrapy.Request(url=link + 'jbzs', meta={'url': link}, callback=self.intro_parse)

            # # 治疗
            # yield scrapy.Request(url=link + 'yyzl', callback=self.treat_parse)

            # # 症状
            # yield scrapy.Request(url=link + 'zztz', meta=response.meta, callback=self.symptom_parse)

            # # 病因
            # yield scrapy.Request(url=link + 'blby', callback=self.cause_parse)

            # # 预防
            # yield scrapy.Request(url=link + 'yfhl', callback=self.prevention_parse)

    # ==============================  step4: 以下均为页面解析  =============================

    # 简介

    def intro_parse(self, response):

        print('疾病基本信息-----')

        item = Jbk39Item()
        name = response.xpath('//div[@class="disease"]/h1/text()').extract()[0]
        intro = response.xpath('//p[@class="introduction"]').extract()[0]

        # 概述
        summary = {}

        elements = response.xpath('.//ul[@class="disease_basic"]/li')

        for ele in elements:
            key = ele.xpath('./span/text()').extract()[0].replace(u'：', u'')
            value = list(map(lambda x:  StrFunc().str_format(x), ele.xpath('./span[position()>1]/a | ./span[position()>1]/text() \
                | ./span[position()>1]/span/text() | ./span[position()>1]/p/text()').extract()))
            value = list(
                filter(lambda x: x not in ('', '[', ']', '详细'), value))
            summary[key] = value

        item['intro'] = StrFunc().str_format(intro)
        item['url'] = StrFunc().str_format(response.meta['url'])
        item['summary'] = json.dumps(summary, ensure_ascii=False)
        item['classify'] = 'disease:intro'
        item['name'] = name
        yield item

    # 治疗
    def treat_parse(self, response):

        item = Jbk39Item()

        name = response.xpath('//div[@class="disease"]/h1/text()').extract()[0]

        path = '//div[@class="article_paragraph"]/p'

        treatment = fp().parse_item_treatment(response, path)

        # 西医治疗
        common_treat = {}
        chinese_med_treat = {}

        child = treatment['children']

        if len(child) == 1:
            title_content = child[0]['title']+child[0]['content']
            if re.search(r'(辩证)|(中医)', title_content):
                common_treat = []
                chinese_med_treat = child[0]
            else:
                common_treat = child[0]
                chinese_med_treat = []

        elif len(child) == 2:
            common_treat = child[0]
            chinese_med_treat = child[1]

        item["common_treat"] = common_treat
        item["chinese_med_treat"] = chinese_med_treat
        item['classify'] = 'disease:treat'
        item['name'] = name

        yield item

    # 症状
    def symptom_parse(self, response):
        global count

        item = Jbk39Item()

        name = response.xpath('//div[@class="disease"]/h1/text()').extract()[0]

        symptom = []
        text_lists_symptom = response.xpath(
            '//div[@class="article_box"]//p').extract()

        for text in text_lists_symptom:
            mystr = StrFunc().str_format(text)
            symptom.append(mystr)

        count = count+1
        print('symptom count: {}'.format(count))

        item["symptom"] = symptom
        item['classify'] = 'disease:symptom'
        item['name'] = name

        yield item

    # 病因
    def cause_parse(self, response):

        item = Jbk39Item()

        name = response.xpath('//div[@class="disease"]/h1/text()').extract()[0]

        cause = []
        text_lists_cause = response.xpath(
            '//div[@class="article_box"]//p').extract()

        for text in text_lists_cause:
            mystr = StrFunc().str_format(text)
            cause.append(mystr)

        item["cause"] = cause
        item['classify'] = 'disease:cause'
        item['name'] = name

        yield item

    # 预防
    def prevention_parse(self, response):

        item = Jbk39Item()

        name = response.xpath('//div[@class="disease"]/h1/text()').extract()[0]

        prevention = []
        path = '//div[@class="article_paragraph"]/p'

        prevention = fp().parse_item_identify(response, path, '预防')['children'][0]

        item["prevention"] = prevention
        item['classify'] = 'disease:prevention'
        item['name'] = name

        yield item

    # 鉴别（诊断）
    def diagnosis_parse(self, response):
        # print('goto diagnosis_parse')
        item = Jbk39Item()

        # 疾病名称
        name = response.xpath('//div[@class="disease"]/h1/text()').extract()[0]

        # 鉴别
        identify = []  # 鉴别

        path = '//div[@class="article_paragraph"]/p'

        identify = fp().parse_item_identify(response, path, '鉴别')['children'][0]

        # 诊断
        diagnosis = []

        path = '//div[@class="art-box"]/p'

        diagnosis = fp().parse_item_identify(response, path, '诊断')['children'][0]

        item["name"] = name
        item['department'] = response.meta["pinyin"]
        item["identify"] = identify
        item["diagnosis"] = diagnosis
        item['classify'] = 'disease:diagnosis'

        yield item
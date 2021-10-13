import scrapy
import time  # 引入time模块
import logging

from jbk39.items import Jbk39Item
import json

CRAWL_INTERVAL= 0.5 #睡眠时间，反爬


class jbk39(scrapy.Spider):  # 需要继承scrapy.Spider类

    name = "fuke"  # 定义蜘蛛名

    # step1: 开始请求妇科疾病
    def start_requests(self):
        # 定义爬取的链接
        base_url = 'https://jbk.39.net/bw/fuke_t1/'  # 疾病
        yield scrapy.Request(url=base_url, callback=self.init_parse)
    
    # step2: 获取妇科疾病分页
    def init_parse(self, response):

        print('goto init_parse')

        pages=response.xpath('//ul[@class="result_item_dots"]/li/span[last()-1]/a/text()')[0].extract()

        for i in range(int(pages)):
            url = 'https://jbk.39.net/bw/fuke_t1_p' + str(i+1)
            # step2.2: 请求某一分页
            yield scrapy.Request(url=url, callback=self.parse)

    # step3: 获取某一分页的所有疾病
    def parse(self, response):

        time.sleep(CRAWL_INTERVAL)  
        print('goto parse ')

        links_intro = []
        links_treat = []
        links_diagnosis = []

        # 获取子项目的 url
        diseaseUrls=response.xpath('//*[@class="result_item_top_l"]')
        for item in diseaseUrls:
            link = item.xpath('a/@href').extract()[0] # 该病的url，比如 "https://jbk.39.net/jxzgnmy/"
            links_intro.append(link + 'jbzs') #简介
            links_treat.append(link + 'yyzl') #治疗
            links_diagnosis.append(link + 'jb') #鉴别（诊断）

        # for link in links_intro:
        #     yield scrapy.Request(url=link, callback=self.intro_parse)
		
        for link in links_treat:
            yield scrapy.Request(url=link, callback=self.treat_parse)
		
		
        # for link in links_diagnosis:
        #      # step3.2: 向相应疾病页面发送请求
        #     yield scrapy.Request(url=link, callback=self.diagnosis_parse)


    # ==============================  step4: 以下均为页面解析  =============================

    # 简介
    def intro_parse(self, response):

        time.sleep(CRAWL_INTERVAL)
        print('goto intro_parse ')

        # 一定要搞清楚路径，你在第一层根目录下
        fs=open('fuke_step4_intro.html','w')
        fs.write(response.body.decode())
        fs.close()

        item = Jbk39Item()      
        name = response.xpath('//div[@class="disease"]/h1/text()').extract()
        intro = response.xpath('//p[@class="introduction"]/text()').extract()
        txt = response.xpath('//span[@class="disease_basic_txt"]/text()').extract()

        alias = txt[1] if len(txt) > 1 else ''
        
        item['name'] = name[0]
        item['intro'] = intro[0]
        item['alias'] = alias.strip()
        item['department'] = '妇科'
        item['classify'] = 'intro'
        yield item

    # 治疗
    def treat_parse(self, response):

        time.sleep(CRAWL_INTERVAL)  
        print('goto treat_parse')

        item = Jbk39Item()

        name = response.xpath('//div[@class="disease"]/h1/text()').extract()[0]

        common_treat = []
        chinese_med_treat = []
        flag = 1  # 1、西医治疗； 2、中医治疗
        text_lists = response.xpath('//p[@class="article_name"]/text() | //p[@class="article_content_text"]/text()').extract()

        for text in text_lists:

            mystr = str(text.replace(u'\u3000', u''))

            if mystr.find('中医治疗') >= 0:
                flag = 2

            if mystr.find("西医治疗") < 0 and mystr.find("中医治疗") < 0:

                if flag == 1:
                    common_treat.append(mystr)
                else:
                    chinese_med_treat.append(mystr)

        item["common_treat"] = common_treat
        item["chinese_med_treat"] = chinese_med_treat
        item['department'] = '妇科'
        item["name"] = name
        item['classify'] = 'treat'

        yield item


    # 鉴别（诊断）
    def diagnosis_parse(self, response):


        
        # 一定要搞清楚路径，你在第一层根目录下
        fs=open('fuke_step4_jb.html','w')
        fs.write(response.body.decode())
        fs.close()

        time.sleep(CRAWL_INTERVAL)   
        print('goto diagnosis_parse')
        item = Jbk39Item()

        # 疾病名称
        name = response.xpath('//div[@class="disease"]/h1/text()').extract()[0]
        diagnosis = [] # 诊断
        identify = [] # 鉴别

        text_lists_diagnosis = response.xpath('//div[@class="art-box"]/p/text() | //div[@class="art-box"]/p/*/text() ').extract()
        text_lists_identify = response.xpath('//div[@class="article_paragraph"]/p/text() | //div[@class="article_paragraph"]/p/*/text() ').extract()

        for text in text_lists_diagnosis:
            mystr = str(text.replace(u'\u3000', u'')) # \u3000 全角空白符
            diagnosis.append(mystr)

        for text in text_lists_identify:
            mystr = str(text.replace(u'\u3000', u''))
            identify.append(mystr)

        item["diagnosis"] = diagnosis
        item["identify"] = identify
        item["name"] = name
        item['department'] = '妇科'
        item['classify'] = 'diagnosis'

        yield item

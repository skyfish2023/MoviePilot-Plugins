import re
from typing import List, Tuple
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup
from http.cookies import SimpleCookie
from app.core.config import settings
from app.core.meta import MetaBase
from app.helper.cookiecloud import CookieCloudHelper
from app.log import logger
from app.utils.http import RequestUtils


class DoubanHelper:

    def __init__(self, user_cookie: str = None):
        if not user_cookie:
            self.cookiecloud = CookieCloudHelper()
            cookie_dict, msg = self.cookiecloud.download()
            if cookie_dict is None:
                logger.error(f"获取cookiecloud数据错误 {msg}")
            self.cookies = cookie_dict.get("douban.com")
        else:
            self.cookies = user_cookie
        self.cookies = {k: v.value for k, v in SimpleCookie(self.cookies).items()}
        if self.cookies.get('__utmz'):
            self.cookies.pop("__utmz")
        self.ck = self.cookies.get('ck') or ""
        logger.debug(f"ck:{self.ck} cookie:{self.cookies}")

        if not self.cookies or not self.ck:
            logger.error(f"豆瓣cookie错误 ck:{self.ck if self.ck else 'cookie提取ck获取失败'} cookies:{self.cookies}")
        self.headers = {
            'User-Agent': settings.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4,en-GB;q=0.2,zh-TW;q=0.2',
            'Connection': 'keep-alive',
            'DNT': '1',
            'HOST': 'www.douban.com'
        }

    def get_subject_id(self, title: str = None, meta: MetaBase = None) -> Tuple | None:
        if not title:
            title = meta.title
            year = meta.year
        url = f"https://www.douban.com/search?cat=1002&q={title}"
        response = RequestUtils(headers=self.headers).get_res(url)
        if not response.status_code == 200:
            logger.error(f"搜索 {title} 失败 状态码：{response.status_code}")
            return None
        # self.headers["Cookie"] = response.cookies
        soup = BeautifulSoup(response.text.encode('utf-8'), 'lxml')
        title_divs = soup.find_all("div", class_="title")
        subject_items: List = []
        # 遍历所有找到的div标签
        for div in title_divs:
            item = {}

            # title
            a_tag = div.find_all("a")[0]
            item["title"] = a_tag.string
            item["title"] = item["title"].strip()

            # year 原名:피라미드 게임 / 朴昭妍 / 金知妍 / 2024
            span_tag = div.find_all(class_="subject-cast")[0]
            year: str = span_tag.string[-4:]
            if year.isdigit():
                item["year"] = year

            # subject_id
            link = unquote(a_tag["href"])
            if link.count("subject/"):
                pattern = r"subject/(\d+)/"
                match = re.search(pattern, link)
                if match:
                    subject_id = match.group(1)
                    item["subject_id"] = subject_id
            subject_items.append(item)

        if not subject_items:
            logger.error(f"找不到 {title} 相关条目 搜索结果html:{response.text.encode('utf-8')}")
        for subject_item in subject_items:
            logger.debug(f"{subject_item['title']} {subject_item['subject_id']}")
            return subject_item["title"], subject_item["subject_id"]
        return None, None

    def set_watching_status(self, subject_id: str, status: str = "do", private: bool = True) -> bool:
        self.headers["Referer"] = f"https://movie.douban.com/subject/{subject_id}/"
        self.headers["Origin"] = "https://movie.douban.com"
        self.headers["Host"] = "movie.douban.com"
        self.headers["Cookie"] = ";".join([f"{key}={value}" for key, value in self.cookies.items()])
        data_json = {
            "ck": self.ck,
            "interest": "do",
            "rating": "",
            "foldcollect": "U",
            "tags": "",
            "comment": ""
        }
        if private:
            data_json["private"] = "on"
        data_json["interest"] = status
        response = requests.post(
            url=f"https://movie.douban.com/j/subject/{subject_id}/interest",
            headers=self.headers,
            data=data_json)
        if not response:
            return False
        if response.status_code == 200:
            logger.debug(response.text)
            return True
        logger.error(response.text)
        return False


if __name__ == "__main__":
    doubanHelper = DoubanHelper()
    subject_title, subject_id = doubanHelper.get_subject_id("秘密森林2")
    doubanHelper.set_watching_status(subject_id=subject_id, status="do", private=True)

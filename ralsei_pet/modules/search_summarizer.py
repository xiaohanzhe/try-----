import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote_plus

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入
    import logging

    def get_logger(name):
        return logging.getLogger(name)

_log = get_logger(__name__)

# 搜索结果数量上下限（过大拖慢请求且易被搜索引擎限流，过小无意义）
MIN_RESULTS = 1
MAX_RESULTS = 20


class SearchSummarizer:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    @staticmethod
    def _clamp_num_results(num_results):
        """修复：num_results 原先无范围校验，0/负数会直接拼进 URL。"""
        try:
            num_results = int(num_results)
        except (TypeError, ValueError):
            return 5
        return max(MIN_RESULTS, min(num_results, MAX_RESULTS))

    def _fetch_results(self, url, container_selector, title_tag, desc_class):
        """通用结果抓取：请求 → 解析 → 提取 (title, link, description) 列表。

        修复：原先 search_google / search_bing 各写一份几乎相同的抓取代码（重复编码），
        现在收敛为一个方法，两边只传选择器差异。
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
        except Exception as e:
            _log.warning("搜索请求失败 %s: %s", url, e)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for result in soup.find_all(*container_selector):
            title = result.find(title_tag)
            if not title:
                continue
            title = title.text.strip()

            link_el = result.find("a")
            if not link_el:
                continue
            # 修复：<a> 无 href 时 link.get("href") 返回 None，拼接输出会出现 "链接：None"
            link = link_el.get("href") or ""

            desc_el = result.find("div", class_=desc_class)
            description = desc_el.text.strip() if desc_el else ""

            results.append({"title": title, "link": link, "description": description})
        return results

    def search_google(self, query, num_results=5):
        """搜索 Google 并返回搜索结果"""
        num_results = self._clamp_num_results(num_results)
        # 修复：对查询参数进行 URL 编码，避免含特殊字符（空格、中文、&等）时 URL 出错
        url = f"https://www.google.com/search?q={quote_plus(query)}&num={num_results}"
        return self._fetch_results(url, ("div", "g"), "h3", "VwiC3b")[:num_results]

    def search_bing(self, query, num_results=5):
        """搜索 Bing 并返回搜索结果"""
        num_results = self._clamp_num_results(num_results)
        # 修复：对查询参数进行 URL 编码
        url = f"https://www.bing.com/search?q={quote_plus(query)}&count={num_results}"
        return self._fetch_results(url, ("li", "b_algo"), "h2", "b_caption")[:num_results]

    def _search_any(self, query, num_results):
        """Google 优先、失败回退 Bing 的统一搜索入口。

        修复：原先 summarize_search_results / get_brief_summary 各写一份
        "先 Google 后 Bing" 的回退逻辑（重复编码），现在收敛。
        """
        results = self.search_google(query, num_results)
        if not results:
            results = self.search_bing(query, num_results)
        return results

    def summarize_search_results(self, query, num_results=3):
        """搜索并总结结果"""
        num_results = self._clamp_num_results(num_results)
        results = self._search_any(query, num_results)

        if not results:
            return f"抱歉，我无法搜索到关于'{query}'的内容。"

        summary = f"关于'{query}'的搜索结果：\n"

        for i, result in enumerate(results, 1):
            summary += f"\n{i}. {result['title']}\n"
            summary += f"   {result['description'][:150]}{'...' if len(result['description']) > 150 else ''}\n"
            summary += f"   链接：{result['link'] or '（无链接）'}\n"

        return summary

    def get_brief_summary(self, query):
        """获取简短的搜索总结，适合口语表达"""
        results = self._search_any(query, 3)

        if not results:
            return f"抱歉，我没找到关于'{query}'的信息。"

        summary = f"关于'{query}'，我找到了这些信息：\n"

        for i, result in enumerate(results, 1):
            # 提取关键词
            keywords = self._extract_keywords(result['title'] + " " + result['description'])
            summary += f"\n{i}. {result['title'][:50]}{'...' if len(result['title']) > 50 else ''}\n"
            summary += f"   主要内容：{keywords[:100]}{'...' if len(keywords) > 100 else ''}\n"

        return summary

    def _extract_keywords(self, text):
        """提取文本中的关键词"""
        # 简单的关键词提取，移除常见的停用词
        stop_words = set(["the", "and", "of", "to", "in", "a", "is", "it", "that", "for", "on", "with", "as", "by", "at", "from", "but", "or", "this", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "shall", "should", "can", "could", "may", "might", "must", "ought", "I", "you", "he", "she", "it", "we", "they", "them", "their", "his", "her", "its", "our", "your", "my", "me", "him", "her", "us", "you", "them"])

        # 移除标点符号
        text = re.sub(r'[^\w\s]', '', text)
        # 转换为小写
        text = text.lower()
        # 分割单词
        words = text.split()
        # 移除停用词和短单词
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        # 移除重复词
        keywords = list(set(keywords))
        # 限制数量
        return " ".join(keywords[:10])

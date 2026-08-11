import requests
from bs4 import BeautifulSoup
import re

class SearchSummarizer:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    
    def search_google(self, query, num_results=5):
        """
        搜索Google并返回搜索结果
        """
        try:
            url = f"https://www.google.com/search?q={query}&num={num_results}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            
            # 提取搜索结果
            for result in soup.find_all("div", class_="g")[:num_results]:
                # 提取标题
                title = result.find("h3")
                if not title:
                    continue
                title = title.text.strip()
                
                # 提取链接
                link = result.find("a")
                if not link:
                    continue
                link = link.get("href")
                
                # 提取描述
                description = result.find("div", class_="VwiC3b")
                if description:
                    description = description.text.strip()
                else:
                    description = ""
                
                results.append({
                    "title": title,
                    "link": link,
                    "description": description
                })
            
            return results
        except Exception as e:
            print(f"搜索失败: {e}")
            return []
    
    def search_bing(self, query, num_results=5):
        """
        搜索Bing并返回搜索结果
        """
        try:
            url = f"https://www.bing.com/search?q={query}&count={num_results}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            
            # 提取搜索结果
            for result in soup.find_all("li", class_="b_algo")[:num_results]:
                # 提取标题
                title = result.find("h2")
                if not title:
                    continue
                title = title.text.strip()
                
                # 提取链接
                link = result.find("a")
                if not link:
                    continue
                link = link.get("href")
                
                # 提取描述
                description = result.find("div", class_="b_caption")
                if description:
                    description = description.text.strip()
                else:
                    description = ""
                
                results.append({
                    "title": title,
                    "link": link,
                    "description": description
                })
            
            return results
        except Exception as e:
            print(f"Bing搜索失败: {e}")
            return []
    
    def summarize_search_results(self, query, num_results=3):
        """
        搜索并总结结果
        """
        # 首先尝试Google搜索
        results = self.search_google(query, num_results)
        
        # 如果Google搜索失败，尝试Bing
        if not results:
            results = self.search_bing(query, num_results)
        
        if not results:
            return f"抱歉，我无法搜索到关于'{query}'的内容。"
        
        # 生成总结
        summary = f"关于'{query}'的搜索结果：\n"
        
        for i, result in enumerate(results, 1):
            summary += f"\n{i}. {result['title']}\n"
            summary += f"   {result['description'][:150]}{'...' if len(result['description']) > 150 else ''}\n"
            summary += f"   链接：{result['link']}\n"
        
        return summary
    
    def get_brief_summary(self, query):
        """
        获取简短的搜索总结，适合口语表达
        """
        results = self.search_google(query, 3)
        
        if not results:
            results = self.search_bing(query, 3)
        
        if not results:
            return f"抱歉，我没找到关于'{query}'的信息。"
        
        # 生成简短总结
        summary = f"关于'{query}'，我找到了这些信息：\n"
        
        for i, result in enumerate(results, 1):
            # 提取关键词
            keywords = self._extract_keywords(result['title'] + " " + result['description'])
            summary += f"\n{i}. {result['title'][:50]}{'...' if len(result['title']) > 50 else ''}\n"
            summary += f"   主要内容：{keywords[:100]}{'...' if len(keywords) > 100 else ''}\n"
        
        return summary
    
    def _extract_keywords(self, text):
        """
        提取文本中的关键词
        """
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

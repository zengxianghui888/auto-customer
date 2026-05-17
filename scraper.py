import requests
import re
import random
import time
import pandas as pd
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup

# ==================== 配置区 ====================
YOUR_EMAIL = "mike@3csin.com"
QUALITY_LEVEL = 2
MAX_RESULTS = 100
MIN_DELAY = 5
MAX_DELAY = 10

BASE_COMMANDS = [
    "\"we import\" \"camping tents\" \"sleeping bags\" -manufacturer -factory -producer -retail -shop -store -alibaba -china -amazon",
    "\"wholesale only\" \"camping tent\" \"sleeping bag\" -manufacturer -factory -retail -alibaba -china",
    "\"camping tent\" \"sleeping bag\" importer distributor -manufacturer -factory -retail -shop -alibaba -china",
    "site:linkedin.com/company \"camping tent\" \"sleeping bag\" importer distributor -manufacturer -factory -alibaba",
    "site:facebook.com/pages \"camping tent\" \"sleeping bag\" wholesale -manufacturer -retail -alibaba -china",
    "site:instagram.com \"camping tent\" \"sleeping bag\" wholesale -manufacturer -retail -alibaba -china",
    "site:google.com/maps \"camping tent\" \"sleeping bag\" importer -retail -shop -alibaba -china",
    "site:yellowpages.com \"camping tent\" \"sleeping bag\" wholesale importer -retail -alibaba -china",
    "\"import data\" \"camping tent\" \"sleeping bag\" importer -manufacturer -factory -alibaba -china"
]

MEDIUM_COMMANDS = [
    "\"private label\" \"camping tent\" \"sleeping bag\" -manufacturer -factory -retail -alibaba -china",
    "\"outdoor gear\" importer \"camping tent\" \"sleeping bag\" -manufacturer -factory -retail -alibaba -china",
    "site:yelp.com \"camping equipment\" wholesale -retail -shop -alibaba -china",
    "\"US import data\" \"camping tent\" -manufacturer -alibaba -china"
]

EXCLUDE_KEYWORDS = [
    "alibaba", "made-in-china", "china", "amazon", "ebay", "etsy", "aliexpress"
]

REQUIRED_KEYWORDS = [
    "import", "importer", "wholesale", "wholesaler", "distributor", "supplier",
    "bulk", "trade", "b2b", "reseller", "dealer", "export"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
]
# ==============================================

def get_search_commands():
    if QUALITY_LEVEL == 1:
        return BASE_COMMANDS
    elif QUALITY_LEVEL == 2:
        return BASE_COMMANDS + MEDIUM_COMMANDS
    else:
        return BASE_COMMANDS + MEDIUM_COMMANDS

def random_delay():
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    time.sleep(delay)

def scrape_google_stable(query):
    results = []
    ua = random.choice(USER_AGENTS)
    
    headers = {
        "User-Agent": ua,
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1"
    }
    
    url = f"https://www.google.com/search?q={quote(query)}&num=30"
    
    try:
        print(f"正在请求Google搜索: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Google响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Google搜索失败，状态码: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        search_results = soup.find_all('div', class_='yuRUbf')
        print(f"原始搜索结果数量: {len(search_results)}")
        
        for result in search_results:
            link_tag = result.find('a')
            if not link_tag or 'href' not in link_tag.attrs:
                continue
                
            link = link_tag['href']
            title_tag = result.find('h3')
            if not title_tag:
                continue
                
            title = title_tag.get_text(strip=True)
            if not link.startswith('http') or 'google.com' in link:
                continue
                
            results.append({
                "title": title,
                "link": link,
                "desc": ""
            })
            
        print(f"过滤后有效搜索结果数量: {len(results)}")
            
    except Exception as e:
        print(f"搜索异常: {e}")
        
    return results

def extract_email(html):
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    emails = re.findall(pattern, html)
    
    if not emails:
        return "未检索到公开邮箱", "待自查"
    
    priority_emails = [e for e in emails if any(k in e.lower() for k in ["sales", "info", "contact", "buyer", "purchase", "export", "import"])]
    email = priority_emails[0] if priority_emails else emails[0]
    
    if any(d in email.split("@")[1] for d in ["example.com", "test.com", "noreply.com", "domain.com"]):
        return email, "无效"
        
    return email, "有效可用"

def check_company(url):
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        print(f"正在检查公司网站: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return False, 0
            
        text = response.text.lower()
        exclude_count = 0
        for k in EXCLUDE_KEYWORDS:
            if k.lower() in text:
                exclude_count += 1
        
        if exclude_count >= 2:
            print(f"包含过多排除关键词，跳过")
            return False, 0
            
        required_count = 0
        for k in REQUIRED_KEYWORDS:
            if k.lower() in text:
                required_count += 1
        
        if required_count < 1:
            print(f"未找到必需关键词，跳过")
            return False, 0
            
        core_words = ["camping tent", "sleeping bag", "outdoor gear", "tent", "camping equipment", "hiking gear"]
        score = 0
        for word in core_words:
            count = text.count(word)
            score += count * 5
            
        print(f"公司匹配分数: {score}")
        return True, score
    except:
        return False,0

def main():
    all_data = []
    keywords_list = get_search_commands()
    for search_word in keywords_list:
        res_list = scrape_google_stable(search_word)
        for item in res_list:
            link = item["link"]
            flag,score = check_company(link)
            if not flag:
                continue
            try:
                html_text = requests.get(link,headers={"User-Agent":random.choice(USER_AGENTS)},timeout=10).text
                mail,status = extract_email(html_text)
            except:
                mail = "访问失败无邮箱"
                status = "异常"
            row = {
                "公司标题":item["title"],
                "官网链接":link,
                "客户邮箱":mail,
                "邮箱状态":status,
                "匹配分值":score,
                "采集时间":datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            all_data.append(row)
            random_delay()
    save_name = f"客户资源_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    df = pd.DataFrame(all_data)
    df.to_excel(save_name,index=False)
    print(f"采集完成，已保存：{save_name}")
    print(f"::set-output name=filename::{save_name}")

if __name__=="__main__":
    main()

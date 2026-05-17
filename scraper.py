import requests
import re
import random
import time
import smtplib
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup
import sys
import os

# ==================== 配置区 ====================
YOUR_EMAIL = "mike@3csin.com"
QUALITY_LEVEL = 2
MIN_DELAY = 6
MAX_DELAY = 12

BASE_COMMANDS = [
    "camping tent wholesaler USA",
    "sleeping bag distributor United States",
    "outdoor gear importer bulk",
    "camping equipment wholesale supplier",
    "tent and sleeping bag importer"
]

MEDIUM_COMMANDS = []  # 先简化，确保能跑通

EXCLUDE_KEYWORDS = [
    "alibaba", "made-in-china", "china", "amazon", "ebay", "etsy", "aliexpress",
    "walmart", "target", "shopify", "kickstarter", "youtube", "wikipedia"
]

REQUIRED_KEYWORDS = [
    "import", "importer", "wholesale", "wholesaler", "distributor", "supplier",
    "bulk", "trade", "b2b", "reseller", "dealer"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
]

# 邮件配置
SENDER_EMAIL = "auto.customer.scraper@gmail.com"
SENDER_PASSWORD = "xqjb wqzk yvzj qmhl"
# ==============================================

# 解决GitHub Ubuntu环境编码问题
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def get_search_commands():
    if QUALITY_LEVEL == 1:
        return BASE_COMMANDS[:3]
    elif QUALITY_LEVEL == 2:
        return BASE_COMMANDS
    else:
        return BASE_COMMANDS

def random_delay():
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    print(f"等待 {delay:.1f} 秒...")
    time.sleep(delay)

def scrape_google_stable(query):
    results = []
    ua = random.choice(USER_AGENTS)
    
    headers = {
        "User-Agent": ua,
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Upgrade-Insecure-Requests": "1"
    }
    
    # 用Google香港域名，风控最低
    url = f"https://www.google.com.hk/search?q={quote(query)}&num=10&gl=us&safe=off"
    
    try:
        print(f"\n正在搜索: {query}")
        response = requests.get(url, headers=headers, timeout=30)
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ 搜索失败，状态码: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        # 兼容2026年Google最新页面结构
        search_results = soup.find_all('div', class_='g')
        
        print(f"找到 {len(search_results)} 条原始结果")
        
        for result in search_results:
            link_tag = result.find('a')
            if not link_tag or 'href' not in link_tag.attrs:
                continue
                
            link = link_tag['href']
            title_tag = result.find('h3')
            if not title_tag:
                continue
                
            title = title_tag.get_text(strip=True)
            
            # 过滤无效链接
            if not link.startswith('http') or 'google.com' in link:
                continue
                
            results.append({
                "company_name": title.split('|')[0].split('-')[0].strip(),
                "website": link
            })
            
        print(f"过滤后有效结果: {len(results)} 条")
            
    except Exception as e:
        print(f"❌ 搜索异常: {str(e)}")
        return []
        
    return results

def extract_email(html):
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    emails = re.findall(pattern, html)
    
    if not emails:
        return "未检索到公开邮箱", "待自查"
    
    # 优先选择业务邮箱
    priority_emails = [e for e in emails if any(k in e.lower() for k in ["sales", "info", "contact"])]
    email = priority_emails[0] if priority_emails else emails[0]
    
    # 过滤测试邮箱
    if any(d in email.split("@")[1] for d in ["example.com", "test.com", "noreply.com"]):
        return email, "无效"
        
    return email, "有效可用"

def check_company(url):
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        print(f"正在分析: {url[:60]}...")
        # 超时时间缩短，避免卡壳
        response = requests.get(url, headers=headers, timeout=8)
        
        if response.status_code != 200:
            return False, 0
            
        text = response.text.lower()
        
        # 过滤中国供应商
        exclude_count = 0
        for k in EXCLUDE_KEYWORDS:
            if k.lower() in text:
                exclude_count += 1
        
        if exclude_count >= 1:
            print("❌ 包含排除关键词，跳过")
            return False, 0
            
        # 验证B2B属性
        required_count = 0
        for k in REQUIRED_KEYWORDS:
            if k.lower() in text:
                required_count += 1
        
        if required_count < 1:
            print("❌ 不是B2B客户，跳过")
            return False, 0
            
        # 计算匹配分数
        core_words = ["camping tent", "sleeping bag", "outdoor gear", "tent"]
        score = 0
        for word in core_words:
            score += text.count(word) * 5
            
        print(f"✅ 匹配分数: {score}")
        return True, score
    except Exception as e:
        print(f"❌ 分析异常: {str(e)}")
        return False, 0

def send_results_to_email(filename):
    print("\n正在发送结果到你的邮箱...")
    
    if not os.path.exists(filename):
        print(f"❌ 找不到文件: {filename}")
        return
    
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = YOUR_EMAIL
    msg['Subject'] = f"自动获客系统 - 新客户名录 {datetime.now().strftime('%Y-%m-%d')}"
    
    body = f"""
    你好 Mike，
    自动获客系统已完成本次采集。
    本次共采集到 {len(pd.read_excel(filename))} 条有效客户线索。
    附件是完整的客户名录Excel文件。
    祝商祺！
    自动获客系统
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        with open(filename, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, YOUR_EMAIL, msg.as_string())
        server.quit()
        print("✅ 邮件发送成功！已发送到 mike@3csin.com")
    except Exception as e:
        print(f"❌ 邮件发送失败: {str(e)}")

def main():
    print("="*50)
    print("Google全自动获客系统 最终稳定版")
    print("2026年5月19日 凌晨修复版")
    print("="*50)
    
    all_data = []
    keywords_list = get_search_commands()
    
    print(f"\n本次将运行 {len(keywords_list)} 个搜索指令")
    print(f"预计运行时间: {len(keywords_list) * (MAX_DELAY + 5) / 60:.1f} 分钟\n")
    
    try:
        for i, search_word in enumerate(keywords_list):
            print(f"\n[{i+1}/{len(keywords_list)}] 处理中...")
            
            res_list = scrape_google_stable(search_word)
            
            for item in res_list:
                link = item["website"]
                flag, score = check_company(link)
                
                if not flag:
                    continue
                    
                try:
                    html_text = requests.get(link, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=8).text
                    mail, status = extract_email(html_text)
                except Exception as e:
                    print(f"❌ 提取邮箱失败: {str(e)}")
                    mail = "访问失败无邮箱"
                    status = "异常"
                    
                row = {
                    "公司名称": item["company_name"],
                    "官网链接": link,
                    "客户邮箱": mail,
                    "邮箱状态": status,
                    "匹配分值": score,
                    "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                all_data.append(row)
                random_delay()
    except Exception as e:
        print(f"❌ 主程序异常: {str(e)}")
    
    print("\n" + "="*50)
    print(f"采集完成！共获取 {len(all_data)} 条有效客户线索")
    
    if len(all_data) > 0:
        save_name = f"客户资源_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df = pd.DataFrame(all_data)
        df = df.sort_values(by='匹配分值', ascending=False)
        df.to_excel(save_name, index=False)
        
        print(f"✅ 数据已保存到: {save_name}")
        print(f"::set-output name=filename::{save_name}")
        
        send_results_to_email(save_name)
    else:
        print("❌ 没有获取到任何客户线索")
        print("::set-output name=filename::")
    
    print("\n系统运行结束！")

if __name__ == "__main__":
    main()

import requests
from bs4 import BeautifulSoup
import csv
import re
import os
import time
from collections import Counter
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端，避免GUI问题
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
try:
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except ImportError:
    print("提示: 未安装wordcloud库，将不会生成词云图。可通过'pip install wordcloud'安装。")
    WORDCLOUD_AVAILABLE = False

# 设置中文字体支持
def set_chinese_font():
    """设置中文字体，解决中文显示乱码问题"""
    try:
        # 尝试使用系统中的中文字体
        if os.name == 'nt':  # Windows系统
            font_paths = [
                'C:/Windows/Fonts/simhei.ttf',  # 黑体
                'C:/Windows/Fonts/simsun.ttc',  # 宋体
                'C:/Windows/Fonts/msyh.ttc',    # 微软雅黑
                'C:/Windows/Fonts/simkai.ttf'   # 楷体
            ]
            
            # 检查字体是否存在并设置
            for font_path in font_paths:
                if os.path.exists(font_path):
                    font_prop = FontProperties(fname=font_path)
                    plt.rcParams['font.family'] = font_prop.get_name()
                    print(f"已设置中文字体: {font_path}")
                    return font_path  # 返回字体路径供词云使用
                    
            # 如果以上字体都不存在，使用matplotlib内置的中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'KaiTi', 'STSong', 'SimSun']
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
            print("已尝试使用matplotlib内置中文字体")
            
        else:  # Linux/Mac系统
            plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Heiti TC', 'SimHei', 'STHeiti']
            plt.rcParams['axes.unicode_minus'] = False
            print("已尝试使用系统中文字体")
            
    except Exception as e:
        print(f"设置中文字体时出错: {e}")
        print("将使用默认字体，中文可能显示为乱码")
    
    return None

# 在程序开始时调用设置中文字体
chinese_font_path = set_chinese_font()

# 创建输出目录
if not os.path.exists('output'):
    os.makedirs('output')

# 定义停用词
STOP_WORDS = {'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what',
              'which', 'this', 'that', 'these', 'those', 'then', 'just', 'so', 'than',
              'such', 'both', 'through', 'about', 'for', 'is', 'of', 'while', 'during',
              'to', 'from', 'in', 'on', 'by', 'with', 'without', 'at', 'between'}

# 定义会议配置
CONFERENCE_CONFIGS = {
    'aaai': {
        'name': 'AAAI',
        'url_pattern': 'https://dblp.org/db/conf/aaai/aaai{year}.html',
        'start_year': 2020,
        'end_year': 2025
    },
    'cvpr': {
        'name': 'CVPR',
        'url_pattern': 'https://dblp.org/db/conf/cvpr/cvpr{year}.html',
        'start_year': 2020,
        'end_year': 2024
    },
    'iccv': {
        'name': 'ICCV',
        'url_pattern': 'https://dblp.org/db/conf/iccv/iccv{year}.html',
        'start_year': 2019,  # ICCV是双年会议
        'end_year': 2023
    }
}

# 1. 爬取会议论文信息
def get_paper_info(conf_key, year):
    """爬取指定会议和年份的论文信息"""
    conf_config = CONFERENCE_CONFIGS[conf_key]
    url = conf_config['url_pattern'].format(year=year)
    print(f"正在爬取 {conf_config['name']} {year} 年论文...")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()  # 检查请求是否成功
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        papers = []
        
        # 查找所有论文条目
        entries = soup.find_all('li', class_='entry inproceedings')
        if not entries:
            print(f"警告: {conf_config['name']} {year}年未找到论文条目，请检查网页结构是否变化")
            return []
            
        for entry in entries:
            paper = {}
            
            # 提取标题
            title_tag = entry.find('span', class_='title')
            paper['title'] = title_tag.text.strip() if title_tag else '未知标题'
            
            # 提取作者
            authors = []
            for author_tag in entry.find_all('span', itemprop='author'):
                name_tag = author_tag.find('span', itemprop='name')
                if name_tag:
                    authors.append(name_tag.text.strip())
            paper['authors'] = '; '.join(authors) if authors else '未知作者'
            
            # 会议名称
            paper['conference'] = conf_config['name']
            
            # 年份
            paper['year'] = str(year)
            
            # 提取链接 lambda用于检测是否存在doi.org或dblp.org/rec/
            link = ''
            doi_link = entry.find('a', href=lambda href: href and 'doi.org' in href)
            if doi_link:
                link = doi_link['href']
            else:
                details_link = entry.find('a', href=lambda href: href and 'dblp.org/rec/' in href)
                if details_link:
                    link = details_link['href']
            paper['link'] = link
            
            papers.append(paper)
        
        print(f"成功爬取 {len(papers)} 篇论文")
        return papers
        
    except Exception as e:
        print(f"爬取 {conf_config['name']} {year} 年论文时出错: {e}")
        return []

def save_to_csv(papers, filename):
    """保存论文信息到CSV文件"""
    if not papers:
        print("没有论文数据可保存")
        return
        
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['title', 'authors', 'year', 'conference', 'link'])#Dicwriter较于writer更适合结构化数据通过字典的键名直接映射到列名
            writer.writeheader()
            for paper in papers:
                writer.writerow(paper)#按照每行写入论文数据
        print(f"已保存 {len(papers)} 篇论文信息到 {filename}")
    except Exception as e:
        print(f"保存CSV文件时出错: {e}")

# 2. 统计每届会议论文数量并绘制趋势图
def plot_paper_trend(papers, conf_name):
    """绘制论文数量趋势图"""
    if not papers:
        print(f"没有 {conf_name} 论文数据可分析")
        return {}
        
    # 按年份统计论文数量
    year_count = {}
    for paper in papers:
        year = paper['year']
        year_count[year] = year_count.get(year, 0) + 1
    
    # 排序年份
    years = sorted(year_count.keys())
    counts = [year_count[year] for year in years]
    
    try:
        # 绘制趋势图
        plt.figure(figsize=(10, 6))
        plt.plot(years, counts, marker='o', linewidth=2)
        plt.title(f'{conf_name}会议论文数量趋势', fontsize=14)
        plt.xlabel('年份', fontsize=12)
        plt.ylabel('论文数量', fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # 添加数据标签
        for x, y in zip(years, counts):
            plt.text(x, y+50, f"{y}", ha='center', va='bottom', fontsize=10)
            
        plt.tight_layout()
        plt.savefig(f'output/{conf_name.lower()}_paper_trend.png', dpi=300)
        print(f"已保存论文数量趋势图到 output/{conf_name.lower()}_paper_trend.png")
        
        return year_count
    except Exception as e:
        print(f"绘制趋势图时出错: {e}")
        return year_count

# 3. 提取关键词并生成词云
def extract_keywords(papers):
    """从论文标题中提取关键词"""
    if not papers:
        print("没有论文数据可分析")
        return {}
        
    # 合并所有标题
    all_titles = ' '.join([paper['title'] for paper in papers])
    
    # 清理文本
    all_titles = all_titles.lower()
    all_titles = re.sub(r'[^\w\s]', ' ', all_titles)  # 移除标点符号
    
    # 分词
    words = all_titles.split()
    
    # 移除停用词和短词
    words = [word for word in words if word not in STOP_WORDS and len(word) > 2]
    
    # 统计词频
    word_freq = Counter(words)
    
    return word_freq

def plot_keywords_bar(word_freq, conf_name, top_n=20):
    """绘制关键词频率条形图"""
    if not word_freq:
        print(f"没有 {conf_name} 关键词数据可分析")
        return
        
    try:
        # 获取前N个高频词
        top_words = word_freq.most_common(top_n)
        words, counts = zip(*top_words)
        
        # 绘制条形图
        plt.figure(figsize=(12, 8))
        plt.barh(range(len(words)), counts, align='center')
        plt.yticks(range(len(words)), words)
        plt.xlabel('频率', fontsize=12)
        plt.ylabel('关键词', fontsize=12)
        plt.title(f'{conf_name}论文标题高频关键词 (Top {top_n})', fontsize=14)
        plt.tight_layout()
        plt.savefig(f'output/{conf_name.lower()}_keywords_bar.png', dpi=300)
        print(f"已保存关键词频率图到 output/{conf_name.lower()}_keywords_bar.png")
        
        # 保存高频词到文本文件
        with open(f'output/{conf_name.lower()}_top_keywords.txt', 'w', encoding='utf-8') as f:
            f.write(f"{conf_name}论文标题高频关键词 (Top {top_n}):\n")
            for i, (word, count) in enumerate(top_words, 1):
                f.write(f"{i}. {word}: {count}\n")
        print(f"已保存高频关键词列表到 output/{conf_name.lower()}_top_keywords.txt")
        
        # 生成词云图
        if WORDCLOUD_AVAILABLE:
            generate_wordcloud(word_freq, conf_name)
            
    except Exception as e:
        print(f"绘制关键词图时出错: {e}")

def generate_wordcloud(word_freq, conf_name):
    """生成词云图"""
    try:
        # 创建词云对象
        wc_kwargs = {
            'width': 800, 
            'height': 400, 
            'background_color': 'white',
            'max_words': 200,
            'colormap': 'viridis',
            'contour_width': 1,
            'contour_color': 'steelblue'
        }
        
        # 如果有中文字体，设置字体
        if chinese_font_path and os.path.exists(chinese_font_path):
            wc_kwargs['font_path'] = chinese_font_path
            
        wordcloud = WordCloud(**wc_kwargs)
        
        # 从词频生成词云
        wordcloud.generate_from_frequencies(word_freq)
        
        # 绘制词云图
        plt.figure(figsize=(10, 6))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.title(f'{conf_name}论文标题词云', fontsize=16)
        plt.tight_layout()
        plt.savefig(f'output/{conf_name.lower()}_wordcloud.png', dpi=300)
        print(f"已保存词云图到 output/{conf_name.lower()}_wordcloud.png")
    except Exception as e:
        print(f"生成词云图时出错: {e}")

# 4. 预测下一届论文数量
def predict_next_year(year_count, conf_name):
    """简单线性预测下一届论文数量"""
    if not year_count or len(year_count) < 2:
        print(f"数据不足，无法预测 {conf_name} 下一届论文数量")
        return
        
    try:
        # 转换为数值列表
        years = sorted([int(y) for y in year_count.keys()])
        counts = [year_count[str(y)] for y in years]
        
        # 计算年增长率
        growth_rates = []
        for i in range(1, len(counts)):
            if counts[i-1] > 0:  # 避免除零错误
                growth_rate = (counts[i] - counts[i-1]) / counts[i-1]
                growth_rates.append(growth_rate)
        
        # 如果没有足够的增长率数据，使用平均值
        if not growth_rates:
            avg_count = sum(counts) / len(counts)
            next_year = years[-1] + 1
            prediction = int(avg_count)
        else:
            # 使用平均增长率预测
            avg_growth_rate = sum(growth_rates) / len(growth_rates)
            next_count = counts[-1] * (1 + avg_growth_rate)
            next_year = years[-1] + 1
            prediction = int(next_count)
        
        print(f"预测 {conf_name} {next_year} 年论文数量: {prediction}")
        
        # 保存预测结果
        with open(f'output/{conf_name.lower()}_prediction.txt', 'w', encoding='utf-8') as f:
            f.write(f"{conf_name} {next_year} 年论文数量预测: {prediction}\n")
            f.write("\n历年论文数量:\n")
            for y, c in zip(years, counts):
                f.write(f"{y}: {c}\n")
            if growth_rates:
                f.write("\n历年增长率:\n")
                for i, rate in enumerate(growth_rates):
                    f.write(f"{years[i]} 至 {years[i+1]}: {rate:.2%}\n")
                f.write(f"\n平均增长率: {avg_growth_rate:.2%}\n")
        
        print(f"已保存预测结果到 output/{conf_name.lower()}_prediction.txt")
    except Exception as e:
        print(f"预测论文数量时出错: {e}")

def process_conference(conf_key):
    """处理单个会议的所有数据"""
    conf_config = CONFERENCE_CONFIGS[conf_key]
    conf_name = conf_config['name']
    start_year = conf_config['start_year']
    end_year = conf_config['end_year']
    
    print(f"\n开始爬取{conf_name}会议论文信息 ({start_year}-{end_year})...")
    
    # 爬取论文
    all_papers = []
    for year in range(start_year, end_year + 1):
        # 对于ICCV，只处理奇数年份
        if conf_key == 'iccv' and year % 2 == 0:
            continue
        
        # 爬取当前年份的论文
        papers = get_paper_info(conf_key, year)
        all_papers.extend(papers)
        time.sleep(2)  # 避免请求过于频繁
    
    if not all_papers:
        print(f"未能获取任何{conf_name}论文信息，跳过该会议")
        return
    
    # 保存所有论文信息
    save_to_csv(all_papers, f'output/{conf_name.lower()}_papers_{start_year}_{end_year}.csv')
    
    # 统计论文数量并绘制趋势图
    year_count = plot_paper_trend(all_papers, conf_name)
    
    # 提取关键词并可视化
    word_freq = extract_keywords(all_papers)
    plot_keywords_bar(word_freq, conf_name)
    
    # 预测下一届论文数量
    predict_next_year(year_count, conf_name)
    
    print(f"{conf_name}会议数据处理完成！")

def main():
    """主函数"""
    print("DBLP会议论文爬取与分析工具")
    print("="*50)
    
    # 处理所有配置的会议
    for conf_key in CONFERENCE_CONFIGS:
        process_conference(conf_key)
    
    print("\n所有会议数据处理完成！")

if __name__ == "__main__":
    main() 
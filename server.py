import os
import json
import smtplib
from datetime import datetime
from email.message import EmailMessage
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

mcp = FastMCP("NewsServer")


async def fetch_news_data(api_key: str, keyword: str) -> dict:
    """发送新闻搜索请求并获取结果"""
    url = "https://google.serper.dev/news"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": keyword}

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        data = response.json()

    # 检查数据
    if "news" not in data:
        raise ValueError("❌ 未获取到搜索结果")

    return data["news"]


@mcp.tool  # 装饰器，将函数注册为工具
async def search_google_news(keyword: str) -> str:
    """
    使用 Serper API（Google Search 封装）根据关键词搜索新闻内容，返回前5条标题、描述和链接。

    参数:
        keyword (str): 关键词，如 "小米汽车"

    返回:
        str: JSON 字符串，包含新闻标题、描述、链接
    """

    # 从环境中获取 API 密钥并进行检查
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise ValueError("❌ SERPER_API_KEY is not set，请在.env文件中设置")

    # 设置请求参数并发送请求
    news_data = await fetch_news_data(api_key, keyword)

    # 按照格式提取新闻，返回前五条新闻
    articles = [
        {
            "title": item.get("title"),
            "desc": item.get("snippet"),
            "url": item.get("link"),
        }
        for item in news_data[:5]
    ]

    # 将新闻结果以带有时间戳命名后的 JSON 格式文件的形式保存在本地指定的路径
    file_path = save_news_to_file(articles)

    return (
        f"✅ 已获取与 [{keyword}] 相关的前5条 Google 新闻：\n"
        f"{json.dumps(articles, ensure_ascii=False, indent=2)}\n"
        f"📄 已保存到：{file_path}"
    )


def save_news_to_file(articles: list) -> str:
    """将新闻结果以带有时间戳命名后的 JSON 格式文件的形式保存在本地指定的路径"""
    output_dir = "./google_news"
    os.makedirs(output_dir, exist_ok=True)
    filename = f"google_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    file_path = os.path.join(output_dir, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    return file_path


def generate_sentiment_report(text: str, result: str) -> str:
    return f"""# 舆情分析报告

    **分析时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    ---

    ## 📥 原始文本

    {text}

    ---

    ## 📊 分析结果

    {result}
    """


@mcp.tool()
async def analyze_sentiment(text: str, file_path: str) -> str:
    """
    对传入的一段文本内容进行情感分析，并保存为指定名称的 Markdown 文件。

    参数:
        text (str): 新闻描述或文本内容
        file_path (str): 保存的 Markdown 文件路径

    返回:
        str: 完整文件路径（用于邮件发送）
    """

    # 这里的情感分析功能需要去调用 LLM，所以从环境中获取 LLM 的一些相应配置
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("BASE_URL")
    model = os.getenv("MODEL")
    if not api_key:
        raise ValueError("❌ DASHSCOPE_API_KEY is not set，请在.env文件中设置")
    if not base_url:
        raise ValueError("❌ BASE_URL is not set，请在.env文件中设置")
    if not model:
        raise ValueError("❌ MODEL is not set，请在.env文件中设置")

    # 构造情感分析的提示词
    prompt = f"请对以下新闻内容进行情绪倾向分析，并说明原因：\n\n{text}"

    # 向模型发送请求，并处理返回的结果
    response = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}]
    )
    result = response.choices[0].message.content.strip()

    # 生成 Markdown 格式的舆情分析报告，并存放进设置好的输出目录
    markdown = generate_sentiment_report(text, result)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    return file_path


def add_attachment_to_email(msg: EmailMessage, file_path: str):
    """添加附件并发送邮件"""
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
            file_name = os.path.basename(file_path)
            msg.add_attachment(
                file_data,
                maintype="application",
                subtype="octet-stream",
                filename=file_name,
            )
    except Exception as e:
        return f"❌ 附件读取失败: {str(e)}"


def send_email(
    msg: EmailMessage,
    to: str,
    smtp_server: str,
    smtp_port: int,
    sender_email: str,
    sender_pass: str,
    file_path: str,
):
    """发送邮件"""
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_pass)
            server.send_message(msg)
        return f"✅ 邮件已成功发送给 {to}，附件路径: {file_path}"
    except Exception as e:
        return f"❌ 邮件发送失败: {str(e)}"

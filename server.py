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

    return data


@mcp.tool  # 装饰器，将函数注册为工具
async def search_google_news(keyword: str) -> str:
    """使用 Serper API（Google Search 封装）根据关键词搜索新闻内容，返回前5条标题、描述和链接"""

    # 从环境中获取 API 密钥并进行检查
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise ValueError("❌ SERPER_API_KEY is not set，请在.env文件中设置")

    # 设置请求参数并发送请求
    data = await fetch_news_data(api_key, keyword)

    # 按照格式提取新闻，返回前五条新闻
    articles = [
        {
            "title": item.get("title"),
            "desc": item.get("snippet"),
            "url": item.get("link"),
        }
        for item in data["news"][:5]
    ]

    # 将新闻结果以带有时间戳命名后的 JSON 格式文件的形式保存在本地指定的路径 TODO
    file_path = save_news_to_file(articles)

    return (
        f"✅ 已获取与 [{keyword}] 相关的前5条 Google 新闻：\n"
        f"{json.dumps(articles, ensure_ascii=False, indent=2)}\n"
        f"📄 已保存到：{file_path}"
    )

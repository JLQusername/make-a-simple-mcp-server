import asyncio
import os
import json
from typing import Optional, List
from contextlib import AsyncExitStack
from datetime import datetime
import re
from openai import OpenAI
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()


class MCPClient:

    # 初始化客户端配置
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.base_url = os.getenv("BASE_URL")
        self.model = os.getenv("MODEL")
        if not self.api_key:
            raise ValueError("❌ DASHSCOPE_API_KEY is not set，请在.env文件中设置")
        if not self.base_url:
            raise ValueError("❌ BASE_URL is not set，请在.env文件中设置")
        if not self.model:
            raise ValueError("❌ MODEL is not set，请在.env文件中设置")

        # 初始化MCP客户端
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.session: Optional[ClientSession] = None

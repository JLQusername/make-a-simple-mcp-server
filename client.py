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

    # 与服务器建立连接 初始化阶段
    async def connect(self, server_script_path: str):
        # 判断服务器脚本类型
        is_py = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_py or is_js):
            raise ValueError("❌ 服务器脚本类型错误，请使用.py或.js文件")

        # 确定启动命令
        command = "python", server_script_path if is_py else "node"

        # 构造 MCP 所需要的服务器参数
        server_parameters = StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )

        # 启动 MCP 工具服务进程，并建立 stdio 通信
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_parameters)
        )

        # 拆包通信通道，用于读取服务端返回的数据，并向服务端发送请求
        self.stdio, self.writer = stdio_transport

        # 创建 MCP 客户端会话对象
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.writer)
        )

        # 初始化客户端会话
        await self.session.initialize()

        # 获取并打印工具列表
        await self.list_tools()

    async def list_tools(self):
        """获取并打印可用的工具列表"""
        response = await self.session.list_tools()
        self.tools = response.tools
        print("已连接到服务器，🔧 工具列表:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")

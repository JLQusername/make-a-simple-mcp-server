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

    async def connect_to_server(self, server_script_path: str):
        """连接到服务器 完成初始化阶段"""
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
        """请求可用工具列表"""
        response = await self.session.list_tools()
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                },
            }
            for tool in response.tools
        ]
        print(f"已连接到服务器，🔧 工具列表: {self.tools}")

    def clean_filename(text: str) -> str:
        """清理文本，生成合法的文件名"""
        text = text.strip()
        text = re.sub(r"[\\/:*?\"<>|]", "", text)
        return text[:50]

    def prepare_file_paths(self, query: str) -> tuple[str, str, str, str]:
        """准备文件路径相关信息"""
        safe_filename = self.clean_filename(query)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 准备 markdown 报告路径
        md_filename = f"{safe_filename}_{timestamp}.md"
        os.makedirs("./sentiment_reports", exist_ok=True)
        md_path = os.path.join("./sentiment_reports", md_filename)

        # 准备对话记录路径
        txt_filename = f"{safe_filename}_{timestamp}.txt"
        os.makedirs("./llm_outputs", exist_ok=True)
        txt_path = os.path.join("./llm_outputs", txt_filename)

        return md_filename, md_path, txt_filename, txt_path

    def resolve_tool_args(
        self,
        tool_name: str,
        tool_args: dict,
        tool_outputs: dict,
        md_filename: str,
        md_path: str,
    ):
        # 处理参数引用
        for key, val in tool_args.items():
            if isinstance(val, str) and val.startswith("{{") and val.endswith("}}"):
                ref_key = val.strip("{} ")
                resolved_val = tool_outputs.get(ref_key, val)
                tool_args[key] = resolved_val

        # 注入统一的文件名或路径（用于分析和邮件）
        if tool_name == "analyze_sentiment" and "filename" not in tool_args:
            tool_args["filename"] = md_filename
        if (
            tool_name == "send_email_with_attachment"
            and "attachment_path" not in tool_args
        ):
            tool_args["attachment_path"] = md_path

    async def plan_tool_usage(self, query: str, tools: List[dict]) -> List[dict]:
        """获取计划执行的工具列表"""
        # 构造系统提示词 system_prompt
        # 将所有可用工具组织为文本列表插入提示中，并明确指出工具名
        # 限定返回格式是 JSON，防止其输出错误格式的数据
        print("\n📤 提交给大模型的工具定义:")
        print(json.dumps(tools, ensure_ascii=False, indent=2))
        tool_list_text = "\n".join(
            [
                f"- {tool['function']['name']}: {tool['function']['description']}"
                for tool in tools
            ]
        )
        system_prompt = {
            "role": "system",
            "content": (
                "你是一个智能任务规划助手，用户会给出一句自然语言请求。\n"
                "你只能从以下工具中选择（严格使用工具名称）：\n"
                f"{tool_list_text}\n"
                "如果多个工具需要串联，后续步骤中可以使用 {{上一步工具名}} 占位。\n"
                "返回格式：JSON 数组，每个对象包含 name 和 arguments 字段。\n"
                "不要返回自然语言，不要使用未列出的工具名。"
            ),
        }

        # 构造对话上下文并调用模型
        # 将系统提示和用户的自然语言一起作为消息输入，并选用当前的模型
        planning_messages = [system_prompt, {"role": "user", "content": query}]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=planning_messages,
            tools=tools,
            tool_choice="none",
        )

        # 提取出模型返回的 JSON 内容
        content = response.choices[0].message.content.strip()
        match = re.search(r"```(?:json)?\\s*([\s\S]+?)\\s*```", content)
        if match:
            json_text = match.group(1)
        else:
            json_text = content

        # 在解析 JSON 之后返回调用计划
        try:
            plan = json.loads(json_text)
            return plan if isinstance(plan, list) else []
        except Exception as e:
            print(f"❌ 获取计划执行的工具列表失败: {e}\n原始返回: {content}")
            return []

    async def execute_tool_chain(
        self, query: str, tool_plan: list, md_filename: str, md_path: str
    ) -> list:
        """执行工具调用链"""
        tool_outputs = {}
        messages = [{"role": "user", "content": query}]

        for step in tool_plan:
            tool_name = step["tool"]
            tool_args = step["arguments"]

            # 处理参数引用
            self.resolve_tool_args(
                tool_name, tool_args, tool_outputs, md_filename, md_path
            )

            # 执行工具调用
            result = await self.session.call_tool(tool_name, tool_args)

            # 更新工具输出
            tool_outputs[tool_name] = result.content[0].text

            # 添加工具调用记录
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_name,
                    "content": result.content[0].text,
                }
            )

        return messages

    async def generate_final_response(self, messages: list) -> str:
        """生成最终响应"""
        final_response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return final_response.choices[0].message.content

    def save_conversation(self, query: str, final_output: str, file_path: str):
        """保存对话记录"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"🤵 用户提问：{query}\n\n")
            f.write(f"🤖 模型回复：\n{final_output}\n")
        print(f"📄 对话记录已保存为：{file_path}")

    async def process_query(self, query: str) -> str:
        """处理用户查询的主流程"""
        # 准备文件路径
        md_filename, md_path, txt_filename, txt_path = self.prepare_file_paths(query)

        # 更新查询，添加文件信息
        query = query.strip() + f" [md_filename={md_filename}] [md_path={md_path}]"

        # 获取工具调用计划
        tool_plan = await self.plan_tool_usage(query, self.tools)

        # 执行工具调用链
        messages = await self.execute_tool_chain(query, tool_plan, md_filename, md_path)

        # 生成最终响应
        final_output = await self.generate_final_response(messages)

        # 保存对话记录
        self.save_conversation(query, final_output, txt_path)

        return final_output

    async def chat_loop(self):
        # 初始化提示信息
        print("\n🤖花果茶 MCP 客户端已启动！输入 'quit' 退出")

        # 进入主循环中等待用户输入
        while True:
            try:
                query = input("\n你: ").strip()
                if query.lower() == "quit":
                    break

                # 处理用户的提问，并返回结果
                response = await self.process_query(query)
                print(f"\n🤖 AI: {response}")

            except Exception as e:
                print(f"\n⚠️ 发生错误: {str(e)}")

    async def cleanup(self):
        await self.exit_stack.aclose()


async def main():
    server_script_path = "D:\\make-a-simple-mcp-server\\server.py"  # 替换成你自己的路径
    client = MCPClient()
    try:
        await client.connect_to_server(server_script_path)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

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

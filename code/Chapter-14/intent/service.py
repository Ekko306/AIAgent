#!/usr/bin/env python3

__author__ = "xi"

import json
import os
import re
from typing import Any, Dict, List, Optional

import jinja2
from agent_types.common import Intent, LLMConfig, SystemProfile, Tool
from agent_types.intent import IntentRequest, IntentResponse
from libdata.config import Config
from libentry import logger
from libentry.mcp import api
from liblogging import log_request
from pydantic import BaseModel, Field, model_validator

from planning.llm import LLMResponse, call_llm

__dir__ = os.path.dirname(os.path.abspath(__file__))

DEFAULT_SYSTEM_PROFILE = SystemProfile(
    description="你是一个专业的意图理解模块，能够准确识别用户意图并筛选合适的工具",
    language="中文",
    capabilities=[
        "识别用户意图",
        "根据意图筛选工具"
    ],
    constrains=[
        "只筛选存在的工具",
        "严格按照JSON格式输出"
    ]
)


class IntentServiceConfig(BaseModel):
    """Intent service config object"""

    config_url: str = Field(
        title="全局配置URL",
        description="全局配置URL，可以是yml文件或mongodb表或配置服务。"
    )
    llm_name: Optional[str] = Field(
        title="大模型名称",
        description="从全局配置中获取生成选项大模型名称",
        default=None
    )
    llm_config: Optional[LLMConfig] = Field(default=None)
    system_template_path: str = Field(
        title="系统提示词模板文件路径",
        description="系统提示词模板文件路径，jinja2格式",
        default=os.path.join(__dir__, "template/system.j2")
    )
    user_template_path: str = Field(
        title="用户提示词模板文件路径",
        description="用户提示词模板文件路径，jinja2格式",
        default=os.path.join(__dir__, "template/user.j2")
    )

    @model_validator(mode="after")
    def check_configs(self):
        if self.llm_config is None and self.llm_name is None:
            raise ValueError("At least one of `llm_name` and `llm_config` should be given.")
        return self


class IntentService:

    def __init__(self, config: IntentServiceConfig):
        self.config = config
        self.global_config = Config.from_url(self.config.config_url)

        # For thread-safety, we use jinja2.Environment to cache templates.
        template_dict = {}
        with open(self.config.system_template_path, "r") as f:
            template_dict["system"] = f.read().strip()
        with open(self.config.user_template_path, "r") as f:
            template_dict["user"] = f.read().strip()
        self.template_env = jinja2.Environment(loader=jinja2.DictLoader(template_dict))

        logger.info(f"Using {self.get_llm_config()}")

    def get_llm_config(self) -> LLMConfig:
        return (
            self.config.llm_config
            if self.config.llm_config else
            LLMConfig.model_validate(self.global_config[self.config.llm_name])
        )

    @api.post(IntentRequest.get_request_path())
    @log_request("trace_id", message_source="intent")
    def detect_intent(self, request: IntentRequest) -> IntentResponse:
        logger.info(f"Received request: {request.model_dump(exclude_none=True)}")
        messages = self._create_messages(request)

        # 意图识别属于分类任务，使用低温度保证输出稳定
        llm_response = call_llm(
            base_url=self.get_llm_config().base_url,
            api_key=self.get_llm_config().api_key,
            model=self.get_llm_config().model,
            messages=messages,
            tools=[],
            stream=False,
            temperature=0.1
        )
        assert isinstance(llm_response, LLMResponse)
        logger.info(f"LLM Response: {llm_response.content}")

        return self._parse_response(llm_response, request)

    def _parse_response(self, llm_response: LLMResponse, request: IntentRequest) -> IntentResponse:
        """解析LLM输出的JSON，失败时降级：返回默认意图且不过滤工具"""
        content = llm_response.content
        fallback = IntentResponse(
            intents=[Intent(name="unknown", description="意图识别失败，使用默认意图")],
            candidate_tools=None,
            thinking=llm_response.thinking or content
        )

        try:
            # 容错：剥离可能的markdown代码块标记
            text = content.strip()
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                text = match.group(0)
            data = json.loads(text)

            intents = [
                Intent(name=item["name"], description=item.get("description"))
                for item in data.get("intents", [])
                if item.get("name")
            ]
            if not intents:
                return fallback

            # 将工具名映射回Tool对象；无法识别任何工具时不过滤
            tool_map: Dict[str, Tool] = {tool.name: tool for tool in request.tools or []}
            candidate_tools: List[List[Tool]] = []
            for names in data.get("candidate_tools") or []:
                tool_list = [tool_map[name] for name in names if name in tool_map]
                if tool_list:
                    candidate_tools.append(tool_list)
            candidate_tools = candidate_tools if candidate_tools else None

            return IntentResponse(
                intents=intents,
                candidate_tools=candidate_tools,
                thinking=llm_response.thinking
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning(f"Failed to parse intent response: {e}. Content: {content}")
            return fallback

    def _create_messages(self, request: IntentRequest) -> List[Dict[str, Any]]:
        messages = [
            {
                "role": "system",
                "content": self.template_env.get_template("system").render(
                    system_profile=request.system_profile or DEFAULT_SYSTEM_PROFILE
                )
            }
        ]

        # 会话记忆中的历史对话有助于指代消解（如"它还在营业吗"）
        session_memory = request.session_memory
        if session_memory and session_memory.chat_history:
            for message in session_memory.chat_history:
                if message.role in {"user", "assistant"}:
                    messages.append({
                        "role": message.role,
                        "content": message.content
                    })

        messages.append({
            "role": "user",
            "content": self.template_env.get_template("user").render(
                query=request.query if isinstance(request.query, str) else request.query.content,
                tools=request.tools,
                candidate_intents=request.candidate_intents
            )
        })

        return messages

"""
Model layer for the standalone scripts in this repository.

The implementation lives in the aiquality package (aiquality/models/chat_model.py); this file
keeps the old import path working:  from llm import get_chat_model, JUDGE_MODEL, ...

Settings (environment variables, all optional): LLM_PROVIDER, AGENT_MODEL, JUDGE_MODEL.
"""

import paths  # noqa: F401,E402  (the repository root, if aiquality isn't installed)
from aiquality.models.chat_model import (AGENT_MODEL, JUDGE_MODEL, AnthropicChat, ChatModel,  # noqa: F401
                                         extract_json, get_api_key, get_chat_model)

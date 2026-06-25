# -*- coding: utf-8 -*-
"""
고민 난장회의 - LLM 추상화 레이어
환경변수로 OpenAI / Anthropic 중 선택. function calling(tool use) 루프 포함.

환경변수:
  LLM_PROVIDER = "openai" (기본) | "anthropic"
  OPENAI_API_KEY / OPENAI_MODEL (기본 gpt-4o-mini)
  ANTHROPIC_API_KEY / ANTHROPIC_MODEL (기본 claude-haiku-4-5)
"""

import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from tools import OPENAI_TOOLS, anthropic_tools, dispatch_tool

def _provider():
    return os.getenv("LLM_PROVIDER", "openai").lower()


MAX_TOOL_LOOPS = 5


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------
def _run_openai(system_prompt, messages):
    from openai import OpenAI

    client = OpenAI()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    convo = [{"role": "system", "content": system_prompt}] + messages

    for _ in range(MAX_TOOL_LOOPS):
        resp = client.chat.completions.create(
            model=model,
            messages=convo,
            tools=OPENAI_TOOLS,
            temperature=0.9,
            max_tokens=200,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return (msg.content or "").strip()

        # tool 호출 처리
        convo.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = dispatch_tool(tc.function.name, args)
            convo.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "음... 생각이 너무 길어졌어요. 다시 한 번 말해줄래요?"


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
def _run_anthropic(system_prompt, messages):
    import anthropic

    client = anthropic.Anthropic()
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
    tools = anthropic_tools()

    # messages: OpenAI 포맷({role, content})을 Anthropic 포맷으로 (user/assistant만)
    convo = [{"role": m["role"], "content": m["content"]} for m in messages]

    for _ in range(MAX_TOOL_LOOPS):
        resp = client.messages.create(
            model=model,
            system=system_prompt,
            messages=convo,
            tools=tools,
            temperature=0.9,
            max_tokens=200,
        )

        if resp.stop_reason != "tool_use":
            texts = [b.text for b in resp.content if b.type == "text"]
            return "".join(texts).strip()

        convo.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                result = dispatch_tool(block.name, block.input or {})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
        convo.append({"role": "user", "content": tool_results})

    return "음... 생각이 너무 길어졌어요. 다시 한 번 말해줄래요?"


# ---------------------------------------------------------------------------
# 공용 진입점
# ---------------------------------------------------------------------------
def run_with_tools(system_prompt, messages):
    """
    system_prompt: str
    messages: [{"role": "user"/"assistant", "content": str}, ...]
    반환: 페르소나 말투의 최종 텍스트
    """
    try:
        if _provider() == "anthropic":
            return _run_anthropic(system_prompt, messages)
        return _run_openai(system_prompt, messages)
    except Exception as e:
        import traceback
        traceback.print_exc()   # 터미널에 상세 원인 출력
        return f"(앗, 응답 생성 중 문제: {type(e).__name__}: {str(e)[:120]})"


def provider_info():
    if _provider() == "anthropic":
        return f"Anthropic / {os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5')}"
    return f"OpenAI / {os.getenv('OPENAI_MODEL', 'gpt-4o-mini')}"
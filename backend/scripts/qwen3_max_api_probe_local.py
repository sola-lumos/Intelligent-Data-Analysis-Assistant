#!/usr/bin/env python3
"""
百炼 DashScope — OpenAI 兼容 ``/v1/chat/completions`` 探针（流式 / 函数调用）。

**配置**：从 ``backend/.env`` 读取（与 ``app/core/config.py`` 约定一致），勿在脚本写密钥。

示例::

    cd backend && .venv/bin/python scripts/qwen3_max_api_probe_local.py
    .venv/bin/python scripts/qwen3_max_api_probe_local.py --verbose-stream --verbose-tools-stream

环境与字段约定（对齐 OpenAI Chat Completions 兼容形态；服务端可能增补额外顶层键）::

    - 非流式：``id``, ``choices[]``, ``model``, ``created``, ``usage``（若网关返回）。
      ``choices[0].finish_reason`` 含 ``stop`` / ``tool_calls`` / ``length`` 等；
      ``choices[0].message`` 含 ``role``, ``content``（可为 null）, ``tool_calls``（每项含 ``id``, ``type``,
      ``function.name``, ``function.arguments`` 字符串化 JSON）。
    - 纯文本流：每帧 ``choices[0].delta`` 常为 ``role``（首包）, ``content`` 分片；
      末包常有 ``choices[0].finish_reason``。
    - 流式工具：``delta.tool_calls[]`` 为分片列表，每项可能仅含 ``index``, ``id``, ``type``,
      ``function.name`` / ``function.arguments`` 局部字符串，需在客户端拼接。

若上游变更字段命名，请以本脚本 ``--verbose-*`` 打出的原始 ``model_dump`` 为准。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIStatusError
from openai import OpenAI

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv_from_backend(explicit: Path | None = None) -> Path:
    env_path = explicit if explicit is not None else BACKEND_ROOT / ".env"
    load_dotenv(env_path)
    if not env_path.exists():
        print(f"⚠️ 未找到 {env_path}，仅使用进程环境变量", file=sys.stderr)
    return env_path


def _read_client_config(cli_key: str | None, env_dotenv_path: Path | None = None):
    """返回 (api_key, base_url, model, temperature)。"""

    import os

    _load_dotenv_from_backend(env_dotenv_path)
    key = (cli_key or os.getenv("DASHSCOPE_API_KEY") or "").strip()
    base = (
        os.getenv("DASHSCOPE_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).strip().rstrip("/")
    model = (os.getenv("QWEN_MODEL") or "qwen-plus").strip()
    temp_s = os.getenv("QWEN_TEMPERATURE")
    temperature = float(temp_s) if temp_s not in (None, "") else 0.0
    return key, base, model, temperature


def _dump(title: str, obj: Any) -> None:
    if hasattr(obj, "model_dump"):
        data = obj.model_dump(exclude_none=False)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = repr(obj)
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def probe_stream_verbose(
    client: OpenAI,
    *,
    model: str,
    temperature: float,
    verbose: bool,
) -> None:
    print("\n" + "=" * 60)
    print("A) 流式 plain text —— delta / finish_reason / 顶层键")
    print("=" * 60)

    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是助手，简短回答。"},
            {"role": "user", "content": "用一句话说你是谁，然后说数字 1 2 3。"},
        ],
        stream=True,
        temperature=temperature,
    )

    last_i = -1
    tops: set[str] = set()
    for last_i, chunk in enumerate(stream):
        d = chunk.model_dump(exclude_none=False)
        tops |= set(d.keys())
        choices = d.get("choices") or ()
        delta = (choices[0] or {}).get("delta") if choices else {}
        fr = (choices[0] or {}).get("finish_reason") if choices else None
        if verbose or last_i < 10:
            _dump(f"A 流 chunk[{last_i}] 完整字段", chunk)
        else:
            dk = sorted(delta.keys()) if isinstance(delta, dict) else []
            print(
                f"[{last_i}] id={d.get('id')} "
                f"top_extra={sorted(set(d.keys()) - {'choices', 'id', 'object'})} "
                f"finish_reason={fr} delta_keys={dk}"
            )

    print(f"\n... A 段共 chunk 数={last_i + 1} | 见过的顶层字段={sorted(tops)}")


def probe_tool_calls_non_stream(
    client: OpenAI,
    *,
    model: str,
    temperature: float,
) -> None:
    print("\n" + "=" * 60)
    print("B) 非流式 + tools —— message / tool_calls 全量形状")
    print("=" * 60)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "report_integer",
                "description": "向调用方上报一个整数结果。",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"],
                },
            },
        }
    ]

    rsp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "需要上报整数时请调用函数 report_integer。",
            },
            {"role": "user", "content": "请通过工具上报整数 42。"},
        ],
        tools=tools,
        tool_choice="auto",
        temperature=temperature,
    )

    tops = rsp.model_dump(exclude_none=False)
    print("\n=== B responses 顶层键 ===", sorted(tops.keys()))
    _dump("B responses.model_dump()", rsp)

    msg = rsp.choices[0].message
    md = msg.model_dump(exclude_none=False)
    print("\n=== B choices[0].message 键 ===", sorted(md.keys()))
    _dump(
        "B choices[0].message（含 tool_calls[].function.arguments）",
        msg,
    )


def _accumulate_delta_tool_calls(
    acc: dict[int, dict[str, Any]],
    delta_tool_calls: list | None,
) -> None:
    if not delta_tool_calls:
        return
    for part in delta_tool_calls:
        if hasattr(part, "model_dump"):
            p = part.model_dump(exclude_none=False)
        elif isinstance(part, dict):
            p = part
        else:
            continue
        if not isinstance(p, dict):
            continue
        idx = p.get("index", 0)
        cur = acc.setdefault(
            idx,
            {"id": None, "type": None, "function": {"name": "", "arguments": ""}},
        )
        if p.get("id") is not None:
            cur["id"] = p["id"]
        if p.get("type") is not None:
            cur["type"] = p["type"]
        fn = p.get("function")
        if isinstance(fn, dict):
            if fn.get("name"):
                cur["function"]["name"] = cur["function"]["name"] + (fn["name"] or "")
            if fn.get("arguments") is not None:
                cur["function"]["arguments"] += str(fn["arguments"])
        elif fn is not None and hasattr(fn, "name"):
            if getattr(fn, "name", None):
                cur["function"]["name"] += fn.name or ""
            if getattr(fn, "arguments", None) is not None:
                cur["function"]["arguments"] += str(fn.arguments)


def probe_tool_calls_stream(
    client: OpenAI,
    *,
    model: str,
    temperature: float,
    verbose: bool,
) -> None:
    print("\n" + "=" * 60)
    print("C) 流式 + tools —— 分片 delta.tool_calls 与合并结果")
    print("=" * 60)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "report_integer",
                "description": "上报整数。",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"],
                },
            },
        }
    ]

    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "需要上报整数时调用 report_integer。"},
            {"role": "user", "content": "用工具上报 7。"},
        ],
        tools=tools,
        tool_choice="auto",
        stream=True,
        temperature=temperature,
    )

    merged: dict[int, dict[str, Any]] = {}
    top_keys: set[str] = set()
    last_finish: Any = None

    for idx, chunk in enumerate(stream):
        d = chunk.model_dump(exclude_none=False)
        top_keys |= set(d.keys())
        ch0 = (d.get("choices") or [{}])[0]
        last_finish = ch0.get("finish_reason")
        delta = ch0.get("delta") or {}
        _accumulate_delta_tool_calls(merged, delta.get("tool_calls"))

        if verbose:
            _dump(f"C tools+stream chunk[{idx}]", chunk)
        else:
            print(
                f"[{idx}] finish_reason={ch0.get('finish_reason')} "
                f"delta.role={delta.get('role')} "
                f"content_snip={repr(delta.get('content'))[:72]} "
                f"tool_calls_frag={delta.get('tool_calls')}"
            )

    print("\n=== C 见过的流式顶层键（除 choices） ===")
    extras = sorted(top_keys - {"choices"})
    print(extras)
    print("\n=== C 末尾 choices[0].finish_reason ===", last_finish)
    pretty = json.dumps(merged, ensure_ascii=False, indent=2)
    print("\n=== C 客户端合并后的 tool_calls（按 index）===\n" + pretty)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从 backend/.env 加载百炼密钥与模型探针 Chat Completions。"
    )
    parser.add_argument("--verbose-stream", action="store_true")
    parser.add_argument("--verbose-tools-stream", action="store_true")
    parser.add_argument(
        "--only",
        choices=("stream", "tools", "tools_stream", "all"),
        default="all",
    )
    parser.add_argument("--api-key", default=None)
    parser.add_argument(
        "--env-file",
        default=None,
        help="可选，覆盖默认 backend/.env 路径（用于 CI）",
    )
    args = parser.parse_args()

    env_explicit = Path(args.env_file).resolve() if args.env_file else None
    cli_key = args.api_key
    key, base_url, model, temperature = _read_client_config(cli_key, env_explicit)

    if not key:
        cand = env_explicit if env_explicit is not None else BACKEND_ROOT / ".env"
        print(
            f"（诊断）加载 env 路径: {cand} ，文件存在={cand.exists()}",
            file=sys.stderr,
        )
        print(
            "❌ DASHSCOPE_API_KEY 为空。请在 backend/.env 填入密钥或使用 --api-key。",
            file=sys.stderr,
        )
        return 2

    print("MODEL =", model)
    print("BASE_URL =", base_url)
    print("TEMPERATURE =", temperature)
    client = OpenAI(api_key=key, base_url=base_url)

    try:
        if args.only in ("stream", "all"):
            probe_stream_verbose(
                client, model=model, temperature=temperature, verbose=args.verbose_stream
            )
        if args.only in ("tools", "all"):
            probe_tool_calls_non_stream(
                client, model=model, temperature=temperature
            )
        if args.only in ("tools_stream", "all"):
            probe_tool_calls_stream(
                client,
                model=model,
                temperature=temperature,
                verbose=args.verbose_tools_stream,
            )
    except APIStatusError as err:
        print(f"\n❌ APIStatusError HTTP {err.status_code}", file=sys.stderr)
        try:
            print(json.dumps(err.body, ensure_ascii=False, indent=2), file=sys.stderr)
        except (TypeError, ValueError):
            print(err.body, file=sys.stderr)
        return 1

    print(
        "\n✅ 完成。解析工具结果时请始终合并流式 ``delta.tool_calls`` 片段，"
        "非流式则直接读 ``message.tool_calls``。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

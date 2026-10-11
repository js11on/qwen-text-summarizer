# -*- coding: utf-8 -*-
"""
通义文本摘要工具 · Web 版服务端

零第三方依赖，仅使用 Python 标准库。
- 静态页面：index.html
- 接口：POST /api/summarize  (Server-Sent Events 流式返回)
- 配置：同目录 config.json（可用同名环境变量覆盖）

原始命令行版本 main.py 的摘要逻辑（简短/详细、长文本分段+汇总）在此完整保留。
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- 可调参数 ----------
CHUNK_SIZE = 1200        # 长文本分段长度（与 main.py 一致）
CHUNK_OVERLAP = 150      # 分段重叠长度（与 main.py 一致）
LONG_TEXT_THRESHOLD = 1500   # 超过该长度走分段摘要
MAX_INPUT_CHARS = 60000      # 单次输入上限，防止额度被单次耗尽
RATE_LIMIT_WINDOW = 600      # 限流窗口（秒）
RATE_LIMIT_MAX = 20          # 每个 IP 在窗口内最多请求次数
UPSTREAM_TIMEOUT = 180       # 单次上游调用超时（秒）

# ---------- 提示词（与 main.py 一致） ----------
SYSTEM_SHORT = "你是文本摘要助手，输出简短摘要，控制在100字以内，只保留核心要点。"
SYSTEM_DETAIL = "你是文本摘要助手，输出详细摘要，完整保留文章关键逻辑、要点，条理清晰。"
SYSTEM_COMBINE = "你是文本摘要助手，将下面多段摘要整合成一份连贯完整的摘要，不要重复。"


def load_config():
    cfg = {"DASHSCOPE_API_KEY": "", "BASE_URL": "", "MODEL_NAME": ""}
    path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as exc:  # noqa: BLE001
            print("[warn] 读取 config.json 失败：%s" % exc)
    # 环境变量优先，便于在部署环境覆盖
    for key in list(cfg.keys()):
        env_val = os.environ.get(key)
        if env_val:
            cfg[key] = env_val
    return cfg


CONFIG = load_config()

_rate_bucket = defaultdict(list)
_rate_lock = __import__("threading").Lock()


def rate_limited(ip):
    now = time.time()
    with _rate_lock:
        hits = [t for t in _rate_bucket[ip] if now - t < RATE_LIMIT_WINDOW]
        if len(hits) >= RATE_LIMIT_MAX:
            _rate_bucket[ip] = hits
            return True
        hits.append(now)
        _rate_bucket[ip] = hits
        return False


def split_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """文本分段，带重叠，防止上下文断裂（同 main.py）。"""
    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += step
    return chunks


def upstream_chat(messages, model, api_key, base_url, stream=False):
    """
    调用 OpenAI 兼容接口。
    stream=False -> 返回完整文本
    stream=True  -> 生成器，逐段 yield 增量文本
    """
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "stream": bool(stream),
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        },
    )
    resp = urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT)

    if not stream:
        raw = json.loads(resp.read().decode("utf-8"))
        return raw["choices"][0]["message"]["content"]

    def gen():
        while True:
            line = resp.readline()
            if not line:
                break
            line = line.decode("utf-8", errors="ignore").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            piece = delta.get("content")
            if piece:
                yield piece

    return gen()


def sse(payload):
    return ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "QwenSummaryWeb/1.0"

    # ---------- 工具方法 ----------
    def log_message(self, fmt, *args):  # 精简日志
        print("[%s] %s" % (self.address_string(), fmt % args))

    def _send_bytes(self, body, status=200, ctype="application/octet-stream"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=200):
        self._send_bytes(
            json.dumps(obj, ensure_ascii=False).encode("utf-8"),
            status,
            "application/json; charset=utf-8",
        )

    # ---------- 路由 ----------
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            fp = os.path.join(BASE_DIR, "index.html")
            if not os.path.exists(fp):
                self._json({"error": "index.html 缺失"}, 500)
                return
            with open(fp, "rb") as f:
                self._send_bytes(f.read(), 200, "text/html; charset=utf-8")
            return
        if path == "/health":
            self._json({"ok": True, "model": CONFIG.get("MODEL_NAME")})
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/api/summarize":
            self._json({"error": "not found"}, 404)
            return

        ip = self.client_address[0]
        if rate_limited(ip):
            self._json({"error": "请求过于频繁，请稍后再试（窗口内上限 %d 次）" % RATE_LIMIT_MAX}, 429)
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 10 * 1024 * 1024:
            self._json({"error": "请求体为空或过大"}, 400)
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:  # noqa: BLE001
            self._json({"error": "请求体不是合法 JSON"}, 400)
            return

        text = (payload.get("text") or "").strip()
        style = payload.get("style") or "short"
        if style not in ("short", "detail"):
            style = "short"

        if not text:
            self._json({"error": "请先输入或上传需要摘要的文本"}, 400)
            return
        if len(text) > MAX_INPUT_CHARS:
            self._json(
                {"error": "文本过长（%d 字），单次上限 %d 字，请分段后再试" % (len(text), MAX_INPUT_CHARS)},
                400,
            )
            return

        api_key = CONFIG.get("DASHSCOPE_API_KEY")
        base_url = CONFIG.get("BASE_URL")
        model = CONFIG.get("MODEL_NAME")
        if not (api_key and base_url and model):
            self._json({"error": "服务端未配置模型参数（config.json 缺少 API Key / BASE_URL / MODEL_NAME）"}, 500)
            return

        # ---- 开始 SSE ----
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(obj):
            self.wfile.write(sse(obj))
            self.wfile.flush()

        try:
            system_prompt = SYSTEM_SHORT if style == "short" else SYSTEM_DETAIL
            is_long = len(text) > LONG_TEXT_THRESHOLD

            if not is_long:
                emit({"type": "progress", "message": "正在生成摘要…"})
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "请对下面文本做摘要：\n" + text},
                ]
                collected = []
                for piece in upstream_chat(messages, model, api_key, base_url, stream=True):
                    collected.append(piece)
                    emit({"type": "delta", "content": piece})
                final = "".join(collected)
            else:
                chunks = split_text(text)
                emit({"type": "progress", "message": "文本较长，已自动切分为 %d 段，开始分段摘要…" % len(chunks)})
                part_summaries = []
                for idx, chunk in enumerate(chunks):
                    emit({"type": "progress", "message": "正在处理第 %d/%d 段…" % (idx + 1, len(chunks))})
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "请对下面文本做摘要：\n" + chunk},
                    ]
                    part_summaries.append(upstream_chat(messages, model, api_key, base_url, stream=False))
                emit({"type": "progress", "message": "正在合并各分段结果，生成全文总摘要…"})
                messages = [
                    {"role": "system", "content": SYSTEM_COMBINE},
                    {"role": "user", "content": "各分段摘要内容：\n" + "\n".join(part_summaries) + "\n\n输出最终全文摘要"},
                ]
                collected = []
                for piece in upstream_chat(messages, model, api_key, base_url, stream=True):
                    collected.append(piece)
                    emit({"type": "delta", "content": piece})
                final = "".join(collected)

            if not final.strip():
                emit({"type": "error", "message": "模型未返回内容，请重试或更换模型"})
            else:
                emit({"type": "done", "summary": final, "chars": len(text),
                      "chunks": 1 if not is_long else len(split_text(text))})
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="ignore")[:300]
            except Exception:  # noqa: BLE001
                pass
            emit({"type": "error", "message": "模型接口返回 %s：%s" % (exc.code, detail or exc.reason)})
        except Exception as exc:  # noqa: BLE001
            emit({"type": "error", "message": "调用失败：%s" % exc})


def main():
    port = int(os.environ.get("PORT") or 3000)
    host = "0.0.0.0"
    missing = [k for k in ("DASHSCOPE_API_KEY", "BASE_URL", "MODEL_NAME") if not CONFIG.get(k)]
    if missing:
        print("[warn] config.json 缺少配置：%s" % ", ".join(missing))
    print("通义文本摘要工具 Web 版已启动：http://%s:%d  (model=%s)" % (host, port, CONFIG.get("MODEL_NAME")))
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()

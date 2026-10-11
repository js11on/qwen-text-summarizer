# 通义文本摘要工具 · Web 版

`main.py` 命令行版的网页化实现，零第三方依赖（仅 Python 标准库），可一键部署为在线应用。

## 功能

- **手动输入摘要**：直接粘贴文本生成摘要
- **上传 txt 文件**：浏览器端读取本地 txt / md，内容不入库、不上传服务器
- **简短 / 详细摘要**：与命令行版相同的两套提示词
- **长文本自动分段**：超过 1500 字自动按 1200 字/段（重叠 150 字）切分，逐段摘要后再汇总，避免超长文本截断
- **流式输出**：模型生成过程实时逐字显示，可随时点击「停止」
- **结果导出**：一键复制或下载为 `summary.txt`（对应原版的 `result.txt`）

## 运行方式

```bash
python server.py
# 默认监听 0.0.0.0:3000，可通过 PORT 环境变量覆盖
```

浏览器访问 http://localhost:3000

## 配置

复制模板文件后填入自己的密钥：

```bash
cp config.example.json config.json
```

`config.json`：

```json
{
  "DASHSCOPE_API_KEY": "sk-...",
  "BASE_URL": "https://<workspace>.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
  "MODEL_NAME": "qwen3.8-max"
}
```

同名环境变量优先级高于 `config.json`，便于在部署环境覆盖。

> ⚠️ **安全说明**：`config.json` 内含 API Key，仅存在于服务端，不会下发到浏览器（`server.py` 只对外暴露 `/`、`/health`、`/api/summarize`，其他路径一律 404，无法直接下载配置文件）。
>
> 该文件已在仓库根目录 `.gitignore` 中忽略（规则：`.env`、`config.json`、`web/config.json`），**不要提交到公开仓库**；需要分享配置格式时请使用不含真实密钥的 `config.example.json`。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 前端页面 |
| GET | `/health` | 健康检查，返回当前模型名 |
| POST | `/api/summarize` | 摘要接口，SSE 流式返回 |

`POST /api/summarize` 请求体：

```json
{ "text": "需要摘要的文本", "style": "short | detail" }
```

SSE 事件类型：`progress`（进度提示）、`delta`（内容增量）、`done`（完成，含 `summary`）、`error`（错误）。

## 防护

- 单次输入上限 60000 字
- 每 IP 10 分钟内最多 20 次请求
- 上游单次调用超时 180 秒

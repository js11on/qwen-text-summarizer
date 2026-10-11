# qwen-text-summarizer

基于 **LangChain + 通义千问（阿里云百炼）** 的文本摘要工具，提供**命令行版**与**网页版**两种用法。

## 在线体验

网页版已部署上线，打开浏览器即可使用，无需安装任何环境：

**https://qwen-text-summarizer.app.workbuddy.host/**

## 功能特性

- **两种摘要风格**：简短摘要（100 字以内，只留核心要点）/ 详细摘要（完整保留关键逻辑与要点）
- **两种输入方式**：手动输入文本，或读取本地 txt 文件（网页版支持直接上传）
- **长文本自动分段**：超过阈值自动按 1200 字/段（重叠 150 字）切分，逐段摘要后再汇总，避免超长文本被截断或丢失上下文
- **结果可留存**：命令行版自动写入 `result.txt`，网页版支持一键复制 / 下载
- **网页版流式输出**：模型逐字生成实时可见，可随时中止

## 目录结构

```
qwen-text-summarizer/
├── main.py                 # 命令行版入口
├── requirements.txt        # 命令行版依赖
├── test.txt                # 示例文本
├── .env                    # 密钥配置（需自行创建，已被 .gitignore 忽略）
└── web/                    # 网页版
    ├── server.py           # 零依赖 HTTP 服务（仅用 Python 标准库）
    ├── index.html          # 前端页面（单文件，无构建步骤）
    ├── config.json         # 网页版密钥配置（需自行创建，已被忽略）
    ├── config.example.json # 配置模板
    └── README.md           # 网页版详细说明
```

---

## 一、命令行版

### 1. 环境要求

Python >= 3.8（开发环境为 3.8.10；早期 README 写的 3.10 并非硬性要求）

### 2. 安装依赖

```bash
git clone https://github.com/js11on/qwen-text-summarizer.git
cd qwen-text-summarizer
pip install -r requirements.txt
```

### 3. 配置模型密钥

在项目根目录新建 `.env` 文件（**不要提交到仓库**，`.gitignore` 已忽略）：

```ini
DASHSCOPE_API_KEY=sk-你的百炼APIKey
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen3.8-max
```

密钥获取：登录[阿里云百炼控制台](https://bailian.console.aliyun.com/) → API-KEY 管理 → 创建。

> 若使用业务空间专属端点，`BASE_URL` 形如
> `https://<workspace-id>.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`

### 4. 运行

```bash
python main.py
```

按提示操作：

```
===== 文本摘要工具 =====
1: 手动输入文本摘要
2: 读取本地txt文件摘要
3: 【新增】长文本txt自动分段摘要
请选择模式(1/2/3):

请选择摘要类型：
1 - 简短摘要
2 - 详细摘要
输入1或2：
```

生成结果会打印在控制台，并自动保存到 `result.txt`。

---

## 二、网页版

网页版把命令行工具封装成了浏览器界面，**仅使用 Python 标准库，无任何第三方依赖**。

### 本地运行

```bash
cd web
python server.py
# 默认监听 0.0.0.0:3000，可用 PORT 环境变量覆盖
```

浏览器打开 http://localhost:3000

### 配置

```bash
cp config.example.json config.json
```

然后编辑 `config.json` 填入密钥（字段与命令行版 `.env` 相同）：

```json
{
  "DASHSCOPE_API_KEY": "sk-...",
  "BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "MODEL_NAME": "qwen3.8-max"
}
```

同名环境变量优先级高于 `config.json`，便于在部署环境覆盖。

### 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 前端页面 |
| GET | `/health` | 健康检查，返回当前模型名 |
| POST | `/api/summarize` | 摘要接口，SSE 流式返回 |

```json
POST /api/summarize
{ "text": "需要摘要的文本", "style": "short" }
```

SSE 事件类型：`progress`（进度）/ `delta`（内容增量）/ `done`（完成）/ `error`（错误）。

### 部署

可部署到任意支持「单端口 HTTP 服务」的平台，要求：

- 监听 `PORT` 环境变量
- 绑定 `0.0.0.0`

---

## 工作原理

1. 文本短于阈值时，直接构造「系统提示词 + 用户文本」调用模型；
2. 文本过长时，按 1200 字一段（相邻段重叠 150 字，防止上下文断裂）切分；
3. 每段独立生成摘要，再把所有分段摘要交给模型合并成一份连贯的全文摘要，避免截断。

模型调用统一走 OpenAI 兼容协议（`/chat/completions`）。

## 安全说明

- `.env`、`config.json`（含 API Key）均已写入 `.gitignore`，**不会进入仓库**
- 网页版服务端只对外暴露 `/`、`/health`、`/api/summarize` 三个路径，不做静态目录托管，配置文件无法被下载
- 如需分享配置格式，请使用不含真实密钥的 `config.example.json`

## 已知限制

- 摘要质量与速度取决于所选模型，长文本会产生多次模型调用
- 网页版的流式输出会忽略模型的思考过程（`reasoning_content`），只展示最终摘要

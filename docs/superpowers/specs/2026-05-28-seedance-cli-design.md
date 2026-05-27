# seedance-cli 设计文档

**日期**：2026-05-28
**状态**：设计已确认，待落实施计划
**架构参照**：`/Users/andrew/work/trae_project/gpt-image-cli`（Node/TS 同款模式，本项目用 Python 实现）

---

## 0. 项目目标与范围

把 Volcengine Ark 平台的 **Doubao Seedance 视频生成 API** 封装成一个本地 CLI（`seedance-cli`），并配套一个供 Claude Code / AI agent 使用的 **SKILL**。

**v1 覆盖**：
- 核心生成：文生视频 / 图生视频-首帧 / 图生视频-首尾帧 / 多模态参考生视频
- 视频编辑、视频延长（seedance 2.0）
- 任务管理：list / get / delete
- 配置管理：多 profile（单 Bearer 鉴权）

**v1 明确不做**（避免 scope creep）：
- Draft / 样片模式（`--draft`、`--from-draft`）
- 内置 webhook server（仅留 `--callback-url` flag）
- TOS 直传（>64 MB 请求体场景）
- 并发批量调度
- 联网搜索工具
- 中文 prompt 自动改写

---

## 1. 整体结构

```
seedance-cli/
├── pyproject.toml              # uv + hatchling；console_scripts: seedance-cli
├── README.md
├── src/seedance_cli/
│   ├── __init__.py
│   ├── __main__.py             # 装 click 根命令 + 全局 flags + 错误兜底
│   ├── framework/              # 通用层（与领域无关）
│   │   ├── envelope.py         # {ok, data} | {ok:false, error:{...}} 渲染 + --jq
│   │   ├── errors.py           # CliError 类 + exit code 表 + Ark SDK 异常翻译
│   │   └── types.py
│   ├── core/                   # 领域核心
│   │   ├── client.py           # 包 volcenginesdkarkruntime.Ark，按 profile 注入 key
│   │   ├── config.py           # ~/.seedance-cli/config.json，profile + 迁移 + chmod 600
│   │   ├── content.py          # 把 --image/--video/--audio[:role] 折成 API content[]
│   │   ├── media_io.py         # 本地文件读取 + base64 编码 + 大小校验 + MIME 嗅探
│   │   ├── polling.py          # 轮询 + 退避 + Ctrl-C 优雅退出 + 进度
│   │   ├── download.py         # video_url / last_frame_url → 本地文件
│   │   └── naming.py           # --out auto 时的命名规则
│   └── commands/
│       ├── generate.py         # 唯一生成命令
│       ├── task.py             # task list / get / delete 子组
│       └── config.py           # config init/set/show/add/use/list
├── skills/
│   └── seedance/SKILL.md
└── tests/
    ├── conftest.py             # FakeArk fixture、临时 config 目录
    ├── unit/                   # core/* + framework/*
    └── integration/            # CliRunner 端到端
```

**关键边界**：
- `framework/` 不知道 Ark —— 纯 envelope / error 框架，可复用
- `core/client.py` 是 Volcengine SDK 唯一接触面，dry-run 与测试都靠替换它
- `core/content.py` 是命令面方案 A 的核心 —— 纯函数 `build_content(...) -> list[dict]`，单测覆盖所有形状
- `core/polling.py` 单独抽出，所有 `--wait` 路径共用

---

## 2. 命令与标志面

### 2.1 根命令全局 flags

| Flag | 用途 | 默认 |
|---|---|---|
| `--endpoint URL` | 覆盖 base_url | `https://ark.cn-beijing.volces.com/api/v3` |
| `--api-key KEY` | 覆盖 API key | env `ARK_API_KEY` → 当前 profile |
| `--profile NAME` | 选 profile，本次有效 | env `SEEDANCE_PROFILE` → config 的 active |
| `--format json\|table` | 输出形态 | `json` |
| `--jq EXPR` | 过滤 envelope | — |
| `--dry-run` | 打印请求体不发 | false |
| `--verbose` | stderr 打调试栈 | false |

### 2.2 `generate` —— 唯一生成命令（方案 A）

```
seedance-cli generate -p "<prompt>" [--image PATH[:role]]... [--video PATH[:role]]... \
                       [--audio PATH]... [<规格 flags>] [<等待/输出 flags>]
```

**内容输入**

| Flag | 说明 |
|---|---|
| `-p, --prompt TEXT` | 文本提示词。可省略（仅当存在其它 content） |
| `--image PATH_OR_URL[:ROLE]` | 可重复。ROLE ∈ `first_frame` / `last_frame` / `reference`，省略=无 role |
| `--video PATH_OR_URL[:ROLE]` | 可重复。ROLE ∈ `reference` |
| `--audio PATH_OR_URL` | 可重复，最多 3 |
| `--from-json PATH` | 整请求体读 JSON，其它 flag 仍可覆盖 |

> 本地路径自动 base64；`http(s)://` 直接当 URL 传。

**模型与输出规格**

| Flag | 取值 / 默认 |
|---|---|
| `-m, --model` | 默认 `doubao-seedance-2-0-260128`。接受别名 `2.0` / `2.0-fast` / `1.5-pro` / `1.0-pro` / `1.0-pro-fast`，内部映射成完整 model id |
| `--ratio` | `21:9` / `16:9` / `4:3` / `1:1` / `3:4` / `9:16` / `adaptive` |
| `--resolution` | `480p` / `720p` / `1080p` |
| `--duration N` | 秒数；与 `--frames` 互斥 |
| `--frames N` | 仅 1.0-pro / 1.0-pro-fast |
| `--seed N` | |
| `--camera-fixed / --no-camera-fixed` | 1.5-pro / 1.0-pro / 1.0-pro-fast |
| `--watermark / --no-watermark` | **默认 `--no-watermark`**（与 API 默认相反；SKILL 场景几乎不要水印） |
| `--generate-audio / --no-generate-audio` | 2.0 / 2.0-fast / 1.5-pro |
| `--return-last-frame` | 响应里多 `last_frame_url`，给 SKILL 接龙用 |
| `--service-tier default\|flex` | flex = 离线推理，价格 50% |
| `--execution-expires-after SECONDS` | 仅 flex |
| `--callback-url URL` | webhook |

**等待与输出**

| Flag | 默认 / 说明 |
|---|---|
| `--out PATH` | MP4 落盘路径。结尾 `/` 当目录（不存在则 `mkdir -p` 自动创建），文件名 = `<created_at>-<task_id短码>.mp4`；非斜杠结尾视为完整文件路径，父目录不存在则报 `IO_ERROR`，不静默 mkdir。不传 = 落 cwd 用自动文件名 |
| `--out-last-frame PATH` | 配 `--return-last-frame`，把尾帧图也下载；路径语义同 `--out` |
| `--async` | fire-and-forget，立即返回含 task_id 的 envelope |
| `--no-download` | 阻塞到 succeeded 但不下载，envelope 给 `video_url` |
| `--poll-interval N` | 用户显式传则一律生效；不传时按当次 `--service-tier` 推默认：`default`=10s / `flex`=60s |
| `--timeout N` | 默认无（依赖 API 24h 过期） |

### 2.3 `task` —— 任务管理

```
seedance-cli task list   [--status queued|running|succeeded|failed|expired]
                          [--model M] [--page-size N] [--page-token T]
seedance-cli task get    <task_id> [--wait] [--out PATH]
seedance-cli task delete <task_id>          # 也用于取消 queued
```

`task get --wait --out path.mp4` = 把 `--async` 留下的任务接回阻塞-下载路径。

### 2.4 `config` —— 多 profile

只有 Bearer key 一种鉴权，比 gpt-image-cli 的 OpenAI/Azure 分叉简单：

```
seedance-cli config init                    [--yes]
seedance-cli config add <name>              [--yes]
seedance-cli config use <name>
seedance-cli config list                    # active 标 *
seedance-cli config show [<name>]           # api_key 脱敏: sk-***last4
seedance-cli config set <key> <value>       # key ∈ api_key|endpoint|default_model
seedance-cli config unset <key>             # 重置该字段
```

---

## 3. 内容模型（方案 A 核心）

`content.py` 提供纯函数：
```python
def build_content(text: str | None,
                  images: list[MediaRef],
                  videos: list[MediaRef],
                  audios: list[MediaRef],
                  model: str) -> list[dict]
```

### 3.1 折叠规则

CLI 顺序 → API `content[]` 顺序：**text → images → videos → audios**（同类内按 CLI 出现顺序）。

**`PATH:ROLE` 语法**：按**最后一个** `:` 切分，仅当后缀 ∈ `{first_frame, last_frame, reference}` 才识别为 role，否则整串当 PATH。避免 `https://host:8080/x.png` 被错切。

### 3.2 场景识别（无需用户声明）

| 场景 | 触发条件 | content[] 形态 |
|---|---|---|
| 文生视频 | 仅 `-p` | `[text]` |
| 图生视频-首帧 | `-p` + 1 image（无 role 或 `:first_frame`） | `[text, image]` |
| 图生视频-首尾帧 | 2 image 且分别带 `:first_frame` / `:last_frame` | `[text, image(first), image(last)]` |
| 多模态参考（2.0） | 1–9 image 无 role | `[text, image×N]` |
| 视频编辑/延长（2.0） | 含 `--video` | `[text, video, ...]` |
| 多模态组合（2.0） | image + video + audio 任意组合 | `[text, image×, video×, audio×]` |

### 3.3 校验矩阵（build 阶段同步抛 `INVALID_INPUT`，不等 API）

**输入约束**
- 单图 ≤ 30 MB；jpeg/png/webp/bmp/tiff/gif（+heic/heif 当模型 ∈ {1.5-pro, 2.0, 2.0-fast}）；宽高 300–6000 px；宽高比 0.4–2.5
- 单视频 ≤ 50 MB；mp4/mov；时长 2–15s；FPS 24–60
- 单音频 ≤ 15 MB；wav/mp3；时长 2–15s
- 视频总数 ≤ 3、视频总时长 ≤ 15s；音频总数 ≤ 3、音频总时长 ≤ 15s
- 请求体总大小 ≤ 64 MB（base64 编码后估算）
- 多模态参考图片数 1–9（仅 2.0 系列）；首尾帧场景图片数 = 2 且 role 必须配对

**模型 × 参数兼容性**

| 参数 | 限定 |
|---|---|
| `--generate-audio` | 2.0 / 2.0-fast / 1.5-pro |
| `--frames` | 仅 1.0-pro / 1.0-pro-fast；取值满足 `25 + 4n ∈ [29, 289]` |
| `--camera-fixed` | 1.5-pro / 1.0-pro / 1.0-pro-fast |
| `--service-tier flex` | 1.5-pro / 1.0-pro / 1.0-pro-fast（2.0 系列不支持） |
| `--resolution 1080p` | 不允许 2.0-fast |
| `--duration` 范围 | 2.0 / 2.0-fast / 1.5-pro: 4–15；1.0-pro 系列: 2–12 |
| `--duration` ⊕ `--frames` | 互斥 |
| 真人人脸参考图 | 2.0 系列不支持（CLI 无法预检，依赖 API 报错翻译） |

错误信息必含三段：用了什么模型 / 当前 flag / 哪条约束触发。

### 3.4 Base64 编码与本地/远程混用

`media_io.py` 入口：
```python
def to_payload(path_or_url: str, kind: Literal["image","video","audio"]) -> dict:
    # http(s)://  →  {"url": <as-is>}
    # 本地路径    →  读字节 + 校验大小/格式 → {"url": "data:<mime>;base64,<...>"}
    # 累计请求体大小，超 64MB 减余量则抛 INVALID_INPUT 并提示先传 URL
```

**待实施时确认**：Volcengine 是否真正接受 data URI 形式塞 `image_url.url` 字段，或要求 `image_url.b64_json` 这种独立字段。实现阶段读官方 SDK 源码定。

### 3.5 dry-run

`--dry-run` 走到 `build_content` 之后停，envelope 输出完整请求体。base64 内容用 `<base64 ${size_kb}KB>` 占位，避免污染终端。

---

## 4. 配置与 Profile

### 4.1 配置文件 schema (`~/.seedance-cli/config.json`)

```json
{
  "version": 1,
  "active": "default",
  "profiles": {
    "default": {
      "api_key": "...",
      "endpoint": "https://ark.cn-beijing.volces.com/api/v3",
      "default_model": null
    }
  }
}
```

- 创建/写入时 `chmod 600`；父目录自动创建
- `version: 1` 起步，将来 schema 变了用它做迁移分支
- 没有 `api_key` 时只允许只读子命令（`config list/show`、`task list`），其它命令在 `client.py` 实例化时抛 `CONFIG_MISSING`

### 4.2 鉴权解析优先级

```
api_key:  --api-key flag       > env ARK_API_KEY       > profile.api_key
endpoint: --endpoint flag      > env SEEDANCE_ENDPOINT > profile.endpoint > 内置默认
profile:  --profile flag       > env SEEDANCE_PROFILE  > config.active    > "default"
model:    -m flag（含别名展开）> profile.default_model > 内置 doubao-seedance-2-0-260128
```

`--api-key` / `--endpoint` 是字段级覆盖，不会让 `--profile` 失效。

### 4.3 模型别名表（`core/client.py` 暴露成常量）

```python
MODEL_ALIASES = {
    "2.0":          "doubao-seedance-2-0-260128",
    "2.0-fast":     "doubao-seedance-2-0-fast-260128",
    "1.5-pro":      "doubao-seedance-1-5-pro-251215",
    "1.0-pro":      "doubao-seedance-1-0-pro-250528",
    "1.0-pro-fast": "doubao-seedance-1-0-pro-fast-251015",
}
```

未来上新模型只动这张表 + 第 3.3 节兼容矩阵两处。

### 4.4 交互式向导

`config init` / `config add` 需要 TTY，无 TTY 报错并提示用 `config set`。问 3 个字段（带回车默认值）：

```
? API key:                                 [必填，输入时隐藏]
? Endpoint:                                [https://ark.cn-beijing.volces.com/api/v3]
? Default model (回车跳过):                [doubao-seedance-2-0-260128]
```

`config init` 总写 `default`，已有就询问覆盖（遵守 `--yes`）。`config add <name>` 写新 profile 并询问是否 `use`。

---

## 5. 输出 Envelope、错误模型、退出码

### 5.1 Envelope 契约

成功：
```json
{ "ok": true, "data": { ... } }
```

失败：
```json
{
  "ok": false,
  "error": {
    "code": "INVALID_INPUT",
    "message": "human-readable single line",
    "details": { /* 结构化上下文 */ }
  }
}
```

不变量：
- envelope **只走 stdout**；进度 / 调试 / spinner 走 stderr
- `--jq` 仅作用于 `data`，envelope 形态保留：`{"ok":true,"data":<过滤后>}`
- `--format table` 只影响成功路径 `data` 的渲染；失败 envelope 一律 JSON

### 5.2 关键成功 envelope 样本

**`generate`（阻塞 + 下载）**
```json
{
  "ok": true,
  "data": {
    "task_id": "cgt-2025...",
    "status": "succeeded",
    "model": "doubao-seedance-2-0-260128",
    "video_url": "https://...mp4",
    "video_path": "/abs/girl-cgt-abc12.mp4",
    "last_frame_url": "https://...",
    "last_frame_path": "/abs/...png",
    "duration": 5, "ratio": "16:9", "resolution": "1080p", "framespersecond": 24,
    "seed": 58944,
    "usage": { "completion_tokens": 246840, "total_tokens": 246840 },
    "service_tier": "default",
    "created_at": 1765510475, "updated_at": 1765510559,
    "elapsed_seconds": 84, "poll_count": 8
  }
}
```

**`generate --async`**
```json
{ "ok": true, "data": { "task_id": "cgt-...", "status": "queued", "model": "...", "created_at": ... } }
```

**`generate --no-download`** —— 同阻塞版但无 `video_path` / `last_frame_path`。

**`task list`**
```json
{ "ok": true, "data": { "tasks": [ {...}, {...} ], "next_page_token": "..." } }
```

**`task get`** —— 透传 Ark 返回，外层包 envelope。

**`config list/show`** —— `api_key` 脱敏为 `sk-***last4`。

### 5.3 退出码表

| Code | 名 | 触发 | SKILL 应对 |
|---|---|---|---|
| 0 | OK | 成功 | — |
| 2 | INVALID_INPUT / CONFIG_MISSING | 参数错 / 没 key | 改参数 或 引导 config init |
| 3 | IO_ERROR | `--out` 路径不可写 / 本地文件读取失败 | 换路径 |
| 4 | ARK_API_ERROR | API 返回非 2xx | 429 退避；400 看 details.message |
| 5 | NETWORK_ERROR | 连接 / 超时 | 重试，多次失败核对 endpoint |
| 6 | TASK_FAILED | 模型 `status=failed` | 看 `details.error`（多半内容策略 / 输入图问题） |
| 7 | TASK_EXPIRED | `status=expired` 或 24h 后查询 | 重新建任务 |
| 8 | POLL_TIMEOUT | 用户 `--timeout` 命中 | envelope 含 task_id，用 `task get` 续 |
| 9 | POLL_CANCELLED | Ctrl-C 退出轮询 | 同上 |
| 10 | INTERNAL | bug | 报 issue |

**关键设计**：6/7/8/9 都"任务建出来了但当前调用没走完"，envelope 必须含 `task_id`，让 SKILL 按 ID 续杯而不是从头重发。

### 5.4 错误翻译（`framework/errors.py`）

```python
def translate(exc: Exception) -> CliError:
    # volcenginesdkarkruntime.ArkAPIError       → ARK_API_ERROR  (status_code / code / message / request_id)
    # httpx.ConnectError / TimeoutException     → NETWORK_ERROR
    # OSError / PermissionError on file ops     → IO_ERROR
    # CliError (自己抛的)                       → 原样返回
    # 其它                                      → INTERNAL（traceback 仅 --verbose）
```

轮询循环里：
```python
if status == "failed":  raise CliError("TASK_FAILED",  details={"error": resp.error})
if status == "expired": raise CliError("TASK_EXPIRED", details={"task_id": id})
```

Ctrl-C `signal` handler：
```python
raise CliError("POLL_CANCELLED",
               details={"task_id": current_task_id,
                        "hint": "resume with: seedance-cli task get <id> --wait --out <path>"})
```

### 5.5 stderr 进度

- 默认：spinner + `[3/10] running... elapsed 32s`，一行就地刷新
- `--verbose`：每轮打一行带时间戳 + 状态 + 请求 id
- envelope 已含 `elapsed_seconds` / `poll_count`，事后能复盘
- 下载阶段：百分比进度条同样只走 stderr

---

## 6. SKILL 设计

### 6.1 元数据

```yaml
---
name: seedance
version: 1.0.0
description: "当用户需要生成视频、首帧/首尾帧生视频、多模态参考生视频、编辑/延长视频，或需要连续多段视频接龙时使用。"
metadata:
  requires:
    bins: ["seedance-cli"]
  cliHelp: "seedance-cli --help"
---
```

触发覆盖：「生成视频」「文生视频」「图生视频」「首帧/首尾帧」「视频编辑/延长」「连续视频」「seedance」「doubao 视频」。

### 6.2 与 gpt-image SKILL 的核心差异

| 维度 | gpt-image | seedance |
|---|---|---|
| 调用周期 | 同步几秒 | 异步几十秒–几分钟 |
| 验证产物 | Read PNG 看画面 | **看不见 MP4**。只能验文件存在 + 元数据 + 可选 ffmpeg 抽帧后 Read 静图 |
| 多轮 | 同 prompt 重生成 | 接龙：本轮尾帧 → 下轮首帧 |

**结论**：seedance 的"多轮"语义和 gpt-image 完全不同 —— gpt-image 是"同一画面 A/B 改"，seedance 是"故事板下一镜"。SKILL 必须分开讲，不让 Claude 套 gpt-image 心智。

### 6.3 SKILL.md 段落结构

1. **前置**：检查 `seedance-cli` 在 PATH；`ARK_API_KEY` 或 `config init`
2. **多 profile 配置**：和 gpt-image SKILL 同款 `config add/use/show/list`
3. **核心命令速查**：文生 / 首帧 / 首尾帧 / 多模态参考 / 编辑 / 延长 6 行示例 + `task list/get/delete` 3 行
4. **模型选型表**（见 6.4）
5. **参数选型表**：resolution / ratio / duration 的"什么场景用什么"
6. **本地输入 vs URL**：自动 base64 限额 + 超限怎么办
7. **连续视频接龙 workflow**（本 SKILL 最大价值，见 6.5）
8. **异步与任务管理 workflow**：什么时候用 `--async`；POLL_CANCELLED 怎么 `task get` 续
9. **产物验证**：MP4 看不见，怎么用 ffmpeg 抽帧 Read 抽样
10. **常见错误处置**：按 §5.3 退出码表给应对话术
11. **Red Flags / 不要做**
12. **安全与预期**：耗时、计费、key 别写 shell history

### 6.4 模型选型表

| 想要 | 模型 | 关键差异 |
|---|---|---|
| 默认 / 最强 | `2.0` | 全能力，含多模态参考/编辑/延长/有声 |
| 又快又省 | `2.0-fast` | 同 2.0 但无 1080p，企业 RPM=600 |
| 离线推理省钱 | `1.5-pro --service-tier flex` | 2.0 不支持 flex；价格 50% |
| 样片低成本试错 | （v1 暂不实现）`1.5-pro --draft` | — |
| 指定帧数 | `1.0-pro --frames 29` | 唯一支持 frames 参数 |

### 6.5 连续视频接龙 workflow（SKILL §7，主战场）

**触发**：用户说"做一段连续故事 / 接着上一段 / 接龙生成 / 多段视频"。

**产物目录**
```
story/<topic>/
├── clip-1.mp4
├── clip-2.mp4
├── clip-3.mp4
├── last-frame-1.png   # 自动落盘的接续素材
├── last-frame-2.png
└── final.mp4          # 用户拍板后用 ffmpeg 拼出的成片
```

**Step 1 — 写分镜**：让用户先给 N 段提示词；只给一段总意图时，Claude 先拆成 3-5 段分镜并复述给用户确认。

**Step 2 — 首段**：
```bash
seedance-cli generate -m 2.0 \
  -p "<clip-1 prompt>" \
  [--image start.png:first_frame] \
  --return-last-frame \
  --ratio 16:9 --resolution 720p --duration 5 \
  --out story/<topic>/clip-1.mp4 \
  --out-last-frame story/<topic>/last-frame-1.png
```
读 stdout envelope 拿 `last_frame_path`。

**Step 3 — 续段（循环 i = 2…N）**：
```bash
seedance-cli generate -m 2.0 \
  -p "<clip-i prompt — 必须完整重述视觉要素>" \
  --image story/<topic>/last-frame-{i-1}.png:first_frame \
  --return-last-frame \
  --ratio 16:9 --resolution 720p --duration 5 \
  --out story/<topic>/clip-{i}.mp4 \
  --out-last-frame story/<topic>/last-frame-{i}.png
```

**Step 4 — 跨段一致性 prompt 模板**（仿 gpt-image 4 段模板）：
```
[本段动作]:<这一段主体在做什么>
[延续上段]:<上一段最后的状态 — 主体姿态/场景/光线，必须复述，模型不读上下文>
[配色与风格]:<跨段稳定的视觉调性>
[镜头与节奏]:<本段镜头运动>
```
展开成自然语言一段，去掉 `[...]` 标签。

**Step 5 — 拼接**：所有段成功后给 ffmpeg：
```bash
ffmpeg -f concat -safe 0 \
  -i <(for f in story/<topic>/clip-*.mp4; do echo "file '$PWD/$f'"; done) \
  -c copy story/<topic>/final.mp4
```
不满意时**只重生有问题那段 + 后续所有段**（last_frame 链断了）。

**必须做 / 不要做**
- ✅ 每段 prompt 完整自包含 —— 模型不读对话上下文
- ✅ `--ratio` `--resolution` `--duration` 跨段保持 —— 改了会拼接撕裂
- ✅ 每段成功后告诉用户「clip-i 已落盘，下一段将以本段尾帧续接」
- ❌ 不要在中间段省 `--return-last-frame` / `--out-last-frame`，链就断了
- ❌ 不要在没拿到尾帧的情况下凭脑补写下一段 prompt
- ❌ 跨段不要换模型 / 换 seed / 换 ratio
- ❌ 别 1080p 全开 —— 4 段 1080p 慢且贵；试拍走 720p，定稿再可选 1080p 重出

### 6.6 异步与任务管理 workflow

什么时候用 `--async`：批量提交、任务很长、CI 编排。

恢复模式：
```bash
seedance-cli task list --status running --status queued
seedance-cli task get <id> --wait --out path.mp4
seedance-cli task delete <id>
```

### 6.7 产物验证

实话告诉 Claude：你看不见 MP4。能做的：
1. 确认 `video_path` 存在、`os.path.getsize` 非零
2. 报 envelope 里的 `duration` / `resolution` / `ratio` / `framespersecond`
3. 想"看"内容时：
   ```bash
   ffmpeg -ss 00:00:00 -i clip.mp4 -frames:v 1 preview-first.jpg
   ffmpeg -sseof -1 -i clip.mp4 -frames:v 1 preview-last.jpg
   ```
   再 `Read preview-first.jpg / preview-last.jpg`。没 ffmpeg 就明说"装一下或者你自己看"。

### 6.8 Red Flags / 不要做

- 把 gpt-image"重生成本图"心智搬过来 → 停，seedance 多轮 = 故事接龙
- Read 视频文件 → 停，视频读不出来，要么抽帧要么报元数据
- 没 `--return-last-frame` 接龙 → 停，链断了模型从零构图
- 默认开 1080p → 停，试拍 720p
- 自己 spawn 轮询循环 → 停，CLI 已轮询，用 `--wait` 别绕开
- 多段任务并发派 → 停，接龙必须串行（依赖上段尾帧），且并发受模型限制

---

## 7. 测试、打包、发布

### 7.1 工具链

| 层 | 选型 | 理由 |
|---|---|---|
| 包管理 / 构建 | `uv` + `hatchling` | 当前最快的 Python 工具链 |
| 入口 | `[project.scripts]`：`seedance-cli = "seedance_cli.__main__:main"` | console_scripts 标准；`uv tool install` / `pipx install` 都通 |
| Lint + format | `ruff`（含 isort / pyupgrade） | 单工具，秒级 |
| 类型 | `pyright` strict | 比 mypy 快 |
| 测试 | `pytest` + `pytest-cov` | |
| CLI 测试 | `click.testing.CliRunner` | in-process，不 fork |
| HTTP mock | mock SDK 边界，不 mock HTTP（详 7.3） | SDK 换实现不让测试坍塌 |
| Python | ≥ 3.10 | `match` / PEP 604 |

### 7.2 依赖

```toml
[project]
name = "seedance-cli"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "volcengine-python-sdk[ark]>=…",   # 写时确认最低版本
  "click>=8.1",
  "httpx>=0.27",                       # 视频/尾帧下载用
  "rich>=13",                          # spinner + 进度 + table 渲染
]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff", "pyright", "respx"]

[project.scripts]
seedance-cli = "seedance_cli.__main__:main"
```

不引入 `tqdm`（被 rich 覆盖）/ `pydantic`（v1 数据小，dataclass + 手写校验够用）。

### 7.3 测试分层

```
tests/
├── conftest.py                       # FakeArk fixture、临时 config 目录
├── unit/
│   ├── core/test_content.py          # build_content 6 场景 + 错例
│   ├── core/test_media_io.py         # base64 + 大小校验 + MIME
│   ├── core/test_config.py           # 读写 / 迁移 / chmod / 优先级
│   ├── core/test_client.py           # 别名 + endpoint 默认 + 优先级
│   ├── core/test_naming.py           # --out 是目录 / 文件 / 不传
│   ├── core/test_polling.py          # 状态机 + sigint 注入
│   ├── framework/test_envelope.py    # 成功/失败/jq/--format table
│   └── framework/test_errors.py      # 异常 → CliError 翻译表 + 退出码
└── integration/
    ├── test_generate.py              # CliRunner 6 场景 + --async / --dry-run / --no-download / --return-last-frame
    ├── test_task.py                  # list / get / get --wait / delete
    └── test_config.py                # init / add / use / show / set / 优先级混合
```

### 7.4 Mock 策略：注入 FakeArk

```python
# core/client.py
def make_ark_client(api_key: str, endpoint: str) -> ArkLike:
    return Ark(api_key=api_key, base_url=endpoint)

# conftest.py
class FakeArk:                                         # 实现 ArkLike Protocol
    def __init__(self):
        self.created_tasks: list[dict] = []
        self.scripted_states = [...]                   # 按测试场景注入

@pytest.fixture
def fake_ark(monkeypatch):
    fake = FakeArk()
    monkeypatch.setattr(
        "seedance_cli.core.client.make_ark_client",
        lambda *a, **kw: fake,
    )
    return fake
```

下载路径用 `httpx`，用 `respx` mock（与 SDK mock 隔离）。

### 7.5 dry-run 测试

专门 case：build_content + 渲染请求体 envelope，确认 base64 内容被 `<base64 NNKB>` 占位替换。

### 7.6 CI（GitHub Actions）

**`ci.yml`**（push / PR 触发）：
```
- ruff check + ruff format --check
- pyright
- pytest --cov；上传 codecov
- matrix: python 3.10 / 3.11 / 3.12, ubuntu + macos
```

**`release.yml`**（`v*` tag 触发）：
```
- 重跑 ci.yml 全套
- uv build
- pypa/gh-action-pypi-publish (OIDC trusted publishing)
- 自动建 GitHub Release，从 CHANGELOG.md 抽 release notes
```

### 7.7 包名 + 安装

- PyPI: 先占 `seedance-cli`；占了用 `zjandrew-seedance-cli`
- 用户：`uv tool install seedance-cli` 或 `pipx install seedance-cli`
- 开发：`uv sync --all-extras` → `uv run seedance-cli ...`

SKILL 分发沿用 gpt-image 的 `npx skills add` 路径：仓库根放 `skills/seedance/SKILL.md`，README 给一行 `npx skills add zjandrew/seedance-cli -g -y`。**SKILL 不进 PyPI 包**（Python 用户不需要）。

### 7.8 版本号策略

- **Semver**。CLI flags + envelope schema = 公共 API；删 flag / 改 envelope 字段类型 / 调整退出码语义 = major bump
- SKILL.md 自带 `version:`（frontmatter）独立演进；SKILL 写入"配套 CLI ≥ x.y" 兼容约束
- `0.1.0` 起步；v1 全部命令落齐 + 至少跑通真实 Ark 一次后 `1.0.0`

---

## 8. 实施阶段的待确认项（不阻塞设计，写代码时定）

1. **base64 字段名**：Volcengine 接受 `image_url.url: "data:...;base64,..."` 还是单独的 `image_url.b64_json`？读官方 Python SDK 源码定。
2. **video_url / audio_url 的 content[] 形态**：官方文档只给了 text + image_url 的明确 JSON 样例；video/audio 入参的精确字段名同样要按 SDK 源码核实。
3. **`volcengine-python-sdk[ark]` 最低可用版本**：实测能拉起 `client.content_generation.tasks` 的最早版本即可。
4. **`task list` 是否真支持 `next_page_token` 翻页**：文档只给 `page_size` + `filter.status`，分页协议要 SDK 验证。
5. **真人人脸预检**：2.0 系列不接受真人脸，CLI 无法本地预检（无人脸模型），只能依赖 API 报错后翻译成清晰错误。

---

## 附录：架构参照

`gpt-image-cli` 已经踩过的设计、可以直接复用思路的部分：
- envelope `{ok, data | error}` + `--jq` 形态保留
- profile 多端点 + 字段级 flag 覆盖优先级
- exit code 表
- SKILL 的"工作流 + 必须做 / 不要做 / Red Flags"段落组织
- 包发布脚本（`prepublish` 跑 lint + test + build）

`gpt-image-cli` 没有、本项目新增的关键概念：
- 异步任务模型（轮询、`--async`、`task get/wait/download` 续杯）
- 任务态退出码（TASK_FAILED / TASK_EXPIRED / POLL_TIMEOUT / POLL_CANCELLED）
- 内容数组的多媒体折叠（image + video + audio + role）
- 连续视频接龙 workflow（SKILL 主战场，gpt-image 的"多轮优化"换语义）
- "看不见产物"的产物验证策略（ffmpeg 抽帧 → Read）

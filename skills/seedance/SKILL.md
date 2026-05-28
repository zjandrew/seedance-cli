---
name: seedance
version: 0.1.0
description: "当用户需要生成视频、首帧/首尾帧生视频、多模态参考生视频、编辑/延长视频，或需要连续多段视频接龙时使用。"
metadata:
  requires:
    bins: ["seedance-cli"]
  cliHelp: "seedance-cli --help"
---

# seedance

一句话:本 SKILL 驱动 `seedance-cli`,用 Volcengine Doubao Seedance 系列模型生成 / 编辑 / 延长视频。

**核心原则**:统一走 `seedance-cli` 入口(不手拼 curl);视频生成是异步任务,默认 `seedance-cli generate` 已经做了轮询 + 下载,不要绕开;**Claude 看不见 MP4**,要么验文件存在 + 元数据,要么 ffmpeg 抽帧后 Read 静图。

## 前置

1. 确认 `seedance-cli` 可执行(`which seedance-cli` 或 `seedance-cli --version`)。不可执行则提示用户 `uv tool install seedance-cli` 或 `pipx install seedance-cli`。
2. 配置 API key:优先 env `ARK_API_KEY`;缺失时引导 `seedance-cli config init`。
3. 默认 endpoint 是 `https://ark.cn-beijing.volces.com/api/v3`,自建/代理 endpoint 走 `seedance-cli config set endpoint https://<...>/api/v3` 或 `--endpoint` 单次覆盖。

## 多 profile 配置

```bash
seedance-cli config list                # 列所有 profile,active 标 *
seedance-cli config use <name>          # 切 active
seedance-cli config add <name>          # 向导式新增
seedance-cli --profile <name> generate ...   # 单次覆盖,不改 active
seedance-cli config show [<name>]       # 查看(api_key 已脱敏)
```

优先级:`--profile flag > SEEDANCE_PROFILE env > 文件 active`。`--api-key` / `--endpoint` 是字段级覆盖,不会让 `--profile` 失效。

## 核心命令速查

```bash
# 文生视频
seedance-cli generate -p "<prompt>" --ratio 16:9 --duration 5 --out v.mp4

# 图生视频 - 首帧
seedance-cli generate -p "<prompt>" --image start.png --duration 5 --out v.mp4

# 图生视频 - 首尾帧
seedance-cli generate -p "<prompt>" --image first.png:first_frame --image last.png:last_frame --duration 5 --out v.mp4

# 多模态参考(2.0)
seedance-cli generate -p "<prompt>" --image a.png --image b.png --image c.png --duration 5 --out v.mp4

# 视频编辑 / 延长(2.0)
seedance-cli generate -p "把房子刷成蓝色" --video orig.mp4 --duration 5 --out edited.mp4

# 多模态组合(2.0):图 + 视频 + 音频
seedance-cli generate -p "<prompt>" --image a.png --video b.mp4 --audio bgm.mp3 --out v.mp4

# 任务管理
seedance-cli task list --status running --status queued
seedance-cli task get <task_id> --wait --out path.mp4
seedance-cli task delete <task_id>
```

## 模型选型

| 想要 | 模型 (`-m`) | 关键差异 |
|---|---|---|
| 默认 / 最强 | `2.0`(默认) | 全能力,含多模态参考 / 编辑 / 延长 / 有声 |
| 又快又省 | `2.0-fast` | 同 2.0 但无 1080p |
| 离线推理省钱 | `1.5-pro --service-tier flex` | 2.0 不支持 flex;价格 50% |
| 指定帧数 | `1.0-pro --frames 29` | 唯一支持 `--frames`(满足 25+4n,29-289) |

## 参数选型

| 意图 | 推荐参数 |
|---|---|
| 试拍 / 预览 | `--ratio 16:9 --resolution 720p --duration 5` |
| 横版定稿 | `--ratio 16:9 --resolution 1080p`(2.0-fast 除外) |
| 竖版短视频 | `--ratio 9:16` |
| 跟随首帧自适应宽高比 | `--ratio adaptive` |
| 离线推理 | `-m 1.5-pro --service-tier flex --execution-expires-after 172800` |
| 有声视频 | `--generate-audio`(仅 2.0 / 2.0-fast / 1.5-pro) |
| 拿到尾帧做接龙 | `--return-last-frame --out-last-frame last.png` |

## 本地输入 vs URL

- 本地路径(`./a.png`、`/path/v.mp4`)自动 base64 编码,**注意限额**:单图 ≤ 30 MB、单视频 ≤ 50 MB、单音频 ≤ 15 MB,请求体总 ≤ 64 MB。
- 超限会报 `INVALID_INPUT`,提示先上传到 TOS / OSS 拿到公开 URL,再传 `--image https://...`。
- URL 输入零成本,优先用 URL。

## 连续视频接龙 workflow(本 SKILL 主战场)

**触发**:用户说"做一段连续故事 / 接着上一段 / 接龙生成 / 多段视频"。

**产物目录**
```
story/<topic>/
├── clip-1.mp4
├── clip-2.mp4
├── clip-3.mp4
├── last-frame-1.png
├── last-frame-2.png
└── final.mp4
```

`<topic>` 取自用户对此次任务的简短命名;没给就根据语义自造一个 kebab-case 词,如 `fox-girl-story`。

### Step 1 - 写分镜

让用户先给 N 段提示词。只给一段总意图时,Claude 先拆成 3-5 段分镜并复述给用户确认,**不要直接开生**。

### Step 2 - 首段

```bash
seedance-cli generate -m 2.0 \
  -p "<clip-1 prompt>" \
  [--image start.png:first_frame] \
  --return-last-frame \
  --ratio 16:9 --resolution 720p --duration 5 \
  --out story/<topic>/clip-1.mp4 \
  --out-last-frame story/<topic>/last-frame-1.png
```

读 stdout envelope 拿 `last_frame_path`。**`--ratio` `--resolution` `--duration` 跨段保持不变**,改了会拼接撕裂。

### Step 3 - 续段(循环 i = 2…N)

```bash
seedance-cli generate -m 2.0 \
  -p "<clip-i prompt - 必须完整重述视觉要素>" \
  --image story/<topic>/last-frame-{i-1}.png:first_frame \
  --return-last-frame \
  --ratio 16:9 --resolution 720p --duration 5 \
  --out story/<topic>/clip-{i}.mp4 \
  --out-last-frame story/<topic>/last-frame-{i}.png
```

### Step 4 - 跨段一致性 prompt 模板

照下面 4 段模板**填充**,然后展开成自然语言(去掉 `[...]` 标签):

```
[本段动作]:<这一段主体在做什么>
[延续上段]:<上一段最后的状态 - 主体姿态/场景/光线,必须复述,模型不读上下文>
[配色与风格]:<跨段稳定的视觉调性>
[镜头与节奏]:<本段镜头运动>
```

**不要**写 "like before but..." / "保持上一段不变,只改 X" - 模型没有上下文,它不懂"上一段"。每段 prompt 必须**完整自包含**。

### Step 5 - 拼接

所有段都成功后,给用户一行 ffmpeg:

```bash
ffmpeg -f concat -safe 0 \
  -i <(for f in story/<topic>/clip-*.mp4; do echo "file '$PWD/$f'"; done) \
  -c copy story/<topic>/final.mp4
```

不满意时**只重生有问题的那段 + 后续所有段**(链断了)。

### 必须做

- ✅ 每段 prompt 完整自包含 - 模型不读对话上下文
- ✅ `--ratio` `--resolution` `--duration` 跨段保持
- ✅ 每段成功后告诉用户「clip-i 已落盘,下一段将以本段尾帧续接」

### 必须不做

- ❌ 中间段省 `--return-last-frame` / `--out-last-frame`,链就断了
- ❌ 没拿到尾帧的情况下凭脑补写下一段 prompt
- ❌ 跨段换模型 / 换 seed / 换 ratio
- ❌ 试拍直接 1080p 全开 - 4 段 1080p 慢且贵;先 720p,定稿再 1080p 重出

## 异步与任务管理

什么时候用 `--async`:
- 一次性派多个任务,让队列跑
- 任务很长(1080p + 12s + 2.0),开 `--async` 然后睡一觉
- CI 编排,不想 Python 进程挂半小时

恢复模式:

```bash
seedance-cli task list --status running --status queued    # 看哪些没收
seedance-cli task get <id> --wait --out path.mp4           # 接回阻塞下载
seedance-cli task delete <id>                              # 取消排队 / 删历史
```

`POLL_CANCELLED`(Ctrl-C)或 `POLL_TIMEOUT`(`--timeout` 命中)时,envelope 里仍含 `task_id`,用 `task get --wait` 续杯,**不要从头重发**(会浪费 token)。

## 产物验证

**Claude 看不见 MP4**。能做的:

1. 确认 `video_path` 存在、`os.path.getsize` 非零
2. 报 envelope 里的 `duration` / `resolution` / `ratio` / `framespersecond` 给用户
3. 想"看"内容时,ffmpeg 抽帧 + Read:

```bash
ffmpeg -ss 00:00:00 -i clip.mp4 -frames:v 1 preview-first.jpg
ffmpeg -sseof -1 -i clip.mp4 -frames:v 1 preview-last.jpg
```

然后 `Read preview-first.jpg / preview-last.jpg` 让自己看到首尾帧,给用户描述。没 ffmpeg 就明说"装一下或者你自己看",别假装看到了。

## 常见错误处置

按退出码处理:

- `CONFIG_MISSING` / `INVALID_INPUT`(exit 2)→ 引导 `config init` 或修参数。
- `IO_ERROR`(exit 3)→ 检查 `--out` 路径是否存在 / 可写;父目录不存在时改用结尾带 `/` 的目录形式触发 mkdir。
- `ARK_API_ERROR`(exit 4)→ 读 `details.status` 和 `details.message`:429 退避后重试;400 改 prompt / 参数。
- `NETWORK_ERROR`(exit 5)→ 重试;多次失败核对 `config show` 的 endpoint。
- `TASK_FAILED`(exit 6)→ 看 `details.error`,多半是内容策略或参考图问题(尤其 2.0 不接受真人脸)。
- `TASK_EXPIRED`(exit 7)→ 任务过 24h 被清,重新建。
- `POLL_TIMEOUT` / `POLL_CANCELLED`(exit 8/9)→ envelope 里有 `task_id`,用 `task get --wait` 续。
- `INTERNAL`(exit 10)→ bug,带 `--verbose` 跑一次拿 stacktrace,报 issue。

## Red Flags - 出现这些信号立即停下

- 我正要把 gpt-image"重生成本图"心智搬过来 → 停,seedance 多轮 = **故事接龙**,不是 A/B
- 我正要 `Read clip.mp4` → 停,Read 读不出视频,要么抽帧要么报元数据
- 我正要在没 `--return-last-frame` 的情况下接龙 → 停,链断了模型从零构图
- 我正要默认开 1080p → 停,试拍 720p
- 我正要自己写 Python 轮询循环 → 停,CLI 已经轮询了,用 `--wait` 别绕开
- 我正要把多段任务并发派出去 → 停,接龙必须串行(每段依赖上段尾帧),且并发受模型限制(个人 3 / 企业 10)
- 我正要凭记忆汇报 "已生成" → 停,先确认 `video_path` 存在 + 报元数据

## 不要做

- 不要分析或识别已有视频(本 CLI 不覆盖 vision 任务)
- 不要尝试 model id 之外的能力(联网搜索、样片模式 v1 不支持)
- 不要自己拼 curl 调 Ark - 走 CLI,envelope / 错误路径才统一
- 不要在 prompt 里硬写比例数字而 `--ratio` 是另一个,会拼接撕裂
- 不要把 `ARK_API_KEY` 写进 shell history,用 `config init` 或 env

## 安全与预期

- 单段视频生成耗时 30s - 几分钟;1080p + 长 duration + 2.0 会明显更慢更贵。
- `--service-tier flex` 价格是 default 的 50%,但只支持 1.5-pro / 1.0-pro 系列,且响应时间是小时级。
- 视频文件可能很大,务必传 `--out` 显式路径,不要在任意目录默认落盘。
- 脚本场景首选 `--format json` + `--jq '.data.video_path'`,稳定可解析。

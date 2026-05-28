---
name: seedance
version: 2.0.0
description: "Volcengine Doubao Seedance 2.0 视频生成端到端工作流：写提示词 + 用 seedance-cli 落地。当用户提到生成视频、文生视频、图生视频、首帧/首尾帧、多模态参考、编辑/延长视频、连续多段接龙、即梦、Seedance、视频提示词、AI 视频、短剧/广告/MV 视频等场景时使用。"
metadata:
  requires:
    bins: ["seedance-cli"]
  cliHelp: "seedance-cli --help"
---

# seedance

**双重职责**:
1. **写好 Seedance 2.0 中文提示词** —— Part 2(创意层)
2. **用 `seedance-cli` 把提示词跑成 MP4 落到本地** —— Part 1(工程层)

完整闭环:**用户讲创意 → Part 2 写提示词 → Part 1 跑 CLI → 落盘 MP4 → 可选接龙下一段**。

**核心原则**:
- 写提示词时按 Part 2 的十大能力 + 时间戳分镜法,**全中文输出**。
- 跑生成时一律走 `seedance-cli`,不手拼 curl,不绕开默认轮询+下载。
- **Claude 看不见 MP4**——要么验文件 + 元数据,要么 ffmpeg 抽帧后 Read 静图。
- **Seedance 2.0 不接受写实真人脸部素材**——会被平台拦截,直接报 `ARK_API_ERROR` 含 `InputImageSensitiveContentDetected.PrivacyInformation`。

---

# Part 1 — 怎么调用 CLI(工程层)

## 1.1 前置

1. 确认 `seedance-cli` 可执行(`which seedance-cli` 或 `seedance-cli --version`)。不可执行则提示用户 `uv tool install zjandrew-seedance-cli` 或 `pipx install zjandrew-seedance-cli`(PyPI 包名;命令名 `seedance-cli` 不变)。
2. 配置 API key:优先 env `ARK_API_KEY`;缺失时引导 `seedance-cli config init`。
3. 默认 endpoint 是 `https://ark.cn-beijing.volces.com/api/v3`,自建/代理 endpoint 走 `seedance-cli config set endpoint https://<...>/api/v3` 或 `--endpoint` 单次覆盖。

## 1.2 多 profile 配置

```bash
seedance-cli config list                # 列所有 profile,active 标 *
seedance-cli config use <name>          # 切 active
seedance-cli config add <name>          # 向导式新增
seedance-cli --profile <name> generate ...   # 单次覆盖,不改 active
seedance-cli config show [<name>]       # 查看(api_key 已脱敏)
```

优先级:`--profile flag > SEEDANCE_PROFILE env > 文件 active`。`--api-key` / `--endpoint` 是字段级覆盖,不会让 `--profile` 失效。

## 1.3 核心命令速查

```bash
# 文生视频
seedance-cli generate -p "<prompt>" --ratio 16:9 --duration 5 --out v.mp4

# 图生视频 - 首帧
seedance-cli generate -p "<prompt>" --image start.png --duration 5 --out v.mp4

# 图生视频 - 首尾帧
seedance-cli generate -p "<prompt>" \
  --image first.png:first_frame --image last.png:last_frame \
  --duration 5 --out v.mp4

# 多模态参考(2.0)
seedance-cli generate -p "<prompt>" --image a.png --image b.png --image c.png \
  --duration 5 --out v.mp4

# 视频编辑 / 延长(2.0)
seedance-cli generate -p "把房子刷成蓝色" --video orig.mp4 --duration 5 --out edited.mp4

# 多模态组合(2.0):图 + 视频 + 音频
seedance-cli generate -p "<prompt>" --image a.png --video b.mp4 --audio bgm.mp3 --out v.mp4

# 任务管理
seedance-cli task list --status running
seedance-cli task get <task_id> --wait --out path.mp4
seedance-cli task delete <task_id>
```

## 1.4 模型选型(`-m` flag)

| 想要 | `-m` 值 | 关键差异 |
|---|---|---|
| 默认 / 最强 | `2.0`(默认) | 全能力,含多模态参考 / 编辑 / 延长 / 有声 |
| 又快又省 | `2.0-fast` | 同 2.0 但无 1080p |
| 离线推理省钱 | `1.5-pro --service-tier flex` | 2.0 不支持 flex;价格 50% |
| 指定帧数 | `1.0-pro --frames 29` | 唯一支持 `--frames`(满足 25+4n,29-289) |

**Seedance 2.0 系列不支持的:**
- `--service-tier flex` 离线推理
- `--camera-fixed` 固定摄像头
- 写实真人脸部参考图/视频

## 1.5 参数选型(CLI flag)

| 意图 | 推荐参数 |
|---|---|
| 试拍 / 预览 | `--ratio 16:9 --resolution 720p --duration 5` |
| 横版定稿 | `--ratio 16:9 --resolution 1080p`(2.0-fast 除外) |
| 竖版短视频 | `--ratio 9:16` |
| 跟随首帧自适应宽高比 | `--ratio adaptive` |
| 离线推理 | `-m 1.5-pro --service-tier flex --execution-expires-after 172800` |
| 有声视频 | `--generate-audio`(仅 2.0 / 2.0-fast / 1.5-pro) |
| 拿到尾帧做接龙 | `--return-last-frame --out-last-frame last.png` |

## 1.6 本地输入 vs URL

- 本地路径(`./a.png`、`/path/v.mp4`)自动 base64 编码,**注意限额**:单图 ≤ 30 MB、单视频 ≤ 50 MB、单音频 ≤ 15 MB,请求体总 ≤ 64 MB。
- 超限会报 `INVALID_INPUT`,提示先上传到 TOS / OSS 拿到公开 URL,再传 `--image https://...`。
- URL 输入零成本(服务端拉),优先用 URL。
- **已验证**:`data:<mime>;base64,...` data URI 形态服务端接受。

## 1.7 异步与任务管理

什么时候用 `--async`:
- 一次性派多个任务,让队列跑
- 任务很长(1080p + 12s + 2.0),开 `--async` 然后睡一觉
- CI 编排,不想 Python 进程挂半小时

恢复模式:

```bash
seedance-cli task list --status running    # 看哪些没收
seedance-cli task get <id> --wait --out path.mp4    # 接回阻塞下载
seedance-cli task delete <id>              # 取消排队 / 删历史
```

`POLL_CANCELLED`(Ctrl-C)或 `POLL_TIMEOUT`(`--timeout` 命中)时,envelope 里仍含 `task_id`,用 `task get --wait` 续杯,**不要从头重发**(会浪费 token)。

## 1.8 产物验证

**Claude 看不见 MP4**。能做的:

1. 确认 `video_path` 存在、`os.path.getsize` 非零
2. 报 envelope 里的 `duration` / `resolution` / `ratio` / `framespersecond` 给用户
3. 想"看"内容时,ffmpeg 抽帧 + Read:

```bash
ffmpeg -ss 00:00:00 -i clip.mp4 -frames:v 1 preview-first.jpg
ffmpeg -sseof -1 -i clip.mp4 -frames:v 1 preview-last.jpg
```

然后 `Read preview-first.jpg / preview-last.jpg` 让自己看到首尾帧,给用户描述。没 ffmpeg 就明说"装一下或者你自己看",别假装看到了。

## 1.9 常见错误处置

按退出码处理:

- `CONFIG_MISSING` / `INVALID_INPUT`(exit 2)→ 引导 `config init` 或修参数。
- `IO_ERROR`(exit 3)→ 检查 `--out` 路径是否存在 / 可写;父目录不存在时改用结尾带 `/` 的目录形式触发 mkdir。
- `ARK_API_ERROR`(exit 4)→ 读 `details.status` 和 `details.message`:
  - 429 退避后重试
  - 400 改 prompt / 参数
  - `InputImageSensitiveContentDetected.PrivacyInformation` → 输入图含真人脸,2.0 系列不接受;换非真人脸素材
- `NETWORK_ERROR`(exit 5)→ 重试;多次失败核对 `config show` 的 endpoint。
- `TASK_FAILED`(exit 6)→ 看 `details.error`,多半是内容策略或参考图问题。
- `TASK_EXPIRED`(exit 7)→ 任务过 24h 被清,重新建。
- `POLL_TIMEOUT` / `POLL_CANCELLED`(exit 8/9)→ envelope 里有 `task_id`,用 `task get --wait` 续。
- `INTERNAL`(exit 10)→ bug,带 `--verbose` 跑一次拿 stacktrace,报 issue。

## 1.10 Red Flags — 出现这些信号立即停下

- 我正要把 gpt-image"重生成本图"心智搬过来 → 停,seedance 多轮 = **故事接龙**,不是 A/B
- 我正要 `Read clip.mp4` → 停,Read 读不出视频,要么抽帧要么报元数据
- 我正要在没 `--return-last-frame` 的情况下接龙 → 停,链断了模型从零构图
- 我正要默认开 1080p → 停,试拍 720p
- 我正要自己写 Python 轮询循环 → 停,CLI 已经轮询了,用 `--wait` 别绕开
- 我正要把多段任务并发派出去 → 停,接龙必须串行(每段依赖上段尾帧),且并发受模型限制(个人 3 / 企业 10)
- 我正要凭记忆汇报"已生成"→ 停,先确认 `video_path` 存在 + 报元数据
- 我正要上传写实真人脸素材 → 停,2.0 拒收

## 1.11 不要做

- 不要分析或识别已有视频(本 CLI 不覆盖 vision 任务)
- 不要自己拼 curl 调 Ark - 走 CLI,envelope / 错误路径才统一
- 不要在 prompt 里硬写比例数字而 `--ratio` 是另一个,会拼接撕裂
- 不要把 `ARK_API_KEY` 写进 shell history,用 `config init` 或 env

## 1.12 安全与预期

- 单段视频生成耗时 30s - 几分钟;1080p + 长 duration + 2.0 会明显更慢更贵。
- `--service-tier flex` 价格是 default 的 50%,但只支持 1.5-pro / 1.0-pro 系列,且响应时间是小时级。
- 视频文件可能很大,务必传 `--out` 显式路径,不要在任意目录默认落盘。
- 脚本场景首选 `--format json` + `--jq '.data.video_path'`,稳定可解析。

---

# Part 2 — 怎么写提示词(创意层)

你是 Seedance 2.0 的提示词工程师。所有提示词**用中文写**,具体到画面、动作、镜头、声音。

## 2.1 Seedance 2.0 平台规格

| 维度 | 规格 |
|---|---|
| 图片输入 | jpeg/png/webp/bmp/tiff/gif/heic/heif,≤9 张,单张 < 30 MB |
| 视频输入 | mp4/mov,≤3 个,总时长 2-15 秒,单个 < 50 MB,分辨率 480p-720p |
| 音频输入 | mp3/wav,≤3 个,总时长 ≤15 秒,单个 < 15 MB |
| 混合上限 | 最多 12 个文件(图+视频+音频合计) |
| 生成时长 | 4-15 秒,可自由选择 |
| 声音输出 | 自带音效/配乐(`--generate-audio`) |
| 分辨率 | 480p / 720p / 1080p |
| 宽高比 | 21:9 / 16:9 / 4:3 / 1:1 / 3:4 / 9:16 / adaptive |

## 2.2 多模态能力总览

- **多模态参考**:图、视频、音频、文本四种模态输入
- **@引用系统**:在提示词中用 `@图片1`、`@视频1`、`@音频1` 引用上传的参考素材
- **首尾帧控制**:`--image x.png:first_frame --image y.png:last_frame`
- **自动分镜与运镜**:模型可根据故事描述自动规划
- **视频延长**:对已有视频平滑延长(下一段提示词以 `将@视频1延长Xs` 开头)
- **视频编辑**:角色更替、删减、增加(`--video orig.mp4` + 编辑指令)
- **一镜到底**:连续镜头连贯性生成(在提示词里明确"全程不要切镜头,一镜到底")

## 2.3 @引用系统

### 官方命名规范

- 图片:`@图片1`、`@图片2`、...、`@图片9`
- 视频:`@视频1`、`@视频2`、`@视频3`
- 音频:`@音频1`、`@音频2`、`@音频3`

### 在提示词中明确每个素材的用途

```
@图片1为首帧
参考@视频1的运镜效果
背景音乐参考@音频1
@图片1的人物形象
参考@视频1的打斗动作
```

### CLI 上的对应

CLI 这边 `--image` 出现顺序决定 `@图片1`、`@图片2`、...,`--video` 决定 `@视频1`、...:

```bash
seedance-cli generate -m 2.0 \
  -p "以@图片1为首帧,参考@视频1的运镜,@图片2作为最终落点" \
  --image start.png \
  --image end.png \
  --video reference.mp4 \
  --out v.mp4
```

## 2.4 ⚠️ 平台限制

- **不支持上传写实真人脸部素材**(图片和视频均不可),系统会拦截并返回 `InputImageSensitiveContentDetected.PrivacyInformation`
- 有参考视频时生成更慢、更贵
- 视频延长时,选择的生成时长是"新增部分"的时长(例如延长 5 秒,`--duration 5`)

## 2.5 十大能力与提示词模式

### 2.5.1 纯文本生成(无参考素材)

**提示词模式**:`(主体) + (动作序列) + (环境/光影) + (镜头语言) + (风格)`

```
镜头跟随黑衣男子快速逃亡,后面一群人在追,镜头转为侧面跟拍,人物惊慌撞倒路边的水果摊爬起来继续逃,人群慌乱的声音。
```

### 2.5.2 一致性控制(角色/产品/场景统一)

**模式**:`[角色]@图片N + [动作/剧情] + [场景]@图片N + [运镜/光影]`

```
男人@图片1下班后疲惫的走在走廊,脚步变缓,最后停在家门口,脸部特写镜头,男人深呼吸,调整情绪,收起了负面情绪,变得轻松,然后特写翻找出钥匙,插入门锁,进入家里后,他的小女儿和一只宠物狗,欢快的跑过来迎接拥抱,室内非常的温馨,全程自然对话
```

```
对@图片2的包包进行商业化的摄像展示,包包的侧面参考@图片1,包包的表面材质参考@图片3,要求将包包的细节均有所展示,背景音恢宏大气
```

### 2.5.3 运镜与动作精准复刻

**模式**:`参考@视频1的[运镜/动作/节奏] + [主体]@图片N + [场景]`

```
参考@图片1的男人形象,他在@图片2的电梯中,完全参考@视频1的所有运镜效果还有主角的面部表情,主角在惊恐时希区柯克变焦,然后几个环绕镜头展示电梯内视角,电梯门打开,跟随镜头走出电梯,电梯外场景参考@图片3,男人环顾四周
```

### 2.5.4 创意模板/特效复刻

**模式**:`参考@视频1的[特效/转场/创意] + 将[元素]替换为@图片N + [补充说明]`

```
将@视频1的人物换成@图片1,@图片1为首帧,人物带上虚拟科幻眼镜,参考@视频1的运镜,及近的环绕镜头,从第三人称视角变成人物的主观视角,在 AI 虚拟眼镜中穿梭,来到@图片2的深邃的蓝色宇宙
```

### 2.5.5 剧情创作/补全

**模式**:`[分镜脚本/图片内容] + [演绎方式] + [音效/台词要求]`

```
将@图片1以从左到右从上到下的顺序进行漫画演绎,保持人物说的台词与图片上的一致,分镜切换以及重点的情节演绎加入特殊音效,整体风格诙谐幽默;演绎方式参考@视频1
```

### 2.5.6 视频延长

**模式**:`将@视频1延长[X]s + [新增内容描述]` 或 `向前延长[X]s + [前置剧情]`

CLI 这边:**用上段生成的 MP4 作为 `--video`**:

```bash
seedance-cli generate -m 2.0 \
  -p "将@视频1延长15秒。1-5秒:光影透过百叶窗在木桌、杯身上缓缓滑过...11-15秒:英文渐显第一行 Lucky Coffee" \
  --video clip-1.mp4 \
  --duration 15 \
  --out clip-1-extended.mp4
```

### 2.5.7 声音控制(音色/对白/音效)

**模式**:`[画面] + 音色/旁白参考@视频1 + [台词用引号标注]`

```
固定镜头,中央鱼眼镜头透过圆形孔洞向下窥视,参考@视频1的鱼眼镜头,让@视频2中的马看向鱼眼镜头,参考@视频1中的说话动作,背景BGM参考@视频3中的音效。
```

CLI 这边记得加 `--generate-audio`。

### 2.5.8 一镜到底

**模式**:`一镜到底 + @图片1@图片2...@图片N + [连续场景] + 全程不要切镜头`

```
谍战片风格,@图片1作为首帧画面,镜头正面跟拍穿着红风衣的女特工向前走,镜头全景跟随,不断有路人遮挡红衣女子,走到一个拐角处,参考@图片2的拐角建筑,固定镜头红衣女子离开画面,...全程不要切镜头,一镜到底。
```

### 2.5.9 视频编辑

**模式**:`将@视频1中的[A]换成@图片1 + [其他修改]` 或 `颠覆@视频1的剧情 + [新剧情]`

```
@视频1中的女主唱换成@图片1的男主唱,动作完全模仿原视频,不要出现切镜,乐队演唱音乐。
```

```
颠覆@视频1里的剧情,男人眼神从温柔瞬间转为冰冷狠厉,在女主毫无防备的瞬间,猛地将女主从桥上往外推
```

### 2.5.10 音乐卡点

**模式**:`@图片1@图片2...@图片N + 参考@视频1的画面节奏/卡点 + [画面风格]`

```
@图片1@图片2@图片3@图片4@图片5@图片6@图片7中的图片根据@视频1中的画面关键帧的位置和整体节奏进行卡点,画面中的人物更有动感,整体画面风格更梦幻,画面张力强,可根据音乐及画面需求自行改变参考图的景别,及补充画面的光影变化
```

## 2.6 高级提示词技巧

### 时间戳分镜法(13-15 秒长视频的核心技巧)

```
0-3秒:[画面 + 镜头]
4-8秒:[画面 + 镜头]
9-12秒:[画面 + 镜头]
13-15秒:[画面 + 镜头]
```

**仙侠战斗示例**:

```
15秒仙侠高燃战斗镜头,金红暖色调,0-3秒:低角度特写主角蓝袍衣摆被热浪吹得猎猎飘动,双手紧握雷纹巨剑,剑刃赤红电光持续爆闪;4-8秒:环绕摇镜快切,主角旋身挥剑,剑刃撕裂空气迸射红色冲击波,前排魔兵被击飞碎裂成灰烬;9-12秒:仰拍拉远定格慢放,主角跃起腾空,剑刃凝聚巨型雷光电弧劈向魔兵群;13-15秒:缓推特写主角落地收剑的姿态,衣摆余波微动,冷声道"此界之门,不容踏越"。
```

**短剧对白示例**(画面 + 台词 + 音效分开标注):

```
画面(0-5秒):特写女主撕契约镜头,纸屑飘落,总裁单膝跪地伸手阻拦,眼神慌乱
台词1(总裁,卑微慌乱):"苏晚!契约还没结束,你不能走!我给你钱,给你地位!"
画面(6-10秒):女主抬脚避开他的手,将撕碎的契约纸扔在他脸上,镜头扫过周围宾客的窃窃私语
台词2(女主,冷漠反杀):"契约?顾总,当初是你说,我连给你提鞋都不配,现在求我?晚了!"
画面(11-15秒):总裁僵在原地,脸上沾着纸屑,女主转身昂首离开,红裙裙摆飘动
音效:华丽又带张力的背景音,契约撕碎的声响,宾客轻微的窃窃私语声
时长:精准15秒
```

### 技术参数指定法

提示词开头明确画面技术规格:

```
[尺寸]竖屏/横屏 + [画幅比]2.35:1/16:9/9:16 + [帧率]24fps + [时长]Xs + [色调/风格总纲]
```

### 禁止项声明(放提示词结尾)

```
禁止:
- 任何文字、字幕、LOGO或水印
- 不允许出现XXX
- 画面全部片段都不要出现字幕
```

## 2.7 镜头语言词汇库

| 类别 | 关键词 |
|---|---|
| 景别 | 大远景、远景、全景、中景、近景、特写、大特写 |
| 运镜 | 推镜头、拉镜头、摇镜头、移镜头、跟拍、环绕拍摄、航拍、手持跟拍、希区柯克变焦 |
| 角度 | 平视、俯拍、仰拍、低角度、鸟瞰视角、鱼眼镜头、第一人称视角、主观视角 |
| 节奏 | 慢动作、快切、延时摄影、一镜到底、升格拍摄、硬切、卡点 |
| 焦点 | 浅景深、深景深、焦点转移、虚化背景、选择性对焦 |
| 特殊 | 遮挡擦镜转场、无缝渐变转场、环绕摇镜快切特写、定格慢放 |

## 2.8 风格词汇库

| 类别 | 关键词 |
|---|---|
| 画面质感 | 电影感、胶片质感、高清晰度、8K分辨率、HDR、RAW质感、4K医学CGI |
| 影像风格 | 好莱坞大片、独立电影、纪录片、MV风格、广告大片、Vlog风格、2.35:1宽银幕 |
| 色调氛围 | 暖色调、冷色调、高对比度、低饱和度、莫兰迪色系、赛博朋克霓虹、红金高饱和 |
| 艺术风格 | 写实主义、超现实主义、极简主义、蒸汽波、赛博朋克、中国风水墨、3D国漫CG |
| 光影效果 | 自然光、侧逆光、丁达尔效应、霓虹灯光、月光、黄金时段光线、体积光 |
| 动画风格 | 中国奇幻动画电影风格、超精细CG动画、日漫赛璐璐、3D渲染写实 |

## 2.9 场景类型策略

### 电商/广告
- 产品 360 度旋转、爆炸分解、3D 渲染
- 第一人称沉浸式手作体验
- 配品牌口播 + logo(注意 1.10 提到的 `--watermark` 默认 false,需要 logo 走 prompt 描述)

### AI 漫剧/仙侠
- 用首尾帧控制变身/变装
- 时间戳分镜法精确控制
- 详细特效描述(法阵、能量波、粒子)
- 台词引号标注 + 语气

### 短剧/对白
- 画面+台词分开
- 台词标注角色 + 情绪
- 音效单独描述
- 旁白说"预知后事如何,请看下集"

### 科普教学
- 4K 医学 CGI 风格
- 半透明人体结构可视化
- 配教育性旁白

### MV/音乐卡点
- 指定画幅比(2.35:1)+ 帧率(24fps)
- 分镜头描述
- 强调声音设计与节拍同步

## 2.10 时长策略

### 单段(4-15 秒)

Seedance 2.0 单次生成上限 15 秒。

- **4-8 秒**:产品展示、单个动作、简短特效。聚焦 1-2 个核心画面,无需时间戳。
- **9-12 秒**:完整短场景。可选时间戳分 2-3 段。
- **13-15 秒**:完整叙事。**强烈推荐**时间戳分镜法,分 3-4 段。

### 超长(>15 秒):分段生成 + 视频延长

**核心原理**:第一段正常生成(≤15 秒);后续每段用「视频延长」,把上段 MP4 作为 `@视频1` 输入,延续生成。

**分段规则**:
1. 总时长按叙事节奏切分,每段 ≤15 秒
2. 每段之间必须有**画面衔接点**:上段结尾状态 = 下段开头状态
3. 第一段正常生成,后续每段提示词以 `将@视频1延长Xs` 开头
4. 每段标注属于整体的第几段、承接什么

**总时长建议**:

| 总时长 | 推荐分段 |
|---|---|
| 16-30 秒 | 2 段 |
| 31-45 秒 | 3 段 |
| 46-60 秒 | 4 段 |
| >60 秒 | 拆成独立场景分别生成,再用剪辑软件拼接 |

> 注意区分两种"接续"机制:
> - **视频延长**(本节):把整段 MP4 当 `@视频1`,自然延续 → 用 `--video` flag
> - **接龙(尾帧→首帧)**(Part 3.2):取上段尾帧当下段首帧 → 用 `--return-last-frame` + 下段 `--image last.png:first_frame`
>
> 视频延长**保留更多语境**(整段画面 + 运镜节奏),适合无缝续拍;尾帧接龙**更省 token、画面更可控**,适合分镜切换式叙事(像分场景的短剧)。

---

# Part 3 — 端到端 workflow

## 3.1 单段视频(≤15 秒)

```
Step 1: 听用户讲创意意图
Step 2: 按 Part 2 写出一条 Seedance 2.0 中文提示词
Step 3: 决定要用的参考素材(URL / 本地路径)和 ratio/resolution/duration
Step 4: 用 seedance-cli generate 跑(默认阻塞 + 下载)
Step 5: 读 envelope 的 video_path,确认文件存在 + 报元数据给用户
```

最小例子:

```bash
seedance-cli generate -m 2.0 \
  -p "镜头跟随黑衣男子快速逃亡..." \
  --ratio 16:9 --resolution 720p --duration 5 \
  --out v.mp4
```

## 3.2 连续多段接龙(本 SKILL 主战场)

**触发词**:"做一段连续故事"、"接着上一段"、"接龙生成"、"多段视频"、"短剧"、"剧情视频"。

### 产物目录

```
story/<topic>/
├── clip-1.mp4
├── clip-2.mp4
├── clip-3.mp4
├── last-frame-1.png      ← 自动落盘的接续素材
├── last-frame-2.png
└── final.mp4             ← 拼成的成片
```

`<topic>` 取自用户对此次任务的简短命名;没给就根据语义自造一个 kebab-case 词,如 `fox-girl-story`。

### Step 1 — 写分镜(Part 2 的能力)

让用户给 N 段提示词。**只给一段总意图时,Claude 先拆成 3-5 段分镜并复述给用户确认**,不要直接开生。每段按 Part 2 §2.6 的时间戳分镜法写。

### Step 2 — 首段

```bash
seedance-cli generate -m 2.0 \
  -p "<clip-1 prompt,完整自包含>" \
  [--image start.png:first_frame] \
  --return-last-frame \
  --ratio 16:9 --resolution 720p --duration 5 \
  --out story/<topic>/clip-1.mp4 \
  --out-last-frame story/<topic>/last-frame-1.png
```

读 stdout envelope 拿 `last_frame_path`。

**`--ratio` `--resolution` `--duration` 跨段保持不变**,改了会拼接撕裂。

### Step 3 — 续段(循环 i = 2…N)

```bash
seedance-cli generate -m 2.0 \
  -p "<clip-i prompt,必须完整重述视觉要素>" \
  --image story/<topic>/last-frame-{i-1}.png:first_frame \
  --return-last-frame \
  --ratio 16:9 --resolution 720p --duration 5 \
  --out story/<topic>/clip-{i}.mp4 \
  --out-last-frame story/<topic>/last-frame-{i}.png
```

### Step 4 — 跨段一致性提示词模板

照下面 4 段模板**填充**,然后展开成自然语言(去掉 `[...]` 标签):

```
[本段动作]:<这一段主体在做什么>
[延续上段]:<上一段最后的状态 - 主体姿态/场景/光线,必须复述,模型不读上下文>
[配色与风格]:<跨段稳定的视觉调性>
[镜头与节奏]:<本段镜头运动>
```

**不要**写 "like before but..." / "保持上一段不变,只改 X"——模型没有上下文,它不懂"上一段"。每段 prompt 必须**完整自包含**。

### Step 5 — 拼接

所有段都成功后,给用户一行 ffmpeg:

```bash
ffmpeg -f concat -safe 0 \
  -i <(for f in story/<topic>/clip-*.mp4; do echo "file '$PWD/$f'"; done) \
  -c copy story/<topic>/final.mp4
```

不满意时**只重生有问题的那段 + 后续所有段**(链断了)。

### 必须做 / 必须不做(接龙)

- ✅ 每段 prompt 完整自包含 - 模型不读对话上下文
- ✅ `--ratio` `--resolution` `--duration` 跨段保持
- ✅ 每段成功后告诉用户「clip-i 已落盘,下一段将以本段尾帧续接」
- ❌ 中间段省 `--return-last-frame` / `--out-last-frame`,链就断了
- ❌ 没拿到尾帧的情况下凭脑补写下一段 prompt
- ❌ 跨段换模型 / 换 seed / 换 ratio
- ❌ 试拍直接 1080p 全开 - 4 段 1080p 慢且贵;先 720p,定稿再 1080p 重出

## 3.3 视频延长 workflow(语境保留型续拍)

和 §3.2 接龙不同——这里**把整段 MP4 作为参考输入**,让模型基于完整视频画面延续:

```bash
# Step 1: 生成第一段(或用户已有视频)
seedance-cli generate -m 2.0 \
  -p "<base prompt>" \
  --ratio 16:9 --duration 10 --out story/<topic>/clip-1.mp4

# Step 2: 用 --video 把整段 MP4 喂回去
seedance-cli generate -m 2.0 \
  -p "将@视频1延长5秒。0-2秒:接上段结尾画面继续...3-5秒:..." \
  --video story/<topic>/clip-1.mp4 \
  --duration 5 \
  --out story/<topic>/clip-1-extended.mp4
```

**视频延长 vs 尾帧接龙怎么选**:

| 维度 | 视频延长(`--video`) | 尾帧接龙(`--return-last-frame`) |
|---|---|---|
| 输入信息 | 整段画面 + 节奏 | 仅最后一帧 |
| 一致性 | 高(运镜/光影自然续) | 中(模型从首帧重新构图) |
| Token 成本 | 高(视频输入计入参考成本) | 低 |
| 适合场景 | 一镜到底续拍、无缝转场 | 分镜切换、多场景叙事 |
| Prompt 写法 | `将@视频1延长Xs。...` | 完整自包含,复述上段尾态 |

## 3.4 视频编辑 workflow

```bash
seedance-cli generate -m 2.0 \
  -p "将@视频1中的房子外立面墙壁刷成蓝色,天气和光线参考@图片1的雪天" \
  --video original.mp4 \
  --image snowy-day.jpg \
  --duration 5 \
  --out edited.mp4
```

或角色替换:

```bash
seedance-cli generate -m 2.0 \
  -p "@视频1中的女主唱换成@图片1的男主唱,动作完全模仿原视频,不要出现切镜" \
  --video original.mp4 \
  --image new-singer.png \
  --duration 5 \
  --out replaced.mp4
```

---

# Part 4 — 交互指引

当识别到用户有视频生成需求时,按以下流程:

### Step 1 — 听创意

用户只需提供主题,例如:
- "一段仙侠战斗"
- "奶茶产品广告"
- "猫咪在月球上跳舞"
- "一个 30 秒的悬疑短剧"

### Step 2 — 确认关键参数

通过提问确认(用户已说清的可跳过):

1. **时长**(必问):
   - 短片(4-8 秒)
   - 中等(9-12 秒)
   - 长片(13-15 秒)
   - **超长**(>15 秒)→ 进入 §3.2 接龙或 §3.3 延长 workflow
2. **比例**:16:9 / 9:16 / adaptive
3. **参考素材情况**:纯文本 / 有图片 / 有视频 / 全模态
4. **补充偏好**:情绪氛围、镜头风格、用途场景

### Step 3 — 写提示词

- ≤15 秒:按 Part 2 写 **1-2 个不同风格版本**供选择(主战场不要超过 3 个)
- >15 秒:按 §3.2 或 §3.3 切段,每段独立提示词

### Step 4 — 跑 CLI

按 Part 1 的 `seedance-cli generate` 跑。**默认阻塞 + 下载**,不要手拼 curl,不要自己写轮询。

### Step 5 — 验证 + 汇报

- `video_path` 存在?
- envelope 里的 `duration` / `resolution` / `ratio` / `framespersecond` 报给用户
- 想"看"内容用 ffmpeg 抽帧 + Read(§1.8)

### Step 6 — 微调

用户选定后可要求:
- 调某个时间段的画面
- 换风格/色调/镜头语言
- 增减台词/音效描述
- 调时长或分段

---

# 注意事项汇总

- **所有提示词(视频提示词 + 图片生成提示词)必须中文编写**
- **@引用使用官方命名**:`@图片1`、`@视频1`、`@音频1`(不是 `@img1` 之类)
- 多素材时**检查每个 @ 对象有没有标清楚**,别把图、视频、角色搞混
- 写清楚是「参考」还是「编辑」——参考是借鉴风格/动作,编辑是在原素材上修改
- **图片风格必须与视频主题契合**:
  - 仙侠/修真 → 3D 国漫渲染、中国仙侠概念设计
  - 古风/历史 → 中国风工笔画、水墨画
  - 赛博朋克/科幻 → 未来科幻写实 CG
  - 现实/人物 → 电影摄影写实、人像摄影
  - 美食 → 美食广告摄影、商业摄影
  - 自然风光 → 风光摄影、航拍纪录片
  - 动漫 → 对应美术风格(日漫赛璐璐、国漫 3D 渲染等)
- 描述具体且有画面感,避免抽象模糊
- 镜头语言和动作描述要有**时间顺序**,让模型理解先后关系
- 13-15 秒长视频**强烈推荐时间戳分镜法**
- 台词/对白用引号包裹 + 角色 + 情绪
- 音效描述单独成行,与画面分开
- 控制提示词长度,重点突出,避免信息过载
- 情绪和氛围对最终效果影响很大,**不要忽略**
- **不要上传写实真人脸素材**,会被平台拦截
- 不要绕开 `seedance-cli`,所有调用走 CLI(envelope/错误路径才统一)
- 不要假装看到了 MP4——Claude 看不见视频,要么 ffmpeg 抽帧要么报元数据

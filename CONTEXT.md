# seedance-cli

火山引擎方舟 Seedance 视频生成的命令行封装：把一次视频生成请求的组装、提交、轮询、下载做成可脚本化的工具。

## Language

**Model ID**:
方舟侧的完整模型标识（如 `doubao-seedance-2-5-260628`），请求体中 `model` 字段的唯一合法形态。
_Avoid_: 模型名、model name

**Model alias**:
用户输入的短别名（`2.5`、`2.0`、`2.0-mini`、`1.5-pro`…），仅是 Model ID 的便利映射，不是校验白名单——未知但形如 `doubao-seedance-*` 的 ID 一律信任放行。
_Avoid_: shortcut、简称

**Scenario**:
CLI 侧从输入素材组合**推断**出的生成场景：text_to_video / image_to_video_first / first_last_frame / multimodal_reference / video_edit_extend。只描述"用户给了什么"。
_Avoid_: mode、任务模式

**Task type**:
Seedance 2.5 服务端的任务分类（auto / reference / edit / extend），由用户**声明**（`omni_reference_task_type`），决定服务端如何使用参考素材。与 Scenario 的区别：Scenario 是 CLI 推断的输入形态，Task type 是 2.5 声明的处理意图；显式声明 edit/extend 可把校验从异步提前到同步。
_Avoid_: 场景（保留给 Scenario）

**Capability**:
某个 Model ID 支持的能力面：分辨率档位、时长范围、素材数量上限、可用参数。本地校验以 Capability 为单位按模型查表，而非按"系列"猜测。
_Avoid_: feature set、支持列表

**Deferred rejection（异步报错）**:
任务创建成功、但在排队消费阶段才因参数不合法而 failed 的失败方式（2.5 auto 模式的典型行为），错误信息只能通过轮询结果的 `error` 字段获得。本地校验策略的主要假想敌。
_Avoid_: 延迟失败、服务端二次校验

**Reference material（参考素材）**:
随请求附带的图片 / 视频 / 音频输入的统称，各类数量与总时长受所选模型的 Capability 约束。
_Avoid_: 附件、输入文件

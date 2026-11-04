---
name: kaggle-comfyui-skill
description: 在 Kaggle 官方免费额度内部署并运行 ComfyUI API 工作流，生成图像或视频；用于 Kaggle 配额查询、工作流迁移、私有任务准备与单次提交、进度巡检、产物下载验收以及首尾帧分段接力。不轮换账号，不规避平台额度，不默认消耗 GPU。
---

# Kaggle ComfyUI Skill

把用户的 ComfyUI API 工作流变成可追踪的 Kaggle 私有批处理任务。先查额度、验证输入，再提交一次；技术成功不等于画面验收通过。

给仓库使用者的中文首页与快速开始见 [README.md](README.md)；Agent 执行任务仍以本文件的操作规则为准。

## 开始前

1. 使用终端工具或系统命令行执行本目录下的脚本。Python 3.11+；本地校验仅用标准库。联机操作需要官方 `kaggle==2.2.4` CLI/SDK，已有新版本须先核验兼容性，不静默升级。
2. 将源代码仓库保留为干净 Skill；运行文件放在独立、可写的开发目录。不要把任务、模型、个人图片、视频或凭证提交到 Git。
3. 读取 [references/operations.md](references/operations.md)，核实账号、Kaggle 资格、输入挂载和授权。涉及反复下载或权重缓存时，读取 [references/model-cache.md](references/model-cache.md)：用户授权后一次性保存为本人私有数据集，CPU核验实际挂载路径/hash，再优先复用；未就绪时不得称已缓存。所有 Kaggle CLI/SDK 联机操作均需通过 API Key 鉴权，支持通过环境变量 `KAGGLE_API_TOKEN` 或凭证文件 `~/.kaggle/kaggle.json` 配置。凭证只由用户通过官方登录或安全环境配置；不读取、复述或上传凭证文件。
4. 查询真实额度：`python scripts/kaggle_comfy.py quota`。30 小时 GPU /20 小时 TPU 不是保证值，以官方当前返回为准。此 CUDA 工作流不能把 TPU 时长直接当 GPU 使用。
5. 确认工作流、模型许可、分辨率、帧率、预计耗时、交付形式及是否允许消耗额度。不以“免费”为由自动启动；不轮换账号、绕过配额或修改平台限制。

## 操作流程

1. 准备 ComfyUI 的 **API JSON**，不是 UI 的 `nodes/links` JSON。读取 [references/workflows.md](references/workflows.md)。
2. 从配套运行配置选择：基础 SD [assets/image.spec.json](assets/image.spec.json)、Wan [assets/video.spec.json](assets/video.spec.json)、Anima Turbo [assets/anima-turbo.spec.json](assets/anima-turbo.spec.json) 或 H3 [assets/h3-character-swap.spec.json](assets/h3-character-swap.spec.json)。填写本人账号、私有数据集、实际挂载路径和素材 SHA256；公开模型 hash 已写入专用 spec，零哈希仍需替换。模型公开元数据来源见 [assets/model-sources.json](assets/model-sources.json)，不代表已下载或允许任意使用。
3. 工作流包括 SD [assets/image.workflow.json](assets/image.workflow.json)、Wan [assets/video.workflow.json](assets/video.workflow.json)、Anima Turbo v1.1 [assets/anima-turbo.workflow.json](assets/anima-turbo.workflow.json)、H3 角色替换+首帧控制 [assets/h3-character-swap.workflow.json](assets/h3-character-swap.workflow.json)。Anima 使用前读 [references/anima-turbo.md](references/anima-turbo.md)；默认采用嘉依卡作者示例的 CFG1/8步。作者未改 API 见 [assets/anima-chaika-original.api.json](assets/anima-chaika-original.api.json)，可导入 UI 见 [assets/anima-chaika-original.ui.json](assets/anima-chaika-original.ui.json)，来源与 hash 见 [assets/anima-chaika-source.json](assets/anima-chaika-source.json)。批处理图只将 PreviewImage 改为 SaveImage，不得声称它完全未改。核对非商业许可；H3 必须读 [references/h3-workflow.md](references/h3-workflow.md)，显式启用固定双T4兼容配置，不是任意图自动适配。Anima作者原版已在专项inline-download runner完成GPU核验；不等于通用runner或H3 profile已GPU复测。节点仍需对照目标 `/object_info`。
4. 离线检查：`python scripts/kaggle_comfy.py validate --spec RUN.json --workflow WORKFLOW.json`。这只检查格式、引用、循环、路径、来源和固定版本；不是实际模型运行成功证明。
5. 离线准备：`python scripts/kaggle_comfy.py prepare --spec RUN.json --workflow WORKFLOW.json --jobs-dir /absolute/writable/jobs`。记录返回的任务目录与 UUID；`prepare` 不调用 Kaggle、不用 GPU。
6. 在用户明确授权后，用已配置 Kaggle SDK 的同一个 Python 解释器运行：`python scripts/kaggle_comfy.py submit --job JOB_DIR --confirm-remote-execution`。提交前再次查询额度，要求“最大会话时长 +5分钟余量”不超过剩余额度。任务始终私有，自动带唯一 slug；只提交一次。超时/未知返回先按该 slug 核对远端，禁止删除本地提交标记后盲目重投。
7. 先 `status --job JOB_DIR` 核对远端，随后 `logs --job JOB_DIR --seconds 20` 有界读取日志。运行中必须区分安装、等待服务、排队、生成和解码。只报告真实 `KAGGLE_COMFY` 事件；“GENERATING”与心跳不等于某个采样步数或完成百分比。
8. 用户要求挂机时，可使用环境提供的定时/异步任务机制（如系统的 cron、定时唤醒工具等）创建任务级定时检查，普通长任务默认每小时；预计数分钟的单图任务按用户要求每2分钟检查。提交后当回合立刻查状态、捕获有界日志并登记巡检，不得等用户催问；把任务 UUID、路径、精确命令、失败处理、发送实际图片的交付要求和清除条件写入任务说明，记录任务标识并实际核验。**本仓库不会自己创建宿主定时任务**。完成或不可恢复失败后清除对应任务，不动无关计划。
9. 远端终态后 `download --job JOB_DIR`；继续或复查已下载文件用 `verify --job JOB_DIR`。核对 result 任务身份、工作流 hash、输出清单、文件大小和 SHA256。`COMPLETE` 仍可能只有失败诊断；以 `result.json` 为准。
10. 读取 [references/quality-and-recovery.md](references/quality-and-recovery.md)，检查实际图片/视频与输入是否一致。只有技术校验、逐帧视觉与时序/接缝要求均通过才称验收成功。默认不加文字/水印/状态说明；将质量限制写在聊天里。
11. 使用环境支持的文件发送工具或媒体交付机制向用户发送实际产物文件，不只发送路径。保留原始输出与证据；有缺陷可以交付明确说明的预览，但不得假称通过。

## 边界与限制

- 默认是批处理，不开公网 ComfyUI，不提供反向隧道、不挖矿、不保活、不自动开启 Manager、遥测或未知脚本。
- 同一任务只一次远端写请求；并发靠锁与原子标记挡住。固定 SDK 的传输适配器强制有界请求并拒绝传输重试；SDK内部结构变化时失败关闭，未知结果仍必须人工核对唯一 slug。
- 不自动上传本地文件；模型和素材须由用户提前挂载合法私有数据集/前置任务输出。自定义节点等同任意代码执行，先审查来源、requirements 与模型许可。上游依赖未全量锁定，是运行风险，不宣称可复现位级一致。
- T4 任务不会自动把两张卡显存合并；仅显式 `minimax-h3-t4-v1` 使用指定双卡插件和 [scripts/h3_compat.py](scripts/h3_compat.py) 的固定源码兼容处理、两卡拷贝预检、原生帧导出。普通 profile 不套 H3 补丁。迁移版未做新的 GPU 端到端验证；原流程经验见 [references/h3-lessons.md](references/h3-lessons.md)。
- 取消必须有官方精确会话 ID 与专用取消接口；此版本不猜 ID、不通过重启/删库“取消”，可在 Kaggle 的 Active sessions 中 Stop Session。仅删除定时巡检不会停止云端 GPU。
- 有界超时、固定模型 hash 与严格解码只能保证技术层；不能保证无幻觉、手势清晰或像素级无缝。分段尾帧控制必须使用上一段**真正交付的最后原生帧**，去掉下一段重复边界与模型网格 padding。
- 安装位置：将本目录作为 `kaggle-comfyui-skill` 放入支持 Agent Skill 的工作区技能目录或实例 Skill 目录中并刷新。仓库发布不等于全局安装/启用，不擅自改宿主配置。

## 开发验证

执行 `python -m unittest discover -s tests -v`。测试默认离线，不读取账号、不触发网络/算力。新增通用 runner、Anima 模板和 H3 迁移配置已做离线测试，未做新的 Kaggle GPU 冒烟运行；不要把原项目的 H3 成片经验冒称为这个新 runner 的端到端通过证明。验证详情与上游边界见 [references/verification.md](references/verification.md)。

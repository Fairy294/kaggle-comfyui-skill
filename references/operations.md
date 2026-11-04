# 配置和运行契约

## 自动安装与配置

README 的简短复制指令包含完整安装配置流程，由 Agent 执行：

1. 定位当前 Agent 实际加载的 skills 目录，从用户指定的仓库安装；已有安装先核对并复用，保留本地修改。
2. 使用 Python 3.11+ 自带的 `venv`；安装目录已有兼容的 `.venv` 时复用，否则运行 `python -m venv .venv` 创建。通过该环境的解释器安装 `requirements.txt` 中的依赖，并运行 `python -m pip check`。
3. 用户已提供 API Token 时，通过 `configure --token-stdin` 持久化保存；未提供时先复用本机 JSON。Token 不回显，不拼入 shell 命令或命令参数。
4. 使用同一 Python 解释器运行 `quota`，向用户报告实际安装位置、配置状态和真实剩余额度。缺少 Token 且本机没有可用配置，或遇到无法自行解决的错误时，再说明具体缺项。

简短请求中的“自动保存配置”按本文件的 JSON 路径和权限规则执行；安装配置只进行本地操作和只读额度查询，GPU 生图按工作流运行授权另行处理。下文保留命令与格式，供 Agent 自动执行及用户选择手动操作时参考。

## 环境与认证

本地支持 Windows、Linux 和 macOS，使用 Python 3.11+ 标准库 `venv` 创建或复用安装目录中的 `.venv`。下文的 `python` 均指该环境的解释器：Linux/macOS 为 `.venv/bin/python`，Windows 为 `.venv\Scripts\python.exe`。Agent 优先直接调用其完整路径，无需依赖 shell 激活状态。

离线 `validate`、`prepare` 和 `configure` 仅用标准库；联机操作在该环境中运行 `python -m pip install -r requirements.txt`，安装官方 `kaggle==2.2.4` CLI/SDK 与 `six==1.17.0`，随后运行 `python -m pip check`。`kaggle==2.2.4` 实际导入 `six`，但未声明该依赖，不能依赖其他包间接安装它。后续命令和子进程均使用同一解释器，无需另行配置 `kaggle` 可执行文件路径。提交锁在 Windows 使用 `msvcrt`，在 Linux/macOS 使用 `fcntl`。

API Token 由用户通过 [Kaggle 官方设置](https://www.kaggle.com/settings/api) 的 API Tokens 创建。用户选择手动命令行配置时运行：

```sh
python scripts/kaggle_comfy.py configure
python scripts/kaggle_comfy.py quota
```

`configure` 提示输入 API Token，不回显输入；成功时仅显示保存路径。持久化文件通过 `Path.home()` 定位：

| 系统 | 默认文件 |
| --- | --- |
| Linux/macOS | `~/.kaggle/kaggle-comfyui.json` |
| Windows | `%USERPROFILE%\.kaggle\kaggle-comfyui.json` |

```json
{
  "api_token": "YOUR_KAGGLE_API_TOKEN"
}
```

这是本 Skill 的配置格式。官方 Token 文件方式使用 `~/.kaggle/access_token`（纯文本），不能直接换成上述 JSON，见 [官方认证说明](https://github.com/Kaggle/kaggle-cli/blob/main/docs/README.md#authentication)。本脚本每次从 JSON 读取 API Token，临时通过 `KAGGLE_API_TOKEN` 传给官方 SDK 或 CLI 子进程；JSON 优先于 shell 中的旧值，不修改宿主 shell，也不要求用户执行 `export`。重开终端、Agent 或电脑后仍然可用；Token 失效、过期或更换时重新运行 `configure`。

用户已提供 API Token 时，Agent 直接运行 `python scripts/kaggle_comfy.py configure --token-stdin`，通过子进程标准输入传入一行 Token，完成保存与额度校验；按用户指令更新已有配置，不再要求用户自行运行命令。不要将 Token 拼进 shell 命令、命令参数，或复述到聊天和日志。用户未提供时先复用本机 JSON；配置缺失时才请用户提供 Token 或使用隐藏输入。也可由用户在上述位置编辑 JSON，字段必须为 `api_token`。没有安全输入终端时，默认配置命令会报错，不降级为回显输入。

JSON 为本机明文配置，放在仓库外。Linux/macOS 写入文件权限为 `0600`；Windows 使用用户目录继承的访问权限，应仅允许本人和必要的系统账户访问。不要将 API Token 写入 Skill、任务配置、工作流或上传到 Kaggle。认证失败时检查该 JSON 与 Token 有效性，不显示内容；离线校验和准备不读取 Token。

需要执行其他官方 CLI 命令时，通过 `python scripts/kaggle_comfy.py kaggle -- ...` 复用同一 JSON。例如 `python scripts/kaggle_comfy.py kaggle -- datasets status your-kaggle-user/private-model-cache --format json`。该入口不重试，单次最多 900 秒；写请求超时先核对远端，不能据此盲目重发。GPU 任务仍按下文 `submit` 流程提交。

## 运行配置

除可选的 `runtime_profile` 外，下列字段均须提供；未使用的数组写 `[]`。字段校验以 [scripts/common.py](../scripts/common.py) 为准。

| 字段 | 约束 |
| --- | --- |
| `version` | 当前为 1 |
| `owner` | 本人 Kaggle 用户名 |
| `accelerator` | `NvidiaTeslaT4` 或 `NvidiaTeslaP100`；实际可用性由平台决定 |
| `timeout_seconds` | 300..43200；还须满足平台限制和实时剩余额度 |
| `comfy` | HTTPS GitHub `repo` 与完整的 40 字符 `revision` |
| `datasets` | `owner/dataset-slug` 数组，用于挂载模型和素材 |
| `parent_kernels` | `owner/kernel-slug` 数组，用于挂载前置任务输出 |
| `models` | 每项为 `source`、`target`、`sha256`；目标相对 ComfyUI `models/` |
| `inputs` | 每项同上；目标相对 ComfyUI `input/` |
| `custom_nodes` | 插件的 GitHub `repo` 与固定 `revision` 数组 |
| `pip_packages` | 精确的 `package==version` 数组，不接收选项、URL 或 shell 命令 |
| `extra_comfy_args` | 受脚本白名单限制，监听地址、端口和输出目录由工具管理 |
| `runtime_profile` | 缺省为 `standard`；H3 使用专用配置，见 [H3 工作流](h3-workflow.md) |

`models` 和 `inputs` 的 `source` 必须是实际 `/kaggle/input/...` 文件；`target` 必须是无路径穿越、无重叠的相对路径。先通过 Kaggle Input 面板或挂载检查确认真实路径，再填写配置。

## 版本与文件校验

本次运行的 `.spec.json` 保存执行所需的代码版本、文件路径和预期 SHA256。[模型来源清单](../assets/model-sources.json) 提供配套示例的公开来源信息；更换模型或代码版本时，重新确认来源、许可和兼容性，并更新运行配置。

模型的预期校验值应来自发布方或已确认的文件版本；用户素材在确定内容后本地计算，例如 `sha256sum FILE`。文件更名不需要修改校验值，权重转换、量化或内容变更后需要重新确认。示例中的全零哈希是占位值，运行前须替换；`validate` 通过仅说明结构合法。

任务身份、实际工作流、文件清单、日志和输出校验值保存在独立任务目录。重复使用的模型可按 [缓存流程](model-cache.md) 保存为本人私有 Dataset。`parent_kernels` 提供前置任务输出，复用前同样需要确认实际挂载路径和文件完整性。

## 命令与生命周期

| 命令 | 行为与边界 |
| --- | --- |
| `configure` | 本地持久化 API Token；默认隐藏输入，`--token-stdin` 支持非交互输入，不联机、不用 GPU |
| `kaggle -- ...` | 从 JSON 加载 API Token 后调用同一解释器的官方 CLI |
| `validate` | 本地检查配置与 API 图，不确认模型文件存在或节点已安装 |
| `prepare` | 本地创建任务目录和唯一 UUID，不写入云端、不使用 GPU |
| `submit` | 在用户授权后带 `--confirm-remote-execution` 执行；先查实时额度，再持久化提交标记并发出一次私有任务请求 |
| `status` | 查询平台状态；平台 `COMPLETE` 后仍须下载并检查任务结果 |
| `logs` | 有界读取，默认 20 秒、最多 60 秒；脱敏保存最后 200KB |
| `download` | 远端终态后下载本任务目录；最多 100 页、5000 文件、总计 30GiB，单文件最多 10GiB |
| `verify` | 离线重查已下载文件的任务身份、输入来源、工作流与输出清单 |

提交要求剩余 GPU 额度覆盖“最大会话时长 +5 分钟余量”。提交超时或返回未知时，保留 `submission.json`，按唯一任务引用核对远端状态；不要删除标记或重新 `prepare` 绕过单次提交限制。

下载中断后保留已有文件并核查，工具不自动覆盖或断点续传。恢复步骤见 [验收与排错](quality-and-recovery.md)。取消任务使用 Kaggle 对应会话的 Stop Session；关闭宿主巡检后仍须确认云端会话已停止。

`download` 和 `verify` 的报告使用 `local_files` 表示本任务下载目录下当前已有的普通文件数，包含日志、清单和媒体；`downloaded_this_run` 只统计这次命令实际下载的文件，单独运行 `verify` 时为 `0`。原字段 `downloaded_files` 已由这两个字段替代，避免 `null` 被误读为文件丢失。`artifacts` 仍只统计成功结果清单中通过大小与 SHA256 检查的媒体产物；本地文件数不表示所有日志都做了哈希校验。

## 执行边界

- 私有 notebook、素材与输出仍会上传 Kaggle，运行前确认数据允许上云。
- ComfyUI 和自定义节点会执行第三方代码；检查来源与依赖，避免在运行环境放置无关凭证。环境变量过滤不能代替隔离。
- 固定 Git 提交不会自动锁定所有传递依赖；环境变化时结合安装日志核对 torch、CUDA 和插件兼容性。
- 当前工具消费已挂载文件，不负责下载权重或创建模型数据集。额度、机器规格和网络条件以当前账号与平台为准。

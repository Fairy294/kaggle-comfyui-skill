# 配置和运行契约

## 环境与认证

本地需要 Python 3.11+ 和支持 POSIX flock 的 Linux/macOS 环境。离线 `validate`、`prepare` 仅用标准库；联机操作使用官方 `kaggle==2.2.4` CLI/SDK。建议在虚拟环境安装依赖，使用同一解释器检查 `python -m pip show kaggle`。

所有 Kaggle CLI/SDK 联机操作都使用环境变量配置 API Key：

```sh
export KAGGLE_API_TOKEN="YOUR_KAGGLE_API_KEY"
python scripts/kaggle_comfy.py quota
```

API Key 由用户通过 Kaggle 官方设置创建并在本机配置。不运行登录脚本，不将 API Key 写入仓库或日志；认证失败时检查本机环境变量。

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
| `validate` | 本地检查配置与 API 图，不确认模型文件存在或节点已安装 |
| `prepare` | 本地创建任务目录和唯一 UUID，不写入云端、不使用 GPU |
| `submit` | 在用户授权后带 `--confirm-remote-execution` 执行；先查实时额度，再持久化提交标记并发出一次私有任务请求 |
| `status` | 查询平台状态；平台 `COMPLETE` 后仍须下载并检查任务结果 |
| `logs` | 有界读取，默认 20 秒、最多 60 秒；脱敏保存最后 200KB |
| `download` | 远端终态后下载本任务目录；最多 100 页、5000 文件、总计 30GiB，单文件最多 10GiB |
| `verify` | 离线重查已下载文件的任务身份、输入来源、工作流与输出清单 |

提交要求剩余 GPU 额度覆盖“最大会话时长 +5 分钟余量”。提交超时或返回未知时，保留 `submission.json`，按唯一任务引用核对远端状态；不要删除标记或重新 `prepare` 绕过单次提交限制。

下载中断后保留已有文件并核查，工具不自动覆盖或断点续传。恢复步骤见 [验收与排错](quality-and-recovery.md)。取消任务使用 Kaggle 对应会话的 Stop Session；关闭宿主巡检后仍须确认云端会话已停止。

## 执行边界

- 私有 notebook、素材与输出仍会上传 Kaggle，运行前确认数据允许上云。
- ComfyUI 和自定义节点会执行第三方代码；检查来源与依赖，避免在运行环境放置无关凭证。环境变量过滤不能代替隔离。
- 固定 Git 提交不会自动锁定所有传递依赖；环境变化时结合安装日志核对 torch、CUDA 和插件兼容性。
- 当前工具消费已挂载文件，不负责下载权重或创建模型数据集。额度、机器规格和网络条件以当前账号与平台为准。

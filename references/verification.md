# 验证范围与已知限制

## 离线检查

在仓库根目录运行：

```sh
python -m unittest discover -s tests -v
python scripts/kaggle_comfy.py validate --spec assets/image.spec.json --workflow assets/image.workflow.json
python scripts/kaggle_comfy.py validate --spec assets/video.spec.json --workflow assets/video.workflow.json
python scripts/kaggle_comfy.py validate --spec assets/anima-turbo.spec.json --workflow assets/anima-turbo.workflow.json
python scripts/kaggle_comfy.py validate --spec assets/h3-character-swap.spec.json --workflow assets/h3-character-swap.workflow.json
python scripts/check_release.py
```

本地联机依赖在 Python 自带 `venv` 创建的环境中单独检查：`python -m pip install -r requirements.txt`、`python -m pip check`；此处 `python` 指该虚拟环境的解释器，创建与复用方式见 [操作说明](operations.md)。清单固定 `kaggle==2.2.4` 与 `six==1.17.0`，避免依赖未声明的间接安装。CI 在各平台安装该清单并检查依赖与 `six` 导入；这一安装步骤需要网络，离线单元测试本身仍只用标准库。配置 API Token 后，运行 `python scripts/kaggle_comfy.py quota` 才能检查真实认证与平台访问。

测试默认不访问真实账号、网络或 GPU；认证测试仅在临时目录使用虚构 API Token。覆盖 JSON 持久化、新进程自动读取、SDK/CLI/日志的 Token 加载与脱敏、离线准备不读取或上传 Token、跨进程提交锁，以及配置与 API 图校验、预算判断、单次提交保护、模拟状态与下载、文件完整性、运行结果识别及专用 profile 的部分兼容边界。

CI 配置了 Windows、Linux、macOS 与 Python 3.11/3.12 的离线检查矩阵。Windows 账号没有符号链接权限时，仅跳过对应链接防护测试；其余测试仍执行。CI 配置本身不代表已经在这些平台运行通过，以实际检查结果为准。

示例账号、数据集、挂载路径和全零校验值需要替换。`validate` 检查结构，不能确认模型已准备、许可适用或云端节点兼容。具体版本和预期文件校验值读取对应 spec 与 [模型来源清单](../assets/model-sources.json)。

## 验证证据

| 检查层次 | 可以支持的结论 |
| --- | --- |
| 离线测试 | 本地逻辑与模拟场景满足测试约束 |
| 配额、状态等只读查询 | 当前账号和任务的实时平台状态 |
| 授权后的实际云端运行 | 该环境和输入组合能够完成相应执行步骤 |
| 下载、解码及视觉验收 | 本任务交付文件完整且符合约定要求 |

当前 runner 和配套预设尚未完成 Kaggle GPU 端到端验证。插件补丁编译通过、模型元数据吻合或其他运行器的结果，不能代替当前代码的实际云端验证。

实际运行证据保存在任务目录：记录输入与代码版本、环境、任务引用、日志、文件清单和验收结果。对新模型、插件或环境的兼容性判断以相应验证为依据，避免从单次运行推广到所有工作流。

## 已知边界

- 上游 Kaggle 镜像、torch/CUDA 和传递依赖可能变化；固定代码提交与模型文件不能单独保证整个环境可复现。
- 普通工作流不自动获得多卡并行；H3 profile 仅支持其专用版本组合。当前不提供 TPU 适配、自动分段改图或自动画质验收。
- 工具不自动下载权重、创建缓存、建立宿主定时任务或猜测取消会话 ID；对应操作流程需在用户授权范围内执行。
- 未知提交结果先核对，任务不自动重提；下载不支持自动覆盖或断点续传。

## 发布检查

`check_release.py` 检查允许发布的路径、文件类型、Skill 入口的本地资源链接及常见凭证和个人信息模式。`doc/` 支持公开演示用的 PNG、JPEG 和 GIF，按扩展名核对文件头，单文件不超过 10 MB（10,000,000 字节），不按 UTF-8 文本读取；其余文件仍使用原有 300 KB 限制和文本扫描。检查结果按文件与规则报告，不打印秘密；仍需检查变更中是否包含私人素材、模型权重或任务日志。

发布前执行离线检查并审阅变更。第三方软件和模型遵循各自条款。仓库发布、宿主安装和实际任务运行分别按用户授权范围执行。

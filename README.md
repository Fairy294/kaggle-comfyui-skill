# Kaggle ComfyUI Skill

在 Kaggle 官方免费额度内跑 ComfyUI，生成图片或视频。支持查询额度、私有任务提交、状态查询、下载和文件校验；既可作为通用智能体技能（Agent Skill），也可独立使用命令行。

## 效果演示

```
[kaggle-comfyui-skill] 使用anima turbo工作流给我生成一张终末地佩丽卡海边骑自行车的图片，要求16:9
```

![](./doc/pelica.png)

实测**4分05秒**完成任务，其中工作流从入队到完成约**30秒**；其余时间主要用于启动环境和安装ComfyUI。因此建议每次多生成几张图片。

| anima turbo v1.1 工作流 | minimax h3 工作流 |
| --- | --- |
| <img src="./doc/Chaika.jpg" height="318" alt="Anima Turbo 示例"> | <img src="./doc/yeshunguang.gif" height="318" alt="MiniMax H3 示例"> |
| 单张耗时约30秒 | 5秒耗时约8小时(右原图，UP梦忆ye) |

## 快速上手

支持 Windows、Linux 和 macOS，需要 Python 3.11+、Agent 客户端（如 Codex、AstrBot）和 Kaggle 账号；也可以独立使用命令行。

> 注册好 Kaggle 账号后，需要在 setting 中完成 `Phone verification` 电话号码验证和 `Identity verification` 人脸认证，并在 `API Tokens` 生成一个 API Token

将下面的 `YOUR_KAGGLE_API_TOKEN` 替换为你的 Kaggle API Token，再发给智能体，由它完成安装、配置和额度校验：

```
请从 https://github.com/riyuexingchennnn/kaggle-comfyui-skill.git 安装这个 skill。我的 Kaggle API Token 是 YOUR_KAGGLE_API_TOKEN，请自动保存配置并验证剩余额度。
```

也可以通过命令行安装配置，使用 Python 3.11+ 自带的 `venv` 创建虚拟环境：

```sh
git clone https://github.com/riyuexingchennnn/kaggle-comfyui-skill.git
cd kaggle-comfyui-skill
python -m venv .venv
```

激活虚拟环境：Linux/macOS 运行 `source .venv/bin/activate`；Windows PowerShell 运行 `.\.venv\Scripts\Activate.ps1`，CMD 运行 `.venv\Scripts\activate.bat`。也可以直接使用 `.venv/bin/python` 或 `.\.venv\Scripts\python.exe` 替代下文的 `python`，无需激活。安装依赖和后续命令均使用该环境的解释器。

```sh
python -m pip install -r requirements.txt
python -m pip check

# 首次配置：按提示输入 API Token，输入不回显，保存到本机 JSON
python scripts/kaggle_comfy.py configure
python scripts/kaggle_comfy.py quota
```

API Token 只需配置一次，重开终端、Agent 或电脑后自动读取，无需再执行 `export`。默认保存位置是 Linux/macOS 的 `~/.kaggle/kaggle-comfyui.json`，Windows 的 `%USERPROFILE%\.kaggle\kaggle-comfyui.json`，格式如下：

```json
{
  "api_token": "YOUR_KAGGLE_API_TOKEN"
}
```

这是本 Skill 的本地明文 JSON 配置，保存在仓库外；脚本自动将 API Token 传给官方 CLI/SDK。Token 失效、过期或更换时重新运行 `configure`。权限与非交互配置方法见 [操作说明](references/operations.md)。

复制所需运行配置，填写本人的 Kaggle 用户名、私有数据集、实际挂载路径和文件 SHA256，并核对工作流中的模型名。示例不含模型权重或私人素材；自定义工作流准备方法见 [工作流说明](references/workflows.md)。

```sh
# 下面以 Anima 为例；配置修改完成后再执行
python scripts/kaggle_comfy.py validate --spec assets/anima-turbo.spec.json --workflow assets/anima-turbo.workflow.json
python scripts/kaggle_comfy.py prepare --spec assets/anima-turbo.spec.json --workflow assets/anima-turbo.workflow.json --jobs-dir ../comfy-jobs

# 将 JOB_DIR 换成上一条命令返回的任务目录；此步才开始消耗GPU
python scripts/kaggle_comfy.py submit --job JOB_DIR --confirm-remote-execution
python scripts/kaggle_comfy.py status --job JOB_DIR
python scripts/kaggle_comfy.py logs --job JOB_DIR --seconds 20
# 任务结束后下载
python scripts/kaggle_comfy.py download --job JOB_DIR
```

智能体用户可将整个仓库放入支持的技能目录并加载 Skill；智能体（Agent）的操作规则见 [SKILL.md](SKILL.md)。

## 自带工作流

| 工作流 | 默认设置 | 文件 |
| --- | --- | --- |
| SD 兼容检查点文生图 | 512×512，20步 | [工作流](assets/image.workflow.json) · [配置](assets/image.spec.json) |
| Wan 2.1 1.3B 文生视频 | 480×320，17 帧，16FPS | [工作流](assets/video.workflow.json) · [配置](assets/video.spec.json) |
| Anima Turbo v1.1 嘉依卡作者示例 | 976×1296，8步，CFG1（仅输出改为保存） | [工作流](assets/anima-turbo.workflow.json) · [配置](assets/anima-turbo.spec.json) |
| H3 角色替换与首帧接力 | 双T4，736×992，124帧，24FPS，8步 | [工作流](assets/h3-character-swap.workflow.json) · [配置](assets/h3-character-swap.spec.json) |

配套工作流是可选示例，按所选模型和任务修改参数。具体版本、文件路径和预期校验值见对应配置，模型来源见 [来源清单](assets/model-sources.json)。

## 使用前须知

- 当前 runner 与配套预设**尚未完成 Kaggle GPU 端到端验证**，离线检查范围与已知限制见 [验证说明](references/verification.md)。
- H3 必须使用固定双T4配置；普通工作流不会自动合并显存。Anima采用**非商业许可**，模型许可不由本仓库MIT覆盖。
- 当前 runner 读取已挂载文件，不自动下载权重。重复运行可按[私有数据集缓存流程](references/model-cache.md)保存、校验后挂载复用。不轮换账号、不绕过额度；令牌、权重和私人素材不要提交Git。提交未知结果时先查远端，不盲目重投。
- 关闭巡检不等于停止GPU；需要停任务时在Kaggle使用Stop Session。产物技术校验不等于画质合格，默认不叠加说明文字。

详细说明：[配置](references/operations.md) · [Anima Turbo](references/anima-turbo.md) · [H3](references/h3-workflow.md) · [工作流](references/workflows.md) · [验收与排错](references/quality-and-recovery.md) · [验证范围](references/verification.md)

[模型来源与哈希](assets/model-sources.json)仅含公开元数据。代码与文档采用 [MIT](LICENSE)，上游软件和模型保留各自条款。

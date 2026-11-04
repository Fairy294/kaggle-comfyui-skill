# Kaggle ComfyUI Skill · 中文说明

在 Kaggle 官方免费额度内跑 ComfyUI，生成图片或视频。支持查询额度、私有任务提交、状态查询、下载和文件校验；既可作为通用智能体技能（Agent Skill），也可独立使用命令行。

## 自带工作流

| 工作流 | 默认设置 | 文件 |
| --- | --- | --- |
| SD 兼容检查点文生图 | 512×512，20步 | [工作流](assets/image.workflow.json) · [配置](assets/image.spec.json) |
| Wan 2.1 1.3B 文生视频 | 480×320，17 帧，16FPS | [工作流](assets/video.workflow.json) · [配置](assets/video.spec.json) |
| Anima Turbo v1.1 嘉依卡作者示例 | 976×1296，8步，CFG1（仅输出改为保存） | [工作流](assets/anima-turbo.workflow.json) · [配置](assets/anima-turbo.spec.json) |
| H3 角色替换与首帧接力 | 双T4，736×992，124帧，24FPS，8步 | [工作流](assets/h3-character-swap.workflow.json) · [配置](assets/h3-character-swap.spec.json) |

H3 专项工作流已包含角色图、服装图、动作/音轨参考、首帧引导和原生PNG导出。Anima 是独立模型，不是SDXL，使用Qwen3 0.6B编码器和Qwen Image VAE。

## 上手

需要 Python 3.11+、Linux/macOS，以及已通过官方方式配置认证的 Kaggle 账号。

```sh
git clone https://github.com/riyuexingchennnn/kaggle-comfyui-skill.git
cd kaggle-comfyui-skill
python3 -m venv .venv
. .venv/bin/activate
python -m pip install kaggle==2.2.4

# Kaggle CLI / SDK 联机操作必须配置 API Key 鉴权：
# 方式 A：设置环境变量 export KAGGLE_API_TOKEN="YOUR_KAGGLE_API_KEY"
# 方式 B：配置本地凭证文件 ~/.kaggle/kaggle.json，写入 {"username":"YOUR_USERNAME","key":"YOUR_KAGGLE_API_KEY"} 并设置权限 chmod 600 ~/.kaggle/kaggle.json
python scripts/kaggle_comfy.py quota
```

你可以把以下一句话发给你的智能体进行安装skill：
> 请帮我安装并配置 kaggle-comfyui-skill：通过 git clone https://github.com/riyuexingchennnn/kaggle-comfyui-skill.git 将技能安装到 skills 目录，并在环境中配置 Kaggle API Key（设置环境变量 export KAGGLE_API_TOKEN="YOUR_KAGGLE_API_KEY" 或在 ~/.kaggle/kaggle.json 中写入 {"username":"YOUR_USERNAME","key":"YOUR_KAGGLE_API_KEY"}），完成依赖安装 kaggle==2.2.4 后运行 python scripts/kaggle_comfy.py quota 校验额度。

不是开箱即用：复制所需配置，填写自己的账号、私有数据集、实际挂载路径和素材SHA256；配套工作流中的模型名也须匹配。示例不含模型权重或私人素材。

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

## 使用前须知

- 通用runner和迁移后的H3 profile **尚未完成新的 Kaggle GPU 端到端实跑**。Anima嘉依卡作者原版已由专项runner完成一次8步GPU核验，不能替代通用runner实测。
- H3 必须使用固定双T4配置；普通工作流不会自动合并显存。Anima采用**非商业许可**，模型许可不由本仓库MIT覆盖。
- 通用runner不自动下载权重。重复运行建议按[私有数据集缓存流程](references/model-cache.md)一次保存、校验后挂载复用；无缓存时可另做经授权的内核直下载。不轮换账号、不绕过额度；令牌、权重和私人素材不要提交Git。提交未知结果时先查远端，不盲目重投。
- 关闭巡检不等于停止GPU；需要停任务时在Kaggle使用Stop Session。产物技术校验不等于画质合格，默认不叠加说明文字。

详细说明：[配置](references/operations.md) · [Anima Turbo](references/anima-turbo.md) · [H3](references/h3-workflow.md) · [工作流](references/workflows.md) · [验收与排错](references/quality-and-recovery.md) · [验证范围](references/verification.md)

[模型来源与哈希](assets/model-sources.json)仅含公开元数据。代码与文档采用 [MIT](LICENSE)，上游软件和模型保留各自条款。

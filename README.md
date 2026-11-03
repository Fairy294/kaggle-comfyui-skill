# Kaggle ComfyUI Skill

Run ComfyUI image and video workflows within official Kaggle quotas. Features quota queries, guarded private job submissions, status tracking, artifact downloads, and integrity checks. Works both as an AstrBot Skill and as a standalone CLI tool.

## Included Workflows

| Workflow | Default Settings | Files |
| --- | --- | --- |
| SD Compatible Checkpoint (T2I) | 512×512, 20 steps | [Workflow](assets/image.workflow.json) · [Spec](assets/image.spec.json) |
| Wan 2.1 1.3B (T2V) | 480×320, 17 frames, 16 FPS | [Workflow](assets/video.workflow.json) · [Spec](assets/video.spec.json) |
| Anima Turbo v1.1 (T2I) | 1024×1024, 10 steps, CFG 1 | [Workflow](assets/anima-turbo.workflow.json) · [Spec](assets/anima-turbo.spec.json) |
| H3 Character Swap & Relay | 2×T4, 736×992, 124 frames, 24 FPS, 8 steps | [Workflow](assets/h3-character-swap.workflow.json) · [Spec](assets/h3-character-swap.spec.json) |

The H3 workflow includes character reference, costume reference, motion/audio references, first-frame guidance, and native PNG export. Anima is a standalone model (not SDXL), using the Qwen3 0.6B text encoder and Qwen Image VAE.

## Quick Start

Requires Python 3.11+, Linux/macOS, and a Kaggle account configured via official credentials.

```sh
git clone https://github.com/riyuexingchennnn/kaggle-comfyui-skill.git
cd kaggle-comfyui-skill
python3 -m venv .venv
. .venv/bin/activate
python -m pip install kaggle==2.2.4
python scripts/kaggle_comfy.py quota
```

Not turn-key: copy the required spec, fill in your own Kaggle account, private datasets, actual mount paths, and input file SHA256 hashes. Model names in the workflow must match your dataset files. No weights or private media are included.

```sh
# Example using Anima Turbo; run after configuring your spec
python scripts/kaggle_comfy.py validate --spec assets/anima-turbo.spec.json --workflow assets/anima-turbo.workflow.json
python scripts/kaggle_comfy.py prepare --spec assets/anima-turbo.spec.json --workflow assets/anima-turbo.workflow.json --jobs-dir ../comfy-jobs

# Replace JOB_DIR with the path returned above; GPU quota is consumed only starting here
python scripts/kaggle_comfy.py submit --job JOB_DIR --confirm-remote-execution
python scripts/kaggle_comfy.py status --job JOB_DIR
python scripts/kaggle_comfy.py logs --job JOB_DIR --seconds 20
# Download after the remote job completes
python scripts/kaggle_comfy.py download --job JOB_DIR
```

AstrBot users can copy this repository to `skills/kaggle-comfyui-skill/` in their workspace. Agent rules and protocols are in [SKILL.md](SKILL.md).

## Notice Before Use

- **New Kaggle GPU end-to-end runs have not yet been executed.** Offline tests are verified. H3 ran successfully in its original standalone project, but the migrated skill version requires live verification once quotas allow.
- H3 strictly requires the dual-T4 profile; regular workflows will not automatically pool VRAM. Anima is under a **non-commercial license**; model terms are not covered by this repository's MIT license.
- No automatic weight downloads, no account rotation, and no quota bypassing. Do not commit tokens or personal media to Git.
- Stopping polling does not stop remote GPU execution; use Kaggle Stop Session to abort tasks. Technical hash validation does not guarantee visual aesthetic quality.

Documentation: [Operations](references/operations.md) · [Anima Turbo](references/anima-turbo.md) · [H3](references/h3-workflow.md) · [Workflows](references/workflows.md) · [Quality & Recovery](references/quality-and-recovery.md) · [Verification](references/verification.md)

[Model Sources & Hashes](assets/model-sources.json) contains public metadata only. Original code and docs are licensed under [MIT](LICENSE); upstream software and models retain their respective terms.

---

# Kaggle ComfyUI Skill · 中文说明

在 Kaggle 官方免费额度内跑 ComfyUI，生成图片或视频。支持查询额度、私有任务提交、状态查询、下载和文件校验；既可作为 AstrBot Skill，也可独立使用命令行。

## 自带工作流

| 工作流 | 默认设置 | 文件 |
| --- | --- | --- |
| SD 兼容检查点文生图 | 512×512，20步 | [工作流](assets/image.workflow.json) · [配置](assets/image.spec.json) |
| Wan 2.1 1.3B 文生视频 | 480×320，17 帧，16FPS | [工作流](assets/video.workflow.json) · [配置](assets/video.spec.json) |
| Anima Turbo v1.1 文生图 | 1024×1024，10步，CFG1 | [工作流](assets/anima-turbo.workflow.json) · [配置](assets/anima-turbo.spec.json) |
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
python scripts/kaggle_comfy.py quota
```

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

AstrBot 用户可将整个仓库放到工作区 `skills/kaggle-comfyui-skill/` 并刷新 Skill；Agent 的操作规则见 [SKILL.md](SKILL.md)。

## 使用前须知

- **尚未完成新的 Kaggle GPU 端到端实跑**。已有离线测试；H3原专项曾运行成功，但迁移后的版本仍需复测。
- H3 必须使用固定双T4配置；普通工作流不会自动合并显存。Anima采用**非商业许可**，模型许可不由本仓库MIT覆盖。
- 不自动下载权重、不轮换账号、不绕过额度；令牌和私人素材不要提交Git。提交未知结果时先查远端，不盲目重投。
- 关闭巡检不等于停止GPU；需要停任务时在Kaggle使用Stop Session。产物技术校验不等于画质合格，默认不叠加说明文字。

详细说明：[配置](references/operations.md) · [Anima Turbo](references/anima-turbo.md) · [H3](references/h3-workflow.md) · [工作流](references/workflows.md) · [验收与排错](references/quality-and-recovery.md) · [验证范围](references/verification.md)

[模型来源与哈希](assets/model-sources.json)仅含公开元数据。代码与文档采用 [MIT](LICENSE)，上游软件和模型保留各自条款。

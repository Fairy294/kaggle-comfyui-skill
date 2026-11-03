# Kaggle ComfyUI Skill · 中文说明

[![离线检查](https://github.com/Fairy294/kaggle-comfyui-skill/actions/workflows/check.yml/badge.svg)](https://github.com/Fairy294/kaggle-comfyui-skill/actions/workflows/check.yml)

在 **Kaggle 官方免费额度内**运行 ComfyUI 图像、视频 API 工作流的 AstrBot Skill，附带可独立使用的 Python 命令行工具。

它负责把工作流准备成私有任务、检查额度、单次提交、读取进度、下载并校验产物；**不是已经打包好所有模型和插件的一键生图网站，也不是无限算力工具**。不轮换账号、不规避配额、不默认启动 GPU。

给人看的入口是本 README；给 Agent 的执行说明是 [SKILL.md](SKILL.md)。

> **验证边界：尚未完成新的 Kaggle GPU 端到端实跑。** 当前示例已通过离线结构检查，工具有离线单元/模拟集成测试；此前 H3 专项工程的成功运行，不代表这里的新通用 runner 或示例已在 GPU 上跑通。

## 仓库里究竟放了什么工作流？

目前只有 **2 个 ComfyUI API 工作流模板 + 2 个配套运行配置**，均位于 `assets/`。不是四套工作流，也不包含权重、私人素材或以前的成片。

| 文件 | 内容 | 示例参数 |
| --- | --- | --- |
| [assets/image.workflow.json](assets/image.workflow.json) | SD 兼容整合检查点文生图 | 512×512、单张、20 步、CFG 7、Euler / normal |
| [assets/image.spec.json](assets/image.spec.json) | 上述图像工作流的 Kaggle 账号、数据集、模型挂载和时限配置 | T4、最大会话 1800 秒、模型位于 `checkpoints/` |
| [assets/video.workflow.json](assets/video.workflow.json) | Wan 2.1 1.3B 文生视频结构示例 | 480×320、17 帧、16 FPS、20 步、CFG 6、uni_pc / simple |
| [assets/video.spec.json](assets/video.spec.json) | 上述视频示例的运行配置 | T4、最大会话 3600 秒，分别挂载扩散模型、文本编码器、VAE |

### 图像模板：SD 兼容检查点文生图

节点链路：

```text
CheckpointLoaderSimple → CLIPTextEncode（正/负向）
                      → EmptyLatentImage → KSampler → VAEDecode → SaveImage
```

检查点文件名是 `your-checkpoint.safetensors` 占位符。你必须换成自己有权使用、与该节点结构兼容的真实模型；不是任意模型改个名字就能使用。正向示例描述一只花园中的红色小机器人，负向包含模糊、文字、水印等词。

### 视频模板：Wan 2.1 1.3B 文生视频

主要节点：`UNETLoader`、`CLIPLoader(type=wan)`、`VAELoader`、`EmptyHunyuanLatentVideo`、`ModelSamplingSD3`、`KSampler`、`VAEDecode`、`CreateVideo`、`SaveVideo`。

配套配置使用以下文件名，仓库内**没有这些权重文件**：

- `wan2.1_t2v_1.3B_fp16.safetensors`
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors`
- `wan_2.1_vae.safetensors`

17 帧 / 16 FPS 约为 **1.06 秒**，只是小规模结构示例，不是完整长视频配方。`SaveVideo` 的组合输入采用固定 ComfyUI 版本中的 `format` 与 `format.codec`；替换版本时须对照目标 `/object_info`，不能保证跨版本兼容。

### H3 专项工作流未包含

此前 H3 的角色替换、动作参考、首帧引导和双 T4 专项运行流程**没有作为可执行工作流迁入这个仓库**；目前仅将相关经验、失败边界和尾帧接力注意事项写入 [references/h3-lessons.md](references/h3-lessons.md)。

因此当前仓库不是此前舞蹈换人任务的完整复刻，不能直接拿它复现该任务。H3 的并行、内存卸载和兼容补丁需要另行适配和验证；两张 T4 也不会自动合成一张大显存 GPU。

## 能做什么

- 查询当前账号的真实 Kaggle GPU / TPU 配额；本运行器只支持 CUDA GPU，不直接使用 TPU。
- 检查 API 工作流格式、节点引用、循环、路径、固定版本和文件哈希配置。
- 离线生成有唯一 UUID 的任务目录，不消耗 GPU。
- 在明确确认后提交 **私有** Kaggle 任务；要求剩余额度覆盖最大会话时长再加 5 分钟余量。
- 通过原子标记与文件锁防止重复提交，未知返回不盲目重投。
- 查询状态、有界读取日志，终态下载输出并核对身份、输入来源、工作流哈希和输出文件大小 / SHA256。
- 在云端检查图像有效性或视频全片解码，保留失败诊断；**不会把技术通过自动判定为画面合格**。

自动每小时巡检由 Agent 使用 AstrBot 的 `future_task` 等宿主工具创建，不是这个仓库后台常驻的功能。通用工作流的首尾帧节点连接、分段切片、拼接与视觉判断也需要 Agent 根据实际模型处理。

## 环境要求与安装

- 本地 Python **3.11+**，Linux / macOS（使用 POSIX 文件锁；原生 Windows 未适配）。
- 离线检查只用 Python 标准库；联机提交、查询、下载需要官方 `kaggle==2.2.4` CLI / SDK。
- Kaggle 账号必须具备相应 GPU、互联网访问和私有输入数据集权限；实际可用额度、硬件和排队情况以平台为准。
- 模型与素材提前由用户合法上传到自己的私有数据集，或作为已有任务输出挂载。

在开发目录中克隆并创建独立环境：

```sh
git clone https://github.com/Fairy294/kaggle-comfyui-skill.git
cd kaggle-comfyui-skill
python3 -m venv .venv
. .venv/bin/activate
python -m pip install kaggle==2.2.4
```

通过 Kaggle 官方方式在本机配置认证，然后检查：

```sh
kaggle -W quota --format json
python scripts/kaggle_comfy.py quota
```

**不要把令牌、密码、`kaggle.json` 或其他凭证放进仓库、工作流或聊天。** 不要为此修改系统 Python，已有 SDK 版本不应在未核验的情况下静默升级。

作为 AstrBot Skill 使用时，把本目录以 `kaggle-comfyui-skill` 为名放入工作区 `skills/`，或由管理员放入实例 Skill 目录并按宿主方式刷新；Agent 从 `SKILL.md` 读取执行规则。克隆或发布仓库**不等于已经在实例中安装启用**。

## 快速使用：先配置，再提交

以下命令从仓库根目录执行。示例不是开箱即用：账号名、数据集路径、模型文件名和 64 位零哈希都需要替换。运行文件放在仓库外的独立目录：

```sh
mkdir -p ../kaggle-comfyui-data/config ../kaggle-comfyui-data/jobs
cp assets/image.spec.json ../kaggle-comfyui-data/config/run.json
cp assets/image.workflow.json ../kaggle-comfyui-data/config/workflow.json
```

用编辑器修改 `run.json` 和 `workflow.json`：

1. `owner` 填自己的 Kaggle username，`datasets` 填真实私有数据集 `owner/slug`。
2. `models[].source` 填实际 `/kaggle/input/...` 文件路径；不要假定它一定与数据集 slug 相同。
3. `models[].target` 是 ComfyUI `models/` 下的相对路径；工作流中的模型名称须一致。
4. `models[].sha256` 填真实文件的 SHA256，例如通过 `sha256sum MODEL_FILE` 计算。素材 `inputs` 也必须填写哈希。
5. 固定 `comfy.revision` 和所有自定义节点提交；确认模型许可和第三方代码来源。
6. `timeout_seconds` 是最大会话时长，不是完成时间预测；额度须留余量。

### 1. 离线校验与准备（不启动 GPU）

```sh
python scripts/kaggle_comfy.py validate \
  --spec ../kaggle-comfyui-data/config/run.json \
  --workflow ../kaggle-comfyui-data/config/workflow.json

python scripts/kaggle_comfy.py prepare \
  --spec ../kaggle-comfyui-data/config/run.json \
  --workflow ../kaggle-comfyui-data/config/workflow.json \
  --jobs-dir ../kaggle-comfyui-data/jobs \
  > ../kaggle-comfyui-data/prepared-image.json

JOB_DIR="$(python -c 'import json; print(json.load(open("../kaggle-comfyui-data/prepared-image.json"))["job"])')"
printf '%s\n' "$JOB_DIR"
```

`validate` 只验证结构与静态规则，不会验证模型已经挂载、模型兼容或云端成功；`prepare` 创建本地任务目录，返回绝对路径。不要反复 `prepare` 来绕开同一任务的提交保护。

### 2. 明确授权后提交（会消耗 GPU 额度）

确认模型、素材、规格和额度均无误后，才执行：

```sh
python scripts/kaggle_comfy.py quota
python scripts/kaggle_comfy.py submit --job "$JOB_DIR" --confirm-remote-execution
```

提交超时或返回未知状态时，先按任务的唯一 Kaggle slug 核对远端；不要删除 `submission.json` 或新建任务盲目重试。

### 3. 状态、日志与下载

```sh
python scripts/kaggle_comfy.py status --job "$JOB_DIR"
python scripts/kaggle_comfy.py logs --job "$JOB_DIR" --seconds 20

# 仅在远端任务已结束后下载
python scripts/kaggle_comfy.py download --job "$JOB_DIR"
python scripts/kaggle_comfy.py verify --job "$JOB_DIR"
```

输出位于 `JOB_DIR/downloads/task-任务UUID/` 下，媒体位于 `media/`。还需查看 `result.json` 与 `output-manifest.json`；远端 `COMPLETE` 不保证生成成功。`verify` 核对下载完整性，云端完成时做过技术解码检查，但仍需本地检查画面、动作、音轨和接缝。

视频示例将复制源文件换成 `assets/video.spec.json` 和 `assets/video.workflow.json`，仍需完成真实模型挂载与配置。使用自己的工作流则从 ComfyUI 导出 **API JSON**，不是 UI 的 `nodes/links` JSON；自定义节点须额外固定来源并在配置中列明。

## 当前限制与注意事项

- 新通用 runner 和两套模板尚未完成新的 Kaggle GPU 端到端实跑；离线测试、历史 H3 成片和当前配额查询不能代替这一项。
- 不提供自动双卡并行、自动显存合并、任意模型适配、自动 TPU 转换、无限免费额度、账号池或自动长视频拼接。
- 上游 Git 提交和模型哈希固定，但 ComfyUI / 插件的传递依赖未全部锁定；自定义节点属于任意代码信任边界。
- 不创建公网 ComfyUI 隧道，不自动安装 Manager，不为保持会话而保活。
- 取消运行可在 Kaggle 的 Active sessions 中使用 **Stop Session**；本工具不猜会话 ID。关闭巡检并不等于停止云端 GPU。
- 下载暂不支持断点续传；已下载目录存在文件时不自动覆盖，先保留证据并核查再处理。
- 技术通过不代表画面通过。默认不向产物叠加状态说明或水印，不用叠化、光流掩盖接缝；缺陷说明应写在交付消息中。

## 开发验证

```sh
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
python scripts/kaggle_comfy.py validate --spec assets/image.spec.json --workflow assets/image.workflow.json
python scripts/kaggle_comfy.py validate --spec assets/video.spec.json --workflow assets/video.workflow.json
python scripts/check_release.py
```

以上均为离线检查，不会启动 GPU。仓库的 GitHub Actions 对 Python 3.11、3.12 运行离线测试、示例校验和公开文件扫描；扫描不是完整安全审计。

## 文件结构与详细资料

```text
README.md              中文项目首页与使用说明
SKILL.md               Agent 的触发与执行规则
assets/                两个 API 工作流及各自运行配置
scripts/               配额、任务、云端运行与发布检查脚本
references/            配置、工作流、验收恢复与 H3 经验
tests/                 离线单元和模拟集成测试
.github/workflows/     双 Python 版本离线检查
```

- [配置与运行契约](references/operations.md)：字段、挂载、私有任务生命周期和供应链边界。
- [图像与视频工作流](references/workflows.md)：示例节点及分段尾帧控制约束。
- [验收与故障恢复](references/quality-and-recovery.md)：状态区分、逐帧检查、超时与重复提交防护。
- [H3 实践经验](references/h3-lessons.md)：专项工程经验与不能泛化的部分。
- [验证范围](references/verification.md)：已验证与未验证事项。
- [CLI 实现](scripts/kaggle_comfy.py)与[云端运行器](scripts/kernel_runtime.py)：命令和行为的实际来源。

## 许可证

本项目原创代码与文档采用 [MIT License](LICENSE)。Kaggle、ComfyUI、自定义节点、模型权重和用户素材保留各自条款；本仓库不重新分发模型或私人素材。

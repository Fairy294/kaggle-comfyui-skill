# H3 角色替换与首帧引导

## 适用范围与文件

此示例用于角色、服装、动作与音轨参考，以及视频首帧引导，需要双 T4 和专用运行配置。

- [API 工作流](../assets/h3-character-swap.workflow.json)：联合音视频生成，并保存原生 PNG 帧。
- [运行配置](../assets/h3-character-swap.spec.json)：模型、输入、插件、代码版本、启动参数与预期文件校验值。
- [兼容实现](../scripts/h3_compat.py)：源码兼容处理、两卡拷贝预检和 H3NativeVideoSave 节点。

H3 专用运行路径与此预设仍缺 Kaggle GPU 端到端证据；Anima 横幅图的成功反馈不覆盖 H3，准备文件和离线测试通过后仍需实际验证，见 [验证说明](verification.md)。

## 机器与版本要求

使用 `runtime_profile: minimax-h3-t4-v1`。该 profile 要求 T4 规格，并在启动后检查至少两张 CUDA 卡；单卡 P100 不适用。序列并行由专用插件实现，不能将两张卡视为一张合并显存的 GPU。

ComfyUI、ComfyUI-GGUF、多卡插件及启动参数以配套 spec 为准，并受 [scripts/common.py](../scripts/common.py) 的 profile 校验约束。更换版本需要重新核对并验证兼容实现，仅修改 spec 中的提交值不会通过现有 profile 校验。

兼容处理检查固定源码锚点并编译候选修改，任一步不匹配即停止；修改仅应用于云端隔离 checkout。处理内容包括工作进程精度与卸载设置、通信与 LoRA 加载、分块计算及特定原生文件读取路径的 tensor.copy_ 回退。该回退不构成所有 SIGSEGV 的通用修复。

模型包含量化组件；FP32 VAE 参数仅描述 VAE 执行精度。会话超时取自运行配置，提交前按 [额度规则](operations.md) 检查余量，同时预留模型、临时文件和输出空间。

## 模型与输入

模型文件及预期 SHA256 直接读取 spec 的 `models`，公开来源与大小见 [模型来源清单](../assets/model-sources.json)。保持工作流加载名称与 `models[].target` 一致；GGUF 视觉投影文件的目标名称须与文本编码器 basename 配对，配套 spec 已记录重命名后的目标路径。

| 输入 | 用途 |
| --- | --- |
| `character.png` | 角色身份参考 |
| `costume-reference.png` | 服装与人物尺度参考 |
| `reference.mp4` | 动作和原音轨参考 |
| `start-frame.png` | 用户确认的起点或上一段实际交付尾帧 |

填写各输入的真实挂载路径和 SHA256，替换占位值。提前处理参考视频的黑边、过渡和模糊，保持动作视频与音轨同步；通用准备方法见 [工作流说明](workflows.md)。

## 帧数与接力

此模型的帧数需满足 `17k+5`，并结合采样节点与上游版本确认；具体尺寸、步数、帧率和长度读取工作流。计算帧数、实际交付帧数与音轨时长分别核对。

将真实起始帧接入 MiniMaxH3AddGuide 的 frame 0 条件，同时保留身份和动作参考。后续段继承上一段真正交付的尾帧，排除重复边界和末尾补齐帧；流程见 [多段视频与首尾帧](workflows.md#多段视频与首尾帧)。

## 输出与验收

H3NativeVideoSave 保存无损原生 PNG 帧和 H.264 MP4，并通过 ComfyUI history 列出成果。输出清单由 runner 生成，文件完整性与实际画面按 [验收流程](quality-and-recovery.md) 分别检查。

需要保留完整参考音轨时，先按实际交付帧范围拼接画面，再统一同步封装音轨，避免多段反复转码造成时间偏移。角色身份、服装、手脸、构图与段间接缝按用户要求验收。

模型、插件及其衍生文件的许可分别以来源清单和上游说明为准，仓库 MIT 不覆盖第三方模型和软件。

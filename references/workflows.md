# 准备图像和视频工作流

## 导出与检查 API 图

从 ComfyUI 导出 API 格式：根对象为节点 ID 到 `{class_type, inputs}` 的映射，`["节点ID", 输出索引]` 表示连线。界面使用的 `nodes/links/widgets_values` JSON 需要先在 ComfyUI 中导出为 API 图。

本地校验检查连线、输出索引、循环和路径。云端启动后，runner 对照 `/object_info` 检查已安装节点与必填输入，再由 `/prompt` 校验值、类型和枚举。节点版本改变时根据实际 schema 更新 API 图，保留动态组合输入，例如 SaveVideo 的 `format.codec`。

## 按任务配置

1. 选择适合目标模型的加载节点、编码器和 VAE，确认工作流中的文件名与 `models[].target` 一致。代码版本、文件校验值和挂载路径按 [运行配置](operations.md) 填写。
2. 按用户目标设置提示词、分辨率、采样参数、视频帧数和帧率。配套示例的参数只适用于对应示例。
3. 将图片、视频、音轨和前置帧通过 `inputs` 放入 ComfyUI `input/`，核对节点实际使用的文件名。
4. 连接 SaveImage、SaveVideo 或相应插件的保存节点，将成果持久化到受管输出目录。当前 runner 只收集 history 中 `type=output` 的文件，单独使用临时预览节点不足以交付。
5. 先执行离线校验；需要 GPU 验证时，在用户授权的额度和时限内运行小任务，按真实日志区分安装、排队、采样和解码。

参考素材中的黑边、叠化、双主体、文字和运动模糊可能被生成结果继承。按任务需要先处理输入，视频与音轨使用相同的裁切范围；修复手法及质量变化应在交付时说明。

## 配套示例

| 示例 | 工作流与配置 | 使用说明 |
| --- | --- | --- |
| SD 兼容检查点文生图 | [工作流](../assets/image.workflow.json) · [配置](../assets/image.spec.json) | 替换检查点名称、挂载路径和占位校验值 |
| Wan 文生视频 | [工作流](../assets/video.workflow.json) · [配置](../assets/video.spec.json) | 分别配置扩散模型、文本编码器和 VAE，核对目标节点 schema |
| Anima Turbo | [工作流](../assets/anima-turbo.workflow.json) · [配置](../assets/anima-turbo.spec.json) | 基于 Chaika 示例，组件和许可见 [Anima Turbo 说明](anima-turbo.md) |
| H3 角色替换与首帧引导 | [工作流](../assets/h3-character-swap.workflow.json) · [配置](../assets/h3-character-swap.spec.json) | 需要专用双卡 profile，见 [H3 说明](h3-workflow.md) |

使用自定义工作流时保留相同的输入、输出和校验契约，按实际模型准备节点与配置。多张 GPU 的显存不会因平台分配而自动合并；多卡执行需要模型和插件支持。

## 多段视频与首尾帧

当前工具不自动切片或改写首帧节点。需要接力时，先确定每段真正交付的帧范围，再把上一段最后一张交付帧的无损 PNG 作为下一段输入。可以通过私有 Dataset 或 `parent_kernels` 挂载，核对真实路径并填写 `inputs` 校验值。

在 API 图中将该帧连接到模型的 I2V、keyframe 或首帧控制节点，同时保留任务所需的身份、动作和音轨参考。只在提示词提及上一段画面不能建立帧级约束。

下一段若包含重复边界帧，拼接时仅保留一次；模型为计算补齐的末尾帧应按交付范围裁去。帧率、帧数和音轨时长一起核对，接力继续使用裁切后真正交付的尾帧。首帧引导仍可能产生重绘，接缝的姿态、构图、身份和运动速度按 [验收流程](quality-and-recovery.md) 检查。

# Anima Turbo 工作流

## 适用范围与文件

Anima Turbo 示例基于 circlestone_labs 的 [Chaika 示例图](https://civitai.com/images/140742450)，模型来源为 [Anima 模型页](https://civitai.com/models/2458426/anima)。版本和文件来源见 [模型来源清单](../assets/model-sources.json)。

- [工作流](../assets/anima-turbo.workflow.json)：保留示例的提示词、节点和推理链，输出由 PreviewImage 改为 SaveImage，供批处理持久化与下载。
- [运行配置](../assets/anima-turbo.spec.json)：记录 ComfyUI 提交、模型文件、目标目录和预期 SHA256；使用前填写本人的账号、数据集及实际挂载路径。

## 模型组件与节点

| 组件 | 加载节点 | ComfyUI 目录 |
| --- | --- | --- |
| Anima Turbo 扩散模型 | UNETLoader | `models/diffusion_models/` |
| Qwen3 文本编码器 | CLIPLoader | `models/text_encoders/` |
| Qwen Image VAE | VAELoader | `models/vae/` |

Anima 使用分离组件，不能直接套用 SDXL 整合检查点的加载方式。具体文件名和校验值以运行配置为准，模型公开来源由来源清单提供。

配套图使用 `CLIPLoader(type=stable_diffusion, device=default)`，尺寸由 ResolutionSelector 连到 EmptyLatentImage。ResolutionSelector 是配置所固定 ComfyUI 版本中的内置节点，运行时仍须核对 `/object_info`。

采样步数、CFG、种子、提示词和尺寸直接读取工作流；按用户任务修改时同步检查模型建议和显存需求。配套图的参数不作为其他模型的默认值。

## 运行前准备

先将有权使用的模型放入本人私有 Dataset，核对实际挂载文件与运行配置；重复使用时按 [模型缓存流程](model-cache.md) 准备。当前 runner 读取挂载文件，不负责在线下载权重。

按 [通用操作流程](operations.md) 校验、准备和提交任务，完成后执行 [下载与验收](quality-and-recovery.md)。该预设与当前 runner 尚未完成 Kaggle GPU 端到端验证，离线结构检查不代表云端兼容性或画质通过；验证范围见 [验证说明](verification.md)。

## 许可

Anima 模型采用 CircleStone Labs Non-Commercial License，限制非商业使用，并涉及 NVIDIA Cosmos 派生模型条款。运行前核对所选文件的当前许可证；仓库 MIT 许可只覆盖本仓库原创内容。

- [官方模型说明](https://huggingface.co/circlestone-labs/Anima)
- [官方许可证](https://huggingface.co/circlestone-labs/Anima/blob/main/LICENSE.md)
- [官方 ComfyUI 使用说明](https://docs.comfy.org/tutorials/image/anima/anima)

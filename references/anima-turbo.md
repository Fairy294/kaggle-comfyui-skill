# Anima Turbo v1.1 工作流

## 来源与版本

用户指定模型页：https://civitai.com/models/2458426/anima 。本预设固定 **turbo-v1.1**，Civitai modelVersionId **3263843**，文件 ID 3147349；Civitai 下载文件名可能是 `anima_turboV11.safetensors`，官方 HF 名为 `anima-turbo-v1.1.safetensors`，公开 SHA256 相同。本 spec 使用 HF 文件名；下载后可按配置改名，但必须核对 hash。

它是 Anima / Cosmos 派生的约 2B DiT，不是 SDXL 检查点，不能用 `CheckpointLoaderSimple` 直接替代此前 SD 示例。

## 文件、哈希和目录

| 文件 | ComfyUI 目标 | SHA256 |
| --- | --- | --- |
| anima-turbo-v1.1.safetensors | diffusion_models/ | fba11953276b57edf59d1dc4f1857ac05aa079c56f982b4d7c20298d57d3f7eb |
| qwen_3_06b_base.safetensors | text_encoders/ | cd2a512003e2f9f3cd3c32a9c3573f820bb28c940f73c57b1ddaa983d9223eba |
| qwen_image_vae.safetensors | vae/ | a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f |

以上 hash 核对自 Civitai 元数据与 [官方 HF 文件树](https://huggingface.co/circlestone-labs/Anima/tree/main/split_files)，不把“metadata 已核对”说成“已下载并实测”。仓库没有模型权重，也不会自动下载。

## 工作流与默认值

- API 图：`assets/anima-turbo.workflow.json`。
- 挂载配置：`assets/anima-turbo.spec.json`；账号、私有数据集与实际 `/kaggle/input/` 路径仍需替换。
- `UNETLoader` + `CLIPLoader` + `VAELoader` 分离加载；文本编码器采用 **type=stable_diffusion**，不是臆造的 `type=anima`。
- `EmptyLatentImage`、1024×1024、1 张、Euler / simple、**10 步 / CFG 1.0**，处于作者 Turbo 的 8～12 步建议范围。
- `CLIPLoader(type=stable_diffusion)` 与 `EmptyLatentImage` 取自官方 `example.png` 内嵌 API prompt，并核对固定 ComfyUI 的 Anima 支持；不要仅因模型 latent family 推测换成 SD3 节点。
- CFG 1 通常不进行常规负向 CFG 引导；保留负向节点以匹配采样器接口，不宣称负向词在此设置下仍有与高 CFG 相同的效果。
- 普通 `KSampler` → `VAEDecode` → `SaveImage`，不额外依赖自定义节点或 Turbo LoRA。此处是完整 Turbo 模型，不是另一个 Turbo-LoRA 变种。

复用 README 的 validate/prepare/submit 流程，只将 spec/workflow 文件替换成上述两个文件。spec 已填写公开模型 hash，但挂载位置、账号、模型来源许可和额度仍须用户确认。首次实际运行建议小任务；本次没有启动 GPU。

## 许可与实测状态

作者声明 **CircleStone Labs Non-Commercial License，非商业使用**；还受 NVIDIA Cosmos 派生模型条款约束。仓库 MIT 不覆盖该模型或其衍生物，商业用途须另行确认授权。

- 官方模型说明：https://huggingface.co/circlestone-labs/Anima
- 官方许可证：https://huggingface.co/circlestone-labs/Anima/blob/main/LICENSE.md
- 官方 ComfyUI 示例：https://docs.comfy.org/tutorials/image/anima/anima

已核对来源、文件hash元数据、官方节点用法与离线结构；**尚未用新版 runner 在 Kaggle GPU 实跑 Anima Turbo**。不承诺任意精度/模型替换的兼容、画质或显存占用。

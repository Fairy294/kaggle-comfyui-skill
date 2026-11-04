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

## 作者嘉依卡示例（默认，2026-11-04 核验）

- 作者：circlestone_labs；模型页 https://civitai.com/models/2458426/anima ，原图 https://civitai.com/images/140742450 。不是另找通用模板重建。
- 未改作者 API：`assets/anima-chaika-original.api.json`；界面图：`assets/anima-chaika-original.ui.json`；来源与元数据 hash：`assets/anima-chaika-source.json`。两份 JSON 直接来自原始 PNG 的 prompt/workflow 字段，保留原提示词、节点 ID 与连线。
- `assets/anima-turbo.workflow.json` 是批处理持久化版：只将节点1的 PreviewImage 改为 SaveImage 并增加文件名前缀，其余字段和推理链不动。要求“原模原样”时必须执行原版 API，在服务关闭前通过 `/history` 的临时图片记录和 `/view?type=temp` 抓取原始 PNG，不能改成保存图后声称完全未改。
- 参数：Anima Turbo v1.1；8步；CFG1.0；Euler/simple；denoise1.0；seed758641017238633；batch1。保持 `CLIPLoader(type=stable_diffusion, device=default)`、UNET weight_dtype=default 和 `EmptyLatentImage`。不是SDXL检查点、SD3 latent，也不追加 LoRA。
- 分辨率链：内置 ResolutionSelector 的 `3:4 (Portrait Standard)`、1.2MP、multiple16，计算结果976×1296。1MP按1024²计算。EmptyLatentImage界面遗留896×1152被连线覆盖，不是实际尺寸。
- ResolutionSelector 已在固定 ComfyUI 提交 `0b05cd8a3683cbf0c291b1472bb8b64da41de9ae` 的 `comfy_extras/nodes_resolution.py` 核验为内置节点；此前按“未注明插件仓库”判断成第三方节点是错误的。禁止盲装同名插件。运行时仍对照 `/object_info` 并由 `/prompt` 校验枚举与类型。
- 原图 UI 的 `control_after_generate=randomize`；界面复现要改为 fixed 并核对种子。API固定数值只提交一次，不会自动随机化。
- 正向词原文：`masterpiece, best quality, score_7, safe, 1girl, chaika trabant, hitsugi no chaika, purple eyes, white hair, dress, hair ornament, sitting, indoors, table, teacup`。
- 负向词原文：`worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration`。CFG1通常不进行常规负向CFG引导，不擅自加词并宣称“原版”。

## 运行与证据

普通挂载配置仍用 `assets/anima-turbo.spec.json`，账号/路径待填写。通用runner只读取挂载模型，不要假称其已支持内核在线拉取。

重复运行优先建立本人私有模型Dataset，一次下载核验、保存原许可证/NOTICE、私有上传、CPU核验挂载后复用，完整流程见 `references/model-cache.md`。没有就绪缓存时，经用户授权的专项runner可在Kaggle内用huggingface_hub拉取官方公开权重：固定HF提交，核验上表三hash后才启动ComfyUI。临时缓存不是持久化Dataset；不得上传凭证或把模型放进Git。

提交必须是私有、唯一任务ID、官方实时quota及硬会话超时；单次写入不重放。提交后立即status和有界logs；短单图每2分钟宿主巡检，完成后下载、验证、发送实际图片并移除本任务巡检。心跳不等于采样进度。

2026-11-04 GPU专项实测通过：使用作者原版10节点API（含内置ResolutionSelector和PreviewImage），三个模型在线下载并逐一核对SHA256；Tesla T4上8/8步，976×1296，种子758641017238633，完整工作流20.358秒、容器执行160.7秒。history与作者API逐字段相同，输出PNG解码/大小/SHA256核验通过，已检查画面并发送实际新图，巡检已清除。输出SHA256为0521193e8fa21caa980f14f73c35d334301bd1fdb002cd9d9bd997b49cdfd8a7。实测范围仅为有界inline-download与preview收集的专项runner；通用挂载runner仍不能据此声称已GPU复测。硬件/软件差异可能导致像素不同。此前独立inline-download runner的1024²、10步爱丽丝运行保留为不同任务证据。

### 旧前置下载器的边界

此前曾尝试用CPU Kernel输出作为下游模型来源，未验证的跨Kernel层级曾导致失败；不再将其当默认缓存。已有明确核验路径的旧任务可继续引用，但不得声称上游文件必须平铺或挂载目录必然等于slug。私有Dataset持久缓存与前置Kernel输出是两种机制，必须区分。

## 许可与实测状态

作者声明 **CircleStone Labs Non-Commercial License，非商业使用**；还受 NVIDIA Cosmos 派生模型条款约束。仓库 MIT 不覆盖该模型或其衍生物，商业用途须另行确认授权。

- 官方模型说明：https://huggingface.co/circlestone-labs/Anima
- 官方许可证：https://huggingface.co/circlestone-labs/Anima/blob/main/LICENSE.md
- 官方 ComfyUI 示例：https://docs.comfy.org/tutorials/image/anima/anima

已核对来源与原版元数据，并完成上述专项runner的Anima GPU实跑。通用挂载runner仍未通过同等GPU复测；不承诺任意精度/模型替换的兼容、画质、显存占用或位级复现。作者原版JSON与上游模型保留各自权利，不因仓库MIT声明重新许可。

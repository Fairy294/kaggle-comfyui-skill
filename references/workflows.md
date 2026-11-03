# 图像和视频工作流

## API 格式

使用 ComfyUI 的“保存/API 导出”（不同版本名称略异）：根对象是节点ID到 `{class_type, inputs}` 的映射；`["节点ID", 输出索引]` 表示连线。不把UI格式的 `nodes/links/widgets_values` 当成可运行API图。

本地校验拒绝缺失连线、负输出索引、环、明显路径穿越。云端启动后对照 `/object_info` 检查已安装节点与必填字段，再由 `/prompt` 完成值/类型/枚举校验。新节点 schema 可能有动态组合键，别在工具中擅自删字段；对照实际schema更新工作流。

## 图像示例

`assets/image.workflow.json` 是 SD兼容整合检查点的512×512文生图结构：CheckpointLoaderSimple、CLIPTextEncode、EmptyLatentImage、KSampler、VAEDecode、SaveImage。先替换 ckpt_name 与 model spec（数据集路径、models/checkpoints目标和实际SHA256）。20步/CFG7只是示例，不适用于所有模型。输出被SaveImage持久化，否则不算可下载成果。

## 视频示例

`assets/video.workflow.json` 是 Wan2.1小型文生视频结构示例，单段17帧、480×320、16FPS，用UNETLoader、CLIPLoader(type=wan)、VAELoader、EmptyHunyuanLatentVideo、ModelSamplingSD3、KSampler、VAEDecode、CreateVideo、SaveVideo。填入合法Wan模型、text_encoder、VAE，并保证 names 与模型目标目录完全一致。

SaveVideo 在固定版本使用动态组合输入：format=auto，format.codec=auto。若目标版本不同，先确认该节点的 `/object_info`，不要把新旧schemas混用。模板是结构示例，未在本次GPU上执行，不能承诺画质或显存适配。ComfyUI自动使用单进程选中的GPU；并不会因Kaggle给两张T4就自动获得30GB合并显存。

## Anima Turbo v1.1

`assets/anima-turbo.workflow.json` 与同名前缀 spec：分离UNET/Qwen3_0.6B/QwenImageVAE，官方示例CLIPtype=stable_diffusion、EmptyLatentImage，1024×1024、10步、CFG1、Euler/simple。不是SDXL检查点。模型三hash已填，但账号路径需配置；非商业许可，见Anima专用说明。

## H3 专项迁移

`assets/h3-character-swap.workflow.json` 与spec：角色/服装/动作/原音轨 +真实frame0引导，固定双T4SP+GGUF，8步联合音视频，保存全部原生PNG。必须显式H3profile，兼容补丁与模型/输入要求详见H3专用说明。新runner迁移版未GPU复测，不宣称原专项运行与新版本等价。

## 用户自定义工作流

1. 固定ComfyUI与所有插件提交、模型文件hash、模型许可。
2. 明确各LoadImage/LoadVideo的input目录与前置帧/音轨路径。
3. 确认SaveImage/SaveVideo/对应插件持久化到受管 output 目录。
4. 先跑小规格或CPU层面校验；大额GPU运行需要单独授权和真实余量，不自动降质量假装交付。
5. 从日志证明实际进入采样与解码；可用task_id、prompt_id追踪，不把排队心跳当百分比。

## 分段首尾帧

此版本不自动改写任意图中的首帧节点；内置H3图已经连接MiniMaxH3AddGuide(frame0)，但仍需选择正确的实际尾帧输入。由Agent按模型接口把上一段真正交付的最后一张无损原生PNG挂载为下一段输入，parent_kernels引用准确前置任务，inputs记录该PNG的SHA256；再在自己的API图连接真实I2V/keyframe控制，不只是放进prompt。

例如第一段native0..119交付，第二段native0是重复边界、交付native1..120，则下一段应继承第二段native120，不是119、更不是采样器多出的123。末尾模型网格padding需排除，不让动作/音轨错位。实际输出会重绘：首帧引导不保证像素一致；比较生成首帧和尾帧的姿势、构图与速度后才能拼接。不要叠化或光流掩盖接缝、模糊或重复动作。

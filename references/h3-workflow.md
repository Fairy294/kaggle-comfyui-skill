# H3 角色替换 + 动作参考 + 首帧引导

这是此前**原专项流程**的脱敏迁移：保留双 T4 模型加载、GGUF 文本/视觉编码、角色替换与 Ref2V Turbo LoRA、动作和音轨参考、帧 0 引导、音视频解码和无损原生帧导出。移除了私人角色描述、图片、视频、账号与历史任务标识，以及不参与执行的辅助 UI 节点。

- API 图：`assets/h3-character-swap.workflow.json`
- 配套 spec：`assets/h3-character-swap.spec.json`
- 显式运行配置：`runtime_profile: minimax-h3-t4-v1`
- 补丁实现与自定义原生帧保存节点：`scripts/h3_compat.py`

**不是只改提示词，也不是通用单卡 workflow。** 迁移版包含可执行 API 图与专用兼容配置，但**尚未在新的通用 runner 上进行 Kaggle GPU 端到端复测**。原专项流程曾完成整段采样，不能据此替迁移版背书。

## 已保留的执行链

```text
双 T4 SP UNET → Character Swap LoRA → Ref2V Turbo 8-step LoRA
角色图 + 服装图 + 动作视频/音轨 → MiniMaxH3ReferenceToVideo
上一段真实交付尾帧 → MiniMaxH3AddGuide(frame_idx=0)
BasicGuider + Euler/simple 8步 → SamplerCustomAdvanced
视频 VAE + 音频 VAE 解码 → CreateVideo(24fps) → H3NativeVideoSave
```

默认生成 **736×992、124 原生帧、24 FPS、8 步**。124 帧约 5.17 秒；如果交付前 5 秒，只取 120 帧，不能把模型网格或重叠边界多出的帧一并拼入。

H3 的模型帧数满足 **17k+5**，常见124/90；参考长度、首帧重复和末尾 padding 必须单独记账。此工具不自动切原视频或自动改图，输入须用户提前切好、同步好音轨。

## 两张卡、固定版本与有界配置

spec 强制：

- T4 机器规格，启动后验证实际分配至少两张 CUDA 卡；P100 单卡不允许套此配置。
- ComfyUI commit `0b05cd8a3683cbf0c291b1472bb8b64da41de9ae`。
- ComfyUI-GGUF `373048b8403a7820620065210a691263d4da0a61`。
- buqi-minimax-h3-multigpu `a864277f81ee7609972eb64cd1fb086f239d4c99`。
- `--lowvram --disable-async-offload --force-fp32 --fp32-vae --use-pytorch-cross-attention`，不允许随意删改；默认普通 profile 不接受这套专用标志。

模型仍有 int8 DiT 和 Q2_K GGUF 编码器；“FP32 VAE”只是执行精度配置，不代表整个模型无量化。默认会话上限36000秒（10小时），提交前须有至少10小时5分钟官方 GPU 余量；不是预计完成时间。CPU内存、模型磁盘空间、网络和各卡显存仍受Kaggle限制，失败不自动重投。

原始固定插件使用SP worker；补丁同步父子进程的精度/卸载设置、公共gather API与LoRA安全反序列化，按token分块Qwen和DiT MLP，并对曾发生故障的原生file-to-GPU分支采取标准tensor.copy_回退。该SIGSEGV根因未确证，不能将“绕开路径”描述成已经根治全部底层问题。

补丁先在内存中检查所有固定源码锚点、编译所有候选文件，再写入云端隔离checkout；任何锚点漂移即停，不强套最新版本。所有修改均在临时ComfyUI目录，不改本机/宿主ComfyUI。工作进程失败标记持久化，主runner轮询检测；两卡各进行16次1MiB真实映射文件→GPU逐字节校验后才启动生成。补丁试应用不等于真实GPU计算验证。

## 必需模型

配套 spec 已记录7个公开文件的 SHA256，来自固定HF revision的元数据。需要用户提前按许可放入私有数据集，仓库不包含权重也不自动下载：

1. `minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors` → `diffusion_models/`，来源 `smhfacct/Minimax-H3-fl2va-ref2va-hybrid-models`。
2. `qwen3vl-32B-MiniMax-H3-Q2_K.gguf` → `text_encoders/`，来源 `realrebelai/MiniMax-H3_GGUFs`。
3. `MiniMax-H3-encoder-mmproj-F16.gguf` → **重命名为** `text_encoders/qwen3vl-32B-MiniMax-H3-mmproj-F16.gguf`，来源 `joeygambino/MiniMax-H3-encoder-GGUF`；必须与编码器basename配对。
4. `minimax_h3_video_vae_fp16.safetensors` → `vae/`，完整视频VAE，非int8替代版。
5. `minimax_h3_audio_vae_fp32.safetensors` → `vae/`，上述两个VAE来源 `Comfy-Org/MiniMax-H3`。
6. `h3_character_swap_pro4500_1000.safetensors` → `loras/`，来源 `akatz-ai/MiniMax-H3-Character-Swap-LoRA`。
7. `minimax_h3_ref2v_turbo_8step_v1.1_768p_comfyui_bf16.safetensors` → `loras/`，来源 `lightx2v/Minimax-h3-Turbo`。

全部模型约38.6GB，还需临时空间与输出空间；云端只挂载和链接，不额外复制整份模型。来源与固定revision见 [assets/model-sources.json](../assets/model-sources.json)。公开可下载不等于允许任意用途，分别检查模型卡/许可、第三方量化衍生条款；MIT只覆盖本仓库原创代码。

## 输入与首帧衔接

四个素材都需要真实SHA256；示例零哈希必须替换：

- `character.png`：用户自己的角色身份图。
- `costume-reference.png`：服装、人物尺度与构图参考，不应当盖过真实首帧姿势。
- `reference.mp4`：当前段的干净动作视频和原音轨，准备为24FPS，不带交叉叠化、黑边或不需要的文字。
- `start-frame.png`：第一段用用户确认的起点；后续段用上一段**真正交付的最后一张原生PNG**，不是聊天截图或采样器多出的尾帧。

`parent_kernels` 可以挂载此前任务输出，将 `inputs[].source` 指向真实原生PNG，target仍叫start-frame.png，填正确hash。运行前现有输入校验核对hash，不允许误接别的任务尾帧；不自动寻找或猜测历史任务。

`MiniMaxH3AddGuide`作为真实frame0条件输入，动作视频和角色图同时保留，但它不是逐像素锁定。若后一段frame0用于重复边界，交付从frame1开始；例如第二段交付到native120，则下一段继承native120，不是119或sampler的123。实际接缝的姿态、位置、人物外貌与速度需对原生输出验收。

## 输出、音轨与质量

`H3NativeVideoSave`在本任务受管media目录保存每张原生PNG与H.264 CRF14 MP4，通过ComfyUI history列出，输出清单会为所有图片与视频生成hash；无私人素材随代码发布。无任何助手叠字、状态水印、光流或叠化。

H3原生音轨与参考音轨不一定逐样本相同。最终多段视频若要求原音乐，应在本地按真实交付帧范围拼接后，从干净完整原片一次性同步封装原音轨，不要用几段AAC反复转码或造成重音。

历史经验仍有手指/手势模糊、背景文本样残留与接缝外观变化。迁移版不自动修复它们，也不保证逐帧清晰或绝对居中。完整技术解码、hash一致、两卡bytecopy smoke通过都不是画质门禁通过。结果可交付明确说明的预览，但不得把旧失败门禁改成成功。

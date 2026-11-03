# 配置和运行契约

## 环境

本地 Python 3.11+。离线 validate/prepare 仅用标准库；远程调用需要 `kaggle==2.2.4`，建议在用户已有虚拟环境中执行 `python -m pip install kaggle==2.2.4`，不要修改系统环境或自动替换现有版本。宿主需支持 POSIX flock（Linux/macOS）。官方CLI与SDK使用同一解释器：安装好后检查 `python -m pip show kaggle` 和 `kaggle -W quota --format json`。

不运行登录脚本、不扫描用户密码、不把 `~/.kaggle` 拷贝到仓库。用户通过 Kaggle 官方设置创建/配置令牌；CLI因认证失败停止时让用户在本机安全配置，不索取聊天密码或验证码。

## spec 字段

下表原有字段均必填，未用数组写 `[]`；新增可选 `runtime_profile`，缺省为 `standard`。只有 `minimax-h3-t4-v1` 会启用固定双T4专用兼容配置，详见H3工作流说明：

|字段|约束|
|---|---|
|version|1|
|owner|本人 Kaggle username，无额外 URL 或密码|
|accelerator|NvidiaTeslaT4 或 NvidiaTeslaP100；不代表GPU可用性保证|
|timeout_seconds|300..43200；须满足平台实际上限及剩余额度减安全余量|
|comfy|`repo` 为纯 HTTPS GitHub 仓库 URL，`revision` 为40字符提交|
|datasets|`owner/private-dataset` 数组；先在 Kaggle 创建合法私有数据集|
|parent_kernels|`owner/kernel-slug` 数组；用于挂载此前任务输出|
|models|source/target/sha256；source 必须是实际 `/kaggle/input/...` 文件，target 是 ComfyUI `models/` 下相对路径|
|inputs|同上；target 是 ComfyUI `input/` 下相对路径|
|custom_nodes|纯 GitHub repo/revision 数组；会安装该提交的 requirements，属于受信任代码边界|
|pip_packages|可选精确 `package==version` 字符串数组，不接收选项/URL/任意shell|
|runtime_profile|可选：standard 或 minimax-h3-t4-v1；后者强制固定版本、两插件、T4与H3专用启动标志|
|extra_comfy_args|普通 profile 有限白名单：lowvram/normalvram/cpu-vae/fp32-vae/fp16-vae/use-pytorch-cross-attention/disable-smart-memory/disable-pinned-memory（均带--）|

挂载路径要先在 Kaggle Input 面板或 CPU-only notebook 确认，工具不会猜数据集 slug 与文件系统目录关系。哈希可用 `sha256sum file` 计算。零哈希示例不是真实模型 hash。

## 私有批处理生命周期

- validate、prepare：本地，无写云端或GPU。
- submit：显式确认后，先查实时 quota，再持久化任务身份，然后调用官方 ApiSaveKernelRequest。强制私有，设置官方 machine_shape、session_timeout_seconds 与 SAVE_AND_RUN_ALL。只发一次请求。每次 prepare 创建新 UUID；不要连续 prepare+submit 来“重试”。
- status：远端任务状态不是画质通过证据。会话 COMPLETE 需再下载 result。
- logs：最多60秒，默认20秒；脱敏保存最后200KB。不是无限堵塞。
- download：终态才拉取，支持官方分页，最多100页/5000文件/30GiB，单文件最多10GiB。仅下载本任务 task-UUID 前缀，拒绝越界路径与外部下载主机；不输出签名URL。
- verify：已下载数据的离线重新核验。下载中断后若目录已存在文件，不自动覆盖；先保留目录并核查，移到旁边另存后再下载。当前无断点续传。

任务结束后先发送产物，再清除宿主巡检。删除巡检不是停止GPU。取消使用 Kaggle Active sessions 的 Stop Session；未确认远端终态前不能说“已停服”。没有会话ID时不猜，不用删除Notebook/创建新session绕过。

## 安全和供应链

- 私有 notebook 和输出仍会上传至 Kaggle，不适用于不能上云的数据。
- ComfyUI/custom_nodes 是第三方任意代码边界，固定提交、审核来源再运行；不要在其环境配置其他业务凭证。工具会过滤常见凭证环境变量，但这不是沙箱，也不能阻止恶意代码主动访问云平台身份。
- 上游 ComfyUI requirements 可能含范围依赖。固定 Git commit 不是完整依赖锁，首次运行记录 bootstrap.log 并按实际 torch/CUDA排错。不要盲目安装浮动 fork、远程shell脚本或关闭验证。
- 新 runner 的脚本是本项目原创，不捆绑原私有素材、任何模型权重、H3修改后的第三方完整文件或聊天记录；H3 profile 仅随附本项目原创兼容补丁代码，运行时对用户授权的固定上游checkout应用。Kaggle/ComfyUI/模型的各自条款仍适用。
- 额度按当前账号官方返回，无“无限GPU”、账号池、刷时长或账户切换。TPU不等于CUDA；任务能否排队、网络、空间、GPU类型受平台影响。

# 私有模型数据集缓存

## 何时使用

重复运行同一模型时，优先将已获许可、哈希核验通过的权重保存到本人私有 Kaggle Dataset；生图任务通过 `spec.datasets` 挂载，`models[].source` 指向真实只读挂载文件，再由 runner 校验 SHA256 并链接到 ComfyUI。它避免每次从 Hugging Face 重新拉取，不保证平台内部挂载时间为零。

本功能是操作流程，不是新增通用下载器：当前 `kaggle_comfy.py` 只消费已挂载文件，不负责创建、上传数据集，也不会自动把临时缓存持久化。专项 inline-download runner 可作无缓存时的回退；不要把它冒称通用runner能力。

## 一次性建立缓存

1. 先查本人已有数据集、存储空间和许可。用户只问“能否”时只解释；明确要求安排后才上传合法模型。默认私有，禁止加 `--public`；不上传图片、工作目录、凭证或无关文件。上次任务在 `/kaggle/temp` 的下载随容器结束可能丢失，不能把历史下载成功说成现在仍有缓存。
2. 专用 staging 目录放在 Skill/Git 外。固定模型上游 revision，逐文件下载并核验 SHA256、字节数；失败的 `.part` 文件不得上传。模型名用原名且可平铺，便于核验，但实际挂载位置必须实测。
3. 保留原许可证、各组件来源和 NOTICE；Anima 还受 CircleStone 非商业及相关派生条款约束，参考 `anima-turbo.md` 的公开来源。不把模型改标 MIT、CC0 或 CC-BY。Kaggle metadata 的 `licenses` 可选 `other`，它仅为平台类别，不替代随包许可证。
4. 目录内建立 `dataset-metadata.json`，例如：

```json
{
  "id": "your-kaggle-user/anima-turbo-v11-model-cache",
  "title": "Anima Turbo v1.1 Private Model Cache",
  "licenses": [{"name": "other"}]
}
```

5. 用已鉴权的固定版本官方 CLI 执行一次：

```sh
kaggle datasets create -p /absolute/staging/models --keep-tabular
kaggle datasets status your-kaggle-user/anima-turbo-v11-model-cache --format json
kaggle datasets files your-kaggle-user/anima-turbo-v11-model-cache --format json
```

`create` 默认私有，SDK对应 `public=False`。先留任务标识和提交标记；超时/未知返回先查该唯一 slug，禁止重放创建或误加新版本。日志不要打印签名URL或令牌。授权使用已有CLI默认分块/断点机制不等于允许盲目重放整次创建。

## 必须核验后才供GPU任务复用

- `READY`/成功状态 + 文件清单大小 + 平台私有属性分别核验；仅收到上传URL不等于已就绪。
- 使用无加速器、无外网的 CPU-only notebook 挂载该私有 Dataset，扫描 `/kaggle/input` 中真实路径并按三份预期 SHA256 校验。该验证不消耗GPU，但仍是云端执行；需要用户授权、硬超时、单次提交与巡检。禁止靠猜测 slug 到目录名的映射填写 spec。
- 将真实 `models[].source`、数据集引用及验证证据保存到运行目录；公共 Skill 中只放占位配置，不写用户账号、私有路径和任务日志。
- 成功后默认复用这个 Dataset；模型版本变化时先核对上游版本/hash，再显式建新版本。缓存失效/挂载失败先读取诊断，不静默消耗一轮GPU重新拉模型。
- 权重数据集和验证代码分开，输出不再复制权重；清理本机副本前确认远端状态与可用性，未经授权不删除数据集。

## 来源与验证范围

- 官方 CLI dataset metadata：https://github.com/Kaggle/kaggle-cli/blob/main/docs/datasets_metadata.md
- 官方 SDK：`KaggleApi.dataset_create_new(..., public=False)`；固定依赖 `kaggle==2.2.4`，已读源码核验默认私有及metadata字段。
- 当前通用runner通过 `spec.datasets`/`models` 使用挂载输入，来源：`scripts/kaggle_comfy.py`、`scripts/kernel_runtime.py`。本说明不代表任意账号数据集已建立或完成GPU复测。

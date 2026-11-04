# 私有模型数据集缓存

## 何时使用

重复使用同一组权重时，可将获准使用的文件保存为本人私有 Kaggle Dataset，之后通过 `spec.datasets` 挂载。runner 按 `models[].source` 读取真实挂载文件，核对 SHA256 后链接到 ComfyUI 模型目录。

当前命令行工具只消费挂载文件。创建、上传或更新数据集由 Agent 在用户授权范围内通过官方 CLI/SDK 执行；检查现有缓存可用后再决定是否上传。

## 建立缓存

1. 确认模型来源、版本、许可和所需空间，检查本人已有私有数据集。临时容器下载目录不作为持久缓存。
2. 在 Skill/Git 外建立独立 staging 目录。按确定的上游版本准备文件，逐项核对预期 SHA256 和大小；剔除未完成的下载文件及无关素材、日志和凭证。
3. 保留各组件的许可证、来源和 NOTICE。平台的许可分类不能替代模型本身的条款。
4. 在 staging 目录建立 `dataset-metadata.json`，名称按本次模型集合填写，例如：

```json
{
  "id": "your-kaggle-user/private-model-cache",
  "title": "Private Model Cache",
  "licenses": [{"name": "other"}]
}
```

5. 使用已配置环境变量认证的官方 CLI 创建私有数据集，并查询状态与文件：

```sh
kaggle datasets create -p /absolute/staging/models --keep-tabular
kaggle datasets status your-kaggle-user/private-model-cache --format json
kaggle datasets files your-kaggle-user/private-model-cache --format json
```

`create` 默认私有，SDK 使用 `public=False`。记录数据集引用及创建结果；超时或响应未知时先核对该引用，避免重复创建或意外新增版本。日志中隐藏令牌和签名 URL。

## 核验与复用

- 分别确认处理成功、平台私有属性、文件清单和大小；上传请求被接受不代表文件已可挂载。
- 首次复用前核实 `/kaggle/input` 的真实文件位置，并按配置逐文件校验。可在授权范围内使用有硬超时的 CPU-only notebook 检查，无需启动 GPU；挂载路径不能由数据集 slug 推测。
- 将数据集引用、实际 `models[].source`、预期 SHA256 和验证结果保存在独立任务目录，再用于 GPU 任务。
- 后续任务优先复用已核实的缓存。更换模型版本、精度或格式后重新确认文件，明确更新数据集版本和运行配置。
- 缓存不可用时先查看诊断，重新下载或上传须在用户授权范围内进行。清理本地副本前确认远端文件可用；删除数据集另行确认。

## 使用边界

Dataset 用于持久保存模型；`parent_kernels` 用于引用前置任务输出。两者的实际挂载路径都需要检查。生图任务通过挂载和链接使用权重，无需将整份权重复制到输出目录。

数据集 metadata 格式见 [官方 CLI 说明](https://github.com/Kaggle/kaggle-cli/blob/main/docs/datasets_metadata.md)。运行配置与文件校验契约见 [操作说明](operations.md)。

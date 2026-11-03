# 验证范围与已知限制

## 可执行验证

在仓库根目录运行：

```sh
python -m unittest discover -s tests -v
python scripts/kaggle_comfy.py validate --spec assets/image.spec.json --workflow assets/image.workflow.json
python scripts/kaggle_comfy.py validate --spec assets/video.spec.json --workflow assets/video.workflow.json
python scripts/check_release.py
```

示例spec的owner、数据集与零哈希是占位，因此上面仅验证结构；不代表模型已准备就绪。实际运行前替换为合法模型hash与真实挂载路径。新runner不下载公共权重、不绕过模型许可。

## 证据分级

- 已验证：离线参数/图引用/路径检查，提交marker防重入，未知响应阻止第二次提交，预算门禁，SDK请求字段序列化，history成功/失败识别，下载清单/hash/身份验算，示例结构，语法与隐私扫描。
- 只读联机：当前官方配额查询。它不消耗新GPU，但不证明新增runner可以在云端完成图像/视频。
- 尚未验证：此版本通用runner在Kaggle GPU上安装、队列、完整采样及输出端到端。没有为本次重构额外消耗GPU；不能拿旧H3专项成片当这份runner实测结果。
- 上游可变：Kaggle镜像、torch/CUDA、ComfyUI requirements和模型/插件兼容性。本工具固定Git提交与模型hash，但未全锁传递依赖。首次GPU小任务仍需单独授权、足够额度和实际视觉复核。
- 不提供：任意工作流保证运行/自动双卡并行/自动分段改图/TPU适配/自动额度续杯/账号池/取消猜ID/断点续传/全自动画质打分。

## 发布检查

`check_release.py`使用明确文件清单，拒绝凭证型字符串、个人路径/账号、私有资产、大文件和未知目录。只报告文件和规则，不打印命中的秘密。仓库应不含.ai-memory、.audit、jobs、outputs、inputs、模型、媒体或本机凭证。第三方ComfyUI/模型文件不随仓库重新许可。

发布采用新私有GitHub仓库先跑CI，再核对文件与远端CI成功后改公开。仓库回滚用git恢复至已验证提交；运行任务不自动重提。全局安装/宿主配置激活需要单独授权，不因推送仓库就改动用户实例。

# 确定性地图 + Runway Gen-4.5 + Kling 4.0

## 设计边界

生成模型不承担史实表达。输入底板不含文字、数字、单位标记、兵力箭头或时间线；模型片段以 14% 透明度叠加，并被严格裁在地图矩形内，不覆盖顶部标题和右侧时间线。Kling 可能生成音轨，合成时统一移除。

| 层 | 内容 | 生成方式 |
| --- | --- | --- |
| 事实层 | 标题、日期、地点、人数、武器数、路线、来源标签 | 确定性渲染 |
| Runway 氛围层 | 纸张纤维、投影门微抖、河面微光 | Gen-4.5，5 秒 |
| Kling 氛围层 | 轻微墨迹扩散、方向光、红蓝指示光 | Kling 4.0，5 秒 |

Runway 段落用于 16–21 秒，Kling 段落用于 28–33 秒。其余 50 秒完全保持确定性画面。

## 文件

- `scripts/prepare_generative_inputs.py`：生成无文字底板。
- `scripts/runway_dual_generate.py`：干运行、付费提交、轮询、断点续传和下载。
- `scripts/composite_hybrid.py`：缩放、去音轨、低透明度合成、抽帧和媒体校验。
- `output/generative/generation-plan.json`：不含密钥和图像 data URI 的请求计划。
- `output/generative/inputs/shanghai-clean-plate-1280x720.png`：模型输入底板。

## 执行

先准备并检查请求：

```powershell
python scripts/prepare_generative_inputs.py
python scripts/runway_dual_generate.py
```

正式提交前，必须通过系统凭证机制把 `RUNWAYML_API_SECRET` 注入当前进程。脚本不接受命令行密钥，也不会把密钥或图像 data URI 写入日志。

```powershell
python scripts/runway_dual_generate.py --submit
python scripts/composite_hybrid.py
```

若提交后进程中断：

```powershell
python scripts/runway_dual_generate.py --resume
```

## 成本与接口

本次试跑预计为 124 credits，按每 credit 0.01 美元计约 1.24 美元：Gen-4.5 约 60 credits，Kling 4.0 720p 约 64 credits。实际计费以提交时的官方价格为准。

使用 Runway Dev API 的 `POST /v1/image_to_video` 和 `GET /v1/tasks/{id}`，API 版本头为 `2024-11-06`。参考：

- https://docs.dev.runwayml.com/api/
- https://docs.dev.runwayml.com/guides/using-the-api/
- https://docs.dev.runwayml.com/guides/models/
- https://docs.dev.runwayml.com/guides/pricing/

## 当前校验

- 无文字底板：1280×720，PNG，473,538 bytes。
- 输入 SHA-256：`CE7F34EEC799F73318BD999590F9EC1792AE36B1D955850A34804A2B19CE5D52`。
- 双模型请求：干运行通过，未发送付费请求。
- 合成器：已用临时模拟片段跑通完整 60 秒管线。
- 模拟合成媒体规格：1920×1080、30fps、H.264、yuv420p、60.000 秒、无音轨。
- 正式模型片段：等待 `RUNWAYML_API_SECRET`，因此正式混合视频尚未生成。

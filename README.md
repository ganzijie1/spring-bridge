# 1976年10月上海敌我形势视频

这是一个可复核、可编辑的 Remotion 地图动画工程。兵力、武器、节点和来源全部集中在 `src/data.json`；动画不从画面反推事实，也不把未知人数平均分配到地点。

## 运行

```powershell
npm install
npm run validate
npm run typecheck
npm run preview
npm run render
```

最终视频默认输出到 `output/shanghai-1976-force-map.mp4`。

若前端依赖安装受环境影响，可直接使用确定性降级渲染器：

```powershell
..\..\.venv-imagegen\Scripts\python.exe scripts\generate_local_texture.py
..\..\.venv-imagegen\Scripts\python.exe scripts\render_video.py --keyframes-only
..\..\.venv-imagegen\Scripts\python.exe scripts\render_video.py
..\..\.venv-imagegen\Scripts\python.exe scripts\qa_video.py
```

它与 Remotion 工程读取同一个 `src/data.json`，输出同为 1920×1080、30fps 的 H.264 视频。

`public/assets/probe-paper.png` 由 ImageGen CLI 的 `gpt-image-2.5-flare` 生成；`generate_local_texture.py` 将其裁切、归一化为正式背景。若该文件缺失，脚本才会启用确定性本地纹理降级。

## 史料口径

- `2,500人集中 + 31,000人待命`：采用可追到批注影印的口径。
- `27,000件武器、225辆车、15部电台`：明确标成事后官方清查口径。
- 黄浦、长宁、杨浦的枪弹数字：按《供批判四人帮参考》所列区级数字展示，并保留政治性来源提示。
- 60军、东海舰队、上海警备区：没有可复核分项人数，不显示虚构数字。
- 江南造船厂、中纺机：同时显示“官方称指挥点”与“研究称联络点”的分歧。
- “准备接受严重考验”：按后出材料转述展示，明确注明未见可独立核验原始手令。

地图坐标是历史地址的现址/旧址近似点，只用于态势示意。

## 张春桥审判照片过场

```powershell
npm run overlay:zhang
```

该命令在 21.5–25.5 秒将张春桥受审历史照片淡入地图左上空白区域，不改变总时长，也不覆盖右侧时间线和主要态势标记。输出为 `output/shanghai-1976-force-map-with-zhang.mp4`；来源与编辑口径记录在 `public/assets/zhang-trial-source.json`。

## Runway + Kling 4.0 混合版

混合版只让生成模型负责纸张、光照、投影抖动和极弱的地图微动。所有标题、时间、地点、数字、兵力节点与路线始终来自确定性视频，不接受模型生成内容。

```powershell
npm run hybrid:prepare
npm run hybrid:dry-run
npm run hybrid:submit
npm run hybrid:composite
```

`hybrid:submit` 会产生付费 API 请求，且只从进程环境读取 `RUNWAYML_API_SECRET`。不要把密钥写入仓库、命令参数或聊天记录。任务提交后中断时，可用 `npm run hybrid:resume` 继续轮询和下载。

默认试跑包含 Runway Gen-4.5 与 Kling 4.0 各 5 秒，预计合计 124 credits（约 1.24 美元）。正式输出为 `output/shanghai-1976-hybrid-runway-kling4.mp4`。详细约束见 `HYBRID.md`。

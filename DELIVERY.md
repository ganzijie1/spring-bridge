# 交付清单

## 成片

- 文件：`output/shanghai-1976-force-map.mp4`
- 时长：60.000 秒
- 视频：H.264 High，1920×1080，30fps，yuv420p
- 音频：无
- SHA-256：`243403735436388372E75E7EA6538C3FE6460900FC14327DB37188E35D53BBF4`

## 事实与可编辑源

- 事实数据合同：`src/data.json`
- SHA-256：`22B3E934684FCB303EA5B7214FE404B6CCE9BB818536A968A893A8CEF90F678A`
- 确定性渲染器：`scripts/render_video.py`
- 数据守卫：`scripts/validate-data.mjs`
- 媒体验收：`scripts/qa_video.py`
- Remotion 可编辑稿：`src/Shanghai1976.tsx`

## ImageGen CLI 资产链

- 生成模型：`gpt-image-2.5-flare`
- 原始资产：`public/assets/probe-paper.png`
- 原始资产 SHA-256：`83B3CD29EFCF2852F264894CEB1BA2C816825B9E10A47560E94F4674DB408CEB`
- 正式纹理：`public/assets/archive-paper.png`
- 处理：等比裁切至 1920×1080并降低色彩饱和度；在视频中以22%混合度使用
- 状态记录：`output/imagegen-status.json`

前两次探针（`gpt-image-1`、`gpt-image-2`）超时；第三次由服务模型目录中列出的 `gpt-image-2.5-flare` 在133.7秒完成。生成资产仅提供纸纹理，不参与地图、兵力、路线或文字。

## 校验结果

- 总状态：PASS
- 详细报告：`output/validation-report.json`
- 报告 SHA-256：`AD4632C0DBA6968CC2DF31DCFAF0C242A271ADA90EE80DC02EAADFADB4DDA0B1`
- 关键帧：`output/keyframes/frame-*.png`
- 成片抽帧拼图：`output/keyframes/video-montage.png`

硬约束均通过：地点没有补写人员数；60军、东海舰队和警备区没有虚构分项兵力；集中人数为2,500；待命人数为31,000；六张关键帧均通过非空像素检查。

## 史料边界

- 2,500人集中、31,000人待命采用可追到批注影印的口径。
- 27,000件/支武器、225辆车、15部电台只标为事后官方清查口径。
- 江南造船厂、中纺机同时保留“秘密指挥点”与“联络点”两种解释。
- “准备接受严重考验”注明为后出材料转述，未将其冒充为已见原始手令。
- 地图坐标为历史地址现址/旧址近似点，不是精确测绘。

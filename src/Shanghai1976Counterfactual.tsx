import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import simulation from './counterfactual-simulation.json';

const FPS = 30;
const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};
const C = {
  paper: '#e8e0cf',
  ink: '#171a1b',
  muted: '#5f625d',
  resistance: '#a32823',
  resistanceSoft: '#d4a096',
  suppression: '#31566a',
  suppressionSoft: '#8ba2ad',
  contested: '#b28a3b',
  gold: '#d3ae59',
  river: '#8caab5',
  white: '#f7f4ec',
};

const milestones = simulation.milestones;
const series = simulation.series;

const fade = (frame: number, start: number, end: number) =>
  interpolate(frame, [start * FPS, (start + 1.2) * FPS, (end - 1.2) * FPS, end * FPS], [0, 1, 1, 0], clamp);

const formatNumber = (value: number) => new Intl.NumberFormat('zh-CN').format(Math.round(value));

const currentMilestone = (day: number) => {
  let current = milestones[0];
  for (const item of milestones) if (item.day <= day) current = item;
  return current;
};

const nodeSnapshot = (node: (typeof simulation.nodes)[number], day: number) => {
  const left = Math.min(node.history.length - 1, Math.max(0, Math.floor(day)));
  const right = Math.min(node.history.length - 1, left + 1);
  const alpha = Math.max(0, Math.min(1, day - left));
  const control = node.history[left].control * (1 - alpha) + node.history[right].control * alpha;
  const state = control >= 0.58 ? 'resistance' : control <= 0.42 ? 'suppression' : 'contested';
  return {control, state};
};

const colorFor = (state: string) =>
  state === 'resistance' ? C.resistance : state === 'suppression' ? C.suppression : C.contested;

const StatBar: React.FC<{label: string; value: number; color: string; suffix?: string}> = ({label, value, color, suffix = ''}) => (
  <div style={{marginBottom: 16}}>
    <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 16, marginBottom: 6}}>
      <span>{label}</span><b>{Math.round(value * 100)}{suffix || '%'}</b>
    </div>
    <div style={{height: 8, background: '#cbc4b6'}}>
      <div style={{width: `${Math.max(0, Math.min(100, value * 100))}%`, height: '100%', background: color}} />
    </div>
  </div>
);

const TrendChart: React.FC<{day: number}> = ({day}) => {
  const width = 340;
  const height = 120;
  const points = series.map((item, index) => ({
    x: index / (series.length - 1) * width,
    y: height - item.active_militia.p50 / 16000 * height,
  }));
  const path = points.map((point, index) => `${index ? 'L' : 'M'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ');
  const marker = points[Math.min(series.length - 1, Math.max(0, Math.round(day)))];
  return (
    <div>
      <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 14, color: '#c8d0ce', marginBottom: 7}}>
        <span>推演：实际参与民兵中位数</span><span>0—16,000</span>
      </div>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {[0, 0.5, 1].map((part) => <line key={part} x1="0" x2={width} y1={height * part} y2={height * part} stroke="#4b5557" strokeWidth="1" />)}
        <path d={path} fill="none" stroke={C.gold} strokeWidth="4" />
        <line x1={marker.x} x2={marker.x} y1="0" y2={height} stroke={C.white} strokeDasharray="5 5" opacity="0.7" />
        <circle cx={marker.x} cy={marker.y} r="6" fill={C.gold} stroke={C.white} strokeWidth="2" />
      </svg>
    </div>
  );
};

const CampaignMap: React.FC<{day: number; frame: number}> = ({day, frame}) => {
  const centralProgress = interpolate(day, [5.5, 12], [0, 1], clamp);
  const riverProgress = interpolate(day, [6.5, 13], [0, 1], clamp);
  const pulse = 1 + 0.12 * Math.sin(frame / 7);
  return (
    <svg width="1390" height="790" viewBox="0 0 1390 790" style={{position: 'absolute', left: 34, top: 170}}>
      <defs>
        <marker id="arrow-blue" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
          <path d="M 0 0 L 6 3 L 0 6 z" fill={C.suppression} />
        </marker>
        <filter id="shadow"><feDropShadow dx="0" dy="3" stdDeviation="4" floodOpacity="0.28" /></filter>
      </defs>
      <path d="M30 80 C250 5 490 30 670 100 C880 180 1110 70 1360 140 L1360 740 C1090 770 870 720 650 760 C390 800 210 720 30 750 Z" fill="#d7cfbf" stroke="#9e978a" strokeWidth="2" />
      <path d="M835 20 C790 135 850 235 790 335 C730 445 825 535 755 770" fill="none" stroke={C.river} strokeWidth="58" opacity="0.66" />
      <path d="M832 20 C790 140 846 235 790 335 C735 445 822 535 755 770" fill="none" stroke="#d9e6e9" strokeWidth="6" opacity="0.7" />
      <path d="M15 460 C190 430 315 445 480 410 C610 382 705 320 810 300" fill="none" stroke="#8b8579" strokeWidth="5" strokeDasharray="13 9" />
      <path d="M90 100 C320 150 495 210 670 280 C820 340 950 365 1180 400" fill="none" stroke="#aaa294" strokeWidth="3" />
      <text x="1040" y="92" fontSize="20" fill={C.muted} fontWeight="700">长江口 / 沿江控制线</text>
      <text x="72" y="712" fontSize="18" fill={C.muted}>示意地图：节点和路线不代表真实逐街战斗</text>

      <path
        d="M 12 175 C 210 190 330 235 500 320 C 610 375 680 420 760 455"
        fill="none" stroke={C.suppression} strokeWidth="7" strokeDasharray="18 11"
        strokeDashoffset={(1 - centralProgress) * 980} markerEnd="url(#arrow-blue)" opacity={centralProgress > 0 ? 0.95 : 0}
      />
      <text x="40" y="150" fontSize="22" fill={C.suppression} fontWeight="900" opacity={centralProgress}>六十军方向</text>
      <path
        d="M 1320 690 C 1140 620 1010 545 870 425 C 820 380 790 325 800 270"
        fill="none" stroke={C.suppression} strokeWidth="7" strokeDasharray="17 10"
        strokeDashoffset={(1 - riverProgress) * 820} markerEnd="url(#arrow-blue)" opacity={riverProgress > 0 ? 0.9 : 0}
      />
      <text x="1120" y="675" fontSize="22" fill={C.suppression} fontWeight="900" opacity={riverProgress}>沿江封锁</text>

      {simulation.edges.map((edge) => {
        const from = simulation.nodes.find((node) => node.id === edge.from)!;
        const to = simulation.nodes.find((node) => node.id === edge.to)!;
        const fromSnapshot = nodeSnapshot(from, day);
        const toSnapshot = nodeSnapshot(to, day);
        const control = (fromSnapshot.control + toSnapshot.control) / 2;
        const state = control >= 0.56 ? 'resistance' : control <= 0.44 ? 'suppression' : 'contested';
        return (
          <line
            key={`${edge.from}-${edge.to}`}
            x1={100 + from.x * 1120}
            y1={50 + from.y * 650}
            x2={100 + to.x * 1120}
            y2={50 + to.y * 650}
            stroke={colorFor(state)}
            strokeWidth={2 + edge.capacity * 4}
            strokeDasharray={state === 'contested' ? '9 7' : undefined}
            opacity={0.24 + edge.capacity * 0.32}
          />
        );
      })}

      {simulation.nodes.map((node) => {
        const snapshot = nodeSnapshot(node, day);
        const state = snapshot.state;
        const color = colorFor(state);
        const x = 100 + node.x * 1120;
        const y = 50 + node.y * 650;
        const isFalling = snapshot.control > 0.34 && snapshot.control < 0.60;
        return (
          <g key={node.id} transform={`translate(${x} ${y})`} filter="url(#shadow)">
            {isFalling && <circle r={30 * pulse} fill="none" stroke={C.contested} strokeWidth="5" opacity="0.65" />}
            <circle r="16" fill={color} stroke={C.white} strokeWidth="4" />
            <rect x="24" y="-19" width={Math.max(108, node.label.length * 25)} height="38" fill="rgba(247,244,236,0.93)" stroke={color} strokeWidth="2" />
            <text x="34" y="8" fontSize="18" fontWeight="900" fill={C.ink}>{node.label}</text>
          </g>
        );
      })}
    </svg>
  );
};

const Intro: React.FC<{frame: number}> = ({frame}) => {
  const opacity = fade(frame, 0, 12);
  const rise = interpolate(frame, [0, 6 * FPS], [22, 0], clamp);
  return (
    <AbsoluteFill style={{opacity, background: 'rgba(232,224,207,0.97)', alignItems: 'center', justifyContent: 'center', zIndex: 30}}>
      <div style={{textAlign: 'center', transform: `translateY(${rise}px)`, width: 1500}}>
        <div style={{fontSize: 24, fontWeight: 900, color: C.resistance, letterSpacing: 0}}>推演</div>
        <div style={{fontSize: 78, fontWeight: 950, lineHeight: 1.12, marginTop: 24}}>张春桥出走上海<br />民兵起义爆发</div>
        <div style={{fontSize: 27, color: C.muted, marginTop: 34}}>1976年10月6日，张春桥成功离京并抵沪</div>
        <div style={{fontSize: 19, color: C.muted, marginTop: 18}}>12,000 条结构情景路径 · 影片采用“中央指挥崩解后继续抵抗”的条件中位路径</div>
      </div>
    </AbsoluteFill>
  );
};

const Ending: React.FC<{frame: number}> = ({frame}) => {
  const opacity = interpolate(frame, [126 * FPS, 132 * FPS], [0, 1], clamp);
  return (
    <AbsoluteFill style={{opacity, zIndex: 25, background: '#111719', color: C.white}}>
      <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 740, overflow: 'hidden'}}>
        <Img src={staticFile('assets/zhang-chunqiao-trial-1980-byte.jpg')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center', filter: 'grayscale(1) contrast(1.05)', opacity: 0.44}} />
        <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(90deg, transparent 40%, #111719 100%)'}} />
        <div style={{position: 'absolute', left: 40, bottom: 32, width: 600, fontSize: 15, lineHeight: 1.5, color: '#c3cac8'}}>
          画面为1980—1981年特别法庭审判照片，仅作人物识别；并非反事实事件现场。
        </div>
      </div>
      <div style={{position: 'absolute', left: 720, top: 90, width: 1110}}>
        <div style={{fontSize: 22, color: C.gold, fontWeight: 900}}>10月26日 · 最后据点失守</div>
        <div style={{fontSize: 62, fontWeight: 950, marginTop: 13}}>公社式结局</div>
        <div style={{fontSize: 28, lineHeight: 1.55, marginTop: 25, maxWidth: 980}}>
          有组织抵抗被走资派弹压军全面镇压。城市控制网络归零，残余组织失去通信与补给，主要领导层进入自裁或被俘处决分支。
        </div>
        <div style={{display: 'flex', gap: 18, marginTop: 34}}>
          <div style={{borderTop: `5px solid ${C.resistance}`, width: 300, paddingTop: 14}}>
            <div style={{fontSize: 30, fontWeight: 950}}>部分领导自裁</div>
          </div>
          <div style={{borderTop: `5px solid ${C.gold}`, width: 360, paddingTop: 14}}>
            <div style={{fontSize: 30, fontWeight: 950}}>其余被俘后处决</div>
          </div>
        </div>
        <div style={{fontSize: 18, lineHeight: 1.55, color: '#aeb8b5', marginTop: 34, maxWidth: 940}}>
          在无外援、持续增援与交通封锁条件下，局部动员最终无法抵消组织和后勤的不对称。
        </div>
      </div>
      <div style={{position: 'absolute', right: 56, bottom: 36, fontSize: 17, color: C.gold, fontWeight: 900}}>推演</div>
    </AbsoluteFill>
  );
};

export const Shanghai1976Counterfactual: React.FC = () => {
  const frame = useCurrentFrame();
  const seconds = frame / FPS;
  const day = interpolate(seconds, [10, 127], [0, 20], clamp);
  const index = Math.min(series.length - 1, Math.max(0, Math.round(day)));
  const state = series[index];
  const milestone = currentMilestone(day);

  return (
    <AbsoluteFill style={{background: C.paper, color: C.ink, fontFamily: 'Microsoft YaHei, Noto Sans CJK SC, sans-serif', overflow: 'hidden'}}>
      <Audio src={staticFile('assets/shanghai-1976-counterfactual-score.mp3')} />
      <Img src={staticFile('assets/archive-paper.png')} style={{position: 'absolute', inset: -20, width: 1960, height: 1120, objectFit: 'cover', opacity: 0.18, mixBlendMode: 'multiply'}} />
      <div style={{position: 'absolute', left: 42, top: 34, width: 1375}}>
        <div style={{display: 'flex', alignItems: 'baseline', justifyContent: 'space-between'}}>
          <div>
            <div style={{fontSize: 44, fontWeight: 950}}>上海民兵起义：战局推演</div>
            <div style={{fontSize: 18, color: C.muted, marginTop: 10}}>张春桥成功抵沪 · 无外省同盟介入 · 中央持续增援与封锁</div>
          </div>
          <div style={{background: C.resistance, color: C.white, padding: '10px 15px', fontSize: 17, fontWeight: 900}}>推演</div>
        </div>
      </div>

      <CampaignMap day={day} frame={frame} />

      <div style={{position: 'absolute', left: 70, top: 178, width: 390, background: 'rgba(247,244,236,0.94)', borderLeft: `7px solid ${C.resistance}`, padding: '17px 22px'}}>
        <div style={{fontSize: 16, color: C.muted}}>史料基线 / 非模型值</div>
        <div style={{fontSize: 26, fontWeight: 950, marginTop: 6}}>集中 2,500 · 待命 31,000</div>
        <div style={{fontSize: 14, color: C.muted, marginTop: 7}}>来源 S1；不按单一地点拆分</div>
      </div>

      <div style={{position: 'absolute', left: 68, bottom: 82, width: 810, background: 'rgba(23,26,27,0.92)', color: C.white, padding: '18px 24px'}}>
        <div style={{display: 'grid', gridTemplateColumns: '160px 1fr', gap: 20, alignItems: 'center'}}>
          <div>
            <div style={{fontSize: 16, color: C.gold, fontWeight: 900}}>战局第 {Math.round(day) + 1} 日</div>
            <div style={{fontSize: 29, fontWeight: 950, marginTop: 5}}>10月{6 + Math.round(day)}日</div>
          </div>
          <div>
            <div style={{fontSize: 25, fontWeight: 950}}>{milestone.title}</div>
            <div style={{fontSize: 17, color: '#d4d9d7', marginTop: 6, lineHeight: 1.45}}>{milestone.detail}</div>
          </div>
        </div>
      </div>

      <div style={{position: 'absolute', right: 0, top: 0, width: 470, height: 1080, background: 'rgba(20,25,27,0.965)', color: C.white, padding: '42px 38px', boxSizing: 'border-box'}}>
        <div style={{fontSize: 17, color: '#aeb8b5'}}>CONDITIONAL SIMULATION</div>
        <div style={{fontSize: 34, fontWeight: 950, lineHeight: 1.2, marginTop: 10}}>战局状态</div>
        <div style={{display: 'inline-block', marginTop: 12, padding: '6px 10px', border: `1px solid ${C.gold}`, color: C.gold, fontSize: 16, fontWeight: 900}}>
          {state.dominant_regime}
        </div>
        <div style={{borderTop: `1px solid #485154`, marginTop: 24, paddingTop: 22}}>
          <div style={{fontSize: 15, color: '#b9c2bf'}}>推演参与民兵 / P10—P90</div>
          <div style={{fontSize: 43, fontWeight: 950, color: C.gold, marginTop: 5}}>{formatNumber(state.active_militia.p50)}</div>
          <div style={{fontSize: 15, color: '#b9c2bf', marginTop: 3}}>{formatNumber(state.active_militia.p10)}—{formatNumber(state.active_militia.p90)} 人</div>
        </div>
        <div style={{marginTop: 26}}>
          <StatBar label="指挥连续性" value={state.command.p50} color={C.resistance} />
          <StatBar label="抵抗方节点控制" value={state.spatial.resistance_control} color={C.resistance} />
          <StatBar label="走资派弹压军控制" value={state.spatial.suppression_control} color={C.suppressionSoft} />
          <StatBar label="网络通信可用度" value={state.spatial.communications} color={C.gold} />
        </div>
        <div style={{marginTop: 26}}><TrendChart day={day} /></div>
        <div style={{marginTop: 28, borderTop: `1px solid #485154`, paddingTop: 18}}>
          <div style={{fontSize: 15, color: '#aeb8b5'}}>结构情景集</div>
          <div style={{fontSize: 25, fontWeight: 900, marginTop: 6}}>12,000 条固定种子路径</div>
          <div style={{fontSize: 15, color: '#bac3c1', lineHeight: 1.5, marginTop: 10}}>
            中央指挥崩解：第 {simulation.summary.collapse_day.p10}—{simulation.summary.collapse_day.p90} 日<br />
            中位崩解日：第 {simulation.summary.collapse_day.p50} 日
          </div>
        </div>
        <div style={{position: 'absolute', left: 38, right: 38, bottom: 34, fontSize: 13, lineHeight: 1.5, color: '#929c99'}}>
          参数为透明情景假设，不是历史频率。节点失守、冲突和人物结局均为反事实模型输出。
        </div>
      </div>

      <Intro frame={frame} />
      <Ending frame={frame} />
    </AbsoluteFill>
  );
};

export const COUNTERFACTUAL_FPS = FPS;
export const COUNTERFACTUAL_DURATION_FRAMES = 150 * FPS;

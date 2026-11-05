import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import data from './data.json';

const COLORS = {
  paper: '#e8e0cf',
  ink: '#171b1d',
  muted: '#5d625e',
  militia: '#b6342e',
  militiaSoft: '#d96a56',
  suppression: '#31566a',
  suppressionSoft: '#6c8994',
  river: '#819da2',
  road: '#7a766b',
  gold: '#a77723',
  white: '#f7f3e9',
};

const mapBox = {x: 54, y: 174, width: 1400, height: 790};
const bounds = {minLon: 121.395, maxLon: 121.565, minLat: 31.175, maxLat: 31.305};

type Location = (typeof data.locations)[number];

const project = (lon: number, lat: number) => ({
  x: mapBox.x + ((lon - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * mapBox.width,
  y: mapBox.y + (1 - (lat - bounds.minLat) / (bounds.maxLat - bounds.minLat)) * mapBox.height,
});

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const fade = (frame: number, start: number, end: number, edge = 24) =>
  Math.min(
    interpolate(frame, [start, start + edge], [0, 1], clamp),
    interpolate(frame, [end - edge, end], [1, 0], clamp),
  );

const count = (value: number) => new Intl.NumberFormat('zh-CN').format(value);

const SourceTag: React.FC<{ids: string[]; compact?: boolean}> = ({ids, compact}) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      fontFamily: 'Arial, sans-serif',
      fontSize: compact ? 16 : 18,
      fontWeight: 800,
      color: COLORS.white,
      background: COLORS.ink,
      padding: compact ? '3px 7px' : '4px 9px',
      lineHeight: 1,
      marginLeft: 8,
    }}
  >
    {ids.join('·')}
  </span>
);

const MapNode: React.FC<{location: Location; visible: number; delay?: number}> = ({
  location,
  visible,
  delay = 0,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = project(location.lon, location.lat);
  const isSuppression = location.side === 'suppression';
  const color = isSuppression ? COLORS.suppression : COLORS.militia;
  const pop = spring({frame: Math.max(0, frame - delay), fps, config: {damping: 18, stiffness: 120}});
  const distribution = location.kind === 'distribution';
  const disputed = location.kind === 'disputed_command';
  const labelWidth = distribution ? 222 : 198;
  const labelX = p.x > 1180 ? p.x - labelWidth - 18 : p.x + 18;
  const labelY = p.y < 235 ? p.y + 12 : p.y - 34;

  return (
    <g opacity={visible} transform={`translate(${p.x} ${p.y}) scale(${0.6 + 0.4 * pop}) translate(${-p.x} ${-p.y})`}>
      <circle cx={p.x} cy={p.y} r={17} fill={color} opacity={0.15} />
      <circle cx={p.x} cy={p.y} r={8} fill={COLORS.white} stroke={color} strokeWidth={4} />
      {disputed ? (
        <circle cx={p.x} cy={p.y} r={13} fill="none" stroke={color} strokeWidth={2} strokeDasharray="4 4" />
      ) : null}
      <rect
        x={labelX}
        y={labelY}
        width={labelWidth}
        height={distribution ? 66 : 52}
        rx={3}
        fill={COLORS.white}
        fillOpacity={0.93}
        stroke={color}
        strokeWidth={2}
      />
      <text x={labelX + 10} y={labelY + 22} fill={COLORS.ink} fontSize={19} fontWeight={800}>
        {location.short}
      </text>
      {distribution &&
      'weapons' in location &&
      'rounds' in location &&
      typeof location.rounds === 'number' ? (
        <text x={labelX + 10} y={labelY + 49} fill={color} fontSize={17} fontWeight={700}>
          枪 {location.weapons}支 · 弹 {count(location.rounds)}发
        </text>
      ) : (
        <text x={labelX + 10} y={labelY + 42} fill={COLORS.muted} fontSize={14}>
          {isSuppression ? '兵力未见可靠分项' : location.address}
        </text>
      )}
    </g>
  );
};

const Route: React.FC<{
  from: [number, number];
  to: [number, number];
  color: string;
  progress: number;
  dashed?: boolean;
  bend?: number;
}> = ({from, to, color, progress, dashed = true, bend = -80}) => {
  const a = project(from[0], from[1]);
  const b = project(to[0], to[1]);
  const cx = (a.x + b.x) / 2;
  const cy = (a.y + b.y) / 2 + bend;
  const path = `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`;
  return (
    <path
      d={path}
      fill="none"
      stroke={color}
      strokeWidth={5}
      strokeDasharray={dashed ? '12 10' : '1 0'}
      strokeDashoffset={(1 - progress) * 900}
      opacity={0.9}
      markerEnd={`url(#arrow-${color === COLORS.militia ? 'red' : 'blue'})`}
    />
  );
};

const BaseMap: React.FC<{frame: number}> = ({frame}) => {
  const allNodes = data.locations;
  const militiaNodes = allNodes.filter((x) => x.side === 'militia');
  const suppressionNodes = allNodes.filter((x) => x.side === 'suppression');
  const districtVisible = interpolate(frame, [620, 690], [0, 1], clamp);
  const commandVisible = interpolate(frame, [360, 440], [0, 1], clamp);
  const suppressionVisible = interpolate(frame, [1510, 1590], [0, 1], clamp);
  const linkProgress = interpolate(frame, [900, 1130], [0, 1], clamp);
  const takeoverProgress = interpolate(frame, [1580, 1810], [0, 1], clamp);
  const militiaHq = data.locations.find((x) => x.id === 'militia_hq')!;
  const jiangnan = data.locations.find((x) => x.id === 'jiangnan')!;
  const textile = data.locations.find((x) => x.id === 'textile')!;
  const naval = data.locations.find((x) => x.id === 'naval_base')!;
  const garrison = data.locations.find((x) => x.id === 'garrison')!;

  return (
    <svg width="100%" height="100%" viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0}}>
      <defs>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="4" stdDeviation="5" floodOpacity="0.18" />
        </filter>
        <marker id="arrow-red" markerWidth="12" markerHeight="12" refX="10" refY="4" orient="auto">
          <path d="M 0 0 L 10 4 L 0 8 z" fill={COLORS.militia} />
        </marker>
        <marker id="arrow-blue" markerWidth="12" markerHeight="12" refX="10" refY="4" orient="auto">
          <path d="M 0 0 L 10 4 L 0 8 z" fill={COLORS.suppression} />
        </marker>
      </defs>

      <rect x={mapBox.x} y={mapBox.y} width={mapBox.width} height={mapBox.height} fill="#d9d0bd" fillOpacity={0.52} />

      <g opacity={0.28} stroke={COLORS.road} strokeWidth={2} fill="none">
        <path d="M 80 730 C 310 610 520 560 760 580 S 1140 700 1430 610" />
        <path d="M 90 520 C 360 500 580 410 810 440 S 1190 520 1430 420" />
        <path d="M 180 270 C 390 350 620 310 840 330 S 1180 260 1410 330" />
        <path d="M 270 190 C 330 380 390 620 360 930" />
        <path d="M 560 180 C 610 390 580 650 650 950" />
        <path d="M 870 180 C 830 430 900 710 870 960" />
        <path d="M 1190 180 C 1130 390 1220 650 1260 950" />
      </g>

      <path
        d="M 1030 168 C 970 270 1010 350 1080 430 C 1160 520 1070 610 1110 700 C 1150 790 1300 820 1435 880"
        fill="none"
        stroke={COLORS.river}
        strokeWidth={74}
        opacity={0.54}
      />
      <path
        d="M 1030 168 C 970 270 1010 350 1080 430 C 1160 520 1070 610 1110 700 C 1150 790 1300 820 1435 880"
        fill="none"
        stroke="#dce6e4"
        strokeWidth={2}
        opacity={0.85}
      />
      <text x="1110" y="510" fill={COLORS.suppression} fontSize={17} fontWeight={800} transform="rotate(78 1110 510)">
        黄浦江
      </text>

      <g opacity={0.5} fill={COLORS.muted} fontSize={16} fontWeight={700}>
        <text x="105" y="930">长宁</text>
        <text x="520" y="760">徐汇</text>
        <text x="790" y="540">黄浦</text>
        <text x="920" y="300">虹口</text>
        <text x="1210" y="260">杨浦</text>
      </g>

      {frame >= 840 ? (
        <g opacity={interpolate(frame, [840, 900], [0, 1], clamp)}>
          <Route
            from={[militiaHq.lon, militiaHq.lat]}
            to={[jiangnan.lon, jiangnan.lat]}
            color={COLORS.militia}
            progress={linkProgress}
            bend={70}
          />
          <Route
            from={[militiaHq.lon, militiaHq.lat]}
            to={[textile.lon, textile.lat]}
            color={COLORS.militia}
            progress={linkProgress}
            bend={-55}
          />
        </g>
      ) : null}

      {frame >= 1560 ? (
        <g opacity={suppressionVisible}>
          <Route
            from={[naval.lon, naval.lat]}
            to={[garrison.lon, garrison.lat]}
            color={COLORS.suppression}
            progress={takeoverProgress}
            bend={35}
          />
          <Route
            from={[garrison.lon, garrison.lat]}
            to={[militiaHq.lon, militiaHq.lat]}
            color={COLORS.suppression}
            progress={takeoverProgress}
            bend={-20}
          />
        </g>
      ) : null}

      {militiaNodes.map((location, index) => (
        <MapNode
          key={location.id}
          location={location}
          delay={350 + index * 16}
          visible={location.kind === 'distribution' ? districtVisible : commandVisible}
        />
      ))}
      {suppressionNodes.map((location, index) => (
        <MapNode
          key={location.id}
          location={location}
          delay={1520 + index * 25}
          visible={suppressionVisible}
        />
      ))}

      <rect x={mapBox.x} y={mapBox.y} width={mapBox.width} height={mapBox.height} fill="none" stroke={COLORS.ink} strokeWidth={3} />
    </svg>
  );
};

const ForceSummary: React.FC<{frame: number}> = ({frame}) => {
  const opacity = fade(frame, 280, 850, 38);
  const reveal = interpolate(frame, [320, 520], [0, 1], clamp);
  return (
    <div
      style={{
        position: 'absolute',
        left: 86,
        top: 206,
        width: 470,
        opacity,
        background: 'rgba(247,243,233,0.95)',
        borderTop: `7px solid ${COLORS.militia}`,
        boxShadow: '0 12px 30px rgba(26,25,21,0.18)',
        padding: '24px 28px 26px',
      }}
    >
      <div style={{fontSize: 22, fontWeight: 900, color: COLORS.militia}}>10月8日批注所见</div>
      <div style={{display: 'flex', gap: 34, marginTop: 18}}>
        <div>
          <div style={{fontSize: 56, fontWeight: 950, lineHeight: 1}}>{Math.round(2500 * reveal).toLocaleString()}</div>
          <div style={{fontSize: 20, color: COLORS.muted, marginTop: 7}}>人集中</div>
        </div>
        <div>
          <div style={{fontSize: 56, fontWeight: 950, lineHeight: 1}}>{Math.round(31000 * reveal).toLocaleString()}</div>
          <div style={{fontSize: 20, color: COLORS.muted, marginTop: 7}}>人待命</div>
        </div>
      </div>
      <div style={{marginTop: 20, fontSize: 18, lineHeight: 1.55, color: COLORS.ink}}>
        全市汇总，<b>没有可靠逐点/逐区人员拆分</b>
        <SourceTag ids={['S1']} compact />
      </div>
    </div>
  );
};

const OfficialLedger: React.FC<{frame: number}> = ({frame}) => {
  const opacity = fade(frame, 700, 1180, 35);
  const items = [
    ['27,000', '件/支武器'],
    ['225', '辆车辆'],
    ['15', '部电台'],
  ];
  return (
    <div
      style={{
        position: 'absolute',
        left: 80,
        bottom: 130,
        width: 560,
        opacity,
        padding: '22px 26px 20px',
        background: 'rgba(23,27,29,0.92)',
        color: COLORS.white,
      }}
    >
      <div style={{fontSize: 20, fontWeight: 900, color: '#efc66f'}}>事后官方清查口径</div>
      <div style={{display: 'flex', gap: 34, marginTop: 14}}>
        {items.map(([number, label]) => (
          <div key={number} style={{minWidth: 120}}>
            <div style={{fontSize: 34, fontWeight: 950}}>{number}</div>
            <div style={{fontSize: 16, color: '#cfd5d2'}}>{label}</div>
          </div>
        ))}
      </div>
      <div style={{fontSize: 16, color: '#e8d8b7', marginTop: 14}}>
        指控性材料，不自动等同于中性统计 <SourceTag ids={['S3']} compact />
      </div>
    </div>
  );
};

const Instruction: React.FC<{frame: number}> = ({frame}) => {
  const opacity = fade(frame, 170, 830, 30);
  return (
    <div
      style={{
        position: 'absolute',
        right: 502,
        top: 192,
        width: 410,
        opacity,
        background: 'rgba(247,243,233,0.94)',
        borderRight: `8px solid ${COLORS.gold}`,
        padding: '20px 24px',
        textAlign: 'right',
      }}
    >
      <div style={{fontSize: 20, fontWeight: 900, color: COLORS.gold}}>训令</div>
      <div style={{fontFamily: 'STKaiti, KaiTi, serif', fontSize: 34, fontWeight: 800, marginTop: 7}}>
        “准备接受严重考验”
      </div>
      <div style={{fontSize: 14, color: COLORS.muted, lineHeight: 1.45, marginTop: 9}}>
        据后出材料转述；未见可独立核验原始手令 <SourceTag ids={['S5']} compact />
      </div>
    </div>
  );
};

const DisputedNodes: React.FC<{frame: number}> = ({frame}) => {
  const opacity = fade(frame, 890, 1390, 35);
  return (
    <div
      style={{
        position: 'absolute',
        left: 760,
        bottom: 130,
        width: 660,
        opacity,
        background: 'rgba(247,243,233,0.95)',
        borderLeft: `8px solid ${COLORS.militia}`,
        padding: '20px 26px',
      }}
    >
      <div style={{fontSize: 22, fontWeight: 900}}>江南造船厂 · 中纺机</div>
      <div style={{display: 'grid', gridTemplateColumns: '190px 1fr', gap: 8, marginTop: 14, fontSize: 18, lineHeight: 1.45}}>
        <b style={{color: COLORS.militia}}>事后官方材料</b><span>称“秘密指挥点” <SourceTag ids={['S3']} compact /></span>
        <b style={{color: COLORS.suppression}}>回忆与研究</b><span>认为更接近联络点 <SourceTag ids={['S6']} compact /></span>
      </div>
      <div style={{fontSize: 16, color: COLORS.muted, marginTop: 12}}>动画以虚线圆环表示争议，不强行裁决。</div>
    </div>
  );
};

const RegionalInset: React.FC<{frame: number}> = ({frame}) => {
  const opacity = fade(frame, 1160, 1640, 34);
  const progress = interpolate(frame, [1220, 1470], [0, 1], clamp);
  const points = {
    wuxi: {x: 175, y: 130},
    suzhou: {x: 285, y: 210},
    shanghai: {x: 500, y: 270},
    ningbo: {x: 535, y: 425},
  };
  return (
    <div
      style={{
        position: 'absolute',
        left: 82,
        top: 204,
        width: 620,
        height: 520,
        opacity,
        background: 'rgba(247,243,233,0.97)',
        borderTop: `7px solid ${COLORS.suppression}`,
        boxShadow: '0 12px 35px rgba(26,25,21,0.2)',
      }}
    >
      <div style={{padding: '20px 24px 8px', fontSize: 22, fontWeight: 900, color: COLORS.suppression}}>
        走资派弹压军 · 外围压力
      </div>
      <svg width="620" height="450" viewBox="0 0 620 450">
        <path d="M 40 70 C 190 20 360 35 590 95 L 590 430 C 420 420 250 380 70 430 Z" fill="#ded6c6" />
        <path d="M 420 80 C 470 170 430 230 490 300 C 545 360 560 400 590 440" fill="none" stroke={COLORS.river} strokeWidth={22} opacity={0.5} />
        <path
          d={`M ${points.wuxi.x} ${points.wuxi.y} Q 220 175 ${points.suzhou.x} ${points.suzhou.y} Q 400 230 ${points.shanghai.x} ${points.shanghai.y}`}
          fill="none"
          stroke={COLORS.suppression}
          strokeWidth={6}
          strokeDasharray="14 10"
          strokeDashoffset={(1 - progress) * 650}
          markerEnd="url(#inset-arrow)"
        />
        <path
          d={`M ${points.ningbo.x} ${points.ningbo.y} Q 585 355 ${points.shanghai.x} ${points.shanghai.y}`}
          fill="none"
          stroke={COLORS.suppression}
          strokeWidth={6}
          strokeDasharray="14 10"
          strokeDashoffset={(1 - progress) * 420}
          markerEnd="url(#inset-arrow)"
        />
        <defs>
          <marker id="inset-arrow" markerWidth="12" markerHeight="12" refX="10" refY="4" orient="auto">
            <path d="M 0 0 L 10 4 L 0 8 z" fill={COLORS.suppression} />
          </marker>
        </defs>
        {Object.entries(points).map(([name, p]) => (
          <g key={name}>
            <circle cx={p.x} cy={p.y} r={8} fill={name === 'shanghai' ? COLORS.militia : COLORS.suppression} />
            <text x={p.x + 12} y={p.y - 10} fontSize={18} fontWeight={800} fill={COLORS.ink}>
              {{wuxi: '无锡', suzhou: '苏州', shanghai: '上海', ningbo: '宁波'}[name as keyof typeof points]}
            </text>
          </g>
        ))}
        <text x="56" y="340" fontSize={20} fontWeight={900} fill={COLORS.suppression}>陆军第60军</text>
        <text x="56" y="368" fontSize={16} fill={COLORS.muted}>无锡—苏州—上海战略方向示意</text>
        <text x="56" y="398" fontSize={20} fontWeight={900} fill={COLORS.suppression}>东海舰队 / 海军上海基地</text>
        <text x="56" y="426" fontSize={16} fill={COLORS.muted}>指挥与控制关系示意</text>
      </svg>
      <div style={{position: 'absolute', right: 22, top: 22, fontSize: 16, color: COLORS.militia, fontWeight: 900}}>
        人数：未见可靠分项
      </div>
    </div>
  );
};

const TakeoverBand: React.FC<{frame: number}> = ({frame}) => {
  const opacity = fade(frame, 1570, 2070, 35);
  return (
    <div
      style={{
        position: 'absolute',
        left: 82,
        bottom: 126,
        width: 1320,
        opacity,
        background: 'rgba(49,86,106,0.94)',
        color: COLORS.white,
        padding: '19px 26px 20px',
        display: 'grid',
        gridTemplateColumns: '210px 1fr',
        gap: 26,
      }}
    >
      <div>
        <div style={{fontSize: 38, fontWeight: 950}}>10月20日</div>
        <div style={{fontSize: 17, color: '#cbd9de'}}>中央工作组抵沪</div>
      </div>
      <div style={{fontSize: 21, lineHeight: 1.45}}>
        虹桥机场 → 水电路海军上海基地 → 联络上海警备区及驻沪部队
        <div style={{fontSize: 16, color: '#d8e1e4', marginTop: 5}}>
          公开材料确认指挥节点，但不支持给各部队补写人数 <SourceTag ids={['S5']} compact />
        </div>
      </div>
    </div>
  );
};

const Timeline: React.FC<{frame: number}> = ({frame}) => {
  const stages = [120, 470, 820, 1570, 1990];
  const active = stages.reduce((last, threshold, index) => (frame >= threshold ? index : last), 0);
  return (
    <div
      style={{
        position: 'absolute',
        right: 0,
        top: 0,
        width: 420,
        height: 1080,
        background: 'rgba(20,25,27,0.95)',
        color: COLORS.white,
        padding: '54px 38px 40px',
        boxSizing: 'border-box',
      }}
    >
      <div style={{fontSize: 19, color: '#b9c2bf', fontWeight: 800}}>1976 · SHANGHAI</div>
      <div style={{fontSize: 36, fontWeight: 950, lineHeight: 1.15, marginTop: 12}}>事件时间线</div>
      <div style={{position: 'relative', marginTop: 54}}>
        <div style={{position: 'absolute', left: 11, top: 10, bottom: 10, width: 2, background: '#596266'}} />
        {data.timeline.map((item, index) => {
          const isActive = index === active;
          return (
            <div key={item.date} style={{position: 'relative', paddingLeft: 48, minHeight: 150, opacity: isActive ? 1 : 0.5}}>
              <div
                style={{
                  position: 'absolute',
                  left: isActive ? 0 : 4,
                  top: 3,
                  width: isActive ? 24 : 16,
                  height: isActive ? 24 : 16,
                  background: isActive ? (index < 3 ? COLORS.militia : COLORS.suppressionSoft) : '#8c9491',
                  border: '3px solid #161b1d',
                  borderRadius: '50%',
                }}
              />
              <div style={{fontSize: 19, fontWeight: 900, color: isActive ? '#efc66f' : '#b9c2bf'}}>{item.date}</div>
              <div style={{fontSize: 25, fontWeight: 900, marginTop: 5}}>{item.title}</div>
              <div style={{fontSize: 15, lineHeight: 1.45, color: '#cbd1cf', marginTop: 7}}>{item.detail}</div>
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', left: 38, right: 38, bottom: 38, fontSize: 14, lineHeight: 1.5, color: '#9ba6a3'}}>
        圆点、路线和数字均与数据合同绑定。虚线表示关系/方向示意，不等同于逐日行军轨迹。
      </div>
    </div>
  );
};

const SourceLedger: React.FC<{frame: number}> = ({frame}) => {
  const opacity = fade(frame, 2070, 2400, 30);
  const tiers = [
    ['A级', '批注影印或可追原始记录', 'S1'],
    ['B级', '档案/口述研究与交叉解释', 'S2 · S6'],
    ['C级', '事后官方、审判或批判材料', 'S3 · S4 · S5'],
  ];
  return (
    <div
      style={{
        position: 'absolute',
        left: 54,
        top: 174,
        width: 1400,
        height: 790,
        opacity,
        background: 'rgba(232,224,207,0.985)',
        padding: '58px 70px',
        boxSizing: 'border-box',
      }}
    >
      <div style={{fontSize: 24, fontWeight: 900, color: COLORS.militia}}>剩余风险与史料边界</div>
      <div style={{fontSize: 48, fontWeight: 950, lineHeight: 1.15, marginTop: 10}}>知道什么，也标出不知道什么</div>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 70, marginTop: 54}}>
        <div>
          {tiers.map(([tier, label, ids]) => (
            <div key={tier} style={{display: 'grid', gridTemplateColumns: '84px 1fr', gap: 18, marginBottom: 24}}>
              <div style={{fontSize: 22, fontWeight: 950, color: COLORS.white, background: COLORS.ink, padding: '8px 11px', height: 42, boxSizing: 'border-box'}}>{tier}</div>
              <div>
                <div style={{fontSize: 22, fontWeight: 850}}>{label}</div>
                <div style={{fontSize: 17, color: COLORS.muted, marginTop: 4}}>{ids}</div>
              </div>
            </div>
          ))}
        </div>
        <div style={{fontSize: 21, lineHeight: 1.7}}>
          <div style={{borderLeft: `6px solid ${COLORS.militia}`, paddingLeft: 18, marginBottom: 22}}>
            <b>人员：</b>只确认全市2,500人集中、31,000人待命；不把33,500人塞进一个指挥部。
          </div>
          <div style={{borderLeft: `6px solid ${COLORS.suppression}`, paddingLeft: 18, marginBottom: 22}}>
            <b>弹压军：</b>60军、东海舰队与警备区的公开分项人数不足，故只画方向/关系。
          </div>
          <div style={{borderLeft: `6px solid ${COLORS.gold}`, paddingLeft: 18}}>
            <b>训令：</b>“准备接受严重考验”保留，但注明原始手令未见，避免把转述升级为原件。
          </div>
        </div>
      </div>
      <div style={{position: 'absolute', bottom: 50, left: 70, right: 70, borderTop: `2px solid ${COLORS.road}`, paddingTop: 18, fontSize: 16, color: COLORS.muted}}>
        完整URL、来源说明、坐标与数字均保存在 src/data.json；地图为历史态势示意，不是精确测绘成果。
      </div>
    </div>
  );
};

export const Shanghai1976: React.FC = () => {
  const frame = useCurrentFrame();
  const introOpacity = fade(frame, 0, 190, 35);
  const mapOpacity = interpolate(frame, [125, 205], [0, 1], clamp);
  const textureScale = 1.03 + frame / 240000;

  return (
    <AbsoluteFill style={{background: COLORS.paper, color: COLORS.ink, fontFamily: 'Microsoft YaHei, Noto Sans CJK SC, sans-serif', overflow: 'hidden'}}>
      <Img
        src={staticFile('assets/archive-paper.png')}
        style={{
          position: 'absolute',
          inset: -25,
          width: 1970,
          height: 1130,
          objectFit: 'cover',
          opacity: 0.22,
          mixBlendMode: 'multiply',
          transform: `scale(${textureScale})`,
        }}
      />

      <div style={{opacity: mapOpacity}}>
        <div style={{position: 'absolute', left: 54, top: 44, width: 1380, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between'}}>
          <div>
            <div style={{fontSize: 52, lineHeight: 1, fontWeight: 950, letterSpacing: 0}}>1976年10月 上海敌我形势</div>
            <div style={{fontSize: 20, color: COLORS.muted, marginTop: 14}}>兵力、武器与指挥节点的史料分层重建</div>
          </div>
          <div style={{fontSize: 16, color: COLORS.muted, textAlign: 'right', lineHeight: 1.5}}>
            红：民兵武装　蓝：走资派弹压军<br />
            虚线：争议/关系/方向示意
          </div>
        </div>
        <BaseMap frame={frame} />
        <Instruction frame={frame} />
        <ForceSummary frame={frame} />
        <OfficialLedger frame={frame} />
        <DisputedNodes frame={frame} />
        <RegionalInset frame={frame} />
        <TakeoverBand frame={frame} />
        <SourceLedger frame={frame} />
        <Timeline frame={frame} />
      </div>

      <div
        style={{
          position: 'absolute',
          inset: 0,
          opacity: introOpacity,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          textAlign: 'center',
          background: 'rgba(232,224,207,0.92)',
        }}
      >
        <div style={{fontSize: 22, fontWeight: 900, color: COLORS.militia}}>史料分层 · 确定性地图动画</div>
        <div style={{fontSize: 80, lineHeight: 1.1, fontWeight: 950, marginTop: 18}}>1976年10月<br />上海敌我形势</div>
        <div style={{fontSize: 23, color: COLORS.muted, marginTop: 28}}>数字有出处 · 未知不补写 · 路线标明性质</div>
      </div>
    </AbsoluteFill>
  );
};

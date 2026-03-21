# 股票智能预警系统 - 技术规格说明书

## 一、项目概述

股票智能预警系统是一个集实时行情监控、技术指标分析、智能预警通知于一体的综合性股票交易辅助系统。系统能够同时监控多只股票（默认3只），基于多种技术指标进行趋势判断，自动识别买卖点，预测顶部和底部，并在满足预警条件时及时通知用户。

## 二、核心功能

### 2.1 实时行情监控
- 同时监控3只股票（AAPL、TSLA、MSFT）
- 实时价格每5秒更新
- 显示涨跌幅、成交量等关键指标

### 2.2 技术指标计算
支持以下技术指标：
- MA（移动平均线）：5/10/20/60日
- MACD：12/26/9参数
- KDJ：9日周期
- RSI：6/12/24日周期
- 布林带：20日周期，2倍标准差

### 2.3 智能买卖点判断
采用多指标融合评分机制：
- 高级信号：评分≥60且条件≥3个
- 中级信号：评分≥40且条件≥2个
- 低级信号：评分≥20

### 2.4 顶部底部预测
基于以下模型进行预测：
- 背离检测（MACD底背离/顶背离）
- RSI超买超卖判断
- 布林带极端位置检测
- KDJ极端值检测

### 2.5 预警通知系统
- 右侧滑出预警面板
- 支持标记已读、清空等操作
- 预警去重机制（24小时）

## 三、技术架构

### 3.1 技术栈
- 前端框架：React 18 + TypeScript
- UI组件库：Ant Design 5
- 图表库：TradingView Lightweight Charts
- 状态管理：React hooks
- 构建工具：Vite 5

### 3.2 项目结构
```
stock-alert-system/
├── src/
│   ├── components/     # React组件
│   ├── services/       # 业务服务
│   │   ├── stockService.ts      # 股票数据服务
│   │   ├── alertService.ts       # 预警服务
│   │   └── indicatorService.ts   # 指标服务
│   ├── utils/          # 工具函数
│   │   ├── indicators.ts         # 技术指标计算
│   │   ├── signals.ts           # 买卖信号检测
│   │   └── prediction.ts        # 顶底预测
│   ├── types/          # TypeScript类型定义
│   ├── App.tsx         # 主应用组件
│   └── App.css         # 样式文件
├── package.json
├── tsconfig.json
├── vite.config.ts
└── SPEC.md
```

## 四、数据库设计

### 4.1 数据模型

```typescript
interface StockData {
  symbol: string;          // 股票代码
  name: string;           // 股票名称
  price: number;         // 当前价格
  change: number;         // 涨跌额
  changePercent: number;  // 涨跌幅
  volume: number;         // 成交量
  open: number;          // 开盘价
  high: number;          // 最高价
  low: number;           // 最低价
  timestamp: number;      // 更新时间戳
}

interface TechnicalIndicators {
  ma5: number;
  ma10: number;
  ma20: number;
  ma60: number;
  macdDif: number;
  macdDea: number;
  macdHistogram: number;
  kdjK: number;
  kdjD: number;
  kdjJ: number;
  rsi6: number;
  rsi12: number;
  rsi24: number;
  bollUp: number;
  bollMb: number;
  bollDn: number;
}

interface Alert {
  id: string;
  symbol: string;
  type: 'buy' | 'sell' | 'top' | 'bottom';
  level: 'high' | 'medium' | 'low';
  price: number;
  score: number;
  reasons: string[];
  timestamp: number;
  read: boolean;
  message: string;
}
```

## 五、核心算法

### 5.1 技术指标计算

#### MA（移动平均线）
```typescript
MA(N) = Σ(收盘价) / N
```

#### MACD
```typescript
EMA(12) = 前一日EMA × (11/13) + 今日收盘价 × (2/13)
EMA(26) = 前一日EMA × (25/27) + 今日收盘价 × (2/27)
DIF = EMA(12) - EMA(26)
DEA = DIF的9日EMA
MACD = (DIF - DEA) × 2
```

#### KDJ
```typescript
RSV(N) = (Cn - Ln) / (Hn - Ln) × 100
K = 2/3 × 前日K + 1/3 × 今日RSV
D = 2/3 × 前日D + 1/3 × 今日K
J = 3K - 2D
```

#### RSI
```typescript
RSI = 100 - (100 / (1 + RS))
RS = 平均涨幅 / 平均跌幅
```

### 5.2 买卖信号检测

#### 买入信号条件
1. MACD金叉 + 20分
2. KDJ低位金叉 + 20分
3. RSI超卖反弹 + 15分
4. 均线金叉 + 15分
5. 成交量放大 + 15分
6. 布林带下轨反弹 + 10分

#### 卖出信号条件
1. MACD死叉 + 20分
2. KDJ高位死叉 + 20分
3. RSI超买回落 + 15分
4. 均线死叉 + 15分
5. 成交量萎缩/顶部放量 + 15分
6. 布林带上轨回落 + 10分

### 5.3 顶底预测算法

| 预测因素 | 权重 | 条件 |
|---------|------|------|
| MACD背离 | 30分 | 价格与MACD走势背离 |
| RSI超买超卖 | 20分 | RSI>80或RSI<20 |
| 布林带极端位置 | 15分 | 价格突破上下轨 |
| KDJ极端值 | 10分 | KDJ_J>100或KDJ_J<0 |

总分≥50判定为有效顶底信号。

## 六、界面设计

### 6.1 颜色方案
- 主色：#1890ff（科技蓝）
- 上涨色：#52c41a（翠绿色）
- 下跌色：#ff4d4f（警示红）
- 预警高级：#ff4d4f
- 预警中级：#faad14
- 预警低级：#1890ff
- 背景色：#0f1419（深色背景）
- 卡片背景：#1a1f2e

### 6.2 页面布局
1. 顶部导航栏：Logo、标题、时间、预警按钮
2. 监控区域：3只股票卡片网格布局
3. 详情区域：K线图表 + 技术指标面板
4. 预警面板：右侧滑出，显示预警列表

## 七、开发计划

### Phase 1：基础框架（已完成）
- React + TypeScript项目搭建
- Vite构建配置
- 基础组件结构

### Phase 2：数据层（已完成）
- 股票数据模型定义
- 模拟数据生成服务
- 技术指标计算引擎

### Phase 3：功能模块（已完成）
- 股票监控组件
- K线图表集成
- 技术指标面板
- 预警通知系统

### Phase 4：优化部署（进行中）
- 性能优化
- UI细节调整
- 部署上线

## 八、验收标准

- [x] 系统可同时监控3只股票
- [x] 实时价格每5秒更新
- [x] 技术指标正确计算（MA、MACD、KDJ、RSI、BOLL）
- [x] 买卖信号正确识别并分级
- [x] 顶底预测功能正常工作
- [x] 预警通知正确显示
- [x] K线图表正确渲染

## 九、作者

MiniMax Agent

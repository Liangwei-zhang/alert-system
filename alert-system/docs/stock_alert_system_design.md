# 股票智能预警系统设计方案

## 一、系统概述

股票智能预警系统是一个集实时行情监控、技术指标分析、智能预警通知于一体的综合性股票交易辅助系统。系统能够同时监控多只股票（默认3只），基于多种技术指标进行趋势判断，自动识别买卖点，预测顶部和底部，并在满足预警条件时及时通知用户。

### 核心特性
- **多股票并行监控**：同时监控3只股票，独立预警互不干扰
- **智能买卖点识别**：基于多指标融合的买卖点判断算法
- **顶底预测功能**：运用技术分析模型预测阶段性顶部和底部
- **实时预警推送**：WebSocket实时监控，多渠道预警通知
- **可视化分析**：交互式K线图表，技术指标可视化展示

---

## 二、功能需求分析

### 2.1 核心功能模块

#### 2.1.1 实时行情监控
- **数据获取频率**：1分钟级实时数据（盘中），日线数据（历史分析）
- **监控股票数量**：支持同时监控3只股票
- **数据内容**：开盘价、收盘价、最高价、最低价、成交量、成交额

#### 2.1.2 技术指标计算引擎
支持以下技术指标的实时计算：

| 指标类型 | 指标名称 | 计算周期 | 主要用途 |
|---------|---------|---------|---------|
| 趋势类 | MA（移动平均线） | 5/10/20/60日 | 趋势判断、支撑压力 |
| 趋势类 | MACD | 12/26/9 | 买卖信号、趋势确认 |
| 趋势类 | BOLL（布林带） | 20日 | 波动范围、超买超卖 |
| 摆动类 | RSI | 6/12/24日 | 超买超卖判断 |
| 摆动类 | KDJ | 9日 | 短期买卖信号 |
| 能量类 | VOL（成交量） | - | 量价配合分析 |

#### 2.1.3 智能买卖点判断
采用**多指标融合决策机制**，综合以下因素：
- MACD金叉/死叉信号
- KDJ超买超卖区域
- RSI强弱判断
- 均线多头/空头排列
- 成交量放量/缩量确认
- 布林带突破信号

#### 2.1.4 顶部底部预测
基于以下模型进行预测：
- **背离分析**：价格与指标（MACD/RSI/KDJ）的背离
- **形态识别**：W底、M顶、头肩顶底等经典形态
- **波动率分析**：布林带收缩与扩张
- **量价关系**：顶部放量、底部缩量特征

#### 2.1.5 阶段性买卖建议
- **短线建议**（1-3天）：基于KDJ、RSI等快速指标
- **中线建议**（5-10天）：基于MACD、均线系统
- **长线建议**（30天以上）：基于趋势线、重要支撑压力位

#### 2.1.6 多股票预警机制
- **独立监控**：每只股票独立计算指标和预警条件
- **优先级管理**：根据预警级别（高/中/低）排序通知
- **预警去重**：同一股票相同条件24小时内不重复预警
- **预警历史**：记录所有预警信息，便于回测分析

### 2.2 预警触发条件

#### 2.2.1 买入预警条件
```
高优先级买入信号（需满足3个以上条件）：
1. MACD金叉（DIF上穿DEA）且MACD柱由负转正
2. KDJ指标从超卖区（<20）向上金叉
3. RSI从超卖区（<30）反弹向上
4. 股价站上5日均线，且5日线上穿10日线
5. 成交量放大（>5日均量1.5倍）
6. 股价触及布林带下轨后反弹

中优先级买入信号（需满足2个条件）：
1. MACD绿柱缩短
2. KDJ指标在低位（<50）形成二次金叉
3. 股价回调至20日均线获得支撑
```

#### 2.2.2 卖出预警条件
```
高优先级卖出信号（需满足3个以上条件）：
1. MACD死叉（DIF下穿DEA）且MACD柱由正转负
2. KDJ指标从超买区（>80）向下死叉
3. RSI进入超买区（>70）并开始回落
4. 股价跌破5日均线，且5日线下穿10日线
5. 成交量萎缩（<5日均量0.7倍）或顶部放量
6. 股价触及布林带上轨后回落

中优先级卖出信号（需满足2个条件）：
1. MACD红柱缩短
2. KDJ指标在高位（>50）形成二次死叉
3. 股价遇到重要阻力位（前期高点、整数关口）
```

#### 2.2.3 顶部预警条件
```
潜在顶部信号：
1. 价格创新高但MACD/RSI不创新高（顶背离）
2. 股价触及布林带上轨外侧
3. RSI>80持续3天以上
4. 出现M顶或头肩顶形态
5. 成交量急剧放大后快速萎缩
```

#### 2.2.4 底部预警条件
```
潜在底部信号：
1. 价格创新低但MACD/RSI不创新低（底背离）
2. 股价触及布林带下轨外侧
3. RSI<20持续3天以上
4. 出现W底或头肩底形态
5. 成交量持续萎缩后开始温和放量
```

---

## 三、技术架构设计

### 3.1 系统架构概览

系统采用**前后端分离**架构，**微服务**设计思想，确保高性能、高可用、易扩展。

```
┌─────────────────────────────────────────────────────────────┐
│                        用户层                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │Web浏览器 │  │移动端APP │  │Telegram  │  │  邮件    │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS / WebSocket
┌────────────────────┴────────────────────────────────────────┐
│                      前端应用层                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  React/Vue前端应用 + Plotly.js图表可视化               │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────┬────────────────────────────────────────┘
                     │ RESTful API / WebSocket
┌────────────────────┴────────────────────────────────────────┐
│                      API网关层                                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Nginx / API Gateway（路由、鉴权、限流、负载均衡）    │ │
│  └────────────────────────────────────────────────────────┘ │
└──┬──────────────┬──────────────┬──────────────┬────────────┘
   │              │              │              │
┌──┴────┐  ┌─────┴─────┐  ┌────┴─────┐  ┌────┴─────────┐
│用户服务│  │行情数据服务│  │指标计算  │  │ 预警通知服务 │
│ User  │  │  Market   │  │服务      │  │Alert Service│
│Service│  │  Service  │  │Indicator │  │             │
└──┬────┘  └─────┬─────┘  │Service   │  └────┬─────────┘
   │              │        └────┬─────┘       │
   │              │             │             │
┌──┴──────────────┴─────────────┴─────────────┴───────────────┐
│                      数据访问层                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │PostgreSQL│  │   Redis  │  │TimeSeries│  │ MongoDB  │    │
│  │用户/配置 │  │   缓存   │  │  DB      │  │预警日志  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└──────────────────────┬────────────────────────────────────┘
                       │
┌──────────────────────┴────────────────────────────────────┐
│                   外部数据源层                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Yahoo     │  │Alpha     │  │Finnhub   │  │  Tushare │  │
│  │Finance   │  │Vantage   │  │API       │  │  Pro     │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└───────────────────────────────────────────────────────────┘
```

### 3.2 核心模块设计

#### 3.2.1 用户服务（User Service）
**职责**：
- 用户注册、登录、认证、授权
- 用户配置管理（监控股票列表、预警设置）
- 订阅管理（通知渠道绑定）

**技术栈**：
- 框架：Flask/FastAPI (Python) 或 Express (Node.js)
- 认证：JWT + Redis会话管理
- 数据库：PostgreSQL

#### 3.2.2 行情数据服务（Market Data Service）
**职责**：
- 实时股票行情数据获取
- 历史数据获取与存储
- 数据清洗与标准化
- 数据缓存管理

**技术栈**：
- 数据源API：Yahoo Finance (yfinance)、Alpha Vantage、Finnhub、Tushare Pro
- 数据存储：TimescaleDB（时序数据库）
- 缓存：Redis（实时行情）
- 数据更新：WebSocket连接（盘中）+ 定时任务（盘后）

**数据获取策略**：
```python
# 实时数据（盘中）- 1分钟更新
WebSocket连接 → 实时推送 → Redis缓存 → 业务服务

# 历史数据（盘后）- 每日更新
定时任务(cron) → REST API调用 → TimescaleDB持久化

# 数据备份
主数据源故障 → 自动切换备用数据源
```

#### 3.2.3 技术指标计算服务（Indicator Service）
**职责**：
- 技术指标实时计算（MA、MACD、KDJ、RSI、BOLL等）
- 指标数据缓存
- 批量计算优化

**技术栈**：
- 计算引擎：Pandas + TA-Lib (Python技术分析库)
- 缓存：Redis（计算结果缓存，减少重复计算）
- 并发处理：Celery异步任务队列

**计算流程**：
```
行情数据更新 → 触发指标计算任务 → Celery异步计算
→ 结果写入Redis → 通知预警服务检查条件
```

#### 3.2.4 预警通知服务（Alert Service）
**职责**：
- 预警条件持续监控
- 预警规则引擎
- 多渠道通知推送（Web、Telegram、邮件、短信）
- 预警历史记录

**技术栈**：
- 规则引擎：基于条件表达式的规则匹配
- 后台任务：独立线程/进程持续监控
- 通知渠道：
  - Telegram Bot API（Webhook模式）
  - SendGrid/阿里云邮件服务
  - WebSocket推送（前端实时通知）
- 日志存储：MongoDB（预警历史）

**预警流程**：
```
后台监控线程 → 每60秒检查一次 → 按股票分组查询Redis指标数据
→ 规则引擎匹配预警条件 → 满足条件生成预警
→ 检查去重规则 → 多渠道推送 → 记录预警日志
```

### 3.3 前端架构设计

#### 3.3.1 技术栈
- **框架**：React 18 + TypeScript
- **状态管理**：Redux Toolkit / Zustand
- **UI组件库**：Ant Design / Material-UI
- **图表库**：
  - TradingView Lightweight Charts（专业K线图）
  - Plotly.js（技术指标图表）
  - ECharts（数据可视化）
- **实时通信**：Socket.IO (WebSocket客户端)
- **HTTP客户端**：Axios

#### 3.3.2 页面结构
```
├── Dashboard（仪表盘）
│   ├── 监控股票列表（3只股票卡片）
│   ├── 实时预警提示（顶部通知栏）
│   └── 关键指标概览
│
├── Stock Detail（股票详情页）
│   ├── K线图表（支持缩放、指标叠加）
│   ├── 技术指标面板（MACD、KDJ、RSI、BOLL）
│   ├── 买卖点标注
│   ├── 预警设置面板
│   └── 历史预警记录
│
├── Alert Management（预警管理）
│   ├── 预警规则配置
│   ├── 预警历史查询
│   └── 通知渠道设置
│
└── User Settings（用户设置）
    ├── 监控股票管理
    ├── Telegram绑定
    └── 偏好设置
```

#### 3.3.3 实时数据更新机制
```javascript
// WebSocket连接
const socket = io('wss://api.example.com', {
  auth: { token: userToken }
});

// 订阅股票实时数据
socket.emit('subscribe', { symbols: ['AAPL', 'TSLA', 'MSFT'] });

// 接收实时行情
socket.on('market_data', (data) => {
  updateStockPrice(data);
  updateChart(data);
});

// 接收预警通知
socket.on('alert', (alert) => {
  showNotification(alert);
  updateAlertList(alert);
});
```

### 3.4 后端技术栈详细选择

#### 3.4.1 开发语言与框架
**推荐方案一：Python生态**
```
- 语言：Python 3.10+
- Web框架：FastAPI（高性能、异步支持、自动API文档）
- 异步任务：Celery + Redis
- 数据处理：Pandas、NumPy
- 技术分析：TA-Lib
```

**推荐方案二：Node.js生态**
```
- 语言：TypeScript + Node.js 18+
- Web框架：NestJS（企业级框架、模块化）
- 异步任务：Bull + Redis
- 数据处理：technicalindicators库
```

**建议**：Python生态更适合金融数据分析，TA-Lib库成熟稳定，推荐使用方案一。

#### 3.4.2 数据库选型
| 数据库类型 | 选择方案 | 用途 |
|-----------|---------|------|
| 关系型数据库 | PostgreSQL 14+ | 用户数据、配置信息 |
| 时序数据库 | TimescaleDB（基于PostgreSQL） | 股票历史行情数据 |
| 缓存数据库 | Redis 7+ | 实时行情、指标计算结果、会话 |
| 文档数据库 | MongoDB 6+ | 预警日志、非结构化数据 |

#### 3.4.3 消息队列与任务调度
- **消息队列**：Redis + Celery
- **任务类型**：
  - 定时任务：每日盘后数据同步
  - 实时任务：指标计算、预警检测
  - 批量任务：历史数据回测

#### 3.4.4 部署方案
```
开发环境：
- Docker Compose（容器化部署）
- 本地PostgreSQL + Redis

生产环境：
- 容器编排：Kubernetes / Docker Swarm
- 云服务商：AWS / 阿里云 / 腾讯云
- 负载均衡：Nginx / AWS ALB
- 数据库：
  - PostgreSQL: AWS RDS / 阿里云RDS
  - Redis: AWS ElastiCache / 阿里云Redis
- 监控：Prometheus + Grafana
- 日志：ELK Stack (Elasticsearch + Logstash + Kibana)
```

---

## 四、数据源方案

### 4.1 数据源对比

| 数据源 | 免费额度 | 实时性 | 覆盖市场 | WebSocket | 推荐度 |
|-------|---------|-------|---------|-----------|--------|
| Yahoo Finance | 免费无限制 | 延迟15分钟 | 全球主要市场 | 否 | ⭐⭐⭐⭐ |
| Alpha Vantage | 5次/分钟 | 实时 | 美股/外汇/加密货币 | 否 | ⭐⭐⭐ |
| Finnhub | 60次/分钟（免费） | 实时 | 全球股市 | 是 | ⭐⭐⭐⭐⭐ |
| Twelve Data | 800次/日（免费） | 实时 | 全球 | 是 | ⭐⭐⭐⭐ |
| Tushare Pro | 积分制 | T+1 | A股 | 否 | ⭐⭐⭐（A股首选） |

### 4.2 推荐方案

#### 4.2.1 美股/全球市场
**主数据源**：Finnhub（免费额度足够个人使用）
```python
import websocket
import json

# WebSocket实时数据
ws_url = "wss://ws.finnhub.io?token=YOUR_API_KEY"

def on_message(ws, message):
    data = json.loads(message)
    # 处理实时行情数据

ws = websocket.WebSocketApp(ws_url, on_message=on_message)
```

**备用数据源**：Yahoo Finance（历史数据）
```python
import yfinance as yf

# 获取历史数据
ticker = yf.Ticker("AAPL")
hist = ticker.history(period="1mo", interval="1d")
```

#### 4.2.2 A股市场
**主数据源**：Tushare Pro
```python
import tushare as ts

ts.set_token('YOUR_TOKEN')
pro = ts.pro_api()

# 获取日线数据
df = pro.daily(ts_code='000001.SZ', start_date='20240101', end_date='20240319')
```

### 4.3 数据更新频率

| 数据类型 | 更新频率 | 更新方式 |
|---------|---------|---------|
| 实时行情（盘中） | 60秒 | WebSocket推送/轮询 |
| 分钟K线 | 1分钟 | API轮询 |
| 日线数据 | 每日盘后 | 定时任务（凌晨1点） |
| 技术指标 | 行情更新后 | 异步计算 |

### 4.4 数据存储策略

```sql
-- TimescaleDB表结构示例
CREATE TABLE stock_daily (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open NUMERIC(10, 2),
    high NUMERIC(10, 2),
    low NUMERIC(10, 2),
    close NUMERIC(10, 2),
    volume BIGINT,
    PRIMARY KEY (time, symbol)
);

-- 创建超表（时序数据优化）
SELECT create_hypertable('stock_daily', 'time');

-- 创建索引
CREATE INDEX idx_symbol ON stock_daily (symbol, time DESC);
```

---

## 五、预警机制设计

### 5.1 预警级别分类

| 级别 | 颜色标识 | 触发条件 | 通知方式 |
|-----|---------|---------|---------|
| 🔴 高级 | 红色 | 强烈买入/卖出信号（≥3个条件） | WebSocket+Telegram+邮件 |
| 🟡 中级 | 黄色 | 中等信号（2个条件） | WebSocket+Telegram |
| 🔵 低级 | 蓝色 | 参考信号（1个条件） | 仅WebSocket |
| ⚪ 信息 | 灰色 | 指标提示 | 仅界面显示 |

### 5.2 预警触发流程

```
┌─────────────────────────────────────────────────┐
│  1. 行情数据更新（每60秒）                       │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────┐
│  2. 触发指标计算任务（Celery异步）               │
│     - 计算MACD、KDJ、RSI、BOLL、MA               │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────┐
│  3. 预警规则引擎检查                             │
│     - 遍历用户监控的3只股票                      │
│     - 对每只股票应用预警规则                     │
└──────────────────┬──────────────────────────────┘
                   │
          ┌────────┴────────┐
          │  条件满足？      │
          └────┬───────┬────┘
              是│      │否
    ┌───────────┴┐    └──────────────┐
    │  4. 生成预警│              结束  │
    └───────┬────┘                    │
            │                         │
┌───────────┴────────────────────┐    │
│  5. 检查去重规则                │    │
│     - 相同股票+条件24h内不重复  │    │
└───────────┬────────────────────┘    │
            │                         │
   ┌────────┴────────┐                │
   │  是否重复？      │                │
   └────┬───────┬────┘                │
       是│      │否                    │
   ┌────┴┐  ┌──┴───────────────────┐ │
   │ 丢弃│  │ 6. 多渠道推送         │ │
   └─────┘  │    - WebSocket        │ │
            │    - Telegram         │ │
            │    - Email            │ │
            └──────┬────────────────┘ │
                   │                  │
            ┌──────┴──────────────────┴──┐
            │  7. 记录预警日志到MongoDB  │
            └────────────────────────────┘
```

### 5.3 预警去重机制

```python
# Redis去重键设计
def get_alert_key(symbol: str, alert_type: str, level: str) -> str:
    """生成预警去重键"""
    return f"alert:{symbol}:{alert_type}:{level}"

# 检查是否重复预警
def is_duplicate_alert(symbol: str, alert_type: str, level: str) -> bool:
    key = get_alert_key(symbol, alert_type, level)
    exists = redis_client.exists(key)
    if not exists:
        # 设置24小时过期
        redis_client.setex(key, 86400, "1")
        return False
    return True
```

### 5.4 通知推送实现

#### 5.4.1 WebSocket推送
```python
# 服务端推送
async def send_alert_to_user(user_id: int, alert: dict):
    await sio.emit('alert', alert, room=f'user_{user_id}')
```

#### 5.4.2 Telegram推送
```python
import requests

def send_telegram_message(chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    requests.post(url, json=payload)

# 预警消息模板
message = f"""
🔴 *高级买入信号*
股票：{symbol}
价格：${price}
信号：
✅ MACD金叉
✅ KDJ超卖反弹
✅ RSI<30回升
时间：{timestamp}
"""
```

#### 5.4.3 邮件推送
```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_email_alert(to_email: str, alert: dict):
    message = Mail(
        from_email='alert@stocksystem.com',
        to_emails=to_email,
        subject=f"股票预警：{alert['symbol']}",
        html_content=render_alert_html(alert)
    )
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(message)
```

---

（继续下一部分：核心算法设计）

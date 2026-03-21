import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  ConfigProvider, theme, Layout, Row, Col, Card,
  Typography, Tag, Badge, Button, Empty, Tooltip, Spin,
} from 'antd';
import {
  BellOutlined, CloseOutlined, CheckOutlined, DeleteOutlined,
  ArrowUpOutlined, ArrowDownOutlined, WifiOutlined, DisconnectOutlined,
  PlusOutlined, DeleteFilled,
} from '@ant-design/icons';
import { createChart, IChartApi, ISeriesApi, CandlestickData, LineData, Time } from 'lightweight-charts';
import { alertService }     from './services/alertService';
import { indicatorService } from './services/indicatorService';
import { stockService }     from './services/stockService';
import { SearchModal }      from './components/SearchModal';
import { assetTypeLabel, assetTypeColor } from './services/searchService';
import { StockData, SignalResult, Alert, WatchlistItem, DataSource } from './types';
import './App.css';

const { Content, Header } = Layout;
const { Title, Text }     = Typography;

const UPDATE_MS = 20_000;

// ─── 数据源标识 ───────────────────────────────────────────────────────────────

const SOURCE_CONFIG: Record<DataSource, { label: string; color: string; dot: string }> = {
  real:      { label: '实时',   color: '#52c41a', dot: '🟢' },
  database:  { label: '缓存',   color: '#faad14', dot: '🟡' },
  simulated: { label: '模拟',   color: '#8b949e', dot: '⚪' },
};

// ─── App ──────────────────────────────────────────────────────────────────────

const App: React.FC = () => {
  const [initialized,    setInitialized]    = useState(false);
  const [selectedStock,  setSelectedStock]  = useState<string>('');
  const [alertVisible,   setAlertVisible]   = useState(false);
  const [searchVisible,  setSearchVisible]  = useState(false);
  const [refreshKey,     setRefreshKey]     = useState(0);
  const [stocks,         setStocks]         = useState<
    { stock: StockData; buy?: SignalResult; sell?: SignalResult; source: DataSource }[]
  >([]);
  const [watchlistItems, setWatchlistItems] = useState<WatchlistItem[]>([]);
  const [chartContainer, setChartContainer] = useState<HTMLDivElement | null>(null);
  const [chart,          setChart]          = useState<IChartApi | null>(null);
  const [candleSeries,   setCandleSeries]   = useState<ISeriesApi<'Candlestick'> | null>(null);
  const [ma5S,           setMa5S]           = useState<ISeriesApi<'Line'> | null>(null);
  const [ma10S,          setMa10S]          = useState<ISeriesApi<'Line'> | null>(null);
  const [ma20S,          setMa20S]          = useState<ISeriesApi<'Line'> | null>(null);

  const [alerts,         setAlerts]         = useState<Alert[]>([]);
  const [unreadCount,    setUnreadCount]     = useState(0);
  const [currentTime,    setCurrentTime]     = useState(() => new Date());

  // 注册 alertService 回调
  useEffect(() => {
    const sync = () => {
      setAlerts([...alertService.getAlerts()]);
      setUnreadCount(alertService.getUnreadCount());
    };
    alertService.setOnChange(sync);
    return () => alertService.setOnChange(() => {});
  }, []);

  // 时钟
  useEffect(() => {
    const t = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // ─── 初始化（仅一次） ────────────────────────────────────────────────────────

  useEffect(() => {
    stockService.init().then(() => {
      const wl = stockService.getWatchlist();
      setWatchlistItems(wl);
      if (wl.length > 0 && !selectedStock) setSelectedStock(wl[0].symbol);
      setInitialized(true);
    });
  }, []);

  // ─── UI 数据同步 ─────────────────────────────────────────────────────────────

  const updateUI = useCallback(() => {
    indicatorService.invalidateCache();
    const wl = stockService.getWatchlist();
    setWatchlistItems(wl);

    const raw = stockService.getStocks();
    setStocks(raw.map(s => ({
      stock: s,
      buy:   indicatorService.getBuySignal(s.symbol),
      sell:  indicatorService.getSellSignal(s.symbol),
      source: stockService.getSymbolMeta(s.symbol).source,
    })));

    // 批量预警
    for (const sym of stockService.getAvailableStocks()) {
      const a = indicatorService.analyzeStock(sym);
      if (!a) continue;
      if (a.buySignal.signal)  alertService.createAlert(a, 'buy',    a.buySignal);
      if (a.sellSignal.signal) alertService.createAlert(a, 'sell',   a.sellSignal);
      if (a.prediction.type !== 'neutral') {
        alertService.createAlert(a, a.prediction.type, {
          signal:  true,
          level:   a.prediction.probability > 0.7 ? 'high' : 'medium',
          score:   Math.round(a.prediction.probability * 100),
          reasons: a.prediction.signals,
        });
      }
    }
    alertService.flush();
    setRefreshKey(k => k + 1);
  }, []);

  // ─── 轮询（initialized 后启动）───────────────────────────────────────────────

  useEffect(() => {
    if (!initialized) return;
    updateUI();
    let mounted = true;
    const tick = async () => {
      await stockService.updateStocks();
      if (mounted) updateUI();
    };
    const id = setInterval(tick, UPDATE_MS);
    return () => { mounted = false; clearInterval(id); };
  }, [initialized, updateUI]);

  // ─── 图表初始化 ───────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!chartContainer) return;
    const nc = createChart(chartContainer, {
      layout: { background: { color: '#0f1419' }, textColor: '#8b949e' },
      grid:   { vertLines: { color: 'rgba(255,255,255,0.05)' }, horzLines: { color: 'rgba(255,255,255,0.05)' } },
      timeScale: { borderColor: 'rgba(255,255,255,0.1)', timeVisible: true },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
    });
    const cs  = nc.addCandlestickSeries({ upColor: '#52c41a', downColor: '#ff4d4f', borderUpColor: '#52c41a', borderDownColor: '#ff4d4f', wickUpColor: '#52c41a', wickDownColor: '#ff4d4f' });
    const m5  = nc.addLineSeries({ color: '#1890ff', lineWidth: 1, title: 'MA5' });
    const m10 = nc.addLineSeries({ color: '#faad14', lineWidth: 1, title: 'MA10' });
    const m20 = nc.addLineSeries({ color: '#722ed1', lineWidth: 1, title: 'MA20' });
    setChart(nc); setCandleSeries(cs); setMa5S(m5); setMa10S(m10); setMa20S(m20);
    const onResize = () => nc.applyOptions({ width: chartContainer.clientWidth, height: 400 });
    window.addEventListener('resize', onResize);
    onResize();
    return () => { window.removeEventListener('resize', onResize); nc.remove(); };
  }, [chartContainer]);

  // ─── K 线更新 ─────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!chart || !candleSeries || !selectedStock) return;
    const kd = stockService.getKLineData(selectedStock);
    if (!kd.length) return;
    candleSeries.setData(kd.map(d => ({ time: d.time as Time, open: d.open, high: d.high, low: d.low, close: d.close })) as CandlestickData[]);
    const cls = kd.map(d => d.close);
    const m5d: LineData[] = [], m10d: LineData[] = [], m20d: LineData[] = [];
    for (let i = 0; i < kd.length; i++) {
      const t = kd[i].time as Time;
      if (i >= 4)  m5d .push({ time: t, value: cls.slice(i-4,  i+1).reduce((a,b)=>a+b)/5  });
      if (i >= 9)  m10d.push({ time: t, value: cls.slice(i-9,  i+1).reduce((a,b)=>a+b)/10 });
      if (i >= 19) m20d.push({ time: t, value: cls.slice(i-19, i+1).reduce((a,b)=>a+b)/20 });
    }
    ma5S?.setData(m5d); ma10S?.setData(m10d); ma20S?.setData(m20d);
    chart.timeScale().fitContent();
  }, [selectedStock, refreshKey, chart, candleSeries, ma5S, ma10S, ma20S]);

  // ─── 添加 / 移除 symbol ──────────────────────────────────────────────────────

  const handleAdd = useCallback(async (result: { symbol: string; name: string; assetType: any; exchange: string }) => {
    const item: WatchlistItem = {
      symbol:    result.symbol,
      name:      result.name,
      addedAt:   Date.now(),
      assetType: result.assetType,
      exchange:  result.exchange,
    };
    await stockService.addSymbol(item);
    const wl = stockService.getWatchlist();
    setWatchlistItems(wl);
    if (!selectedStock) setSelectedStock(result.symbol);
    setTimeout(updateUI, 500);
  }, [selectedStock, updateUI]);

  const handleRemove = useCallback(async (symbol: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await stockService.removeSymbol(symbol);
    const wl = stockService.getWatchlist();
    setWatchlistItems(wl);
    if (selectedStock === symbol) {
      setSelectedStock(wl[0]?.symbol ?? '');
    }
    updateUI();
  }, [selectedStock, updateUI]);

  // ─── 衍生数据 ────────────────────────────────────────────────────────────────

  const analysis = selectedStock ? indicatorService.analyzeStock(selectedStock) : null;
  const selectedMeta = selectedStock ? stockService.getSymbolMeta(selectedStock) : null;
  const selectedItem = watchlistItems.find(w => w.symbol === selectedStock);

  const fmtVol = (v: number) => v >= 1e6 ? (v/1e6).toFixed(2)+'M' : v >= 1e3 ? (v/1e3).toFixed(2)+'K' : v.toFixed(0);
  const fmtTime = (ts: number) => new Date(ts).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12: false });

  // ─── 渲染 ─────────────────────────────────────────────────────────────────────

  if (!initialized) {
    return (
      <ConfigProvider theme={{ algorithm: theme.darkAlgorithm }}>
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f1419' }}>
          <div style={{ textAlign: 'center' }}>
            <Spin size="large" />
            <div style={{ color: '#8b949e', marginTop: 16 }}>正在加载自选股数据…</div>
          </div>
        </div>
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider theme={{ algorithm: theme.darkAlgorithm, token: {
      colorPrimary: '#1890ff', colorBgContainer: '#1a1f2e', colorBgElevated: '#1a1f2e',
      colorText: '#ffffff', colorTextSecondary: '#8b949e', borderRadius: 8,
    }}}>
      <Layout className="app">

        {/* ── Header ── */}
        <Header className="header">
          <div className="header-left">
            <div className="logo">
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                <rect width="32" height="32" rx="8" fill="#1890ff"/>
                <path d="M8 20L12 14L16 18L20 10L24 16" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="12" cy="14" r="2" fill="white"/>
                <circle cx="16" cy="18" r="2" fill="white"/>
                <circle cx="20" cy="10" r="2" fill="white"/>
              </svg>
            </div>
            <Title level={3} className="header-title">股票智能预警系统</Title>
          </div>
          <div className="header-center">
            <Text className="time-display">
              {currentTime.toLocaleString('zh-CN', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12: false })}
            </Text>
          </div>
          <div className="header-right">
            {/* 添加自选股按钮 */}
            <Tooltip title="搜索并添加股票/黄金/石油/ETF">
              <Button
                icon={<PlusOutlined />}
                type="primary"
                ghost
                style={{ marginRight: 12 }}
                onClick={() => setSearchVisible(true)}
              >
                添加
              </Button>
            </Tooltip>
            {/* 连接状态 */}
            <Tooltip title={stocks.some(s => s.source === 'real') ? '部分接入真实行情' : '未连接实时行情'}>
              <span style={{ marginRight: 10, fontSize: 16, color: stocks.some(s => s.source === 'real') ? '#52c41a' : '#faad14' }}>
                {stocks.some(s => s.source === 'real') ? <WifiOutlined /> : <DisconnectOutlined />}
              </span>
            </Tooltip>
            {/* 预警按钮 */}
            <Badge count={unreadCount} size="small" offset={[-2, 2]}>
              <Button type="text" icon={<BellOutlined style={{ fontSize: 20 }}/>} className="alert-button" onClick={() => setAlertVisible(true)}/>
            </Badge>
          </div>
        </Header>

        <Content className="content">

          {/* ── 自选股监控区 ── */}
          <div className="monitor-section">
            <div className="section-header">
              <Title level={4} style={{ color: '#fff', margin: 0 }}>实时监控</Title>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text className="stock-count">{stocks.length} 只资产</Text>
                <Button size="small" icon={<PlusOutlined/>} type="dashed" onClick={() => setSearchVisible(true)}>
                  添加资产
                </Button>
              </div>
            </div>

            {stocks.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 0', color: '#586069' }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
                <div>暂无监控资产</div>
                <Button type="primary" icon={<PlusOutlined/>} style={{ marginTop: 16 }} onClick={() => setSearchVisible(true)}>
                  添加第一个资产
                </Button>
              </div>
            ) : (
              <Row gutter={[12, 12]}>
                {stocks.map(({ stock: s, buy, sell, source }) => {
                  const wItem = watchlistItems.find(w => w.symbol === s.symbol);
                  const srcCfg = SOURCE_CONFIG[source];
                  return (
                    <Col xs={24} sm={12} lg={8} xl={6} key={s.symbol}>
                      <Card
                        className={`stock-card ${selectedStock === s.symbol ? 'selected' : ''}`}
                        onClick={() => setSelectedStock(s.symbol)}
                        hoverable
                        style={{ position: 'relative' }}
                      >
                        {/* 移除按钮 */}
                        <Button
                          size="small"
                          type="text"
                          icon={<DeleteFilled />}
                          danger
                          style={{ position: 'absolute', top: 6, right: 6, opacity: 0.5, zIndex: 1 }}
                          onClick={e => handleRemove(s.symbol, e)}
                        />

                        <div className="stock-card-header">
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <Title level={4} style={{ margin: 0, color: '#fff' }}>{s.symbol}</Title>
                              {/* 数据源指示点 */}
                              <Tooltip title={`数据来源：${srcCfg.label}`}>
                                <span style={{ fontSize: 10, color: srcCfg.color }}>●</span>
                              </Tooltip>
                            </div>
                            <Text className="stock-name">{s.name}</Text>
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                            {/* 资产类型 */}
                            {wItem && (
                              <Tag color={assetTypeColor(wItem.assetType)} style={{ margin: 0, fontSize: 11 }}>
                                {assetTypeLabel(wItem.assetType)}
                              </Tag>
                            )}
                            {/* 信号标签 */}
                            {buy?.signal  && <Tag color="green" style={{ margin: 0 }}>买入</Tag>}
                            {sell?.signal && <Tag color="red"   style={{ margin: 0 }}>卖出</Tag>}
                            {!buy?.signal && !sell?.signal && <Tag color="default" style={{ margin: 0 }}>观望</Tag>}
                          </div>
                        </div>

                        <div className="stock-price">
                          <Text className="price-value">${s.price.toFixed(s.price >= 100 ? 2 : 4)}</Text>
                          <div className={`price-change ${s.changePercent >= 0 ? 'positive' : 'negative'}`}>
                            {s.changePercent >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                            <Text>{s.changePercent >= 0 ? '+' : ''}{s.changePercent.toFixed(2)}%</Text>
                          </div>
                        </div>
                        <div className="stock-volume">
                          <Text className="volume-label">成交量</Text>
                          <Text className="volume-value">{fmtVol(s.volume)}</Text>
                        </div>
                      </Card>
                    </Col>
                  );
                })}
              </Row>
            )}
          </div>

          {/* ── 详情区（K线 + 指标 + 预测）── */}
          {selectedStock && analysis && (
            <div className="detail-section" key={`${selectedStock}-${refreshKey}`}>
              <Card className="chart-card">
                <div className="chart-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Title level={5} style={{ color: '#fff', margin: 0 }}>{selectedStock} K线图表</Title>
                    {selectedItem && (
                      <Tag color={assetTypeColor(selectedItem.assetType)}>
                        {assetTypeLabel(selectedItem.assetType)}
                      </Tag>
                    )}
                    {selectedMeta && (
                      <Tooltip title={`数据来源：${SOURCE_CONFIG[selectedMeta.source].label}`}>
                        <Tag color={selectedMeta.source === 'real' ? 'success' : selectedMeta.source === 'database' ? 'warning' : 'default'}>
                          {SOURCE_CONFIG[selectedMeta.source].dot} {SOURCE_CONFIG[selectedMeta.source].label}
                        </Tag>
                      </Tooltip>
                    )}
                  </div>
                  <div className="chart-legend">
                    <span className="legend-item"><span className="legend-color ma5"></span> MA5</span>
                    <span className="legend-item"><span className="legend-color ma10"></span> MA10</span>
                    <span className="legend-item"><span className="legend-color ma20"></span> MA20</span>
                  </div>
                </div>
                <div className="chart-container" ref={setChartContainer}></div>
              </Card>

              <Row gutter={[16, 16]}>
                <Col xs={24} lg={16}>
                  <Card className="indicator-card">
                    <Title level={5} style={{ color: '#fff', marginBottom: 16 }}>技术指标</Title>
                    <Row gutter={[16, 16]}>
                      <Col span={6}>
                        <div className="indicator-group">
                          <Text className="indicator-name">MA / EMA</Text>
                          <div className="indicator-row"><Text className="label">MA5</Text><Text className="value">{analysis.indicators.ma5.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">MA20</Text><Text className="value">{analysis.indicators.ma20.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">EMA9</Text><Text className={`value ${analysis.indicators.ema9 > analysis.indicators.ema21 ? 'positive' : 'negative'}`}>{analysis.indicators.ema9.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">EMA21</Text><Text className="value">{analysis.indicators.ema21.toFixed(2)}</Text></div>
                        </div>
                      </Col>
                      <Col span={6}>
                        <div className="indicator-group">
                          <Text className="indicator-name">MACD</Text>
                          <div className="indicator-row"><Text className="label">DIF</Text><Text className={`value ${analysis.indicators.macdDif > 0 ? 'positive' : 'negative'}`}>{analysis.indicators.macdDif.toFixed(4)}</Text></div>
                          <div className="indicator-row"><Text className="label">DEA</Text><Text className={`value ${analysis.indicators.macdDea > 0 ? 'positive' : 'negative'}`}>{analysis.indicators.macdDea.toFixed(4)}</Text></div>
                          <div className="indicator-row"><Text className="label">Hist</Text><Text className={`value ${analysis.indicators.macdHistogram > 0 ? 'positive' : 'negative'}`}>{analysis.indicators.macdHistogram.toFixed(4)}</Text></div>
                        </div>
                      </Col>
                      <Col span={6}>
                        <div className="indicator-group">
                          <Text className="indicator-name">RSI</Text>
                          <div className="indicator-row"><Text className="label">RSI9</Text><Text className={`value ${analysis.indicators.rsi9>70?'negative':analysis.indicators.rsi9<30?'positive':''}`}>{analysis.indicators.rsi9.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">RSI14</Text><Text className={`value ${analysis.indicators.rsi14>70?'negative':analysis.indicators.rsi14<30?'positive':''}`}>{analysis.indicators.rsi14.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">RSI24</Text><Text className="value">{analysis.indicators.rsi24.toFixed(2)}</Text></div>
                        </div>
                      </Col>
                      <Col span={6}>
                        <div className="indicator-group">
                          <Text className="indicator-name">KDJ / ADX</Text>
                          <div className="indicator-row"><Text className="label">K</Text><Text className="value">{analysis.indicators.kdjK.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">D</Text><Text className="value">{analysis.indicators.kdjD.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">ADX</Text><Text className={`value ${analysis.indicators.adx>25?'positive':''}`}>{analysis.indicators.adx.toFixed(1)}</Text></div>
                        </div>
                      </Col>
                    </Row>
                    <Row gutter={[16, 16]} style={{ marginTop: 12 }}>
                      <Col span={8}>
                        <div className="indicator-group">
                          <Text className="indicator-name">成交量分布 (VP)</Text>
                          <div className="indicator-row"><Text className="label">POC</Text><Text className="value">${analysis.indicators.poc.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">VAH</Text><Text className="value negative">${analysis.indicators.valueAreaHigh.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">VAL</Text><Text className="value positive">${analysis.indicators.valueAreaLow.toFixed(2)}</Text></div>
                        </div>
                      </Col>
                      <Col span={8}>
                        <div className="indicator-group">
                          <Text className="indicator-name">先行信号</Text>
                          <div className="indicator-row"><Text className="label">RSI底背离</Text><Text className={`value ${analysis.indicators.rsiBullDiv?'positive':''}`}>{analysis.indicators.rsiBullDiv?'✓ 触发':'—'}</Text></div>
                          <div className="indicator-row"><Text className="label">RSI顶背离</Text><Text className={`value ${analysis.indicators.rsiBearDiv?'negative':''}`}>{analysis.indicators.rsiBearDiv?'✓ 触发':'—'}</Text></div>
                          <div className="indicator-row"><Text className="label">BB压缩</Text><Text className={`value ${analysis.indicators.bollSqueezing?'positive':''}`}>{analysis.indicators.bollSqueezing?'⚡ 压缩中':'正常'}</Text></div>
                        </div>
                      </Col>
                      <Col span={8}>
                        <div className="indicator-group">
                          <Text className="indicator-name">布林带</Text>
                          <div className="indicator-row"><Text className="label">上轨</Text><Text className="value">{analysis.indicators.bollUp.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">中轨</Text><Text className="value">{analysis.indicators.bollMb.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">下轨</Text><Text className="value">{analysis.indicators.bollDn.toFixed(2)}</Text></div>
                        </div>
                      </Col>
                    </Row>
                  </Card>
                </Col>
                <Col xs={24} lg={8}>
                  <Card className="prediction-card">
                    <Title level={5} style={{ color: '#fff', marginBottom: 16 }}>顶底预测</Title>
                    <div className="prediction-content">
                      <Tag className={`prediction-tag ${analysis.prediction.type}`}
                           color={analysis.prediction.type==='top'?'red':analysis.prediction.type==='bottom'?'green':'default'}>
                        {analysis.prediction.type==='top'?'潜在顶部':analysis.prediction.type==='bottom'?'潜在底部':'无明显信号'}
                      </Tag>
                      {analysis.prediction.type !== 'neutral' && (
                        <Text className="probability">{(analysis.prediction.probability * 100).toFixed(0)}%</Text>
                      )}
                      <div className="signals-list">
                        {analysis.prediction.signals.map((s, i) => <Tag key={i} className="signal-tag">{s}</Tag>)}
                      </div>
                      <Text className="recommendation">{analysis.prediction.recommendation}</Text>
                    </div>
                  </Card>
                </Col>
              </Row>
            </div>
          )}
        </Content>

        {/* ── 预警面板 ── */}
        {alertVisible && (
          <div className="alert-overlay" onClick={() => setAlertVisible(false)}>
            <div className="alert-panel" onClick={e => e.stopPropagation()}>
              <div className="alert-header">
                <Title level={4} style={{ color: '#fff', margin: 0 }}>预警通知</Title>
                <div className="alert-actions">
                  <Button type="text" icon={<CheckOutlined/>} size="small" onClick={() => alertService.markAllAsRead()}>全部已读</Button>
                  <Button type="text" icon={<DeleteOutlined/>} size="small" onClick={() => alertService.clearAlerts()}>清空</Button>
                  <Button type="text" icon={<CloseOutlined/>}  size="small" onClick={() => setAlertVisible(false)}/>
                </div>
              </div>
              <div className="alert-list">
                {alerts.length === 0 ? <Empty description="暂无预警通知"/> : alerts.map(alert => (
                  <Card key={alert.id} className={`alert-item ${alert.read ? 'read' : 'unread'}`} onClick={() => alertService.markAsRead(alert.id)}>
                    <div className="alert-header-row">
                      <Text className="alert-icon">{alert.type==='buy'?'🟢':alert.type==='sell'?'🔴':alert.type==='top'?'🔺':'🔻'}</Text>
                      <Text className="alert-symbol">{alert.symbol}</Text>
                      <Tag color={alert.level==='high'?'red':alert.level==='medium'?'orange':'blue'}>
                        {alert.level==='high'?'高级':alert.level==='medium'?'中级':'低级'}
                      </Tag>
                      <Text className="alert-time">{fmtTime(alert.timestamp)}</Text>
                    </div>
                    <Text className="alert-type">
                      {alert.type==='buy'?'买入':alert.type==='sell'?'卖出':alert.type==='top'?'顶部':'底部'}信号
                    </Text>
                    <div className="alert-reasons">
                      {alert.reasons.map((r, i) => <Tag key={i} className="reason-tag">{r}</Tag>)}
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── 搜索添加面板 ── */}
        <SearchModal
          visible={searchVisible}
          watchlist={watchlistItems.map(w => w.symbol)}
          onClose={() => setSearchVisible(false)}
          onAdd={async (item) => { await handleAdd(item); }}
        />

      </Layout>
    </ConfigProvider>
  );
};

export default App;

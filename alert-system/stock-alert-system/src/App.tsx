import React, { useState, useEffect } from 'react';
import { ConfigProvider, theme, Layout, Row, Col, Card, Typography, Tag, Badge, Spin, Button, Empty } from 'antd';
import { BellOutlined, CloseOutlined, CheckOutlined, DeleteOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import { createChart, IChartApi, ISeriesApi, CandlestickData, LineData, Time } from 'lightweight-charts';
import { alertService } from './services/alertService';
import { indicatorService } from './services/indicatorService';
import { stockService } from './services/stockService';
import { StockData, SignalResult, Alert } from './types';
import './App.css';

const { Content, Header } = Layout;
const { Title, Text } = Typography;

const App: React.FC = () => {
  const [selectedStock, setSelectedStock] = useState<string>('AAPL');
  const [alertVisible, setAlertVisible] = useState(false);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [stocks, setStocks] = useState<{ stock: StockData; buySignal?: SignalResult; sellSignal?: SignalResult }[]>([]);
  const [chartContainer, setChartContainer] = useState<HTMLDivElement | null>(null);
  const [chart, setChart] = useState<IChartApi | null>(null);
  const [candlestickSeries, setCandlestickSeries] = useState<ISeriesApi<'Candlestick'> | null>(null);
  const [ma5Series, setMa5Series] = useState<ISeriesApi<'Line'> | null>(null);
  const [ma10Series, setMa10Series] = useState<ISeriesApi<'Line'> | null>(null);
  const [ma20Series, setMa20Series] = useState<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    const updateStocks = () => {
      const stockData = stockService.getStocks();
      const stocksWithSignals = stockData.map((stock) => ({
        stock,
        buySignal: indicatorService.getBuySignal(stock.symbol),
        sellSignal: indicatorService.getSellSignal(stock.symbol),
      }));
      setStocks(stocksWithSignals);

      const symbols = stockService.getAvailableStocks();
      symbols.forEach((symbol) => {
        const analysis = indicatorService.analyzeStock(symbol);
        if (analysis) {
          if (analysis.buySignal.signal) {
            alertService.createAlert(analysis, 'buy', analysis.buySignal);
          }
          if (analysis.sellSignal.signal) {
            alertService.createAlert(analysis, 'sell', analysis.sellSignal);
          }
          if (analysis.prediction.type !== 'neutral') {
            alertService.createAlert(analysis, analysis.prediction.type, {
              signal: true,
              level: analysis.prediction.probability > 0.7 ? 'high' : 'medium',
              score: Math.round(analysis.prediction.probability * 100),
              reasons: analysis.prediction.signals,
            });
          }
        }
      });

      setRefreshKey((k) => k + 1);
    };

    updateStocks();
    const interval = setInterval(() => {
      stockService.updateStocks();
      updateStocks();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!chartContainer) return;

    const newChart = createChart(chartContainer, {
      layout: {
        background: { color: '#0f1419' },
        textColor: '#8b949e',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
      },
    });

    const candleSeries = newChart.addCandlestickSeries({
      upColor: '#52c41a',
      downColor: '#ff4d4f',
      borderUpColor: '#52c41a',
      borderDownColor: '#ff4d4f',
      wickUpColor: '#52c41a',
      wickDownColor: '#ff4d4f',
    });

    const ma5S = newChart.addLineSeries({ color: '#1890ff', lineWidth: 1, title: 'MA5' });
    const ma10S = newChart.addLineSeries({ color: '#faad14', lineWidth: 1, title: 'MA10' });
    const ma20S = newChart.addLineSeries({ color: '#722ed1', lineWidth: 1, title: 'MA20' });

    setChart(newChart);
    setCandlestickSeries(candleSeries);
    setMa5Series(ma5S);
    setMa10Series(ma10S);
    setMa20Series(ma20S);

    const handleResize = () => {
      if (chartContainer) {
        newChart.applyOptions({
          width: chartContainer.clientWidth,
          height: 400,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      newChart.remove();
    };
  }, [chartContainer]);

  useEffect(() => {
    if (!chart || !candlestickSeries) return;

    const kLineData = stockService.getKLineData(selectedStock);
    if (kLineData.length === 0) return;

    const candleData: CandlestickData[] = kLineData.map((d) => ({
      time: d.time as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    candlestickSeries.setData(candleData);

    const closes = kLineData.map((d) => d.close);
    const ma5Data: LineData[] = [];
    const ma10Data: LineData[] = [];
    const ma20Data: LineData[] = [];

    for (let i = 0; i < kLineData.length; i++) {
      if (i >= 4) {
        const ma5 = closes.slice(i - 4, i + 1).reduce((a, b) => a + b, 0) / 5;
        ma5Data.push({ time: kLineData[i].time as Time, value: ma5 });
      }
      if (i >= 9) {
        const ma10 = closes.slice(i - 9, i + 1).reduce((a, b) => a + b, 0) / 10;
        ma10Data.push({ time: kLineData[i].time as Time, value: ma10 });
      }
      if (i >= 19) {
        const ma20 = closes.slice(i - 19, i + 1).reduce((a, b) => a + b, 0) / 20;
        ma20Data.push({ time: kLineData[i].time as Time, value: ma20 });
      }
    }

    ma5Series?.setData(ma5Data);
    ma10Series?.setData(ma10Data);
    ma20Series?.setData(ma20Data);

    chart.timeScale().fitContent();
  }, [selectedStock, refreshKey, chart, candlestickSeries, ma5Series, ma10Series, ma20Series]);

  const analysis = indicatorService.analyzeStock(selectedStock);
  const alerts = alertService.getAlerts();
  const unreadCount = alertService.getUnreadCount();

  const formatVolume = (volume: number): string => {
    if (volume >= 1000000) return (volume / 1000000).toFixed(2) + 'M';
    if (volume >= 1000) return (volume / 1000).toFixed(2) + 'K';
    return volume.toFixed(2);
  };

  const formatTime = (timestamp: number): string => {
    return new Date(timestamp).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
    });
  };

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#1890ff',
          colorBgContainer: '#1a1f2e',
          colorBgElevated: '#1a1f2e',
          colorText: '#ffffff',
          colorTextSecondary: '#8b949e',
          borderRadius: 8,
        },
      }}
    >
      <Layout className="app">
        <Header className="header">
          <div className="header-left">
            <div className="logo">
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                <rect width="32" height="32" rx="8" fill="#1890ff" />
                <path d="M8 20L12 14L16 18L20 10L24 16" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="12" cy="14" r="2" fill="white" />
                <circle cx="16" cy="18" r="2" fill="white" />
                <circle cx="20" cy="10" r="2" fill="white" />
              </svg>
            </div>
            <Title level={3} className="header-title">股票智能预警系统</Title>
          </div>
          <div className="header-center">
            <Text className="time-display">{new Date().toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</Text>
          </div>
          <div className="header-right">
            <Badge count={unreadCount} size="small" offset={[-2, 2]}>
              <Button type="text" icon={<BellOutlined style={{ fontSize: 20 }} />} className="alert-button" onClick={() => setAlertVisible(true)} />
            </Badge>
          </div>
        </Header>

        <Content className="content">
          <div className="monitor-section">
            <div className="section-header">
              <Title level={4} style={{ color: '#fff', margin: 0 }}>实时监控</Title>
              <Text className="stock-count">{stocks.length} 只股票</Text>
            </div>
            <Row gutter={[16, 16]}>
              {stocks.map(({ stock, buySignal, sellSignal }) => (
                <Col xs={24} sm={12} lg={8} key={stock.symbol}>
                  <Card className={`stock-card ${selectedStock === stock.symbol ? 'selected' : ''}`} onClick={() => setSelectedStock(stock.symbol)} hoverable>
                    <div className="stock-card-header">
                      <div>
                        <Title level={4} style={{ margin: 0, color: '#fff' }}>{stock.symbol}</Title>
                        <Text className="stock-name">{stock.name}</Text>
                      </div>
                      <div className="stock-tags">
                        {buySignal?.signal && <Tag color="green">买入</Tag>}
                        {sellSignal?.signal && <Tag color="red">卖出</Tag>}
                        {!buySignal?.signal && !sellSignal?.signal && <Tag color="default">观望</Tag>}
                        <Button 
                          type="text" 
                          size="small" 
                          danger 
                          icon={<DeleteOutlined />} 
                          onClick={(e) => {
                            e.stopPropagation();
                            if (stockService.deleteStock(stock.symbol)) {
                              const newStocks = stocks.filter(s => s.stock.symbol !== stock.symbol);
                              setStocks(newStocks);
                              if (selectedStock === stock.symbol && newStocks.length > 0) {
                                setSelectedStock(newStocks[0].stock.symbol);
                              }
                            }
                          }} 
                        />
                      </div>
                    </div>
                    <div className="stock-price">
                      <Text className="price-value">${stock.price.toFixed(2)}</Text>
                      <div className={`price-change ${stock.changePercent >= 0 ? 'positive' : 'negative'}`}>
                        {stock.changePercent >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                        <Text>{stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%</Text>
                      </div>
                    </div>
                    <div className="stock-volume">
                      <Text className="volume-label">成交量</Text>
                      <Text className="volume-value">{formatVolume(stock.volume)}</Text>
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          </div>

          <div className="detail-section" key={`${selectedStock}-${refreshKey}`}>
            <Card className="chart-card">
              <div className="chart-header">
                <Title level={5} style={{ color: '#fff', margin: 0 }}>{selectedStock} K线图表</Title>
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
                  {analysis && (
                    <Row gutter={[16, 16]}>
                      <Col span={6}>
                        <div className="indicator-group">
                          <Text className="indicator-name">MA</Text>
                          <div className="indicator-row"><Text className="label">MA5</Text><Text className="value">{analysis.indicators.ma5.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">MA10</Text><Text className="value">{analysis.indicators.ma10.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">MA20</Text><Text className="value">{analysis.indicators.ma20.toFixed(2)}</Text></div>
                        </div>
                      </Col>
                      <Col span={6}>
                        <div className="indicator-group">
                          <Text className="indicator-name">MACD</Text>
                          <div className="indicator-row"><Text className="label">DIF</Text><Text className={`value ${analysis.indicators.macdDif > 0 ? 'positive' : 'negative'}`}>{analysis.indicators.macdDif.toFixed(4)}</Text></div>
                          <div className="indicator-row"><Text className="label">DEA</Text><Text className={`value ${analysis.indicators.macdDea > 0 ? 'positive' : 'negative'}`}>{analysis.indicators.macdDea.toFixed(4)}</Text></div>
                          <div className="indicator-row"><Text className="label">MACD</Text><Text className={`value ${analysis.indicators.macdHistogram > 0 ? 'positive' : 'negative'}`}>{analysis.indicators.macdHistogram.toFixed(4)}</Text></div>
                        </div>
                      </Col>
                      <Col span={6}>
                        <div className="indicator-group">
                          <Text className="indicator-name">KDJ</Text>
                          <div className="indicator-row"><Text className="label">K</Text><Text className="value">{analysis.indicators.kdjK.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">D</Text><Text className="value">{analysis.indicators.kdjD.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">J</Text><Text className="value">{analysis.indicators.kdjJ.toFixed(2)}</Text></div>
                        </div>
                      </Col>
                      <Col span={6}>
                        <div className="indicator-group">
                          <Text className="indicator-name">RSI</Text>
                          <div className="indicator-row"><Text className="label">RSI6</Text><Text className="value">{analysis.indicators.rsi6.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">RSI12</Text><Text className="value">{analysis.indicators.rsi12.toFixed(2)}</Text></div>
                          <div className="indicator-row"><Text className="label">RSI24</Text><Text className="value">{analysis.indicators.rsi24.toFixed(2)}</Text></div>
                        </div>
                      </Col>
                    </Row>
                  )}
                </Card>
              </Col>
              <Col xs={24} lg={8}>
                <Card className="prediction-card">
                  <Title level={5} style={{ color: '#fff', marginBottom: 16 }}>顶底预测</Title>
                  {analysis && (
                    <div className="prediction-content">
                      <Tag className={`prediction-tag ${analysis.prediction.type}`} color={analysis.prediction.type === 'top' ? 'red' : analysis.prediction.type === 'bottom' ? 'green' : 'default'}>
                        {analysis.prediction.type === 'top' ? '潜在顶部' : analysis.prediction.type === 'bottom' ? '潜在底部' : '无明显信号'}
                      </Tag>
                      {analysis.prediction.type !== 'neutral' && (
                        <Text className="probability">{(analysis.prediction.probability * 100).toFixed(0)}%</Text>
                      )}
                      <div className="signals-list">
                        {analysis.prediction.signals.map((s, i) => (
                          <Tag key={i} className="signal-tag">{s}</Tag>
                        ))}
                      </div>
                      <Text className="recommendation">{analysis.prediction.recommendation}</Text>
                    </div>
                  )}
                </Card>
              </Col>
            </Row>
          </div>
        </Content>

        {alertVisible && (
          <div className="alert-overlay" onClick={() => setAlertVisible(false)}>
            <div className="alert-panel" onClick={(e) => e.stopPropagation()}>
              <div className="alert-header">
                <Title level={4} style={{ color: '#fff', margin: 0 }}>预警通知</Title>
                <div className="alert-actions">
                  <Button type="text" icon={<CheckOutlined />} size="small" onClick={() => alertService.markAllAsRead()}>全部已读</Button>
                  <Button type="text" icon={<DeleteOutlined />} size="small" onClick={() => alertService.clearAlerts()}>清空</Button>
                  <Button type="text" icon={<CloseOutlined />} size="small" onClick={() => setAlertVisible(false)} />
                </div>
              </div>
              <div className="alert-list">
                {alerts.length === 0 ? (
                  <Empty description="暂无预警通知" />
                ) : (
                  alerts.map((alert) => (
                    <Card key={alert.id} className={`alert-item ${alert.read ? 'read' : 'unread'}`} onClick={() => alertService.markAsRead(alert.id)}>
                      <div className="alert-header-row">
                        <Text className="alert-icon">{alert.type === 'buy' ? '🟢' : alert.type === 'sell' ? '🔴' : alert.type === 'top' ? '🔺' : '🔻'}</Text>
                        <Text className="alert-symbol">{alert.symbol}</Text>
                        <Tag color={alert.level === 'high' ? 'red' : alert.level === 'medium' ? 'orange' : 'blue'}>{alert.level === 'high' ? '高级' : alert.level === 'medium' ? '中级' : '低级'}</Tag>
                        <Text className="alert-time">{formatTime(alert.timestamp)}</Text>
                      </div>
                      <Text className="alert-type">{alert.type === 'buy' ? '买入' : alert.type === 'sell' ? '卖出' : alert.type === 'top' ? '顶部' : '底部'}信号</Text>
                      <div className="alert-reasons">
                        {alert.reasons.map((r, i) => <Tag key={i} className="reason-tag">{r}</Tag>)}
                      </div>
                    </Card>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </Layout>
    </ConfigProvider>
  );
};

export default App;

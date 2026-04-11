import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Animated,
  KeyboardAvoidingView,
  LayoutAnimation,
  Platform,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  UIManager,
  Vibration,
  View,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

type Step = 'login' | 'construct' | 'active';
type ActivePanel = 'overview' | 'notifications';
type NotificationScope = 'all' | 'read' | 'unread' | 'pending_ack';
type Market = 'US' | 'CAD' | 'CRYPTO';

type NotificationType = 'signal' | 'portfolio' | 'push' | 'system';

interface Holding {
  symbol: string;
  name: string;
  market: Market;
  shares: number;
  avg_cost: number;
}

interface Subscription {
  symbol: string;
  name: string;
  market: Market;
}

interface NotificationItem {
  id: string;
  notification_id: string | null;
  type: NotificationType;
  title: string;
  body: string;
  is_read: boolean;
  ack_required: boolean;
  acknowledged_at: string | null;
  opened_at: string | null;
  created_at: string;
  signal_id?: string | null;
  metadata?: Record<string, unknown>;
}

interface BackendSnapshot {
  profile: {
    user: {
      email: string;
      plan: string;
    };
  } | null;
  dashboard: {
    subscription: {
      status: 'active' | 'inactive';
    };
  } | null;
  portfolio: Holding[];
  watchlist: Subscription[];
  notifications: NotificationItem[];
}

interface SyncPayload {
  cash: string;
  holdings: Holding[];
  subscriptions: Subscription[];
}

interface SubscriberAppScreenProps {
  onSendCode?: (email: string) => Promise<{ cooldownSeconds?: number; message?: string } | void>;
  onLogin?: (email: string, code: string) => Promise<{ ok: boolean; message?: string; plan?: string } | boolean>;
  onSync?: (payload: SyncPayload) => Promise<Partial<BackendSnapshot> | void>;
}

interface ScalePressableProps {
  onPress?: () => void;
  onLongPress?: () => void;
  disabled?: boolean;
  delayLongPress?: number;
  style?: object;
  children: React.ReactNode;
}

const STORAGE_KEYS = {
  accessToken: 'stockpy.rn.access-token',
  user: 'stockpy.rn.user',
  notifications: 'stockpy.rn.notifications',
};

const LOCAL_NOTIFICATION_MAX = 500;

const DEFAULT_HOLDINGS: Holding[] = [
  {
    symbol: 'AAPL',
    name: 'Apple Inc.',
    market: 'US',
    shares: 100,
    avg_cost: 100,
  },
];

const DEFAULT_SUBSCRIPTIONS: Subscription[] = [
  { symbol: 'TSLA', name: 'Tesla, Inc.', market: 'US' },
  { symbol: 'RY.TO', name: 'Royal Bank of Canada', market: 'CAD' },
  { symbol: 'BTCUSDT', name: 'BTC / USDT', market: 'CRYPTO' },
];

const DEFAULT_SNAPSHOT: BackendSnapshot = {
  profile: null,
  dashboard: null,
  portfolio: [],
  watchlist: [],
  notifications: [],
};

const FONT_BODY = Platform.select({
  ios: 'PingFang SC',
  android: 'sans-serif',
  default: 'System',
});

const FONT_DISPLAY = Platform.select({
  ios: 'Avenir Next',
  android: 'sans-serif-medium',
  default: 'System',
});

const FONT_MONO = Platform.select({
  ios: 'Menlo',
  android: 'monospace',
  default: 'monospace',
});

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

function formatTime(value?: string | null): string {
  if (!value) {
    return '--';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '--';
  }
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hour = `${date.getHours()}`.padStart(2, '0');
  const minute = `${date.getMinutes()}`.padStart(2, '0');
  return `${month}-${day} ${hour}:${minute}`;
}

function notificationTimestamp(item: NotificationItem): number {
  const ts = new Date(item.created_at).getTime();
  return Number.isNaN(ts) ? 0 : ts;
}

function normalizeNotification(input: Partial<NotificationItem>): NotificationItem {
  const fallbackId = `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const id = String(input.id || input.notification_id || fallbackId);
  const type = (input.type || 'push') as NotificationType;
  return {
    id,
    notification_id: input.notification_id || null,
    type,
    title: String(input.title || '系统通知'),
    body: String(input.body || ''),
    is_read: Boolean(input.is_read),
    ack_required: Boolean(input.ack_required),
    acknowledged_at: input.acknowledged_at || null,
    opened_at: input.opened_at || null,
    created_at: input.created_at || new Date().toISOString(),
    signal_id: input.signal_id || null,
    metadata: input.metadata || {},
  };
}

function sortNotifications(items: NotificationItem[]): NotificationItem[] {
  return [...items]
    .map((item) => normalizeNotification(item))
    .sort((a, b) => notificationTimestamp(b) - notificationTimestamp(a))
    .slice(0, LOCAL_NOTIFICATION_MAX);
}

function marketLabel(value: Market): string {
  if (value === 'CAD') {
    return '加股';
  }
  if (value === 'CRYPTO') {
    return '加密';
  }
  return '美股';
}

function normalizeNotificationType(type: NotificationType): NotificationType {
  const raw = String(type || 'push').toLowerCase();
  if (raw.includes('signal')) {
    return 'signal';
  }
  if (raw.includes('portfolio')) {
    return 'portfolio';
  }
  if (raw.includes('system')) {
    return 'system';
  }
  return 'push';
}

function notificationTypeLabel(type: NotificationType): string {
  const key = normalizeNotificationType(type);
  if (key === 'signal') {
    return '信号通知';
  }
  if (key === 'portfolio') {
    return '持仓通知';
  }
  if (key === 'system') {
    return '系统通知';
  }
  return '推送通知';
}

function ScalePressable({
  onPress,
  onLongPress,
  disabled,
  delayLongPress,
  style,
  children,
}: ScalePressableProps): JSX.Element {
  const scale = useRef(new Animated.Value(1)).current;

  const pressIn = useCallback(() => {
    Animated.spring(scale, {
      toValue: 0.98,
      speed: 30,
      bounciness: 0,
      useNativeDriver: true,
    }).start();
  }, [scale]);

  const pressOut = useCallback(() => {
    Animated.spring(scale, {
      toValue: 1,
      speed: 24,
      bounciness: 6,
      useNativeDriver: true,
    }).start();
  }, [scale]);

  return (
    <Animated.View style={[style, { transform: [{ scale }] }]}>
      <Pressable
        disabled={disabled}
        delayLongPress={delayLongPress}
        onPress={onPress}
        onLongPress={onLongPress}
        onPressIn={pressIn}
        onPressOut={pressOut}
      >
        {children}
      </Pressable>
    </Animated.View>
  );
}

export default function SubscriberAppScreen({ onSendCode, onLogin, onSync }: SubscriberAppScreenProps): JSX.Element {
  const [step, setStep] = useState<Step>('login');
  const [activePanel, setActivePanel] = useState<ActivePanel>('overview');
  const [selectedNotificationId, setSelectedNotificationId] = useState('');
  const [notificationScope, setNotificationScope] = useState<NotificationScope>('all');

  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [sendCodeBusy, setSendCodeBusy] = useState(false);
  const [sendCodeCooldownSeconds, setSendCodeCooldownSeconds] = useState(0);

  const [toast, setToast] = useState('');

  const [accessToken, setAccessToken] = useState('');
  const [cash, setCash] = useState('1000000');
  const [holdings, setHoldings] = useState<Holding[]>(DEFAULT_HOLDINGS);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>(DEFAULT_SUBSCRIPTIONS);

  const [newHoldSym, setNewHoldSym] = useState('');
  const [newHoldVol, setNewHoldVol] = useState('');
  const [newHoldCost, setNewHoldCost] = useState('');
  const [newSubSym, setNewSubSym] = useState('');

  const [backendConnected, setBackendConnected] = useState(false);
  const [backendLoading, setBackendLoading] = useState(false);
  const [backendError, setBackendError] = useState('');
  const [backendSnapshot, setBackendSnapshot] = useState<BackendSnapshot>(DEFAULT_SNAPSHOT);
  const [lastBackendSyncAt, setLastBackendSyncAt] = useState('');

  const [pushConfigured, setPushConfigured] = useState(false);
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushStatus, setPushStatus] = useState('登录后可启用推送。');

  const [refreshingNotifications, setRefreshingNotifications] = useState(false);

  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const notificationItems = backendSnapshot.notifications || [];

  const showToast = useCallback((message: string) => {
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
      toastTimerRef.current = null;
    }
    setToast(message);
    toastTimerRef.current = setTimeout(() => {
      setToast('');
      toastTimerRef.current = null;
    }, 1800);
  }, []);

  const triggerTouchFeedback = useCallback((mode: 'light' | 'strong' = 'light') => {
    if (Platform.OS === 'ios') {
      Vibration.vibrate(mode === 'strong' ? 18 : 8);
      return;
    }
    Vibration.vibrate(mode === 'strong' ? [0, 14, 18, 14] : 10);
  }, []);

  const replaceNotifications = useCallback((items: NotificationItem[]) => {
    setBackendSnapshot((prev) => ({
      ...prev,
      notifications: sortNotifications(items),
    }));
  }, []);

  const persistNotifications = useCallback(async (items: NotificationItem[]) => {
    await AsyncStorage.setItem(STORAGE_KEYS.notifications, JSON.stringify(sortNotifications(items)));
  }, []);

  const loadLocalNotifications = useCallback(
    async (silent = true) => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEYS.notifications);
        const parsed = raw ? (JSON.parse(raw) as NotificationItem[]) : [];
        const sorted = sortNotifications(parsed || []);
        replaceNotifications(sorted);
        if (!silent) {
          showToast('通知已从本地存储刷新');
        }
      } catch (error) {
        if (!silent) {
          showToast(`本地通知读取失败：${String(error)}`);
        }
      }
    },
    [replaceNotifications, showToast],
  );

  const updateAndPersistNotifications = useCallback(
    async (updater: (items: NotificationItem[]) => NotificationItem[]) => {
      const current = notificationItems;
      const next = sortNotifications(updater(current));
      replaceNotifications(next);
      await persistNotifications(next);
      return next;
    },
    [notificationItems, persistNotifications, replaceNotifications],
  );

  const filteredNotificationItems = useMemo(() => {
    if (notificationScope === 'all') {
      return notificationItems;
    }
    if (notificationScope === 'read') {
      return notificationItems.filter((item) => item.is_read);
    }
    if (notificationScope === 'unread') {
      return notificationItems.filter((item) => !item.is_read);
    }
    return notificationItems.filter((item) => item.ack_required && !item.acknowledged_at);
  }, [notificationItems, notificationScope]);

  const notificationGroups = useMemo(() => {
    const groups = new Map<string, NotificationItem[]>();
    for (const item of filteredNotificationItems) {
      const key = normalizeNotificationType(item.type);
      const list = groups.get(key) || [];
      list.push(item);
      groups.set(key, list);
    }
    return [...groups.entries()]
      .map(([key, items]) => ({
        key,
        label: notificationTypeLabel(key as NotificationType),
        items: sortNotifications(items),
      }))
      .sort((a, b) => b.items.length - a.items.length);
  }, [filteredNotificationItems]);

  const unreadNotificationCount = useMemo(
    () => notificationItems.filter((item) => !item.is_read).length,
    [notificationItems],
  );

  const notificationScopeCount = useCallback(
    (scope: NotificationScope): number => {
      if (scope === 'all') {
        return notificationItems.length;
      }
      if (scope === 'read') {
        return notificationItems.filter((item) => item.is_read).length;
      }
      if (scope === 'unread') {
        return notificationItems.filter((item) => !item.is_read).length;
      }
      return notificationItems.filter((item) => item.ack_required && !item.acknowledged_at).length;
    },
    [notificationItems],
  );

  const selectedNotification = useMemo(
    () => notificationItems.find((item) => String(item.id) === String(selectedNotificationId)) || null,
    [notificationItems, selectedNotificationId],
  );

  useEffect(() => {
    void loadLocalNotifications(true);
  }, [loadLocalNotifications]);

  useEffect(() => {
    if (sendCodeCooldownSeconds <= 0) {
      return;
    }
    const timer = setInterval(() => {
      setSendCodeCooldownSeconds((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [sendCodeCooldownSeconds]);

  useEffect(() => {
    if (!selectedNotificationId && notificationItems.length > 0 && activePanel === 'notifications') {
      const preferred = filteredNotificationItems.find((item) => !item.is_read) || filteredNotificationItems[0] || notificationItems[0];
      if (preferred) {
        setSelectedNotificationId(String(preferred.id));
      }
      return;
    }

    if (selectedNotificationId) {
      const exists = notificationItems.some((item) => String(item.id) === String(selectedNotificationId));
      if (!exists) {
        setSelectedNotificationId('');
      }
    }
  }, [activePanel, filteredNotificationItems, notificationItems, selectedNotificationId]);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) {
        clearTimeout(toastTimerRef.current);
      }
    };
  }, []);

  const sendCodeButtonLabel = useMemo(() => {
    if (sendCodeBusy) {
      return '发送中...';
    }
    if (sendCodeCooldownSeconds > 0) {
      return `${sendCodeCooldownSeconds}s`;
    }
    return '发送验证码';
  }, [sendCodeBusy, sendCodeCooldownSeconds]);

  const sendCode = useCallback(async () => {
    if (!email.trim()) {
      showToast('请先输入邮箱地址');
      return;
    }

    if (sendCodeBusy || sendCodeCooldownSeconds > 0) {
      return;
    }

    setSendCodeBusy(true);
    try {
      const payload = await onSendCode?.(email.trim());
      setSendCodeCooldownSeconds(Math.max(1, Number(payload?.cooldownSeconds || 60)));
      showToast(payload?.message || '验证码已发送');
      triggerTouchFeedback('light');
    } catch (error) {
      showToast(`发送失败：${String(error)}`);
    } finally {
      setSendCodeBusy(false);
    }
  }, [email, onSendCode, sendCodeBusy, sendCodeCooldownSeconds, showToast, triggerTouchFeedback]);

  const login = useCallback(async () => {
    const normalizedEmail = email.trim();
    if (!normalizedEmail || !code.trim()) {
      showToast('请输入邮箱和验证码');
      return;
    }

    setBackendLoading(true);
    try {
      const loginResult = await onLogin?.(normalizedEmail, code.trim());
      const ok = typeof loginResult === 'boolean' ? loginResult : Boolean(loginResult?.ok ?? true);
      if (!ok) {
        showToast((typeof loginResult === 'object' && loginResult?.message) || '登录失败');
        return;
      }

      const nextPlan = typeof loginResult === 'object' && loginResult?.plan ? loginResult.plan : 'starter';
      const mockToken = `rn-local-${Date.now()}`;
      setAccessToken(mockToken);
      await AsyncStorage.setItem(STORAGE_KEYS.accessToken, mockToken);
      await AsyncStorage.setItem(STORAGE_KEYS.user, JSON.stringify({ email: normalizedEmail, plan: nextPlan }));
      setBackendSnapshot((prev) => ({
        ...prev,
        profile: { user: { email: normalizedEmail, plan: nextPlan } },
      }));
      setStep('construct');
      triggerTouchFeedback('light');
      showToast('登录成功，开始配置订阅');
    } catch (error) {
      showToast(`登录失败：${String(error)}`);
    } finally {
      setBackendLoading(false);
    }
  }, [code, email, onLogin, showToast, triggerTouchFeedback]);

  const addHolding = useCallback(() => {
    const symbol = newHoldSym.trim().toUpperCase();
    const shares = Number(newHoldVol || 0);
    const avgCost = Number(newHoldCost || 0);
    if (!symbol || shares <= 0 || avgCost <= 0) {
      showToast('请填写完整持仓信息');
      return;
    }

    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setHoldings((prev) => [
      ...prev,
      { symbol, name: symbol, market: symbol.includes('USDT') ? 'CRYPTO' : 'US', shares, avg_cost: avgCost },
    ]);
    setNewHoldSym('');
    setNewHoldVol('');
    setNewHoldCost('');
    triggerTouchFeedback('light');
  }, [newHoldCost, newHoldSym, newHoldVol, showToast, triggerTouchFeedback]);

  const removeHolding = useCallback((index: number) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setHoldings((prev) => prev.filter((_, i) => i !== index));
    triggerTouchFeedback('light');
  }, [triggerTouchFeedback]);

  const addSubscription = useCallback(() => {
    const symbol = newSubSym.trim().toUpperCase();
    if (!symbol) {
      showToast('请输入订阅标的');
      return;
    }

    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setSubscriptions((prev) => {
      if (prev.some((item) => item.symbol === symbol)) {
        return prev;
      }
      const market: Market = symbol.includes('USDT') ? 'CRYPTO' : symbol.endsWith('.TO') ? 'CAD' : 'US';
      return [...prev, { symbol, name: symbol, market }];
    });
    setNewSubSym('');
    triggerTouchFeedback('light');
  }, [newSubSym, showToast, triggerTouchFeedback]);

  const removeSubscription = useCallback((index: number) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setSubscriptions((prev) => prev.filter((_, i) => i !== index));
    triggerTouchFeedback('light');
  }, [triggerTouchFeedback]);

  const syncData = useCallback(async () => {
    if (!accessToken) {
      showToast('请先登录后再同步');
      return;
    }

    setBackendLoading(true);
    setBackendError('');
    try {
      const payload: SyncPayload = { cash, holdings, subscriptions };
      const remote = await onSync?.(payload);

      const nowIso = new Date().toISOString();
      const seedNotification = normalizeNotification({
        type: 'system',
        title: '订阅配置已同步',
        body: `现金 ¥${cash}，持仓 ${holdings.length} 项，订阅 ${subscriptions.length} 项。`,
        ack_required: false,
        is_read: false,
        created_at: nowIso,
      });

      const mergedNotifications = sortNotifications([seedNotification, ...notificationItems]);

      setBackendSnapshot({
        profile: remote?.profile || {
          user: {
            email: email || 'user@example.com',
            plan: remote?.profile?.user?.plan || 'starter',
          },
        },
        dashboard: remote?.dashboard || {
          subscription: {
            status: 'active',
          },
        },
        portfolio: remote?.portfolio || holdings,
        watchlist: remote?.watchlist || subscriptions,
        notifications: mergedNotifications,
      });
      await persistNotifications(mergedNotifications);

      setBackendConnected(true);
      setLastBackendSyncAt(nowIso);
      setStep('active');
      setActivePanel('overview');
      showToast('同步完成，后台监控已激活');
      triggerTouchFeedback('strong');
    } catch (error) {
      const message = String(error);
      setBackendError(message);
      setBackendConnected(false);
      showToast(`同步失败：${message}`);
    } finally {
      setBackendLoading(false);
    }
  }, [accessToken, cash, email, holdings, notificationItems, onSync, persistNotifications, showToast, subscriptions, triggerTouchFeedback]);

  const refreshNotifications = useCallback(async () => {
    setRefreshingNotifications(true);
    await loadLocalNotifications(false);
    triggerTouchFeedback('light');
    setRefreshingNotifications(false);
  }, [loadLocalNotifications, triggerTouchFeedback]);

  const markNotificationRead = useCallback(async (notificationId: string, silent = false) => {
    await updateAndPersistNotifications((items) => items.map((item) => {
      if (String(item.id) !== String(notificationId)) {
        return item;
      }
      return {
        ...item,
        is_read: true,
        opened_at: item.opened_at || new Date().toISOString(),
      };
    }));

    if (!silent) {
      showToast('已标记为已读');
      triggerTouchFeedback('light');
    }
  }, [showToast, triggerTouchFeedback, updateAndPersistNotifications]);

  const markAllNotificationsRead = useCallback(async () => {
    if (notificationItems.length === 0) {
      return;
    }
    const openedAt = new Date().toISOString();
    await updateAndPersistNotifications((items) => items.map((item) => ({
      ...item,
      is_read: true,
      opened_at: item.opened_at || openedAt,
    })));
    showToast('已将通知全部标记为已读');
    triggerTouchFeedback('strong');
  }, [notificationItems.length, showToast, triggerTouchFeedback, updateAndPersistNotifications]);

  const acknowledgeNotification = useCallback(async (notificationId: string) => {
    await updateAndPersistNotifications((items) => items.map((item) => {
      if (String(item.id) !== String(notificationId)) {
        return item;
      }
      return {
        ...item,
        is_read: true,
        acknowledged_at: new Date().toISOString(),
      };
    }));
    showToast('通知已确认');
    triggerTouchFeedback('strong');
  }, [showToast, triggerTouchFeedback, updateAndPersistNotifications]);

  const deleteNotification = useCallback(async (notificationId: string) => {
    await updateAndPersistNotifications((items) => items.filter((item) => String(item.id) !== String(notificationId)));
    if (String(selectedNotificationId) === String(notificationId)) {
      setSelectedNotificationId('');
    }
    showToast('通知已删除（本地）');
    triggerTouchFeedback('strong');
  }, [selectedNotificationId, showToast, triggerTouchFeedback, updateAndPersistNotifications]);

  const switchPanel = useCallback((panel: ActivePanel) => {
    setActivePanel(panel);
    triggerTouchFeedback('light');
  }, [triggerTouchFeedback]);

  const setScope = useCallback((scope: NotificationScope) => {
    setNotificationScope(scope);
    triggerTouchFeedback('light');
  }, [triggerTouchFeedback]);

  const openNotificationDetail = useCallback(async (id: string, markRead = false) => {
    const target = notificationItems.find((item) => String(item.id) === String(id));
    if (!target) {
      showToast('未找到该通知');
      return;
    }
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setSelectedNotificationId(String(id));
    setActivePanel('notifications');
    if (markRead && !target.is_read) {
      await markNotificationRead(String(id), true);
    }
  }, [markNotificationRead, notificationItems, showToast]);

  const enablePush = useCallback(async () => {
    setPushBusy(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 300));
      setPushConfigured(true);
      setPushEnabled(true);
      setPushStatus('推送已启用：新的信号和通知会即时抵达。');
      showToast('推送启用成功');
      triggerTouchFeedback('strong');
    } finally {
      setPushBusy(false);
    }
  }, [showToast, triggerTouchFeedback]);

  const sendPushTest = useCallback(async () => {
    const testNotification = normalizeNotification({
      type: 'push',
      title: '测试推送',
      body: '这是来自 React Native 优化版页面的测试消息。',
      ack_required: false,
      created_at: new Date().toISOString(),
    });
    await updateAndPersistNotifications((items) => [testNotification, ...items]);
    showToast('测试推送已写入本地通知');
    triggerTouchFeedback('strong');
  }, [showToast, triggerTouchFeedback, updateAndPersistNotifications]);

  const loginDisabled = !email.trim() || !code.trim() || backendLoading;

  return (
    <SafeAreaView style={styles.root}>
      <KeyboardAvoidingView
        style={styles.root}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 6 : 0}
      >
        {toast ? (
          <View style={styles.toastWrap} pointerEvents="none">
            <View style={styles.toastBubble}>
              <Text style={styles.toastText}>{toast}</Text>
            </View>
          </View>
        ) : null}

        {step === 'login' ? (
          <View style={styles.loginPage}>
            <View style={styles.loginHead}>
              <View style={styles.logoBox}>
                <Text style={styles.logoText}>A</Text>
              </View>
              <Text style={styles.title}>欢迎回来</Text>
              <Text style={styles.subtitle}>请输入您的邮箱以登录或注册您的订阅账户</Text>
            </View>

            <View style={styles.loginCard}>
              <Text style={styles.fieldLabel}>邮箱地址</Text>
              <TextInput
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
                placeholder="name@example.com"
                placeholderTextColor="#99A0B1"
                style={styles.textInput}
              />

              <Text style={[styles.fieldLabel, styles.mt12]}>验证码</Text>
              <View style={styles.rowGap8}>
                <TextInput
                  value={code}
                  onChangeText={setCode}
                  keyboardType="number-pad"
                  placeholder="6位数字"
                  placeholderTextColor="#99A0B1"
                  style={[styles.textInput, styles.flex1]}
                />
                <ScalePressable
                  disabled={sendCodeBusy || sendCodeCooldownSeconds > 0}
                  onPress={sendCode}
                  style={[
                    styles.codeButton,
                    (sendCodeBusy || sendCodeCooldownSeconds > 0) && styles.codeButtonDisabled,
                  ]}
                >
                  <Text style={styles.codeButtonText}>{sendCodeButtonLabel}</Text>
                </ScalePressable>
              </View>

              <ScalePressable
                disabled={loginDisabled}
                onPress={login}
                style={[styles.primaryButton, loginDisabled && styles.primaryButtonDisabled, styles.mt16]}
              >
                <Text style={[styles.primaryButtonText, loginDisabled && styles.primaryButtonTextDisabled]}>
                  安全登录并连接后台
                </Text>
              </ScalePressable>
            </View>
          </View>
        ) : null}

        {step === 'construct' ? (
          <View style={styles.constructPage}>
            <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
              <Text style={styles.pageTitle}>订阅配置</Text>
              <Text style={styles.pageHint}>当前离线草稿模式，登录后可一键同步到后台。</Text>

              <View style={styles.surfaceCard}>
                <Text style={styles.cardTitle}>当前可用现金</Text>
                <TextInput
                  value={cash}
                  onChangeText={setCash}
                  keyboardType="decimal-pad"
                  placeholder="0.00"
                  placeholderTextColor="#9AA3B2"
                  style={styles.cashInput}
                />
              </View>

              <View style={styles.surfaceCard}>
                <Text style={styles.cardTitle}>已持仓股票</Text>
                {holdings.map((item, idx) => (
                  <View key={`${item.symbol}-${idx}`} style={styles.listRow}>
                    <View style={styles.flex1}>
                      <Text style={styles.listMainText}>{item.symbol}</Text>
                      <Text style={styles.listSubText}>{item.shares} 股 / ${item.avg_cost.toFixed(2)}</Text>
                    </View>
                    <View style={styles.rowGap8}>
                      <Text style={styles.marketChip}>{marketLabel(item.market)}</Text>
                      <Pressable onPress={() => removeHolding(idx)}>
                        <Text style={styles.deleteX}>×</Text>
                      </Pressable>
                    </View>
                  </View>
                ))}

                <View style={styles.rowGap8}>
                  <TextInput
                    value={newHoldSym}
                    onChangeText={setNewHoldSym}
                    placeholder="代码"
                    placeholderTextColor="#9AA3B2"
                    style={[styles.textInput, styles.flex1]}
                  />
                  <TextInput
                    value={newHoldVol}
                    onChangeText={setNewHoldVol}
                    placeholder="股数"
                    keyboardType="number-pad"
                    placeholderTextColor="#9AA3B2"
                    style={[styles.textInputSmall]}
                  />
                  <TextInput
                    value={newHoldCost}
                    onChangeText={setNewHoldCost}
                    placeholder="成本"
                    keyboardType="decimal-pad"
                    placeholderTextColor="#9AA3B2"
                    style={[styles.textInputSmall]}
                  />
                  <ScalePressable onPress={addHolding} style={styles.addBtn}>
                    <Text style={styles.addBtnText}>添加</Text>
                  </ScalePressable>
                </View>
              </View>

              <View style={styles.surfaceCard}>
                <Text style={styles.cardTitle}>订阅标的</Text>
                {subscriptions.map((item, idx) => (
                  <View key={`${item.symbol}-${idx}`} style={styles.listRow}>
                    <View style={styles.flex1}>
                      <Text style={styles.listMainText}>{item.symbol}</Text>
                      <Text style={styles.listSubText}>{item.name}</Text>
                    </View>
                    <View style={styles.rowGap8}>
                      <Text style={styles.marketChip}>{marketLabel(item.market)}</Text>
                      <Pressable onPress={() => removeSubscription(idx)}>
                        <Text style={styles.deleteX}>×</Text>
                      </Pressable>
                    </View>
                  </View>
                ))}

                <View style={styles.rowGap8}>
                  <TextInput
                    value={newSubSym}
                    onChangeText={setNewSubSym}
                    placeholder="输入标的代码"
                    placeholderTextColor="#9AA3B2"
                    style={[styles.textInput, styles.flex1]}
                  />
                  <ScalePressable onPress={addSubscription} style={styles.addBtn}>
                    <Text style={styles.addBtnText}>添加</Text>
                  </ScalePressable>
                </View>
              </View>
            </ScrollView>

            <View style={styles.bottomBar}>
              <ScalePressable onPress={syncData} style={styles.syncButton}>
                <Text style={styles.syncButtonText}>开始订阅 (本地同步)</Text>
              </ScalePressable>
            </View>
          </View>
        ) : null}

        {step === 'active' ? (
          <View style={styles.activePage}>
            <View style={styles.activeHeader}>
              {activePanel === 'overview' ? (
                <View style={styles.rowBetween}>
                  <View style={styles.logoMini}>
                    <Text style={styles.logoMiniText}>A</Text>
                  </View>
                  <ScalePressable onPress={() => setStep('construct')} style={styles.ghostButton}>
                    <Text style={styles.ghostButtonText}>修改配置</Text>
                  </ScalePressable>
                </View>
              ) : (
                <View style={styles.rowBetween}>
                  <ScalePressable onPress={() => switchPanel('overview')} style={styles.ghostButtonStrong}>
                    <Text style={styles.ghostButtonStrongText}>返回总览</Text>
                  </ScalePressable>
                  <View>
                    <Text style={styles.headerMinor}>归类通知页</Text>
                    <Text style={styles.headerTitle}>通知中心</Text>
                  </View>
                </View>
              )}
            </View>

            {activePanel === 'overview' ? (
              <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
                <View style={styles.statusHero}>
                  <Text style={styles.heroTitle}>后台已接入，监控运行中</Text>
                  <Text style={styles.heroSub}>
                    现金 ¥{cash}、{holdings.length} 只持仓、{subscriptions.length} 只订阅已同步云端。
                  </Text>
                </View>

                <View style={styles.glassCard}>
                  <View style={styles.rowBetween}>
                    <Text style={styles.glassTitle}>后台连接状态</Text>
                    <Text style={styles.glassMeta}>{backendLoading ? '同步中...' : backendConnected ? '已连接' : '未连接'}</Text>
                  </View>
                  <Text style={styles.glassLine}>账号: {backendSnapshot.profile?.user.email || email || '未登录'}</Text>
                  <Text style={styles.glassLine}>订阅计划: {backendSnapshot.profile?.user.plan || '--'}</Text>
                  <Text style={styles.glassLine}>关注列表: {(backendSnapshot.watchlist || []).length} 项</Text>
                  <Text style={styles.glassLine}>持仓列表: {(backendSnapshot.portfolio || []).length} 项</Text>
                  <Text style={styles.glassLine}>通知中心: {notificationItems.length} 条</Text>
                  {backendError ? <Text style={styles.errorText}>{backendError}</Text> : null}
                </View>

                <View style={styles.glassCard}>
                  <View style={styles.rowBetween}>
                    <Text style={styles.glassTitle}>浏览器推送</Text>
                    <Text style={styles.glassMeta}>{pushBusy ? '处理中...' : pushEnabled ? '已启用' : '未启用'}</Text>
                  </View>
                  <Text style={styles.glassLine}>{pushStatus}</Text>
                  <View style={styles.rowGap8}>
                    <ScalePressable onPress={enablePush} style={styles.smallActionBtn}>
                      <Text style={styles.smallActionBtnText}>{pushEnabled ? '重新绑定当前设备' : '启用推送'}</Text>
                    </ScalePressable>
                    {pushEnabled ? (
                      <ScalePressable onPress={sendPushTest} style={styles.smallActionBtn}>
                        <Text style={styles.smallActionBtnText}>测试推送</Text>
                      </ScalePressable>
                    ) : null}
                  </View>
                </View>

                <View style={styles.glassCard}>
                  <View style={styles.rowBetween}>
                    <Text style={styles.glassTitle}>通知概览</Text>
                    <Text style={styles.heroBadge}>{unreadNotificationCount} 未读</Text>
                  </View>

                  <View style={styles.statRow}>
                    <View style={styles.statMiniCard}>
                      <Text style={styles.statMiniLabel}>全部</Text>
                      <Text style={styles.statMiniValue}>{notificationScopeCount('all')}</Text>
                    </View>
                    <View style={styles.statMiniCard}>
                      <Text style={styles.statMiniLabel}>已读</Text>
                      <Text style={styles.statMiniValue}>{notificationScopeCount('read')}</Text>
                    </View>
                    <View style={styles.statMiniCard}>
                      <Text style={styles.statMiniLabel}>待确认</Text>
                      <Text style={styles.statMiniValue}>{notificationScopeCount('pending_ack')}</Text>
                    </View>
                  </View>

                  {notificationItems.slice(0, 3).map((item) => (
                    <ScalePressable
                      key={item.id}
                      onPress={() => void openNotificationDetail(item.id, false)}
                      onLongPress={() => void deleteNotification(item.id)}
                      delayLongPress={480}
                      style={styles.overviewNoticeCard}
                    >
                      <Text style={styles.noticeTitle}>{item.title}</Text>
                      <Text style={styles.noticeBody} numberOfLines={2}>{item.body}</Text>
                      <Text style={styles.noticeTime}>{formatTime(item.created_at)}</Text>
                    </ScalePressable>
                  ))}

                  <ScalePressable onPress={() => switchPanel('notifications')} style={styles.enterNoticeBtn}>
                    <Text style={styles.enterNoticeBtnText}>进入归类通知页</Text>
                  </ScalePressable>
                </View>
              </ScrollView>
            ) : (
              <ScrollView
                contentContainerStyle={styles.scrollContent}
                showsVerticalScrollIndicator={false}
                refreshControl={<RefreshControl refreshing={refreshingNotifications} onRefresh={refreshNotifications} />}
              >
                <View style={styles.glassCard}>
                  <View style={styles.rowBetween}>
                    <View>
                      <Text style={styles.glassTitle}>通知中心</Text>
                      <Text style={styles.glassMeta}>按状态与类型归类，减少信息堆叠</Text>
                    </View>
                    <Text style={styles.heroBadge}>{notificationScopeCount('all')}</Text>
                  </View>

                  <View style={styles.scopeRow}>
                    {([
                      { key: 'all', label: '全部' },
                      { key: 'unread', label: '未读' },
                      { key: 'read', label: '已读' },
                      { key: 'pending_ack', label: '待确认' },
                    ] as { key: NotificationScope; label: string }[]).map((scope) => {
                      const active = notificationScope === scope.key;
                      return (
                        <ScalePressable
                          key={scope.key}
                          onPress={() => setScope(scope.key)}
                          style={[styles.scopeChip, active && styles.scopeChipActive]}
                        >
                          <Text style={[styles.scopeChipText, active && styles.scopeChipTextActive]}>
                            {scope.label} {notificationScopeCount(scope.key)}
                          </Text>
                        </ScalePressable>
                      );
                    })}
                  </View>

                  <View style={styles.rowGap8}>
                    <ScalePressable onPress={refreshNotifications} style={styles.smallActionBtn}>
                      <Text style={styles.smallActionBtnText}>刷新通知</Text>
                    </ScalePressable>
                    <ScalePressable onPress={markAllNotificationsRead} style={styles.smallActionBtn}>
                      <Text style={styles.smallActionBtnText}>全部标记已读</Text>
                    </ScalePressable>
                    <ScalePressable onPress={() => switchPanel('overview')} style={styles.smallActionBtn}>
                      <Text style={styles.smallActionBtnText}>返回总览</Text>
                    </ScalePressable>
                  </View>

                  <Text style={styles.longPressHint}>长按通知可删除（仅本地存储）</Text>
                </View>

                {notificationGroups.length === 0 ? (
                  <View style={styles.emptyCard}>
                    <Text style={styles.emptyText}>当前筛选下暂无通知，试试切换分类或刷新通知。</Text>
                  </View>
                ) : null}

                {notificationGroups.map((group) => (
                  <View key={group.key} style={styles.groupCard}>
                    <View style={styles.rowBetween}>
                      <Text style={styles.groupTitle}>{group.label}</Text>
                      <Text style={styles.groupCount}>{group.items.length} 条</Text>
                    </View>

                    {group.items.map((item) => {
                      const expanded = String(selectedNotification?.id) === String(item.id);
                      return (
                        <ScalePressable
                          key={item.id}
                          onPress={() => void openNotificationDetail(item.id, false)}
                          onLongPress={() => void deleteNotification(item.id)}
                          delayLongPress={480}
                          style={[styles.noticeCard, expanded && styles.noticeCardExpanded]}
                        >
                          <View style={styles.rowBetween}>
                            <Text style={styles.noticeTitle}>{item.title}</Text>
                            <Text style={styles.noticeTime}>{formatTime(item.created_at)}</Text>
                          </View>
                          <Text style={styles.noticeBody} numberOfLines={expanded ? undefined : 2}>{item.body}</Text>

                          {expanded ? (
                            <View style={styles.noticeDetailWrap}>
                              <Text style={styles.noticeDetailText}>通知ID: {item.id}</Text>
                              <Text style={styles.noticeDetailText}>状态: {item.is_read ? '已读' : '未读'}</Text>
                              <Text style={styles.noticeDetailText}>关联信号: {item.signal_id || '--'}</Text>
                              <Text style={styles.noticeDetailText}>
                                确认状态: {item.acknowledged_at ? '已确认' : item.ack_required ? '待确认' : '无需确认'}
                              </Text>

                              <View style={styles.rowGap8}>
                                <ScalePressable onPress={() => void markNotificationRead(item.id)} style={styles.smallActionBtn}>
                                  <Text style={styles.smallActionBtnText}>标记已读</Text>
                                </ScalePressable>
                                {item.ack_required && !item.acknowledged_at ? (
                                  <ScalePressable onPress={() => void acknowledgeNotification(item.id)} style={styles.ackBtn}>
                                    <Text style={styles.ackBtnText}>确认收悉</Text>
                                  </ScalePressable>
                                ) : null}
                              </View>
                            </View>
                          ) : null}
                        </ScalePressable>
                      );
                    })}
                  </View>
                ))}
              </ScrollView>
            )}
          </View>
        ) : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#0F2A5F',
  },
  toastWrap: {
    position: 'absolute',
    top: 16,
    left: 0,
    right: 0,
    alignItems: 'center',
    zIndex: 10,
  },
  toastBubble: {
    backgroundColor: '#111827',
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  toastText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  loginPage: {
    flex: 1,
    backgroundColor: '#F8FBFF',
    paddingHorizontal: 20,
    paddingTop: 18,
  },
  loginHead: {
    marginTop: 48,
    marginBottom: 24,
    gap: 10,
  },
  logoBox: {
    width: 48,
    height: 48,
    borderRadius: 16,
    backgroundColor: '#2563EB',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 22,
  },
  title: {
    fontSize: 30,
    fontWeight: '800',
    color: '#111827',
    fontFamily: FONT_DISPLAY,
    letterSpacing: -0.4,
  },
  subtitle: {
    fontSize: 13,
    lineHeight: 19,
    color: '#667085',
    fontFamily: FONT_BODY,
    letterSpacing: 0.2,
  },
  loginCard: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5EBF5',
    borderRadius: 20,
    padding: 14,
    gap: 8,
  },
  fieldLabel: {
    color: '#667085',
    fontSize: 12,
    fontWeight: '600',
    fontFamily: FONT_BODY,
    letterSpacing: 0.3,
  },
  mt12: {
    marginTop: 8,
  },
  mt16: {
    marginTop: 8,
  },
  textInput: {
    backgroundColor: '#F8FAFC',
    borderColor: '#E5E7EB',
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: '#0F172A',
    fontSize: 15,
    fontFamily: FONT_BODY,
    letterSpacing: 0.2,
  },
  textInputSmall: {
    width: 72,
    backgroundColor: '#F8FAFC',
    borderColor: '#E5E7EB',
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 10,
    paddingVertical: 12,
    color: '#0F172A',
    fontSize: 14,
    textAlign: 'center',
    fontFamily: FONT_BODY,
    letterSpacing: 0.2,
  },
  cashInput: {
    marginTop: 8,
    backgroundColor: '#F8FAFC',
    borderColor: '#E6EAF2',
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 14,
    color: '#0F172A',
    fontSize: 24,
    fontWeight: '700',
    fontFamily: FONT_DISPLAY,
    letterSpacing: -0.2,
  },
  codeButton: {
    minWidth: 96,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: '#EEF2FF',
    borderWidth: 1,
    borderColor: '#DCE4FA',
    paddingHorizontal: 10,
    paddingVertical: 10,
  },
  codeButtonDisabled: {
    opacity: 0.45,
  },
  codeButtonText: {
    color: '#334155',
    fontSize: 13,
    fontWeight: '600',
    fontFamily: FONT_BODY,
    letterSpacing: 0.2,
  },
  primaryButton: {
    backgroundColor: '#2563EB',
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
  },
  primaryButtonDisabled: {
    backgroundColor: '#E5E7EB',
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 15,
    fontFamily: FONT_DISPLAY,
    letterSpacing: 0.3,
  },
  primaryButtonTextDisabled: {
    color: '#94A3B8',
  },
  constructPage: {
    flex: 1,
    backgroundColor: '#F7FBFF',
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 120,
    gap: 12,
  },
  pageTitle: {
    color: '#0F172A',
    fontSize: 22,
    fontWeight: '800',
    fontFamily: FONT_DISPLAY,
    letterSpacing: -0.2,
  },
  pageHint: {
    color: '#64748B',
    fontSize: 12,
    marginTop: -4,
    fontFamily: FONT_BODY,
    letterSpacing: 0.2,
  },
  surfaceCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#E8EDF7',
    padding: 14,
    gap: 10,
  },
  cardTitle: {
    color: '#0F172A',
    fontSize: 15,
    fontWeight: '700',
    fontFamily: FONT_DISPLAY,
    letterSpacing: 0.1,
  },
  listRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
  },
  listMainText: {
    color: '#0F172A',
    fontWeight: '700',
    fontSize: 14,
    fontFamily: FONT_DISPLAY,
    letterSpacing: 0.1,
  },
  listSubText: {
    color: '#64748B',
    fontSize: 12,
    marginTop: 2,
    fontFamily: FONT_BODY,
    lineHeight: 18,
  },
  marketChip: {
    fontSize: 11,
    color: '#64748B',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5EAF4',
    fontFamily: FONT_BODY,
    letterSpacing: 0.2,
  },
  deleteX: {
    fontSize: 20,
    color: '#A8B0BF',
    lineHeight: 20,
    marginTop: -2,
  },
  addBtn: {
    minWidth: 64,
    borderRadius: 12,
    backgroundColor: '#0F172A',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
    paddingVertical: 11,
  },
  addBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
    fontFamily: FONT_DISPLAY,
    letterSpacing: 0.2,
  },
  rowGap8: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
  },
  flex1: {
    flex: 1,
  },
  bottomBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    borderTopWidth: 1,
    borderTopColor: '#E4EBF7',
    backgroundColor: 'rgba(248,251,255,0.95)',
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 16,
  },
  syncButton: {
    borderRadius: 16,
    backgroundColor: '#2563EB',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 15,
  },
  syncButtonText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 16,
    fontFamily: FONT_DISPLAY,
    letterSpacing: 0.35,
  },
  activePage: {
    flex: 1,
    backgroundColor: '#2563EB',
  },
  activeHeader: {
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 4,
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  logoMini: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: 'rgba(255,255,255,0.12)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoMiniText: {
    color: '#FFFFFF',
    fontWeight: '800',
  },
  ghostButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.12)',
  },
  ghostButtonText: {
    color: 'rgba(255,255,255,0.9)',
    fontSize: 12,
    fontWeight: '600',
  },
  ghostButtonStrong: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.35)',
    backgroundColor: 'rgba(255,255,255,0.14)',
  },
  ghostButtonStrongText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  headerMinor: {
    color: 'rgba(255,255,255,0.66)',
    fontSize: 11,
    textAlign: 'right',
  },
  headerTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '800',
    fontFamily: FONT_DISPLAY,
    letterSpacing: 0.2,
  },
  statusHero: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
    padding: 16,
    gap: 10,
  },
  heroTitle: {
    color: '#FFFFFF',
    fontSize: 22,
    fontWeight: '800',
    fontFamily: FONT_DISPLAY,
    letterSpacing: -0.2,
  },
  heroSub: {
    color: 'rgba(255,255,255,0.86)',
    fontSize: 14,
    lineHeight: 20,
    fontFamily: FONT_BODY,
  },
  heroBadge: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '800',
  },
  glassCard: {
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
    borderRadius: 16,
    padding: 14,
    gap: 8,
  },
  glassTitle: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
    fontFamily: FONT_DISPLAY,
  },
  glassMeta: {
    color: 'rgba(255,255,255,0.66)',
    fontSize: 11,
    fontFamily: FONT_BODY,
  },
  glassLine: {
    color: 'rgba(255,255,255,0.88)',
    fontSize: 12,
    fontFamily: FONT_BODY,
    lineHeight: 18,
  },
  errorText: {
    color: '#FECACA',
    fontSize: 12,
    marginTop: 2,
  },
  smallActionBtn: {
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.22)',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  smallActionBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
  },
  statRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 2,
  },
  statMiniCard: {
    flex: 1,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.16)',
    backgroundColor: 'rgba(255,255,255,0.06)',
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  statMiniLabel: {
    color: 'rgba(255,255,255,0.65)',
    fontSize: 11,
  },
  statMiniValue: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
    marginTop: 3,
  },
  overviewNoticeCard: {
    marginTop: 8,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.16)',
    backgroundColor: 'rgba(255,255,255,0.07)',
    padding: 10,
  },
  enterNoticeBtn: {
    marginTop: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.22)',
    backgroundColor: 'rgba(255,255,255,0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 11,
  },
  enterNoticeBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  scopeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  scopeChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.24)',
    backgroundColor: 'rgba(255,255,255,0.08)',
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  scopeChipActive: {
    backgroundColor: '#F3F4F6',
    borderColor: '#E5E7EB',
  },
  scopeChipText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
  },
  scopeChipTextActive: {
    color: '#111827',
  },
  longPressHint: {
    color: 'rgba(255,255,255,0.58)',
    fontSize: 11,
    marginTop: 2,
  },
  emptyCard: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
    backgroundColor: 'rgba(255,255,255,0.08)',
    padding: 16,
    alignItems: 'center',
  },
  emptyText: {
    color: 'rgba(255,255,255,0.72)',
    fontSize: 12,
  },
  groupCard: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
    backgroundColor: 'rgba(255,255,255,0.08)',
    padding: 12,
    gap: 8,
  },
  groupTitle: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  groupCount: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 11,
  },
  noticeCard: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.16)',
    backgroundColor: 'rgba(255,255,255,0.06)',
    padding: 10,
  },
  noticeCardExpanded: {
    borderColor: 'rgba(255,255,255,0.35)',
    backgroundColor: 'rgba(255,255,255,0.13)',
  },
  noticeTitle: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '700',
    flex: 1,
    paddingRight: 8,
    fontFamily: FONT_DISPLAY,
  },
  noticeBody: {
    color: 'rgba(255,255,255,0.82)',
    fontSize: 12,
    lineHeight: 18,
    marginTop: 4,
    fontFamily: FONT_BODY,
  },
  noticeTime: {
    color: 'rgba(255,255,255,0.58)',
    fontSize: 10,
    fontFamily: FONT_MONO,
    letterSpacing: 0.2,
  },
  noticeDetailWrap: {
    marginTop: 8,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.18)',
    paddingTop: 8,
    gap: 4,
  },
  noticeDetailText: {
    color: 'rgba(255,255,255,0.86)',
    fontSize: 11,
  },
  ackBtn: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(134,239,172,0.7)',
    backgroundColor: 'rgba(74,222,128,0.18)',
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  ackBtnText: {
    color: '#DCFCE7',
    fontWeight: '700',
    fontSize: 12,
  },
});

# Subscriber React Native Page (Optimized)

This folder keeps the existing HTML subscriber page intact and adds a React Native screen with the same information architecture:

- Login (email + code)
- Construct (cash, holdings, subscriptions)
- Active dashboard (overview + notification center)
- Local-only notification persistence and long-press delete

## File

- `SubscriberAppScreen.tsx`

## UX Improvements in RN Version

- Press-scale interaction for cards/buttons (`Animated.spring`)
- Touch feedback (`Vibration`) on key actions
- Pull-to-refresh for notification center (`RefreshControl`)
- Smooth expand/collapse transitions (`LayoutAnimation`)
- Long-press delete for notifications with stronger feedback

## Required RN Dependencies

Install these in your RN app project if not present:

```bash
npm i @react-native-async-storage/async-storage
```

## Basic Usage

```tsx
import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import SubscriberAppScreen from './frontend/app-rn/SubscriberAppScreen';

export default function App() {
  return (
    <SafeAreaProvider>
      <SubscriberAppScreen />
    </SafeAreaProvider>
  );
}
```

## Optional Backend Hooks

`SubscriberAppScreen` accepts optional props:

- `onSendCode(email)`
- `onLogin(email, code)`
- `onSync(payload)`

If not provided, the screen uses local fallback behavior for fast prototyping.

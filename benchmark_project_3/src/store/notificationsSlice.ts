import { createSlice, PayloadAction } from '@reduxjs/toolkit';

/**
 * notificationsSlice manages toast notifications and badge counts.
 * Used by OrderActions to show success/error feedback after operations.
 * Also tracks unread notification count displayed in the Dashboard header.
 * 
 * Notifications auto-dismiss after a configurable timeout.
 * The badge count is updated via WebSocket events from the server.
 * 
 * @see OrderActions.tsx - dispatches addNotification on action results
 * @see Dashboard.tsx - displays unreadCount badge
 */
interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  timestamp: number;
  dismissed: boolean;
  autoDismissMs?: number;
}

interface NotificationsState {
  toasts: Notification[];
  unreadCount: number;
  maxToasts: number;
}

const initialState: NotificationsState = {
  toasts: [],
  unreadCount: 0,
  maxToasts: 5,
};

let notificationIdCounter = 0;

const notificationsSlice = createSlice({
  name: 'notifications',
  initialState,
  reducers: {
    /**
     * Add a new toast notification. Auto-generates an ID and timestamp.
     * If max toasts exceeded, removes the oldest one.
     */
    addNotification(state, action: PayloadAction<{ type: Notification['type']; message: string; autoDismissMs?: number }>) {
      const notification: Notification = {
        id: `notif-${++notificationIdCounter}`,
        type: action.payload.type,
        message: action.payload.message,
        timestamp: Date.now(),
        dismissed: false,
        autoDismissMs: action.payload.autoDismissMs ?? 5000,
      };
      state.toasts.push(notification);
      if (state.toasts.length > state.maxToasts) {
        state.toasts.shift();
      }
    },
    dismissNotification(state, action: PayloadAction<string>) {
      const notif = state.toasts.find((n) => n.id === action.payload);
      if (notif) notif.dismissed = true;
    },
    clearAllNotifications(state) {
      state.toasts = [];
    },
    /** Update unread badge count — typically from WebSocket events */
    setUnreadCount(state, action: PayloadAction<number>) {
      state.unreadCount = action.payload;
    },
    incrementUnread(state) {
      state.unreadCount += 1;
    },
    markAllRead(state) {
      state.unreadCount = 0;
    },
  },
});

export const {
  addNotification,
  dismissNotification,
  clearAllNotifications,
  setUnreadCount,
  incrementUnread,
  markAllRead,
} = notificationsSlice.actions;

export default notificationsSlice.reducer;

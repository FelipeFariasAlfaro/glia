import { configureStore } from '@reduxjs/toolkit';
import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
import authReducer from './authSlice';
import ordersReducer from './ordersSlice';
import notificationsReducer from './notificationsSlice';
import { apiMiddleware } from './middleware/apiMiddleware';

/**
 * Redux store configuration.
 * Uses Redux Toolkit with typed hooks for dispatch and selector.
 * 
 * The apiMiddleware is added as custom middleware to handle
 * API call interception, auth headers, and token refresh.
 * 
 * @see docs/decisions/adr-001-redux-over-context.md - why Redux was chosen
 */
export const store = configureStore({
  reducer: {
    auth: authReducer,
    orders: ordersReducer,
    notifications: notificationsReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({ serializableCheck: false }).concat(apiMiddleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

/** Typed hooks for use throughout the app */
export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;

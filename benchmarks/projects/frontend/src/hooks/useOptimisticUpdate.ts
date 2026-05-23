import { useCallback } from 'react';
import { useAppDispatch } from '../store';

/**
 * useOptimisticUpdate provides optimistic UI update functionality with rollback.
 * 
 * When an action is performed (e.g., cancel order), this hook:
 * 1. Immediately dispatches the optimistic update to Redux (shows new state)
 * 2. Calls the API in the background
 * 3. On failure, dispatches the rollback action to revert the state
 * 
 * CRITICAL COUPLING: The rollback mechanism dispatches actions to ordersSlice.
 * It assumes a specific slice shape (e.g., items array with status field).
 * If the ordersSlice shape changes (e.g., renaming 'items' to 'orders',
 * or changing the status update reducer), the rollback will dispatch an
 * action that silently does nothing — the UI stays in the optimistic state
 * even though the API call failed.
 * 
 * This is a fragile coupling that has no runtime validation.
 * 
 * @see ordersSlice.ts - target of optimistic/rollback dispatches
 * @see OrderActions.tsx - primary consumer of this hook
 */
interface OptimisticUpdateConfig {
  /** Action to dispatch immediately for optimistic UI */
  optimisticUpdate: { type: string; payload: any };
  /** API call to execute in background */
  apiCall: () => Promise<any>;
  /** Action to dispatch if API call fails (rollback) */
  rollbackUpdate: { type: string; payload: any };
  /** Optional callback on success */
  onSuccess?: (result: any) => void;
  /** Optional callback on failure */
  onError?: (error: Error) => void;
}

interface OptimisticUpdateResult {
  execute: (config: OptimisticUpdateConfig) => Promise<any>;
  executeMultiple: (configs: OptimisticUpdateConfig[]) => Promise<any[]>;
}

export function useOptimisticUpdate(): OptimisticUpdateResult {
  const dispatch = useAppDispatch();

  /**
   * Execute a single optimistic update with rollback on failure.
   * Dispatches optimisticUpdate immediately, then calls API.
   * On failure, dispatches rollbackUpdate to revert.
   * 
   * WARNING: If ordersSlice reducer shape changes, rollback silently fails.
   */
  const execute = useCallback(async (config: OptimisticUpdateConfig): Promise<any> => {
    const { optimisticUpdate, apiCall, rollbackUpdate, onSuccess, onError } = config;

    // Step 1: Apply optimistic update immediately
    dispatch(optimisticUpdate);

    try {
      // Step 2: Execute the actual API call
      const result = await apiCall();
      onSuccess?.(result);
      return result;
    } catch (error: any) {
      // Step 3: Rollback on failure — dispatches to ordersSlice
      // If slice shape changed, this dispatch may be a no-op
      dispatch(rollbackUpdate);
      onError?.(error);
      throw error;
    }
  }, [dispatch]);

  /** Execute multiple optimistic updates in parallel */
  const executeMultiple = useCallback(async (configs: OptimisticUpdateConfig[]): Promise<any[]> => {
    return Promise.all(configs.map((config) => execute(config)));
  }, [execute]);

  return { execute, executeMultiple };
}

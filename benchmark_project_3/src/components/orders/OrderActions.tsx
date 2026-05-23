import React, { useCallback, useState } from 'react';
import { useAppSelector, useAppDispatch } from '../../store';
import { selectUserPermissions } from '../../store/authSlice';
import { useOptimisticUpdate } from '../../hooks/useOptimisticUpdate';
import { cancelOrder, refundOrder, resendOrder } from '../../api/orders';
import { addNotification } from '../../store/notificationsSlice';

/**
 * OrderActions renders action buttons (cancel, refund, resend) for an order.
 * 
 * IMPORTANT: This component performs its OWN permission checks independently
 * from ProtectedRoute. It reads permissions from authSlice.permissions and
 * checks for specific action permissions like 'orders:cancel', 'orders:refund'.
 * 
 * If the permission model changes (e.g., switching from flat strings to
 * hierarchical permissions), BOTH ProtectedRoute and this component need
 * updating. They share the same permission source but check independently.
 * 
 * Uses useOptimisticUpdate for immediate UI feedback on actions.
 * The optimistic update dispatches to ordersSlice — if the slice shape
 * changes, the rollback mechanism may silently fail.
 * 
 * @see ProtectedRoute.tsx - also checks permissions from authSlice
 * @see useOptimisticUpdate.ts - handles optimistic UI with rollback
 * @see ordersSlice.ts - rollback target for failed operations
 */
interface OrderActionsProps {
  orderId: string;
  orderStatus: string;
}

export const OrderActions: React.FC<OrderActionsProps> = ({ orderId, orderStatus }) => {
  const dispatch = useAppDispatch();
  const permissions = useAppSelector(selectUserPermissions);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const { execute: executeOptimistic } = useOptimisticUpdate();

  /** Independent permission check — mirrors logic in ProtectedRoute */
  const canCancel = permissions.includes('orders:cancel') && ['pending', 'processing'].includes(orderStatus);
  const canRefund = permissions.includes('orders:refund') && ['delivered', 'shipped'].includes(orderStatus);
  const canResend = permissions.includes('orders:resend') && orderStatus === 'delivered';

  const handleAction = useCallback(async (action: 'cancel' | 'refund' | 'resend') => {
    setActionInProgress(action);
    const apiCall = { cancel: cancelOrder, refund: refundOrder, resend: resendOrder }[action];
    const newStatus = { cancel: 'cancelled', refund: 'refunded', resend: 'resending' }[action];

    try {
      await executeOptimistic({
        optimisticUpdate: { type: 'orders/updateOrderStatus', payload: { orderId, status: newStatus } },
        apiCall: () => apiCall(orderId),
        rollbackUpdate: { type: 'orders/updateOrderStatus', payload: { orderId, status: orderStatus } },
      });
      dispatch(addNotification({ type: 'success', message: `Order ${action} successful` }));
    } catch (error: any) {
      dispatch(addNotification({ type: 'error', message: `Failed to ${action} order: ${error.message}` }));
    } finally {
      setActionInProgress(null);
    }
  }, [orderId, orderStatus, executeOptimistic, dispatch]);

  return (
    <div className="order-actions" role="group" aria-label="Order actions">
      {canCancel && (
        <button onClick={() => handleAction('cancel')} disabled={!!actionInProgress} className="btn-danger">
          {actionInProgress === 'cancel' ? 'Cancelling...' : 'Cancel Order'}
        </button>
      )}
      {canRefund && (
        <button onClick={() => handleAction('refund')} disabled={!!actionInProgress} className="btn-warning">
          {actionInProgress === 'refund' ? 'Processing...' : 'Refund Order'}
        </button>
      )}
      {canResend && (
        <button onClick={() => handleAction('resend')} disabled={!!actionInProgress} className="btn-primary">
          {actionInProgress === 'resend' ? 'Resending...' : 'Resend Order'}
        </button>
      )}
      {!canCancel && !canRefund && !canResend && (
        <p className="no-actions">No actions available for this order status.</p>
      )}
    </div>
  );
};

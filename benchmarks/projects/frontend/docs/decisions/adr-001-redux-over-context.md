# ADR-001: Redux Toolkit Over React Context for State Management

**Status**: Accepted  
**Date**: 2023-11-15  
**Decision Makers**: Frontend Team Lead, Senior Engineers

## Context

We needed a state management solution for our order management SPA. The application has:
- Complex auth state with token refresh logic
- Real-time data via WebSocket that updates multiple components
- Optimistic updates with rollback capability
- Middleware needs (API interception, retry logic, auth headers)

Options considered:
1. React Context + useReducer
2. Redux Toolkit
3. Zustand
4. Jotai/Recoil

## Decision

We chose **Redux Toolkit** for the following reasons:

### Middleware Support

The `apiMiddleware` pattern was critical for our auth flow. We needed to:
- Intercept all API-related actions
- Attach auth headers automatically
- Handle 401 responses with token refresh
- Queue requests during refresh
- Retry failed requests with exponential backoff

React Context has no middleware concept. We would have needed to build this into every API call or create a custom wrapper.

### DevTools and Debugging

Redux DevTools provide time-travel debugging, action logging, and state diff visualization. This was invaluable during the [2024-04 infinite refresh incident](../incidents/2024-04-infinite-refresh.md) — we could see the infinite action dispatch loop in DevTools.

### Optimistic Updates with Rollback

Our `useOptimisticUpdate` hook dispatches actions to the store for immediate UI feedback, then rolls back on failure. This pattern requires:
- Predictable state updates (reducers)
- Ability to dispatch rollback actions
- State shape that supports targeted updates

Context's setState doesn't provide the same granular control.

### Performance

With React Context, any state change re-renders all consumers. Redux's `useSelector` with shallow equality checks prevents unnecessary re-renders. Given our real-time WebSocket data updating frequently, this was important.

## Consequences

### Positive
- Clean middleware pattern for API interception
- Excellent debugging with DevTools
- Predictable state updates via reducers
- Good TypeScript support with Redux Toolkit

### Negative
- More boilerplate than Context (mitigated by Redux Toolkit)
- Team needs Redux knowledge
- Serializable state constraint (disabled for our use case)
- Two refresh mechanisms exist (middleware + Axios interceptor) — added complexity

### Risks
- Optimistic rollback is tightly coupled to slice shape — fragile
- Permission checks duplicated between ProtectedRoute and OrderActions
- Feature flags affect both Redux thunks and route config — coordination needed

## Alternatives Not Chosen

**Zustand**: Simpler API but lacks middleware pattern we needed for apiMiddleware.  
**React Context**: No middleware, performance concerns with frequent WebSocket updates.  
**Jotai/Recoil**: Atomic state model doesn't fit our interconnected auth/orders/notifications state.

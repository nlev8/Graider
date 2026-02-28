import { useReducer, useCallback, useRef } from 'react'
import { getAuthHeaders } from '../services/api'

const API_BASE = ''

// ─── State shape ───
const initialState = {
  sessionActive: false,
  sessionStartTime: null,
  period: '',
  date: new Date().toISOString().slice(0, 10),
  // Pending events from STT detection (teacher must approve)
  pendingEvents: [],
  // Approved events for this session
  sessionEvents: [],
  // Cumulative data from backend
  cumulativeData: {},
  // View toggle
  viewMode: 'session', // 'session' | 'cumulative'
  loading: false,
  error: null,
}

// ─── Actions ───
const ACTION = {
  START_SESSION: 'START_SESSION',
  END_SESSION: 'END_SESSION',
  SET_PERIOD: 'SET_PERIOD',
  SET_DATE: 'SET_DATE',
  ADD_PENDING: 'ADD_PENDING',
  APPROVE_PENDING: 'APPROVE_PENDING',
  EDIT_PENDING: 'EDIT_PENDING',
  DISMISS_PENDING: 'DISMISS_PENDING',
  ADD_EVENT: 'ADD_EVENT',
  REMOVE_EVENT: 'REMOVE_EVENT',
  INCREMENT: 'INCREMENT',
  DECREMENT: 'DECREMENT',
  SET_CUMULATIVE: 'SET_CUMULATIVE',
  SET_VIEW: 'SET_VIEW',
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  RESTORE_SESSION: 'RESTORE_SESSION',
}

function reducer(state, action) {
  switch (action.type) {
    case ACTION.START_SESSION:
      return { ...state, sessionActive: true, sessionStartTime: Date.now(), sessionEvents: [], pendingEvents: [], error: null }
    case ACTION.END_SESSION:
      return { ...state, sessionActive: false, sessionStartTime: null }
    case ACTION.SET_PERIOD:
      return { ...state, period: action.payload }
    case ACTION.SET_DATE:
      return { ...state, date: action.payload }
    case ACTION.ADD_PENDING:
      return { ...state, pendingEvents: [...state.pendingEvents, { ...action.payload, id: Date.now() + Math.random() }] }
    case ACTION.APPROVE_PENDING: {
      const evt = state.pendingEvents.find(e => e.id === action.payload)
      if (!evt) return state
      return {
        ...state,
        pendingEvents: state.pendingEvents.filter(e => e.id !== action.payload),
        sessionEvents: [...state.sessionEvents, { ...evt, approved: true }],
      }
    }
    case ACTION.EDIT_PENDING:
      return {
        ...state,
        pendingEvents: state.pendingEvents.map(e => e.id === action.payload.id ? { ...e, ...action.payload.changes } : e),
      }
    case ACTION.DISMISS_PENDING:
      return { ...state, pendingEvents: state.pendingEvents.filter(e => e.id !== action.payload) }
    case ACTION.ADD_EVENT:
      return { ...state, sessionEvents: [...state.sessionEvents, { ...action.payload, id: Date.now() + Math.random(), approved: true }] }
    case ACTION.REMOVE_EVENT: {
      const idx = state.sessionEvents.findLastIndex(
        e => e.student_name === action.payload.student_name && e.type === action.payload.type
      )
      if (idx === -1) return state
      const next = [...state.sessionEvents]
      next.splice(idx, 1)
      return { ...state, sessionEvents: next }
    }
    case ACTION.INCREMENT:
      return {
        ...state,
        sessionEvents: [
          ...state.sessionEvents,
          {
            id: Date.now() + Math.random(),
            student_name: action.payload.student_name,
            student_id: action.payload.student_id,
            type: action.payload.type,
            note: '',
            timestamp: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
            period: state.period,
            approved: true,
          },
        ],
      }
    case ACTION.DECREMENT: {
      const di = state.sessionEvents.findLastIndex(
        e => e.student_name === action.payload.student_name && e.type === action.payload.type
      )
      if (di === -1) return state
      const dn = [...state.sessionEvents]
      dn.splice(di, 1)
      return { ...state, sessionEvents: dn }
    }
    case ACTION.SET_CUMULATIVE:
      return { ...state, cumulativeData: action.payload }
    case ACTION.SET_VIEW:
      return { ...state, viewMode: action.payload }
    case ACTION.SET_LOADING:
      return { ...state, loading: action.payload }
    case ACTION.SET_ERROR:
      return { ...state, error: action.payload }
    case ACTION.RESTORE_SESSION:
      return { ...state, ...action.payload }
    default:
      return state
  }
}

// ─── LocalStorage backup key ───
const LS_KEY = 'graider_behavior_session'

export function useBehaviorStore() {
  const [state, dispatch] = useReducer(reducer, initialState, (init) => {
    // Restore from localStorage if tab was closed mid-session
    try {
      const saved = localStorage.getItem(LS_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (parsed.sessionActive) {
          return { ...init, ...parsed }
        }
      }
    } catch { /* ignore */ }
    return init
  })

  const saveTimeoutRef = useRef(null)

  // Debounced localStorage backup
  const backupToLocalStorage = useCallback((newState) => {
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(() => {
      if (newState.sessionActive) {
        localStorage.setItem(LS_KEY, JSON.stringify({
          sessionActive: newState.sessionActive,
          sessionStartTime: newState.sessionStartTime,
          period: newState.period,
          date: newState.date,
          sessionEvents: newState.sessionEvents,
          pendingEvents: newState.pendingEvents,
        }))
      } else {
        localStorage.removeItem(LS_KEY)
      }
    }, 500)
  }, [])

  // Wrap dispatch to auto-backup
  const d = useCallback((action) => {
    dispatch(action)
    // We need current state after dispatch — use a microtask
    setTimeout(() => {
      // Read from the reducer by dispatching a no-op won't work,
      // so we backup based on the action type
      if (action.type === ACTION.END_SESSION) {
        localStorage.removeItem(LS_KEY)
      }
    }, 0)
  }, [])

  // ─── API calls ───

  const saveSession = useCallback(async (events, period, date) => {
    dispatch({ type: ACTION.SET_LOADING, payload: true })
    try {
      const headers = await getAuthHeaders()
      const resp = await fetch(API_BASE + '/api/behavior/session', {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ events, period, date }),
      })
      const data = await resp.json()
      if (data.error) {
        dispatch({ type: ACTION.SET_ERROR, payload: data.error })
        return false
      }
      localStorage.removeItem(LS_KEY)
      return true
    } catch (e) {
      dispatch({ type: ACTION.SET_ERROR, payload: e.message })
      return false
    } finally {
      dispatch({ type: ACTION.SET_LOADING, payload: false })
    }
  }, [])

  const loadCumulative = useCallback(async (filters = {}) => {
    dispatch({ type: ACTION.SET_LOADING, payload: true })
    try {
      const headers = await getAuthHeaders()
      const params = new URLSearchParams()
      if (filters.student_name) params.set('student_name', filters.student_name)
      if (filters.period) params.set('period', filters.period)
      if (filters.date_from) params.set('date_from', filters.date_from)
      if (filters.date_to) params.set('date_to', filters.date_to)
      const resp = await fetch(API_BASE + '/api/behavior/data?' + params.toString(), { headers })
      const data = await resp.json()
      if (data.error) {
        dispatch({ type: ACTION.SET_ERROR, payload: data.error })
      } else {
        dispatch({ type: ACTION.SET_CUMULATIVE, payload: data.data || {} })
      }
    } catch (e) {
      dispatch({ type: ACTION.SET_ERROR, payload: e.message })
    } finally {
      dispatch({ type: ACTION.SET_LOADING, payload: false })
    }
  }, [])

  // ─── Action creators ───

  const startSession = useCallback((period) => {
    dispatch({ type: ACTION.SET_PERIOD, payload: period || '' })
    dispatch({ type: ACTION.SET_DATE, payload: new Date().toISOString().slice(0, 10) })
    dispatch({ type: ACTION.START_SESSION })
  }, [])

  const endSession = useCallback(async () => {
    // Save approved events to backend
    if (state.sessionEvents.length > 0) {
      const events = state.sessionEvents.map(e => ({
        student_id: e.student_id || e.student_name.toLowerCase().replace(/\s+/g, '_'),
        student_name: e.student_name,
        type: e.type,
        note: e.note || '',
        timestamp: e.timestamp || '',
        period: e.period || state.period,
      }))
      await saveSession(events, state.period, state.date)
    }
    dispatch({ type: ACTION.END_SESSION })
    localStorage.removeItem(LS_KEY)
  }, [state.sessionEvents, state.period, state.date, saveSession])

  const addPending = useCallback((event) => {
    dispatch({ type: ACTION.ADD_PENDING, payload: event })
  }, [])

  const approvePending = useCallback((id) => {
    dispatch({ type: ACTION.APPROVE_PENDING, payload: id })
  }, [])

  const editPending = useCallback((id, changes) => {
    dispatch({ type: ACTION.EDIT_PENDING, payload: { id, changes } })
  }, [])

  const dismissPending = useCallback((id) => {
    dispatch({ type: ACTION.DISMISS_PENDING, payload: id })
  }, [])

  const addManualEvent = useCallback((event) => {
    dispatch({ type: ACTION.ADD_EVENT, payload: event })
  }, [])

  const increment = useCallback((student_name, student_id, type) => {
    dispatch({ type: ACTION.INCREMENT, payload: { student_name, student_id, type } })
  }, [])

  const decrement = useCallback((student_name, student_id, type) => {
    dispatch({ type: ACTION.DECREMENT, payload: { student_name, student_id, type } })
  }, [])

  const setViewMode = useCallback((mode) => {
    dispatch({ type: ACTION.SET_VIEW, payload: mode })
  }, [])

  // Backup on every state change when session is active
  // (called externally after re-render)

  return {
    state,
    startSession,
    endSession,
    addPending,
    approvePending,
    editPending,
    dismissPending,
    addManualEvent,
    increment,
    decrement,
    setViewMode,
    loadCumulative,
    saveSession,
  }
}

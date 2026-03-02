/* ═══════════════════════════════════════════════════════════
   STATE — Lightweight reactive store (pub/sub)
   ═══════════════════════════════════════════════════════════ */

const state = {
  currentView: 'welcome',       // 'welcome' | 'chat'
  conversationId: null,
  conversations: [],             // [{id, title, updated_at}]
  messages: [],                  // [{role, content, meta?}]
  isStreaming: false,
  streamingText: '',
  streamingToolCalls: [],
  sidebarOpen: false,
  health: { status: 'unknown' },
};

const listeners = new Map();

/**
 * Subscribe to state changes for a specific key.
 * Returns an unsubscribe function.
 */
export function subscribe(key, fn) {
  if (!listeners.has(key)) listeners.set(key, new Set());
  listeners.get(key).add(fn);
  return () => listeners.get(key).delete(fn);
}

/**
 * Update state and notify subscribers for changed keys.
 */
export function setState(updates) {
  const changedKeys = [];
  for (const [key, value] of Object.entries(updates)) {
    if (state[key] !== value) {
      state[key] = value;
      changedKeys.push(key);
    }
  }
  for (const key of changedKeys) {
    if (listeners.has(key)) {
      for (const fn of listeners.get(key)) {
        try { fn(state[key], state); } catch (e) { console.error(`State listener error [${key}]:`, e); }
      }
    }
  }
}

/**
 * Get current state (read-only snapshot).
 */
export function getState() {
  return { ...state };
}

/**
 * Get a single state value.
 */
export function get(key) {
  return state[key];
}

/**
 * Push a message to the messages array and notify.
 */
export function pushMessage(msg) {
  state.messages = [...state.messages, msg];
  if (listeners.has('messages')) {
    for (const fn of listeners.get('messages')) {
      try { fn(state.messages, state); } catch (e) { console.error('State listener error [messages]:', e); }
    }
  }
}

/**
 * Update the last message in the array (for streaming).
 */
export function updateLastMessage(updates) {
  if (state.messages.length === 0) return;
  const last = { ...state.messages[state.messages.length - 1], ...updates };
  state.messages = [...state.messages.slice(0, -1), last];
  // Don't notify for every token — caller handles DOM updates directly
}

/**
 * Persist conversation ID to sessionStorage.
 */
export function persistConversation() {
  if (state.conversationId) {
    sessionStorage.setItem('af_conversation_id', state.conversationId);
  } else {
    sessionStorage.removeItem('af_conversation_id');
  }
}

/**
 * Restore conversation ID from sessionStorage.
 */
export function restoreConversation() {
  return sessionStorage.getItem('af_conversation_id');
}

/**
 * Save verification metadata for a conversation in localStorage.
 * Appends to existing array (one entry per assistant message).
 */
export function saveVerificationMeta(conversationId, meta) {
  if (!conversationId || !meta) return;
  const key = `af_meta_${conversationId}`;
  try {
    const existing = JSON.parse(localStorage.getItem(key) || '[]');
    existing.push(meta);
    localStorage.setItem(key, JSON.stringify(existing));
  } catch { /* ignore storage errors */ }
}

/**
 * Load cached verification metadata for a conversation.
 * Returns array of meta objects (one per assistant message, in order).
 */
export function loadVerificationMeta(conversationId) {
  if (!conversationId) return [];
  try {
    return JSON.parse(localStorage.getItem(`af_meta_${conversationId}`) || '[]');
  } catch { return []; }
}

/**
 * Clear cached verification metadata for a conversation.
 */
export function clearVerificationMeta(conversationId) {
  if (!conversationId) return;
  localStorage.removeItem(`af_meta_${conversationId}`);
}

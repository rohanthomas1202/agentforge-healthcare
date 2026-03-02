/* ═══════════════════════════════════════════════════════════
   API CLIENT — Port of frontend/api_client.py to browser JS
   ═══════════════════════════════════════════════════════════ */

const API_BASE = '';  // Same origin (relative paths)
const CHAT_TIMEOUT = 90000;
const HEALTH_TIMEOUT = 5000;

function headers() {
  const h = { 'Content-Type': 'application/json' };
  const apiKey = document.querySelector('meta[name="api-key"]')?.content;
  if (apiKey) h['X-API-Key'] = apiKey;
  return h;
}

/**
 * POST /api/chat — Non-streaming chat (fallback)
 */
export async function sendMessage(message, conversationId = null) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CHAT_TIMEOUT);
  try {
    const resp = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ message, conversation_id: conversationId }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') return { error: 'Request timed out' };
    return { error: err.message };
  }
}

/**
 * POST /api/chat/stream — SSE streaming via fetch + ReadableStream
 */
export async function streamMessage(message, conversationId, callbacks = {}) {
  const { onThinking, onToolCall, onToken, onDone, onError } = callbacks;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CHAT_TIMEOUT);

  try {
    const resp = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ message, conversation_id: conversationId }),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!resp.ok) {
      onError?.({ message: `HTTP ${resp.status}` });
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let yieldCounter = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete last line

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;

        try {
          const parsed = JSON.parse(trimmed.slice(6));
          const { event, data } = parsed;

          switch (event) {
            case 'thinking': onThinking?.(data); break;
            case 'tool_call': onToolCall?.(data); break;
            case 'token':     onToken?.(data); break;
            case 'done':      onDone?.(data); break;
            case 'error':     onError?.(data); break;
          }
        } catch {
          // Skip malformed lines
        }
      }

      // Yield to the browser event loop periodically so rAF/rendering can run.
      // Every 20 chunks keeps the UI responsive without adding visible pauses.
      if (++yieldCounter % 20 === 0) {
        await new Promise(r => setTimeout(r, 0));
      }
    }
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') {
      onError?.({ message: 'Request timed out' });
    } else {
      onError?.({ message: err.message || 'Connection error' });
    }
  }
}

/**
 * POST /api/feedback
 */
export async function sendFeedback(conversationId, rating, comment = null) {
  try {
    const resp = await fetch(`${API_BASE}/api/feedback`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ conversation_id: conversationId, rating, comment }),
    });
    return await resp.json();
  } catch {
    return { status: 'error' };
  }
}

/**
 * GET /api/conversations
 */
export async function getConversations() {
  try {
    const resp = await fetch(`${API_BASE}/api/conversations`, { headers: headers() });
    if (!resp.ok) return [];
    return await resp.json();
  } catch {
    return [];
  }
}

/**
 * GET /api/conversations/:id
 */
export async function getConversation(id) {
  try {
    const resp = await fetch(`${API_BASE}/api/conversations/${id}`, { headers: headers() });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

/**
 * DELETE /api/conversations/:id
 */
export async function deleteConversation(id) {
  try {
    const resp = await fetch(`${API_BASE}/api/conversations/${id}`, {
      method: 'DELETE',
      headers: headers(),
    });
    return await resp.json();
  } catch {
    return { status: 'error' };
  }
}

/**
 * GET /api/health
 */
export async function checkHealth() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT);
  try {
    const resp = await fetch(`${API_BASE}/api/health`, {
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!resp.ok) return { status: 'error' };
    return await resp.json();
  } catch {
    clearTimeout(timer);
    return { status: 'error' };
  }
}

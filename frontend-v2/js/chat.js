/* ═══════════════════════════════════════════════════════════
   CHAT — Message rendering, SSE streaming, input handling
   ═══════════════════════════════════════════════════════════ */

import { getState, setState, pushMessage, updateLastMessage, persistConversation, saveVerificationMeta, loadVerificationMeta } from './state.js';
import * as api from './api.js';
import { renderMarkdown, escapeHtml } from './utils.js';
import { renderVerification, renderFeedback } from './verification.js';

let messagesContainer = null;
let chatInput = null;
let sendBtn = null;
let onStreamComplete = null;

/**
 * Initialize chat interface.
 */
export function initChat({ onComplete }) {
  messagesContainer = document.getElementById('messages');
  chatInput = document.getElementById('chat-input');
  sendBtn = document.getElementById('send-btn');
  onStreamComplete = onComplete;

  // Auto-grow textarea
  chatInput?.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + 'px';
    updateSendButton();
  });

  // Send on Enter (Shift+Enter for newline)
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Send button click
  sendBtn?.addEventListener('click', handleSend);
}

/**
 * Send a message from an external trigger (suggestion card, example).
 */
export function sendQuery(query) {
  if (getState().isStreaming) return;
  handleSendWithText(query);
}

/**
 * Load and render a conversation history.
 */
export async function loadConversation(conversationId) {
  const data = await api.getConversation(conversationId);
  if (!data || !data.messages) return;

  setState({
    conversationId,
    messages: data.messages,
    currentView: 'chat',
  });
  persistConversation();
  renderAllMessages();
}

/**
 * Clear the chat for a new conversation.
 */
export function clearChat() {
  setState({
    conversationId: null,
    messages: [],
    isStreaming: false,
    streamingText: '',
    streamingToolCalls: [],
    currentView: 'welcome',
  });
  persistConversation();
  if (messagesContainer) messagesContainer.innerHTML = '';
}

// ── Internal ────────────────────────────────────────────────

function updateSendButton() {
  const hasText = chatInput?.value.trim().length > 0;
  const isStreaming = getState().isStreaming;
  if (sendBtn) {
    sendBtn.disabled = !hasText || isStreaming;
    sendBtn.classList.toggle('active', hasText && !isStreaming);
  }
}

function handleSend() {
  const text = chatInput?.value.trim();
  if (!text || getState().isStreaming) return;
  chatInput.value = '';
  chatInput.style.height = 'auto';
  updateSendButton();
  handleSendWithText(text);
}

async function handleSendWithText(text) {
  // Switch to chat view
  setState({ currentView: 'chat' });

  // Add user message
  pushMessage({ role: 'user', content: text });
  appendMessageToDOM({ role: 'user', content: text }, true);

  // Prepare streaming assistant message
  setState({ isStreaming: true, streamingText: '', streamingToolCalls: [] });
  updateSendButton();

  const assistantEl = createStreamingAssistantBubble();
  const contentEl = assistantEl.querySelector('.message-content');
  const toolStatusEl = assistantEl.querySelector('.tool-status-area');

  let fullText = '';
  let conversationId = getState().conversationId;
  let metadata = null;
  let dotsRemoved = false;

  // ── Typewriter animation state ──
  // Tokens arrive in bursts from the network. Instead of rendering them
  // all at once (choppy), we queue them and drain at a steady rate via
  // requestAnimationFrame — like a typewriter that never stutters.
  let displayedText = '';     // What's currently shown on screen
  let streamTextNode = null;  // The <span> we write into
  let animFrameId = null;     // rAF handle for the drain loop
  let mdFlushTimer = null;    // Periodic markdown formatting flush
  const MD_FLUSH_MS = 800;    // Flush markdown every 800ms
  const CHARS_PER_FRAME = 3;  // ~180 chars/sec at 60fps — fast but smooth
  let streamDone = false;     // Set true when SSE stream ends

  function ensureStreamNode() {
    if (!streamTextNode) {
      contentEl.textContent = '';
      const rawSpan = document.createElement('span');
      rawSpan.className = 'streaming-raw';
      contentEl.appendChild(rawSpan);
      streamTextNode = rawSpan;
      const cursor = document.createElement('span');
      cursor.className = 'streaming-cursor';
      contentEl.appendChild(cursor);
    }
  }

  function drainQueue() {
    const remaining = fullText.length - displayedText.length;
    if (remaining <= 0) {
      animFrameId = null;
      // If the stream is done and we've caught up, do the final markdown render
      if (streamDone) finishRender();
      return;
    }

    // Speed up if the queue is getting long (catch up without stalling)
    const burst = remaining > 60 ? Math.ceil(remaining / 8) :
                  remaining > 20 ? CHARS_PER_FRAME * 2 :
                  CHARS_PER_FRAME;
    displayedText = fullText.slice(0, displayedText.length + burst);

    ensureStreamNode();
    streamTextNode.textContent = displayedText;
    scrollToBottom();

    animFrameId = requestAnimationFrame(drainQueue);
  }

  function startDrain() {
    if (!animFrameId) {
      animFrameId = requestAnimationFrame(drainQueue);
    }
  }

  function finishRender() {
    if (mdFlushTimer) { clearInterval(mdFlushTimer); mdFlushTimer = null; }
    if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }
    streamTextNode = null;
    contentEl.innerHTML = renderMarkdown(fullText);
    scrollToBottom();
  }

  try {
    try {
      await api.streamMessage(text, conversationId, {
        onThinking: (data) => {
          if (data.conversation_id) {
            conversationId = data.conversation_id;
            setState({ conversationId });
            persistConversation();
          }
          showStreamingDots(contentEl);
        },

        onToolCall: (data) => {
          removeStreamingDots(contentEl);
          dotsRemoved = true;
          addToolStatus(toolStatusEl, data.tool);
        },

        onToken: (data) => {
          if (!dotsRemoved) {
            removeStreamingDots(contentEl);
            dotsRemoved = true;
          }
          fullText += data.text;

          // Kick the typewriter drain loop (no-op if already running)
          startDrain();

          // Start periodic markdown flush so formatting appears progressively
          if (!mdFlushTimer) {
            mdFlushTimer = setInterval(() => {
              if (!contentEl) return;
              // Flush only what's been displayed so far
              contentEl.innerHTML = renderMarkdown(displayedText) + '<span class="streaming-cursor"></span>';
              streamTextNode = null; // Will be recreated by drainQueue
              scrollToBottom();
            }, MD_FLUSH_MS);
          }
        },

        onDone: (data) => {
          fullText = data.response || fullText;
          metadata = data;
          streamDone = true;

          // If the typewriter has already caught up, render now
          if (displayedText.length >= fullText.length) {
            finishRender();
          }
          // Otherwise drainQueue will call finishRender when it catches up

          // Collapse tool status into summary
          collapseToolStatus(toolStatusEl, data.tool_calls);
        },

        onError: (data) => {
          if (mdFlushTimer) { clearInterval(mdFlushTimer); mdFlushTimer = null; }
          if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }
          contentEl.innerHTML = `<p style="color: var(--confidence-low)">Error: ${escapeHtml(data.message)}</p>`;
        },
      });
    } catch {
      // Clean up streaming state before fallback
      if (mdFlushTimer) { clearInterval(mdFlushTimer); mdFlushTimer = null; }
      if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }
      streamTextNode = null;

      // Fallback to non-streaming
      try {
        const response = await api.sendMessage(text, conversationId);
        if (response.error) {
          contentEl.innerHTML = `<p style="color: var(--confidence-low)">Error: ${escapeHtml(response.error)}</p>`;
        } else {
          fullText = response.response;
          metadata = response;
          conversationId = response.conversation_id;
          setState({ conversationId });
          persistConversation();
          contentEl.innerHTML = renderMarkdown(fullText);
        }
      } catch (e) {
        contentEl.innerHTML = `<p style="color: var(--confidence-low)">Connection error. Is the backend running?</p>`;
      }
    }

    // Finalize
    removeStreamingDots(contentEl);
    const cursor = contentEl?.querySelector('.streaming-cursor');
    if (cursor) cursor.remove();

    // Save message with metadata
    const assistantMsg = { role: 'assistant', content: fullText, meta: metadata };
    pushMessage(assistantMsg);

    // Render verification + feedback
    if (metadata) {
      saveVerificationMeta(conversationId, metadata);
      const metaContainer = assistantEl?.querySelector('.message-meta-area');
      if (metaContainer) {
        renderVerification(metaContainer, metadata);
        renderFeedback(metaContainer, conversationId);
      }
    }
  } finally {
    // Always clean up — even if DOM updates above throw
    if (mdFlushTimer) { clearInterval(mdFlushTimer); mdFlushTimer = null; }
    if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }
    setState({ isStreaming: false, streamingText: '', streamingToolCalls: [] });
    updateSendButton();
  }

  scrollToBottom();
  onStreamComplete?.();
}

/**
 * Render all messages from state (for loading a conversation).
 */
function renderAllMessages() {
  if (!messagesContainer) return;
  messagesContainer.innerHTML = '';

  const { messages, conversationId } = getState();
  const cachedMeta = loadVerificationMeta(conversationId);
  let assistantIndex = 0;

  for (const msg of messages) {
    if (!msg.content) continue;
    const el = appendMessageToDOM(msg, false);

    // Render verification for assistant messages
    if (msg.role === 'assistant') {
      const meta = msg.meta || cachedMeta[assistantIndex] || null;
      if (meta) {
        const metaContainer = el.querySelector('.message-meta-area');
        if (metaContainer) {
          renderVerification(metaContainer, meta);
          renderFeedback(metaContainer, conversationId);
        }
      }
      assistantIndex++;
    }
  }
  scrollToBottom();
}

/**
 * Append a message element to the DOM.
 */
function appendMessageToDOM(msg, animate = true) {
  if (!messagesContainer) return null;

  const row = document.createElement('div');
  row.className = `message-row ${msg.role}${animate ? ' animate animate-message-in' : ''}`;

  if (msg.role === 'user') {
    row.innerHTML = `<div class="message-bubble user">${escapeHtml(msg.content)}</div>`;
  } else {
    row.innerHTML = `
      <div class="message-group">
        <div class="message-bubble assistant">
          <div class="tool-status-area"></div>
          <div class="message-content">${renderMarkdown(msg.content)}</div>
        </div>
        <div class="message-meta-area"></div>
      </div>
    `;
  }

  messagesContainer.appendChild(row);
  scrollToBottom();
  return row;
}

/**
 * Create a streaming assistant bubble (empty, for progressive fill).
 */
function createStreamingAssistantBubble() {
  if (!messagesContainer) return null;

  const row = document.createElement('div');
  row.className = 'message-row assistant animate animate-message-in';
  row.innerHTML = `
    <div class="message-group">
      <div class="message-bubble assistant">
        <div class="tool-status-area"></div>
        <div class="message-content"></div>
      </div>
      <div class="message-meta-area"></div>
    </div>
  `;

  messagesContainer.appendChild(row);
  scrollToBottom();
  return row;
}

function showStreamingDots(contentEl) {
  if (contentEl && !contentEl.querySelector('.streaming-dots')) {
    contentEl.innerHTML = `<div class="streaming-dots"><span></span><span></span><span></span></div>`;
  }
}

function removeStreamingDots(contentEl) {
  const dots = contentEl?.querySelector('.streaming-dots');
  if (dots) dots.remove();
}

function addToolStatus(container, toolName) {
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'tool-status';
  el.innerHTML = `
    <svg class="tool-status-spinner" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>
    <span>Calling ${escapeHtml(toolName)}...</span>
  `;
  container.appendChild(el);
}

function collapseToolStatus(container, toolCalls) {
  if (!container) return;
  container.innerHTML = '';
  if (toolCalls && toolCalls.length > 0) {
    const names = toolCalls.map(t => t.tool || t.name).filter(Boolean);
    if (names.length > 0) {
      const summary = document.createElement('div');
      summary.className = 'tool-status-summary';
      summary.textContent = `Used ${names.length} tool${names.length > 1 ? 's' : ''}: ${names.join(', ')}`;
      container.appendChild(summary);
    }
  }
}

function scrollToBottom() {
  if (messagesContainer) {
    requestAnimationFrame(() => {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    });
  }
}

/* ═══════════════════════════════════════════════════════════
   SIDEBAR — Conversations, examples, tools, mobile toggle
   ═══════════════════════════════════════════════════════════ */

import { getState, setState, subscribe } from './state.js';
import * as api from './api.js';
import { truncate, timeAgo } from './utils.js';

let onConversationSelect = null;
let onNewChat = null;
let onExampleClick = null;

/**
 * Initialize sidebar with callbacks.
 */
export function initSidebar({ onSelect, onNew, onExample }) {
  onConversationSelect = onSelect;
  onNewChat = onNew;
  onExampleClick = onExample;

  // New chat button
  document.getElementById('new-chat-btn')?.addEventListener('click', () => {
    onNewChat?.();
    closeSidebar();
  });

  // Collapsible sections
  setupCollapsible('tools-toggle', 'tools-body');

  // Tool buttons → send example prompt
  document.querySelectorAll('.tool-item[data-query]').forEach(el => {
    el.addEventListener('click', () => {
      const query = el.dataset.query;
      if (query) {
        onExampleClick?.(query);
        closeSidebar();
      }
    });
  });

  // Mobile toggle
  document.getElementById('menu-toggle')?.addEventListener('click', toggleSidebar);
  document.getElementById('sidebar-scrim')?.addEventListener('click', closeSidebar);

  // Subscribe to conversation list changes
  subscribe('conversations', renderConversations);
  subscribe('conversationId', () => renderConversations(getState().conversations));

  // Initial fetch
  loadConversations();
}

/**
 * Fetch and update conversations.
 */
export async function loadConversations() {
  const conversations = await api.getConversations();
  setState({ conversations });
}

/**
 * Render conversation list in sidebar.
 */
function renderConversations(conversations) {
  const container = document.getElementById('conversation-list');
  if (!container) return;

  const currentId = getState().conversationId;
  container.innerHTML = '';

  if (!conversations || conversations.length === 0) return;

  for (const conv of conversations) {
    const item = document.createElement('div');
    item.className = `conversation-item${conv.id === currentId ? ' active' : ''}`;

    const title = document.createElement('span');
    title.className = 'conv-title';
    title.textContent = truncate(conv.title || 'Untitled', 35);

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'conv-delete';
    deleteBtn.innerHTML = '&times;';
    deleteBtn.title = 'Delete conversation';
    deleteBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await api.deleteConversation(conv.id);
      if (getState().conversationId === conv.id) {
        onNewChat?.();
      }
      await loadConversations();
    });

    item.appendChild(title);
    item.appendChild(deleteBtn);

    item.addEventListener('click', () => {
      onConversationSelect?.(conv.id);
      closeSidebar();
    });

    container.appendChild(item);
  }
}

/**
 * Setup collapsible section toggle.
 */
function setupCollapsible(toggleId, bodyId) {
  const toggle = document.getElementById(toggleId);
  const body = document.getElementById(bodyId);
  if (!toggle || !body) return;

  toggle.addEventListener('click', () => {
    const isCollapsed = toggle.classList.contains('collapsed');
    if (isCollapsed) {
      toggle.classList.remove('collapsed');
      body.classList.remove('collapsed');
      body.style.maxHeight = body.scrollHeight + 'px';
    } else {
      toggle.classList.add('collapsed');
      body.style.maxHeight = '0';
      body.classList.add('collapsed');
    }
  });

  // Set initial max-height for open sections
  if (!toggle.classList.contains('collapsed')) {
    requestAnimationFrame(() => {
      body.style.maxHeight = body.scrollHeight + 'px';
    });
  }
}

/**
 * Update health indicator in sidebar and header.
 */
export function updateHealth(health) {
  const dot = document.getElementById('health-dot');
  const headerDot = document.getElementById('header-health-dot');
  const text = document.getElementById('health-text');

  const isOk = health?.status === 'ok';

  if (dot) {
    dot.className = `health-dot ${isOk ? 'online' : 'offline'}`;
  }
  if (headerDot) {
    headerDot.className = `health-dot ${isOk ? 'online' : 'offline'}`;
  }
  if (text) {
    text.textContent = isOk ? 'Online' : 'Offline';
  }
}

/**
 * Toggle mobile sidebar.
 */
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const scrim = document.getElementById('sidebar-scrim');
  const isOpen = sidebar?.classList.contains('open');

  if (isOpen) {
    closeSidebar();
  } else {
    sidebar?.classList.add('open');
    scrim?.classList.add('active');
  }
}

function closeSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.getElementById('sidebar-scrim')?.classList.remove('active');
}

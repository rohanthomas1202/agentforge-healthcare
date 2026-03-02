/* ═══════════════════════════════════════════════════════════
   APP — Entry point, initialization, view switching
   ═══════════════════════════════════════════════════════════ */

import { subscribe, setState, getState, restoreConversation } from './state.js';
import { checkHealth } from './api.js';
import { initSidebar, updateHealth, loadConversations } from './sidebar.js';
import { initWelcome } from './welcome.js';
import { initChat, sendQuery, loadConversation, clearChat } from './chat.js';

document.addEventListener('DOMContentLoaded', async () => {
  // ── View switching ──────────────────────────────────────
  const welcomeEl = document.getElementById('welcome');
  const chatEl = document.getElementById('chat');
  const chatHeader = document.getElementById('chat-header');

  subscribe('currentView', (view) => {
    welcomeEl?.classList.toggle('hidden', view !== 'welcome');
    chatEl?.classList.toggle('hidden', view !== 'chat');
    chatHeader?.classList.toggle('hidden', view !== 'chat');
  });

  // ── Initialize modules ──────────────────────────────────

  // Welcome: suggestion cards trigger sendQuery
  initWelcome((query) => sendQuery(query));

  // Chat: notify sidebar on stream complete to refresh conversation list
  initChat({
    onComplete: () => loadConversations(),
  });

  // Sidebar: handle conversation selection, new chat, examples
  initSidebar({
    onSelect: (id) => loadConversation(id),
    onNew: () => clearChat(),
    onExample: (query) => sendQuery(query),
  });

  // ── Health check ────────────────────────────────────────
  const health = await checkHealth();
  setState({ health });
  updateHealth(health);

  // Periodic health check every 30s
  setInterval(async () => {
    const h = await checkHealth();
    setState({ health: h });
    updateHealth(h);
  }, 30000);

  // ── Restore session ─────────────────────────────────────
  const savedId = restoreConversation();
  if (savedId) {
    try {
      await loadConversation(savedId);
    } catch {
      clearChat();
    }
  }
});

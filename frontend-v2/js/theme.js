/* ═══════════════════════════════════════════════════════════
   THEME — Dark / Light mode toggle with persistence
   ═══════════════════════════════════════════════════════════ */

const STORAGE_KEY = 'af_theme';

/**
 * Initialize theme system.
 * Reads preference from: localStorage > system preference > default (light).
 */
export function initTheme() {
  const saved = localStorage.getItem(STORAGE_KEY);
  const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (systemDark ? 'dark' : 'light');

  applyTheme(theme);

  // Toggle button
  document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);

  // Listen for system preference changes (only if no manual override)
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });
}

/**
 * Toggle between dark and light.
 */
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  localStorage.setItem(STORAGE_KEY, next);
}

/**
 * Apply theme to document.
 */
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);

  // Toggle icon visibility
  const sun = document.querySelector('.theme-icon-sun');
  const moon = document.querySelector('.theme-icon-moon');
  if (sun && moon) {
    // In dark mode: show sun (to switch to light). In light mode: show moon (to switch to dark).
    sun.style.display = theme === 'dark' ? 'block' : 'none';
    moon.style.display = theme === 'dark' ? 'none' : 'block';
  }
}

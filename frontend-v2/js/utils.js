/* ═══════════════════════════════════════════════════════════
   UTILS — Markdown renderer, escaping, formatting
   ═══════════════════════════════════════════════════════════ */

/**
 * Escape HTML entities to prevent XSS.
 */
export function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Markdown to HTML converter.
 * Handles: tables, hr, blockquotes, bold, italic, code blocks,
 * inline code, links, lists, headings, paragraphs.
 */
export function renderMarkdown(text) {
  if (!text) return '';

  // Process block-level elements first (before escaping)
  const lines = text.split('\n');
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code blocks (``` ... ```)
    if (line.trim().startsWith('```')) {
      const lang = line.trim().slice(3);
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      blocks.push(`<pre><code class="${escapeHtml(lang)}">${escapeHtml(codeLines.join('\n'))}</code></pre>`);
      continue;
    }

    // Tables (detect | at start)
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
        tableLines.push(lines[i]);
        i++;
      }
      blocks.push(renderTable(tableLines));
      continue;
    }

    // Horizontal rule
    if (/^---+$|^\*\*\*+$|^___+$/.test(line.trim())) {
      blocks.push('<hr>');
      i++;
      continue;
    }

    // Blockquote
    if (line.trim().startsWith('> ')) {
      const quoteLines = [];
      while (i < lines.length && lines[i].trim().startsWith('> ')) {
        quoteLines.push(lines[i].replace(/^>\s?/, ''));
        i++;
      }
      blocks.push(`<blockquote>${renderInline(quoteLines.join('\n'))}</blockquote>`);
      continue;
    }

    // Headings
    const h4 = line.match(/^#### (.+)$/);
    if (h4) { blocks.push(`<h5>${renderInline(h4[1])}</h5>`); i++; continue; }
    const h3 = line.match(/^### (.+)$/);
    if (h3) { blocks.push(`<h4>${renderInline(h3[1])}</h4>`); i++; continue; }
    const h2 = line.match(/^## (.+)$/);
    if (h2) { blocks.push(`<h3>${renderInline(h2[1])}</h3>`); i++; continue; }
    const h1 = line.match(/^# (.+)$/);
    if (h1) { blocks.push(`<h2>${renderInline(h1[1])}</h2>`); i++; continue; }

    // Ordered list
    if (/^\d+\.\s/.test(line.trim())) {
      const listItems = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) {
        listItems.push(lines[i].replace(/^\d+\.\s/, ''));
        i++;
      }
      blocks.push('<ol>' + listItems.map(li => `<li>${renderInline(li)}</li>`).join('') + '</ol>');
      continue;
    }

    // Unordered list
    if (/^[-*]\s/.test(line.trim())) {
      const listItems = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i].trim())) {
        listItems.push(lines[i].replace(/^[-*]\s/, ''));
        i++;
      }
      blocks.push('<ul>' + listItems.map(li => `<li>${renderInline(li)}</li>`).join('') + '</ul>');
      continue;
    }

    // Empty line = paragraph break
    if (line.trim() === '') {
      i++;
      continue;
    }

    // Regular paragraph — collect consecutive non-empty lines
    const paraLines = [];
    while (i < lines.length && lines[i].trim() !== '' &&
           !lines[i].trim().startsWith('#') && !lines[i].trim().startsWith('|') &&
           !lines[i].trim().startsWith('```') && !lines[i].trim().startsWith('> ') &&
           !/^[-*]\s/.test(lines[i].trim()) && !/^\d+\.\s/.test(lines[i].trim()) &&
           !/^---+$|^\*\*\*+$|^___+$/.test(lines[i].trim())) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length > 0) {
      blocks.push(`<p>${renderInline(paraLines.join('<br>'))}</p>`);
    }
  }

  return blocks.join('\n');
}

/**
 * Render inline markdown (bold, italic, code, links).
 */
function renderInline(text) {
  let html = escapeHtml(text);

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

  // Italic
  html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // Preserve <br> that was already inserted
  html = html.replace(/&lt;br&gt;/g, '<br>');

  return html;
}

/**
 * Render a markdown table to HTML.
 */
function renderTable(lines) {
  if (lines.length < 2) return lines.map(l => `<p>${escapeHtml(l)}</p>`).join('');

  const parseRow = (line) =>
    line.split('|').slice(1, -1).map(cell => cell.trim());

  const headerCells = parseRow(lines[0]);

  // Find separator row (contains ---)
  let dataStart = 1;
  if (lines.length > 1 && /^[\s|:-]+$/.test(lines[1])) {
    dataStart = 2;
  }

  let html = '<div class="table-wrapper"><table><thead><tr>';
  for (const cell of headerCells) {
    html += `<th>${renderInline(cell)}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (let r = dataStart; r < lines.length; r++) {
    const cells = parseRow(lines[r]);
    html += '<tr>';
    for (const cell of cells) {
      html += `<td>${renderInline(cell)}</td>`;
    }
    html += '</tr>';
  }

  html += '</tbody></table></div>';
  return html;
}

/**
 * Relative time formatting (e.g., "2h ago", "3d ago").
 */
export function timeAgo(timestamp) {
  if (!timestamp) return '';
  const now = Date.now();
  const then = typeof timestamp === 'number'
    ? (timestamp > 1e12 ? timestamp : timestamp * 1000)
    : new Date(timestamp).getTime();

  const seconds = Math.floor((now - then) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(then).toLocaleDateString();
}

/**
 * Truncate string with ellipsis.
 */
export function truncate(str, len = 35) {
  if (!str) return '';
  return str.length > len ? str.slice(0, len) + '...' : str;
}

/**
 * Debounce function.
 */
export function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

/**
 * Format latency for display.
 */
export function formatLatency(ms) {
  if (!ms && ms !== 0) return '';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Format token count for display.
 */
export function formatTokens(usage) {
  if (!usage) return '';
  const total = (usage.input || 0) + (usage.output || 0);
  if (total === 0) return '';
  return total.toLocaleString();
}

/**
 * SVG icon helper — returns inline SVG strings (Lucide-style).
 */
export const icons = {
  clipboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="4" rx="1"></rect><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path></svg>',
  pill: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m10.5 1.5 3 3L5.5 12.5l-3-3a2.12 2.12 0 0 1 3-3l5-5Z"></path><path d="m13.5 6.5 3 3"></path><path d="m10.5 9.5 6.5-6.5"></path><path d="M12 12 7.5 16.5"></path></svg>',
  stethoscope: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3"></path><path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4"></path><circle cx="20" cy="10" r="2"></circle></svg>',
  userSearch: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="7" r="4"></circle><path d="M10.3 15H7a4 4 0 0 0-4 4v2"></path><circle cx="17" cy="17" r="3"></circle><path d="m21 21-1.9-1.9"></path></svg>',
  hospital: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 6v4"></path><path d="M14 14h-4"></path><path d="M14 18h-4"></path><path d="M14 8h-4"></path><path d="M18 12h2a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h2"></path><path d="M18 22V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v18"></path></svg>',
  flask: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"></path><path d="M10 9V3"></path><path d="M14 9V3"></path><path d="m10 9-3.7 7.4c-.7 1.4.2 3.1 1.8 3.4L12 21l3.9-1.2c1.6-.3 2.5-2 1.8-3.4L14 9"></path></svg>',
  thumbsUp: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v12"></path><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z"></path></svg>',
  thumbsDown: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14V2"></path><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z"></path></svg>',
  chevronDown: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>',
  loader: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
  alertTriangle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>',
  wrench: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
  shieldCheck: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><path d="m9 12 2 2 4-4"></path></svg>',
  heartPulse: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"></path><path d="M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27"></path></svg>',
  gauge: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 14 4-4"></path><path d="M3.34 19a10 10 0 1 1 17.32 0"></path></svg>',
  fileCheck: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"></path><path d="M14 2v4a2 2 0 0 0 2 2h4"></path><path d="m9 15 2 2 4-4"></path></svg>',
};

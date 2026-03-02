/* ═══════════════════════════════════════════════════════════
   VERIFICATION — Confidence badges, details panels, feedback
   ═══════════════════════════════════════════════════════════ */

import { getState } from './state.js';
import * as api from './api.js';
import { escapeHtml, formatLatency, icons } from './utils.js';

/**
 * Render verification metadata below an assistant message.
 */
export function renderVerification(container, meta) {
  if (!container || !meta) return;

  const html = [];

  // ── Top row: confidence + tools + performance ──
  html.push('<div class="message-meta">');
  html.push('<div class="meta-row">');

  // Confidence badge
  if (meta.confidence != null) {
    const pct = Math.round(meta.confidence * 100);
    const level = pct >= 70 ? 'high' : pct >= 40 ? 'mid' : 'low';
    const label = pct >= 70 ? 'High' : pct >= 40 ? 'Moderate' : 'Low';
    html.push(`<span class="confidence-badge ${level}">${label} (${pct}%)</span>`);
  }

  // Tool calls
  if (meta.tool_calls?.length > 0) {
    const names = meta.tool_calls.map(t => t.tool || t.name).filter(Boolean).join(', ');
    html.push(`<span class="meta-tools">${escapeHtml(names)}</span>`);
  }

  // Performance
  const perfParts = [];
  if (meta.latency_ms) perfParts.push(formatLatency(meta.latency_ms));
  if (meta.token_usage) {
    const total = (meta.token_usage.input || 0) + (meta.token_usage.output || 0);
    if (total > 0) perfParts.push(`${total.toLocaleString()} tokens`);
  }
  if (perfParts.length > 0) {
    html.push(`<span class="meta-performance">${perfParts.join(' · ')}</span>`);
  }

  html.push('</div>'); // meta-row

  // ── Disclaimers ──
  if (meta.disclaimers?.length > 0) {
    for (const d of meta.disclaimers) {
      html.push(`<div class="meta-disclaimer">${escapeHtml(d)}</div>`);
    }
  }

  // ── Verification details toggle ──
  if (meta.verification && Object.keys(meta.verification).length > 0) {
    const panelId = 'vp-' + Math.random().toString(36).slice(2, 8);

    html.push(`
      <button class="verification-toggle" data-panel="${panelId}">
        <span class="toggle-icon">${icons.shield}</span>
        <span>Verification Details</span>
        <svg class="toggle-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
      </button>
      <div class="verification-panel" id="${panelId}">
        <div class="verification-panel-inner">
    `);

    const v = meta.verification;

    // Drug safety
    if (v.drug_safety) {
      const ds = v.drug_safety;
      const passed = ds.passed !== false;
      html.push(`
        <div class="verification-section${!passed ? ' has-flags' : ''}" data-section="drug-safety">
          <div class="verification-section-title">${icons.shieldCheck}<span>Drug Safety</span></div>
          <div class="verification-item">
            <span>${passed ? icons.check : icons.alertTriangle}</span>
            <span>${passed ? 'No critical interactions detected' : 'Issues flagged'}</span>
          </div>
      `);
      if (ds.flags?.length > 0) {
        for (const fi of ds.flags) {
          html.push(`
            <div class="verification-item" style="padding-left: var(--space-5)">
              <span style="color: var(--confidence-mid)">${icons.alertTriangle}</span>
              <span><strong>${escapeHtml(fi.severity || 'Warning')}</strong>: ${escapeHtml(fi.reason || fi.description || fi.message || JSON.stringify(fi))}</span>
            </div>
          `);
        }
      }
      html.push('</div>');
    }

    // Allergy safety
    if (v.allergy_safety) {
      const as = v.allergy_safety;
      const passed = as.passed !== false;
      html.push(`
        <div class="verification-section${!passed ? ' has-flags' : ''}" data-section="allergy-safety">
          <div class="verification-section-title">${icons.heartPulse}<span>Allergy Safety</span></div>
          <div class="verification-item">
            <span>${passed ? icons.check : icons.alertTriangle}</span>
            <span>${passed ? 'No allergy conflicts detected' : 'Allergy conflicts flagged'}</span>
          </div>
      `);
      if (as.flags?.length > 0) {
        for (const fi of as.flags) {
          html.push(`
            <div class="verification-item" style="padding-left: var(--space-5)">
              <span style="color: var(--confidence-low)">${icons.alertTriangle}</span>
              <span><strong>${escapeHtml(fi.severity || 'Warning')}</strong>: ${escapeHtml(fi.reason || fi.description || fi.message || JSON.stringify(fi))}</span>
            </div>
          `);
        }
      }
      html.push('</div>');
    }

    // Confidence scoring breakdown
    if (v.confidence_scoring) {
      const cs = v.confidence_scoring;
      const factors = cs.factors || cs; // factors nested under .factors
      html.push(`
        <div class="verification-section" data-section="confidence">
          <div class="verification-section-title">${icons.gauge}<span>Confidence Factors</span></div>
          <div class="confidence-factors">
      `);

      const factorDefs = [
        { label: 'Tools', key: 'tools_used' },
        { label: 'Data', key: 'data_richness' },
        { label: 'Hedging', key: 'response_hedging' },
        { label: 'Errors', key: 'tool_error_rate' },
      ];

      for (const f of factorDefs) {
        const val = factors[f.key];
        if (val != null) {
          const pct = Math.round(val * 100);
          const level = pct >= 70 ? 'high' : pct >= 40 ? 'mid' : 'low';
          html.push(`
            <div class="confidence-factor">
              <div class="factor-label">${f.label}</div>
              <div class="factor-bar"><div class="factor-fill level-${level}" data-width="${pct}"></div></div>
              <div class="factor-value level-${level}">${pct}%</div>
            </div>
          `);
        }
      }

      html.push('</div></div>'); // confidence-factors, verification-section
    }

    // Claim verification
    if (v.claim_verification) {
      const cv = v.claim_verification;
      html.push(`
        <div class="verification-section" data-section="claims">
          <div class="verification-section-title">${icons.fileCheck}<span>Claim Verification</span></div>
      `);

      if (cv.grounding_rate != null) {
        const rate = Math.round(cv.grounding_rate * 100);
        const grounded = cv.grounded_claims ?? '?';
        const total = cv.total_claims ?? '?';
        const level = rate >= 70 ? 'high' : rate >= 40 ? 'mid' : 'low';
        html.push(`
          <div class="grounding-rate">
            <div class="grounding-rate-bar">
              <div class="grounding-rate-fill level-${level}" data-width="${rate}" style="width: 0"></div>
            </div>
            <div class="grounding-rate-label level-${level}">${grounded}/${total} (${rate}%)</div>
          </div>
        `);
      }

      if (cv.details?.length > 0) {
        for (const claim of cv.details) {
          const isGrounded = claim.grounded;
          const iconSvg = isGrounded ? icons.check : icons.alertTriangle;
          const stateClass = isGrounded ? 'grounded' : 'ungrounded';
          const source = claim.source_tool
            ? ` <span class="claim-source">[${escapeHtml(claim.source_tool)}]</span>`
            : '';
          html.push(`
            <div class="claim-item ${stateClass}">
              <span class="claim-icon ${stateClass}">${iconSvg}</span>
              <span class="claim-text">${escapeHtml(claim.claim || claim.text || '')}${source}</span>
            </div>
          `);
        }
      }

      html.push('</div>');
    }

    // Overall safety
    const isSafe = meta.verification.overall_safe !== false;
    html.push(`
      <div class="safety-status ${isSafe ? 'safe' : 'review'}">
        <span class="safety-dot"></span>
        <span>${isSafe ? 'Verified Safe' : 'Review Needed'}</span>
      </div>
    `);

    html.push('</div></div>'); // panel-inner, panel
  }

  html.push('</div>'); // message-meta

  container.innerHTML = html.join('');

  // Wire up toggle
  const toggleBtn = container.querySelector('.verification-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const panelId = toggleBtn.dataset.panel;
      const panel = document.getElementById(panelId);
      if (!panel) return;

      const isExpanding = !toggleBtn.classList.contains('expanded');
      toggleBtn.classList.toggle('expanded');
      panel.classList.toggle('expanded');

      if (isExpanding) {
        // Animate bars from 0 to their target width
        requestAnimationFrame(() => {
          const fills = panel.querySelectorAll('.factor-fill[data-width]');
          fills.forEach((fill, i) => {
            fill.style.transitionDelay = `${i * 80}ms`;
            fill.style.width = `${fill.dataset.width}%`;
          });
          const groundingFill = panel.querySelector('.grounding-rate-fill[data-width]');
          if (groundingFill) {
            groundingFill.style.transitionDelay = '200ms';
            groundingFill.style.width = `${groundingFill.dataset.width}%`;
          }
        });
      }
    });
  }
}

/**
 * Render feedback buttons (thumbs up/down) below verification.
 */
export function renderFeedback(container, conversationId) {
  if (!container) return;

  const row = document.createElement('div');
  row.className = 'feedback-row';

  const upBtn = document.createElement('button');
  upBtn.className = 'feedback-btn up';
  upBtn.innerHTML = icons.thumbsUp;
  upBtn.title = 'Good response';

  const downBtn = document.createElement('button');
  downBtn.className = 'feedback-btn down';
  downBtn.innerHTML = icons.thumbsDown;
  downBtn.title = 'Poor response';

  let submitted = false;

  upBtn.addEventListener('click', async () => {
    if (submitted) return;
    submitted = true;
    upBtn.classList.add('selected');
    downBtn.classList.add('faded');
    await api.sendFeedback(conversationId, 'up');
  });

  downBtn.addEventListener('click', async () => {
    if (submitted) return;
    submitted = true;
    downBtn.classList.add('selected');
    upBtn.classList.add('faded');
    await api.sendFeedback(conversationId, 'down');
  });

  row.appendChild(upBtn);
  row.appendChild(downBtn);
  container.appendChild(row);
}

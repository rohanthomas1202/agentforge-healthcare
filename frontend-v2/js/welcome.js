/* ═══════════════════════════════════════════════════════════
   WELCOME — Hero echo stack + suggestion cards
   ═══════════════════════════════════════════════════════════ */

import { icons } from './utils.js';

const SUGGESTIONS = [
  {
    icon: icons.clipboard,
    title: 'Clinical Summary',
    desc: 'Get a comprehensive patient overview with conditions, medications, and allergies',
    query: 'Give me a full clinical decision report for patient John Smith including all active conditions, medications, allergies, and any potential drug interactions',
  },
  {
    icon: icons.pill,
    title: 'Drug Interactions',
    desc: 'Check for dangerous interactions between medications',
    query: 'Check for drug interactions between Warfarin, Aspirin, and Metoprolol',
  },
  {
    icon: icons.stethoscope,
    title: 'Symptom Triage',
    desc: 'Analyze symptoms and get condition differentials with urgency levels',
    query: 'I have a patient with chest pain, shortness of breath, and dizziness. What conditions should I consider and what is the triage urgency?',
  },
  {
    icon: icons.userSearch,
    title: 'Find a Provider',
    desc: 'Search for specialists by name or specialty',
    query: 'Find me a cardiologist and check their availability',
  },
  {
    icon: icons.hospital,
    title: 'Insurance Coverage',
    desc: 'Check patient insurance and coverage details',
    query: 'Check insurance coverage for patient John Smith',
  },
  {
    icon: icons.flask,
    title: 'Lab Results',
    desc: 'Analyze lab results and identify abnormal values',
    query: 'Analyze the latest lab results for patient John Smith and flag any abnormal values',
  },
];

/**
 * Initialize suggestion cards.
 * @param {function} onCardClick - Callback when a card is clicked (receives query string)
 */
export function initWelcome(onCardClick) {
  const container = document.getElementById('suggestion-cards');
  if (!container) return;

  container.innerHTML = '';

  for (const suggestion of SUGGESTIONS) {
    const card = document.createElement('button');
    card.className = 'suggestion-card';
    card.innerHTML = `
      <div class="card-icon">${suggestion.icon}</div>
      <div class="card-title">${suggestion.title}</div>
      <div class="card-desc">${suggestion.desc}</div>
    `;
    card.addEventListener('click', () => onCardClick(suggestion.query));
    container.appendChild(card);
  }
}

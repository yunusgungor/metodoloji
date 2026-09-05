#!/usr/bin/env python3
"""SVG tanımlarını PNG'ye çevirir ve docs/images/ klasörüne kaydeder."""

import os
import cairosvg

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "images")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── SVG 1: Record Chain ──────────────────────────────────────────────────────
RECORD_CHAIN_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="820" height="120" viewBox="0 0 820 120" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="chainGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#8A2BE2;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#4B32C3;stop-opacity:1" />
    </linearGradient>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#6B7280" />
    </marker>
  </defs>
  <rect width="820" height="120" rx="12" fill="#0F0F1A" />
  <!-- E -->
  <rect x="20" y="30" width="80" height="60" rx="10" fill="url(#chainGrad)" opacity="0.9"/>
  <text x="60" y="54" text-anchor="middle" fill="white" font-family="monospace" font-size="18" font-weight="bold">E</text>
  <text x="60" y="74" text-anchor="middle" fill="#C4B5FD" font-family="sans-serif" font-size="10">Experiment</text>
  <line x1="102" y1="60" x2="130" y2="60" stroke="#6B7280" stroke-width="2" marker-end="url(#arrow)"/>
  <!-- IR -->
  <rect x="132" y="30" width="80" height="60" rx="10" fill="url(#chainGrad)" opacity="0.85"/>
  <text x="172" y="54" text-anchor="middle" fill="white" font-family="monospace" font-size="16" font-weight="bold">IR</text>
  <text x="172" y="74" text-anchor="middle" fill="#C4B5FD" font-family="sans-serif" font-size="10">Impl. Ready</text>
  <line x1="214" y1="60" x2="242" y2="60" stroke="#6B7280" stroke-width="2" marker-end="url(#arrow)"/>
  <!-- SP -->
  <rect x="244" y="30" width="80" height="60" rx="10" fill="url(#chainGrad)" opacity="0.80"/>
  <text x="284" y="54" text-anchor="middle" fill="white" font-family="monospace" font-size="16" font-weight="bold">SP</text>
  <text x="284" y="74" text-anchor="middle" fill="#C4B5FD" font-family="sans-serif" font-size="10">Sprint Plan</text>
  <line x1="326" y1="60" x2="354" y2="60" stroke="#6B7280" stroke-width="2" marker-end="url(#arrow)"/>
  <!-- S -->
  <rect x="356" y="30" width="80" height="60" rx="10" fill="url(#chainGrad)" opacity="0.75"/>
  <text x="396" y="54" text-anchor="middle" fill="white" font-family="monospace" font-size="18" font-weight="bold">S</text>
  <text x="396" y="74" text-anchor="middle" fill="#C4B5FD" font-family="sans-serif" font-size="10">Story</text>
  <line x1="438" y1="60" x2="466" y2="60" stroke="#6B7280" stroke-width="2" marker-end="url(#arrow)"/>
  <!-- QR -->
  <rect x="468" y="30" width="80" height="60" rx="10" fill="url(#chainGrad)" opacity="0.85"/>
  <text x="508" y="54" text-anchor="middle" fill="white" font-family="monospace" font-size="16" font-weight="bold">QR</text>
  <text x="508" y="74" text-anchor="middle" fill="#C4B5FD" font-family="sans-serif" font-size="10">Quality Rev.</text>
  <line x1="550" y1="60" x2="578" y2="60" stroke="#6B7280" stroke-width="2" marker-end="url(#arrow)"/>
  <!-- PR -->
  <rect x="580" y="30" width="80" height="60" rx="10" fill="url(#chainGrad)" opacity="0.95"/>
  <text x="620" y="54" text-anchor="middle" fill="white" font-family="monospace" font-size="16" font-weight="bold">PR</text>
  <text x="620" y="74" text-anchor="middle" fill="#C4B5FD" font-family="sans-serif" font-size="10">Prod. Ready</text>
  <!-- HMAC lock -->
  <g transform="translate(690, 38)">
    <rect x="0" y="10" width="26" height="20" rx="3" fill="none" stroke="#10B981" stroke-width="1.5"/>
    <path d="M5,10 Q5,2 13,2 Q21,2 21,10" fill="none" stroke="#10B981" stroke-width="1.5"/>
    <circle cx="13" cy="20" r="3" fill="#10B981"/>
    <line x1="13" y1="23" x2="13" y2="27" stroke="#10B981" stroke-width="1.5"/>
  </g>
  <text x="703" y="75" text-anchor="middle" fill="#10B981" font-family="sans-serif" font-size="9">HMAC</text>
  <text x="703" y="85" text-anchor="middle" fill="#10B981" font-family="sans-serif" font-size="9">signed</text>
  <text x="410" y="108" text-anchor="middle" fill="#6B7280" font-family="sans-serif" font-size="11">The full record chain — each stage gate-locked before the next opens</text>
</svg>"""

# ─── SVG 2: Hook Architecture ─────────────────────────────────────────────────
HOOK_ARCH_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="760" height="300" viewBox="0 0 760 300" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="headerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#1E1B4B;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#312E81;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="redGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#7F1D1D;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#991B1B;stop-opacity:0.8" />
    </linearGradient>
    <linearGradient id="amberGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#78350F;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#92400E;stop-opacity:0.8" />
    </linearGradient>
    <linearGradient id="greenGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#064E3B;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#065F46;stop-opacity:0.8" />
    </linearGradient>
    <linearGradient id="blueGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#1E3A5F;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#1E40AF;stop-opacity:0.8" />
    </linearGradient>
  </defs>
  <rect width="760" height="300" rx="14" fill="#0D1117" />
  <rect x="0" y="0" width="760" height="40" rx="14" fill="url(#headerGrad)" />
  <rect x="0" y="26" width="760" height="14" fill="url(#headerGrad)" />
  <text x="380" y="26" text-anchor="middle" fill="white" font-family="sans-serif" font-size="14" font-weight="bold">Hook Architecture — hooks/hooks.json (shared by both runtimes)</text>

  <!-- SessionStart -->
  <rect x="20" y="58" width="140" height="70" rx="8" fill="url(#blueGrad)" stroke="#3B82F6" stroke-width="1"/>
  <text x="90" y="80" text-anchor="middle" fill="#93C5FD" font-family="monospace" font-size="12" font-weight="bold">SessionStart</text>
  <text x="90" y="97" text-anchor="middle" fill="#BFDBFE" font-family="sans-serif" font-size="10">bootstrap.sh</text>
  <text x="90" y="113" text-anchor="middle" fill="#93C5FD" font-family="sans-serif" font-size="9">initializes env</text>

  <!-- PreToolUse guard -->
  <rect x="180" y="58" width="140" height="70" rx="8" fill="url(#redGrad)" stroke="#EF4444" stroke-width="1"/>
  <text x="250" y="80" text-anchor="middle" fill="#FCA5A5" font-family="monospace" font-size="11" font-weight="bold">PreToolUse/guard</text>
  <text x="250" y="97" text-anchor="middle" fill="#FEE2E2" font-family="sans-serif" font-size="10">Write · Edit · MultiEdit</text>
  <text x="250" y="113" text-anchor="middle" fill="#FCA5A5" font-family="sans-serif" font-size="9">fail-closed · needs E</text>

  <!-- PreToolUse quality -->
  <rect x="340" y="58" width="140" height="70" rx="8" fill="url(#amberGrad)" stroke="#F59E0B" stroke-width="1"/>
  <text x="410" y="80" text-anchor="middle" fill="#FCD34D" font-family="monospace" font-size="11" font-weight="bold">PreToolUse/quality</text>
  <text x="410" y="97" text-anchor="middle" fill="#FEF3C7" font-family="sans-serif" font-size="10">Bash · git commit</text>
  <text x="410" y="113" text-anchor="middle" fill="#FCD34D" font-family="sans-serif" font-size="9">soft/hard · needs QR</text>

  <!-- PreToolUse deploy -->
  <rect x="500" y="58" width="140" height="70" rx="8" fill="url(#amberGrad)" stroke="#F59E0B" stroke-width="1"/>
  <text x="570" y="80" text-anchor="middle" fill="#FCD34D" font-family="monospace" font-size="11" font-weight="bold">PreToolUse/deploy</text>
  <text x="570" y="97" text-anchor="middle" fill="#FEF3C7" font-family="sans-serif" font-size="10">deploy commands</text>
  <text x="570" y="113" text-anchor="middle" fill="#FCD34D" font-family="sans-serif" font-size="9">soft/hard · needs PR</text>

  <!-- PostToolUse audit -->
  <rect x="20" y="148" width="140" height="70" rx="8" fill="url(#greenGrad)" stroke="#10B981" stroke-width="1"/>
  <text x="90" y="170" text-anchor="middle" fill="#6EE7B7" font-family="monospace" font-size="11" font-weight="bold">PostToolUse/audit</text>
  <text x="90" y="187" text-anchor="middle" fill="#D1FAE5" font-family="sans-serif" font-size="10">Write · Edit · Bash</text>
  <text x="90" y="203" text-anchor="middle" fill="#6EE7B7" font-family="sans-serif" font-size="9">async · logs all ops</text>

  <!-- Stop -->
  <rect x="180" y="148" width="140" height="70" rx="8" fill="url(#redGrad)" stroke="#EF4444" stroke-width="1"/>
  <text x="250" y="170" text-anchor="middle" fill="#FCA5A5" font-family="monospace" font-size="12" font-weight="bold">Stop</text>
  <text x="250" y="187" text-anchor="middle" fill="#FEE2E2" font-family="sans-serif" font-size="10">session close</text>
  <text x="250" y="203" text-anchor="middle" fill="#FCA5A5" font-family="sans-serif" font-size="9">fail-closed · full chain</text>

  <!-- Engine box -->
  <rect x="380" y="138" width="360" height="90" rx="8" fill="#1A1F2E" stroke="#4B5563" stroke-width="1" stroke-dasharray="4,3"/>
  <text x="560" y="162" text-anchor="middle" fill="#9CA3AF" font-family="monospace" font-size="12" font-weight="bold">hooks/engine/main.py</text>
  <text x="560" y="181" text-anchor="middle" fill="#6B7280" font-family="sans-serif" font-size="10">HMAC verification · record chain validation</text>
  <text x="560" y="197" text-anchor="middle" fill="#6B7280" font-family="sans-serif" font-size="10">hooks/engine/modules/* · 10+ enforcement modules</text>
  <text x="560" y="213" text-anchor="middle" fill="#6B7280" font-family="sans-serif" font-size="10">hooks/scripts/run-hook.sh · bootstrap.sh</text>

  <!-- Runtime label -->
  <rect x="20" y="248" width="720" height="34" rx="6" fill="#131722" stroke="#374151" stroke-width="1"/>
  <rect x="250" y="254" width="140" height="20" rx="4" fill="#1E1B4B"/>
  <text x="320" y="268" text-anchor="middle" fill="#A5B4FC" font-family="sans-serif" font-size="11">OpenHands SDK</text>
  <rect x="410" y="254" width="140" height="20" rx="4" fill="#1E1B4B"/>
  <text x="480" y="268" text-anchor="middle" fill="#A5B4FC" font-family="sans-serif" font-size="11">Claude Code plugin</text>
</svg>"""

# ─── SVG 3: Skill Ecosystem ───────────────────────────────────────────────────
SKILL_ECO_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="760" height="280" viewBox="0 0 760 280" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="centerGrad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" style="stop-color:#8A2BE2;stop-opacity:0.3" />
      <stop offset="100%" style="stop-color:#8A2BE2;stop-opacity:0" />
    </radialGradient>
  </defs>
  <rect width="760" height="280" rx="14" fill="#0D1117" />
  <!-- Center hub -->
  <circle cx="380" cy="140" r="48" fill="#1A1033" stroke="#8A2BE2" stroke-width="2"/>
  <circle cx="380" cy="140" r="44" fill="url(#centerGrad)"/>
  <text x="380" y="134" text-anchor="middle" fill="#C4B5FD" font-family="monospace" font-size="13" font-weight="bold">125</text>
  <text x="380" y="150" text-anchor="middle" fill="#C4B5FD" font-family="sans-serif" font-size="10">skills</text>
  <text x="380" y="163" text-anchor="middle" fill="#8A2BE2" font-family="sans-serif" font-size="9">metodoloji</text>

  <!-- spokes -->
  <line x1="380" y1="92" x2="380" y2="40" stroke="#8A2BE2" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
  <line x1="428" y1="108" x2="580" y2="52" stroke="#8A2BE2" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
  <line x1="426" y1="140" x2="680" y2="140" stroke="#8A2BE2" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
  <line x1="428" y1="172" x2="580" y2="230" stroke="#8A2BE2" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
  <line x1="380" y1="188" x2="380" y2="240" stroke="#8A2BE2" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
  <line x1="332" y1="172" x2="180" y2="230" stroke="#8A2BE2" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
  <line x1="334" y1="108" x2="180" y2="52" stroke="#8A2BE2" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
  <line x1="332" y1="140" x2="80" y2="140" stroke="#8A2BE2" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>

  <!-- bmad -->
  <rect x="320" y="14" width="120" height="44" rx="8" fill="#1E1B4B" stroke="#6D28D9" stroke-width="1.5"/>
  <text x="380" y="33" text-anchor="middle" fill="#A78BFA" font-family="monospace" font-size="11" font-weight="bold">bmad-*</text>
  <text x="380" y="49" text-anchor="middle" fill="#7C3AED" font-family="sans-serif" font-size="10">core + agents · 60+ skills</text>

  <!-- gds -->
  <rect x="560" y="26" width="120" height="44" rx="8" fill="#1A2E1A" stroke="#059669" stroke-width="1.5"/>
  <text x="620" y="45" text-anchor="middle" fill="#6EE7B7" font-family="monospace" font-size="11" font-weight="bold">gds-*</text>
  <text x="620" y="61" text-anchor="middle" fill="#059669" font-family="sans-serif" font-size="10">game dev · 25+ skills</text>

  <!-- wds -->
  <rect x="590" y="114" width="130" height="44" rx="8" fill="#1A1F2E" stroke="#3B82F6" stroke-width="1.5"/>
  <text x="655" y="133" text-anchor="middle" fill="#93C5FD" font-family="monospace" font-size="11" font-weight="bold">wds-*</text>
  <text x="655" y="149" text-anchor="middle" fill="#3B82F6" font-family="sans-serif" font-size="10">workflow design · 9 skills</text>

  <!-- testarch -->
  <rect x="540" y="210" width="140" height="44" rx="8" fill="#1F1A10" stroke="#D97706" stroke-width="1.5"/>
  <text x="610" y="229" text-anchor="middle" fill="#FCD34D" font-family="monospace" font-size="11" font-weight="bold">testarch-*</text>
  <text x="610" y="245" text-anchor="middle" fill="#D97706" font-family="sans-serif" font-size="10">test architecture · 6 skills</text>

  <!-- cis/tea -->
  <rect x="310" y="240" width="140" height="34" rx="8" fill="#1A1A2E" stroke="#EC4899" stroke-width="1.5"/>
  <text x="380" y="258" text-anchor="middle" fill="#F9A8D4" font-family="monospace" font-size="11" font-weight="bold">cis-* · tea-*</text>
  <text x="380" y="270" text-anchor="middle" fill="#EC4899" font-family="sans-serif" font-size="9">innovation · storytelling</text>

  <!-- memory/sync -->
  <rect x="72" y="210" width="150" height="44" rx="8" fill="#101A1A" stroke="#06B6D4" stroke-width="1.5"/>
  <text x="147" y="229" text-anchor="middle" fill="#67E8F9" font-family="monospace" font-size="11" font-weight="bold">memory · sync</text>
  <text x="147" y="245" text-anchor="middle" fill="#06B6D4" font-family="sans-serif" font-size="10">cross-session context</text>

  <!-- qa/eval -->
  <rect x="60" y="26" width="140" height="44" rx="8" fill="#1A1010" stroke="#EF4444" stroke-width="1.5"/>
  <text x="130" y="45" text-anchor="middle" fill="#FCA5A5" font-family="monospace" font-size="11" font-weight="bold">qa-* · eval-*</text>
  <text x="130" y="61" text-anchor="middle" fill="#EF4444" font-family="sans-serif" font-size="10">quality gates · benchmarks</text>

  <!-- loop/party -->
  <rect x="8" y="114" width="150" height="44" rx="8" fill="#121A10" stroke="#84CC16" stroke-width="1.5"/>
  <text x="83" y="133" text-anchor="middle" fill="#BEF264" font-family="monospace" font-size="11" font-weight="bold">loop-* · party</text>
  <text x="83" y="149" text-anchor="middle" fill="#84CC16" font-family="sans-serif" font-size="10">automation · sweep · resolve</text>
</svg>"""

# ─── SVG 4: Platform Install ──────────────────────────────────────────────────
PLATFORM_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="760" height="220" viewBox="0 0 760 220" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#6D28D9" />
    </marker>
    <marker id="arr2" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#2563EB" />
    </marker>
    <marker id="arr3" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#166534" />
    </marker>
  </defs>
  <rect width="760" height="220" rx="14" fill="#0D1117" />

  <!-- OpenHands column -->
  <rect x="20" y="16" width="340" height="40" rx="8" fill="#1E1B4B" stroke="#6D28D9" stroke-width="1.5"/>
  <text x="190" y="42" text-anchor="middle" fill="#A78BFA" font-family="sans-serif" font-size="14" font-weight="bold">OpenHands (SDK)</text>
  <rect x="30" y="70" width="140" height="52" rx="6" fill="#131320" stroke="#4C1D95" stroke-width="1"/>
  <text x="100" y="88" text-anchor="middle" fill="#8B5CF6" font-family="monospace" font-size="10" font-weight="bold">1. fetch</text>
  <text x="100" y="104" text-anchor="middle" fill="#7C3AED" font-family="sans-serif" font-size="9">Plugin.fetch(</text>
  <text x="100" y="116" text-anchor="middle" fill="#7C3AED" font-family="sans-serif" font-size="9">"github:...")</text>
  <line x1="172" y1="96" x2="196" y2="96" stroke="#6D28D9" stroke-width="1.5" marker-end="url(#arr)"/>
  <rect x="198" y="70" width="140" height="52" rx="6" fill="#131320" stroke="#4C1D95" stroke-width="1"/>
  <text x="268" y="88" text-anchor="middle" fill="#8B5CF6" font-family="monospace" font-size="10" font-weight="bold">2. install</text>
  <text x="268" y="104" text-anchor="middle" fill="#7C3AED" font-family="sans-serif" font-size="9">install_plugin(</text>
  <text x="268" y="116" text-anchor="middle" fill="#7C3AED" font-family="sans-serif" font-size="9">"github:...")</text>
  <text x="190" y="152" text-anchor="middle" fill="#4B5563" font-family="sans-serif" font-size="9">~/.openhands/plugins/installed/metodoloji/</text>

  <!-- Claude Code column -->
  <rect x="400" y="16" width="340" height="40" rx="8" fill="#1A2540" stroke="#2563EB" stroke-width="1.5"/>
  <text x="570" y="42" text-anchor="middle" fill="#93C5FD" font-family="sans-serif" font-size="14" font-weight="bold">Claude Code (marketplace)</text>
  <rect x="410" y="70" width="100" height="52" rx="6" fill="#111A2E" stroke="#1D4ED8" stroke-width="1"/>
  <text x="460" y="88" text-anchor="middle" fill="#60A5FA" font-family="monospace" font-size="10" font-weight="bold">1. add</text>
  <text x="460" y="104" text-anchor="middle" fill="#3B82F6" font-family="sans-serif" font-size="9">/plugin</text>
  <text x="460" y="116" text-anchor="middle" fill="#3B82F6" font-family="sans-serif" font-size="9">marketplace</text>
  <line x1="512" y1="96" x2="526" y2="96" stroke="#2563EB" stroke-width="1.5" marker-end="url(#arr2)"/>
  <rect x="528" y="70" width="100" height="52" rx="6" fill="#111A2E" stroke="#1D4ED8" stroke-width="1"/>
  <text x="578" y="88" text-anchor="middle" fill="#60A5FA" font-family="monospace" font-size="10" font-weight="bold">2. install</text>
  <text x="578" y="104" text-anchor="middle" fill="#3B82F6" font-family="sans-serif" font-size="9">/plugin</text>
  <text x="578" y="116" text-anchor="middle" fill="#3B82F6" font-family="sans-serif" font-size="9">install</text>
  <line x1="630" y1="96" x2="644" y2="96" stroke="#2563EB" stroke-width="1.5" marker-end="url(#arr2)"/>
  <rect x="646" y="70" width="90" height="52" rx="6" fill="#111A2E" stroke="#1D4ED8" stroke-width="1"/>
  <text x="691" y="88" text-anchor="middle" fill="#60A5FA" font-family="monospace" font-size="10" font-weight="bold">3. enable</text>
  <text x="691" y="104" text-anchor="middle" fill="#3B82F6" font-family="sans-serif" font-size="9">claude plugin</text>
  <text x="691" y="116" text-anchor="middle" fill="#3B82F6" font-family="sans-serif" font-size="9">enable</text>
  <text x="570" y="152" text-anchor="middle" fill="#4B5563" font-family="sans-serif" font-size="9">~/.claude/plugins/cache/yunusgungor/metodoloji/</text>

  <!-- First session row -->
  <rect x="20" y="168" width="720" height="40" rx="8" fill="#121A12" stroke="#166534" stroke-width="1"/>
  <text x="160" y="184" text-anchor="middle" fill="#86EFAC" font-family="monospace" font-size="11">/metodoloji:init</text>
  <text x="160" y="198" text-anchor="middle" fill="#4B5563" font-family="sans-serif" font-size="9">record skeleton + templates</text>
  <line x1="270" y1="188" x2="300" y2="188" stroke="#166534" stroke-width="1.5" marker-end="url(#arr3)"/>
  <text x="430" y="184" text-anchor="middle" fill="#86EFAC" font-family="monospace" font-size="11">/metodoloji:gate-setup</text>
  <text x="430" y="198" text-anchor="middle" fill="#4B5563" font-family="sans-serif" font-size="9">~/.bmad/gate-key (HMAC)</text>
  <line x1="555" y1="188" x2="585" y2="188" stroke="#166534" stroke-width="1.5" marker-end="url(#arr3)"/>
  <text x="670" y="184" text-anchor="middle" fill="#86EFAC" font-family="monospace" font-size="11">Run first E</text>
  <text x="670" y="198" text-anchor="middle" fill="#4B5563" font-family="sans-serif" font-size="9">APPROVED -&gt; guard opens</text>
</svg>"""

SVGS = {
    "record-chain": RECORD_CHAIN_SVG,
    "hook-architecture": HOOK_ARCH_SVG,
    "skill-ecosystem": SKILL_ECO_SVG,
    "platform-install": PLATFORM_SVG,
}

for name, svg_content in SVGS.items():
    out_path = os.path.join(OUT_DIR, f"{name}.png")
    cairosvg.svg2png(
        bytestring=svg_content.encode("utf-8"),
        write_to=out_path,
        scale=2.0,          # 2x retina
        background_color=None,
    )
    size_kb = os.path.getsize(out_path) // 1024
    print(f"✓ {name}.png  ({size_kb} KB)  →  {out_path}")

print("\nDone.")

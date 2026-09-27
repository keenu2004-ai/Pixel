# PIXEL — Design System & Voice Interaction State Specification
**Status:** Approved Source of Truth  
**Version:** 1.0.0  

---

## 1. Design Philosophy

PIXEL's user interface is minimalist, hyper-responsive, and voice-state centric. Rather than cluttering the screen with unnecessary 3D elements or gratuitous dashboard widgets, the UI focuses on:
- **Instant Clarity**: Immediate recognition of whether PIXEL is listening, thinking, executing, or awaiting confirmation.
- **Dark Mode First**: Tailored deep-neutral palette (`#0a0b0e`, `#12151c`) with vivid state accents.
- **Accessibility & Contrast**: WCAG 2.1 AAA compliance for typography and interactive targets.
- **Micro-Interactions**: Fluid, purposeful spring physics for voice visualizers and action cards.

---

## 2. Voice State Machine & Visual States

The UI dynamically transitions between 11 primary operating states:

| State | Visual Accent / Halo | Particle / Waveform Behavior | Meaning |
| :--- | :--- | :--- | :--- |
| `IDLE` | Subtle Slate (`#64748b`, 20% opacity) | Gentle breathing pulse (0.2 Hz) | Ambiently waiting for wake trigger |
| `LISTENING` | Cyan Glow (`#06b6d4`, 80% opacity) | Dynamic reactive VAD waveform | Active microphone audio capture |
| `THINKING` | Indigo / Violet Swirl (`#6366f1`) | Orbiting gradient pulse | Intent classification & LLM planning |
| `EXECUTING` | Amber Accent (`#f59e0b`) | Linear indeterminate progress beam | Tool execution / OS command active |
| `SPEAKING` | Emerald Wave (`#10b981`) | Modulated amplitude bar spectrum | TTS synthesis streaming output |
| `INTERRUPTED` | Warm Orange Snap (`#f97316`) | Fast fade-out contraction | Barge-in detected; stopping playback |
| `WAITING_CONFIRMATION` | Pulsing Yellow (`#eab308`) | Modal halo with explicit action card | Sensitive tool waiting for user approval |
| `SECURE_ACTION_PENDING` | Crimson / Rose (`#f43f5e`) | Border lock badge with biometric prompt | High-impact action requires re-auth |
| `SUCCESS` | Vivid Mint (`#22c55e`) | Momentary check ring expansion | Action verified successfully |
| `FAILED` | Crisp Red (`#ef4444`) | Double jitter + error toast | Unrecoverable error / fallback active |
| `OFFLINE` | Muted Gray (`#475569`) | Static dotted ring | No local/remote models available |

---

## 3. Design Tokens

### 3.1 Color Palette
```css
:root {
  /* Surface Layers */
  --bg-base: #08090c;
  --bg-surface: #111318;
  --bg-surface-elevated: #181b22;
  --bg-overlay: rgba(8, 9, 12, 0.85);

  /* Borders & Dividers */
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-focus: rgba(6, 182, 212, 0.6);
  --border-danger: rgba(239, 68, 68, 0.5);

  /* Typography */
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --text-accent: #38bdf8;

  /* State Signals */
  --state-idle: #64748b;
  --state-listening: #06b6d4;
  --state-thinking: #6366f1;
  --state-executing: #f59e0b;
  --state-speaking: #10b981;
  --state-warning: #eab308;
  --state-error: #ef4444;
}
```

### 3.2 Typography Hierarchy
- **Font Families**:
  - Primary UI & Sans: `'Inter'`, `'Plus Jakarta Sans'`, system fallback.
  - Indic / Multilingual Display: `'Noto Sans Devanagari'`, `'Inter'`.
  - Code & Monospace: `'JetBrains Mono'`, `'Fira Code'`.
- **Scale**:
  - Display: `32px` (Line height: `40px`, Weight: `700`)
  - Title: `20px` (Line height: `28px`, Weight: `600`)
  - Body: `14px` (Line height: `20px`, Weight: `400`)
  - Small / Caption: `12px` (Line height: `16px`, Weight: `500`)
  - Code: `13px` (Line height: `18px`, Weight: `400`)

---

## 4. Component Primitives

1. **VoiceOrb / Waveform**: Canvas/SVG WebGL-accelerated audio visualizer with sub-16ms frame rendering.
2. **ActionApprovalCard**: High-contrast dialog showing exact tool name, target resource, risk class, and single-click Approve / Deny buttons.
3. **LiveTranscriptStream**: Dual-pane real-time speech-to-text feedback supporting bilingual script rendering (Latin & Devanagari).
4. **ExecutionTimeline**: Collapsible step-by-step progress view showing tool input, latency, output status, and verification evidence.

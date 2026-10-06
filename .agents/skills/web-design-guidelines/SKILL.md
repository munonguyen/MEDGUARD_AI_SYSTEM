---
name: web-design-guidelines
description: Review UI code for Vercel Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
metadata:
  author: vercel-labs
  version: "1.0.0"
---

# Web Interface Guidelines & UI Design Audit

Review UI code against modern Web Interface Guidelines, Accessibility (WCAG AA/AAA), Form UX, Animations, and Layout standards.

## Core Rules & Audit Standards

### 1. Accessibility (a11y)
- **Icon-only buttons**: Always provide an explicit `aria-label` or `title`.
- **Form controls**: Must have associated `<label>` (via `htmlFor` or wrapping) or explicit `aria-label`.
- **Buttons vs Links**: Use `<button>` for actions/state changes, `<a>` for navigational links (never `<div onClick>`).
- **Images & Icons**: Every `<img>` needs `alt` text (or `alt=""` if strictly decorative). Decorative icons need `aria-hidden="true"`.
- **Live Regions**: Asynchronous updates (toasts, validation, loading phase announcements) need `aria-live="polite"` or `role="status"` / `role="alert"`.
- **Headings**: Semantic, hierarchical `<h1>`–`<h6>` structure without skipped levels.
- **Redundant Status Cues**: Never rely on color alone to convey clinical or operational state; always pair color with clear text labels or icons.

### 2. Focus States & Keyboard Navigation
- **Visible Focus**: Every interactive control must show a clean, visible focus indicator: `:focus-visible` with high-contrast ring or outline.
- **Never unstyled `outline: none`**: Always provide a replacement focus indicator.
- **Group Focus**: Use `:focus-within` for grouped controls or composite inputs.
- **Overlays & Sticky Elements**: Sticky headers, footers, and floating overlays must not obscure focused elements.

### 3. Forms & Inputs
- **Autocomplete & Name**: Form inputs must have standard `autoComplete` and meaningful `name` attributes.
- **Input Types & Modes**: Use semantic types (`type="email"`, `type="password"`, `type="number"`) and appropriate `inputMode`.
- **No Blocked Paste**: Never prevent pasting in text inputs or textareas (`onPaste` without `preventDefault()`).
- **Clickable Labels**: Clicking the label must focus the associated input control.
- **Submit States**: Submit buttons must remain enabled until submission starts, then show a spinner while maintaining the label context.
- **Inline Validation**: Validation errors must appear inline next to the field, with the first invalid field receiving focus.
- **Ellipsis**: Placeholders and pending actions that require further input must end with an ellipsis `…` (e.g., `"Tìm cuộc trò chuyện…"`).

### 4. Animation & Motion Performance
- **Honor Reduced Motion**: Strictly respect `@media (prefers-reduced-motion: reduce)`.
- **Compositor-Friendly**: Animate GPU-accelerated properties (`transform`, `opacity`) only. Avoid animating properties that trigger layout reflow (`width`, `height`, `top`, `left`).
- **Never `transition: all`**: Explicitly specify only the animated properties (e.g., `transition: transform 0.2s ease, opacity 0.2s ease`).
- **Interruptible Motion**: Animations must respond immediately to new user interactions.

### 5. Layout, Typography & Visual Polish
- **Tabular Numbers**: Use `font-variant-numeric: tabular-nums` for counters, numbers, statistics, and timestamps.
- **Widows & Ragged Text**: Use `text-wrap: balance` or `text-wrap: pretty` on headings.
- **Typography**: Prefer typographic ellipsis `…` instead of three periods `...`.
- **Text Containers**: Containers must handle long or unbounded text gracefully with `min-width: 0`, overflow truncation, or word breaking.
- **Hit Targets**: Minimum hit target size of 24x24px on desktop and 44x44px on mobile devices.
- **Overscroll Containment**: Modals, drawers, and nested scroll areas must specify `overscroll-behavior: contain`.

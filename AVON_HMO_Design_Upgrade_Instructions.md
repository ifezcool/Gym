# AVON HMO Portal — Complete Design Upgrade Instructions

## Overview

This document provides exhaustive, file-by-file, component-by-component instructions for upgrading the visual design of the AVON HMO multi-page Dash portal. The app uses **Dash**, **dash-bootstrap-components**, **dash-svg**, and serves three portals: **Home**, **Wellness Portal** (+ Provider sub-portal), and **Gym Portal**.

The goal is: **smooth, modern, premium healthcare SaaS feel** — think Stripe, Linear, or Notion meets a clean medical brand. Responsive, snappy, easy on the eyes. No jarring colours. Consistent design language across all pages.

---

## Design System (Apply Everywhere)

### Colour Palette

Replace all ad-hoc colour values across all files with this system:

```
--avon-purple-900: #2D1B69   /* Deepest purple — for large headings only */
--avon-purple-700: #5B21B6   /* Primary brand purple */
--avon-purple-600: #7C3AED   /* Hover states, accents */
--avon-purple-500: #8B5CF6   /* Secondary accents */
--avon-purple-100: #EDE9FE   /* Tint backgrounds */
--avon-purple-50:  #F5F3FF   /* Very light purple wash */

--avon-green-600:  #059669   /* Success states */
--avon-green-500:  #10B981   /* Success hover */
--avon-green-100:  #D1FAE5   /* Success backgrounds */

--avon-red-600:    #DC2626   /* Error/danger */
--avon-red-100:    #FEE2E2   /* Error backgrounds */

--avon-amber-500:  #F59E0B   /* Warning */
--avon-amber-100:  #FEF3C7   /* Warning backgrounds */

--avon-blue-600:   #2563EB   /* Info / links */
--avon-blue-100:   #DBEAFE   /* Info backgrounds */

--avon-gray-900:   #111827   /* Body text */
--avon-gray-700:   #374151   /* Secondary text */
--avon-gray-500:   #6B7280   /* Muted text */
--avon-gray-300:   #D1D5DB   /* Borders */
--avon-gray-100:   #F3F4F6   /* Light backgrounds */
--avon-gray-50:    #F9FAFB   /* Page backgrounds */

--avon-white:      #FFFFFF
```

**Background rule**: All pages use `--avon-gray-50` (`#F9FAFB`) as the page background, NOT purple/grey gradients. The heavy coloured backgrounds currently used on Home and Gym portal pages feel dated — replace with a clean off-white.

### Typography

```
Primary font: 'Inter', system-ui, sans-serif  (already loaded in app.py)
Display font: 'Playfair Display', serif        (already loaded in app.py)

Scale:
  Page title (H1):   2.25rem / 700 / --avon-gray-900
  Section title (H2): 1.5rem / 600 / --avon-gray-900
  Card title (H3):   1.25rem / 600 / --avon-gray-900
  Body large:        1rem    / 400 / --avon-gray-700
  Body small:        0.875rem / 400 / --avon-gray-500
  Label:             0.875rem / 500 / --avon-gray-700
  Caption/footer:    0.75rem  / 400 / --avon-gray-500
```

### Spacing System (8px base grid)

```
--space-1:  4px
--space-2:  8px
--space-3:  12px
--space-4:  16px
--space-5:  20px
--space-6:  24px
--space-8:  32px
--space-10: 40px
--space-12: 48px
--space-16: 64px
```

### Elevation / Shadow System

```
--shadow-xs:  0 1px 2px rgba(0,0,0,0.05)
--shadow-sm:  0 1px 3px rgba(0,0,0,0.10), 0 1px 2px rgba(0,0,0,0.06)
--shadow-md:  0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05)
--shadow-lg:  0 10px 15px rgba(0,0,0,0.10), 0 4px 6px rgba(0,0,0,0.05)
--shadow-xl:  0 20px 25px rgba(0,0,0,0.10), 0 10px 10px rgba(0,0,0,0.04)
```

### Border Radius

```
--radius-sm:  6px
--radius-md:  10px
--radius-lg:  14px
--radius-xl:  20px
--radius-2xl: 28px
--radius-full: 9999px
```

### Animation / Transition

All interactive elements (buttons, cards, inputs) must use:
```css
transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
```

---

## File: `app.py` — Global CSS Overhaul

Replace the entire `WELLNESS_CSS` string with the following expanded global stylesheet. This is the single source of truth for design tokens and shared component styles.

```python
WELLNESS_CSS = """
<style>
  /* ─── DESIGN TOKENS ─── */
  :root {
    --purple-900: #2D1B69;
    --purple-700: #5B21B6;
    --purple-600: #7C3AED;
    --purple-500: #8B5CF6;
    --purple-100: #EDE9FE;
    --purple-50:  #F5F3FF;

    --green-600:  #059669;
    --green-500:  #10B981;
    --green-100:  #D1FAE5;

    --red-600:    #DC2626;
    --red-100:    #FEE2E2;

    --amber-500:  #F59E0B;
    --amber-100:  #FEF3C7;

    --blue-600:   #2563EB;
    --blue-100:   #DBEAFE;

    --gray-900:   #111827;
    --gray-700:   #374151;
    --gray-500:   #6B7280;
    --gray-300:   #D1D5DB;
    --gray-100:   #F3F4F6;
    --gray-50:    #F9FAFB;

    --shadow-sm:  0 1px 3px rgba(0,0,0,0.10), 0 1px 2px rgba(0,0,0,0.06);
    --shadow-md:  0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05);
    --shadow-lg:  0 10px 15px rgba(0,0,0,0.10), 0 4px 6px rgba(0,0,0,0.05);
    --shadow-xl:  0 20px 25px rgba(0,0,0,0.10), 0 10px 10px rgba(0,0,0,0.04);

    --radius-sm:  6px;
    --radius-md:  10px;
    --radius-lg:  14px;
    --radius-xl:  20px;
    --radius-2xl: 28px;

    --transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  }

  /* ─── BASE ─── */
  *, *::before, *::after { box-sizing: border-box; }
  
  html { scroll-behavior: smooth; }
  
  body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background-color: var(--gray-50);
    color: var(--gray-900);
    margin: 0;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', system-ui, sans-serif;
    font-weight: 600;
    line-height: 1.3;
    color: var(--gray-900);
    margin: 0 0 0.5em;
  }

  /* ─── PAGE LAYOUT ─── */
  .page-wrapper {
    min-height: 100vh;
    background: var(--gray-50);
  }

  /* ─── TOP NAV / HEADER BAR ─── */
  .avon-topbar {
    position: sticky;
    top: 0;
    z-index: 1000;
    background: rgba(255,255,255,0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--gray-100);
    padding: 0 32px;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: var(--shadow-sm);
  }

  .avon-topbar-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 700;
    font-size: 1rem;
    color: var(--purple-700);
    text-decoration: none;
  }

  .avon-topbar-brand:hover { color: var(--purple-600); }

  .avon-logo-mark {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--purple-700), var(--purple-500));
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(91,33,182,0.3);
  }

  /* ─── CARDS ─── */
  .avon-card {
    background: #fff;
    border-radius: var(--radius-xl);
    border: 1px solid var(--gray-100);
    box-shadow: var(--shadow-sm);
    transition: var(--transition);
    overflow: hidden;
  }

  .avon-card:hover { box-shadow: var(--shadow-md); }

  .avon-card-elevated {
    background: #fff;
    border-radius: var(--radius-xl);
    border: 1px solid var(--gray-100);
    box-shadow: var(--shadow-lg);
  }

  /* ─── FORMS ─── */
  .avon-input {
    width: 100%;
    height: 44px;
    padding: 0 14px;
    font-size: 0.9375rem;
    font-family: 'Inter', sans-serif;
    color: var(--gray-900);
    background: #fff;
    border: 1.5px solid var(--gray-300);
    border-radius: var(--radius-md);
    outline: none;
    transition: var(--transition);
    appearance: none;
  }

  .avon-input:focus {
    border-color: var(--purple-500);
    box-shadow: 0 0 0 3px rgba(139,92,246,0.12);
  }

  .avon-input::placeholder { color: var(--gray-500); }

  .avon-label {
    display: block;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--gray-700);
    margin-bottom: 6px;
  }

  .form-control, .form-select {
    height: 44px !important;
    border: 1.5px solid var(--gray-300) !important;
    border-radius: var(--radius-md) !important;
    font-size: 0.9375rem !important;
    color: var(--gray-900) !important;
    transition: var(--transition) !important;
    box-shadow: none !important;
  }

  .form-control:focus, .form-select:focus {
    border-color: var(--purple-500) !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,0.12) !important;
  }

  /* Dash dcc.Input override */
  input.dash-input {
    height: 44px;
    padding: 0 14px;
    border: 1.5px solid var(--gray-300);
    border-radius: var(--radius-md);
    font-family: 'Inter', sans-serif;
    font-size: 0.9375rem;
    transition: var(--transition);
    width: 100%;
  }

  input.dash-input:focus {
    border-color: var(--purple-500);
    box-shadow: 0 0 0 3px rgba(139,92,246,0.12);
    outline: none;
  }

  /* Dropdown */
  .Select-control, .VirtualizedSelectFocusedOption {
    border-radius: var(--radius-md) !important;
    border: 1.5px solid var(--gray-300) !important;
  }

  .Select--multi .Select-value {
    background: var(--purple-100) !important;
    border-color: var(--purple-200) !important;
    color: var(--purple-700) !important;
    border-radius: 4px !important;
  }

  .Select-option.is-focused {
    background: var(--purple-50) !important;
  }

  .Select-option.is-selected {
    background: var(--purple-600) !important;
  }

  /* ─── BUTTONS ─── */
  .avon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    height: 44px;
    padding: 0 20px;
    font-size: 0.9375rem;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: var(--transition);
    text-decoration: none;
    white-space: nowrap;
  }

  .avon-btn-primary {
    background: linear-gradient(135deg, var(--purple-700), var(--purple-600));
    color: #fff;
    box-shadow: 0 2px 8px rgba(91,33,182,0.30);
  }

  .avon-btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(91,33,182,0.40);
    color: #fff;
  }

  .avon-btn-primary:active { transform: translateY(0); }

  .avon-btn-secondary {
    background: #fff;
    color: var(--purple-700);
    border: 1.5px solid var(--gray-300);
    box-shadow: var(--shadow-xs);
  }

  .avon-btn-secondary:hover {
    background: var(--purple-50);
    border-color: var(--purple-300);
    color: var(--purple-700);
  }

  .avon-btn-danger {
    background: var(--red-600);
    color: #fff;
    box-shadow: 0 2px 8px rgba(220,38,38,0.25);
  }

  .avon-btn-danger:hover {
    background: #B91C1C;
    transform: translateY(-1px);
    color: #fff;
  }

  .avon-btn-success {
    background: var(--green-600);
    color: #fff;
    box-shadow: 0 2px 8px rgba(5,150,105,0.25);
  }

  .avon-btn-success:hover {
    background: #047857;
    transform: translateY(-1px);
    color: #fff;
  }

  .avon-btn-full { width: 100%; }

  /* Override dbc.Button styles to match above — by adding className */
  .btn-avon-primary {
    background: linear-gradient(135deg, #5B21B6, #7C3AED) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(91,33,182,0.30) !important;
    transition: all 0.18s cubic-bezier(0.4,0,0.2,1) !important;
    color: #fff !important;
  }
  .btn-avon-primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(91,33,182,0.40) !important;
  }

  /* ─── PROVIDER PORTAL BUTTON (fixed top-right) ─── */
  .provider-portal-btn {
    position: fixed;
    top: 14px;
    right: 24px;
    z-index: 9999;
    background: linear-gradient(135deg, var(--purple-700), var(--purple-600));
    color: #fff !important;
    border: none;
    border-radius: var(--radius-md);
    padding: 8px 16px;
    font-weight: 600;
    font-size: 0.8125rem;
    box-shadow: 0 2px 8px rgba(91,33,182,0.35);
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: var(--transition);
  }

  .provider-portal-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(91,33,182,0.45);
    color: #fff !important;
  }

  /* ─── STAT / SUMMARY CARDS ─── */
  .avon-stat-card {
    background: #fff;
    border: 1px solid var(--gray-100);
    border-radius: var(--radius-lg);
    padding: 20px 24px;
    box-shadow: var(--shadow-sm);
    text-align: center;
  }

  .avon-stat-number {
    font-size: 2.25rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 4px;
  }

  .avon-stat-label {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--gray-500);
    letter-spacing: 0.025em;
    text-transform: uppercase;
  }

  .avon-stat-purple .avon-stat-number { color: var(--purple-700); }
  .avon-stat-green  .avon-stat-number { color: var(--green-600); }
  .avon-stat-red    .avon-stat-number { color: var(--red-600); }

  /* ─── ALERTS / BANNERS ─── */
  .avon-alert {
    border-radius: var(--radius-lg);
    padding: 16px 20px;
    border: 1px solid transparent;
    font-size: 0.9375rem;
    line-height: 1.6;
  }

  .avon-alert-info {
    background: var(--blue-100);
    border-color: #BFDBFE;
    color: #1E40AF;
  }

  .avon-alert-success {
    background: var(--green-100);
    border-color: #A7F3D0;
    color: #065F46;
  }

  .avon-alert-warning {
    background: var(--amber-100);
    border-color: #FDE68A;
    color: #92400E;
  }

  .avon-alert-danger {
    background: var(--red-100);
    border-color: #FECACA;
    color: #991B1B;
  }

  /* Override Bootstrap alerts */
  .alert {
    border-radius: var(--radius-lg) !important;
    border-width: 1px !important;
    box-shadow: none !important;
    font-size: 0.9375rem !important;
  }

  /* ─── DATA TABLES ─── */
  .dash-spreadsheet-container {
    border-radius: var(--radius-lg) !important;
    overflow: hidden;
    border: 1px solid var(--gray-200) !important;
    box-shadow: var(--shadow-sm);
  }

  .dash-spreadsheet .dash-header {
    background: #5B21B6 !important;
    color: #fff !important;
    font-size: 0.8125rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    text-transform: uppercase !important;
    padding: 12px 10px !important;
    border: none !important;
  }

  .dash-spreadsheet .dash-cell {
    font-size: 0.875rem !important;
    padding: 10px !important;
    border-color: var(--gray-100) !important;
    color: var(--gray-700) !important;
  }

  .dash-spreadsheet tr:nth-child(odd) .dash-cell {
    background: var(--purple-50) !important;
  }

  .dash-spreadsheet tr:hover .dash-cell {
    background: var(--purple-100) !important;
  }

  /* ─── MODAL ─── */
  .modal-content {
    border-radius: var(--radius-xl) !important;
    border: none !important;
    box-shadow: var(--shadow-xl) !important;
  }

  .modal-header {
    border-bottom: 1px solid var(--gray-100) !important;
    padding: 20px 24px !important;
  }

  .modal-footer {
    border-top: 1px solid var(--gray-100) !important;
    padding: 16px 24px !important;
  }

  .modal-body { padding: 24px !important; }

  /* ─── WELLNESS PAGE SPECIFICS ─── */
  .wellness-hero {
    background: linear-gradient(135deg, #F5F3FF 0%, #FFFFFF 50%, #F0FDF4 100%);
    padding: 48px 24px 40px;
    text-align: center;
    position: relative;
    overflow: hidden;
  }

  .wellness-hero::before {
    content: '';
    position: absolute;
    top: -60px; left: -60px;
    width: 240px; height: 240px;
    background: radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%);
    border-radius: 50%;
  }

  .wellness-hero::after {
    content: '';
    position: absolute;
    bottom: -40px; right: -40px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(16,185,129,0.07) 0%, transparent 70%);
    border-radius: 50%;
  }

  .logo-container {
    width: 56px;
    height: 56px;
    background: linear-gradient(135deg, var(--purple-700), var(--purple-500));
    border-radius: var(--radius-lg);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 14px rgba(91,33,182,0.30);
    margin: 0 auto 20px;
  }

  .wellness-card {
    background: rgba(255,255,255,0.95);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(91,33,182,0.08);
    border-radius: var(--radius-2xl);
    box-shadow: var(--shadow-xl);
  }

  .questionnaire-section {
    background: var(--gray-50);
    border: 1px solid var(--gray-100);
    border-radius: var(--radius-lg);
    padding: 20px 24px;
    margin-bottom: 12px;
  }

  .questionnaire-section h5 {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--purple-700);
    margin-bottom: 16px;
  }

  .question-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--gray-700);
    margin-bottom: 8px;
    line-height: 1.5;
  }

  .section-divider {
    border: none;
    border-top: 1px solid var(--gray-200);
    margin: 24px 0;
  }

  .consent-banner {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-left: 4px solid var(--amber-500);
    border-radius: var(--radius-lg);
    padding: 16px 20px;
  }

  .already-booked-card {
    background: #fff;
    border: 1px solid var(--blue-100);
    border-left: 4px solid var(--blue-600);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
  }

  /* DatePicker */
  .SingleDatePicker, .DateInput {
    border-radius: var(--radius-md) !important;
  }

  .DateInput_input {
    border-bottom: none !important;
    border: 1.5px solid var(--gray-300) !important;
    border-radius: var(--radius-md) !important;
    font-size: 0.9375rem !important;
    padding: 10px 12px !important;
    height: 44px !important;
    font-family: 'Inter', sans-serif !important;
  }

  .DateInput_input__focused {
    border-color: var(--purple-500) !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,0.12) !important;
  }

  .CalendarDay__selected, .CalendarDay__selected:active, .CalendarDay__selected:hover {
    background: var(--purple-600) !important;
    border-color: var(--purple-600) !important;
  }

  /* RadioItems */
  .custom-radio .form-check-input:checked {
    background-color: var(--purple-600) !important;
    border-color: var(--purple-600) !important;
  }

  .form-check-input:focus {
    box-shadow: 0 0 0 3px rgba(139,92,246,0.15) !important;
    border-color: var(--purple-500) !important;
  }

  /* ─── PROVIDER PORTAL ─── */
  .provider-sidebar-card {
    background: #fff;
    border: 1px solid var(--gray-100);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
  }

  .provider-nav-btn {
    display: block;
    width: 100%;
    text-align: left;
    padding: 10px 14px;
    border-radius: var(--radius-md);
    font-size: 0.875rem;
    font-weight: 500;
    border: none;
    cursor: pointer;
    transition: var(--transition);
    background: transparent;
    color: var(--gray-700);
    margin-bottom: 4px;
  }

  .provider-nav-btn:hover {
    background: var(--purple-50);
    color: var(--purple-700);
  }

  .provider-nav-btn-active {
    background: var(--purple-100);
    color: var(--purple-700);
    font-weight: 600;
  }

  /* ─── LOADING SCREEN ─── */
  .avon-loading-screen {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, var(--purple-50) 0%, #fff 50%, #F0FDF4 100%);
  }

  /* ─── GYM PORTAL ─── */
  .gym-hero {
    background: linear-gradient(135deg, var(--purple-50) 0%, #fff 100%);
    padding: 48px 24px;
    border-bottom: 1px solid var(--gray-100);
    text-align: center;
  }

  .gym-eligibility-card {
    background: #fff;
    border: 1px solid var(--gray-100);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-lg);
    padding: 32px;
  }

  /* ─── BADGE / PILL ─── */
  .avon-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: var(--radius-full);
    font-size: 0.75rem;
    font-weight: 600;
  }

  .avon-badge-purple { background: var(--purple-100); color: var(--purple-700); }
  .avon-badge-green  { background: var(--green-100);  color: var(--green-600); }
  .avon-badge-red    { background: var(--red-100);    color: var(--red-600); }
  .avon-badge-amber  { background: var(--amber-100);  color: #92400E; }

  /* ─── SPINNER / LOADING ─── */
  ._dash-loading {
    visibility: hidden;
  }

  /* ─── SCROLLBAR ─── */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb {
    background: var(--gray-300);
    border-radius: 99px;
  }
  ::-webkit-scrollbar-thumb:hover { background: var(--gray-500); }

  /* ─── FOOTER ─── */
  .avon-footer {
    text-align: center;
    padding: 24px;
    font-size: 0.75rem;
    color: var(--gray-500);
    border-top: 1px solid var(--gray-100);
    margin-top: 48px;
  }

  /* ─── RESPONSIVE ─── */
  @media (max-width: 768px) {
    .wellness-hero { padding: 32px 16px 28px; }
    .gym-hero { padding: 32px 16px; }
    .provider-portal-btn { top: 10px; right: 12px; font-size: 0.75rem; padding: 7px 12px; }
  }
</style>
"""
```

---

## File: `pages/home.py` — Home Page Redesign

**Current problem**: Heavy dark purple/lilac gradient background, dated card style, low contrast text, not responsive at narrow widths.

**Target**: Clean white page with a subtle purple-accented hero, modern feature cards with hover lift, and a sticky topbar.

### Topbar Component

Add a sticky topbar at the very top of the layout (before the hero div). This is a shared pattern but implemented per-page in Dash multi-page:

```python
topbar = html.Header(className="avon-topbar", children=[
    html.A(className="avon-topbar-brand", href="/", children=[
        html.Div(className="avon-logo-mark", children=[
            # Use the same SVG shield icon from combined.py
            Svg(width="18", height="18", viewBox="0 0 24 24", fill="none", stroke="white",
                style={"strokeWidth": "2.5"},
                children=[
                    Path(d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"),
                    Path(d="m9 12 2 2 4-4")
                ])
        ]),
        html.Span("AVON HMO")
    ]),
    html.Span("Your Health, Our Priority",
              style={"fontSize": "0.8125rem", "color": "#6B7280"})
])
```

*(Import `dash_svg` — `from dash_svg import Svg, Path` — in home.py)*

### Hero Section

Replace the current gradient header with:

```python
hero = html.Section(style={
    "background": "linear-gradient(135deg, #F5F3FF 0%, #FFFFFF 60%, #F0FDF4 100%)",
    "padding": "72px 24px 56px",
    "textAlign": "center",
    "position": "relative",
    "overflow": "hidden",
    "borderBottom": "1px solid #F3F4F6",
}, children=[
    # Decorative blobs — pure CSS, no images
    html.Div(style={
        "position": "absolute", "top": "-80px", "left": "-80px",
        "width": "320px", "height": "320px",
        "background": "radial-gradient(circle, rgba(139,92,246,0.07) 0%, transparent 70%)",
        "borderRadius": "50%", "pointerEvents": "none"
    }),
    html.Div(style={
        "position": "absolute", "bottom": "-60px", "right": "-60px",
        "width": "280px", "height": "280px",
        "background": "radial-gradient(circle, rgba(16,185,129,0.06) 0%, transparent 70%)",
        "borderRadius": "50%", "pointerEvents": "none"
    }),

    html.Div(style={"position": "relative", "zIndex": "1"}, children=[
        # Logo mark
        html.Div(className="logo-container", style={"marginBottom": "24px"}),

        # Eyebrow label
        html.Span("Member Portal", style={
            "display": "inline-block",
            "background": "#EDE9FE",
            "color": "#5B21B6",
            "fontSize": "0.75rem",
            "fontWeight": "600",
            "letterSpacing": "0.06em",
            "textTransform": "uppercase",
            "padding": "4px 12px",
            "borderRadius": "9999px",
            "marginBottom": "16px"
        }),

        html.H1("Welcome to AVON HMO Portal", style={
            "fontSize": "clamp(1.75rem, 4vw, 2.75rem)",
            "fontWeight": "700",
            "color": "#111827",
            "marginBottom": "12px",
            "maxWidth": "600px",
            "margin": "0 auto 12px",
        }),

        html.P("Choose a portal to get started with your health and wellness journey.", style={
            "fontSize": "1.0625rem",
            "color": "#6B7280",
            "maxWidth": "480px",
            "margin": "0 auto",
            "lineHeight": "1.6",
        })
    ])
])
```

### Portal Cards

Replace the current `dbc.Row` with:

```python
cards_section = html.Section(style={
    "maxWidth": "960px",
    "margin": "0 auto",
    "padding": "48px 24px 80px",
}, children=[
    dbc.Row([
        dbc.Col([
            html.A(href="/gym-portal", style={"textDecoration": "none"}, children=[
                html.Div(className="avon-card", style={
                    "padding": "32px",
                    "cursor": "pointer",
                    "borderTop": "3px solid #5B21B6",
                }, children=[
                    html.Div("🏋️", style={"fontSize": "2.5rem", "marginBottom": "16px"}),
                    html.H3("Gym Portal", style={
                        "color": "#111827", "fontSize": "1.25rem",
                        "fontWeight": "700", "marginBottom": "10px"
                    }),
                    html.P("Book gym sessions, track usage, and access fitness facilities across Nigeria.",
                           style={"color": "#6B7280", "fontSize": "0.9375rem",
                                  "lineHeight": "1.6", "marginBottom": "24px"}),
                    html.Div(style={
                        "display": "inline-flex", "alignItems": "center", "gap": "6px",
                        "color": "#5B21B6", "fontWeight": "600", "fontSize": "0.875rem"
                    }, children=["Go to Gym Portal ", html.Span("→")])
                ])
            ])
        ], xs=12, md=6, className="mb-4"),

        dbc.Col([
            html.A(href="/wellness", style={"textDecoration": "none"}, children=[
                html.Div(className="avon-card", style={
                    "padding": "32px",
                    "cursor": "pointer",
                    "borderTop": "3px solid #059669",
                }, children=[
                    html.Div("🧘", style={"fontSize": "2.5rem", "marginBottom": "16px"}),
                    html.H3("Wellness Portal", style={
                        "color": "#111827", "fontSize": "1.25rem",
                        "fontWeight": "700", "marginBottom": "10px"
                    }),
                    html.P("Check eligibility, book your annual wellness checkup, and access health resources.",
                           style={"color": "#6B7280", "fontSize": "0.9375rem",
                                  "lineHeight": "1.6", "marginBottom": "24px"}),
                    html.Div(style={
                        "display": "inline-flex", "alignItems": "center", "gap": "6px",
                        "color": "#059669", "fontWeight": "600", "fontSize": "0.875rem"
                    }, children=["Go to Wellness Portal ", html.Span("→")])
                ])
            ])
        ], xs=12, md=6, className="mb-4"),
    ])
])
```

### Footer

```python
footer = html.Footer(className="avon-footer", children=[
    f"© {dt.datetime.now().year} AVON HMO. All rights reserved."
])
```

### Final `layout`

```python
layout = html.Div(style={"background": "#F9FAFB", "minHeight": "100vh"}, children=[
    topbar,
    hero,
    cards_section,
    footer,
])
```

**Remove**: `backgroundColor: '#d4c4e0'` from the outer div — this heavy purple background must go.

---

## File: `pages/combined.py` — Wellness Portal Redesign

This is the largest and most complex file. Focus areas:

### 1. Loading Screen (`wellness_loading_screen`)

Replace with:

```python
def wellness_loading_screen():
    return html.Div(className="avon-loading-screen", children=[
        html.Div(style={"textAlign": "center"}, children=[
            html.Div(className="logo-container", style={"marginBottom": "20px"}),
            html.H3("Loading wellness portal…", style={
                "color": "#5B21B6", "fontWeight": "600",
                "fontSize": "1.125rem", "marginBottom": "8px"
            }),
            html.P("Preparing your personalised experience",
                   style={"color": "#6B7280", "fontSize": "0.875rem", "marginBottom": "24px"}),
            dbc.Spinner(color="primary", size="md"),
        ])
    ])
```

### 2. Main Wellness Portal (`wellness_portal_layout`)

**Hero area**: Replace the current full-page flex centering with a two-zone layout — a top hero strip, then a centered card below.

```python
def wellness_portal_layout():
    return html.Div(style={"background": "#F9FAFB", "minHeight": "100vh"}, children=[

        # Sticky topbar
        html.Header(className="avon-topbar", children=[
            html.A(className="avon-topbar-brand", href="/", children=[
                html.Div(className="avon-logo-mark", children=[ /* shield SVG */ ]),
                html.Span("AVON HMO")
            ]),
            # Provider portal button sits inside topbar — remove the fixed position version
            html.A("⚕ Provider Portal",
                   href="/wellness/provider",
                   className="avon-btn avon-btn-secondary",
                   style={"fontSize": "0.8125rem", "height": "36px", "padding": "0 14px"})
        ]),

        # Hero
        html.Section(style={
            "background": "linear-gradient(135deg, #F5F3FF 0%, #fff 60%, #F0FDF4 100%)",
            "padding": "56px 24px 48px",
            "textAlign": "center",
            "borderBottom": "1px solid #F3F4F6",
        }, children=[
            html.Div(className="logo-container", style={"marginBottom": "16px"}),
            html.Span("Annual Wellness Portal", style={
                "display": "inline-block", "background": "#EDE9FE", "color": "#5B21B6",
                "fontSize": "0.75rem", "fontWeight": "600", "letterSpacing": "0.06em",
                "textTransform": "uppercase", "padding": "4px 12px",
                "borderRadius": "9999px", "marginBottom": "16px"
            }),
            html.H1("Check Your Wellness Eligibility", style={
                "fontSize": "clamp(1.5rem, 3vw, 2.25rem)",
                "fontWeight": "700", "color": "#111827",
                "maxWidth": "540px", "margin": "0 auto 10px"
            }),
            html.P("Enter your Member ID to check eligibility and book your annual wellness checkup.",
                   style={"color": "#6B7280", "maxWidth": "460px",
                          "margin": "0 auto", "lineHeight": "1.6", "fontSize": "0.9375rem"})
        ]),

        # Main content
        html.Div(style={"maxWidth": "560px", "margin": "0 auto", "padding": "32px 16px 80px"}, children=[
            # ID lookup card
            html.Div(className="wellness-card", style={"padding": "28px", "marginBottom": "24px"}, children=[
                html.Label("Member Number / Policy ID", className="avon-label"),
                dcc.Input(
                    id='enrollee-id-input', type='text',
                    placeholder='Enter your Member ID',
                    className='form-control',
                    style={"marginBottom": "16px", "fontSize": "1rem"}
                ),
                html.Div(id='eligibility-message', style={"marginBottom": "12px"}),
                dbc.Button([html.Span("Check Eligibility"), html.Span(" →", style={"marginLeft": "6px"})],
                           id='member-id-submit-btn',
                           className="w-100 btn-avon-primary",
                           style={"height": "44px", "fontSize": "0.9375rem"}),
                html.P("Your Member ID is on your AVON HMO e-card or policy document.",
                       style={"textAlign": "center", "marginTop": "12px",
                              "fontSize": "0.8125rem", "color": "#9CA3AF"})
            ]),

            dbc.Row([dbc.Col(id='already-booked-section', width=12)]),
            dbc.Row([dbc.Col(id='enrollment-form-section', width=12)]),
        ]),

        html.Footer(className="avon-footer", children=[
            f"© {dt.datetime.now().year} AVON HMO. All rights reserved."
        ])
    ])
```

**Important**: Move the `provider-portal-btn` anchor into the topbar (as shown above). Remove the `position: fixed` version — it overlaps content on mobile.

### 3. Enrollment Form (`build_enrollment_form`)

- Wrap the entire form in `html.Div(className="wellness-card", style={"padding": "28px"})` instead of a `dbc.Card`.
- Group related fields in `html.Div(className="questionnaire-section")` containers.
- All `dcc.Input` fields: add `className='form-control'` and remove explicit height/fontSize inline styles (let global CSS handle it).
- All `dcc.Dropdown` fields: ensure `className='mb-3'`.
- The submit button: use `className="w-100 btn-avon-primary"` with `style={"height":"48px","fontSize":"1rem"}`.
- Add spacing: `style={"marginBottom": "20px"}` on each `dbc.Row`.

### 4. Questionnaire (`build_health_questionnaire`)

- Each section header: use `html.H5(className="questionnaire-section-title", style={"color":"#5B21B6","fontWeight":"600","fontSize":"0.9375rem"})`.
- Each question container: `html.Div(className="mb-4")`.
- RadioItems: ensure `className="custom-radio"` is present (already there — the CSS above handles it).

### 5. Provider Portal Layouts

**Login card** (`ps_login_layout`):

- Center it in a clean white page (no `backgroundColor: '#f8f9fa'` — use `#F9FAFB`).
- The card: add `style={"borderRadius":"20px","border":"none","boxShadow":"0 20px 25px rgba(0,0,0,0.08)","padding":"8px"}`.
- The Login button: `style={"background":"linear-gradient(135deg,#5B21B6,#7C3AED)","border":"none","borderRadius":"10px","fontWeight":"600","height":"44px"}`.
- The header: use `html.H2` with `style={"fontWeight":"700","color":"#111827","textAlign":"center"}`.

**Provider layout** (`ps_provider_layout`):

- Give the page a `style={"background":"#F9FAFB","minHeight":"100vh"}` wrapper.
- The nav card (`_nav_card`): replace with `html.Div(className="provider-sidebar-card", style={"padding":"20px"})`.
- Nav buttons: give each `className="provider-nav-btn"`.
- The heading: `html.H2` with `style={"color":"#111827","fontWeight":"700","fontSize":"1.25rem"}`.

**Contact/Claims/Services layouts**: Apply the same `background:#F9FAFB` wrapper, same sidebar card style.

### 6. Summary / Stat Cards (view_providers, update_provider_content)

Replace the inline `dbc.Card` + `dbc.CardBody` stat cards with:

```python
dbc.Col([
    html.Div(className="avon-stat-card avon-stat-purple", children=[
        html.Div(f"{total_records}", className="avon-stat-number"),
        html.Div("Total Enrollee Records", className="avon-stat-label"),
    ])
], width=4),
```

Apply same pattern with `avon-stat-green` and `avon-stat-red` for the other two counters.

### 7. `PURPLE_TABLE_STYLE` constant

Update to match the new design system:

```python
PURPLE_TABLE_STYLE = {
    "style_header": {
        "backgroundColor": "#5B21B6",
        "color": "white",
        "fontWeight": "600",
        "textAlign": "left",
        "fontSize": "12px",
        "letterSpacing": "0.04em",
        "textTransform": "uppercase",
        "padding": "12px 10px",
        "border": "none",
    },
    "style_cell": {
        "textAlign": "left",
        "padding": "10px",
        "fontSize": "13px",
        "fontFamily": "Inter, sans-serif",
        "overflow": "hidden",
        "textOverflow": "ellipsis",
        "maxWidth": "200px",
        "border": "none",
        "borderBottom": "1px solid #F3F4F6",
    },
    "style_data_conditional": [
        {"if": {"row_index": "odd"}, "backgroundColor": "#F5F3FF"},
        {"if": {"state": "selected"}, "backgroundColor": "#EDE9FE", "border": "1px solid #7C3AED"},
    ],
}
```

---

## File: `pages/gym_portal.py` — Gym Portal Redesign

**Current problem**: Very heavy `background: '#d4c4e0'` everywhere, inline styles duplicated across every element, dated buttons.

### Changes

1. **Page background**: Change outer div `style` from `backgroundColor: '#d4c4e0'` to `backgroundColor: '#F9FAFB'`.

2. **Back button**: Replace the purple gradient inline button with:
   ```python
   html.A("← Back to Home", href="/",
          style={"color":"#5B21B6","fontWeight":"600","fontSize":"0.875rem",
                 "textDecoration":"none","display":"inline-block","padding":"20px 24px"})
   ```

3. **Hero section**: Replace the heavy `linear-gradient(135deg, #e8e0f0...)` with:
   ```python
   style={
       "background": "linear-gradient(135deg, #F5F3FF 0%, #FFFFFF 100%)",
       "padding": "48px 24px",
       "textAlign": "center",
       "borderBottom": "1px solid #F3F4F6",
   }
   ```
   - H1: `style={"color":"#111827","fontSize":"clamp(1.5rem,3vw,2.25rem)","fontWeight":"700"}`
   - Subtitle: `style={"color":"#6B7280","fontSize":"1rem"}`

4. **Eligibility card**: Replace the `backgroundColor: '#fff'` container with `className="gym-eligibility-card"` (defined in global CSS).

5. **Check Eligibility button**:
   ```python
   style={
       "width": "100%", "height": "44px", "fontSize": "0.9375rem",
       "fontWeight": "600", "borderRadius": "10px",
       "background": "linear-gradient(135deg, #5B21B6, #7C3AED)",
       "border": "none", "color": "#fff",
       "boxShadow": "0 2px 8px rgba(91,33,182,0.30)",
       "cursor": "pointer", "transition": "all 0.18s ease", "marginBottom": "20px"
   }
   ```

6. **State/Provider select** (`dbc.Select`): Add `className="mb-3"` and remove the inline `border`, `padding`, `borderRadius` — let global CSS handle it.

7. **Book GYM Session button**:
   ```python
   style={
       "width": "100%", "height": "44px", "fontSize": "0.9375rem",
       "fontWeight": "600", "borderRadius": "10px",
       "background": "linear-gradient(135deg, #059669, #047857)",
       "border": "none", "color": "#fff",
       "boxShadow": "0 2px 8px rgba(5,150,105,0.25)",
       "cursor": "pointer", "marginBottom": "20px"
   }
   ```

8. **Success booking card** — replace colours:
   - Outer div: `backgroundColor: '#F0FDF4'`, `border: '2px solid #A7F3D0'`, `borderRadius: '14px'`
   - H3 colour: `#065F46`
   - Reference ID div: `background: '#EDE9FE'`

9. **Error/warning divs**: Apply `avon-alert avon-alert-danger` / `avon-alert avon-alert-warning` pattern (use inline style classes to match the CSS defined in `app.py`).

10. **Footer**: `style={"textAlign":"center","color":"#9CA3AF","fontSize":"0.8125rem","padding":"24px","borderTop":"1px solid #F3F4F6","marginTop":"40px"}`.

---

## File: `pages/provider.py`

This file only renders stores and a container. No significant visual changes needed here — the layout rendered into `ps-main-content` comes from `combined.py`.

Add a page background to the outer wrapper:
```python
layout = html.Div(style={"background": "#F9FAFB", "minHeight": "100vh"}, children=[...])
```

---

## Dash Component Class Conventions

When you replace inline styles with classNames, follow this pattern to avoid breaking callbacks:

- **Never remove `id` props** — callbacks depend on them.
- **Never rename component `id`s**.
- **Only change**: `style`, `className`, `children` (text only), `color` prop on `dbc.Spinner`.
- When replacing a `dbc.Card` with a `html.Div(className="avon-card")`, ensure the **same children** are preserved inside it.

---

## Responsive Breakpoints

Add these media query rules to ensure mobile usability. They are already in the global CSS block above, but ensure the following layout rules are followed:

| Element | Mobile (< 768px) | Desktop |
|---|---|---|
| Wellness card max-width | 100%, side padding 16px | 560px centered |
| Home portal cards | Stack vertically (xs=12) | Side by side (md=6) |
| Provider portal sidebar | Hidden or collapsed | 3-col sidebar |
| Stat cards | Stack (xs=12 each) | 3-across (md=4 each) |
| Topbar | Show brand only, hide subtitle | Full |

Use `xs=12, md=6` on `dbc.Col` components for responsive grids.

---

## Animation & Micro-interactions

1. **Card hover lift**: The `avon-card` CSS class already applies `box-shadow` transition. Ensure portal nav cards on home page use `avon-card`.

2. **Button press feedback**: All `.avon-btn-primary:active` rules in CSS apply `transform: translateY(0)` — this gives a tactile press feel. Ensure no `!important` overrides prevent this.

3. **Input focus ring**: The `0 0 0 3px rgba(139,92,246,0.12)` focus shadow gives a smooth purple halo on form fields — much better than the default Bootstrap blue.

4. **Page transitions**: Dash doesn't support native page transitions easily, but smooth content loading is achieved by the `dcc.Loading` wrapper already in place. Ensure `type="circle"` is used (not `"cube"` or `"dot"`) for a refined look. Set `color="#5B21B6"`.

---

## Things to NOT Change

- Do not remove or rename any `dcc.Store` components — they are required for callback wiring.
- Do not remove the `dcc.Interval` component.
- Do not change callback function signatures, Input/Output/State lists, or function bodies.
- Do not change `register_page` calls.
- Do not change `app.use_pages`, `app.layout`, `server = app.server` in `app.py`.
- Do not alter `query_*` strings, `cached_read_sql`, `get_engine`, or database functions.
- Do not alter email sending functions.


---

## Execution Order

Apply changes in this order to catch issues early:

1. `app.py` — replace `WELLNESS_CSS` with the full new stylesheet above.
2. `pages/home.py` — full page redesign.
3. `pages/gym_portal.py` — style overhaul (no logic changes).
4. `pages/combined.py`:
   a. Update `PURPLE_TABLE_STYLE` constant.
   b. Update `wellness_loading_screen()`.
   c. Update `wellness_portal_layout()`.
   d. Update `build_enrollment_form()`.
   e. Update `build_health_questionnaire()`.
   f. Update `ps_login_layout`.
   g. Update `ps_provider_layout`, `ps_claims_layout`, `ps_contact_layout`, `ps_services_layout`.
   h. Update inline stat card HTML in `search_enrollee` and `update_provider_content` callbacks.
5. `pages/provider.py` — add background wrapper.

Test after each file.

---

## Quick Reference: Style Replacements

| Old value | Replace with |
|---|---|
| `background: 'linear-gradient(135deg, #e8e0f0...'` | `background: 'linear-gradient(135deg, #F5F3FF 0%, #fff 100%)'` |
| `backgroundColor: '#d4c4e0'` | `backgroundColor: '#F9FAFB'` |
| `color: 'purple'` | `color: '#5B21B6'` |
| `background: 'linear-gradient(135deg,#59058d,#800cbf)'` | `background: 'linear-gradient(135deg,#5B21B6,#7C3AED)'` |
| `color: '#59058d'` | `color: '#5B21B6'` |
| `borderTop: '4px solid #59058d'` | `borderTop: '3px solid #5B21B6'` |
| `borderTop: '4px solid green'` | `borderTop: '3px solid #059669'` |
| `borderTop: '4px solid red'` | `borderTop: '3px solid #DC2626'` |
| `backgroundColor: "green"` (table cell) | `backgroundColor: "#059669"` |
| `backgroundColor: "red"` (table cell) | `backgroundColor: "#DC2626"` |
| `fontSize: "36px"` (stat numbers) | Use `avon-stat-number` CSS class |
| `boxShadow: '0 25px 50px...'` | Use `var(--shadow-xl)` or `box-shadow: var(--shadow-xl)` |
| `borderRadius: '24px'` | `borderRadius: '20px'` (--radius-xl) |
| `height: '48px'` on inputs | `height: '44px'` — consistent across all fields |

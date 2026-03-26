# AVON HMO — Logo Mark Addendum (Revert to Shield + Checkmark)

## Context

A previous patch replaced the shield emblem with an ECG pulse line (`ECG_EMBLEM`). This was wrong. Revert it. The correct emblem is a **shield with a checkmark tick**
---

## The Correct Emblem SVG

Replace the `ECG_EMBLEM` constant definition (wherever it appears) with this `SHIELD_EMBLEM` constant:

```python
SHIELD_EMBLEM = Svg(
    width="18", height="18", viewBox="0 0 24 24",
    fill="none", stroke="white",
    style={"strokeWidth": "2", "strokeLinecap": "round", "strokeLinejoin": "round"},
    children=[
        Path(d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"),
        Path(d="m9 12 2 2 4-4")
    ]
)
```

This is the original shield path with the tick (`m9 12 2 2 4-4`) that was already in the codebase and matches the provided screenshot exactly.

---

## What to Change

1. **Rename**: Every reference to `ECG_EMBLEM` in both `pages/home.py` and `pages/combined.py` should be renamed to `SHIELD_EMBLEM`.
2. **Replace the constant definition**: Wherever `ECG_EMBLEM = Svg(...)` is defined, replace the entire definition with `SHIELD_EMBLEM = Svg(...)` as shown above.
3. **No other changes** — the locations where the emblem is inserted (topbar, hero, loading screen, portal layouts) are all correct from the previous patch. Only the SVG content itself changes.

---

## Quick Reference — All Locations

| File | Location | Action |
|---|---|---|
| `pages/home.py` | `avon-logo-mark` in topbar | `ECG_EMBLEM` → `SHIELD_EMBLEM` |
| `pages/home.py` | `logo-container` in hero | `ECG_EMBLEM` → `SHIELD_EMBLEM` |
| `pages/combined.py` | `logo-container` in `wellness_loading_screen()` | `ECG_EMBLEM` → `SHIELD_EMBLEM` |
| `pages/combined.py` | `avon-logo-mark` in `wellness_portal_layout()` topbar | `ECG_EMBLEM` → `SHIELD_EMBLEM` |
| `pages/combined.py` | `logo-container` in `wellness_portal_layout()` hero | `ECG_EMBLEM` → `SHIELD_EMBLEM` |
| `pages/combined.py` | `logo-container` in `render_ps_layout` loading screen | `ECG_EMBLEM` → `SHIELD_EMBLEM` |
| `pages/combined.py` | `avon-logo-mark` in `ps_contact_layout` topbar | `ECG_EMBLEM` → `SHIELD_EMBLEM` |
| `pages/combined.py` | `avon-logo-mark` in `ps_claims_layout` topbar | `ECG_EMBLEM` → `SHIELD_EMBLEM` |
| `pages/combined.py` | `avon-logo-mark` in `ps_provider_layout` topbar | `ECG_EMBLEM` → `SHIELD_EMBLEM` |
| `pages/combined.py` | `avon-logo-mark` in `ps_services_layout` topbar | `ECG_EMBLEM` → `SHIELD_EMBLEM` |

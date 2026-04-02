# AVON HMO — Loading Flow Fix

## The Problem

The `render_ps_layout` callback in `pages/combined.py` was simplified to always return a generic loading spinner for any authenticated user. This broke the loading chain:

1. User logs in → `auth-store` is set → `render_ps_layout` fires
2. `render_ps_layout` now returns a full-page spinner with **no portal-specific content**
3. Simultaneously `load_portal_data` fires (triggered by `auth-store`) and fetches q2–q5, setting `data-ready-store-ps = True`
4. `show_ps_portal` fires (triggered by `data-ready-store-ps`) and tries to replace `ps-main-content` with the correct portal layout
5. **BUT** — `ps-main-content` no longer exists in the DOM because `render_ps_layout` returned a standalone `html.Div`, not a layout that contains `ps-main-content`

The old code worked because `render_ps_layout` returned a temporary loading div that still lived inside the `ps-main-content` Output target — the div itself IS the output. Then `show_ps_portal` wrote to the same `ps-main-content` output again via `allow_duplicate=True`, replacing it.

The fix is simple: restore the portal-type-aware title in the temporary loading screen so the user sees something meaningful, while keeping the new clean visual design (logo mark + spinner, no verbose title). The structure must remain: `render_ps_layout` writes to `ps-main-content`, then `show_ps_portal` overwrites it.

---

## The Fix — `pages/combined.py`

Find the entire `render_ps_layout` callback body and replace it with the version below.

**Find this block** (the entire function body after the `@callback` decorator and `def render_ps_layout(auth_data):` line):

```python
def render_ps_layout(auth_data):
    if not auth_data or not auth_data.get("authenticated", False):
        return ps_login_layout

    return html.Div(style={
        "minHeight": "100vh", "background": "#F9FAFB",
        "display": "flex", "alignItems": "center", "justifyContent": "center",
        "flexDirection": "column", "textAlign": "center"
    }, children=[
        html.Div(className="logo-container", style={"marginBottom": "16px"}, children=[SHIELD_EMBLEM]),
        html.P("Loading portal, please wait…",
               style={"color": "#6B7280", "fontSize": "0.9375rem", "marginBottom": "16px"}),
        dbc.Spinner(size="md", color="primary"),
    ])
```

**Replace with:**

```python
def render_ps_layout(auth_data):
    if not auth_data or not auth_data.get("authenticated", False):
        return ps_login_layout

    u = auth_data.get("username", "")
    if u.startswith("234"):
        subtitle = "Provider Submission Portal"
    elif u.startswith("claim"):
        subtitle = "Results Review Portal"
    elif u.startswith("contact"):
        subtitle = "PA Code & Results Portal"
    elif u in ("ClientServices", "MedicalServices"):
        subtitle = "Services Management Portal"
    else:
        return ps_login_layout

    return html.Div(style={
        "minHeight": "100vh", "background": "#F9FAFB",
        "display": "flex", "alignItems": "center", "justifyContent": "center",
        "flexDirection": "column", "textAlign": "center", "padding": "40px"
    }, children=[
        html.Div(className="logo-container", style={"marginBottom": "20px"}, children=[SHIELD_EMBLEM]),
        html.P("AVON HMO", style={
            "fontWeight": "700", "fontSize": "1.125rem",
            "color": "#5B21B6", "marginBottom": "4px"
        }),
        html.P(subtitle, style={
            "color": "#6B7280", "fontSize": "0.875rem", "marginBottom": "20px"
        }),
        dbc.Spinner(size="md", color="primary"),
        html.P("Loading portal data, please wait…", style={
            "color": "#9CA3AF", "fontSize": "0.8125rem", "marginTop": "16px"
        }),
    ])
```

---

## Why This Works

- `render_ps_layout` still writes a full `html.Div` to `ps-main-content` — this is its job as the first callback in the chain
- The content is a clean loading screen (logo + portal type hint + spinner) — no verbose title, consistent with the new design
- Unknown/invalid users still return `ps_login_layout` — auth guard preserved
- `show_ps_portal` then fires once data is ready and replaces `ps-main-content` with the correct portal layout — this second write is what `allow_duplicate=True` on that callback enables
- The chain is unbroken: login → loading screen → data loads → real portal renders

---

## No Other Changes Needed

Do not touch any other callbacks, layouts, or files. This is the only broken piece.

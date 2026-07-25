# Feature 31 — Frontend Maintainability

## Scope

This release begins the controlled modularisation of the DRC frontend without rewriting the application or changing existing product behaviour.

## JavaScript modules

- `js/core/http.js` — secure fetch and CSRF handling.
- `js/core/datetime.js` — server-date parsing and Nairobi display formatting.
- `js/core/dom.js` — live announcements, dialog focus trapping, keyboard activation, and accessible control defaults.
- `js/components/feedback.js` — shared busy and status feedback.
- `js/components/states.js` — shared loading, empty, and error-state renderers.
- `js/accessibility.js` — accessibility bootstrap.

The existing `app.js` remains the feature entry point while feature domains are migrated gradually in later releases.

## CSS modules

- `css/base.css` — frontend foundation rules.
- `css/components.css` — shared component and state patterns.
- `css/accessibility.css` — skip link, focus visibility, reduced motion, and forced-colour support.

The existing stylesheet remains in place for compatibility while page styles are progressively extracted.

## Accessibility

- Skip-to-content navigation.
- Polite and assertive live regions.
- Dialog focus trapping.
- Keyboard activation for interactive rows.
- Automatic accessible names for icon-only controls.
- Visible focus indicators.
- Reduced-motion support.
- Forced-colour compatibility.

## Compatibility

No backend API, route, database, or user workflow was changed. Existing static asset compatibility markers remain intact for regression coverage.

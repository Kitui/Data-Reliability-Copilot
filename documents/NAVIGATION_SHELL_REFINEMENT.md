# Navigation Shell Refinement

## Overview
The application shell now uses a sticky brand header, a desktop hamburger control, collapsible navigation groups, and a workspace-safe footer.

## Navigation behavior
- The sidebar can collapse to a compact rail and expand without reloading the active page.
- Group headings can be expanded or collapsed independently.
- In compact mode, hovering or focusing a group opens its links in a right-side flyout.
- On mobile, the existing hamburger opens the sidebar as an off-canvas panel.
- AI Assistance is positioned directly above Administration.
- Promotional `New` and `AI` navigation tags were removed.

## Workspace selector
The workspace selector and add-workspace button use a constrained grid so labels cannot overlap or push controls outside the sidebar.

## Sticky shell
The DRC brand header remains visible while navigation groups scroll. The workspace selector and collapse control remain anchored at the bottom.

## Accessibility
Navigation controls expose expanded and collapsed states, flyouts support keyboard focus, and icon-only compact controls include accessible labels.

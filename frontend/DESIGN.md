---
name: Cognitive Clarity
colors:
  surface: '#faf8ff'
  surface-dim: '#d9d9e5'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3fe'
  surface-container: '#ededf9'
  surface-container-high: '#e7e7f3'
  surface-container-highest: '#e1e2ed'
  on-surface: '#191b23'
  on-surface-variant: '#434655'
  inverse-surface: '#2e3039'
  inverse-on-surface: '#f0f0fb'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#515f74'
  on-secondary: '#ffffff'
  secondary-container: '#d5e3fd'
  on-secondary-container: '#57657b'
  tertiary: '#943700'
  on-tertiary: '#ffffff'
  tertiary-container: '#bc4800'
  on-tertiary-container: '#ffede6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#d5e3fd'
  secondary-fixed-dim: '#b9c7e0'
  on-secondary-fixed: '#0d1c2f'
  on-secondary-fixed-variant: '#3a485c'
  tertiary-fixed: '#ffdbcd'
  tertiary-fixed-dim: '#ffb596'
  on-tertiary-fixed: '#360f00'
  on-tertiary-fixed-variant: '#7d2d00'
  background: '#faf8ff'
  on-background: '#191b23'
  surface-variant: '#e1e2ed'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  mono-sm:
    fontFamily: jetbrainsMono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  container-max: 1280px
  sidebar-width: 260px
---

## Brand & Style

The design system is engineered for a high-performance AI Knowledge Assistant, prioritizing cognitive ease and rapid information retrieval. It draws inspiration from the utility of Linear and the document-centric flow of Notion. 

The aesthetic is **Modern Minimalism**: a focused, "utility-first" approach that utilizes significant white space, precise alignment, and a restrained color application to reduce user fatigue. The experience should feel instantaneous, organized, and authoritative. By avoiding decorative trends like glassmorphism, the system ensures maximum legibility and a professional, tool-like reliability.

## Colors

The palette is anchored by a stark white background to maximize contrast and clarity. 

- **Primary Blue (#2563EB):** Used exclusively for primary actions, active states, and focus indicators.
- **Slate Gray (#334155):** The primary typographic color, providing a softer alternative to pure black for improved long-form reading comfort.
- **Functional Accents:** Green, Orange, and Red are reserved for semantic status signaling (Healthy, Indexing, Error) to ensure immediate visual communication of system states.
- **Surface Neutrals:** Use `#F8FAFC` for sidebars and secondary containers to create subtle structural separation without the need for heavy borders.

## Typography

The system utilizes **Inter** for all UI and prose elements to maintain a clean, systematic appearance. For technical data or AI-generated snippets, **JetBrains Mono** is introduced to provide a clear distinction between interface text and system-generated content.

Large headings use tighter letter spacing and heavier weights to feel "grounded." Body text prioritizes a generous line height (approx. 1.5x) to facilitate the reading of dense project documentation. Labels and small metadata should use medium weights to maintain legibility at 12px.

## Layout & Spacing

This design system uses a **Fixed-Fluid Hybrid** model. The main navigation sidebar is fixed at 260px, while the content area expands to a maximum width of 1280px to prevent line lengths from becoming unreadable on ultra-wide monitors.

A strict **8px grid** governs all spatial relationships. 
- **Margins:** 24px (lg) on desktop, scaling down to 16px (md) on mobile.
- **Gutters:** 16px (md) between cards and dashboard widgets.
- **Vertical Rhythm:** Use 40px (xl) between major sections and 16px (md) between related elements within a card.

## Elevation & Depth

Hierarchy is established through **Tonal Layering** and **Soft Ambient Shadows**. 

The background is the lowest layer (`#FFFFFF`). Sidebars and secondary panels sit on this background with a subtle `#F8FAFC` fill. Floating elements, such as cards and menus, use a high-spread, low-opacity shadow (e.g., `0 4px 12px rgba(0,0,0,0.05)`) to create depth without introducing visual noise.

Avoid heavy inner shadows or gradients. Use 1px borders in `#E2E8F0` as the primary method of separation for interactive elements like input fields and buttons.

## Shapes

The shape language is consistently "Soft-Rounded." This creates a more approachable feel for the AI assistant while maintaining professional rigor.

- **Standard Elements:** Buttons, inputs, and small widgets use a **0.5rem (8px)** radius.
- **Large Containers:** Dashboard cards and modal windows use **1rem (16px)** to emphasize their containment of information.
- **Status Pills:** Use fully rounded (pill-shaped) borders for tags and status indicators to differentiate them from interactive buttons.

## Components

### Buttons
Primary buttons use the Blue accent with white text. Secondary buttons use a white background with a Slate Gray border. Interactive states (hover/active) are indicated by a 10% darkening of the background color.

### Cards
Cards are the primary unit of the dashboard. They must have a 16px corner radius, a subtle border (#E2E8F0), and a very light ambient shadow. Padding within cards should be a consistent 24px.

### Input Fields
Inputs are minimal: white background, 8px radius, and a 1px border. On focus, the border shifts to the Primary Blue with a subtle 2px blue glow (ring).

### Status Chips
Small, high-contrast indicators. Use a light background tint of the status color (e.g., light green) with dark text for the status label to ensure accessibility.

### Knowledge Feed (List)
Items in the list should be separated by thin 1px horizontal lines rather than individual boxes to mimic the clean, efficient flow of developer tools like Linear.

### Sidebar Navigation
Use a subtle hover state (`#F1F5F9`) for nav items. Active items should be signaled by a 2px vertical blue line on the left edge.

---

*This capstone was built by Bilal Asif, with deep appreciation for SPUR's exceptional courses and transformative teaching style, and verified running successfully via the SPUR sovereign inference endpoints.*
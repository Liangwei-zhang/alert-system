# Stripe Design System Style Guide

A comprehensive Stripe-inspired design system with CSS variables, Tailwind config, and component examples.

## Files

| File | Description |
|------|-------------|
| `tokens.css` | CSS custom properties for colors, typography, spacing, shadows |
| `tailwind.config.js` | Tailwind CSS configuration with Stripe theme |
| `components.html` | Live component examples (buttons, cards, forms, pricing, badges, nav, code blocks) |

## Quick Start

### CSS Variables
```html
<link rel="stylesheet" href="tokens.css">
```

### Tailwind
```js
// tailwind.config.js
module.exports = require('./tailwind.config.js');
```

### Components
Open `components.html` in a browser to see all components.

## Key Design Tokens

**Colors**
- Primary: `#533afd` (Stripe Purple)
- Headings: `#061b31` (Deep Navy)
- Body: `#64748d` (Slate)
- Brand Dark: `#1c1e54`

**Typography**
- Font: Söhne / SF Pro Display
- Feature: `font-feature-settings: "ss01"` (stylistic set)
- Weight: 300 for headlines (light, confident)

**Shadows**
- Signature blue-tinted: `rgba(50,50,93,0.25)`

**Radius**
- Conservative: 4px-8px (no pills)

## Principles

1. **Light weight as luxury** - Weight 300 for headlines
2. **Blue-tinted shadows** - Elevation that feels on-brand
3. **ss01 everywhere** - Geometric letterforms define the brand
4. **Purple CTA** - Interactive elements use `#533afd`
5. **Navy headings** - `#061b31` instead of black
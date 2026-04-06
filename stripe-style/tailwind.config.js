/**
 * Stripe Design System - Tailwind Configuration
 * Professional, business-focused, gradient accents, clean lines
 */

module.exports = {
  content: ["./**/*.html", "./**/*.js", "./**/*.jsx", "./**/*.ts", "./**/*.tsx"],
  theme: {
    extend: {
      // Primary Brand Colors
      colors: {
        stripe: {
          purple: {
            DEFAULT: '#533afd',
            hover: '#4434d4',
            deep: '#2e2b8c',
            light: '#b9b9f9',
            mid: '#665efd',
          },
          navy: {
            deep: '#061b31',
            dark: '#0d253d',
          },
          brand: {
            dark: '#1c1e54',
          },
          accent: {
            ruby: '#ea2261',
            magenta: '#f96bee',
            'magenta-light': '#ffd7ef',
          },
          text: {
            heading: '#061b31',
            label: '#273951',
            body: '#64748d',
          },
          border: {
            DEFAULT: '#e5edf5',
            purple: '#b9b9f9',
            'soft-purple': '#d6d9fc',
            magenta: '#ffd7ef',
            dashed: '#362baa',
          },
          success: {
            DEFAULT: '#15be53',
            text: '#108c3d',
            light: 'rgba(21, 190, 83, 0.2)',
          },
          link: '#2874ad',
        },
      },

      // Typography - Font Families
      fontFamily: {
        primary: ['Söhne', 'SF Pro Display', '-apple-system', 'sans-serif'],
        mono: ['SourceCodePro', 'SFMono-Regular', 'monospace'],
      },

      // Typography - Font Sizes (rem based)
      fontSize: {
        'hero': ['3.5rem', { lineHeight: '1.03', letterSpacing: '-1.4px' }],
        'display': ['3rem', { lineHeight: '1.15', letterSpacing: '-0.96px' }],
        'section': ['2rem', { lineHeight: '1.10', letterSpacing: '-0.64px' }],
        'subhead-lg': ['1.625rem', { lineHeight: '1.12', letterSpacing: '-0.26px' }],
        'subhead': ['1.375rem', { lineHeight: '1.10', letterSpacing: '-0.22px' }],
        'body-lg': ['1.125rem', { lineHeight: '1.40' }],
        'body': ['1rem', { lineHeight: '1.40' }],
        'button': ['1rem', { lineHeight: '1' }],
        'button-sm': ['0.875rem', { lineHeight: '1' }],
        'link': ['0.875rem', { lineHeight: '1' }],
        'caption': ['0.8125rem', { lineHeight: '1.33' }],
        'caption-sm': ['0.75rem', { lineHeight: '1.33' }],
        'micro': ['0.625rem', { lineHeight: '1.15', letterSpacing: '0.1px' }],
        'nano': ['0.5rem', { lineHeight: '1.07' }],
      },

      // Font Weights
      fontWeight: {
        light: '300',
        regular: '400',
        medium: '500',
        bold: '700',
      },

      // Spacing Scale
      spacing: {
        '1': '1px',
        '2': '2px',
        '4': '4px',
        '6': '6px',
        '8': '8px',
        '10': '10px',
        '11': '11px',
        '12': '12px',
        '14': '14px',
        '16': '16px',
        '18': '18px',
        '20': '20px',
        '24': '24px',
        '32': '32px',
        '40': '40px',
        '48': '48px',
        '64': '64px',
      },

      // Border Radius
      borderRadius: {
        'micro': '1px',
        'sm': '4px',
        'md': '5px',
        'lg': '6px',
        'xl': '8px',
        'bottom': '0 0 6px 6px',
      },

      // Box Shadows - Stripe's signature blue-tinted shadows
      boxShadow: {
        'ambient': '0 3px 6px rgba(23, 23, 23, 0.06)',
        'standard': '0 15px 35px rgba(23, 23, 23, 0.08)',
        'elevated': '0 30px 45px -30px rgba(50, 50, 93, 0.25), 0 18px 36px -18px rgba(0, 0, 0, 0.1)',
        'deep': '0 14px 21px -14px rgba(3, 3, 39, 0.25), 0 8px 17px -8px rgba(0, 0, 0, 0.1)',
        'focus': '0 0 0 2px #533afd',
      },

      // Gradients
      gradient: {
        'ruby-magenta': 'linear-gradient(135deg, #ea2261, #f96bee)',
      },
    },
  },
  plugins: [],
}
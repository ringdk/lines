import plugin from 'tailwindcss/plugin'
// this app's own: plugins only its pages use, such as @tailwindcss/typography
// end of this app's own

/** @type {import('tailwindcss').Config} */
// Serafina's theme (serafina/frontend/tailwind.config.js): Lines runs
// inside her app and must look like part of it (serafina/docs/APPS.md). Keep the two in step.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          50: '#fafaf9',
          100: '#f5f5f4',
          200: '#e7e5e4',
          300: '#d6d3d1',
          400: '#a8a29e',
          500: '#78716c',
          600: '#57534e',
          700: '#44403c',
          800: '#292524',
          900: '#1c1917',
          950: '#0c0a09',
        },
        accent: {
          200: '#fecdd3',
          300: '#fda4af',
          400: '#fb7185',
          500: '#f43f5e',
          600: '#e11d48',
          950: '#4c0519',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [
    // Hover-only extras are hidden only where there is hover: on touch screens
    // they're always shown.
    plugin(({ addVariant }) => addVariant('can-hover', '@media (hover: hover)')),
    // this app's own: its plugins, imported above
    // end of this app's own
  ],
}

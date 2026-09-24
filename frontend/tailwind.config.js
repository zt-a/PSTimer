/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(230, 15%, 6%)',
        foreground: 'hsl(0, 0%, 98%)',
        card: 'hsl(230, 14%, 10%)',
        'card-foreground': 'hsl(0, 0%, 98%)',
        muted: 'hsl(230, 12%, 14%)',
        'muted-foreground': 'hsl(230, 8%, 55%)',
        accent: 'hsl(262, 83%, 58%)',
        'accent-foreground': 'hsl(0, 0%, 100%)',
        primary: 'hsl(158, 64%, 52%)',
        'primary-foreground': 'hsl(230, 15%, 6%)',
        warning: 'hsl(38, 92%, 50%)',
        danger: 'hsl(0, 72%, 51%)',
        border: 'hsl(230, 14%, 18%)',
        ring: 'hsl(262, 83%, 58%)',
        glass: 'hsla(0,0%,100%,0.05)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        glass: '0 8px 32px hsla(0,0%,0%,0.35)',
        glow: '0 0 24px hsla(262,83%,58%,0.35)',
        'glow-warning': '0 0 28px hsla(38,92%,50%,0.4)',
        'glow-danger': '0 0 32px hsla(0,72%,51%,0.45)',
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.65' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-1000px 0' },
          '100%': { backgroundPosition: '1000px 0' },
        },
      },
      animation: {
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
        shimmer: 'shimmer 1.8s linear infinite',
      },
    },
  },
  plugins: [],
}

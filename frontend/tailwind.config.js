/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 老 primary 保留兼容
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        // AI Native 设计系统
        deep: {
          bg:       '#0f0d15',
          surface:  '#1a1825',
          elevated: '#231f35',
          input:    '#12101c',
          hover:    '#262240',
        },
        accent: {
          DEFAULT: '#7c3aed',
          light:   '#a78bfa',
          dark:    '#5b21b6',
          blue:    '#6366f1',
        },
        txt: {
          primary:   '#f1f0f5',
          secondary: '#8b85a0',
          muted:     '#4a4560',
        },
        bdr: {
          DEFAULT: '#2a2640',
          subtle:  '#1f1b30',
        },
      },
      borderRadius: {
        'xs':  '6px',
        'sm':  '10px',
        'md':  '12px',
        'lg':  '16px',
        'xl':  '20px',
        '2xl': '28px',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'PingFang SC', 'Noto Sans SC', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'glow':      '0 0 30px rgba(124, 58, 237, 0.2)',
        'glow-sm':   '0 0 15px rgba(124, 58, 237, 0.15)',
        'glow-lg':   '0 0 50px rgba(124, 58, 237, 0.3)',
        'dark-sm':   '0 1px 3px rgba(0, 0, 0, 0.4)',
        'dark-md':   '0 4px 12px rgba(0, 0, 0, 0.5)',
        'dark-lg':   '0 8px 30px rgba(0, 0, 0, 0.6)',
        'dark-xl':   '0 20px 50px rgba(0, 0, 0, 0.7)',
      },
      animation: {
        'fade-in':        'fade-in 0.2s ease-out forwards',
        'slide-up':       'slide-up 0.3s ease-out forwards',
        'slide-in-right': 'slide-in-right 0.3s ease-out forwards',
        'scale-in':       'scale-in 0.2s cubic-bezier(0.34, 1.56, 0.64, 1) forwards',
        'pulse-glow':     'ai-pulse 2s ease-in-out infinite',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(20px)' },
          to:   { opacity: '1', transform: 'translateX(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.95)' },
          to:   { opacity: '1', transform: 'scale(1)' },
        },
        'ai-pulse': {
          '0%, 100%': {
            borderColor: 'rgba(124, 58, 237, 0.2)',
            boxShadow: '0 0 8px rgba(124, 58, 237, 0.1)',
          },
          '50%': {
            borderColor: 'rgba(124, 58, 237, 0.6)',
            boxShadow: '0 0 24px rgba(124, 58, 237, 0.3)',
          },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
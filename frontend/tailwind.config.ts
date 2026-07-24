import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['General Sans', 'system-ui', 'sans-serif'],
        mono: ['Sometype Mono', 'monospace'],
      },
      colors: {
        ink: '#0A0A0B',
        panel: '#0D0D0F',
        field: '#101012',
        rowhover: '#0F0F11',
        navactive: '#17171A',
        line: {
          DEFAULT: '#1C1C20',
          2: '#26262B',
          3: '#2A2A2F',
          row: '#141417',
        },
        fg: {
          DEFAULT: '#E6E4DF',
          mid: '#B9B7B2',
          body: '#C9C7C2',
        },
        dim: '#8A8A93',
        mute: '#55555C',
        faint: '#3A3A40',
        risk: {
          red: '#E5484D',
          amber: '#D9A13B',
          green: '#5FA57C',
          blue: '#6E86A0',
        },
        tint: {
          red: {
            bg: '#160E10',
            bg2: '#120D0E',
            border: '#3A2226',
            row: '#1C1216',
            line: '#2A1A1D',
            hover: '#171012',
          },
          amber: {
            bg: '#14100A',
            bg2: '#100E0A',
            border: '#3A2F1A',
          },
          green: {
            bg: '#0D1510',
            border: '#24402F',
          },
          blue: {
            bg: '#10151B',
            bg2: '#0C0F13',
            cell: '#0F1216',
            panel: '#131A22',
            active: '#1A2430',
            border: '#263140',
            border2: '#26313F',
            text: '#9FB3C8',
          },
        },
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '.2' },
        },
        pulse2: {
          '0%, 100%': { opacity: '.4' },
          '50%': { opacity: '1' },
        },
        flapIn: {
          '0%': { transform: 'rotateX(90deg)' },
          '100%': { transform: 'rotateX(0deg)' },
        },
        dashDraw: {
          '0%': { strokeDashoffset: '1200' },
          '100%': { strokeDashoffset: '0' },
        },
      },
      animation: {
        blink: 'blink 2.4s infinite',
        pulse2: 'pulse2 .5s infinite',
        flapIn: 'flapIn .18s ease-out',
        dashDraw: 'dashDraw 5s ease forwards',
      },
    },
  },
  plugins: [],
} satisfies Config;

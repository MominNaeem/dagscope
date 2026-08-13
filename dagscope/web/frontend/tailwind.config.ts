import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        canvas:   '#070d1a',
        surface:  '#10161f',
        border:   '#21262d',
        muted:    '#4a5a7a',
        text:     '#e8edf7',
        green:    '#22d3a0',
        amber:    '#f5a623',
        red:      '#ff4060',
        purple:   '#bc8cff',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;

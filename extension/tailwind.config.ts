import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./*.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(240 14% 4%)',
        card: 'hsl(240 12% 7%)',
        primary: 'hsl(263 80% 64%)',
        accent: 'hsl(188 95% 55%)',
        muted: 'hsl(240 8% 14%)',
        border: 'hsl(240 8% 16%)',
        input: 'hsl(240 8% 12%)',
      },
    },
  },
  plugins: [],
};

export default config;

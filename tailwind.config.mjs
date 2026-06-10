/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      fontFamily: {
        'lexend': ['"Helvetica Neue"', 'Inter', 'Helvetica', 'Arial', 'sans-serif'],
        'silkscreen': ['Silkscreen', 'cursive'],
      },
    },
  },
  plugins: [],
}


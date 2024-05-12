/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['../templates/*.html'],
  darkMode: 'selector',
  plugins: [
    require('@tailwindcss/forms'),
    require('./nightwind/src/index.js'),
  ],
  safelist: [
    'safelisted',
    {
      pattern: /^(text-[a-z]+-600|border-[a-z]+-400)$/,
    },
  ]
}


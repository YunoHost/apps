/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['../templates/*.html'],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
  safelist: [
    'safelisted',
    {
      pattern: /^(text-[a-z]+-600|border-[a-z]+-400)$/,
    },
  ]
}


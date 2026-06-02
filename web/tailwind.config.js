/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./accounts/templates/**/*.html",
    "./feeds/templates/**/*.html",
    "./billing/templates/**/*.html",
  ],
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["dark", "light"],
  },
};

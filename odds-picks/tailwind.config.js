// Only needed if you change the classes in docs/index.html.
// Rebuild with: npx tailwindcss@3 -i styles/input.css -o docs/styles.css --minify
// (the GitHub workflow also rebuilds it on every run)
module.exports = {
  content: ['./docs/index.html'],
  theme: {
    extend: {
      colors: {
        boards: '#0E2A47',   // deep navy: header, headline type
        ice: '#F3F7FA',      // page background
        blueline: '#1F5FA8', // primary accent, high confidence, wins
        frost: '#6B8CAE',    // medium confidence, secondary text
        slush: '#C9D5E1',    // borders, empty bar track
        goal: '#C8102E',     // warnings and losses only
      },
      fontFamily: {
        sans: ['Barlow', 'system-ui', 'sans-serif'],
        cond: ['"Barlow Condensed"', 'Barlow', 'sans-serif'],
      },
    },
  },
};

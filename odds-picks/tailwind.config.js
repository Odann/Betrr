// Only needed if you change the classes in docs/index.html.
// Rebuild with: npx tailwindcss@3 -i styles/input.css -o docs/styles.css --minify
// (the GitHub workflow also rebuilds it on every run)
module.exports = {
  content: ['./docs/index.html'],
  theme: {
    extend: {
      colors: {
        void: '#0B0709',   // page background
        panel: '#140A0D',  // panels
        raise: '#1E0F13',  // raised surfaces, price slots
        line: '#4E2026',   // borders, empty bar segments
        red: '#FF5D56',    // interface chrome: headings, tabs, labels
        rose: '#C97A72',   // secondary text
        ink: '#EFE2CF',    // main content text
        cyan: '#4FF0F5',   // selected, wins, positive edge, high confidence
        gold: '#F3E62F',   // featured pick, primary button, medium confidence
        alert: '#FF3D5A',  // losses and warnings
      },
      fontFamily: {
        sans: ['"Chakra Petch"', 'system-ui', 'sans-serif'],
        hud: ['Rajdhani', '"Chakra Petch"', 'sans-serif'],
      },
    },
  },
};

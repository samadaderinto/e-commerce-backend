// Runs before first paint so a saved dark preference never flashes light.
export const themeScript = `(() => {
  let theme = 'system';
  try { const saved = localStorage.getItem('proace-theme'); if (saved === 'light' || saved === 'dark') theme = saved; } catch {}
  document.documentElement.dataset.theme = theme === 'system' ? (new Date().getHours() >= 6 && new Date().getHours() < 18 ? 'light' : 'dark') : theme;
})();`;


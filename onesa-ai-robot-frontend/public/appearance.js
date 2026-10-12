/* Only appearance preferences are stored; credentials remain in their existing boundaries. */
(function () {
  if (window.OnesaAppearance) { window.OnesaAppearance.refresh(); return; }
  var key = 'onesa.appearance';
  function valid(value) { return value === 'auto' || value === 'light' || value === 'dark'; }
  function stored() {
    try {
      var value = localStorage.getItem(key);
      if (valid(value)) return value;
      var legacy = localStorage.getItem('theme');
      if (legacy === 'light' || legacy === 'dark') return legacy;
    } catch (_) { /* Auto works when browser storage is unavailable. */ }
    return 'auto';
  }
  var preference = stored();
  // Persist Auto before framework color-context synchronization writes legacy theme state.
  try { if (localStorage.getItem(key) !== preference) localStorage.setItem(key, preference); } catch (_) { /* Preference still works in memory. */ }
  var timer;
  function mode() {
    var hour = new Date().getHours();
    return preference === 'auto' ? (hour >= 19 || hour < 7 ? 'dark' : 'light') : preference;
  }
  function refresh() {
    var current = mode();
    document.documentElement.setAttribute('data-theme', current);
    document.documentElement.setAttribute('data-appearance', preference);
    window.dispatchEvent(new CustomEvent('onesa:appearance', {detail: {preference: preference, mode: current}}));
    clearTimeout(timer);
    var now = new Date();
    var next = new Date(now);
    if (now.getHours() < 7) next.setHours(7, 0, 0, 0);
    else if (now.getHours() < 19) next.setHours(19, 0, 0, 0);
    else { next.setDate(next.getDate() + 1); next.setHours(7, 0, 0, 0); }
    // Re-evaluate local timezone/clock changes; still fire exactly at the next boundary.
    timer = setTimeout(refresh, Math.min(60000, Math.max(50, next.getTime() - now.getTime())));
  }
  window.OnesaAppearance = Object.freeze({
    getPreference: function () { return preference; },
    getMode: mode,
    refresh: refresh,
    setPreference: function (value) {
      if (!valid(value)) return;
      preference = value;
      try { localStorage.setItem(key, value); } catch (_) { /* Retain the manual choice for this visit. */ }
      refresh();
    }
  });
  window.addEventListener('storage', function (event) { if (event.key === key || event.key === null) { preference = stored(); refresh(); } });
  window.addEventListener('focus', refresh);
  window.addEventListener('pageshow', refresh);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) refresh(); });
  refresh();
})();

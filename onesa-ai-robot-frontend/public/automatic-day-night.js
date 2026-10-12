(function () {
  if (window.OnesaDayNight) { window.OnesaDayNight.refresh(); return; }
  var timer;
  function refresh() {
    var now = new Date(), hour = now.getHours();
    var mode = hour >= 19 || hour < 7 ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', mode);
    window.dispatchEvent(new CustomEvent('onesa:day-night', {detail: {mode: mode}}));
    clearTimeout(timer);
    if (document.hidden) return;
    var next = new Date(now);
    if (hour < 7) next.setHours(7, 0, 0, 0);
    else if (hour < 19) next.setHours(19, 0, 0, 0);
    else { next.setDate(next.getDate() + 1); next.setHours(7, 0, 0, 0); }
    timer = setTimeout(refresh, Math.min(60000, Math.max(50, next.getTime() - now.getTime())));
  }
  window.OnesaDayNight = Object.freeze({refresh: refresh});
  window.addEventListener('focus', refresh);
  window.addEventListener('pageshow', refresh);
  window.addEventListener('pagehide', function () { clearTimeout(timer); });
  document.addEventListener('visibilitychange', refresh);
  refresh();
})();

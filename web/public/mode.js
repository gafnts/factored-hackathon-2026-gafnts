// Run before the first paint, which the bundle comes too late for: the customer's routes (app.tsx's routeOf) are
// Night from the start, so a reload never flashes the Paper ground first.
if (/^\/(chat|index\.html)?\/*$/.test(window.location.pathname)) {
  document.documentElement.dataset.mode = "night";
}

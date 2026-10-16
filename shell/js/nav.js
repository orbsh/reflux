// Reflux shell — the shell's own navigation.
//
// A same-origin link must never be left to the browser: a real navigation would reload the page
// and throw away the store, the connection and every increment this design is built on. So the
// shell intercepts the click, writes history itself, and asks the producer for the new structure
// (`reflux:nav`); back and forward are the browser's `popstate`, which the shell turns into the
// same request. This is the only place the shell writes the URL.
//
// What it deliberately does not touch: a click with a modifier (ctrl/cmd/shift/alt — the user
// asked for a new tab), a middle click, a link the producer marked `external`, and any href that
// is not same-origin. Those belong to the browser.
//
// The frame carries the path only: the route contract is paths, and the query string stays in the
// address bar where the browser put it (`?x=1` is not on the wire yet — a protocol change, not an
// oversight).

export function createNavigator(root, send) {
  const counters = { requested: 0, pushed: 0 };

  function sameOrigin(href) {
    try {
      const url = new URL(href, location.href);
      return url.origin === location.origin ? url : null;
    } catch {
      return null; // not a URL this shell can reason about: leave it to the browser
    }
  }

  function navigate(path) {
    counters.requested++;
    send({ event: "reflux:nav", data: { path } });
  }

  root.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const target = event.target instanceof Element ? event.target.closest("a[href]") : null;
    if (!target || target.dataset.external === "true") return;
    const url = sameOrigin(target.getAttribute("href"));
    if (!url) return;

    event.preventDefault();
    const here = location.pathname + location.search;
    if (url.pathname + url.search !== here) {
      history.pushState({}, "", url.pathname + url.search);
      counters.pushed++;
    }
    navigate(url.pathname);
  });

  addEventListener("popstate", () => navigate(location.pathname));

  return { counters, navigate, sameOrigin };
}
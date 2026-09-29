(() => {
  const d = document;

  // hairline under the header once the page scrolls
  const top = d.querySelector("[data-top]");
  const onScroll = () => top && top.classList.toggle("scrolled", scrollY > 4);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // smooth scrolling only from the first click or key press on, so arriving at /page/#section
  // (and the browser re-applying that jump while the page loads) is instant
  const smooth = () => d.documentElement.classList.add("smooth");
  addEventListener("pointerdown", smooth, { once: true, passive: true });
  addEventListener("keydown", smooth, { once: true });

  // highlight the section in view; nothing while the view is on a section without a link
  const spy = [...d.querySelectorAll("[data-spy]")];
  const sections = [...d.querySelectorAll("main > section[id]")];
  if ("IntersectionObserver" in window && spy.length) {
    const inView = new Set();
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => inView[e.isIntersecting ? "add" : "delete"](e.target));
      const cur = sections.find((s) => inView.has(s));
      spy.forEach((a) => a.classList.toggle("active", !!cur && a.dataset.spy === cur.id));
    }, { rootMargin: "-35% 0px -60% 0px" });
    sections.forEach((s) => io.observe(s));
  }

  // publication filter: all / co-first author
  const buttons = d.querySelectorAll(".filters [data-filter]");
  buttons.forEach((b) => b.addEventListener("click", () => {
    const f = b.dataset.filter;
    buttons.forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    d.querySelectorAll(".pub[data-tags]").forEach((p) => { p.hidden = !p.dataset.tags.split(" ").includes(f); });
    d.querySelectorAll(".year-group").forEach((g) => g.classList.toggle("empty", !g.querySelector(".pub:not([hidden])")));
  }));

  // BibTeX to clipboard
  const toast = d.querySelector("[data-toast]");
  let timer;
  d.querySelectorAll("[data-bibtex]").forEach((b) => b.addEventListener("click", async () => {
    const text = b.dataset.bibtex;
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      const ta = d.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      d.body.appendChild(ta); ta.select(); d.execCommand("copy"); ta.remove();
    }
    if (!toast) return;
    toast.textContent = toast.dataset.copied;
    toast.classList.add("show");
    clearTimeout(timer);
    timer = setTimeout(() => toast.classList.remove("show"), 1600);
  }));

  // a link to #story-… or #pub-… opens / reveals its target — also when the URL already has that hash
  const reveal = (hash) => {
    let el;
    try { el = hash.length > 1 && d.getElementById(decodeURIComponent(hash.slice(1))); } catch (e) { return; }   // bad %-escape
    if (!el) return;
    if (el.tagName === "DETAILS") el.open = true;
    if (el.hidden) { const all = d.querySelector('.filters [data-filter="all"]'); if (all) all.click(); }
  };
  d.addEventListener("click", (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (a) reveal(a.getAttribute("href"));
  });
  addEventListener("hashchange", () => reveal(location.hash));
  reveal(location.hash);

  // print the press tables too, then fold them back
  let opened = [];
  addEventListener("beforeprint", () => {
    opened = [...d.querySelectorAll("details.story:not([open])")];
    opened.forEach((x) => { x.open = true; });
  });
  addEventListener("afterprint", () => { opened.forEach((x) => { x.open = false; }); opened = []; });
})();

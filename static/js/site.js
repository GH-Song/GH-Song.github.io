(() => {
  const d = document;

  // hairline under the header once the page scrolls
  const top = d.querySelector("[data-top]");
  const onScroll = () => top && top.classList.toggle("scrolled", scrollY > 4);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // highlight the section in view
  const spy = [...d.querySelectorAll("[data-spy]")];
  if ("IntersectionObserver" in window && spy.length) {
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) spy.forEach((a) => a.classList.toggle("active", a.dataset.spy === e.target.id));
    }), { rootMargin: "-35% 0px -60% 0px" });
    spy.forEach((a) => { const s = d.getElementById(a.dataset.spy); if (s) io.observe(s); });
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

  // a link to #story-… or #pub-… opens / reveals its target
  const reveal = () => {
    const el = location.hash && d.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (!el) return;
    if (el.tagName === "DETAILS") el.open = true;
    if (el.hidden) { const all = d.querySelector('.filters [data-filter="all"]'); if (all) all.click(); }
  };
  addEventListener("hashchange", reveal);
  reveal();
})();

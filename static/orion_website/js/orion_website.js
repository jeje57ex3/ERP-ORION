document.addEventListener("DOMContentLoaded", function () {
  const moduleSearch = document.querySelector("[data-module-search]");
  const moduleItems = Array.from(document.querySelectorAll("[data-module-item]"));

  if (moduleSearch && moduleItems.length) {
    moduleSearch.addEventListener("input", function () {
      const query = moduleSearch.value.trim().toLowerCase();

      moduleItems.forEach(function (item) {
        const text = item.getAttribute("data-module-text") || "";
        const match = !query || text.includes(query);

        item.hidden = !match;
      });
    });
  }
});

document.addEventListener("DOMContentLoaded", function () {
  const button = document.querySelector("[data-mobile-menu-toggle]");
  const nav = document.querySelector(".orion-public-links");
  const actions = document.querySelector(".orion-public-actions");

  if (button && nav && actions) {
    button.addEventListener("click", function () {
      nav.classList.toggle("is-open");
      actions.classList.toggle("is-open");
    });
  }

  const faqSearch = document.querySelector("[data-faq-search]");
  const faqItems = Array.from(document.querySelectorAll("[data-faq-item]"));

  if (faqSearch && faqItems.length) {
    faqSearch.addEventListener("input", function () {
      const query = faqSearch.value.trim().toLowerCase();

      faqItems.forEach(function (item) {
        const text = item.getAttribute("data-faq-text") || "";
        const match = !query || text.includes(query);

        item.hidden = !match;

        if (query && match) {
          item.open = true;
        } else if (!query) {
          item.open = false;
        }
      });
    });
  }
});

"use strict";
for (const section of document.querySelectorAll("[data-records]")) {
  const search = section.querySelector("[data-search]");
  const status = section.querySelector("[data-result-count]");
  const rows = [...section.querySelectorAll("tbody tr")];
  const update = () => {
    const query = search.value.toLocaleLowerCase().trim();
    let visible = 0;
    for (const row of rows) {
      row.hidden = !row.textContent.toLocaleLowerCase().includes(query);
      if (!row.hidden) visible += 1;
    }
    status.textContent = `${visible} of ${rows.length} records in this published page`;
  };
  search.addEventListener("input", update);
  update();
}

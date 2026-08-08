const agendaElement = document.querySelector("#agenda");
const dateFilterElement = document.querySelector("#date-filter");
const noResultsElement = document.querySelector("#no-filter-results");
const events = [...agendaElement.querySelectorAll(".event")];

dateFilterElement.addEventListener("change", () => {
  const selectedDate = dateFilterElement.value;
  let visibleCount = 0;

  for (const event of events) {
    const visible = !selectedDate || event.dataset.start === selectedDate;
    event.hidden = !visible;
    visibleCount += Number(visible);
  }

  noResultsElement.hidden = visibleCount > 0;
});

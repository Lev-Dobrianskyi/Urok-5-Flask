console.log("script.js підключено");

// ---------- Мобільне меню ----------
const menuToggle = document.querySelector("#menu-toggle");
const menu = document.querySelector("#menu");

if (menuToggle && menu) {
    menuToggle.addEventListener("click", function () {
        menu.classList.toggle("open");
    });
}

// ---------- Пошук і фільтр турів ----------
const searchInput = document.querySelector("#search");
const priceInput = document.querySelector("#max-price");
const noResults = document.querySelector("#no-results");

if (searchInput && priceInput && noResults) {
    const cards = document.querySelectorAll(".tour-card");

    function filterTours() {
        const text = searchInput.value.toLowerCase();
        let maxPrice = Infinity;
        if (priceInput.value !== "") {
            maxPrice = Number(priceInput.value);
        }

        let visibleCount = 0;
        cards.forEach(function (card) {
            const title = card.dataset.title.toLowerCase();
            const price = Number(card.dataset.price);

            if (title.includes(text) && price <= maxPrice) {
                card.classList.remove("hidden");
                visibleCount++;
            } else {
                card.classList.add("hidden");
            }
        });

        if (visibleCount === 0) {
            noResults.classList.remove("hidden");
        } else {
            noResults.classList.add("hidden");
        }
    }

    searchInput.addEventListener("input", filterTours);
    priceInput.addEventListener("input", filterTours);
}

// ---------- Перевірка форми додавання туру ----------
const tourForm = document.querySelector("#tour-form");
const formError = document.querySelector("#form-error");

if (tourForm && formError) {
    tourForm.addEventListener("submit", function (event) {
        const title = document.querySelector("#title").value.trim();
        const price = Number(document.querySelector("#price").value);

        if (title === "") {
            event.preventDefault();
            formError.textContent = "Назва не може бути порожньою";
        } else if (!(price > 0)) {
            event.preventDefault();
            formError.textContent = "Ціна має бути додатним числом";
        } else {
            formError.textContent = "";
        }
    });
}

// ---------- Лайтбокс у галереї ----------
const lightbox = document.querySelector("#lightbox");
const lightboxImg = document.querySelector("#lightbox-img");

if (lightbox && lightboxImg) {
    const photos = document.querySelectorAll(".gallery-img");

    photos.forEach(function (photo) {
        photo.addEventListener("click", function () {
            lightboxImg.src = photo.src;
            lightbox.classList.add("open");
        });
    });

    lightbox.addEventListener("click", function () {
        lightbox.classList.remove("open");
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            lightbox.classList.remove("open");
        }
    });
}

// ---------- Графіки на сторінці статистики ----------
// Дані приходять з Jinja через data-атрибути елементів .chart-item
function drawChart(chart) {
    const items = chart.querySelectorAll(".chart-item");

    let maxValue = 0;
    items.forEach(function (item) {
        maxValue = Math.max(maxValue, Number(item.dataset.value));
    });

    const bars = document.createElement("div");
    bars.className = "bars";

    items.forEach(function (item) {
        const value = Number(item.dataset.value);
        let percent = 0;
        if (maxValue > 0) {
            percent = value / maxValue * 100;
        }

        const column = document.createElement("div");
        column.className = "bar-col";

        const area = document.createElement("div");
        area.className = "bar-area";

        const bar = document.createElement("div");
        bar.className = "bar";
        bar.style.height = percent + "%";

        const valueLabel = document.createElement("div");
        valueLabel.className = "bar-value";
        valueLabel.textContent = value;
        valueLabel.style.bottom = percent + "%";

        const label = document.createElement("div");
        label.className = "bar-label";
        label.textContent = item.dataset.label;

        area.appendChild(bar);
        area.appendChild(valueLabel);
        column.appendChild(area);
        column.appendChild(label);
        bars.appendChild(column);
    });

    chart.appendChild(bars);
}

document.querySelectorAll(".chart").forEach(drawChart);

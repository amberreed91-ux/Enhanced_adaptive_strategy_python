const state = {
  payload: null,
  query: "",
  category: "All",
  modalItem: null,
};

const dom = {
  stats: document.querySelector("#stats"),
  search: document.querySelector("#search"),
  chips: document.querySelector("#track-filters"),
  featuredGrid: document.querySelector("#featured-grid"),
  resultCount: document.querySelector("#result-count"),
  grid: document.querySelector("#project-grid"),
  modal: document.querySelector("#project-modal"),
  modalCategory: document.querySelector("#modal-category"),
  modalTitle: document.querySelector("#modal-title"),
  modalSummary: document.querySelector("#modal-summary"),
  modalClientValue: document.querySelector("#modal-client-value"),
  modalPreview: document.querySelector("#modal-preview"),
  modalCompletion: document.querySelector("#modal-completion"),
  modalOutcomes: document.querySelector("#modal-outcomes"),
  modalProof: document.querySelector("#modal-proof"),
  modalMetrics: document.querySelector("#modal-metrics"),
  modalCommand: document.querySelector("#modal-command"),
  modalOutput: document.querySelector("#modal-output"),
  modalLive: document.querySelector("#modal-live"),
  modalRepo: document.querySelector("#modal-repo"),
  modalDocs: document.querySelector("#modal-docs"),
  modalVideo: document.querySelector("#modal-video"),
  modalCode: document.querySelector("#modal-code"),
  modalReadme: document.querySelector("#modal-readme"),
  closeModal: document.querySelector("#close-modal"),
  copyCommand: document.querySelector("#copy-command"),
  copyRunAll: document.querySelector("#copy-run-all"),
};

async function loadPayload() {
  const res = await fetch("./assets/projects.json", { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to load project data: ${res.status}`);
  }
  return res.json();
}

function hasLink(url) {
  return typeof url === "string" && url.trim().length > 0;
}

function safeList(items) {
  return Array.isArray(items) ? items.filter((v) => typeof v === "string" && v.trim()) : [];
}

function renderList(target, items, fallback) {
  const values = safeList(items);
  if (!values.length) {
    target.innerHTML = `<li>${fallback}</li>`;
    return;
  }
  target.innerHTML = values.map((value) => `<li>${value}</li>`).join("");
}

function linkButtons(project, includeDetails = true) {
  const links = project.links || {};
  const out = [];

  if (hasLink(links.live)) {
    out.push(`<a href="${links.live}" target="_blank" rel="noreferrer">Live</a>`);
  }
  if (hasLink(links.repo)) {
    out.push(`<a href="${links.repo}" target="_blank" rel="noreferrer">GitHub</a>`);
  }
  if (hasLink(links.docs)) {
    out.push(`<a href="${links.docs}" target="_blank" rel="noreferrer">Docs</a>`);
  }
  if (hasLink(links.video)) {
    out.push(`<a href="${links.video}" target="_blank" rel="noreferrer">Video</a>`);
  }

  out.push(`<a href="${project.code_path}" target="_blank" rel="noreferrer">Code</a>`);
  out.push(`<a href="${project.readme_path}" target="_blank" rel="noreferrer">README</a>`);

  if (includeDetails) {
    out.push(`<button type="button" data-open="${project.slug}">Details</button>`);
  }
  return out.join("");
}

function filteredProjects() {
  if (!state.payload) return [];
  const q = state.query.trim().toLowerCase();

  return state.payload.projects.filter((project) => {
    const inCategory = state.category === "All" || project.category === state.category;
    if (!inCategory) return false;
    if (!q) return true;

    const haystack = [
      project.title,
      project.summary,
      project.category,
      project.completion,
      project.client_value,
      ...project.skills,
      ...safeList(project.impact_metrics),
      ...safeList(project.outcomes),
      ...safeList(project.proof_points),
      project.slug,
    ]
      .join(" ")
      .toLowerCase();

    return haystack.includes(q);
  });
}

function renderStats(payload) {
  const statCards = [
    ["Projects", payload.project_count],
    ["Featured", payload.featured_count || 0],
    ["Unique Skills", payload.skills.length],
  ];

  dom.stats.innerHTML = statCards
    .map(
      ([label, value]) => `
      <article class="stat">
        <p>${label}</p>
        <strong>${value}</strong>
      </article>
    `,
    )
    .join("");
}

function renderChips(payload) {
  const categories = ["All", ...payload.categories];
  dom.chips.innerHTML = categories
    .map(
      (category) => `
      <button
        class="chip ${state.category === category ? "active" : ""}"
        data-category="${category}"
      >${category}</button>
    `,
    )
    .join("");

  dom.chips.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      state.category = chip.dataset.category;
      renderChips(payload);
      renderGrid();
    });
  });
}

function featuredTemplate(project, index) {
  const metrics = safeList(project.impact_metrics).slice(0, 2);
  return `
    <article class="featured-card" style="animation-delay:${index * 40}ms">
      <div class="card-head">
        <h3>${project.title}</h3>
        <span class="tag">${project.completion || "In Progress"}</span>
      </div>
      <p>${project.client_value || project.summary}</p>
      <div class="skill-list">
        ${(metrics.length ? metrics : [project.category]).map((item) => `<span class="skill">${item}</span>`).join("")}
      </div>
      <div class="actions">${linkButtons(project, true)}</div>
    </article>
  `;
}

function cardTemplate(project, index) {
  const skills = project.skills.slice(0, 4);
  return `
    <article class="card" style="animation-delay:${index * 28}ms">
      <div class="card-head">
        <h3>${project.title}</h3>
        <span class="tag">${project.category}</span>
      </div>
      <p>${project.summary}</p>
      <p class="completion">${project.completion || "In Progress"}</p>
      <div class="skill-list">
        ${skills.map((skill) => `<span class="skill">${skill}</span>`).join("")}
      </div>
      <div class="actions">${linkButtons(project, true)}</div>
    </article>
  `;
}

function bindDetailButtons(container) {
  container.querySelectorAll("button[data-open]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const slug = btn.dataset.open;
      const project = state.payload.projects.find((item) => item.slug === slug);
      openModal(project);
    });
  });
}

function renderFeatured(payload) {
  const featured = Array.isArray(payload.featured_projects) ? payload.featured_projects : [];
  if (!featured.length) {
    dom.featuredGrid.innerHTML = "<article class='card'><h3>No featured projects yet</h3><p>Add `featured: true` in project_meta.json.</p></article>";
    return;
  }
  dom.featuredGrid.innerHTML = featured.map(featuredTemplate).join("");
  bindDetailButtons(dom.featuredGrid);
}

function renderGrid() {
  const items = filteredProjects();
  dom.resultCount.textContent = `${items.length} of ${state.payload.project_count} projects`;

  if (!items.length) {
    dom.grid.innerHTML = `<article class="card"><h3>No matches</h3><p>Try another search term or category.</p></article>`;
    return;
  }

  dom.grid.innerHTML = items.map(cardTemplate).join("");
  bindDetailButtons(dom.grid);
}

function setOptionalLink(element, url) {
  if (!hasLink(url)) {
    element.style.display = "none";
    element.removeAttribute("href");
    return;
  }
  element.style.display = "inline-flex";
  element.href = url;
}

function openModal(project) {
  if (!project) return;
  state.modalItem = project;

  dom.modalCategory.textContent = project.category;
  dom.modalTitle.textContent = project.title;
  dom.modalSummary.textContent = project.summary;
  dom.modalClientValue.textContent = project.client_value || "";
  const hasVisual = hasLink((project.links || {}).video);
  if (hasVisual) {
    dom.modalPreview.style.display = "block";
    dom.modalPreview.src = `./assets/project_media/${project.slug}/preview.png`;
  } else {
    dom.modalPreview.style.display = "none";
    dom.modalPreview.removeAttribute("src");
  }
  dom.modalCompletion.textContent = project.completion || "In Progress";

  renderList(dom.modalOutcomes, project.outcomes, "Add project outcomes in project_meta.json.");
  renderList(dom.modalProof, project.proof_points, "Add proof points in project_meta.json.");
  renderList(dom.modalMetrics, project.impact_metrics, "Add measurable metrics in project_meta.json.");

  dom.modalCommand.textContent = project.run_command;
  dom.modalOutput.textContent = JSON.stringify(project.demo_output, null, 2);

  const links = project.links || {};
  setOptionalLink(dom.modalLive, links.live);
  setOptionalLink(dom.modalRepo, links.repo);
  setOptionalLink(dom.modalDocs, links.docs);
  setOptionalLink(dom.modalVideo, links.video);

  dom.modalCode.href = project.code_path;
  dom.modalReadme.href = project.readme_path;

  dom.modal.showModal();
}

function closeModal() {
  state.modalItem = null;
  dom.modal.close();
}

async function copyText(text, button) {
  const prior = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
  } catch {
    button.textContent = "Copy failed";
  } finally {
    setTimeout(() => {
      button.textContent = prior;
    }, 1200);
  }
}

function bindEvents() {
  dom.search.addEventListener("input", (event) => {
    state.query = event.target.value;
    renderGrid();
  });

  dom.closeModal.addEventListener("click", closeModal);
  dom.modal.addEventListener("click", (event) => {
    const bounds = dom.modal.querySelector(".modal-card").getBoundingClientRect();
    const inside =
      event.clientX >= bounds.left &&
      event.clientX <= bounds.right &&
      event.clientY >= bounds.top &&
      event.clientY <= bounds.bottom;
    if (!inside) closeModal();
  });

  dom.copyCommand.addEventListener("click", () => {
    if (!state.modalItem) return;
    copyText(state.modalItem.run_command, dom.copyCommand);
  });

  dom.copyRunAll.addEventListener("click", () => {
    copyText("python3 run_all_smoke.py && python3 tests/test_portfolio_smoke.py", dom.copyRunAll);
  });
}

async function init() {
  try {
    const payload = await loadPayload();
    state.payload = payload;
    renderStats(payload);
    renderChips(payload);
    renderFeatured(payload);
    renderGrid();
    bindEvents();
  } catch (error) {
    dom.grid.innerHTML = `<article class="card"><h3>Data load failed</h3><p>${error.message}</p></article>`;
  }
}

init();

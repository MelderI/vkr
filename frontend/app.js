const form = document.querySelector("#scheduleForm");
const statusBox = document.querySelector("#status");
const result = document.querySelector("#result");
const scheduleBody = document.querySelector("#scheduleBody");
const issuesList = document.querySelector("#issuesList");
const sampleSelect = document.querySelector("#sampleFile");
const downloadButton = document.querySelector("#downloadCsv");

let currentLessons = [];

loadSamples();

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showStatus("Формируем расписание...");
  result.classList.add("hidden");

  const formData = new FormData(form);

  try {
    const response = await fetch("/api/schedule", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Не удалось сформировать расписание");
    }
    renderResult(data);
    hideStatus();
  } catch (error) {
    showStatus(error.message, true);
  }
});

downloadButton.addEventListener("click", () => {
  const csv = toCsv(currentLessons);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "schedule.csv";
  link.click();
  URL.revokeObjectURL(url);
});

async function loadSamples() {
  const response = await fetch("/api/samples");
  const data = await response.json();
  for (const file of data.files) {
    const option = document.createElement("option");
    option.value = file;
    option.textContent = file;
    sampleSelect.append(option);
  }
}

function renderResult(data) {
  currentLessons = data.lessons;
  document.querySelector("#requestCount").textContent = data.request_count;
  document.querySelector("#lessonCount").textContent = data.lesson_count;
  document.querySelector("#issueCount").textContent = data.issues.filter(
    (issue) => issue.severity === "error",
  ).length;
  document.querySelector("#windowCount").textContent = Math.round(
    data.metrics.teacher_windows || 0,
  );
  document.querySelector("#solverInfo").textContent =
    `Решатель: ${data.solver}. Штраф: ${data.objective}. Источник: ${data.source}.`;

  scheduleBody.innerHTML = "";
  for (const lesson of data.lessons) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(lesson.teacher)}</td>
      <td>${escapeHtml(lesson.day)}</td>
      <td>${lesson.pair}</td>
      <td>${escapeHtml(lesson.subject)}</td>
      <td>${escapeHtml(lesson.activity_type)}</td>
      <td>${escapeHtml(lesson.groups)}</td>
      <td>${escapeHtml(lesson.room)}</td>
    `;
    scheduleBody.append(row);
  }

  issuesList.innerHTML = "";
  if (data.issues.length === 0) {
    issuesList.innerHTML = '<div class="issue">Конфликтов не найдено</div>';
  } else {
    for (const issue of data.issues) {
      const item = document.createElement("div");
      item.className = `issue ${issue.severity === "error" ? "error" : ""}`;
      item.textContent = `${issue.code}: ${issue.message}`;
      issuesList.append(item);
    }
  }

  result.classList.remove("hidden");
}

function showStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
  statusBox.classList.remove("hidden");
}

function hideStatus() {
  statusBox.classList.add("hidden");
}

function toCsv(rows) {
  const headers = ["teacher", "day", "pair", "subject", "activity_type", "groups", "room"];
  const lines = [headers.join(",")];
  for (const row of rows) {
    lines.push(headers.map((header) => csvCell(row[header])).join(","));
  }
  return `\ufeff${lines.join("\n")}`;
}

function csvCell(value) {
  const text = String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

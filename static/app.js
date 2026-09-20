(function () {
  "use strict";

  var fileInput = document.getElementById("file-input");
  var dropzone = document.getElementById("dropzone");
  var fileChip = document.getElementById("file-chip");
  var fileName = document.getElementById("file-name");
  var resetFile = document.getElementById("reset-file");
  var parseBtn = document.getElementById("parse-btn");
  var errorBox = document.getElementById("error");

  var teamPanel = document.getElementById("team-panel");
  var teamCount = document.getElementById("team-count");
  var teamGrid = document.getElementById("team-grid");

  var reportPanel = document.getElementById("report-panel");
  var reportTeam = document.getElementById("report-team");
  var reportFrame = document.getElementById("report-frame");
  var openTab = document.getElementById("open-tab");
  var downloadBtn = document.getElementById("download-btn");

  var token = null;
  var currentTeam = null;
  var currentHtml = "";
  var currentFilename = "report.html";

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = !message;
  }

  function setBusy(button, busy, label) {
    if (busy) {
      button.dataset.label = button.textContent;
      button.disabled = true;
      button.innerHTML = '<span class="spinner"></span>' + label;
    } else {
      button.disabled = false;
      button.textContent = button.dataset.label || label;
    }
  }

  function selectFile(file) {
    if (!file) return;
    if (file.type && file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      showError("File harus berupa PDF.");
      return;
    }
    showError("");
    fileName.textContent = file.name;
    fileChip.hidden = false;
    teamPanel.hidden = true;
    reportPanel.hidden = true;
  }

  fileInput.addEventListener("change", function () {
    selectFile(fileInput.files && fileInput.files[0]);
  });

  dropzone.addEventListener("click", function () {
    fileInput.click();
  });
  dropzone.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  ["dragenter", "dragover"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });
  dropzone.addEventListener("drop", function (e) {
    var files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) selectFile(files[0]);
  });

  resetFile.addEventListener("click", function () {
    fileInput.value = "";
    fileChip.hidden = true;
    teamPanel.hidden = true;
    reportPanel.hidden = true;
    showError("");
  });

  parseBtn.addEventListener("click", function () {
    var file = fileInput.files && fileInput.files[0];
    if (!file) {
      showError("Pilih file PDF terlebih dahulu.");
      fileInput.click();
      return;
    }

    var form = new FormData();
    form.append("file", file);

    setBusy(parseBtn, true, "Memproses&hellip;");
    showError("");

    fetch("/parse", { method: "POST", body: form })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (result) {
        setBusy(parseBtn, false, "Proses PDF");
        if (!result.ok) {
          showError(result.data.error || "Terjadi kesalahan.");
          return;
        }
        token = result.data.token;
        renderTeams(result.data.teams);
      })
      .catch(function () {
        setBusy(parseBtn, false, "Proses PDF");
        showError("Tidak dapat terhubung ke server.");
      });
  });

  function renderTeams(teams) {
    teamCount.textContent = teams.length;
    teamGrid.innerHTML = "";
    teams.forEach(function (team) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "team-btn";
      btn.textContent = team;
      btn.addEventListener("click", function () { requestReport(team); });
      teamGrid.appendChild(btn);
    });
    teamPanel.hidden = false;
    teamPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function requestReport(team) {
    currentTeam = team;
    showError("");

    fetch("/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: token, team: team }),
    })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (result) {
        if (!result.ok) {
          showError(result.data.error || "Terjadi kesalahan.");
          return;
        }
        currentHtml = result.data.html;
        currentFilename = (result.data.team || "report") + "_statistik_report.html";
        reportTeam.textContent = result.data.team;
        reportFrame.srcdoc = result.data.html;
        reportPanel.hidden = false;
        reportPanel.scrollIntoView({ behavior: "smooth", block: "start" });
      })
      .catch(function () {
        showError("Tidak dapat terhubung ke server.");
      });
  }

  function download() {
    if (!currentHtml) return;
    var blob = new Blob([currentHtml], { type: "text/html;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = currentFilename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  openTab.addEventListener("click", function () {
    if (!currentHtml) return;
    var blob = new Blob([currentHtml], { type: "text/html;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
  });

  downloadBtn.addEventListener("click", download);
})();

import { $, fetchJson, caseApi, casePage, downloadReportPdf, DISCLAIMER_HTML, type CaseRow } from "./helpers";
import { isPipelineActive, pipelineStatusCellHtml } from "./pipelineProgress";
import { showReportPreview } from "./reportPreview";

type UploadResult = {
  total: number;
  imported: number;
  skipped: number;
  errors: number;
  results: { filename?: string; status: string; study_uid?: string; error?: string }[];
};

type CaseImportResult = {
  schema_version: string;
  imported: string[];
  skipped: string[];
  errors: { study_uid?: string; error: string }[];
  index_rebuilt_cases?: number;
};

type FilterTab = "all" | "in_review" | "computing" | "approved" | "error";
type StatusFilter = "any" | "in_review" | "approved" | "signed";
type PipelineFilter = "any" | "queued" | "computing" | "done" | "error" | "ingesting";
type RecentFilter = "any" | "1d" | "7d" | "30d";

const FILTER_TABS: { key: FilterTab; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "in_review", label: "待审阅" },
  { key: "computing", label: "推理中" },
  { key: "approved", label: "已完成" },
  { key: "error", label: "异常" },
];

function _statusBadge(status?: string, pipelineStatus?: string): string {
  const map: Record<string, [string, string]> = {
    queued:     ["badge-queued",     "排队中"],
    running:    ["badge-computing",  "推理中"],
    computing:  ["badge-computing",  "推理中"],
    done:       ["badge-done",       "推理完成"],
    error:      ["badge-error",      "推理失败"],
    ingesting:  ["badge-computing",  "导入中"],
    in_review:  ["badge-review",     "待审阅"],
    approved:   ["badge-approved",   "已完成"],
    signed:     ["badge-approved",   "已签发"],
  };
  const statusKey = status || "";
  if (statusKey === "in_review" || statusKey === "approved" || statusKey === "signed") {
    const [cls, label] = map[statusKey] || ["badge-default", statusKey || "-"];
    return `<span class="cl-badge ${cls}">${label}</span>`;
  }
  const s = pipelineStatus || status || "";
  const [cls, label] = map[s] || ["badge-default", s || "-"];
  return `<span class="cl-badge ${cls}">${label}</span>`;
}

function _relativeTime(iso?: string): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const diff = Date.now() - d.getTime();
  if (diff < 0) return _fmtDate(d);
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return "刚刚";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day} 天前`;
  return _fmtDate(d);
}

function _fmtDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${day} ${hh}:${mm}`;
}

function _fmtDateFull(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return _fmtDate(d);
}

function _caseTimeMs(c: CaseRow): number {
  const iso = c.updated_at || c.created_at;
  if (!iso) return 0;
  const d = new Date(iso);
  const t = d.getTime();
  return isNaN(t) ? 0 : t;
}

function _matchAdvFilters(
  c: CaseRow,
  statusFilter: StatusFilter,
  pipelineFilter: PipelineFilter,
  onlyWithTasks: boolean,
  recent: RecentFilter,
  textQuery: string
): boolean {
  if (statusFilter !== "any") {
    if ((c.status || "") !== statusFilter) return false;
  }
  if (pipelineFilter !== "any") {
    if ((c.pipeline_status || "") !== pipelineFilter) return false;
  }
  if (onlyWithTasks) {
    if (!(c.review_task_count && c.review_task_count > 0)) return false;
  }
  if (recent !== "any") {
    const t = _caseTimeMs(c);
    if (!t) return false;
    const days = recent === "1d" ? 1 : recent === "7d" ? 7 : 30;
    const cutoff = Date.now() - days * 24 * 3600 * 1000;
    if (t < cutoff) return false;
  }
  if (textQuery) {
    const q = textQuery.toLowerCase();
    const hay = [
      c.patient_display_id || "",
      c.study_uid || "",
      c.status || "",
      c.pipeline_status || "",
    ]
      .join(" ")
      .toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}

function _matchFilter(c: CaseRow, filter: FilterTab): boolean {
  if (filter === "all") return true;
  const s = c.status || "";
  const ps = c.pipeline_status || "";
  if (filter === "in_review") return s === "in_review";
  if (filter === "approved") return s === "approved" || s === "signed";
  if (filter === "computing") {
    return ps === "computing" || ps === "queued" || ps === "running" || s === "computing" || s === "ingesting";
  }
  if (filter === "error") return ps === "error";
  return true;
}

function _shortUid(uid: string): string {
  if (uid.length <= 20) return uid;
  return uid.slice(0, 8) + "…" + uid.slice(-8);
}

function _taskCountBadge(count?: number): string {
  if (!count) return "";
  return `<span class="cl-task-count">${count}</span>`;
}

function _buildRow(c: CaseRow, idx: number, selected: boolean): string {
  const pid = c.patient_display_id || "-";
  const shortId = _shortUid(c.study_uid);
  const badge = _statusBadge(c.status, c.pipeline_status);
  const pipeProg = isPipelineActive(c) ? pipelineStatusCellHtml(c) : "";
  const time = _relativeTime(c.updated_at || c.created_at);
  const timeFull = _fmtDateFull(c.updated_at || c.created_at);
  const tasks = _taskCountBadge(c.review_task_count);
  const checked = selected ? "checked" : "";
  return `<tr data-uid="${encodeURIComponent(c.study_uid)}" class="${selected ? "cl-selected" : ""}">
    <td class="cl-col-check"><input type="checkbox" class="cl-row-check" ${checked} /></td>
    <td class="cl-col-idx">${idx}</td>
    <td class="cl-col-pid">${pid}</td>
    <td class="cl-col-uid" title="${c.study_uid}">${shortId}</td>
    <td class="cl-col-status"><div class="cl-status-cell">${badge}${pipeProg}</div></td>
    <td class="cl-col-tasks">${tasks}</td>
    <td class="cl-col-time" title="${timeFull}">${time}</td>
    <td class="cl-col-actions">
      <button type="button" class="btn-cl-report" data-action="report" title="预览报告">报告</button>
      <button type="button" class="btn-cl-pdf" data-action="pdf" title="导出 PDF 报告">PDF</button>
      <button type="button" class="btn-delete" data-action="delete" title="删除病例">删除</button>
    </td>
  </tr>`;
}

export async function renderList(nav: (path: string) => void): Promise<void> {
  const data = await fetchJson<{ cases: CaseRow[]; total: number }>("/api/cases");
  const allCases = data.cases;

  let currentFilter: FilterTab = "all";
  let searchQuery = "";
  const selectedUids = new Set<string>();
  let advStatus: StatusFilter = "any";
  let advPipeline: PipelineFilter = "any";
  let onlyTasks = false;
  let recent: RecentFilter = "any";
  let advText = "";

  function filteredCases(): CaseRow[] {
    let list = allCases.filter((c) => _matchFilter(c, currentFilter));
    list = list.filter((c) => _matchAdvFilters(c, advStatus, advPipeline, onlyTasks, recent, advText));
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (c) =>
          (c.patient_display_id || "").toLowerCase().includes(q) ||
          c.study_uid.toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => _caseTimeMs(b) - _caseTimeMs(a));
    return list;
  }

  function filterCounts(): Record<FilterTab, number> {
    const counts: Record<FilterTab, number> = { all: 0, in_review: 0, computing: 0, approved: 0, error: 0 };
    for (const c of allCases) {
      counts.all++;
      if (_matchFilter(c, "in_review")) counts.in_review++;
      if (_matchFilter(c, "computing")) counts.computing++;
      if (_matchFilter(c, "approved")) counts.approved++;
      if (_matchFilter(c, "error")) counts.error++;
    }
    return counts;
  }

  function _updateSelectionUI() {
    const count = selectedUids.size;
    const bar = document.querySelector(".cl-selection-bar") as HTMLElement;
    if (!bar) return;
    if (count > 0) {
      bar.hidden = false;
      const txt = bar.querySelector(".cl-sel-text");
      if (txt) txt.textContent = `已选中 ${count} 例`;
    } else {
      bar.hidden = true;
    }
    const headerCheck = document.querySelector(".cl-header-check") as HTMLInputElement;
    if (headerCheck) {
      const visible = filteredCases();
      const allChecked = visible.length > 0 && visible.every((c) => selectedUids.has(c.study_uid));
      const someChecked = visible.some((c) => selectedUids.has(c.study_uid));
      headerCheck.checked = allChecked;
      headerCheck.indeterminate = someChecked && !allChecked;
    }
  }

  let listPollTimer: ReturnType<typeof setInterval> | null = null;

  function stopListPoll() {
    if (listPollTimer) {
      clearInterval(listPollTimer);
      listPollTimer = null;
    }
  }

  async function refreshCasesFromApi() {
    const data = await fetchJson<{ cases: CaseRow[] }>("/api/cases");
    allCases.splice(0, allCases.length, ...data.cases);
  }

  function syncListPoll() {
    if (!allCases.some(isPipelineActive)) {
      stopListPoll();
      return;
    }
    if (listPollTimer) return;
    listPollTimer = setInterval(async () => {
      try {
        await refreshCasesFromApi();
        renderTable();
      } catch {
        /* ignore transient errors */
      }
    }, 2000);
  }

  function renderTable() {
    const cases = filteredCases();
    const tbody = document.querySelector(".cl-table tbody") as HTMLElement;
    if (!tbody) return;
    if (cases.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="cl-empty">暂无匹配的检查</td></tr>`;
    } else {
      tbody.innerHTML = cases.map((c, i) => _buildRow(c, i + 1, selectedUids.has(c.study_uid))).join("");
    }
    const countEl = document.querySelector(".cl-count");
    if (countEl) countEl.textContent = `${cases.length} / ${allCases.length} 例`;
    _wireRowEvents();
    _updateSelectionUI();
    syncListPoll();
  }

  function _wireRowEvents() {
    document.querySelectorAll<HTMLElement>(".cl-table tbody tr[data-uid]").forEach((tr) => {
      const checkbox = tr.querySelector(".cl-row-check") as HTMLInputElement;

      checkbox?.addEventListener("click", (e) => {
        e.stopPropagation();
        const uid = decodeURIComponent(tr.dataset.uid || "");
        if (!uid) return;
        if (checkbox.checked) {
          selectedUids.add(uid);
        } else {
          selectedUids.delete(uid);
        }
        tr.classList.toggle("cl-selected", checkbox.checked);
        _updateSelectionUI();
      });

      tr.addEventListener("click", (e) => {
        const target = e.target as HTMLElement;
        if (target.tagName === "INPUT" || target.tagName === "BUTTON" || target.closest(".cl-col-check") || target.closest(".cl-col-actions")) return;
        const uid = tr.dataset.uid;
        if (uid) nav(casePage(decodeURIComponent(uid)));
      });

      tr.querySelector(".btn-cl-report")?.addEventListener("click", (e) => {
        e.stopPropagation();
        const uid = decodeURIComponent(tr.dataset.uid || "");
        if (uid) void showReportPreview(uid);
      });

      tr.querySelector(".btn-cl-pdf")?.addEventListener("click", (e) => {
        e.stopPropagation();
        const uid = decodeURIComponent(tr.dataset.uid || "");
        if (uid) downloadReportPdf(uid);
      });

      tr.querySelector(".btn-delete")?.addEventListener("click", async (e) => {
        e.stopPropagation();
        const uid = decodeURIComponent(tr.dataset.uid || "");
        if (!uid) return;
        const label = tr.querySelector(".cl-col-pid")?.textContent || uid;
        if (!confirm(`确定删除该病例？\n\n${label}\n\n将删除 case_bundle 目录及未执行的队列任务，不可恢复。`)) return;
        try {
          await fetchJson(caseApi(uid, "/delete"), { method: "POST" });
          selectedUids.delete(uid);
          await renderList(nav);
        } catch (err) {
          alert(String(err));
        }
      });
    });
  }

  const counts = filterCounts();
  const filterTabsHtml = FILTER_TABS.map(
    (t) =>
      `<button type="button" class="cl-filter-tab${t.key === "all" ? " active" : ""}" data-filter="${t.key}">${t.label}<span class="cl-filter-count">${counts[t.key]}</span></button>`
  ).join("");

  $("#app").innerHTML = `
    ${DISCLAIMER_HTML}
    <div class="cl-page">
      <header class="cl-header">
        <div class="cl-header-left">
          <h1 class="cl-title">BoneMet Workstation</h1>
          <span class="cl-count">${allCases.length} / ${allCases.length} 例</span>
        </div>
        <div class="cl-header-right">
          <div class="cl-search-box">
            <input type="text" id="clSearch" placeholder="搜索患者ID / Study UID …" />
          </div>
          <button type="button" class="cl-export-btn" id="btnExportAll" title="导出所有病例">导出全部</button>
        </div>
      </header>

      <section class="cl-ingest-panel">
        <details class="cl-ingest-details">
          <summary class="cl-ingest-summary">导入新检查</summary>
          <div class="cl-ingest-body">
            <div class="ingest-tabs">
              <button type="button" class="ingest-tab active" data-tab="upload">本地文件上传</button>
              <button type="button" class="ingest-tab" data-tab="path">服务器路径</button>
              <button type="button" class="ingest-tab" data-tab="casezip">导入导出包(zip)</button>
            </div>
            <div class="ingest-tab-body" id="tabUpload">
              <div class="upload-zone" id="uploadZone">
                <p>点击选择或拖拽 DICOM 文件到此处</p>
                <p class="hint">支持批量导入，仅接受双帧（前位+后位）全身骨显像 DICOM</p>
                <input type="file" id="fileInput" multiple accept=".dcm,.DCM,.dicom" hidden />
              </div>
              <div id="uploadProgress" class="upload-progress" hidden></div>
              <div id="uploadResults" class="upload-results" hidden></div>
            </div>
            <div class="ingest-tab-body" id="tabPath" hidden>
              <label>WholeBody DICOM（单文件含正反帧，或所在目录）
                <input type="text" id="dicomDir" placeholder="/path/to/wholebody.dcm" style="width:min(520px,95%)"/></label>
              <p class="hint" style="margin:0.25rem 0 0.5rem 1rem;font-size:0.8rem;color:#666">须为服务器上的绝对路径。</p>
              <button id="btnIngestDicom" class="primary">导入并入队推理</button>
              <span id="ingestMsg" class="status"></span>
            </div>
            <div class="ingest-tab-body" id="tabCaseZip" hidden>
              <div class="upload-zone" id="caseZipZone">
                <p>点击选择或拖拽「病例导出包 .zip」到此处</p>
                <p class="hint">支持从其它 Workstation 导出的 zip 导入；如 Study UID 已存在将覆盖（可关闭）</p>
                <input type="file" id="caseZipInput" accept=".zip" hidden />
              </div>
              <label style="display:flex;gap:0.5rem;align-items:center;margin-top:0.5rem;">
                <input type="checkbox" id="caseZipForce" checked />
                覆盖同 Study UID（force）
              </label>
              <div id="caseZipProgress" class="upload-progress" hidden></div>
              <div id="caseZipResults" class="upload-results" hidden></div>
            </div>
          </div>
        </details>
      </section>

      <div class="cl-selection-bar" hidden>
        <span class="cl-sel-text">已选中 0 例</span>
        <button type="button" class="cl-sel-export" id="btnExportSel">导出选中</button>
        <button type="button" class="cl-sel-clear" id="btnClearSel">取消选择</button>
      </div>

      <div class="cl-filter-bar">${filterTabsHtml}</div>
      <div class="cl-adv-filter">
        <label class="cl-adv-item cl-adv-text">关键词
          <input type="text" id="advText" placeholder="输入字符筛选…" />
        </label>
        <label class="cl-adv-item">状态
          <select id="advStatus">
            <option value="any">不限</option>
            <option value="in_review">待审阅</option>
            <option value="approved">已完成</option>
            <option value="signed">已签发</option>
          </select>
        </label>
        <label class="cl-adv-item">推理
          <select id="advPipeline">
            <option value="any">不限</option>
            <option value="queued">排队中</option>
            <option value="computing">推理中</option>
            <option value="done">推理完成</option>
            <option value="error">推理失败</option>
            <option value="ingesting">导入中</option>
          </select>
        </label>
        <label class="cl-adv-item">最近更新
          <select id="advRecent">
            <option value="any">不限</option>
            <option value="1d">1 天内</option>
            <option value="7d">7 天内</option>
            <option value="30d">30 天内</option>
          </select>
        </label>
        <label class="cl-adv-item cl-adv-check">
          <input type="checkbox" id="advOnlyTasks" />
          仅显示有待审
        </label>
        <button type="button" class="cl-adv-clear" id="btnClearFilters">清除筛选</button>
      </div>

      <div class="cl-table-wrap">
        <table class="cl-table">
          <thead>
            <tr>
              <th class="cl-col-check"><input type="checkbox" class="cl-header-check" title="全选/取消全选" /></th>
              <th class="cl-col-idx">#</th>
              <th class="cl-col-pid">患者</th>
              <th class="cl-col-uid">Study UID</th>
              <th class="cl-col-status">状态</th>
              <th class="cl-col-tasks">待审</th>
              <th class="cl-col-time">更新时间</th>
              <th class="cl-col-actions">操作</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>`;

  renderTable();

  // ── Header checkbox (select all visible) ──
  const headerCheck = document.querySelector(".cl-header-check") as HTMLInputElement;
  headerCheck?.addEventListener("change", () => {
    const visible = filteredCases();
    if (headerCheck.checked) {
      visible.forEach((c) => selectedUids.add(c.study_uid));
    } else {
      visible.forEach((c) => selectedUids.delete(c.study_uid));
    }
    renderTable();
  });

  // ── Filter tabs ──
  document.querySelectorAll<HTMLButtonElement>(".cl-filter-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".cl-filter-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = (btn.dataset.filter || "all") as FilterTab;
      renderTable();
    });
  });

  // ── Search ──
  const searchInput = document.getElementById("clSearch") as HTMLInputElement;
  searchInput?.addEventListener("input", () => {
    searchQuery = searchInput.value.trim();
    renderTable();
  });

  // ── Advanced filters ──
  const inpText = document.getElementById("advText") as HTMLInputElement;
  const selStatus = document.getElementById("advStatus") as HTMLSelectElement;
  const selPipeline = document.getElementById("advPipeline") as HTMLSelectElement;
  const selRecent = document.getElementById("advRecent") as HTMLSelectElement;
  const chkTasks = document.getElementById("advOnlyTasks") as HTMLInputElement;
  const btnClearFilters = document.getElementById("btnClearFilters") as HTMLButtonElement;

  inpText?.addEventListener("input", () => {
    advText = inpText.value.trim();
    renderTable();
  });
  selStatus?.addEventListener("change", () => {
    advStatus = (selStatus.value || "any") as StatusFilter;
    renderTable();
  });
  selPipeline?.addEventListener("change", () => {
    advPipeline = (selPipeline.value || "any") as PipelineFilter;
    renderTable();
  });
  selRecent?.addEventListener("change", () => {
    recent = (selRecent.value || "any") as RecentFilter;
    renderTable();
  });
  chkTasks?.addEventListener("change", () => {
    onlyTasks = Boolean(chkTasks.checked);
    renderTable();
  });
  btnClearFilters?.addEventListener("click", () => {
    advStatus = "any";
    advPipeline = "any";
    recent = "any";
    onlyTasks = false;
    advText = "";
    if (inpText) inpText.value = "";
    if (selStatus) selStatus.value = "any";
    if (selPipeline) selPipeline.value = "any";
    if (selRecent) selRecent.value = "any";
    if (chkTasks) chkTasks.checked = false;
    renderTable();
  });

  // ── Selection bar buttons ──
  document.getElementById("btnClearSel")?.addEventListener("click", () => {
    selectedUids.clear();
    renderTable();
  });

  document.getElementById("btnExportSel")?.addEventListener("click", () => {
    if (selectedUids.size === 0) return;
    _triggerExport([...selectedUids]);
  });

  document.getElementById("btnExportAll")?.addEventListener("click", () => {
    _triggerExport([]);
  });

  async function _triggerExport(uids: string[]) {
    const label = uids.length > 0 ? `选中的 ${uids.length} 例` : `全部 ${allCases.length} 例`;
    const btn = (uids.length > 0
      ? document.getElementById("btnExportSel")
      : document.getElementById("btnExportAll")) as HTMLButtonElement;
    const origText = btn?.textContent || "导出";
    if (btn) { btn.disabled = true; btn.textContent = "导出中…"; }

    try {
      const resp = await fetch("/api/cases/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ study_uids: uids }),
      });
      if (!resp.ok) {
        const text = await resp.text();
        alert(`导出失败: ${text}`);
        return;
      }
      const blob = await resp.blob();
      const disposition = resp.headers.get("content-disposition") || "";
      const nameMatch = disposition.match(/filename="?([^"]+)"?/);
      const filename = nameMatch?.[1] || "bonemet_export.zip";

      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        URL.revokeObjectURL(a.href);
        a.remove();
      }, 100);
    } catch (e) {
      alert(`导出异常: ${e}`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = origText; }
    }
  }

  // ── Ingest tab switching ──
  document.querySelectorAll<HTMLButtonElement>(".ingest-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".ingest-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      (document.getElementById("tabUpload") as HTMLElement).hidden = tab !== "upload";
      (document.getElementById("tabPath") as HTMLElement).hidden = tab !== "path";
      (document.getElementById("tabCaseZip") as HTMLElement).hidden = tab !== "casezip";
    });
  });

  // ── File upload ──
  const uploadZone = document.getElementById("uploadZone")!;
  const fileInput = document.getElementById("fileInput") as HTMLInputElement;

  uploadZone.addEventListener("click", () => fileInput.click());
  uploadZone.addEventListener("dragover", (e) => { e.preventDefault(); uploadZone.classList.add("dragover"); });
  uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("dragover"));
  uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    if (e.dataTransfer?.files?.length) handleFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files?.length) handleFiles(fileInput.files);
  });

  async function handleFiles(files: FileList) {
    const progressEl = document.getElementById("uploadProgress")!;
    const resultsEl = document.getElementById("uploadResults")!;
    progressEl.hidden = false;
    resultsEl.hidden = true;

    const total = files.length;
    progressEl.innerHTML = `<div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div><p>正在上传 0/${total}…</p>`;
    const fill = progressEl.querySelector(".progress-fill") as HTMLElement;
    const text = progressEl.querySelector("p")!;

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) formData.append("files", files[i]);
    formData.append("run_pipeline", "true");

    text.textContent = `正在上传 ${total} 个文件…`;
    fill.style.width = "30%";

    try {
      const resp = await fetch("/api/ingest/upload", { method: "POST", body: formData });
      fill.style.width = "100%";

      if (!resp.ok) {
        const err = await resp.text();
        text.textContent = `上传失败: ${err}`;
        return;
      }

      const data: UploadResult = await resp.json();
      text.textContent = `完成: ${data.imported} 导入, ${data.skipped} 已存在, ${data.errors} 失败`;

      const rowsHtml = data.results
        .map((r) => {
          const cls = r.status === "ok" ? "ok" : r.status === "skipped" ? "skip" : "err";
          const icon = r.status === "ok" ? "✓" : r.status === "skipped" ? "~" : "✗";
          const info = r.status === "ok" ? r.study_uid || "" : r.error || "";
          return `<div class="upload-row ${cls}"><span class="upload-icon">${icon}</span><span class="upload-name">${r.filename || ""}</span><span class="upload-info">${info}</span></div>`;
        })
        .join("");
      resultsEl.innerHTML = rowsHtml;
      resultsEl.hidden = false;

      if (data.imported > 0) setTimeout(() => renderList(nav), 1500);
    } catch (e) {
      fill.style.width = "100%";
      fill.style.background = "#dc2626";
      text.textContent = `上传异常: ${e}`;
    }
  }

  // ── Import exported cases zip ──
  const caseZipZone = document.getElementById("caseZipZone")!;
  const caseZipInput = document.getElementById("caseZipInput") as HTMLInputElement;
  const caseZipForce = document.getElementById("caseZipForce") as HTMLInputElement;

  caseZipZone.addEventListener("click", () => caseZipInput.click());
  caseZipZone.addEventListener("dragover", (e) => { e.preventDefault(); caseZipZone.classList.add("dragover"); });
  caseZipZone.addEventListener("dragleave", () => caseZipZone.classList.remove("dragover"));
  caseZipZone.addEventListener("drop", (e) => {
    e.preventDefault();
    caseZipZone.classList.remove("dragover");
    const f = e.dataTransfer?.files?.[0];
    if (f) void handleCaseZip(f);
  });
  caseZipInput.addEventListener("change", () => {
    const f = caseZipInput.files?.[0];
    if (f) void handleCaseZip(f);
  });

  async function handleCaseZip(file: File) {
    const progressEl = document.getElementById("caseZipProgress")!;
    const resultsEl = document.getElementById("caseZipResults")!;
    progressEl.hidden = false;
    resultsEl.hidden = true;

    const force = Boolean(caseZipForce?.checked);
    progressEl.innerHTML = `<div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div><p>正在导入…</p>`;
    const fill = progressEl.querySelector(".progress-fill") as HTMLElement;
    const text = progressEl.querySelector("p")!;

    const fd = new FormData();
    fd.append("file", file);

    try {
      fill.style.width = "25%";
      const resp = await fetch(`/api/cases/import?force=${force ? "1" : "0"}`, { method: "POST", body: fd });
      fill.style.width = "100%";

      if (!resp.ok) {
        const err = await resp.text();
        text.textContent = `导入失败: ${err}`;
        return;
      }

      const data: CaseImportResult = await resp.json();
      const imported = data.imported?.length || 0;
      const skipped = data.skipped?.length || 0;
      const errs = data.errors?.length || 0;
      text.textContent = `完成: ${imported} 导入, ${skipped} 跳过, ${errs} 失败`;

      const rows: string[] = [];
      for (const uid of data.imported || []) rows.push(`<div class="upload-row ok"><span class="upload-icon">✓</span><span class="upload-name">${uid}</span><span class="upload-info">已导入</span></div>`);
      for (const uid of data.skipped || []) rows.push(`<div class="upload-row skip"><span class="upload-icon">~</span><span class="upload-name">${uid}</span><span class="upload-info">已存在（跳过）</span></div>`);
      for (const e of data.errors || []) rows.push(`<div class="upload-row err"><span class="upload-icon">✗</span><span class="upload-name">${e.study_uid || "-"}</span><span class="upload-info">${e.error || "error"}</span></div>`);
      resultsEl.innerHTML = rows.join("") || `<div class="upload-row skip"><span class="upload-icon">~</span><span class="upload-name">无变更</span><span class="upload-info"></span></div>`;
      resultsEl.hidden = false;

      if (imported > 0) setTimeout(() => renderList(nav), 800);
    } catch (e) {
      fill.style.width = "100%";
      fill.style.background = "#dc2626";
      text.textContent = `导入异常: ${e}`;
    } finally {
      // allow re-select same file
      caseZipInput.value = "";
    }
  }

  // ── Server path import ──
  document.getElementById("btnIngestDicom")?.addEventListener("click", async () => {
    const dir = (document.getElementById("dicomDir") as HTMLInputElement).value.trim();
    if (!dir) return;
    const msg = document.getElementById("ingestMsg")!;
    msg.textContent = "导入中…";
    try {
      const out = await fetchJson<{ study_uid: string }>("/api/ingest/dicom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dicom_dir: dir, run_pipeline: true }),
      });
      msg.textContent = `已创建 ${out.study_uid}，请确保 worker 运行`;
      setTimeout(() => nav(casePage(out.study_uid)), 800);
    } catch (e) {
      const text = String(e);
      const m = text.match(/409:病例已存在:(.+)/);
      if (m) {
        msg.textContent = "该检查已导入，正在打开…";
        setTimeout(() => nav(casePage(m[1])), 300);
        return;
      }
      msg.textContent = text.includes("path not found") ? `${text} — 请用绝对路径` : text;
    }
  });
}

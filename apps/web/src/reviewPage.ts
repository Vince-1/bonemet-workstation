import { $, fetchJson, caseApi, casePage, DISCLAIMER_COMPACT, type CaseRow, type CaseDetail } from "./helpers";
import { ReviewEditor, type Box, type BonePolygonItem, type EditorOp } from "./reviewEditor";
import { showReportPreview } from "./reportPreview";

let reviewRev = 0;
let reviewFront: Box[] = [];
let reviewBack: Box[] = [];
let editor: ReviewEditor | null = null;
let _onAnalysisUpdate: ((analysis: any) => void) | null = null;
let _signedReviewRev: number | null = null;
let _reviewDirty = false;

type ReportSignState = "none" | "current" | "stale";

const SIGN_UI: Record<
  ReportSignState,
  { badge: string; label: string; desc: string; hint: string }
> = {
  none: {
    badge: "待签发",
    label: "签发报告",
    desc: "根据当前审阅生成 PDF 并归档",
    hint: "尚未生成正式报告",
  },
  current: {
    badge: "已同步",
    label: "报告已签发",
    desc: "与当前审阅一致，无需重复操作",
    hint: "审阅未变更",
  },
  stale: {
    badge: "需更新",
    label: "重新签发报告",
    desc: "审阅已修改，请更新报告后归档",
    hint: "内容已变更",
  },
};

function effectiveSignState(): ReportSignState {
  if (_reviewDirty) return "stale";
  if (_signedReviewRev === null) return "none";
  if (_signedReviewRev !== reviewRev) return "stale";
  return "current";
}

function updateSignButtonUI() {
  const btn = document.getElementById("btnSign");
  if (!btn) return;
  const state = effectiveSignState();
  const ui = SIGN_UI[state];
  btn.classList.remove("bm-dock-sign--none", "bm-dock-sign--current", "bm-dock-sign--stale");
  btn.classList.add(`bm-dock-sign--${state}`);
  const badge = btn.querySelector(".bm-dock-sign-badge");
  const label = btn.querySelector(".bm-dock-label");
  const desc = btn.querySelector(".bm-dock-desc");
  if (badge) badge.textContent = ui.badge;
  if (label) label.textContent = ui.label;
  if (desc) desc.textContent = ui.desc;
  const hintEl = document.getElementById("signDockHint");
  if (hintEl) hintEl.textContent = ui.hint;
}

function setSaveStatus(text: string) {
  const el = document.getElementById("saveStatus");
  if (el) {
    el.textContent = text;
    el.classList.toggle("err", /失败|错误|error/i.test(text));
  }
}

function setBenchHint(text: string) {
  const hint = document.getElementById("bmHint");
  if (hint) hint.textContent = text;
}

function syncOpButtons(op: EditorOp) {
  document.querySelectorAll(".bm-op-btn[data-op]").forEach((b) => {
    b.classList.toggle("active", (b as HTMLElement).dataset.op === op);
  });
}

async function saveReview(uid: string) {
  const neg = reviewFront.length === 0 && reviewBack.length === 0;
  setSaveStatus("保存中…");
  try {
    const out = await fetchJson<{ rev: number; analysis?: { lesions?: any[] } }>(caseApi(uid, "/review"), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rev: reviewRev,
        front: reviewFront,
        back: reviewBack,
        negative_explicit: neg,
      }),
    });
    reviewRev = out.rev;
    _reviewDirty = false;
    if (out.analysis && _onAnalysisUpdate) _onAnalysisUpdate(out.analysis);
    setSaveStatus("已保存");
    updateSignButtonUI();
  } catch (e) {
    setSaveStatus(`保存失败: ${e}`);
  }
}

function markDirty() {
  _reviewDirty = true;
  setSaveStatus("未保存");
  updateSignButtonUI();
}

export function getEditor(): ReviewEditor | null {
  return editor;
}

export function resetEditorState() {
  editor = null;
}

export async function renderCase(uid: string, nav: (path: string) => void): Promise<void> {
  const detail = await fetchJson<CaseDetail>(caseApi(uid));
  const review = detail.data["review/boxes.json"] as {
    rev: number;
    front: Box[];
    back: Box[];
    negative_explicit?: boolean;
  };
  const meta = detail.data["meta.json"] as {
    patient_display_id?: string;
    status?: string;
    pipeline_status?: string;
    rev?: number;
  };
  reviewRev = meta?.rev ?? review?.rev ?? 0;
  const reportSign = detail.data["_report_sign"] as {
    signed_review_rev?: number | null;
    has_report?: boolean;
  } | undefined;
  if (reportSign?.signed_review_rev != null) {
    _signedReviewRev = reportSign.signed_review_rev;
  } else if (reportSign?.has_report || meta?.status === "approved") {
    _signedReviewRev = reviewRev;
  } else {
    _signedReviewRev = null;
  }
  _reviewDirty = false;
  const displaySource = (detail.data["_display_source"] as string) || "review";
  const fromInference =
    Boolean(detail.data["_review_seeded_from_inference"]) ||
    displaySource === "inference" ||
    reviewRev === 0;
  const front = review?.front || [];
  const back = review?.back || [];
  const boxWarnings = (detail.data["_box_warnings"] as string[]) || [];
  const seededFromInference = fromInference;
  reviewFront = JSON.parse(JSON.stringify(front));
  reviewBack = JSON.parse(JSON.stringify(back));

  const displayId = meta?.patient_display_id || uid;
  const boxN = reviewFront.length + reviewBack.length;

  $("#app").innerHTML = `
    ${DISCLAIMER_COMPACT}
    <div id="bm-review-root" class="bm-review-root">
      <div class="bm-topbar">
        <a href="/" class="bm-back">← 列表</a>
        <span class="bm-pid">${displayId}</span>
        <span class="bm-header-meta">${meta?.status || ""}</span>
        <div class="bm-op-group">
          <button type="button" class="bm-op-btn active" data-op="none">浏览</button>
          <button type="button" class="bm-op-btn bm-op-move" data-op="move">移框</button>
          <button type="button" class="bm-op-btn bm-op-add" data-op="add">补框</button>
          <button type="button" class="bm-op-btn bm-op-remove" data-op="remove">删框</button>
          <button type="button" class="bm-op-btn bm-op-save" id="btnSave">保存</button>
        </div>
        <span class="bm-hint" id="bmHint">浏览：悬浮高亮 · 点击选中 · Esc</span>
        <div class="bm-toolbar-end">
          <div class="bm-zoom-group">
            <button type="button" id="bmZoomOut" class="bm-zoom-btn">−</button>
            <button type="button" id="bmZoomLabel" class="bm-zoom-value" title="复位 (3)">100%</button>
            <button type="button" id="bmZoomIn" class="bm-zoom-btn">+</button>
          </div>
          <button type="button" id="bmBtnBoxes" class="bm-toggle-btn active" title="显示/隐藏检测框 (B)">框</button>
          <button type="button" id="bmBtnContour" class="bm-toggle-btn active" title="显示/隐藏病灶轮廓 (C)">轮廓</button>
          <button type="button" id="bmBtnBone" class="bm-toggle-btn active" title="显示/隐藏骨骼分割 (G)">骨骼</button>
          <button type="button" id="bmBtnInvert" class="bm-toggle-btn active">反色</button>
          <button type="button" id="btnPreview" class="bm-toggle-btn">报告</button>
        </div>
        <span class="bm-bench-status" id="saveStatus"></span>
      </div>
      <div class="bm-layout">
        <main class="bm-canvas-area">
          <div class="bm-views">
            <div class="bm-canvas-wrap">
              <canvas id="cvCombined" class="bm-canvas"></canvas>
            </div>
          </div>
        </main>
        <div class="bm-resize-handle" id="bmResizeHandle"></div>
        <aside class="bm-sidebar-right" id="bmSidebar">
          <div class="bm-sidebar-header">
            <div class="bm-change-summary">${fromInference ? "显示：最新推理" : "显示：已保存修改"} · 病灶 ${boxN}</div>
            ${boxWarnings.length ? `<div class="bm-box-warn">${boxWarnings.map((w) => `<div>${w}</div>`).join("")}</div>` : ""}
            <label class="bm-pair-toggle"><input type="checkbox" id="pairMode"/> 配对模式</label>
            <label class="bm-pair-toggle"><input type="checkbox" id="reportMode"/> 报告模式</label>
          </div>
          <div class="bm-lists-cols">
            <div class="bm-panel-section">
              <div class="bm-panel-title">病灶列表 <span class="bm-count" id="lesionCount">${boxN}</span></div>
              <ul class="bm-lesion-list" id="lesionList"></ul>
            </div>
            <div class="bm-panel-section">
              <div class="bm-panel-title">骨骼区域 <span class="bm-count" id="boneCount">0</span></div>
              <ul class="bm-bone-list" id="boneList"></ul>
            </div>
          </div>
          <section class="bm-action-dock" aria-label="病例重要操作">
            <header class="bm-action-dock-head">
              <span class="bm-action-dock-title">重要操作</span>
              <span class="bm-action-dock-hint" id="signDockHint">尚未生成正式报告</span>
            </header>
            <div class="bm-action-dock-row">
              <button type="button" id="btnRerun" class="bm-dock-btn bm-dock-rerun">
                <span class="bm-dock-icon" aria-hidden="true">↻</span>
                <span class="bm-dock-text">
                  <span class="bm-dock-label">重新推理</span>
                  <span class="bm-dock-desc">覆盖当前框</span>
                </span>
              </button>
              <button type="button" id="btnResetInf" class="bm-dock-btn bm-dock-reset">
                <span class="bm-dock-icon" aria-hidden="true">⟲</span>
                <span class="bm-dock-text">
                  <span class="bm-dock-label">恢复推理框</span>
                  <span class="bm-dock-desc">撤销人工修改</span>
                </span>
              </button>
            </div>
            <button type="button" id="btnSign" class="bm-dock-btn bm-dock-sign bm-dock-sign--none">
              <span class="bm-dock-sign-badge">待签发</span>
              <span class="bm-dock-icon" aria-hidden="true">✓</span>
              <span class="bm-dock-text">
                <span class="bm-dock-label">签发报告</span>
                <span class="bm-dock-desc">根据当前审阅生成 PDF 并归档</span>
              </span>
            </button>
          </section>
        </aside>
      </div>
    </div>`;

  if (!detail.images.front || !detail.images.back) {
    setSaveStatus("缺少图像");
    return;
  }

  let pairedMode = false;
  let reportMode = false;
  function isPaired() { return pairedMode; }

  type AnalysisLesion = {
    view: string; box_index: number; lesion_id?: string;
    bone_label?: string; assessment?: string; assessment_zh?: string;
    features?: { lbr?: number };
  };
  let analysisData = detail.data["inference/lesion_analysis.json"] as { lesions?: AnalysisLesion[] } | undefined;
  const analysisMap = new Map<string, AnalysisLesion>();
  function _rebuildAnalysisMap() {
    analysisMap.clear();
    if (analysisData?.lesions) {
      for (const al of analysisData.lesions) {
        analysisMap.set(`${al.view}:${al.box_index}`, al);
      }
    }
  }
  _rebuildAnalysisMap();

  _onAnalysisUpdate = (newAnalysis: { lesions?: AnalysisLesion[] }) => {
    analysisData = newAnalysis;
    _rebuildAnalysisMap();
    if (reportMode) refreshAllLists();
  };

  function _analysisFor(view: string, idx: number): AnalysisLesion | undefined {
    return analysisMap.get(`${view}:${idx}`);
  }

  const _ASSESS_OPTIONS: { value: string; label: string }[] = [
    { value: "suspicious", label: "不排除骨转移" },
    { value: "indeterminate", label: "性质待定" },
    { value: "likely_benign", label: "考虑良性" },
  ];

  function _assessmentSelect(al: AnalysisLesion | undefined, key: string): string {
    if (!al) return "";
    const cur = al.assessment || "likely_benign";
    const cls = cur === "suspicious" ? "rpt-suspicious"
      : cur === "indeterminate" ? "rpt-indeterminate" : "rpt-benign";
    const opts = _ASSESS_OPTIONS.map((o) =>
      `<option value="${o.value}"${o.value === cur ? " selected" : ""}>${o.label}</option>`
    ).join("");
    return `<select class="bm-assess-select ${cls}" data-assess-key="${key}">${opts}</select>`;
  }

  let assessSaveTimer: ReturnType<typeof setTimeout> | null = null;
  const assessDirty = new Set<string>();

  function _flushAssessChanges() {
    if (assessDirty.size === 0) return;
    const overrides = [...assessDirty].map((k) => {
      const al = analysisMap.get(k)!;
      const [view, idx] = k.split(":");
      return { view, box_index: Number(idx), assessment: al.assessment || "", assessment_zh: al.assessment_zh || "" };
    });
    assessDirty.clear();
    fetchJson(caseApi(uid, "/analysis"), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ overrides }),
    }).catch((e) => setSaveStatus(`评估保存失败: ${e}`));
  }

  function _onAssessChange(key: string, newVal: string) {
    const al = analysisMap.get(key);
    if (!al) return;
    al.assessment = newVal;
    al.assessment_zh = _ASSESS_OPTIONS.find((o) => o.value === newVal)?.label || "";
    assessDirty.add(key);
    if (assessSaveTimer) clearTimeout(assessSaveTimer);
    assessSaveTimer = setTimeout(_flushAssessChanges, 800);
    refreshLesionList();
    refreshBoneList();
  }

  function refreshLesionList() {
    if (!editor) return;
    const listEl = document.getElementById("lesionList");
    const countEl = document.getElementById("lesionCount");
    if (!listEl) return;

    type FlatItem = { view: "front" | "back"; idx: number; box: Box };
    const flat: FlatItem[] = [];
    for (const view of ["front", "back"] as const) {
      const boxes = view === "front" ? reviewFront : reviewBack;
      boxes.forEach((b, i) => flat.push({ view, idx: i, box: b }));
    }
    flat.sort((a, b) => a.box.cy - b.box.cy);

    const selFront = (editor as any).front.selected as number | null;
    const selBack = (editor as any).back.selected as number | null;

    const showAssess = reportMode;

    if (reportMode && !isPaired()) {
      pairedMode = true;
      const chk = document.getElementById("pairMode") as HTMLInputElement | null;
      if (chk) chk.checked = true;
    }

    if (isPaired()) {
      type MergedLesion = { id: string; entries: FlatItem[]; minCy: number };
      const byId = new Map<string, MergedLesion>();
      const singles: FlatItem[] = [];
      for (const it of flat) {
        const lid = it.box.lesion_id;
        if (lid) {
          let m = byId.get(lid);
          if (!m) { m = { id: lid, entries: [], minCy: it.box.cy }; byId.set(lid, m); }
          m.entries.push(it);
          if (it.box.cy < m.minCy) m.minCy = it.box.cy;
        } else {
          singles.push(it);
        }
      }
      const merged = [...byId.values()].sort((a, b) => a.minCy - b.minCy);
      singles.sort((a, b) => a.box.cy - b.box.cy);

      type DisplayItem = { kind: "merged"; m: MergedLesion } | { kind: "single"; it: FlatItem };
      let displayItems: DisplayItem[] = [
        ...merged.map((m) => ({ kind: "merged" as const, m })),
        ...singles.map((it) => ({ kind: "single" as const, it })),
      ];

      const getAssessment = (d: DisplayItem): string => {
        if (d.kind === "merged") {
          const al = _analysisFor(d.m.entries[0].view, d.m.entries[0].idx);
          return al?.assessment || "unknown";
        }
        const al = _analysisFor(d.it.view, d.it.idx);
        return al?.assessment || "unknown";
      };

      if (reportMode) {
        const tierOrder: Record<string, number> = { suspicious: 0, indeterminate: 1, likely_benign: 2, unknown: 3 };
        displayItems.sort((a, b) => (tierOrder[getAssessment(a)] ?? 9) - (tierOrder[getAssessment(b)] ?? 9));
      }

      const totalCount = displayItems.length;
      if (countEl) countEl.textContent = String(totalCount);

      let html = "";
      let lastTier = "";
      const tierLabels: Record<string, string> = {
        suspicious: "可疑转移",
        indeterminate: "性质待定",
        likely_benign: "考虑良性",
        unknown: "未评估",
      };

      for (const d of displayItems) {
        if (reportMode) {
          const tier = getAssessment(d);
          if (tier !== lastTier) {
            const tierCls = tier === "suspicious" ? "rpt-suspicious"
              : tier === "indeterminate" ? "rpt-indeterminate" : "rpt-benign";
            html += `<li class="bm-li-group-header ${tierCls}">${tierLabels[tier] || tier}</li>`;
            lastTier = tier;
          }
        }

        if (d.kind === "merged") {
          const m = d.m;
          const isSel = m.entries.some(
            (e) => (e.view === "front" && selFront === e.idx) || (e.view === "back" && selBack === e.idx)
          );
          const views = m.entries.map((e) => e.view === "front" ? "正" : "背").join("+");
          const noSeg = m.entries.some((e) => e.box.seg_valid === false);
          const conf = m.entries[0].box.conf != null ? ` ${(m.entries[0].box.conf * 100).toFixed(0)}%` : "";
          const dataEntries = encodeURIComponent(JSON.stringify(m.entries.map((e) => ({ view: e.view, idx: e.idx }))));
          const al = _analysisFor(m.entries[0].view, m.entries[0].idx);
          const bone = al?.bone_label || "";
          const assessKey = `${m.entries[0].view}:${m.entries[0].idx}`;
          const dropdown = showAssess ? _assessmentSelect(al, assessKey) : "";
          html += `<li class="bm-li${isSel ? " active" : ""}${noSeg ? " no-seg" : ""}" data-paired="${dataEntries}" data-lid="${m.id}">
            <span class="bm-li-tag paired">${views}</span>
            <span class="bm-li-label">${bone || m.id}${noSeg ? " ?" : ""}</span>
            ${dropdown || `<span class="bm-li-conf">${conf}</span>`}
          </li>`;
        } else {
          const it = d.it;
          const isSel = (it.view === "front" && selFront === it.idx) || (it.view === "back" && selBack === it.idx);
          const viewLabel = it.view === "front" ? "正" : "背";
          const noSeg = it.box.seg_valid === false;
          const conf = it.box.conf != null ? ` ${(it.box.conf * 100).toFixed(0)}%` : "";
          const al = _analysisFor(it.view, it.idx);
          const bone = al?.bone_label || "";
          const label = bone || `#${it.idx + 1}`;
          const assessKey = `${it.view}:${it.idx}`;
          const dropdown = showAssess ? _assessmentSelect(al, assessKey) : "";
          html += `<li class="bm-li${isSel ? " active" : ""}${noSeg ? " no-seg" : ""}" data-view="${it.view}" data-idx="${it.idx}">
            <span class="bm-li-tag ${it.view}">${viewLabel}</span>
            <span class="bm-li-label">${label}${noSeg ? " ?" : ""}</span>
            ${dropdown || `<span class="bm-li-conf">${conf}</span>`}
          </li>`;
        }
      }
      listEl.innerHTML = html;
      listEl.querySelectorAll(".bm-li[data-paired]").forEach((li) => {
        li.addEventListener("click", () => {
          const raw = decodeURIComponent((li as HTMLElement).dataset.paired || "[]");
          const entries: { view: "front" | "back"; idx: number }[] = JSON.parse(raw);
          const lid = (li as HTMLElement).dataset.lid;
          editor?.selectBoxPaired(lid, entries);
        });
        li.addEventListener("mouseenter", () => {
          const raw = decodeURIComponent((li as HTMLElement).dataset.paired || "[]");
          const entries: { view: "front" | "back"; idx: number }[] = JSON.parse(raw);
          editor?.setHoverBoxes(entries);
        });
        li.addEventListener("mouseleave", () => editor?.clearHover());
      });
      listEl.querySelectorAll(".bm-li[data-view]").forEach((li) => {
        li.addEventListener("click", () => {
          const v = (li as HTMLElement).dataset.view as "front" | "back";
          const i = Number((li as HTMLElement).dataset.idx);
          editor?.selectBox(v, i);
        });
        li.addEventListener("mouseenter", () => {
          const v = (li as HTMLElement).dataset.view as "front" | "back";
          const i = Number((li as HTMLElement).dataset.idx);
          editor?.setHoverBoxes([{ view: v, idx: i }]);
        });
        li.addEventListener("mouseleave", () => editor?.clearHover());
      });
      listEl.querySelectorAll(".bm-assess-select").forEach((sel) => {
        sel.addEventListener("click", (e) => e.stopPropagation());
        sel.addEventListener("change", (e) => {
          const s = e.target as HTMLSelectElement;
          _onAssessChange(s.dataset.assessKey || "", s.value);
        });
      });
    } else {
      if (countEl) countEl.textContent = String(flat.length);
      listEl.innerHTML = flat
        .map((it) => {
          const isSel = (it.view === "front" && selFront === it.idx) || (it.view === "back" && selBack === it.idx);
          const viewLabel = it.view === "front" ? "正" : "背";
          const label = it.box.lesion_id || `#${it.idx + 1}`;
          const conf = it.box.conf != null ? ` ${(it.box.conf * 100).toFixed(0)}%` : "";
          const noSeg = it.box.seg_valid === false;
          return `<li class="bm-li${isSel ? " active" : ""}${noSeg ? " no-seg" : ""}" data-view="${it.view}" data-idx="${it.idx}">
            <span class="bm-li-tag ${it.view}">${viewLabel}</span>
            <span class="bm-li-label">${label}${noSeg ? " ?" : ""}</span>
            <span class="bm-li-conf">${conf}</span>
          </li>`;
        })
        .join("");
      listEl.querySelectorAll(".bm-li").forEach((li) => {
        li.addEventListener("click", () => {
          const v = (li as HTMLElement).dataset.view as "front" | "back";
          const i = Number((li as HTMLElement).dataset.idx);
          editor?.selectBox(v, i);
        });
        li.addEventListener("mouseenter", () => {
          const v = (li as HTMLElement).dataset.view as "front" | "back";
          const i = Number((li as HTMLElement).dataset.idx);
          editor?.setHoverBoxes([{ view: v, idx: i }]);
        });
        li.addEventListener("mouseleave", () => editor?.clearHover());
      });
    }
    const activeEl = listEl.querySelector(".bm-li.active") as HTMLElement | null;
    if (activeEl) activeEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function refreshBoneList() {
    if (!editor) return;
    const listEl = document.getElementById("boneList");
    const countEl = document.getElementById("boneCount");
    if (!listEl) return;

    const capVertebra = (name: string, count: number) =>
      count > 1 && (/胸椎|腰椎/.test(name)) ? 1 : count;

    const boneCentroidY = (item: BonePolygonItem): number => {
      let sumY = 0, count = 0;
      for (const poly of item.polygons) {
        const rings = poly.rings || [{ points: poly.points }];
        for (const ring of rings) {
          for (const pt of ring.points) { sumY += pt.y; count++; }
        }
      }
      return count > 0 ? sumY / count : 0.5;
    };

    const boneGroupOrder = (name: string): [number, number] => {
      if (/颅骨/.test(name)) return [0, 0];
      if (/颈椎/.test(name)) return [1, 0];
      if (/胸椎/.test(name)) { const m = name.match(/第(\d+)/); return [2, m ? +m[1] : 0]; }
      if (/腰椎/.test(name)) { const m = name.match(/第(\d+)/); return [3, m ? +m[1] : 0]; }
      if (/骶骨/.test(name)) return [4, 0];
      if (/胸骨/.test(name)) return [5, 0];
      if (/锁骨/.test(name)) return [6, 0];
      if (/肩胛骨/.test(name)) return [7, 0];
      if (/肩关节/.test(name)) return [8, 0];
      if (/肋/.test(name)) { const m = name.match(/第(\d+)/); return [9, m ? +m[1] : 0]; }
      if (/肱骨/.test(name)) return [10, 0];
      if (/肘关节/.test(name)) return [11, 0];
      if (/前臂/.test(name)) return [12, 0];
      if (/手/.test(name)) return [13, 0];
      if (/骨盆/.test(name)) return [14, 0];
      if (/股骨/.test(name)) return [15, 0];
      if (/膝关节/.test(name)) return [16, 0];
      if (/胫骨/.test(name)) return [17, 0];
      if (/足/.test(name)) return [18, 0];
      return [19, 0];
    };

    const boneSortCmp = (a: string, b: string): number => {
      const [ga, sa] = boneGroupOrder(a);
      const [gb, sb] = boneGroupOrder(b);
      return ga !== gb ? ga - gb : sa - sb;
    };

    type BoneEntry = { view: "front" | "back"; idx: number; item: BonePolygonItem; lesions: number; cy: number };
    const raw: BoneEntry[] = [];
    for (const view of ["front", "back"] as const) {
      const items = editor.boneContours[view];
      const counts = editor.lesionCountsPerBone(view);
      items.forEach((item, i) => {
        const name = item.name || "";
        raw.push({ view, idx: i, item, lesions: capVertebra(name, counts[i] || 0), cy: boneCentroidY(item) });
      });
    }
    raw.sort((a, b) => boneSortCmp(a.item.name || "", b.item.name || ""));

    const sel = editor.selectedBone;
    const selNames = editor._selectedBoneNames;

    const boneAssessment = (boneName: string): string => {
      if (!analysisData?.lesions) return "";
      const tierRank: Record<string, number> = { suspicious: 0, indeterminate: 1, likely_benign: 2 };
      let worst = "";
      let worstRank = 99;
      for (const al of analysisData.lesions) {
        if (al.bone_label === boneName && al.assessment) {
          const r = tierRank[al.assessment] ?? 9;
          if (r < worstRank) { worstRank = r; worst = al.assessment; }
        }
      }
      return worst;
    };

    const boneAssessBadge = (boneName: string): string => {
      if (!reportMode) return "";
      const a = boneAssessment(boneName);
      if (!a) return "";
      const labels: Record<string, string> = { suspicious: "可疑", indeterminate: "待定", likely_benign: "良性" };
      const cls = a === "suspicious" ? "rpt-suspicious" : a === "indeterminate" ? "rpt-indeterminate" : "rpt-benign";
      return `<span class="bm-li-assess ${cls}">${labels[a] || ""}</span>`;
    };

    if (isPaired()) {
      type MergedBone = { name: string; color: string; lesions: number; entries: BoneEntry[]; minCy: number };
      const byName = new Map<string, MergedBone>();
      for (const e of raw) {
        const name = e.item.name || `${e.item.group}-${e.item.label}`;
        let m = byName.get(name);
        if (!m) { m = { name, color: e.item.color, lesions: 0, entries: [], minCy: e.cy }; byName.set(name, m); }
        if (e.cy < m.minCy) m.minCy = e.cy;
        m.lesions += e.lesions;
        m.entries.push(e);
      }
      const merged = [...byName.values()].sort((a, b) => boneSortCmp(a.name, b.name));
      for (const m of merged) m.lesions = capVertebra(m.name, m.lesions);
      if (reportMode) {
        const tierRank: Record<string, number> = { suspicious: 0, indeterminate: 1, likely_benign: 2 };
        merged.sort((a, b) => {
          const ra = tierRank[boneAssessment(a.name)] ?? (a.lesions > 0 ? 3 : 9);
          const rb = tierRank[boneAssessment(b.name)] ?? (b.lesions > 0 ? 3 : 9);
          return ra !== rb ? ra - rb : boneSortCmp(a.name, b.name);
        });
      }
      if (countEl) countEl.textContent = String(merged.length);
      listEl.innerHTML = merged
        .map((m) => {
          const isSel = selNames.includes(m.name) ||
            m.entries.some((e) => sel?.view === e.view && sel?.idx === e.idx);
          const badge = m.lesions > 0 ? `<span class="bm-li-badge">${m.lesions}</span>` : "";
          const assessTag = boneAssessBadge(m.name);
          return `<li class="bm-li${isSel ? " active" : ""}" data-bone-name="${encodeURIComponent(m.name)}">
            <span class="bm-li-swatch" style="background:${m.color}"></span>
            <span class="bm-li-label">${m.name}</span>
            ${assessTag}${badge}
          </li>`;
        })
        .join("");
      listEl.querySelectorAll(".bm-li").forEach((li) => {
        li.addEventListener("click", () => {
          const name = decodeURIComponent((li as HTMLElement).dataset.boneName || "");
          editor?.selectBonePaired(name);
        });
        li.addEventListener("mouseenter", () => {
          const name = decodeURIComponent((li as HTMLElement).dataset.boneName || "");
          editor?.setHoverBones([name]);
        });
        li.addEventListener("mouseleave", () => editor?.clearHover());
      });
    } else {
      if (countEl) countEl.textContent = String(raw.length);
      listEl.innerHTML = raw
        .map((e) => {
          const isSel = (sel?.view === e.view && sel?.idx === e.idx) ||
            selNames.includes(e.item.name || "");
          const viewLabel = e.view === "front" ? "正" : "背";
          const name = e.item.name || `${e.item.group}-${e.item.label}`;
          const badge = e.lesions > 0 ? `<span class="bm-li-badge">${e.lesions}</span>` : "";
          return `<li class="bm-li${isSel ? " active" : ""}" data-view="${e.view}" data-idx="${e.idx}">
            <span class="bm-li-swatch" style="background:${e.item.color}"></span>
            <span class="bm-li-tag ${e.view}">${viewLabel}</span>
            <span class="bm-li-label">${name}</span>
            ${badge}
          </li>`;
        })
        .join("");
      listEl.querySelectorAll(".bm-li").forEach((li) => {
        li.addEventListener("click", () => {
          const v = (li as HTMLElement).dataset.view as "front" | "back";
          const i = Number((li as HTMLElement).dataset.idx);
          editor?.selectBone(v, i);
        });
        li.addEventListener("mouseenter", () => {
          const v = (li as HTMLElement).dataset.view as "front" | "back";
          const i = Number((li as HTMLElement).dataset.idx);
          const item = editor?.boneContours[v]?.[i];
          if (item?.name) editor?.setHoverBones([item.name]);
        });
        li.addEventListener("mouseleave", () => editor?.clearHover());
      });
    }
    const activeEl = listEl.querySelector(".bm-li.active") as HTMLElement | null;
    if (activeEl) activeEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function refreshAllLists() {
    refreshLesionList();
    refreshBoneList();
  }

  function highlightListItems(listId: string, items: { view: "front" | "back"; idx: number }[]) {
    const listEl = document.getElementById(listId);
    if (!listEl) return;
    listEl.querySelectorAll(".bm-li").forEach((li) => (li as HTMLElement).classList.remove("hover"));
    let scrollTarget: HTMLElement | null = null;

    for (const item of items) {
      if (isPaired()) {
        if (listId === "lesionList") {
          const box = (item.view === "front" ? reviewFront : reviewBack)[item.idx];
          const lid = box?.lesion_id;
          if (lid) {
            const el = listEl.querySelector(`.bm-li[data-lid="${lid}"]`) as HTMLElement | null;
            if (el && !el.classList.contains("hover")) { el.classList.add("hover"); scrollTarget = scrollTarget || el; }
            continue;
          }
        }
        if (listId === "boneList" && editor) {
          const boneName = editor.boneContours[item.view]?.[item.idx]?.name;
          if (boneName) {
            const el = listEl.querySelector(`.bm-li[data-bone-name="${encodeURIComponent(boneName)}"]`) as HTMLElement | null;
            if (el && !el.classList.contains("hover")) { el.classList.add("hover"); scrollTarget = scrollTarget || el; }
            continue;
          }
        }
      }
      const el = listEl.querySelector(`.bm-li[data-view="${item.view}"][data-idx="${item.idx}"]`) as HTMLElement | null;
      if (el && !el.classList.contains("hover")) { el.classList.add("hover"); scrollTarget = scrollTarget || el; }
    }
    if (scrollTarget) scrollTarget.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function clearListHighlights() {
    document.querySelectorAll("#lesionList .bm-li.hover, #boneList .bm-li.hover").forEach(
      (el) => (el as HTMLElement).classList.remove("hover")
    );
  }

  editor = new ReviewEditor(reviewFront, reviewBack, detail.images.front, detail.images.back, {
    onChange: () => {
      markDirty();
      refreshAllLists();
    },
    onStatus: (msg) => setBenchHint(msg),
    onOpChange: syncOpButtons,
    onSelectionChange: refreshAllLists,
    onHoverChange: (items, kind) => {
      if (items.length > 0) {
        const listId = kind === "box" ? "lesionList" : "boneList";
        highlightListItems(listId, items);
      } else {
        clearListHighlights();
      }
    },
  });
  editor.mountCombined($("#cvCombined") as HTMLCanvasElement);
  refreshLesionList();

  for (const view of ["front", "back"] as const) {
    editor.loadOverlay(
      `lesion_${view}`,
      caseApi(uid, `/overlays/lesion_mask_${view}.png`)
    ).catch(() => {});
  }
  fetchJson<Record<string, BonePolygonItem[]>>(caseApi(uid, "/overlays/bone_contours"))
    .then((data) => {
      editor?.setBoneContours({
        front: data.front || [],
        back: data.back || [],
      });
      refreshBoneList();
    })
    .catch(() => {});

  if (boxWarnings.length) {
    setSaveStatus(boxWarnings[0]);
  } else if (seededFromInference) {
    setSaveStatus("最新推理 · 修改后请保存");
  } else {
    setSaveStatus(`已保存修改 · 病灶 ${boxN}`);
  }

  // --- Wire up toolbar buttons ---

  document.querySelectorAll(".bm-op-btn[data-op]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const op = (btn as HTMLElement).dataset.op as EditorOp;
      editor?.setOp(op);
    });
  });
  $("#bmBtnBoxes").addEventListener("click", (e) => {
    const on = !(editor?.showBoxes ?? true);
    editor?.setShowBoxes(on);
    (e.currentTarget as HTMLElement).classList.toggle("active", on);
  });
  $("#bmBtnContour").addEventListener("click", (e) => {
    const on = !(editor?.showLesionMask ?? true);
    editor?.setShowLesionMask(on);
    (e.currentTarget as HTMLElement).classList.toggle("active", on);
  });
  $("#bmBtnBone").addEventListener("click", (e) => {
    const on = !(editor?.showBoneOverlay ?? false);
    editor?.setShowBone(on);
    (e.currentTarget as HTMLElement).classList.toggle("active", on);
  });
  $("#bmBtnInvert").addEventListener("click", (e) => {
    const on = !(editor?.invertDisplay ?? true);
    editor?.setInvert(on);
    (e.currentTarget as HTMLElement).classList.toggle("active", on);
  });
  $("#bmZoomIn").addEventListener("click", () => editor?.zoomIn());
  $("#bmZoomOut").addEventListener("click", () => editor?.zoomOut());
  $("#bmZoomLabel").addEventListener("click", () => editor?.zoomReset());

  (document.getElementById("pairMode") as HTMLInputElement).addEventListener("change", (e) => {
    pairedMode = (e.target as HTMLInputElement).checked;
    refreshAllLists();
  });
  (document.getElementById("reportMode") as HTMLInputElement).addEventListener("change", (e) => {
    reportMode = (e.target as HTMLInputElement).checked;
    refreshAllLists();
  });

  // --- Resizable sidebar ---
  {
    const handle = document.getElementById("bmResizeHandle")!;
    const sidebar = document.getElementById("bmSidebar")!;
    let dragging = false;
    let startX = 0;
    let startW = 0;
    handle.addEventListener("mousedown", (e) => {
      e.preventDefault();
      dragging = true;
      startX = e.clientX;
      startW = sidebar.offsetWidth;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const dx = startX - e.clientX;
      sidebar.style.width = `${Math.max(200, Math.min(window.innerWidth * 0.6, startW + dx))}px`;
    });
    window.addEventListener("mouseup", () => {
      if (!dragging) return;
      dragging = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    });
  }

  // --- Action buttons ---
  updateSignButtonUI();
  $("#btnSave").addEventListener("click", () => saveReview(uid));
  $("#btnPreview").addEventListener("click", () => showReportPreview(uid));
  $("#btnSign").addEventListener("click", async () => {
    const state = effectiveSignState();
    if (state === "current") {
      if (!confirm("报告与当前审阅已一致，仍要重新生成并签发吗？")) return;
    } else if (state === "stale") {
      if (!confirm("将按当前审阅内容重新生成报告并签发，是否继续？")) return;
    }
    await saveReview(uid);
    const res = await fetchJson<{ report_pdf?: string; report_sign?: { signed_review_rev?: number } }>(
      caseApi(uid, "/sign"),
      { method: "POST" }
    );
    if (res.report_sign?.signed_review_rev != null) {
      _signedReviewRev = res.report_sign.signed_review_rev;
    } else {
      _signedReviewRev = reviewRev;
    }
    _reviewDirty = false;
    updateSignButtonUI();
    alert(res.report_pdf ? "已签发（Markdown + PDF 报告已生成）" : "已签发（Markdown 报告已生成，PDF 未生成）");
    nav("/");
  });

  fetchJson<{ cases: CaseRow[] }>("/api/cases").then((data) => {
    const idx = data.cases.findIndex((c) => c.study_uid === uid);
    const next = idx >= 0 ? data.cases[idx + 1] : null;
    if (next?.study_uid) {
      fetch(caseApi(next.study_uid)).catch(() => {});
    }
  });

  $("#btnRerun").addEventListener("click", async () => {
    if (
      reviewRev > 0 &&
      !confirm("重推理将用新模型结果覆盖当前已保存的框，是否继续？")
    ) {
      return;
    }
    setSaveStatus("推理排队中…");
    await fetchJson(caseApi(uid, "/run_pipeline"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reset_review: true }),
    });
    const pollMs = 2000;
    const maxWait = 600000;
    const t0 = Date.now();
    const timer = setInterval(async () => {
      try {
        const detail = await fetchJson<CaseDetail>(caseApi(uid));
        const meta = detail.data["meta.json"] as { pipeline_status?: string };
        const st = meta?.pipeline_status || "";
        if (st === "ready") {
          clearInterval(timer);
          await renderCase(uid, nav);
          setSaveStatus("推理完成，已刷新");
          return;
        }
        if (st === "failed") {
          clearInterval(timer);
          setSaveStatus("推理失败，请查看 worker 日志");
          return;
        }
        setSaveStatus(st === "running" ? "推理中…" : `状态: ${st}`);
        if (Date.now() - t0 > maxWait) {
          clearInterval(timer);
          setSaveStatus("推理超时，请确认 make worker 已启动后刷新");
        }
      } catch (e) {
        clearInterval(timer);
        setSaveStatus(String(e));
      }
    }, pollMs);
  });
  $("#btnResetInf").addEventListener("click", async () => {
    if (!confirm("将用最新推理结果覆盖当前框（仅未保存修改时可用），继续？")) return;
    try {
      await fetchJson(caseApi(uid, "/review/reset_inference"), { method: "POST" });
      await renderCase(uid, nav);
    } catch (e) {
      alert(String(e));
    }
  });
}

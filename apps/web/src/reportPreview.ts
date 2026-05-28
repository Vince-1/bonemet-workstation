import { fetchJson, caseApi, downloadReportPdf } from "./helpers";

type ReportContext = {
  study_uid: string;
  patient_display_id: string;
  approved_at: string;
  summary_line: string;
  findings_text: string;
  total_lesions: number;
  regions: { name: string; count: number }[];
  lesions: {
    index: number;
    view: string;
    lesion_id: string;
    bone_label: string;
    conf: string;
    assessment_zh?: string;
    lbr?: number | string;
  }[];
};

const FINDING_KEYWORDS: [RegExp, string][] = [
  [/不排除骨转移/g, "rpt-hl-suspicious"],
  [/性质待定，建议随诊/g, "rpt-hl-indeterminate"],
  [/考虑良性/g, "rpt-hl-benign"],
  [/对称性放射性摄取增高/g, "rpt-hl-benign"],
];

function highlightFindings(text: string, ctx: ReportContext): string {
  const regionNames = (ctx.regions || []).map((r) => r.name).filter(Boolean);
  const lesionBones = (ctx.lesions || []).map((l) => l.bone_label).filter(Boolean);
  const allNames = [...new Set([...regionNames, ...lesionBones])];
  allNames.sort((a, b) => b.length - a.length);

  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  if (allNames.length) {
    const pattern = new RegExp(`(${allNames.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "g");
    html = html.replace(pattern, '<span class="rpt-hl-region">$1</span>');
  }

  for (const [re, cls] of FINDING_KEYWORDS) {
    html = html.replace(re, (m) => `<span class="${cls}">${m}</span>`);
  }

  return html;
}

export async function showReportPreview(uid: string): Promise<void> {
  const prev = await fetchJson<{ markdown: string; context: ReportContext }>(
    caseApi(uid, "/report/preview")
  );
  const ctx = prev.context;

  const regionRows = (ctx.regions || [])
    .map((r, i) => `<tr class="${i % 2 ? "even" : ""}"><td>${r.name}</td><td class="num">${r.count}</td></tr>`)
    .join("");

  const assessCls = (a?: string) =>
    a === "不排除骨转移" ? "rpt-suspicious" : a === "考虑良性摄取增高" ? "rpt-benign" : "rpt-indeterminate";

  const lesionRows = (ctx.lesions || [])
    .map((l, i) => {
      const az = l.assessment_zh || "";
      const lbr = typeof l.lbr === "number" ? l.lbr.toFixed(2) : (l.lbr || "");
      return `<tr class="${i % 2 ? "even" : ""}"><td>${l.lesion_id}</td><td>${l.view}</td><td>${l.bone_label}</td><td class="num">${l.conf}</td><td class="num">${lbr}</td><td class="${assessCls(az)}">${az}</td></tr>`;
    })
    .join("");

  const html = `
    <div class="rpt-header">
      <h1>全身骨显像报告<span class="rpt-tag">科研辅助</span></h1>
    </div>
    <table class="rpt-meta">
      <tr><td class="rpt-meta-label">检查编号</td><td>${ctx.study_uid}</td></tr>
      <tr><td class="rpt-meta-label">患者编号</td><td>${ctx.patient_display_id}</td></tr>
      <tr><td class="rpt-meta-label">生成时间</td><td>${ctx.approved_at}</td></tr>
    </table>
    <div class="rpt-disclaimer">本系统为科研辅助工具，输出结果仅供临床参考，不能替代医师独立判断与正式诊断报告；不作为医疗器械注册产品使用。</div>
    <h2>检查结论</h2>
    <p class="rpt-summary">${ctx.summary_line}</p>
    <h2>检查所见</h2>
    <p class="rpt-findings">${highlightFindings(ctx.findings_text, ctx)}</p>
    <h2>各区域病灶统计</h2>
    ${ctx.regions?.length ? `
      <table class="rpt-table">
        <thead><tr><th>骨骼区域</th><th class="num">病灶数</th></tr></thead>
        <tbody>${regionRows}
          <tr class="rpt-total"><td><strong>合计</strong></td><td class="num"><strong>${ctx.total_lesions}</strong></td></tr>
        </tbody>
      </table>
    ` : "<p>未见明确骨转移灶。</p>"}
    <h2>病灶明细</h2>
    ${ctx.lesions?.length ? `
      <table class="rpt-table">
        <thead><tr><th>编号</th><th>视图</th><th>所属骨骼</th><th class="num">置信度</th><th class="num">LBR</th><th>评估</th></tr></thead>
        <tbody>${lesionRows}</tbody>
      </table>
    ` : "<p>无记录。</p>"}
    <div class="rpt-footer">本报告由 BoneMet Workstation 辅助生成，须经医师审核后签发。</div>
  `;

  const overlay = document.createElement("div");
  overlay.className = "bm-report-overlay";
  overlay.innerHTML = `<div class="bm-report-modal">
    <div class="bm-report-header">
      <span>报告预览</span>
      <div class="bm-report-actions">
        <button type="button" class="bm-report-export-pdf">导出 PDF</button>
        <button type="button" class="bm-report-close" title="关闭">&times;</button>
      </div>
    </div>
    <div class="bm-report-body">${html}</div>
  </div>`;
  overlay.querySelector(".bm-report-export-pdf")!.addEventListener("click", () => {
    downloadReportPdf(uid);
  });
  overlay.querySelector(".bm-report-close")!.addEventListener("click", () => overlay.remove());
  overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
}

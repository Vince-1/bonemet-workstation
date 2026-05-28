export type CaseRow = {
  study_uid: string;
  patient_display_id?: string;
  status?: string;
  pipeline_status?: string;
  review_task_count?: number;
  rev?: number;
  created_at?: string;
  updated_at?: string;
};

export type CaseDetail = {
  study_uid: string;
  images: { front?: string; back?: string };
  data: Record<string, unknown>;
};

export const DISCLAIMER_HTML = `<div class="disclaimer-bar" role="note">
  <strong>科研辅助</strong>：本系统输出仅供临床参考，不能替代医师独立判断；非医疗器械注册产品。
</div>`;

export const DISCLAIMER_COMPACT = `<div class="disclaimer-bar disclaimer-compact" role="note">
  <strong>科研辅助</strong>：输出仅供临床参考，不能替代医师独立判断。
</div>`;

export function $(sel: string) {
  return document.querySelector(sel)!;
}

export function caseApi(uid: string, sub = ""): string {
  return `/api/cases/${encodeURIComponent(uid)}${sub}`;
}

export function casePage(uid: string): string {
  return `/cases/${encodeURIComponent(uid)}`;
}

export function downloadReportPdf(uid: string): void {
  const url = caseApi(uid, "/report/pdf");
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      const j = JSON.parse(text);
      detail = j.detail?.message || j.detail || text;
      if (res.status === 409 && j.detail?.study_uid) {
        throw new Error(`409:病例已存在:${j.detail.study_uid}`);
      }
    } catch (e) {
      if (e instanceof Error && e.message.startsWith("409:")) throw e;
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

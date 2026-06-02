import type { CaseRow } from "./helpers";

export type PipelineProgress = {
  step?: number;
  total_steps?: number;
  percent?: number;
  stage?: string;
  label?: string;
  updated_at?: string;
};

export function isPipelineActive(c: {
  pipeline_status?: string;
  status?: string;
}): boolean {
  const ps = c.pipeline_status || "";
  const st = c.status || "";
  return ps === "queued" || ps === "running" || st === "computing" || st === "ingesting";
}

export function pipelineProgressText(
  pipelineStatus?: string,
  progress?: PipelineProgress | null,
): string {
  if (progress?.label) {
    const pct = progress.percent ?? 0;
    const step = progress.step ?? 0;
    const total = progress.total_steps ?? 0;
    if (total > 0) {
      return `${progress.label} (${step}/${total} · ${pct}%)`;
    }
    return `${progress.label} (${pct}%)`;
  }
  if (pipelineStatus === "queued") return "排队中…";
  if (pipelineStatus === "running") return "推理中…";
  return "推理中…";
}

export function pipelineProgressPercent(progress?: PipelineProgress | null): number {
  if (progress?.percent != null) return Math.max(0, Math.min(100, progress.percent));
  return 0;
}

export function pipelineProgressBarHtml(
  percent: number,
  opts?: { compact?: boolean; className?: string },
): string {
  const cls = opts?.className || (opts?.compact ? "bm-pipe-progress bm-pipe-progress--compact" : "bm-pipe-progress");
  const p = Math.max(0, Math.min(100, percent));
  return `<div class="${cls}" role="progressbar" aria-valuenow="${p}" aria-valuemin="0" aria-valuemax="100">
    <div class="bm-pipe-progress-fill" style="width:${p}%"></div>
  </div>`;
}

export function pipelineStatusCellHtml(c: CaseRow): string {
  if (!isPipelineActive(c)) {
    return "";
  }
  const pct = pipelineProgressPercent(c.pipeline_progress);
  const text = pipelineProgressText(c.pipeline_status, c.pipeline_progress);
  return `<div class="cl-pipe-status">
    ${pipelineProgressBarHtml(pct, { compact: true })}
    <span class="cl-pipe-label" title="${text}">${text}</span>
  </div>`;
}

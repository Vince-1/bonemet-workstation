export type Box = {
  cls: number;
  cx: number;
  cy: number;
  w: number;
  h: number;
  conf?: number;
  lesion_id?: string;
  seg_valid?: boolean;
};

export type BonePolygonRing = {
  points: { x: number; y: number }[];
};

export type BonePolygonItem = {
  group: string;
  label: number;
  color: string;
  name?: string;
  polygons: { points: { x: number; y: number }[]; rings?: BonePolygonRing[] }[];
};

type ViewName = "front" | "back";
export type EditorOp = "none" | "add" | "remove" | "move";

export type ReviewEditorOptions = {
  onChange: () => void;
  onStatus?: (msg: string) => void;
  onOpChange?: (op: EditorOp) => void;
  onSelectionChange?: () => void;
  onHoverChange?: (items: { view: ViewName; idx: number }[], kind: "box" | "bone") => void;
};

type ViewLayout = { ix: number; iy: number; iw: number; ih: number };

type ViewState = {
  selected: number | null;
  imageUrl: string;
  color: string;
  layout: ViewLayout | null;
};

const PAIR_GAP = 16;

type UndoSnapshot = {
  frontBoxes: Box[];
  backBoxes: Box[];
  frontSelected: number | null;
  backSelected: number | null;
};

const MAX_UNDO = 50;
const HANDLE_R = 5;

type ResizeEdge = "nw" | "ne" | "sw" | "se" | "n" | "s" | "e" | "w";
const EDGE_CURSORS: Record<ResizeEdge, string> = {
  nw: "nwse-resize", ne: "nesw-resize", sw: "nesw-resize", se: "nwse-resize",
  n: "ns-resize", s: "ns-resize", e: "ew-resize", w: "ew-resize",
};

export class ReviewEditor {
  activeView: ViewName = "front";
  opMode: EditorOp = "none";
  invertDisplay = true;
  showBoxes = true;
  showBoneOverlay = true;
  showLesionMask = true;
  boneOpacity = 0.35;
  displayZoom = 1;
  wwBrightness = 1.0;
  wwContrast = 1.0;

  boneContours: Record<ViewName, BonePolygonItem[]> = { front: [], back: [] };
  selectedBone: { view: ViewName; idx: number } | null = null;
  hoveredBoxes: { view: ViewName; idx: number }[] = [];
  hoveredBoneNames: string[] = [];
  private pendingRemove: { view: ViewName; idx: number } | null = null;
  private overlayImages: Record<string, HTMLImageElement> = {};
  private undoStack: UndoSnapshot[] = [];

  private front: ViewState;
  private back: ViewState;

  private canvas: HTMLCanvasElement | null = null;
  private images: Record<ViewName, HTMLImageElement> = { front: new Image(), back: new Image() };
  private drag:
    | { mode: "move"; view: ViewName; idx: number; offX: number; offY: number }
    | { mode: "draw"; view: ViewName; x0: number; y0: number; x1: number; y1: number }
    | { mode: "resize"; view: ViewName; idx: number; edge: ResizeEdge; anchorX: number; anchorY: number }
    | { mode: "wl"; startX: number; startY: number; startBri: number; startCon: number }
    | null = null;

  constructor(
    public frontBoxes: Box[],
    public backBoxes: Box[],
    frontUrl: string,
    backUrl: string,
    private opts: ReviewEditorOptions
  ) {
    this.front = { selected: null, imageUrl: frontUrl, color: "#eab308", layout: null };
    this.back = { selected: null, imageUrl: backUrl, color: "#38bdf8", layout: null };
  }

  mountCombined(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    canvas.addEventListener("contextmenu", (e) => e.preventDefault());
    canvas.addEventListener("mousedown", (e) => this.onDown(e));
    canvas.addEventListener("mousemove", (e) => this.onMove(e));
    canvas.addEventListener("mouseup", (e) => this.onUp(e));
    canvas.addEventListener("mouseleave", (e) => this.onUp(e));
    window.addEventListener("keydown", (e) => this.onKey(e));
    window.addEventListener("resize", () => this.applyFitWidth());
    void this.loadAll();
  }

  setOp(mode: EditorOp) {
    this.opMode = mode;
    this.hoveredBoxes = [];
    this.hoveredBoneNames = [];
    this.pendingRemove = null;
    this.opts.onOpChange?.(mode);
    const hints: Record<EditorOp, string> = {
      none: "浏览：悬浮高亮 · 点击选中 · Esc",
      move: "移框：拖拽移动 (M)",
      add: "补框：拖拽绘制 (A)",
      remove: "删框：点击删除 (R)",
    };
    this.status(hints[mode]);
    if (this.canvas) {
      this.canvas.style.cursor = mode === "move" ? "grab" : mode === "add" ? "crosshair" : "default";
    }
    this.redrawAll();
  }

  selectBox(view: ViewName, idx: number) {
    this.activeView = view;
    const boxes = this.boxesRef(view);
    if (idx < 0 || idx >= boxes.length) return;
    ["front", "back"].forEach((v) => {
      if (v !== view) this.state(v as ViewName).selected = null;
    });
    this.state(view).selected = idx;
    this.selectedBone = null;
    this.setOp("none");
    this.redrawAll();
    this.status(`已选中 ${view === "front" ? "正面" : "背面"} #${idx + 1}`);
    this.opts.onSelectionChange?.();
  }

  /** Select boxes on both views by lesion_id, or single box if no pair. */
  selectBoxPaired(lesionId: string | undefined, entries: { view: ViewName; idx: number }[]) {
    this.selectedBone = null;
    this.front.selected = null;
    this.back.selected = null;
    for (const e of entries) {
      this.state(e.view).selected = e.idx;
    }
    if (entries.length > 0) this.activeView = entries[0].view;
    this.setOp("none");
    this.redrawAll();
    this.opts.onSelectionChange?.();
  }

  /** Select all bone regions matching a name across both views. */
  selectBonePaired(name: string) {
    this.front.selected = null;
    this.back.selected = null;
    this.selectedBone = null;
    this._selectedBoneNames = [name];
    this.redrawAll();
    this.opts.onSelectionChange?.();
  }

  /** Currently highlighted bone names (for paired mode). */
  _selectedBoneNames: string[] = [];

  // ── External hover control (list → canvas) ──

  setHoverBoxes(items: { view: ViewName; idx: number }[]) {
    this.hoveredBoxes = items;
    this.hoveredBoneNames = [];
    this.redrawAll();
    if (items.length > 0) this.scrollToRegion(items[0].view, items[0].idx, "box");
  }

  setHoverBones(names: string[]) {
    this.hoveredBoneNames = names;
    this.hoveredBoxes = [];
    this.redrawAll();
    if (names.length > 0) {
      for (const view of ["front", "back"] as ViewName[]) {
        const idx = this.boneContours[view].findIndex((b) => names.includes(b.name || ""));
        if (idx >= 0) { this.scrollToRegion(view, idx, "bone"); break; }
      }
    }
  }

  clearHover() {
    if (this.hoveredBoxes.length === 0 && this.hoveredBoneNames.length === 0) return;
    this.hoveredBoxes = [];
    this.hoveredBoneNames = [];
    this.redrawAll();
  }

  private scrollToRegion(view: ViewName, idx: number, kind: "box" | "bone") {
    const L = this.state(view).layout;
    if (!L || !this.canvas) return;
    const scrollEl = this.canvas.closest(".bm-views") as HTMLElement | null;
    if (!scrollEl) return;

    const canvasH = this.canvas.height;
    const yOff = (canvasH - L.ih) / 2;
    let px: number, py: number;

    if (kind === "box") {
      const boxes = this.boxesRef(view);
      if (idx >= boxes.length) return;
      px = L.ix + boxes[idx].cx * L.iw;
      py = yOff + boxes[idx].cy * L.ih;
    } else {
      const item = this.boneContours[view][idx];
      if (!item?.polygons?.length) return;
      const img = this.images[view];
      const natW = img.naturalWidth || 1;
      const natH = img.naturalHeight || 1;
      let sumX = 0, sumY = 0, count = 0;
      for (const poly of item.polygons) {
        const rings = poly.rings || [{ points: poly.points }];
        for (const ring of rings) {
          for (const pt of ring.points) { sumX += pt.x; sumY += pt.y; count++; }
        }
      }
      if (count === 0) return;
      px = L.ix + (sumX / count) * (L.iw / natW);
      py = yOff + (sumY / count) * (L.ih / natH);
    }

    const canvasRect = this.canvas.getBoundingClientRect();
    const scrollRect = scrollEl.getBoundingClientRect();
    const scaleCSS = canvasRect.width > 0 ? canvasRect.width / this.canvas.width : 1;

    const relX = (canvasRect.left - scrollRect.left) + px * scaleCSS;
    const relY = (canvasRect.top - scrollRect.top) + py * scaleCSS;

    const margin = 40;
    let dx = 0, dy = 0;

    if (relX < margin) {
      dx = relX - margin;
    } else if (relX > scrollEl.clientWidth - margin) {
      dx = relX - (scrollEl.clientWidth - margin);
    }

    if (relY < margin) {
      dy = relY - margin;
    } else if (relY > scrollEl.clientHeight - margin) {
      dy = relY - (scrollEl.clientHeight - margin);
    }

    if (dx !== 0 || dy !== 0) {
      scrollEl.scrollTo({
        left: scrollEl.scrollLeft + dx,
        top: scrollEl.scrollTop + dy,
        behavior: "smooth",
      });
    }
  }

  setInvert(on: boolean) {
    this.invertDisplay = on;
    this.redrawAll();
  }

  setShowBoxes(on: boolean) {
    this.showBoxes = on;
    this.redrawAll();
  }

  setShowBone(on: boolean) {
    this.showBoneOverlay = on;
    this.redrawAll();
  }

  setShowLesionMask(on: boolean) {
    this.showLesionMask = on;
    this.redrawAll();
  }

  setBoneContours(data: Record<ViewName, BonePolygonItem[]>) {
    this.boneContours = data;
    this.redrawAll();
  }

  selectBone(view: ViewName, idx: number) {
    const items = this.boneContours[view];
    if (idx < 0 || idx >= items.length) {
      this.selectedBone = null;
    } else {
      this.selectedBone = { view, idx };
      this.activeView = view;
    }
    this._selectedBoneNames = [];
    this.redrawAll();
    this.opts.onSelectionChange?.();
  }

  deselectBone() {
    this.selectedBone = null;
    this._selectedBoneNames = [];
    this.redrawAll();
    this.opts.onSelectionChange?.();
  }

  /** Count lesions whose center falls inside each bone region (for active view). */
  lesionCountsPerBone(view: ViewName): number[] {
    const bones = this.boneContours[view];
    const boxes = this.boxesRef(view);
    const img = this.images[view];
    const natW = img.naturalWidth || 1;
    const natH = img.naturalHeight || 1;
    return bones.map((bone) => {
      let count = 0;
      for (const box of boxes) {
        const px = box.cx * natW;
        const py = box.cy * natH;
        if (this.pointInBone(px, py, bone)) count++;
      }
      return count;
    });
  }

  private pointInBone(px: number, py: number, bone: BonePolygonItem): boolean {
    for (const poly of bone.polygons) {
      const rings = poly.rings || [{ points: poly.points }];
      if (rings.length > 0 && this.pointInPolygon(px, py, rings[0].points)) {
        let inHole = false;
        for (let r = 1; r < rings.length; r++) {
          if (this.pointInPolygon(px, py, rings[r].points)) {
            inHole = true;
            break;
          }
        }
        if (!inHole) return true;
      }
    }
    return false;
  }

  private pointInPolygon(px: number, py: number, pts: { x: number; y: number }[]): boolean {
    let inside = false;
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      const xi = pts[i].x, yi = pts[i].y;
      const xj = pts[j].x, yj = pts[j].y;
      if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) {
        inside = !inside;
      }
    }
    return inside;
  }

  loadOverlay(key: string, url: string): Promise<void> {
    if (this.overlayImages[key]) {
      this.redrawAll();
      return Promise.resolve();
    }
    const img = new window.Image();
    img.src = url;
    return img.decode().then(() => {
      this.overlayImages[key] = img;
      this.redrawAll();
    });
  }

  zoomIn() {
    this.displayZoom = Math.min(6, this.displayZoom * 1.15);
    this.computeLayout();
    this.redrawAll();
    this.updateZoomLabel();
  }

  zoomOut() {
    this.displayZoom = Math.max(0.15, this.displayZoom / 1.15);
    this.computeLayout();
    this.redrawAll();
    this.updateZoomLabel();
  }

  zoomReset() {
    this.applyFitWidth();
    this.redrawAll();
    this.updateZoomLabel();
  }

  private updateZoomLabel() {
    const el = document.getElementById("bmZoomLabel");
    if (el) el.textContent = `${Math.round(this.displayZoom * 100)}%`;
  }

  private pushUndo() {
    this.undoStack.push({
      frontBoxes: this.frontBoxes.map((b) => ({ ...b })),
      backBoxes: this.backBoxes.map((b) => ({ ...b })),
      frontSelected: this.front.selected,
      backSelected: this.back.selected,
    });
    if (this.undoStack.length > MAX_UNDO) this.undoStack.shift();
  }

  undo() {
    const snap = this.undoStack.pop();
    if (!snap) return;
    this.frontBoxes.length = 0;
    this.frontBoxes.push(...snap.frontBoxes);
    this.backBoxes.length = 0;
    this.backBoxes.push(...snap.backBoxes);
    this.front.selected = snap.frontSelected;
    this.back.selected = snap.backSelected;
    this.redrawAll();
    this.opts.onChange();
    this.status("已撤回");
  }

  private status(msg: string) {
    this.opts.onStatus?.(msg);
  }

  private state(view: ViewName) {
    return view === "front" ? this.front : this.back;
  }

  private boxesRef(view: ViewName): Box[] {
    return view === "front" ? this.frontBoxes : this.backBoxes;
  }

  private async loadAll() {
    for (const view of ["front", "back"] as ViewName[]) {
      const img = this.images[view];
      img.src = this.state(view).imageUrl;
      await img.decode();
    }
    this.applyFitWidth();
    this.redrawAll();
    this.status("就绪");
  }

  private computeLayout() {
    const f = this.images.front;
    const b = this.images.back;
    const z = this.displayZoom;
    const fw = (f.naturalWidth || 320) * z;
    const fh = (f.naturalHeight || 480) * z;
    const bw = (b.naturalWidth || 320) * z;
    const bh = (b.naturalHeight || 480) * z;
    const totalH = Math.max(fh, bh);

    this.front.layout = { ix: 0, iy: 0, iw: fw, ih: fh };
    const backX = fw + PAIR_GAP;
    this.back.layout = { ix: backX, iy: 0, iw: bw, ih: bh };

    if (!this.canvas) return;
    this.canvas.width = Math.round(backX + bw);
    this.canvas.height = Math.round(totalH);
    this.canvas.style.width = `${this.canvas.width}px`;
    this.canvas.style.height = "auto";
  }

  private applyFitWidth() {
    if (!this.canvas) return;
    const scrollEl = this.canvas.closest(".bm-views") as HTMLElement | null;
    const available = scrollEl?.clientWidth || this.canvas.parentElement?.clientWidth || 0;
    const f = this.images.front;
    const b = this.images.back;
    const baseW = (f.naturalWidth || 320) + PAIR_GAP + (b.naturalWidth || 320);
    if (!baseW || !available) {
      this.displayZoom = 1;
    } else {
      this.displayZoom = Math.max(0.15, (available - 4) / baseW);
    }
    this.computeLayout();
    this.updateZoomLabel();
  }

  private viewAtCanvasPx(px: number, py: number): ViewName | null {
    if (!this.canvas) return null;
    for (const view of ["front", "back"] as ViewName[]) {
      const L = this.state(view).layout;
      if (!L) continue;
      const yOff = (this.canvas.height - L.ih) / 2;
      if (px >= L.ix && px < L.ix + L.iw && py >= yOff && py < yOff + L.ih) return view;
    }
    return null;
  }

  private eventPixels(e: MouseEvent) {
    const c = this.canvas!;
    const rect = c.getBoundingClientRect();
    const scaleX = c.width / rect.width;
    const scaleY = c.height / rect.height;
    return {
      px: (e.clientX - rect.left) * scaleX,
      py: (e.clientY - rect.top) * scaleY,
    };
  }

  private yOff(L: ViewLayout) {
    return (this.canvas!.height - L.ih) / 2;
  }

  redrawAll() {
    const canvas = this.canvas;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = this.invertDisplay ? "#f2f6fb" : "#0f172a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (const view of ["front", "back"] as ViewName[]) {
      const st = this.state(view);
      const L = st.layout;
      if (!L) continue;
      const img = this.images[view];
      const yOff = this.yOff(L);

      ctx.save();
      ctx.beginPath();
      ctx.rect(L.ix, 0, L.iw, canvas.height);
      ctx.clip();
      const filters: string[] = [];
      if (this.invertDisplay) filters.push("invert(1)");
      if (this.wwBrightness !== 1.0) filters.push(`brightness(${this.wwBrightness})`);
      if (this.wwContrast !== 1.0) filters.push(`contrast(${this.wwContrast})`);
      ctx.filter = filters.length ? filters.join(" ") : "none";
      ctx.drawImage(img, L.ix, yOff, L.iw, L.ih);
      ctx.filter = "none";

      if (this.showBoneOverlay) {
        this.drawBonePolygons(ctx, view, L, yOff);
      }

      if (this.showLesionMask) {
        this.drawOverlayImage(ctx, `lesion_${view}`, L, yOff);
      }

      if (this.showBoxes) {
        this.drawBoxes(ctx, view, L, yOff, this.boxesRef(view), {
          stroke: st.color,
          selected: st.selected,
        });
      }

      if (this.drag?.mode === "draw" && this.drag.view === view) {
        const { x0, y0, x1, y1 } = this.drag;
        ctx.strokeStyle = "#16a34a";
        ctx.setLineDash([6, 4]);
        ctx.lineWidth = 2;
        ctx.strokeRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
        ctx.setLineDash([]);
      }
      ctx.restore();

      ctx.fillStyle = "rgba(15, 23, 42, 0.75)";
      ctx.fillRect(L.ix + 4, 4, 40, 18);
      ctx.fillStyle = "#f8fafc";
      ctx.font = "600 14px system-ui, sans-serif";
      ctx.fillText(view === "front" ? "正面" : "背面", L.ix + 8, 20);
    }

    if (this.front.layout && this.back.layout) {
      const gapX = this.front.layout.ix + this.front.layout.iw;
      ctx.fillStyle = this.invertDisplay ? "#e2e8f0" : "#1e293b";
      ctx.fillRect(gapX, 0, PAIR_GAP, canvas.height);
    }
  }

  private drawBoxes(
    ctx: CanvasRenderingContext2D,
    view: ViewName,
    L: ViewLayout,
    yOff: number,
    boxes: Box[],
    style: { stroke: string; selected: number | null }
  ) {
    const hovSet = new Set(this.hoveredBoxes.filter((h) => h.view === view).map((h) => h.idx));

    boxes.forEach((b, i) => {
      const x = L.ix + (b.cx - b.w / 2) * L.iw;
      const y = yOff + (b.cy - b.h / 2) * L.ih;
      const bw = b.w * L.iw;
      const bh = b.h * L.ih;
      const isSel = style.selected === i;
      const isHov = hovSet.has(i) && !isSel;
      const noSeg = b.seg_valid === false;

      const isPendingRemove = this.pendingRemove?.view === view && this.pendingRemove?.idx === i;
      const isRemoveHov = isHov && this.opMode === "remove" && !isPendingRemove;

      if (isPendingRemove) {
        ctx.fillStyle = "rgba(239, 68, 68, 0.3)";
        ctx.fillRect(x, y, bw, bh);
        ctx.save();
        ctx.shadowColor = "#ef4444";
        ctx.shadowBlur = 12;
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 3;
        ctx.setLineDash([6, 3]);
        ctx.strokeRect(x, y, bw, bh);
        ctx.setLineDash([]);
        ctx.restore();
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(x + 6, y + 6);
        ctx.lineTo(x + bw - 6, y + bh - 6);
        ctx.moveTo(x + bw - 6, y + 6);
        ctx.lineTo(x + 6, y + bh - 6);
        ctx.stroke();
      } else if (isRemoveHov) {
        ctx.fillStyle = "rgba(239, 68, 68, 0.12)";
        ctx.fillRect(x, y, bw, bh);
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
        ctx.strokeRect(x, y, bw, bh);
      } else if (isSel) {
        ctx.save();
        ctx.shadowColor = "#f97316";
        ctx.shadowBlur = 12;
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 5;
        ctx.setLineDash([]);
        ctx.strokeRect(x, y, bw, bh);
        ctx.restore();
        ctx.strokeStyle = "#f97316";
        ctx.lineWidth = 3;
        ctx.setLineDash([]);
        ctx.strokeRect(x, y, bw, bh);
      } else if (isHov) {
        ctx.save();
        ctx.shadowColor = "#60a5fa";
        ctx.shadowBlur = 8;
        ctx.strokeStyle = "#93c5fd";
        ctx.lineWidth = 3;
        ctx.setLineDash([]);
        ctx.strokeRect(x, y, bw, bh);
        ctx.restore();
        ctx.fillStyle = "rgba(96, 165, 250, 0.08)";
        ctx.fillRect(x, y, bw, bh);
      } else {
        ctx.strokeStyle = noSeg ? "#fbbf24" : style.stroke;
        ctx.lineWidth = 2;
        ctx.setLineDash(noSeg ? [6, 4] : []);
        ctx.strokeRect(x, y, bw, bh);
        ctx.setLineDash([]);
      }

      const label = b.lesion_id || `#${i + 1}`;
      const suffix = noSeg ? " ?" : "";
      ctx.font = "bold 13px system-ui, sans-serif";
      ctx.strokeStyle = "rgba(0,0,0,0.85)";
      ctx.lineWidth = 3;
      ctx.strokeText(label + suffix, x + 3, y + 15);
      ctx.fillStyle = isSel ? "#f97316" : isHov ? "#93c5fd" : noSeg ? "#fbbf24" : style.stroke;
      ctx.fillText(label + suffix, x + 3, y + 15);

      if (isSel && this.opMode === "move") {
        const hx = [x, x + bw / 2, x + bw];
        const hy = [y, y + bh / 2, y + bh];
        ctx.fillStyle = "#fff";
        ctx.strokeStyle = "#f97316";
        ctx.lineWidth = 2;
        for (const cx of hx) {
          for (const cy of hy) {
            if (cx === hx[1] && cy === hy[1]) continue;
            ctx.beginPath();
            ctx.arc(cx, cy, HANDLE_R, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
          }
        }
      }
    });
  }

  private drawBonePolygons(
    ctx: CanvasRenderingContext2D,
    view: ViewName,
    L: ViewLayout,
    yOff: number
  ) {
    const items = this.boneContours[view];
    if (!items?.length) return;
    const img = this.images[view];
    const natW = img.naturalWidth || 1;
    const natH = img.naturalHeight || 1;
    const sx = L.iw / natW;
    const sy = L.ih / natH;
    const selIdx = this.selectedBone?.view === view ? this.selectedBone.idx : -1;
    const hovNames = this.hoveredBoneNames;
    const selNames = this._selectedBoneNames;
    const fillAlpha = this.boneOpacity;
    const strokeAlpha = Math.min(0.95, fillAlpha + 0.35);

    for (let ii = 0; ii < items.length; ii++) {
      const item = items[ii];
      const isSel = ii === selIdx || (selNames.length > 0 && selNames.includes(item.name || ""));
      const isHov = !isSel && hovNames.length > 0 && hovNames.includes(item.name || "");
      const color = item.color;
      ctx.save();
      ctx.fillStyle = this.rgba(color, isSel ? Math.min(0.7, fillAlpha + 0.3) : isHov ? Math.min(0.6, fillAlpha + 0.2) : fillAlpha);
      ctx.strokeStyle = isSel ? "#ffffff" : isHov ? "#e0e7ff" : this.rgba(color, strokeAlpha);
      ctx.lineWidth = isSel ? 2.5 : isHov ? 2 : 1.2;
      for (const poly of item.polygons) {
        const rings = poly.rings || [{ points: poly.points }];
        ctx.beginPath();
        for (const ring of rings) {
          const pts = ring.points;
          if (pts.length < 3) continue;
          ctx.moveTo(L.ix + pts[0].x * sx, yOff + pts[0].y * sy);
          for (let i = 1; i < pts.length; i++) {
            ctx.lineTo(L.ix + pts[i].x * sx, yOff + pts[i].y * sy);
          }
          ctx.closePath();
        }
        ctx.fill("evenodd");
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  private rgba(hex: string, alpha: number): string {
    const raw = hex.replace("#", "");
    const v = parseInt(raw, 16);
    const r = (v >> 16) & 255;
    const g = (v >> 8) & 255;
    const b = v & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  private drawOverlayImage(
    ctx: CanvasRenderingContext2D,
    key: string,
    L: ViewLayout,
    yOff: number
  ) {
    const img = this.overlayImages[key];
    if (!img) return;
    ctx.drawImage(img, L.ix, yOff, L.iw, L.ih);
  }

  private hitTestBone(view: ViewName, px: number, py: number): number | null {
    const items = this.boneContours[view];
    if (!items?.length) return null;
    const L = this.state(view).layout;
    if (!L) return null;
    const img = this.images[view];
    const natW = img.naturalWidth || 1;
    const natH = img.naturalHeight || 1;
    const yOff = this.yOff(L);
    const imgPx = (px - L.ix) / L.iw * natW;
    const imgPy = (py - yOff) / L.ih * natH;
    for (let i = items.length - 1; i >= 0; i--) {
      if (this.pointInBone(imgPx, imgPy, items[i])) return i;
    }
    return null;
  }

  private hitTest(view: ViewName, px: number, py: number, boxes: Box[]): number | null {
    const L = this.state(view).layout!;
    const yOff = this.yOff(L);
    for (let i = boxes.length - 1; i >= 0; i--) {
      const b = boxes[i];
      const x = L.ix + (b.cx - b.w / 2) * L.iw;
      const y = yOff + (b.cy - b.h / 2) * L.ih;
      const bw = b.w * L.iw;
      const bh = b.h * L.ih;
      if (px >= x && px <= x + bw && py >= y && py <= y + bh) return i;
    }
    return null;
  }

  private hitTestEdge(view: ViewName, px: number, py: number, idx: number): ResizeEdge | null {
    const L = this.state(view).layout!;
    const yOff = this.yOff(L);
    const b = this.boxesRef(view)[idx];
    if (!b) return null;
    const x1 = L.ix + (b.cx - b.w / 2) * L.iw;
    const y1 = yOff + (b.cy - b.h / 2) * L.ih;
    const x2 = x1 + b.w * L.iw;
    const y2 = y1 + b.h * L.ih;

    const r = HANDLE_R + 3;
    const nearL = Math.abs(px - x1) <= r;
    const nearR = Math.abs(px - x2) <= r;
    const nearT = Math.abs(py - y1) <= r;
    const nearB = Math.abs(py - y2) <= r;

    if (nearT && nearL) return "nw";
    if (nearT && nearR) return "ne";
    if (nearB && nearL) return "sw";
    if (nearB && nearR) return "se";
    if (nearT && px > x1 && px < x2) return "n";
    if (nearB && px > x1 && px < x2) return "s";
    if (nearL && py > y1 && py < y2) return "w";
    if (nearR && py > y1 && py < y2) return "e";
    return null;
  }

  private onDown(e: MouseEvent) {
    const { px, py } = this.eventPixels(e);

    if (e.button === 2) {
      e.preventDefault();
      this.drag = { mode: "wl", startX: px, startY: py, startBri: this.wwBrightness, startCon: this.wwContrast };
      if (this.canvas) this.canvas.style.cursor = "move";
      return;
    }

    const view = this.viewAtCanvasPx(px, py);
    if (!view) return;
    this.activeView = view;
    const st = this.state(view);
    const boxes = this.boxesRef(view);

    if (this.opMode === "remove") {
      const hit = this.hitTest(view, px, py, boxes);
      if (hit !== null && this.pendingRemove?.view === view && this.pendingRemove?.idx === hit) {
        this.pushUndo();
        boxes.splice(hit, 1);
        st.selected = null;
        this.pendingRemove = null;
        this.hoveredBoxes = [];
        this.redrawAll();
        this.opts.onChange();
        this.opts.onSelectionChange?.();
        this.status(`已删除 ${view} #${hit + 1}`);
      } else if (hit !== null) {
        this.pendingRemove = { view, idx: hit };
        this.redrawAll();
        this.status(`再次点击确认删除 ${view === "front" ? "正面" : "背面"} #${hit + 1}`);
      } else {
        this.pendingRemove = null;
        this.redrawAll();
      }
      return;
    }

    if (this.opMode === "add") {
      st.selected = null;
      this.drag = { mode: "draw", view, x0: px, y0: py, x1: px, y1: py };
      this.redrawAll();
      return;
    }

    const hit = this.hitTest(view, px, py, boxes);

    if (this.opMode === "move") {
      const L = st.layout!;
      const yOff = this.yOff(L);
      if (st.selected !== null) {
        const edge = this.hitTestEdge(view, px, py, st.selected);
        if (edge) {
          this.pushUndo();
          const b = boxes[st.selected];
          const x1 = b.cx - b.w / 2;
          const y1 = b.cy - b.h / 2;
          const x2 = b.cx + b.w / 2;
          const y2 = b.cy + b.h / 2;
          const anchorX = edge.includes("w") ? x2 : edge.includes("e") ? x1 : b.cx;
          const anchorY = edge.includes("n") ? y2 : edge.includes("s") ? y1 : b.cy;
          this.drag = { mode: "resize", view, idx: st.selected, edge, anchorX, anchorY };
          if (this.canvas) this.canvas.style.cursor = EDGE_CURSORS[edge];
          this.redrawAll();
          return;
        }
      }
      if (hit !== null) {
        this.pushUndo();
        st.selected = hit;
        this.selectedBone = null;
        const b = boxes[hit];
        const bx = L.ix + (b.cx - b.w / 2) * L.iw;
        const by = yOff + (b.cy - b.h / 2) * L.ih;
        this.drag = { mode: "move", view, idx: hit, offX: px - bx, offY: py - by };
        if (this.canvas) this.canvas.style.cursor = "grabbing";
      }
      this.redrawAll();
      this.opts.onSelectionChange?.();
      return;
    }

    // Browse mode ("none"): click to select (+ paired counterpart)
    this.front.selected = null;
    this.back.selected = null;
    this.selectedBone = null;
    this._selectedBoneNames = [];

    if (hit !== null) {
      st.selected = hit;
      const lid = this.boxesRef(view)[hit].lesion_id;
      if (lid) {
        const otherView: ViewName = view === "front" ? "back" : "front";
        const pairIdx = this.boxesRef(otherView).findIndex((b) => b.lesion_id === lid);
        if (pairIdx >= 0) this.state(otherView).selected = pairIdx;
      }
    } else if (this.showBoneOverlay) {
      const boneHit = this.hitTestBone(view, px, py);
      if (boneHit !== null) {
        this.selectedBone = { view, idx: boneHit };
        const name = this.boneContours[view][boneHit]?.name;
        if (name) this._selectedBoneNames = [name];
      }
    }
    this.redrawAll();
    this.opts.onSelectionChange?.();
  }

  private onMove(e: MouseEvent) {
    const { px, py } = this.eventPixels(e);

    if (this.drag?.mode === "wl") {
      const dx = px - this.drag.startX;
      const dy = py - this.drag.startY;
      this.wwContrast = Math.max(0.2, Math.min(3.0, this.drag.startCon + dx * 0.005));
      this.wwBrightness = Math.max(0.2, Math.min(3.0, this.drag.startBri - dy * 0.005));
      this.status(`窗宽 ${(this.wwContrast * 100).toFixed(0)}% · 窗位 ${(this.wwBrightness * 100).toFixed(0)}%`);
      this.redrawAll();
      return;
    }

    // Handle active drags
    if (this.drag) {
      if (this.drag.mode === "draw") {
        this.drag.x1 = px;
        this.drag.y1 = py;
        this.redrawAll();
        return;
      }
      if (this.drag.mode === "resize") {
        const view = this.drag.view;
        const L = this.state(view).layout!;
        const yOff = this.yOff(L);
        const b = this.boxesRef(view)[this.drag.idx];
        const edge = this.drag.edge;
        const curX = (px - L.ix) / L.iw;
        const curY = (py - yOff) / L.ih;
        const ax = this.drag.anchorX;
        const ay = this.drag.anchorY;
        const MIN_DIM = 0.01;

        let x1 = edge.includes("w") ? curX : edge.includes("e") ? ax : ax - b.w / 2;
        let y1 = edge.includes("n") ? curY : edge.includes("s") ? ay : ay - b.h / 2;
        let x2 = edge.includes("e") ? curX : edge.includes("w") ? ax : ax + b.w / 2;
        let y2 = edge.includes("s") ? curY : edge.includes("n") ? ay : ay + b.h / 2;

        if (x2 - x1 < MIN_DIM) { if (edge.includes("w")) x1 = x2 - MIN_DIM; else x2 = x1 + MIN_DIM; }
        if (y2 - y1 < MIN_DIM) { if (edge.includes("n")) y1 = y2 - MIN_DIM; else y2 = y1 + MIN_DIM; }

        x1 = Math.max(0, x1); y1 = Math.max(0, y1);
        x2 = Math.min(1, x2); y2 = Math.min(1, y2);

        b.cx = (x1 + x2) / 2;
        b.cy = (y1 + y2) / 2;
        b.w = x2 - x1;
        b.h = y2 - y1;
        this.redrawAll();
        this.opts.onChange();
        return;
      }
      // "move" drag
      const view = this.drag.view;
      const L = this.state(view).layout!;
      const yOff = this.yOff(L);
      const b = this.boxesRef(view)[this.drag.idx];
      const x = px - this.drag.offX - L.ix;
      const y = py - this.drag.offY - yOff;
      b.cx = (x + b.w * L.iw * 0.5) / L.iw;
      b.cy = (y + b.h * L.ih * 0.5) / L.ih;
      b.cx = Math.max(b.w / 2, Math.min(1 - b.w / 2, b.cx));
      b.cy = Math.max(b.h / 2, Math.min(1 - b.h / 2, b.cy));
      this.redrawAll();
      this.opts.onChange();
      return;
    }

    if (this.opMode === "move" && this.canvas) {
      const view = this.viewAtCanvasPx(px, py);
      if (view) {
        const st = this.state(view);
        if (st.selected !== null) {
          const edge = this.hitTestEdge(view, px, py, st.selected);
          if (edge) {
            this.canvas.style.cursor = EDGE_CURSORS[edge];
            return;
          }
        }
        const hit = this.hitTest(view, px, py, this.boxesRef(view));
        this.canvas.style.cursor = hit !== null ? "grab" : "default";
      } else {
        this.canvas.style.cursor = "default";
      }
      return;
    }

    if (this.opMode === "remove" && this.canvas) {
      const view = this.viewAtCanvasPx(px, py);
      let newHov: { view: ViewName; idx: number }[] = [];
      if (view) {
        const hit = this.hitTest(view, px, py, this.boxesRef(view));
        this.canvas.style.cursor = hit !== null ? "pointer" : "default";
        if (hit !== null) newHov = [{ view, idx: hit }];
      } else {
        this.canvas.style.cursor = "default";
      }
      const key = newHov.map((h) => `${h.view}:${h.idx}`).join(",");
      const prevKey = this.hoveredBoxes.map((h) => `${h.view}:${h.idx}`).join(",");
      if (key !== prevKey) {
        this.hoveredBoxes = newHov;
        this.redrawAll();
      }
      return;
    }

    // Browse mode hover: highlight box or bone under cursor (+ paired counterpart)
    if (this.opMode === "none") {
      const view = this.viewAtCanvasPx(px, py);
      let newBoxes: { view: ViewName; idx: number }[] = [];
      let newBoneNames: string[] = [];

      if (view) {
        const boxHit = this.showBoxes ? this.hitTest(view, px, py, this.boxesRef(view)) : null;
        if (boxHit !== null) {
          newBoxes.push({ view, idx: boxHit });
          const lid = this.boxesRef(view)[boxHit].lesion_id;
          if (lid) {
            const otherView: ViewName = view === "front" ? "back" : "front";
            const otherBoxes = this.boxesRef(otherView);
            const pairIdx = otherBoxes.findIndex((b) => b.lesion_id === lid);
            if (pairIdx >= 0) newBoxes.push({ view: otherView, idx: pairIdx });
          }
        } else if (this.showBoneOverlay) {
          const boneHit = this.hitTestBone(view, px, py);
          if (boneHit !== null) {
            const name = this.boneContours[view][boneHit]?.name;
            if (name) newBoneNames = [name];
          }
        }
      }

      const boxKey = newBoxes.map((b) => `${b.view}:${b.idx}`).join(",");
      const prevBoxKey = this.hoveredBoxes.map((b) => `${b.view}:${b.idx}`).join(",");
      const boneKey = newBoneNames.join(",");
      const prevBoneKey = this.hoveredBoneNames.join(",");

      if (boxKey !== prevBoxKey || boneKey !== prevBoneKey) {
        this.hoveredBoxes = newBoxes;
        this.hoveredBoneNames = newBoneNames;
        if (this.canvas) this.canvas.style.cursor = newBoxes.length || newBoneNames.length ? "pointer" : "default";
        this.redrawAll();
        if (boxKey !== prevBoxKey) this.opts.onHoverChange?.(newBoxes, "box");
        if (boneKey !== prevBoneKey) {
          const boneItems: { view: ViewName; idx: number }[] = [];
          if (newBoneNames.length) {
            for (const v of ["front", "back"] as ViewName[]) {
              this.boneContours[v].forEach((item, i) => {
                if (newBoneNames.includes(item.name || "")) boneItems.push({ view: v, idx: i });
              });
            }
          }
          this.opts.onHoverChange?.(boneItems, "bone");
        }
      }
      return;
    }

    // Move mode hover feedback (no drag active)
    if (this.opMode === "move") {
      const view = this.viewAtCanvasPx(px, py);
      if (view && this.canvas) {
        const boxHit = this.hitTest(view, px, py, this.boxesRef(view));
        this.canvas.style.cursor = boxHit !== null ? "grab" : "default";
      }
    }
  }


  private onUp(_e: MouseEvent) {
    if (!this.drag) return;
    if (this.drag.mode === "wl") {
      this.drag = null;
      if (this.canvas) this.canvas.style.cursor = this.opMode === "move" ? "grab" : this.opMode === "add" ? "crosshair" : "default";
      return;
    }
    const view = this.drag.view;
    const L = this.state(view).layout!;

    if (this.drag.mode === "draw") {
      const x0 = Math.min(this.drag.x0, this.drag.x1);
      const y0 = Math.min(this.drag.y0, this.drag.y1);
      const x1 = Math.max(this.drag.x0, this.drag.x1);
      const y1 = Math.max(this.drag.y0, this.drag.y1);
      const yOff = this.yOff(L);
      const lx0 = x0 - L.ix;
      const ly0 = y0 - yOff;
      const lx1 = x1 - L.ix;
      const ly1 = y1 - yOff;
      if (lx1 - lx0 > 8 && ly1 - ly0 > 8) {
        this.pushUndo();
        this.boxesRef(view).push({
          cls: 0,
          cx: ((lx0 + lx1) / 2) / L.iw,
          cy: ((ly0 + ly1) / 2) / L.ih,
          w: (lx1 - lx0) / L.iw,
          h: (ly1 - ly0) / L.ih,
          conf: 1,
        });
        this.state(view).selected = this.boxesRef(view).length - 1;
        this.opts.onChange();
      }
    } else {
      this.opts.onChange();
    }
    this.drag = null;
    if (this.canvas && this.opMode === "move") this.canvas.style.cursor = "grab";
    this.redrawAll();
  }

  private static readonly OP_CYCLE: EditorOp[] = ["none", "move", "add", "remove"];

  private onKey(e: KeyboardEvent) {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
    const view = this.activeView;
    const st = this.state(view);
    if (e.key === "Tab") {
      e.preventDefault();
      const cycle = ReviewEditor.OP_CYCLE;
      const cur = cycle.indexOf(this.opMode);
      const next = cycle[(cur + 1) % cycle.length];
      this.setOp(next);
      return;
    }
    if (e.key === "a" || e.key === "A") {
      this.setOp("add");
      return;
    }
    if (e.key === "m" || e.key === "M") {
      this.setOp("move");
      return;
    }
    if (e.key === "r" || e.key === "R") {
      this.setOp("remove");
      return;
    }
    if (e.key === "b" || e.key === "B") {
      this.setShowBoxes(!this.showBoxes);
      const btn = document.getElementById("bmBtnBoxes");
      if (btn) btn.classList.toggle("active", this.showBoxes);
      return;
    }
    if (e.key === "g" || e.key === "G") {
      this.setShowBone(!this.showBoneOverlay);
      const btn = document.getElementById("bmBtnBone");
      if (btn) btn.classList.toggle("active", this.showBoneOverlay);
      return;
    }
    if (e.key === "c" || e.key === "C") {
      this.setShowLesionMask(!this.showLesionMask);
      const btn = document.getElementById("bmBtnContour");
      if (btn) btn.classList.toggle("active", this.showLesionMask);
      return;
    }
    if (e.key === "w" || e.key === "W") {
      this.wwBrightness = 1.0;
      this.wwContrast = 1.0;
      this.redrawAll();
      this.status("窗宽窗位已复位");
      return;
    }
    if (e.key === "Escape") {
      this.setOp("none");
      return;
    }
    if (e.key === "1" || e.key === "=") {
      this.zoomIn();
      return;
    }
    if (e.key === "2" || e.key === "-") {
      this.zoomOut();
      return;
    }
    if (e.key === "3" || e.key === "0") {
      this.zoomReset();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      document.getElementById("btnSave")?.click();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "z") {
      e.preventDefault();
      this.undo();
      return;
    }
    if ((e.key === "Delete" || e.key === "Backspace") && st.selected !== null) {
      this.pushUndo();
      this.boxesRef(view).splice(st.selected, 1);
      st.selected = null;
      this.redrawAll();
      this.opts.onChange();
    }
  }

  deleteSelected() {
    const view = this.activeView;
    const st = this.state(view);
    if (st.selected === null) return;
    this.pushUndo();
    this.boxesRef(view).splice(st.selected, 1);
    st.selected = null;
    this.redrawAll();
    this.opts.onChange();
  }
}

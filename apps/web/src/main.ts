import "./style.css";
import { $ } from "./helpers";
import { renderList } from "./caseListPage";
import { renderCase, resetEditorState } from "./reviewPage";

function parseRoute(): { page: "list" | "case"; uid?: string } {
  const parts = location.pathname.replace(/\/+$/, "").split("/").filter(Boolean);
  if (parts[0] === "cases" && parts[1]) {
    try {
      return { page: "case", uid: decodeURIComponent(parts[1]) };
    } catch {
      return { page: "case", uid: parts[1] };
    }
  }
  return { page: "list" };
}

function nav(path: string) {
  history.pushState(null, "", path);
  render();
}

async function render() {
  resetEditorState();
  const route = parseRoute();
  try {
    if (route.page === "case" && route.uid) {
      await renderCase(route.uid, nav);
    } else {
      await renderList(nav);
    }
  } catch (e) {
    $("#app").innerHTML = `<p style="padding:1rem;color:#c00">错误: ${e}</p><p>请先 <code>make setup-demo api worker</code></p>`;
  }
}

window.addEventListener("popstate", () => render());
render();

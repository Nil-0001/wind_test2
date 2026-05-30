export function openResultPage(state, kind, emptyFrame) {
  if (!state.result) return;
  const html = kind === "2d"
    ? (state.result.visualization_html || emptyFrame())
    : (state.result.stowage_3d_html || emptyFrame());
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener,noreferrer");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

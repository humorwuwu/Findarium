export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value >= 10 || index === 0 ? Math.round(value) : value.toFixed(1)} ${units[index]}`;
}

export function formatTime(
  ns: number | null | undefined,
  locale = "zh-CN",
): string {
  if (!ns) return "—";
  const date = new Date(ns / 1_000_000);
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  if (sameDay) {
    return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString(locale, {
    year: date.getFullYear() === now.getFullYear() ? undefined : "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function extensionLabel(ext: string): string {
  return ext.replace(".", "").toUpperCase() || "FILE";
}

export function extensionColor(ext: string): string {
  switch (ext) {
    case ".pdf":
      return "#ff453a";
    case ".docx":
      return "#0a84ff";
    case ".xlsx":
      return "#30d158";
    case ".pptx":
      return "#ff9f0a";
    case ".md":
    case ".markdown":
      return "#5e5ce6";
    case ".csv":
      return "#64d2ff";
    case ".html":
    case ".htm":
      return "#bf5af2";
    default:
      return "#8e8e93";
  }
}

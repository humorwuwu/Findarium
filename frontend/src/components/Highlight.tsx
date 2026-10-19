import type { ReactNode } from "react";

interface Props {
  text: string;
  spans: number[][];
}

export function Highlight({ text, spans }: Props) {
  if (!spans || spans.length === 0) return <>{text}</>;
  const sorted = [...spans].sort((a, b) => a[0] - b[0]);
  const parts: ReactNode[] = [];
  let cursor = 0;
  sorted.forEach(([start, end], index) => {
    if (start > cursor) parts.push(text.slice(cursor, start));
    if (end > start) parts.push(<mark key={index}>{text.slice(start, end)}</mark>);
    cursor = Math.max(cursor, end);
  });
  if (cursor < text.length) parts.push(text.slice(cursor));
  return <>{parts}</>;
}

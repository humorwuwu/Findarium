import { Loader2 } from "lucide-react";
import type { AppStatus } from "../types";

interface Props {
  status: AppStatus | null;
}

export function StatusBar({ status }: Props) {
  if (!status) {
    return (
      <div className="flex h-7 items-center gap-2 border-t border-[var(--border)] px-3 text-[11px] text-[var(--muted)]">
        正在连接本地服务…
      </div>
    );
  }
  const embeddingLabel =
    status.embedding_state === "ready"
      ? `语义 ${status.embedding_ready ?? 0}`
      : status.embedding_state === "loading"
        ? "语义模型加载中"
        : status.embedding_state === "failed"
          ? "语义不可用"
          : "语义已关闭";
  const busy = (status.pending ?? 0) > 0 || (status.running ?? 0) > 0 || status.indexing > 0;
  return (
    <div className="flex h-7 items-center gap-3 border-t border-[var(--border)] px-3 text-[11px] text-[var(--muted)]">
      {busy && <Loader2 size={12} className="spin" />}
      <span>{status.sources} 个目录</span>
      <span>{status.documents} 个文档</span>
      {status.indexing > 0 && <span>待索引 {status.indexing}</span>}
      {(status.pending ?? 0) > 0 && <span>队列 {status.pending}</span>}
      <span>{embeddingLabel}</span>
      {status.workers && (
        <span>
          并发 {status.workers.active}/{status.workers.desired}（上限 {status.workers.max}）
        </span>
      )}
      {status.load_ratio != null && <span>负载 {status.load_ratio.toFixed(2)}</span>}
      {status.encrypted > 0 && <span>加密 {status.encrypted}</span>}
      {status.failed > 0 && <span className="text-[var(--danger)]">失败 {status.failed}</span>}
      <span className="ml-auto mono truncate max-w-[420px]">
        {status.library.path ?? "索引库未初始化"}
      </span>
    </div>
  );
}

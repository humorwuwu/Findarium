import { useEffect, useState } from "react";
import { FolderOpen, RefreshCw, RotateCcw, ShieldCheck } from "lucide-react";
import { api, pickFolder } from "../api";
import type { AppStatus } from "../types";

interface Props {
  status: AppStatus;
  onRefresh: () => void;
}

export function SettingsPage({ status, onRefresh }: Props) {
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [errors, setErrors] = useState<{ jobs: unknown[]; documents: unknown[] } | null>(null);

  async function load() {
    setSettings(await api.settings());
    try {
      setErrors(await api.errors());
    } catch {
      setErrors(null);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save(key: string, value: string) {
    const next = await api.updateSettings({ [key]: value });
    setSettings(next);
    setMessage("已保存");
    setTimeout(() => setMessage(null), 1500);
  }

  async function relocate() {
    const path = await pickFolder();
    if (!path) return;
    if (!window.confirm(`将索引库迁移到：\n${path}\n\n迁移期间会暂停索引，确定继续？`)) return;
    await api.relocateLibrary(path);
    onRefresh();
  }

  const libraryPath = String(settings.library_path ?? status.library.path ?? "");

  return (
    <div className="mx-auto w-full max-w-[900px] space-y-5 p-6">
      <div className="text-[18px] font-semibold">设置</div>

      <div className="solid-panel p-4">
        <div className="section-title mb-3">索引库</div>
        <div className="mono mb-2 break-all text-[11.5px] text-[var(--muted)]">{libraryPath}</div>
        {status.library.fallback && (
          <div className="mb-2 rounded-lg bg-[rgba(255,149,0,0.12)] p-2 text-[11.5px] text-[#ff9500]">
            程序目录不可写，数据已回退到应用支持目录；可以在这里迁移到其他位置。
          </div>
        )}
        <div className="mb-3 text-[11.5px] text-[var(--muted)]">
          默认位置：程序所在目录下的 <span className="mono">FindariumData</span>
          {status.library.program_dir ? `（当前程序目录：${status.library.program_dir}）` : ""}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={relocate}>
            <FolderOpen size={14} />
            迁移索引库位置
          </button>
          <button
            className="btn"
            onClick={async () => {
              const result = await api.rebuild();
              setMessage(`已加入重建队列：${result.queued} 个文档`);
            }}
          >
            <RotateCcw size={14} />
            重建全部索引
          </button>
          <button className="btn" onClick={() => api.openPrivacySettings()}>
            <ShieldCheck size={14} />
            完全磁盘访问权限
          </button>
        </div>
      </div>

      <div className="solid-panel p-4">
        <div className="section-title mb-3">扫描与加密复查</div>
        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <div className="mb-1 text-[12px] text-[var(--muted)]">定时校对间隔（秒）</div>
            <input
              className="input"
              defaultValue={String(settings.scan_interval_seconds ?? 600)}
              onBlur={(event) => save("scan_interval_seconds", event.target.value)}
            />
          </label>
          <label className="block">
            <div className="mb-1 text-[12px] text-[var(--muted)]">加密文件复查间隔（秒）</div>
            <input
              className="input"
              defaultValue={String(settings.encrypted_recheck_seconds ?? 600)}
              onBlur={(event) => save("encrypted_recheck_seconds", event.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="solid-panel p-4">
        <div className="section-title mb-3">索引性能</div>
        <div className="mb-2 text-[12.5px] text-[var(--muted)]">
          并发 worker：{status.workers?.active ?? 0} / {status.workers?.desired ?? 0}
          （上限 {status.workers?.max ?? 1}） · 系统负载{" "}
          {(status.load_ratio ?? 0).toFixed(2)} · 进程 CPU{" "}
          {((status.process_cpu ?? 0) * 100).toFixed(0)}% · 向量批大小{" "}
          {status.embedding_batch ?? "—"}
        </div>
        <div className="text-[11.5px] leading-5 text-[var(--muted)]">
          空闲时自动提高提取并发；CPU 占用或系统负载升高时降回 1 个 worker，并缩小向量批大小，
          避免影响你正在使用的其他程序。
        </div>
      </div>

      <div className="solid-panel p-4">
        <div className="section-title mb-3">语义模型</div>
        <div className="mb-3 text-[12.5px] text-[var(--muted)]">
          模型：{status.embedding_model ?? "BAAI/bge-small-zh-v1.5"} · 状态：
          {status.embedding_state === "ready"
            ? "已就绪"
            : status.embedding_state === "loading"
              ? "加载中"
              : status.embedding_state === "failed"
                ? `失败（${status.embedding_error ?? "未知错误"}）`
                : "未启用"}
          {status.embedding_ready != null ? ` · 已向量化 ${status.embedding_ready} 个文档` : ""}
        </div>
        <button
          className="btn"
          onClick={async () => {
            const result = await api.retryModel();
            setMessage(`模型状态：${result.state}，重新排队 ${result.queued} 个文档`);
          }}
        >
          <RefreshCw size={14} />
          重试模型加载 / 重新排队
        </button>
      </div>

      {errors && (errors.jobs.length > 0 || errors.documents.length > 0) && (
        <div className="solid-panel p-4">
          <div className="section-title mb-3">索引问题</div>
          <div className="space-y-1 text-[11.5px] text-[var(--muted)]">
            {errors.jobs.slice(0, 10).map((job, index) => (
              <div key={index} className="mono truncate">
                {JSON.stringify(job)}
              </div>
            ))}
            {errors.documents.slice(0, 10).map((doc, index) => (
              <div key={`d${index}`} className="mono truncate">
                {JSON.stringify(doc)}
              </div>
            ))}
          </div>
        </div>
      )}

      {message && <div className="text-[12px] text-[var(--success)]">{message}</div>}
    </div>
  );
}

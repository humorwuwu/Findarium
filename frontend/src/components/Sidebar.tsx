import {
  Clock,
  FolderSearch,
  Lock,
  Search,
  Settings,
} from "lucide-react";

export type View = "search" | "recent" | "sources" | "encrypted" | "settings";

const ITEMS: { key: View; label: string; icon: typeof Search }[] = [
  { key: "search", label: "搜索", icon: Search },
  { key: "recent", label: "最近", icon: Clock },
  { key: "sources", label: "索引目录", icon: FolderSearch },
  { key: "encrypted", label: "加密文件", icon: Lock },
  { key: "settings", label: "设置", icon: Settings },
];

interface Props {
  view: View;
  onChange: (view: View) => void;
  encryptedCount: number;
}

export function Sidebar({ view, onChange, encryptedCount }: Props) {
  return (
    <aside className="flex w-[184px] shrink-0 flex-col gap-1 border-r border-[var(--border)] px-3 py-3">
      <div className="mb-3 flex items-center gap-2 px-2">
        <img src="/icon-64.png" alt="Findarium" className="h-7 w-7 rounded-lg" />
        <div className="text-[13px] font-semibold">寻册</div>
      </div>
      {ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <div
            key={item.key}
            className={`sidebar-item ${view === item.key ? "active" : ""}`}
            onClick={() => onChange(item.key)}
          >
            <Icon size={15} />
            <span className="flex-1">{item.label}</span>
            {item.key === "encrypted" && encryptedCount > 0 && (
              <span className="chip neutral !px-2 !py-0 text-[11px]">{encryptedCount}</span>
            )}
          </div>
        );
      })}
      <div className="mt-auto px-2 text-[11px] leading-5 text-[var(--muted)]">
        所有数据仅保存在本机
      </div>
    </aside>
  );
}

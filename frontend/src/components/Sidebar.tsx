import {
  Clock,
  FolderSearch,
  HelpCircle,
  Lock,
  Search,
  Settings,
} from "lucide-react";
import { useI18n } from "../i18n";

export type View = "search" | "recent" | "sources" | "encrypted" | "settings" | "help";

interface Props {
  view: View;
  onChange: (view: View) => void;
  encryptedCount: number;
}

export function Sidebar({ view, onChange, encryptedCount }: Props) {
  const { t } = useI18n();
  const items: { key: View; label: string; icon: typeof Search }[] = [
    { key: "search", label: t.nav.search, icon: Search },
    { key: "recent", label: t.nav.recent, icon: Clock },
    { key: "sources", label: t.nav.sources, icon: FolderSearch },
    { key: "encrypted", label: t.nav.encrypted, icon: Lock },
    { key: "settings", label: t.nav.settings, icon: Settings },
    { key: "help", label: t.nav.help, icon: HelpCircle },
  ];

  return (
    <aside className="flex w-[184px] shrink-0 flex-col gap-1 border-r border-[var(--border)] px-3 py-3">
      <div className="mb-3 flex items-center gap-2 px-2">
        <img src="/icon-64.png" alt="Findarium" className="h-7 w-7 rounded-lg" />
        <div className="text-[13px] font-semibold">{t.brand}</div>
      </div>
      {items.map((item) => {
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
        {t.nav.localOnly}
      </div>
    </aside>
  );
}

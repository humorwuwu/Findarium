import { CircleHelp } from "lucide-react";
import { useI18n } from "../i18n";

export function HelpPage() {
  const { t } = useI18n();

  return (
    <div className="mx-auto w-full max-w-[900px] space-y-5 p-6">
      <div>
        <div className="flex items-center gap-2 text-[18px] font-semibold">
          <CircleHelp size={18} />
          {t.help.title}
        </div>
        <div className="mt-1 text-[12px] text-[var(--muted)]">{t.help.subtitle}</div>
      </div>

      <section className="solid-panel p-4">
        <div className="section-title mb-3">{t.help.quickStart.title}</div>
        <ol className="ml-4 list-decimal space-y-1.5 text-[12.5px] leading-6">
          {t.help.quickStart.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>

      <section className="solid-panel p-4">
        <div className="section-title mb-2">{t.help.syntax.title}</div>
        <div className="mb-3 text-[12px] text-[var(--muted)]">{t.help.syntax.intro}</div>
        <div className="space-y-1.5">
          {t.help.syntax.rows.map((row) => (
            <div key={row.syntax} className="flex flex-wrap items-baseline gap-2 text-[12.5px]">
              <code className="mono rounded bg-[var(--accent-soft)] px-1.5 py-0.5 text-[11.5px] text-[var(--accent)]">
                {row.syntax}
              </code>
              <span className="text-[var(--muted)]">{row.meaning}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="solid-panel p-4">
        <div className="section-title mb-2">{t.help.encrypted.title}</div>
        <p className="text-[12.5px] leading-6 text-[var(--muted)]">{t.help.encrypted.body}</p>
      </section>

      <section className="solid-panel p-4">
        <div className="section-title mb-2">{t.help.performance.title}</div>
        <p className="text-[12.5px] leading-6 text-[var(--muted)]">{t.help.performance.body}</p>
      </section>

      <section className="solid-panel p-4">
        <div className="section-title mb-2">{t.help.privacy.title}</div>
        <p className="text-[12.5px] leading-6 text-[var(--muted)]">{t.help.privacy.body}</p>
      </section>

      <section className="solid-panel p-4">
        <div className="section-title mb-3">{t.help.faq.title}</div>
        <div className="space-y-3">
          {t.help.faq.items.map((item) => (
            <div key={item.q}>
              <div className="text-[12.5px] font-medium">{item.q}</div>
              <div className="mt-1 text-[12px] leading-6 text-[var(--muted)]">{item.a}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

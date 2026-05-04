import type { ReactNode } from "react";

export interface TabDef<T extends string> {
  id: T;
  label: string;
}

interface TabsProps<T extends string> {
  tabs: TabDef<T>[];
  active: T;
  onChange: (id: T) => void;
  children?: ReactNode;
}

export function Tabs<T extends string>({ tabs, active, onChange }: TabsProps<T>) {
  return (
    <div className="inline-flex rounded-xl border border-slate-200 bg-slate-100 p-1 dark:border-slate-800 dark:bg-slate-900">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className="tab"
          data-active={tab.id === active}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

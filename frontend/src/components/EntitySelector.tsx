import type { EntityState } from "../types";

interface EntitySelectorProps {
  label: string;
  entities: EntityState[];
  selected: string;
  onSelect: (id: string) => void;
  onAdd?: (name: string) => void;
  onRemove?: (id: string) => void;
  addPlaceholder?: string;
  addLabel?: string;
  allowRemove: boolean;
}

import { useState } from "react";

export function EntitySelector({
  label,
  entities,
  selected,
  onSelect,
  onAdd,
  onRemove,
  addPlaceholder,
  addLabel,
  allowRemove,
}: EntitySelectorProps) {
  const [name, setName] = useState("");
  const submit = () => {
    const trimmed = name.trim();
    if (!trimmed || !onAdd) return;
    onAdd(trimmed);
    setName("");
  };

  return (
    <div className="flex flex-col gap-2">
      <label className="input-label">{label}</label>
      <div className="flex flex-wrap items-center gap-2">
        <select
          className="select max-w-xs"
          value={selected}
          onChange={(e) => onSelect(e.target.value)}
        >
          {entities.map((e) => (
            <option key={e.id} value={e.id}>
              {e.id}
            </option>
          ))}
        </select>
        {allowRemove && onRemove && entities.length > 1 && (
          <button
            type="button"
            className="btn-secondary"
            onClick={() => onRemove(selected)}
            title={`Remove ${selected}`}
          >
            Remove
          </button>
        )}
      </div>
      {onAdd && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="input max-w-xs"
            placeholder={addPlaceholder ?? "New name"}
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
          />
          <button type="button" className="btn-primary" onClick={submit} disabled={!name.trim()}>
            {addLabel ?? "Add"}
          </button>
        </div>
      )}
    </div>
  );
}

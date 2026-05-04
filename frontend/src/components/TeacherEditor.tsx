import { useCallback } from "react";
import { useEditor } from "../state/editor";
import { CalendarGrid, type PaintChange } from "./CalendarGrid";
import { CsvUploader } from "./CsvUploader";
import { EntitySelector } from "./EntitySelector";
import { PaintControls } from "./PaintControls";
import { Tabs } from "./Tabs";

export function TeacherEditor() {
  const { state, dispatch, visibleTeachers, selectedTeacherEntity } = useEditor();

  const handlePaint = useCallback(
    (changes: PaintChange[]) => {
      if (!selectedTeacherEntity) return;
      dispatch({
        type: "paint_cells",
        kind: "teacher",
        id: selectedTeacherEntity.id,
        changes,
      });
    },
    [dispatch, selectedTeacherEntity],
  );

  return (
    <article className="card flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="card-title">Teachers</h2>
          <p className="muted">
            With multiple teachers, the optimizer assigns each block a host and a student is
            covered if they can attend any chosen block.
          </p>
        </div>
        <Tabs
          tabs={[
            { id: "manual", label: "Manual Input" },
            { id: "csv", label: "CSV Upload" },
          ]}
          active={state.teacherInputMode}
          onChange={(id) => dispatch({ type: "set_input_mode", kind: "teacher", mode: id })}
        />
      </div>

      {state.teacherInputMode === "csv" ? (
        <CsvUploader
          kind="teacher"
          csvText={state.teacherCsvText}
          csvName={state.teacherCsvName}
          onChange={(text, name) => dispatch({ type: "set_csv", kind: "teacher", text, name })}
          onClear={() =>
            dispatch({ type: "set_csv", kind: "teacher", text: "", name: "" })
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          <EntitySelector
            label="Editing availability for"
            entities={visibleTeachers}
            selected={state.selectedTeacher}
            onSelect={(id) => dispatch({ type: "select_teacher", id })}
            allowRemove={false}
          />
          {selectedTeacherEntity && (
            <>
              <PaintControls
                kind="teacher"
                mode={selectedTeacherEntity.mode}
                strength={state.paintStrength.teacher}
                onModeChange={(mode) =>
                  dispatch({
                    type: "set_teacher_mode",
                    id: selectedTeacherEntity.id,
                    mode,
                  })
                }
                onStrengthChange={(strength) =>
                  dispatch({
                    type: "set_paint_strength",
                    kind: "teacher",
                    strength,
                  })
                }
                onClear={() =>
                  dispatch({ type: "clear_teacher", id: selectedTeacherEntity.id })
                }
              />
              <CalendarGrid
                kind="teacher"
                settings={state.settings}
                entity={selectedTeacherEntity}
                paintStrength={state.paintStrength.teacher}
                onPaint={handlePaint}
              />
            </>
          )}
          <p className="muted text-xs">
            Tip: increase “Number of teachers” in the settings card above to add more hosts.
          </p>
        </div>
      )}
    </article>
  );
}

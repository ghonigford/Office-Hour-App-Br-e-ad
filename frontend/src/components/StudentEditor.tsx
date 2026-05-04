import { useCallback } from "react";
import { useEditor } from "../state/editor";
import { CalendarGrid, type PaintChange } from "./CalendarGrid";
import { CsvUploader } from "./CsvUploader";
import { EntitySelector } from "./EntitySelector";
import { PaintControls } from "./PaintControls";
import { Tabs } from "./Tabs";

export function StudentEditor() {
  const { state, dispatch, selectedStudentEntity } = useEditor();

  const handlePaint = useCallback(
    (changes: PaintChange[]) => {
      if (!selectedStudentEntity) return;
      dispatch({
        type: "paint_cells",
        kind: "student",
        id: selectedStudentEntity.id,
        changes,
      });
    },
    [dispatch, selectedStudentEntity],
  );

  return (
    <article className="card flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="card-title">Students</h2>
          <p className="muted">
            Provide student availability by clicking on the grid below or uploading a CSV.
          </p>
        </div>
        <Tabs
          tabs={[
            { id: "manual", label: "Manual Input" },
            { id: "csv", label: "CSV Upload" },
          ]}
          active={state.studentInputMode}
          onChange={(id) => dispatch({ type: "set_input_mode", kind: "student", mode: id })}
        />
      </div>

      {state.studentInputMode === "csv" ? (
        <CsvUploader
          kind="student"
          csvText={state.studentCsvText}
          csvName={state.studentCsvName}
          onChange={(text, name) => dispatch({ type: "set_csv", kind: "student", text, name })}
          onClear={() =>
            dispatch({ type: "set_csv", kind: "student", text: "", name: "" })
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          <EntitySelector
            label="Editing availability for"
            entities={state.students}
            selected={state.selectedStudent}
            onSelect={(id) => dispatch({ type: "select_student", id })}
            onAdd={(id) => dispatch({ type: "add_student", id })}
            onRemove={(id) => dispatch({ type: "remove_student", id })}
            addPlaceholder="e.g. s1 or Alice"
            addLabel="Add student"
            allowRemove
          />
          {selectedStudentEntity && (
            <>
              <PaintControls
                kind="student"
                mode={selectedStudentEntity.mode}
                strength={state.paintStrength.student}
                onModeChange={(mode) =>
                  dispatch({
                    type: "set_student_mode",
                    id: selectedStudentEntity.id,
                    mode,
                  })
                }
                onStrengthChange={(strength) =>
                  dispatch({
                    type: "set_paint_strength",
                    kind: "student",
                    strength,
                  })
                }
                onClear={() =>
                  dispatch({ type: "clear_student", id: selectedStudentEntity.id })
                }
              />
              <CalendarGrid
                kind="student"
                settings={state.settings}
                entity={selectedStudentEntity}
                paintStrength={state.paintStrength.student}
                onPaint={handlePaint}
              />
            </>
          )}
        </div>
      )}
    </article>
  );
}

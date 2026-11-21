import { useReducer } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "cn";
import {
  canAdvanceFromStep,
  createFieldWizardReducer,
  initialWizardState,
  type WizardStep,
} from "./createFieldWizardState";
import BoundaryStep from "./steps/BoundaryStep";
import NameStep from "./steps/NameStep";

const STEPS: ReadonlyArray<{ step: WizardStep; label: string }> = [
  { step: 1, label: "Name" },
  { step: 2, label: "Boundary" },
  { step: 3, label: "Sowing" },
  { step: 4, label: "Confirm" },
];

export default function CreateFieldWizard() {
  const [state, dispatch] = useReducer(
    createFieldWizardReducer,
    initialWizardState,
  );

  const canGoNext = canAdvanceFromStep(state, state.step);

  return (
    <section className="mx-auto max-w-4xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-primary">Create New Field</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Set up a new winter wheat field in four steps.
        </p>
      </div>

      <nav aria-label="Wizard steps" className="mb-6">
        <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {STEPS.map(({ step, label }) => {
            const isCurrent = state.step === step;
            const isCompleted = state.step > step;

            return (
              <li key={step}>
                <button
                  type="button"
                  aria-current={isCurrent ? "step" : undefined}
                  onClick={() => dispatch({ type: "GO_TO_STEP", step })}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-lg border px-3 py-2.5 text-left text-sm transition-colors",
                    isCurrent &&
                      "border-primary bg-primary/10 font-semibold text-primary",
                    isCompleted &&
                      !isCurrent &&
                      "border-border bg-muted/60 font-medium text-foreground hover:bg-muted",
                    !isCurrent &&
                      !isCompleted &&
                      "border-border bg-background text-muted-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                      isCurrent &&
                        "border-primary bg-primary text-primary-foreground",
                      isCompleted &&
                        !isCurrent &&
                        "border-primary/40 bg-primary/15 text-primary",
                      !isCurrent && !isCompleted && "border-border",
                    )}
                  >
                    {step}
                  </span>
                  <span className="truncate">{label}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <Card>
        {state.step === 1 && (
          <NameStep
            name={state.name}
            onChange={(name) => dispatch({ type: "SET_NAME", name })}
          />
        )}

        {state.step === 2 && (
          <BoundaryStep
            geometry={state.geometry}
            outsideDenmark={state.outsideDenmark}
            onChange={(geometry) =>
              dispatch({ type: "SET_GEOMETRY", geometry })
            }
          />
        )}

        {state.step === 3 && (
          <>
            <CardHeader>
              <CardTitle>Step 3: Sowing</CardTitle>
              <CardDescription>
                Placeholder for the sowing date or sowing window step (S5-36).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Sowing date or window selection will be added here.
              </p>
            </CardContent>
          </>
        )}

        {state.step === 4 && (
          <>
            <CardHeader>
              <CardTitle>Step 4: Confirm</CardTitle>
              <CardDescription>
                Placeholder for confirmation and simulation launch (S5-36).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Review and submit placeholder for field{" "}
                <span className="font-medium text-foreground">
                  {state.name.trim() || "Untitled"}
                </span>
                .
              </p>
            </CardContent>
          </>
        )}

        <CardFooter className="justify-between gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={state.step === 1}
            onClick={() => dispatch({ type: "PREV_STEP" })}
          >
            Back
          </Button>
          <Button
            type="button"
            disabled={!canGoNext}
            onClick={() => dispatch({ type: "NEXT_STEP" })}
          >
            Next
          </Button>
        </CardFooter>
      </Card>
    </section>
  );
}

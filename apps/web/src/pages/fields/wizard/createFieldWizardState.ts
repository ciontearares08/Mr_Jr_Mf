import type { Polygon as GeoJSONPolygon } from "geojson";
import type { components } from "@/shared/api-types";
import { isBoundaryValid } from "../validations/boundaryValidation";
import { isInsideDenmark } from "../validations/denmarkAreaValidation";

export type WizardStep = 1 | 2 | 3 | 4;

type SowingWindow = components["schemas"]["SowingWindow"];

export interface CreateFieldWizardState {
  step: WizardStep;
  name: string;
  geometry: GeoJSONPolygon | null;
  outsideDenmark: boolean; //returns true when field is outside of DK (*** after next is pressed)
  sowingDate: string | null;
  sowingWindow: SowingWindow | null;
}

export type CreateFieldWizardAction =
  | { type: "SET_NAME"; name: string }
  | { type: "SET_GEOMETRY"; geometry: GeoJSONPolygon | null }
  | {
      type: "SET_SOWING";
      sowingDate: string | null;
      sowingWindow: SowingWindow | null;
    }
  | { type: "NEXT_STEP" }
  | { type: "PREV_STEP" }
  | { type: "GO_TO_STEP"; step: WizardStep };

export const initialWizardState: CreateFieldWizardState = {
  step: 1,
  name: "",
  geometry: null,
  outsideDenmark: false,
  sowingDate: null,
  sowingWindow: null,
};

// function to check if the name has valid characters and is of length <=50
export function isNameStepValid(name: string): boolean {
  const trimmed = name.trim();
  return trimmed.length >= 1 && trimmed.length <= 50;
}

/* function to check if there exists a valid input to be able to go to the next step
returns false if not returns the check which advances to next step. */
export function canAdvanceFromStep(
  state: CreateFieldWizardState,
  step: WizardStep = state.step,
): boolean {
  if (step === 1) {
    return isNameStepValid(state.name);
  }
  if (step === 2) {
    return isBoundaryValid(state.geometry) && !state.outsideDenmark;
  }
  return false;
}

// helper function for canReachStep (may put in separate file later)
function isStepComplete(
  state: CreateFieldWizardState,
  step: WizardStep,
): boolean {
  if (step === 2) {
    return (
      canAdvanceFromStep(state, 2) &&
      state.geometry !== null &&
      isInsideDenmark(state.geometry)
    );
  }
  return canAdvanceFromStep(state, step);
}

// return true when every step before the "target" is complete, allows the user to jump to it.
export function canReachStep(
  state: CreateFieldWizardState,
  target: WizardStep = state.step,
): boolean {
  for (let step = 1; step < target; step++) {
    if (!isStepComplete(state, step as WizardStep)) {
      return false;
    }
  }
  return true;
}

/* Called when the user tries to leave step 2. Returns the state with the
  outside-Denmark error set when the field is outside Denmark, otherwise null. */
function rejectOutsideDenmark(
  state: CreateFieldWizardState,
): CreateFieldWizardState | null {
  if (
    state.step === 2 &&
    state.geometry !== null &&
    isBoundaryValid(state.geometry) &&
    !isInsideDenmark(state.geometry)
  ) {
    return { ...state, outsideDenmark: true };
  }
  return null;
}

// function that helps create the field
export function createFieldWizardReducer(
  state: CreateFieldWizardState,
  action: CreateFieldWizardAction,
): CreateFieldWizardState {
  switch (action.type) {
    case "SET_NAME":
      return {
        ...state,
        name: action.name,
      };
    case "SET_GEOMETRY":
      return {
        ...state,
        geometry: action.geometry,
        outsideDenmark: false,
      };
    case "SET_SOWING":
      return {
        ...state,
        sowingDate: action.sowingDate,
        sowingWindow: action.sowingWindow,
      };
    case "NEXT_STEP": {
      if (state.step >= 4 || !canAdvanceFromStep(state, state.step)) {
        return state;
      }
      const rejected = rejectOutsideDenmark(state);
      if (rejected) {
        return rejected;
      }
      return {
        ...state,
        step: (state.step + 1) as WizardStep,
      };
    }
    case "PREV_STEP": {
      if (state.step <= 1) {
        return state;
      }
      return {
        ...state,
        step: (state.step - 1) as WizardStep,
      };
    }
    case "GO_TO_STEP": {
      if (canReachStep(state, action.step)) {
        return {
          ...state,
          step: action.step,
        };
      }
      return rejectOutsideDenmark(state) ?? state;
    }
    default:
      return state;
  }
}

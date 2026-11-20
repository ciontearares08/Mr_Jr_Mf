import type { Polygon as GeoJSONPolygon } from "geojson";
import type { components } from "@/shared/api-types";

export type WizardStep = 1 | 2 | 3 | 4;

type SowingWindow = components["schemas"]["SowingWindow"];

export interface CreateFieldWizardState {
  step: WizardStep;
  name: string;
  geometry: GeoJSONPolygon | null;
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
  sowingDate: null,
  sowingWindow: null,
};

export function isNameStepValid(name: string): boolean {
  const trimmed = name.trim();
  return trimmed.length >= 1 && trimmed.length <= 50;
}

export function canAdvanceFromStep(
  state: CreateFieldWizardState,
  step: WizardStep = state.step,
): boolean {
  if (step === 1) {
    return isNameStepValid(state.name);
  }
  return false;
}

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
      if (action.step === state.step) {
        return state;
      }
      if (action.step < state.step) {
        return {
          ...state,
          step: action.step,
        };
      }
      if (action.step === 2 && isNameStepValid(state.name)) {
        return {
          ...state,
          step: 2,
        };
      }
      return state;
    }
    default:
      return state;
  }
}

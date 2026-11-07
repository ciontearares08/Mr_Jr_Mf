import type { components } from "@/shared/api-types";
import { API_URL } from "./config";

// Generated from the API, run `make api-types` after a backend schema change
type Schemas = components["schemas"];
export type Overview = Schemas["Overview"];
export type Timeline = Schemas["Timeline"];
export type TimelineStage = Schemas["TimelineStage"];
export type TimelineDetails = Schemas["TimelineDetails"];
export type FloatRange = Schemas["FloatRange"];
export type DateRange = Schemas["DateRange"];
export type Rating = Schemas["Rating"];

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) {
    throw new Error(`HTTP error! Status: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

// Stub endpoints until S4-01/S4-02, then only these paths change to /fields/{id}/...
export function getOverview(): Promise<Overview> {
  return getJson<Overview>("/stub/overview");
}

export function getTimeline(): Promise<Timeline> {
  return getJson<Timeline>("/stub/timeline");
}

// Daily rows for the detailed table, fetch only when the table is opened
export function getTimelineDetails(): Promise<TimelineDetails> {
  return getJson<TimelineDetails>("/stub/timeline/details");
}

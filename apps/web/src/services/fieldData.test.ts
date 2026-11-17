import { afterEach, describe, expect, it, vi } from "vitest";

import { API_URL } from "./config";
import { getOverview } from "./fieldData";

function answerWith(response: Partial<Response>) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getOverview", () => {
  it("returns the JSON body of the overview route", async () => {
    const body = { as_of: "2025-06-15" };
    const fetchMock = answerWith({ ok: true, json: async () => body });

    await expect(getOverview()).resolves.toEqual(body);
    expect(fetchMock).toHaveBeenCalledWith(`${API_URL}/stub/overview`);
  });

  it("throws with the status when the API answers with an error", async () => {
    answerWith({ ok: false, status: 503 });

    await expect(getOverview()).rejects.toThrow("503");
  });
});

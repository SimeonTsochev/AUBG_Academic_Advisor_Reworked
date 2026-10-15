import { describe, expect, it } from "vitest";
import { describeRequestError } from "./requestErrors";

describe("describeRequestError", () => {
  it("says the service is unreachable instead of the browser's fetch error", () => {
    const sentence = "The planning service could not be reached. Check your connection and try again.";
    expect(describeRequestError(new Error("POST /plan/generate failed: Failed to fetch"), "x")).toBe(sentence);
    expect(describeRequestError(new TypeError("Failed to fetch"), "x")).toBe(sentence);
    expect(describeRequestError(new TypeError("NetworkError when attempting to fetch resource."), "x")).toBe(sentence);
  });

  it("keeps the server's reason without the request prefix", () => {
    expect(
      describeRequestError(new Error("POST /plan/generate failed (400 Bad Request): Unknown major: Basket Weaving"), "x")
    ).toBe("Unknown major: Basket Weaving");
    expect(describeRequestError(new Error("POST /plan/generate failed (500 Internal Server Error)"), "Fallback.")).toBe(
      "Fallback."
    );
    expect(describeRequestError(undefined, "Fallback.")).toBe("Fallback.");
  });
});

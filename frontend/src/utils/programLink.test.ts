import { describe, expect, it } from "vitest";
import { NO_PROGRAM_LINK, readProgramLink } from "./programLink";

const MAJORS = ["Computer Science", "Economics", "Mathematics"];
const MINORS = ["Computer Science", "Finance", "Economics"];

describe("readProgramLink", () => {
  it("returns the shared empty link when nothing is requested", () => {
    expect(readProgramLink("", MAJORS, MINORS)).toBe(NO_PROGRAM_LINK);
    expect(readProgramLink("?utm_source=x", MAJORS, MINORS)).toBe(NO_PROGRAM_LINK);
  });

  it("matches encoded names case-insensitively and returns the catalog spelling", () => {
    expect(readProgramLink("?major=computer%20science&minor=FINANCE", MAJORS, MINORS)).toEqual({
      majors: ["Computer Science"],
      minors: ["Finance"],
    });
  });

  it("ignores programs the catalog does not offer", () => {
    expect(readProgramLink("?major=Alchemy", MAJORS, MINORS)).toBe(NO_PROGRAM_LINK);
  });

  it("drops a minor that is already a linked major", () => {
    expect(readProgramLink("?major=Economics&minor=Economics", MAJORS, MINORS)).toEqual({
      majors: ["Economics"],
      minors: [],
    });
  });

  it("keeps at most two programs of each type, without duplicates", () => {
    const link = readProgramLink(
      "?major=Economics&major=Economics&major=Mathematics&major=Computer%20Science",
      MAJORS,
      MINORS,
    );
    expect(link.majors).toEqual(["Economics", "Mathematics"]);
  });
});

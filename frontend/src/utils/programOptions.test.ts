import { describe, expect, it } from "vitest";
import type { ProgramInfo } from "../api";
import { majorsMissingRequiredOption, normalizeProgramOptions, toggleProgramOption } from "./programOptions";

const INFO: Record<string, ProgramInfo> = {
  "European Studies": {
    diploma: "dual",
    options: {
      label: "Language (B1)",
      required: true,
      multiple: false,
      choices: ["French", "German", "Spanish", "Bulgarian", "Waived (B1 certificate)"],
    },
  },
  "Computer Science": {
    diploma: "dual",
    options: {
      label: "Concentration",
      required: false,
      multiple: true,
      choices: ["Foundations of Computing", "Software Development"],
    },
  },
  Psychology: { diploma: "single" },
};

describe("normalizeProgramOptions", () => {
  it("keeps valid choices for selected majors only", () => {
    const raw = {
      "European Studies": ["French", "German", "Klingon"],
      "Computer Science": ["Software Development", "Software Development", 7],
      Psychology: ["Anything"],
      Economics: ["French"],
    };
    expect(normalizeProgramOptions(raw, ["European Studies", "Computer Science", "Psychology"], INFO)).toEqual({
      "European Studies": ["French"],
      "Computer Science": ["Software Development"],
    });
  });

  it("drops options for majors that are no longer selected and ignores junk", () => {
    expect(normalizeProgramOptions({ "European Studies": ["French"] }, ["Psychology"], INFO)).toEqual({});
    expect(normalizeProgramOptions(null, ["European Studies"], INFO)).toEqual({});
    expect(normalizeProgramOptions(["French"], ["European Studies"], INFO)).toEqual({});
  });
});

describe("majorsMissingRequiredOption", () => {
  it("lists only required options without a choice", () => {
    const majors = ["European Studies", "Computer Science"];
    expect(majorsMissingRequiredOption(majors, INFO, {})).toEqual(["European Studies"]);
    expect(majorsMissingRequiredOption(majors, INFO, { "European Studies": ["Waived (B1 certificate)"] })).toEqual([]);
  });
});

describe("toggleProgramOption", () => {
  it("replaces a single choice and toggles multiple ones", () => {
    let selection = toggleProgramOption({}, "European Studies", "French", false);
    selection = toggleProgramOption(selection, "European Studies", "German", false);
    expect(selection["European Studies"]).toEqual(["German"]);

    selection = toggleProgramOption(selection, "Computer Science", "Foundations of Computing", true);
    selection = toggleProgramOption(selection, "Computer Science", "Software Development", true);
    expect(selection["Computer Science"]).toEqual(["Foundations of Computing", "Software Development"]);
    selection = toggleProgramOption(selection, "Computer Science", "Foundations of Computing", true);
    selection = toggleProgramOption(selection, "Computer Science", "Software Development", true);
    expect(selection).toEqual({ "European Studies": ["German"] });
  });
});

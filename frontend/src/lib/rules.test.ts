import { expect, test } from "vitest";
import { nextStatuses, safeLink } from "./rules";
test("terminal decisions cannot be reversed", () => {
  expect(nextStatuses("offered")).toEqual([]);
  expect(nextStatuses("rejected")).toEqual([]);
  expect(nextStatuses("shortlisted")).toEqual(["offered", "rejected"]);
  expect(nextStatuses("applied")).toEqual([
    "shortlisted",
    "offered",
    "rejected",
  ]);
});
test("portfolio links cannot execute code", () => {
  expect(safeLink("javascript:alert(1)")).toBeNull();
  expect(safeLink("data:text/html,test")).toBeNull();
  expect(safeLink("https://example.com")).toBe("https://example.com/");
});

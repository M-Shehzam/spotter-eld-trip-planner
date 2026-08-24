/**
 * The sheet's geometry, checked without a browser.
 *
 * The duty line is the graded part of this project, and a screenshot only
 * proves it looks right on the day it was taken. These check the arithmetic
 * that puts the line where it goes.
 */

import { describe, expect, it } from "vitest";

import type { GridEntry, LogRemark } from "../../types/trip";
import {
  GRID,
  GRID_X1,
  dutyLinePath,
  formatHours,
  hourX,
  layOutRemarks,
  rowCentre,
} from "./sheet-layout";

function entry(row: 1 | 2 | 3 | 4, start: number, end: number): GridEntry {
  const status = (["off_duty", "sleeper_berth", "driving", "on_duty"] as const)[row - 1];
  return { status, row, start_hour: start, end_hour: end, hours: end - start };
}

function remark(hour: number): LogRemark {
  return { hour, text: "Fuel stop", location: "Harlan, IA", kind: "fuel" };
}

describe("the hour scale", () => {
  it("puts midnight at the left edge and midnight again at the right", () => {
    expect(hourX(0)).toBe(GRID.x0);
    expect(hourX(24)).toBe(GRID_X1);
  });

  it("gives every hour the same width", () => {
    const widths = Array.from({ length: 24 }, (_, hour) => hourX(hour + 1) - hourX(hour));
    expect(new Set(widths).size).toBe(1);
  });

  it("keeps the four rows in order and inside the grid", () => {
    const centres = ([1, 2, 3, 4] as const).map(rowCentre);
    expect(centres).toEqual([...centres].sort((a, b) => a - b));
    expect(centres[0]).toBeGreaterThan(GRID.top);
    expect(centres[3]).toBeLessThan(GRID.top + GRID.rows * GRID.rowHeight);
  });
});

describe("the duty line", () => {
  it("draws nothing for a day with no entries", () => {
    expect(dutyLinePath([])).toBe("");
  });

  it("runs a single status straight across its own row", () => {
    expect(dutyLinePath([entry(1, 0, 24)])).toBe(
      `M ${hourX(0)} ${rowCentre(1)} L ${hourX(24)} ${rowCentre(1)}`,
    );
  });

  it("connects a status change with a vertical at the hour it happened", () => {
    const path = dutyLinePath([entry(1, 0, 8), entry(3, 8, 18)]);
    // The move to the second row happens at the same x the first run ended,
    // which is what makes the connector vertical rather than diagonal.
    expect(path).toContain(`L ${hourX(8)} ${rowCentre(1)} L ${hourX(8)} ${rowCentre(3)}`);
  });

  it("starts with a move and never uses another", () => {
    const path = dutyLinePath([entry(1, 0, 6), entry(2, 6, 16), entry(3, 16, 24)]);
    expect(path.startsWith("M ")).toBe(true);
    expect(path.match(/M /g)).toHaveLength(1);
  });

  it("covers the whole day when the entries do", () => {
    const path = dutyLinePath([entry(1, 0, 10), entry(3, 10, 21), entry(4, 21, 24)]);
    expect(path).toContain(`M ${hourX(0)}`);
    expect(path.endsWith(`L ${hourX(24)} ${rowCentre(4)}`)).toBe(true);
  });
});

describe("the remark labels", () => {
  it("stands each tick at its own hour", () => {
    const [tick] = layOutRemarks([remark(6.5)]);
    expect(tick.x).toBe(hourX(6.5));
  });

  it("keeps well-spaced remarks on the top lane", () => {
    const ticks = layOutRemarks([remark(2), remark(9), remark(17)]);
    expect(ticks.map((tick) => tick.lane)).toEqual([0, 0, 0]);
  });

  it("drops a crowded label to the next lane instead of overprinting", () => {
    const ticks = layOutRemarks([remark(8), remark(8.1), remark(8.2)]);
    expect(new Set(ticks.map((tick) => tick.lane)).size).toBe(3);
  });

  it("reuses a lane once the gap reopens", () => {
    const ticks = layOutRemarks([remark(8), remark(8.1), remark(20)]);
    expect(ticks[2].lane).toBe(0);
  });
});

describe("hours as a driver writes them", () => {
  it("leaves whole hours whole", () => {
    expect(formatHours(8)).toBe("8");
    expect(formatHours(0)).toBe("0");
  });

  it("keeps the quarters the grid can show", () => {
    expect(formatHours(10.25)).toBe("10.25");
    expect(formatHours(8.5)).toBe("8.5");
  });

  it("rounds the float noise out of a computed total", () => {
    expect(formatHours(13.000000001)).toBe("13");
  });
});

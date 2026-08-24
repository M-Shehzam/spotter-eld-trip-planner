/**
 * Where every line on the sheet goes.
 *
 * The proportions come from the blank form the assessment ships,
 * `blank-paper-log.png`, redrawn at a size that stays sharp on a screen and
 * on paper. The numbers live apart from the drawing so they can be checked on
 * their own, and so the PNG export can size a canvas without importing React.
 *
 * One rule holds the sheet together: every x position on it comes from
 * `hourX`. The grid, the hour labels above it and the remark ticks below it
 * all share that scale, which is what makes a tick at 14:30 line up with the
 * duty line above it.
 */

import type { GridEntry, LogRemark } from "../../types/trip";

export const SHEET = { width: 1010, height: 780, margin: 24 } as const;

export const GRID = {
  x0: 132,
  hourWidth: 32,
  hours: 24,
  /** The black strip carrying the hour numbers. It reaches back past the
   *  first hour line, because the word centred on midnight is wider than the
   *  numerals and would otherwise be cut in half by the left edge. */
  headerOverhang: 26,
  headerTop: 248,
  headerHeight: 26,
  /** Top of the first duty row. */
  top: 274,
  rowHeight: 27,
  rows: 4,
} as const;

export const GRID_X1 = GRID.x0 + GRID.hours * GRID.hourWidth;
export const GRID_BOTTOM = GRID.top + GRID.rows * GRID.rowHeight;
/** The right edge, shared by the totals column and every full-width rule. */
export const SHEET_X1 = SHEET.width - SHEET.margin;

export const REMARKS = {
  top: GRID_BOTTOM + 14,
  height: 122,
  /** The rule the ticks stand on, and the baseline the labels hang from. */
  ruleY: GRID_BOTTOM + 46,
} as const;

export function hourX(hour: number): number {
  return GRID.x0 + hour * GRID.hourWidth;
}

export function rowTop(row: 1 | 2 | 3 | 4): number {
  return GRID.top + (row - 1) * GRID.rowHeight;
}

export function rowCentre(row: 1 | 2 | 3 | 4): number {
  return GRID.top + (row - 0.5) * GRID.rowHeight;
}

/**
 * The duty line as a single path.
 *
 * One path rather than a line per row, for two reasons. The vertical
 * connector at a status change is the same continuous stroke as the
 * horizontal run, which is how a driver draws it and how an inspector reads
 * it. And a single path draws itself with one stroke-dashoffset animation
 * instead of coordinating a dozen.
 *
 * Each entry contributes a vertical move to its row followed by a horizontal
 * run to its end hour. The first entry starts with a move instead, since
 * there is nothing to connect back to.
 */
export function dutyLinePath(entries: GridEntry[]): string {
  if (entries.length === 0) return "";

  const parts: string[] = [];
  entries.forEach((entry, index) => {
    const y = rowCentre(entry.row);
    parts.push(`${index === 0 ? "M" : "L"} ${hourX(entry.start_hour)} ${y}`);
    parts.push(`L ${hourX(entry.end_hour)} ${y}`);
  });
  return parts.join(" ");
}

export interface RemarkTick extends LogRemark {
  x: number;
  /** How many steps down the label sits, to keep it clear of its neighbour. */
  lane: number;
}

/**
 * Place the remark labels so they stay readable.
 *
 * The labels run at an angle, which already buys most of the clearance, but a
 * pickup and a fuel stop twenty minutes apart still collide. A label closer
 * than `minGapPx` to the last one on its lane drops to the next lane, and
 * three lanes cycle. Three is enough: the planner never puts four stops
 * inside forty minutes.
 */
export function layOutRemarks(remarks: LogRemark[], minGapPx = 17): RemarkTick[] {
  const lastX = [-Infinity, -Infinity, -Infinity];

  return remarks.map((remark) => {
    const x = hourX(remark.hour);
    let lane = lastX.findIndex((previous) => x - previous >= minGapPx);
    if (lane === -1) lane = 0;
    lastX[lane] = x;
    return { ...remark, x, lane };
  });
}

/** Hours as a driver writes them in the totals column: 8, 8.5, 10.25. */
export function formatHours(hours: number): string {
  const rounded = Math.round(hours * 100) / 100;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2).replace(/0$/, "");
}

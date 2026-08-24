/**
 * Colours that mean something.
 *
 * The duty statuses and the stop kinds appear in four places: the map
 * markers, the timeline, the log sheet grid, and the summary. They have to
 * agree everywhere. A driver who learns that amber is on-duty on the log
 * should see the same amber on the map. They live here rather than in the MUI
 * palette because the log sheet is drawn as SVG and never touches a theme.
 */

import type { DutyStatus, StopKind } from "../types/trip";

export const DUTY_COLOURS: Record<DutyStatus, string> = {
  off_duty: "#94A3B8", // slate, not working
  sleeper_berth: "#818CF8", // indigo, in the bunk
  driving: "#38BDF8", // sky, the accent, because this is the point
  on_duty: "#FBBF24", // amber, working but not driving
};

export const DUTY_LABELS: Record<DutyStatus, string> = {
  off_duty: "Off duty",
  sleeper_berth: "Sleeper berth",
  driving: "Driving",
  on_duty: "On duty (not driving)",
};

/** The row each status occupies on the paper form, top to bottom. */
export const DUTY_ROWS: DutyStatus[] = [
  "off_duty",
  "sleeper_berth",
  "driving",
  "on_duty",
];

export const STOP_COLOURS: Record<StopKind, string> = {
  start: "#E2E8F0",
  drive: "#38BDF8",
  pickup: "#34D399", // emerald, cargo on
  dropoff: "#FB7185", // rose, cargo off
  fuel: "#FBBF24",
  break: "#94A3B8",
  rest: "#818CF8",
  restart: "#A78BFA",
};

export const STOP_GLYPHS: Record<StopKind, string> = {
  start: "A",
  drive: "→",
  pickup: "P",
  dropoff: "D",
  fuel: "F",
  break: "B",
  rest: "R",
  restart: "34",
};

export const SURFACE = {
  page: "#0B1220",
  card: "#131C2E",
  raised: "#1B2740",
  line: "#24324D",
  ink: "#E6EDF7",
  inkMuted: "#93A4BF",
  accent: "#38BDF8",
  good: "#34D399",
  warn: "#FBBF24",
  bad: "#FB7185",
} as const;

/**
 * The same statuses again, in ink that survives white paper.
 *
 * The colours above are tuned for a near-black background and go pale on a
 * printed sheet. The log sheet is drawn as paper because that is what it is,
 * so it needs its own set.
 */
export const DUTY_INK: Record<DutyStatus, string> = {
  off_duty: "#475569",
  sleeper_berth: "#4338CA",
  driving: "#0369A1",
  on_duty: "#B45309",
};

/** The sheet itself. Printed as-is, so the values are print values. */
export const PAPER = {
  sheet: "#F8FAFC",
  ink: "#0F172A",
  rule: "#334155",
  hairline: "#94A3B8",
  strip: "#0F172A",
  stripInk: "#F8FAFC",
  filled: "#0F172A",
} as const;

/**
 * The log sheets, one tab per day.
 *
 * A trip that crosses midnight needs a sheet per calendar day, and the
 * assessment asks for all of them. Tabs rather than a stack: a driver checks
 * one day at a time, and eight stacked sheets bury the map.
 *
 * Print puts every sheet on its own page. Screen shows the selected one.
 */

import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";
import { useCallback, useRef, useState } from "react";

import { LogSheetSvg } from "./logsheet/LogSheetSvg";
import { SHEET, formatHours } from "./logsheet/sheet-layout";
import { fadeIn, riseIn } from "../theme/motion";
import { DUTY_COLOURS, DUTY_LABELS, DUTY_ROWS, SURFACE } from "../theme/tokens";
import type { LogSheet, Trip } from "../types/trip";

/** The date as the tab shows it. Parsed as local, not UTC, so it stays put. */
function tabDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function hourClock(hour: number): string {
  const whole = Math.floor(hour);
  const minutes = Math.round((hour - whole) * 60);
  return `${String(whole).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

/**
 * Export the sheet on screen as a PNG.
 *
 * The SVG is serialised, drawn onto a canvas at twice its size and handed
 * back as a download. Two things need care. The duty line animates by holding
 * a stroke-dashoffset, so the clone has to have that cleared or the line
 * exports half drawn. And a canvas will not accept an SVG that carries no
 * explicit width and height.
 */
async function exportPng(svg: SVGSVGElement, filename: string): Promise<void> {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("width", String(SHEET.width));
  clone.setAttribute("height", String(SHEET.height));
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");

  const line = clone.querySelector<SVGPathElement>("[data-duty-line]");
  if (line) {
    line.style.strokeDasharray = "none";
    line.style.strokeDashoffset = "0";
    line.style.animation = "none";
  }

  const source = new XMLSerializer().serializeToString(clone);
  const url = URL.createObjectURL(new Blob([source], { type: "image/svg+xml;charset=utf-8" }));

  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("The sheet could not be rasterised."));
      image.src = url;
    });

    const scale = 2;
    const canvas = document.createElement("canvas");
    canvas.width = SHEET.width * scale;
    canvas.height = SHEET.height * scale;

    const context = canvas.getContext("2d");
    if (!context) throw new Error("This browser gave no 2D canvas.");
    context.fillStyle = "#FFFFFF";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);

    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = filename;
    link.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}

function Totals({ sheet }: { sheet: LogSheet }) {
  return (
    <Stack direction="row" spacing={2.5} sx={{ flexWrap: "wrap", rowGap: 1 }}>
      {DUTY_ROWS.map((status) => (
        <Stack key={status} direction="row" spacing={0.75} sx={{ alignItems: "center" }}>
          <Box
            aria-hidden
            sx={{
              width: 10,
              height: 10,
              borderRadius: 0.5,
              backgroundColor: DUTY_COLOURS[status],
              flexShrink: 0,
            }}
          />
          <Typography variant="caption" sx={{ color: SURFACE.inkMuted }}>
            {DUTY_LABELS[status]}
          </Typography>
          <Typography className="tabular" variant="caption" sx={{ color: SURFACE.ink }}>
            {formatHours(sheet.totals[status] ?? 0)} h
          </Typography>
        </Stack>
      ))}
    </Stack>
  );
}

/**
 * The remarks again, as text.
 *
 * They are already on the sheet, angled and small, because that is where the
 * form puts them. Nobody should have to read them at that angle to find out
 * where the driver stopped.
 */
function RemarksList({ sheet }: { sheet: LogSheet }) {
  if (sheet.remarks.length === 0) return null;

  return (
    <Box>
      <Typography variant="overline" sx={{ color: SURFACE.inkMuted, letterSpacing: 1 }}>
        Remarks
      </Typography>
      <Stack spacing={0.5} sx={{ mt: 0.5 }}>
        {sheet.remarks.map((remark, index) => (
          <Stack
            key={`${remark.hour}-${index}`}
            direction="row"
            spacing={1.5}
            sx={{ alignItems: "baseline", ...fadeIn(index) }}
          >
            <Typography
              className="tabular"
              variant="body2"
              sx={{ color: SURFACE.accent, minWidth: 46 }}
            >
              {hourClock(remark.hour)}
            </Typography>
            <Typography variant="body2" sx={{ color: SURFACE.ink, minWidth: 0 }}>
              {remark.text}
            </Typography>
            <Typography variant="body2" sx={{ color: SURFACE.inkMuted }}>
              {remark.location}
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Box>
  );
}

export function LogSheets({ trip }: { trip: Trip }) {
  const [selected, setSelected] = useState(0);
  const svgHolder = useRef<HTMLDivElement>(null);
  const sheet = trip.logs[selected] ?? trip.logs[0];

  const download = useCallback(() => {
    const svg = svgHolder.current?.querySelector("svg");
    if (svg) void exportPng(svg, `eld-log-${sheet.date}.png`);
  }, [sheet.date]);

  if (trip.logs.length === 0) return null;

  return (
    <Paper sx={{ p: { xs: 2, md: 2.5 } }}>
      <Stack
        direction="row"
        sx={{ alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 1.5 }}
      >
        <Box>
          <Typography variant="h6">Daily log sheets</Typography>
          <Typography variant="body2" sx={{ color: SURFACE.inkMuted }}>
            {trip.logs.length === 1
              ? "One sheet, drawn from the plan"
              : `${trip.logs.length} sheets, one per calendar day`}
          </Typography>
        </Box>

        <Stack direction="row" spacing={1} className="no-print">
          <Button variant="outlined" size="small" onClick={download}>
            Download PNG
          </Button>
          <Button variant="outlined" size="small" onClick={() => window.print()}>
            Print all
          </Button>
        </Stack>
      </Stack>

      {trip.logs.length > 1 && (
        <Tabs
          value={selected}
          onChange={(_, next: number) => setSelected(next)}
          variant="scrollable"
          scrollButtons="auto"
          className="no-print"
          sx={{ mt: 1.5, minHeight: 40, borderBottom: `1px solid ${SURFACE.line}` }}
        >
          {trip.logs.map((log, index) => (
            <Tab
              key={log.date}
              sx={{ minHeight: 40, textTransform: "none" }}
              label={`Day ${index + 1} · ${tabDate(log.date)}`}
            />
          ))}
        </Tabs>
      )}

      {/* The sheet keeps its proportions. On a narrow screen it scrolls
          sideways rather than shrinking the hour grid past reading. */}
      <Box
        ref={svgHolder}
        key={sheet.date}
        sx={{ mt: 2, overflowX: "auto", ...riseIn(0) }}
      >
        <Box
          className="print-sheet"
          sx={{
            minWidth: 720,
            borderRadius: 2,
            overflow: "hidden",
            boxShadow: "0 18px 48px rgba(0,0,0,0.45)",
          }}
        >
          <LogSheetSvg sheet={sheet} inputs={trip.inputs} />
        </Box>
      </Box>

      {/* On a phone the sheet runs past the edge. Say so, rather than
          leaving the right half to be discovered. */}
      <Typography
        variant="caption"
        className="no-print"
        sx={{ display: { xs: "block", md: "none" }, mt: 0.75, color: SURFACE.inkMuted }}
      >
        Scroll the sheet sideways to reach the evening hours.
      </Typography>

      <Stack spacing={2} sx={{ mt: 2 }}>
        <Totals sheet={sheet} />
        <RemarksList sheet={sheet} />
      </Stack>

      {/* Print takes every day, not the one on screen. */}
      <Box className="print-only" aria-hidden>
        {trip.logs.map((log, index) =>
          index === selected ? null : (
            <Box key={log.date} className="print-sheet">
              <LogSheetSvg sheet={log} inputs={trip.inputs} animate={false} />
            </Box>
          ),
        )}
      </Box>
    </Paper>
  );
}

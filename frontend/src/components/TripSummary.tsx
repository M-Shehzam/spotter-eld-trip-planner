import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ReportProblemIcon from "@mui/icons-material/ReportProblem";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

import { riseIn } from "../theme/motion";
import { SURFACE } from "../theme/tokens";
import type { Trip } from "../types/trip";

interface TileProps {
  label: string;
  value: string;
  unit?: string;
  note?: string;
  index: number;
  accent?: string;
}

function StatTile({ label, value, unit, note, index, accent }: TileProps) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        borderRadius: 2.5,
        minWidth: 0,
        backgroundColor: SURFACE.card,
        ...riseIn(index),
      }}
    >
      <Typography
        variant="overline"
        sx={{ color: SURFACE.inkMuted, display: "block" }}
      >
        {label}
      </Typography>

      <Stack direction="row" spacing={0.5} sx={{ alignItems: "baseline", mt: 0.25 }}>
        <Typography
          className="tabular"
          sx={{
            fontSize: "1.55rem",
            fontWeight: 600,
            lineHeight: 1.15,
            color: accent ?? SURFACE.ink,
            // Long values shrink rather than spilling out of the tile.
            overflowWrap: "anywhere",
          }}
        >
          {value}
        </Typography>
        {unit && (
          <Typography variant="body2" sx={{ color: SURFACE.inkMuted }}>
            {unit}
          </Typography>
        )}
      </Stack>

      {note && (
        <Typography
          variant="caption"
          sx={{ color: SURFACE.inkMuted, display: "block", mt: 0.25 }}
        >
          {note}
        </Typography>
      )}
    </Paper>
  );
}

/**
 * Whether the plan actually obeys the regulation.
 *
 * This is not decoration. The backend re-checks every finished plan against
 * the limits with a second implementation, and this reports what that check
 * found. A plan that broke a rule says so rather than looking fine.
 */
function ComplianceBanner({ summary }: { summary: Trip["summary"] }) {
  const ok = summary.compliant;

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        borderRadius: 2.5,
        gridColumn: "1 / -1",
        borderColor: ok ? "rgba(52,211,153,0.35)" : "rgba(251,113,133,0.45)",
        backgroundColor: ok ? "rgba(52,211,153,0.07)" : "rgba(251,113,133,0.09)",
        ...riseIn(6),
      }}
    >
      <Stack direction="row" spacing={1.5} sx={{ alignItems: "flex-start" }}>
        {ok ? (
          <CheckCircleIcon sx={{ color: SURFACE.good, fontSize: 21, mt: 0.2 }} />
        ) : (
          <ReportProblemIcon sx={{ color: SURFACE.bad, fontSize: 21, mt: 0.2 }} />
        )}

        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {ok
              ? "Compliant with 49 CFR 395.3"
              : `${summary.violations.length} problem${
                  summary.violations.length === 1 ? "" : "s"
                } found in this plan`}
          </Typography>

          {ok ? (
            <Typography variant="caption" sx={{ color: SURFACE.inkMuted }}>
              11-hour driving limit, 14-hour window, 30-minute break, and the
              70-hour cycle all verified against the finished plan.
            </Typography>
          ) : (
            <Stack component="ul" spacing={0.25} sx={{ m: 0, pl: 2.2, mt: 0.5 }}>
              {summary.violations.map((problem) => (
                <Typography
                  key={problem}
                  component="li"
                  variant="caption"
                  sx={{ color: SURFACE.ink }}
                >
                  {problem}
                </Typography>
              ))}
            </Stack>
          )}
        </Box>
      </Stack>
    </Paper>
  );
}

/**
 * Day and time, on a 24-hour clock.
 *
 * Log sheets are kept in 24-hour time, so the summary matches them rather
 * than making a reader convert. It also keeps the value on one line, which
 * "Thu 07:10 PM" does not.
 */
function shortDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function TripSummary({ trip }: { trip: Trip }) {
  const { summary } = trip;
  const rests = summary.rests + summary.restarts;

  return (
    <Box
      sx={{
        display: "grid",
        gap: 1.5,
        gridTemplateColumns: {
          xs: "repeat(2, minmax(0, 1fr))",
          md: "repeat(3, minmax(0, 1fr))",
          xl: "repeat(6, minmax(0, 1fr))",
        },
      }}
    >
      <StatTile
        index={0}
        label="Distance"
        value={Math.round(summary.total_miles).toLocaleString()}
        unit="mi"
        note={`${summary.average_speed_mph} mph average`}
      />
      <StatTile
        index={1}
        label="Driving"
        value={summary.drive_hours.toFixed(1)}
        unit="h"
        note={`${summary.on_duty_hours.toFixed(1)} h on duty`}
      />
      <StatTile
        index={2}
        label="Log sheets"
        value={String(summary.days)}
        unit={summary.days === 1 ? "day" : "days"}
        note={`${summary.elapsed_hours.toFixed(0)} h door to door`}
      />
      <StatTile
        index={3}
        label="Arrival"
        value={shortDateTime(summary.arrival)}
        note={`Departs ${shortDateTime(summary.departure)}`}
      />
      {/* Counts only the stops the rules force. Pickup, dropoff and the
          origin are in the timeline but are not what this number is about. */}
      <StatTile
        index={4}
        label="Required stops"
        value={String(summary.fuel_stops + summary.rest_breaks + rests)}
        note={`${summary.fuel_stops} fuel · ${summary.rest_breaks} break${
          summary.rest_breaks === 1 ? "" : "s"
        } · ${rests} rest${rests === 1 ? "" : "s"}`}
      />
      <Tooltip
        title={`Started the trip with ${summary.cycle_hours_at_start} of 70 hours used`}
      >
        <Box sx={{ minWidth: 0 }}>
          <StatTile
            index={5}
            label="Cycle left"
            value={summary.cycle_hours_available.toFixed(1)}
            unit="h"
            accent={summary.cycle_hours_available < 11 ? SURFACE.warn : undefined}
            note={`${summary.cycle_hours_at_finish.toFixed(1)} h used of 70`}
          />
        </Box>
      </Tooltip>

      <ComplianceBanner summary={summary} />
    </Box>
  );
}

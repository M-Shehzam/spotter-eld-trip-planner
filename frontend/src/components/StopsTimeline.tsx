import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import { riseIn } from "../theme/motion";
import { STOP_COLOURS, STOP_GLYPHS, SURFACE } from "../theme/tokens";
import type { Stop, Trip } from "../types/trip";

/** 24-hour, to match the log sheets these times end up on. */
function timeOf(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function dayOf(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function Row({
  stop,
  index,
  previous,
  last,
}: {
  stop: Stop;
  index: number;
  previous?: Stop;
  last: boolean;
}) {
  const colour = STOP_COLOURS[stop.kind];
  const newDay =
    !previous || dayOf(previous.arrive ?? previous.depart) !== dayOf(stop.arrive ?? stop.depart);
  const legMiles = previous ? stop.mile_marker - previous.mile_marker : 0;

  return (
    <Box sx={{ display: "flex", gap: 1.75, ...riseIn(index) }}>
      {/* The rail: a marker and the line running to the next stop. */}
      <Stack sx={{ alignItems: "center", flexShrink: 0 }}>
        <Box
          aria-hidden
          sx={{
            width: 26,
            height: 26,
            borderRadius: "50%",
            backgroundColor: colour,
            color: "#06111F",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: '"Fira Code", monospace',
            fontSize: 11,
            fontWeight: 600,
            flexShrink: 0,
          }}
        >
          {STOP_GLYPHS[stop.kind]}
        </Box>
        {!last && (
          <Box
            sx={{
              width: 2,
              flex: 1,
              minHeight: 26,
              mt: 0.5,
              borderRadius: 1,
              background: `linear-gradient(${colour}55, ${SURFACE.line})`,
            }}
          />
        )}
      </Stack>

      <Box sx={{ pb: last ? 0 : 2.5, minWidth: 0, flex: 1 }}>
        {newDay && (
          <Typography
            variant="overline"
            sx={{ color: SURFACE.inkMuted, display: "block", mb: 0.25 }}
          >
            {dayOf(stop.arrive ?? stop.depart)}
          </Typography>
        )}

        <Stack
          direction="row"
          spacing={1}
          sx={{ alignItems: "baseline", flexWrap: "wrap" }}
        >
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {stop.title}
          </Typography>
          <Typography className="tabular" variant="caption" sx={{ color: colour }}>
            {timeOf(stop.arrive ?? stop.depart)}
            {stop.duration_hours > 0 && ` – ${timeOf(stop.depart)}`}
          </Typography>
        </Stack>

        <Typography variant="body2" sx={{ color: SURFACE.inkMuted }}>
          {stop.location}
        </Typography>

        <Typography
          className="tabular"
          variant="caption"
          sx={{ color: SURFACE.inkMuted, opacity: 0.8 }}
        >
          Mile {Math.round(stop.mile_marker).toLocaleString()}
          {legMiles > 0 && ` · ${Math.round(legMiles).toLocaleString()} mi driven`}
        </Typography>
      </Box>
    </Box>
  );
}

/**
 * Every stop in the order the driver reaches them.
 *
 * The map answers "where", this answers "when and for how long", which is the
 * question a dispatcher actually asks. Days are marked as they change so a
 * multi-day trip reads without cross-referencing the log sheets.
 */
export function StopsTimeline({ trip }: { trip: Trip }) {
  return (
    <Paper elevation={0} sx={{ p: { xs: 2, sm: 2.5 }, borderRadius: 3 }}>
      <Typography variant="h3" sx={{ mb: 0.25 }}>
        Stops and rests
      </Typography>
      <Typography variant="body2" sx={{ color: SURFACE.inkMuted, mb: 2.5 }}>
        Every stop including pickup and dropoff, over{" "}
        {Math.round(trip.summary.elapsed_hours)} hours.
      </Typography>

      <Box>
        {trip.stops.map((stop, index) => (
          <Row
            key={stop.seq}
            stop={stop}
            index={index}
            previous={trip.stops[index - 1]}
            last={index === trip.stops.length - 1}
          />
        ))}
      </Box>
    </Paper>
  );
}

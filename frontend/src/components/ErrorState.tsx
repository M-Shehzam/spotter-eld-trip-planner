/**
 * What the results column shows when a request fails.
 *
 * An error with no way out is a dead end, so this names what went wrong in
 * the terms the API used, says what to do about it, and offers the retry
 * rather than leaving the driver to guess that resubmitting might work.
 */

import RefreshIcon from "@mui/icons-material/Refresh";
import ReportProblemIcon from "@mui/icons-material/ReportProblem";
import Button from "@mui/material/Button";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import type { ApiError } from "../api/client";
import { riseIn } from "../theme/motion";
import { SURFACE } from "../theme/tokens";

/** What a driver can actually do about each code the API returns. */
const RECOVERY: Record<string, string> = {
  location_not_found:
    "One of the locations did not match a US place. Try a nearby town with its state, like Joliet, IL, or paste coordinates as latitude, longitude.",
  route_not_found:
    "No road route connects those three points in that order. Check that each one sits on the mainland road network.",
  routing_unavailable:
    "The public routing service is refusing requests. It rate limits by address, so this usually clears within a minute.",
  routing_error: "The routing service answered with something unusable. Try again.",
  routing_request_invalid:
    "The routing service rejected the request. Check the locations and try again.",
  unknown_time_zone:
    "The time zone for that starting point could not be resolved, and every hour on a log sheet depends on it.",
  timeout:
    "The request ran past its limit. The free tier sleeps when idle, so a second attempt usually lands.",
  network_error: "The server did not answer. Check the connection and try again.",
  internal_error: "The planner failed partway through. Trying again is worth a shot.",
};

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  const advice = RECOVERY[error.code] ?? "Try again, or change one of the locations.";

  return (
    <Paper
      role="alert"
      sx={{
        p: { xs: 3, md: 4 },
        borderColor: "rgba(251,113,133,0.35)",
        backgroundColor: "rgba(251,113,133,0.05)",
        ...riseIn(0),
      }}
    >
      <Stack spacing={2} sx={{ alignItems: "flex-start" }}>
        <Stack direction="row" spacing={1.25} sx={{ alignItems: "center" }}>
          <ReportProblemIcon sx={{ color: SURFACE.bad }} />
          <Typography variant="h3">The trip could not be planned</Typography>
        </Stack>

        <Typography variant="body2" sx={{ color: SURFACE.ink }}>
          {error.message}
        </Typography>
        <Typography variant="body2" sx={{ color: SURFACE.inkMuted, maxWidth: 560 }}>
          {advice}
        </Typography>

        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={onRetry}>
          Try again
        </Button>
      </Stack>
    </Paper>
  );
}

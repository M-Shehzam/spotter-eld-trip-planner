import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import CssBaseline from "@mui/material/CssBaseline";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { ThemeProvider } from "@mui/material/styles";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "./api/client";
import { getTrip, planTrip } from "./api/trips";
import { AppHeader } from "./components/AppHeader";
import { EmptyState } from "./components/EmptyState";
import { ErrorState } from "./components/ErrorState";
import { LogSheets } from "./components/LogSheets";
import { RouteMap } from "./components/RouteMap";
import { StopsTimeline } from "./components/StopsTimeline";
import { TripForm } from "./components/TripForm";
import { TripSkeleton } from "./components/TripSkeleton";
import { TripSummary } from "./components/TripSummary";
import { riseIn } from "./theme/motion";
import { theme } from "./theme/theme";
import { SURFACE } from "./theme/tokens";
import type { Trip, TripRequest } from "./types/trip";

function Results({ trip }: { trip: Trip }) {
  return (
    <Stack spacing={3}>
      <Box className="no-print">
        <TripSummary trip={trip} />
      </Box>

      <Box className="no-print" sx={{ ...riseIn(2) }}>
        <RouteMap trip={trip} />
      </Box>

      {/* The sheets are the deliverable the brief names, so they sit above
          the timeline that explains them. */}
      <Box sx={{ ...riseIn(3) }}>
        <LogSheets trip={trip} />
      </Box>

      <Box className="no-print" sx={{ ...riseIn(4) }}>
        <StopsTimeline trip={trip} />
      </Box>
    </Stack>
  );
}

/**
 * A keyboard user should not have to tab through the whole form to reach the
 * plan. Hidden until focused, which is the one case where hiding is correct.
 */
function SkipLink() {
  return (
    <Box
      component="a"
      href="#results"
      className="no-print"
      sx={{
        position: "absolute",
        left: 12,
        top: -80,
        zIndex: 2000,
        px: 2,
        py: 1.25,
        borderRadius: 2,
        fontWeight: 600,
        color: "#062032",
        backgroundColor: SURFACE.accent,
        textDecoration: "none",
        transition: "top 160ms cubic-bezier(0.16,1,0.3,1)",
        // A skip link is reachable only by keyboard, so plain :focus is
        // the right trigger and does not depend on the heuristics behind
        // :focus-visible.
        "&:focus, &:focus-visible": { top: 12 },
      }}
    >
      Skip to the plan
    </Box>
  );
}

export default function App() {
  const [trip, setTrip] = useState<Trip | null>(null);
  const [busy, setBusy] = useState(false);
  const [waking, setWaking] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const lastRequest = useRef<TripRequest | null>(null);
  // Set only when a plan arrives from a shared link, so the form can show
  // what produced it. A plan the user just submitted needs no restoring.
  const [restored, setRestored] = useState<Trip | null>(null);

  const run = useCallback(async (request: TripRequest) => {
    lastRequest.current = request;
    setBusy(true);
    setError(null);
    setWaking(false);
    try {
      const planned = await planTrip(request, () => setWaking(true));
      setTrip(planned);
      // The id in the address bar makes a plan shareable, and the backend
      // already caches by it, so reopening the link costs no routing call.
      const url = new URL(window.location.href);
      url.searchParams.set("trip", planned.id);
      window.history.replaceState(null, "", url);
    } catch (cause) {
      setError(cause as ApiError);
      setTrip(null);
      // Below the large breakpoint the results sit under the form, so an
      // error there would land off-screen without this.
      if (window.matchMedia("(max-width: 1199px)").matches) {
        requestAnimationFrame(() =>
          document.getElementById("results")?.scrollIntoView({ block: "start" }),
        );
      }
    } finally {
      setBusy(false);
      setWaking(false);
    }
  }, []);

  const retry = useCallback(() => {
    if (lastRequest.current) void run(lastRequest.current);
  }, [run]);

  // A link with ?trip=<id> opens that plan.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("trip");
    if (!id) return;

    let live = true;
    setBusy(true);
    getTrip(id, () => setWaking(true))
      .then((found) => {
        if (live) {
          setTrip(found);
          setRestored(found);
        }
      })
      .catch(() => {
        // A stale or unknown id is not worth an error panel. The form is
        // right there, and the empty state already explains what to do.
        if (live) window.history.replaceState(null, "", window.location.pathname);
      })
      .finally(() => {
        if (live) {
          setBusy(false);
          setWaking(false);
        }
      });

    return () => {
      live = false;
    };
  }, []);

  // Field-level problems belong beside their field; anything else goes in the
  // panel where the results would have been.
  const fieldErrors =
    error?.code === "invalid_request"
      ? (error.detail as Record<string, string[]>)
      : undefined;

  const status = busy
    ? "Planning the trip."
    : error
      ? `The trip could not be planned. ${error.message}`
      : trip
        ? `Plan ready. ${trip.summary.days} days, ${Math.round(trip.summary.total_miles)} miles, ${trip.logs.length} log sheets.`
        : "";

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <SkipLink />
      <AppHeader />

      {/* One polite announcement per state change, rather than a screen
          reader having to hunt the page for what just happened. */}
      <Box
        role="status"
        aria-live="polite"
        sx={{
          position: "absolute",
          width: 1,
          height: 1,
          overflow: "hidden",
          clip: "rect(0 0 0 0)",
          whiteSpace: "nowrap",
        }}
      >
        {status}
      </Box>

      <Container maxWidth="xl" sx={{ py: { xs: 3, md: 4 } }}>
        <Box
          sx={{
            display: "grid",
            gap: { xs: 3, md: 3.5 },
            gridTemplateColumns: { xs: "1fr", lg: "minmax(330px, 390px) 1fr" },
            alignItems: "start",
          }}
        >
          <Box
            className="no-print"
            sx={{ position: { lg: "sticky" }, top: { lg: 86 } }}
          >
            {/* The form shows a summary only for problems with its own
                fields, next to the inline messages that say which. A request
                that failed outright is reported once, in the results panel,
                rather than twice in two different shapes. */}
            <TripForm
              key={restored?.id ?? "blank"}
              initial={restored?.inputs}
              onSubmit={run}
              busy={busy}
              errorMessage={fieldErrors ? (error?.message ?? null) : null}
              fieldErrors={fieldErrors}
            />

            {waking && (
              <Typography
                variant="caption"
                sx={{ display: "block", mt: 1.5, color: SURFACE.inkMuted }}
              >
                The server sleeps when idle on the free tier, so a first request
                can take about a minute.
              </Typography>
            )}
          </Box>

          <Box component="main" id="results" sx={{ minWidth: 0 }}>
            {busy ? (
              <TripSkeleton />
            ) : error && !fieldErrors ? (
              <ErrorState error={error} onRetry={retry} />
            ) : trip ? (
              <Results key={trip.id} trip={trip} />
            ) : (
              <EmptyState />
            )}
          </Box>
        </Box>
      </Container>
    </ThemeProvider>
  );
}

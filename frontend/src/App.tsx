import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import CssBaseline from "@mui/material/CssBaseline";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { ThemeProvider } from "@mui/material/styles";
import { useCallback, useState } from "react";

import { ApiError } from "./api/client";
import { planTrip } from "./api/trips";
import { AppHeader } from "./components/AppHeader";
import { EmptyState } from "./components/EmptyState";
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

export default function App() {
  const [trip, setTrip] = useState<Trip | null>(null);
  const [busy, setBusy] = useState(false);
  const [waking, setWaking] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const submit = useCallback(async (request: TripRequest) => {
    setBusy(true);
    setError(null);
    setWaking(false);
    try {
      setTrip(await planTrip(request, () => setWaking(true)));
    } catch (cause) {
      setError(cause as ApiError);
      setTrip(null);
    } finally {
      setBusy(false);
      setWaking(false);
    }
  }, []);

  // Field-level problems belong beside their field; anything else goes in the
  // banner above the submit button.
  const fieldErrors =
    error?.code === "invalid_request"
      ? (error.detail as Record<string, string[]>)
      : undefined;

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppHeader />

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
            <TripForm
              onSubmit={submit}
              busy={busy}
              errorMessage={fieldErrors ? null : (error?.message ?? null)}
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

          <Box sx={{ minWidth: 0 }}>
            {busy ? (
              <TripSkeleton />
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

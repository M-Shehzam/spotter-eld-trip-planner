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
import { TripForm } from "./components/TripForm";
import { theme } from "./theme/theme";
import { SURFACE } from "./theme/tokens";
import type { Trip, TripRequest } from "./types/trip";

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

  const fieldErrors =
    error?.code === "invalid_request"
      ? (error.detail as Record<string, string[]>)
      : undefined;

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppHeader />

      <Container maxWidth="xl" sx={{ py: { xs: 3, md: 5 } }}>
        <Box
          sx={{
            display: "grid",
            gap: { xs: 3, md: 4 },
            gridTemplateColumns: { xs: "1fr", lg: "minmax(340px, 400px) 1fr" },
            alignItems: "start",
          }}
        >
          <Box sx={{ position: { lg: "sticky" }, top: { lg: 88 } }}>
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
                The server sleeps when idle on the free tier. First request takes
                about a minute.
              </Typography>
            )}
          </Box>

          <Box>
            {trip ? (
              <Stack spacing={3}>
                <Typography variant="h2">
                  {trip.summary.total_miles.toLocaleString()} miles ·{" "}
                  {trip.summary.days} days
                </Typography>
                <Typography variant="body2" sx={{ color: SURFACE.inkMuted }}>
                  Route, stops and log sheets land here next.
                </Typography>
              </Stack>
            ) : (
              <Typography variant="body2" sx={{ color: SURFACE.inkMuted }}>
                Enter a trip to see the route and its log sheets.
              </Typography>
            )}
          </Box>
        </Box>
      </Container>
    </ThemeProvider>
  );
}

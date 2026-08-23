import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import LocalShippingIcon from "@mui/icons-material/LocalShipping";
import MyLocationIcon from "@mui/icons-material/MyLocation";
import PlaceIcon from "@mui/icons-material/Place";
import WarehouseIcon from "@mui/icons-material/Warehouse";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Collapse from "@mui/material/Collapse";
import Divider from "@mui/material/Divider";
import InputAdornment from "@mui/material/InputAdornment";
import Link from "@mui/material/Link";
import Paper from "@mui/material/Paper";
import Slider from "@mui/material/Slider";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import type { TripRequest } from "../types/trip";
import { riseIn } from "../theme/motion";
import { SURFACE } from "../theme/tokens";

import { LocationField } from "./LocationField";

const CYCLE_LIMIT = 70;

/** One button that fills the form with a trip worth looking at. */
const EXAMPLE: TripRequest = {
  current_location: "Newark, NJ",
  pickup_location: "Columbus, OH",
  dropoff_location: "Denver, CO",
  current_cycle_used_hours: 52,
};

interface Props {
  onSubmit: (request: TripRequest) => void;
  busy: boolean;
  errorMessage?: string | null;
  fieldErrors?: Record<string, string[]>;
}

export function TripForm({ onSubmit, busy, errorMessage, fieldErrors }: Props) {
  const [current, setCurrent] = useState("");
  const [pickup, setPickup] = useState("");
  const [dropoff, setDropoff] = useState("");
  const [cycleHours, setCycleHours] = useState(0);
  const [showDetails, setShowDetails] = useState(false);
  const [driver, setDriver] = useState("");
  const [carrier, setCarrier] = useState("");
  const [truck, setTruck] = useState("");
  const [touched, setTouched] = useState(false);

  const missing = {
    current_location: !current.trim(),
    pickup_location: !pickup.trim(),
    dropoff_location: !dropoff.trim(),
  };
  const incomplete = Object.values(missing).some(Boolean);

  function firstError(field: keyof typeof missing): string | undefined {
    if (touched && missing[field]) return "Required.";
    return fieldErrors?.[field]?.[0];
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (incomplete || busy) return;

    onSubmit({
      current_location: current.trim(),
      pickup_location: pickup.trim(),
      dropoff_location: dropoff.trim(),
      current_cycle_used_hours: cycleHours,
      driver_name: driver.trim(),
      carrier_name: carrier.trim(),
      truck_number: truck.trim(),
    });
  }

  function loadExample() {
    setCurrent(EXAMPLE.current_location);
    setPickup(EXAMPLE.pickup_location);
    setDropoff(EXAMPLE.dropoff_location);
    setCycleHours(EXAMPLE.current_cycle_used_hours);
    setTouched(false);
  }

  const remaining = CYCLE_LIMIT - cycleHours;

  return (
    <Paper
      component="form"
      onSubmit={submit}
      elevation={0}
      sx={{ p: { xs: 2.5, sm: 3.5 }, borderRadius: 3, ...riseIn(0) }}
    >
      <Stack
        direction="row"
        sx={{ justifyContent: "space-between", alignItems: "baseline", mb: 0.5 }}
      >
        <Typography variant="h2">Plan a trip</Typography>
        <Link
          component="button"
          type="button"
          variant="body2"
          onClick={loadExample}
          sx={{ color: SURFACE.accent, textDecorationColor: "rgba(56,189,248,0.4)" }}
        >
          Use an example
        </Link>
      </Stack>

      <Typography variant="body2" sx={{ color: SURFACE.inkMuted, mb: 3 }}>
        Route and daily log sheets for a property-carrying driver on the 70-hour,
        8-day cycle.
      </Typography>

      <Stack spacing={2.5}>
        <LocationField
          label="Current location"
          value={current}
          onChange={setCurrent}
          placeholder="Newark, NJ"
          icon={<MyLocationIcon fontSize="small" />}
          error={firstError("current_location")}
          required
        />
        <LocationField
          label="Pickup"
          value={pickup}
          onChange={setPickup}
          placeholder="Columbus, OH"
          icon={<WarehouseIcon fontSize="small" />}
          error={firstError("pickup_location")}
          required
        />
        <LocationField
          label="Dropoff"
          value={dropoff}
          onChange={setDropoff}
          placeholder="Denver, CO"
          icon={<PlaceIcon fontSize="small" />}
          error={firstError("dropoff_location")}
          required
        />

        <Box>
          <Stack
            direction="row"
            sx={{ justifyContent: "space-between", alignItems: "baseline", mb: 0.5 }}
          >
            <Typography variant="body2" component="label" id="cycle-label">
              Current cycle used
            </Typography>
            <Typography
              className="tabular"
              variant="body2"
              sx={{ color: remaining <= 11 ? SURFACE.warn : SURFACE.inkMuted }}
            >
              {remaining.toFixed(1)} h left of {CYCLE_LIMIT}
            </Typography>
          </Stack>

          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
            <Slider
              value={cycleHours}
              onChange={(_, next) => setCycleHours(next as number)}
              min={0}
              max={CYCLE_LIMIT}
              step={0.5}
              valueLabelDisplay="auto"
              aria-labelledby="cycle-label"
              sx={{ flex: 1 }}
            />
            <TextField
              value={cycleHours}
              onChange={(event) => {
                const parsed = Number(event.target.value);
                if (Number.isNaN(parsed)) return;
                setCycleHours(Math.min(Math.max(parsed, 0), CYCLE_LIMIT));
              }}
              type="number"
              size="small"
              slotProps={{
                htmlInput: {
                  min: 0,
                  max: CYCLE_LIMIT,
                  step: 0.5,
                  "aria-label": "Cycle hours used",
                },
                input: {
                  endAdornment: <InputAdornment position="end">h</InputAdornment>,
                },
              }}
              sx={{ width: 108, "& input": { fontFamily: '"Fira Code", monospace' } }}
            />
          </Stack>

          <Typography variant="caption" sx={{ color: SURFACE.inkMuted }}>
            {remaining <= 0
              ? "The cycle is spent, so the plan will open with a 34-hour restart."
              : "Hours already on duty in the current 8-day cycle."}
          </Typography>
        </Box>

        <Box>
          <Button
            type="button"
            size="small"
            onClick={() => setShowDetails((open) => !open)}
            endIcon={
              <ExpandMoreIcon
                sx={{
                  transition: "transform 180ms cubic-bezier(0.16,1,0.3,1)",
                  transform: showDetails ? "rotate(180deg)" : "none",
                }}
              />
            }
            sx={{ px: 1, ml: -1, color: SURFACE.inkMuted, minHeight: 36 }}
          >
            Driver and vehicle details
          </Button>

          <Collapse in={showDetails} timeout={220}>
            <Stack spacing={2} sx={{ pt: 2 }}>
              <Typography variant="caption" sx={{ color: SURFACE.inkMuted }}>
                Optional. These print on the log sheets, which look unfinished
                without them.
              </Typography>
              <TextField
                label="Driver name"
                value={driver}
                onChange={(event) => setDriver(event.target.value)}
                fullWidth
                size="small"
              />
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField
                  label="Carrier"
                  value={carrier}
                  onChange={(event) => setCarrier(event.target.value)}
                  fullWidth
                  size="small"
                />
                <TextField
                  label="Truck / trailer no."
                  value={truck}
                  onChange={(event) => setTruck(event.target.value)}
                  fullWidth
                  size="small"
                />
              </Stack>
            </Stack>
          </Collapse>
        </Box>

        {errorMessage && (
          <Alert severity="error" variant="outlined" sx={{ ...riseIn(0) }}>
            {errorMessage}
          </Alert>
        )}

        <Divider sx={{ borderColor: SURFACE.line }} />

        <Button
          type="submit"
          variant="contained"
          size="large"
          disabled={busy}
          startIcon={!busy && <LocalShippingIcon />}
          sx={{ py: 1.4 }}
        >
          {busy ? "Planning the trip…" : "Plan trip"}
        </Button>
      </Stack>
    </Paper>
  );
}

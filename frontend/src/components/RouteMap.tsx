import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";

import { DURATION, STAGGER_MS } from "../theme/motion";
import { STOP_COLOURS, STOP_GLYPHS, SURFACE } from "../theme/tokens";
import type { Stop, Trip } from "../types/trip";

/** CARTO's dark basemap. No key, and the cyan route reads clearly on it. */
const TILES = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';

/**
 * A stop marker: a coloured disc carrying its sequence number.
 *
 * Built as a divIcon rather than an image so the colours come from the same
 * tokens the timeline and the log sheets use, and so each one can carry its
 * own animation delay and land in sequence.
 */
function stopIcon(stop: Stop, index: number): L.DivIcon {
  const colour = STOP_COLOURS[stop.kind];
  const glyph = STOP_GLYPHS[stop.kind];
  const size = stop.kind === "start" || stop.kind === "dropoff" ? 30 : 25;

  return L.divIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `
      <div style="
        width:${size}px;height:${size}px;border-radius:50%;
        background:${colour};color:#06111F;
        display:flex;align-items:center;justify-content:center;
        font:600 ${size > 27 ? 12 : 11}px/1 'Fira Code',monospace;
        border:2px solid rgba(6,17,31,0.85);
        box-shadow:0 3px 10px rgba(0,0,0,0.55);
        animation:pop ${DURATION.enter}ms cubic-bezier(0.34,1.56,0.64,1) both;
        animation-delay:${400 + index * STAGGER_MS}ms;
      ">${glyph}</div>`,
  });
}

/**
 * Keep the whole route in frame.
 *
 * Refits when the route changes and again whenever the container is resized.
 * Without the second part, a map framed on a desktop layout keeps that
 * viewport after the grid reflows to a single column, and both ends of the
 * route end up outside the visible area. Leaflet also has to be told its own
 * size changed before it can recompute the fit.
 */
function FitToRoute({ bbox }: { bbox: Trip["route"]["bbox"] }) {
  const map = useMap();

  useEffect(() => {
    const [west, south, east, north] = bbox;

    const fit = () => {
      map.invalidateSize({ animate: false });
      map.fitBounds(
        [
          [south, west],
          [north, east],
        ],
        { padding: [40, 40], animate: false },
      );
    };

    fit();

    const observer = new ResizeObserver(() => {
      // The next frame, so the fit sees the settled size rather than the one
      // mid-reflow.
      requestAnimationFrame(fit);
    });
    observer.observe(map.getContainer());

    return () => observer.disconnect();
  }, [map, bbox]);

  return null;
}

/**
 * Trace the route rather than flicking it on.
 *
 * Leaflet renders a Polyline as an SVG path but sets no pathLength, so a dash
 * pattern would depend on the route's real length in pixels and change with
 * every zoom. Setting pathLength to 1 normalises it, after which one CSS
 * animation draws any route in the same time regardless of how long it is.
 */
function useDrawOnMount(reference: React.RefObject<L.Polyline | null>, trigger: string) {
  useEffect(() => {
    const path = reference.current?.getElement() as SVGPathElement | undefined;
    if (!path) return;

    path.setAttribute("pathLength", "1");
    path.style.strokeDasharray = "1";
    path.style.strokeDashoffset = "1";
    path.style.animation = `draw ${DURATION.draw}ms cubic-bezier(0.65,0,0.35,1) both`;
    path.style.animationDelay = "120ms";
  }, [reference, trigger]);
}

function Legend({ stops }: { stops: Stop[] }) {
  const kinds = Array.from(new Set(stops.map((stop) => stop.kind)));

  return (
    <Stack
      direction="row"
      spacing={1.5}
      sx={{ flexWrap: "wrap", rowGap: 1, px: 0.5, pt: 1.5 }}
    >
      {kinds.map((kind) => {
        const label = stops.find((stop) => stop.kind === kind)!.title;
        return (
          <Stack
            key={kind}
            direction="row"
            spacing={0.75}
            sx={{ alignItems: "center" }}
          >
            <Box
              sx={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                backgroundColor: STOP_COLOURS[kind],
                flexShrink: 0,
              }}
            />
            <Typography variant="caption" sx={{ color: SURFACE.inkMuted }}>
              {label}
            </Typography>
          </Stack>
        );
      })}
    </Stack>
  );
}

export function RouteMap({ trip }: { trip: Trip }) {
  const line = useRef<L.Polyline | null>(null);
  useDrawOnMount(line, trip.id);

  const centre: [number, number] = [
    (trip.route.bbox[1] + trip.route.bbox[3]) / 2,
    (trip.route.bbox[0] + trip.route.bbox[2]) / 2,
  ];

  return (
    <Box>
      <Box
        sx={{
          height: { xs: 320, sm: 400, lg: 460 },
          borderRadius: 3,
          overflow: "hidden",
          border: `1px solid ${SURFACE.line}`,
          position: "relative",
        }}
      >
        <MapContainer
          center={centre}
          zoom={5}
          scrollWheelZoom={false}
          style={{ height: "100%", width: "100%" }}
          attributionControl
        >
          <TileLayer url={TILES} attribution={ATTRIBUTION} maxZoom={19} />
          <FitToRoute bbox={trip.route.bbox} />

          {/* A wide, faint pass under the route gives the line a glow without
              a filter, which would cost a repaint on every pan. */}
          <Polyline
            positions={trip.route.geometry}
            pathOptions={{
              color: SURFACE.accent,
              weight: 11,
              opacity: 0.16,
              lineCap: "round",
            }}
          />
          <Polyline
            ref={line}
            positions={trip.route.geometry}
            pathOptions={{
              color: SURFACE.accent,
              weight: 3.5,
              opacity: 0.95,
              lineCap: "round",
            }}
          />

          {trip.stops.map((stop, index) => (
            <Marker
              key={stop.seq}
              position={[stop.latitude, stop.longitude]}
              icon={stopIcon(stop, index)}
            >
              <Popup>
                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                  {stop.title}
                </Typography>
                <Typography variant="body2" sx={{ color: SURFACE.inkMuted }}>
                  {stop.location}
                </Typography>
                <Typography
                  className="tabular"
                  variant="caption"
                  sx={{ display: "block", mt: 0.75 }}
                >
                  Mile {stop.mile_marker.toLocaleString()}
                  {stop.duration_hours > 0 && ` · ${stop.duration_hours} h`}
                </Typography>
                <Typography
                  className="tabular"
                  variant="caption"
                  sx={{ color: SURFACE.inkMuted }}
                >
                  {formatWhen(stop.arrive ?? stop.depart)}
                </Typography>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </Box>

      <Legend stops={trip.stops} />
    </Box>
  );
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import { DURATION } from "../theme/motion";
import { SURFACE } from "../theme/tokens";

/**
 * What the results column shows before anything has been planned.
 *
 * A drawn miniature of the duty grid rather than a placeholder box: it
 * previews what the app produces, and it says what this tool is for faster
 * than a paragraph would.
 */
export function EmptyState() {
  const rows = ["Off duty", "Sleeper", "Driving", "On duty"];

  // A plausible day: overnight off, on duty at the dock, a long drive with a
  // break in it, then into the bunk.
  const strokes = [
    { row: 0, from: 0, to: 26 },
    { row: 3, from: 26, to: 32 },
    { row: 2, from: 32, to: 63 },
    { row: 0, from: 63, to: 68 },
    { row: 2, from: 68, to: 82 },
    { row: 1, from: 82, to: 100 },
  ];

  return (
    <Stack
      sx={{
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        py: { xs: 5, md: 9 },
        px: 2,
      }}
    >
      <Box
        component="svg"
        viewBox="0 0 320 96"
        aria-hidden
        sx={{ width: "100%", maxWidth: 340, mb: 3 }}
      >
        {rows.map((label, index) => (
          <g key={label}>
            <line
              x1="0"
              x2="320"
              y1={16 + index * 22}
              y2={16 + index * 22}
              stroke={SURFACE.line}
              strokeWidth="1"
            />
            <text
              x="0"
              y={11 + index * 22}
              fill={SURFACE.inkMuted}
              fontSize="7"
              fontFamily="Fira Sans, sans-serif"
              opacity="0.75"
            >
              {label}
            </text>
          </g>
        ))}

        {strokes.map((stroke, index) => (
          <line
            key={index}
            x1={(stroke.from / 100) * 320}
            x2={(stroke.to / 100) * 320}
            y1={16 + stroke.row * 22}
            y2={16 + stroke.row * 22}
            stroke={SURFACE.accent}
            strokeWidth="2.5"
            strokeLinecap="round"
            pathLength={1}
            style={{
              strokeDasharray: 1,
              strokeDashoffset: 1,
              animation: `draw ${DURATION.draw}ms cubic-bezier(0.65,0,0.35,1) both`,
              animationDelay: `${220 + index * 130}ms`,
            }}
          />
        ))}
      </Box>

      <Typography variant="h3" sx={{ mb: 0.75 }}>
        No trip planned yet
      </Typography>
      <Typography
        variant="body2"
        sx={{ color: SURFACE.inkMuted, maxWidth: 430, lineHeight: 1.7 }}
      >
        Enter where the driver is, where the load is picked up and dropped off,
        and how much of the 70-hour cycle is already spent. You get the route,
        every stop the rules require, and a filled-in log sheet for each day.
      </Typography>
    </Stack>
  );
}

import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import { SURFACE } from "../theme/tokens";

/** The route glyph from the favicon, so the tab and the page agree. */
function Mark() {
  return (
    <Box
      component="svg"
      viewBox="0 0 32 32"
      aria-hidden
      sx={{ width: 30, height: 30, flexShrink: 0 }}
    >
      <rect width="32" height="32" rx="8" fill="#131C2E" stroke="#24324D" />
      <path
        d="M5 21h22M5 15h22M5 9h22"
        stroke={SURFACE.accent}
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.22"
      />
      <path
        d="M5 21h6v-6h7v-6h9"
        stroke={SURFACE.accent}
        strokeWidth="2.4"
        strokeLinejoin="round"
        strokeLinecap="round"
        fill="none"
      />
    </Box>
  );
}

export function AppHeader() {
  return (
    <Box
      component="header"
      className="no-print"
      sx={{
        position: "sticky",
        top: 0,
        zIndex: 1100,
        borderBottom: `1px solid ${SURFACE.line}`,
        backdropFilter: "blur(14px)",
        backgroundColor: "rgba(11,18,32,0.78)",
      }}
    >
      <Container maxWidth="xl">
        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", py: 1.5 }}>
          <Mark />
          <Box>
            <Typography variant="h4" sx={{ lineHeight: 1.2 }}>
              ELD Trip Planner
            </Typography>
            <Typography
              variant="caption"
              sx={{ color: SURFACE.inkMuted, letterSpacing: "0.02em" }}
            >
              Hours of service under 49 CFR 395.3
            </Typography>
          </Box>
        </Stack>
      </Container>
    </Box>
  );
}

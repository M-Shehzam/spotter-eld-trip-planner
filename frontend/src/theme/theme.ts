import { createTheme } from "@mui/material/styles";

import { DURATION, EASING } from "./motion";
import { SURFACE } from "./tokens";

/**
 * Dark only, on purpose.
 *
 * A dispatcher reads this in a cab or an office at four in the morning, and
 * the log sheets carry their own light background because paper forms are
 * black on white and pretending otherwise would make them harder to check
 * against the real thing.
 *
 * Fira Sans for text, Fira Code for anything numeric. Almost every panel here
 * is a column of hours or miles, and tabular figures stop them shifting as
 * they update.
 */
export const theme = createTheme({
  cssVariables: true,
  palette: {
    mode: "dark",
    primary: { main: SURFACE.accent, contrastText: "#062032" },
    secondary: { main: "#818CF8" },
    success: { main: SURFACE.good },
    warning: { main: SURFACE.warn },
    error: { main: SURFACE.bad },
    background: { default: SURFACE.page, paper: SURFACE.card },
    text: { primary: SURFACE.ink, secondary: SURFACE.inkMuted },
    divider: SURFACE.line,
  },

  shape: { borderRadius: 12 },

  typography: {
    fontFamily: '"Fira Sans", system-ui, -apple-system, sans-serif',
    h1: { fontSize: "1.9rem", fontWeight: 600, letterSpacing: "-0.02em" },
    h2: { fontSize: "1.4rem", fontWeight: 600, letterSpacing: "-0.015em" },
    h3: { fontSize: "1.1rem", fontWeight: 600 },
    h4: { fontSize: "1rem", fontWeight: 600 },
    body1: { fontSize: "0.95rem", lineHeight: 1.6 },
    body2: { fontSize: "0.85rem", lineHeight: 1.6 },
    button: { textTransform: "none", fontWeight: 600, letterSpacing: 0 },
    overline: {
      fontSize: "0.68rem",
      fontWeight: 600,
      letterSpacing: "0.1em",
      lineHeight: 1.6,
    },
  },

  components: {
    MuiCssBaseline: {
      styleOverrides: {
        // A focus ring that is visible on every surface in the palette,
        // rather than the browser default that disappears on dark blue.
        "*:focus-visible": {
          outline: `2px solid ${SURFACE.accent}`,
          outlineOffset: 2,
          borderRadius: 6,
        },
        "::selection": { background: "rgba(56,189,248,0.28)" },
      },
    },

    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          border: `1px solid ${SURFACE.line}`,
        },
        elevation0: { border: "none" },
      },
    },

    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          borderRadius: 10,
          // Comfortably past the 44px touch minimum without looking chunky.
          minHeight: 44,
          paddingInline: 18,
          transition: `background-color ${DURATION.micro}ms ${EASING.out},
                       transform ${DURATION.instant}ms ${EASING.out},
                       box-shadow ${DURATION.micro}ms ${EASING.out}`,
          "&:active": { transform: "scale(0.985)" },
        },
      },
      // Per-variant styling moved to the variants array in MUI v6; the old
      // containedPrimary class key no longer exists.
      variants: [
        {
          props: { variant: "contained", color: "primary" },
          style: {
            boxShadow: "0 8px 24px -10px rgba(56,189,248,0.75)",
            "&:hover": { boxShadow: "0 12px 30px -10px rgba(56,189,248,0.85)" },
          },
        },
      ],
    },

    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          backgroundColor: "rgba(255,255,255,0.02)",
          transition: `border-color ${DURATION.micro}ms ${EASING.out},
                       background-color ${DURATION.micro}ms ${EASING.out}`,
          "&:hover": { backgroundColor: "rgba(255,255,255,0.04)" },
          "&.Mui-focused": { backgroundColor: "rgba(56,189,248,0.06)" },
        },
        // 16px stops iOS Safari zooming the page when a field takes focus.
        input: { fontSize: "1rem" },
      },
    },

    MuiInputLabel: {
      styleOverrides: {
        root: { fontSize: "0.95rem" },
      },
    },

    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 500, borderRadius: 8 },
        sizeSmall: { height: 24 },
      },
    },

    MuiTooltip: {
      defaultProps: { arrow: true },
      styleOverrides: {
        tooltip: {
          backgroundColor: SURFACE.raised,
          border: `1px solid ${SURFACE.line}`,
          fontSize: "0.78rem",
          padding: "7px 11px",
        },
        arrow: { color: SURFACE.raised },
      },
    },

    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 600,
          minHeight: 46,
          transition: `color ${DURATION.micro}ms ${EASING.out}`,
        },
      },
    },

    MuiSlider: {
      styleOverrides: {
        thumb: {
          width: 20,
          height: 20,
          "&::before": { boxShadow: "0 2px 8px rgba(0,0,0,0.5)" },
          "&:hover, &.Mui-focusVisible": {
            boxShadow: "0 0 0 9px rgba(56,189,248,0.16)",
          },
        },
        rail: { opacity: 0.28 },
        valueLabel: {
          backgroundColor: SURFACE.raised,
          border: `1px solid ${SURFACE.line}`,
          fontFamily: '"Fira Code", monospace',
        },
      },
    },

    MuiSkeleton: {
      styleOverrides: {
        root: { backgroundColor: "rgba(255,255,255,0.055)" },
      },
    },

    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 10, alignItems: "center" },
      },
    },
  },
});

/**
 * One rhythm for everything that moves.
 *
 * The rules this follows, and why each one is here:
 *
 * - Micro-interactions stay between 150 and 300ms. Anything slower reads as
 *   lag rather than polish.
 * - Only transform and opacity are animated. Animating width, height or top
 *   forces layout on every frame and drops the map to single digits.
 * - Entrances ease out, exits ease in, and exits run at about two thirds the
 *   duration, so dismissing something feels immediate.
 * - Two motions per view carry meaning; everything else is a fade. The route
 *   drawing itself and the duty line drawing itself are the two that earn
 *   their length.
 * - Every one of them is switched off under prefers-reduced-motion, handled
 *   once in index.css rather than at each call site.
 */

export const DURATION = {
  instant: 120,
  micro: 180,
  enter: 260,
  exit: 170,
  /** The route tracing itself across the map, and the duty line across a log. */
  draw: 1100,
} as const;

export const EASING = {
  /** Entrances: fast then settling. */
  out: "cubic-bezier(0.16, 1, 0.3, 1)",
  /** Exits: gathers speed on the way out. */
  in: "cubic-bezier(0.7, 0, 0.84, 0)",
  /** Both ends, for things that move between two resting states. */
  inOut: "cubic-bezier(0.65, 0, 0.35, 1)",
  /** A little overshoot, for markers landing on the map. */
  overshoot: "cubic-bezier(0.34, 1.56, 0.64, 1)",
} as const;

/** 40ms between siblings: enough to read as a sequence, not enough to wait for. */
export const STAGGER_MS = 40;

export function staggerDelay(index: number, step = STAGGER_MS): string {
  return `${index * step}ms`;
}

/** Fade and rise. The default entrance for a panel or a card. */
export function riseIn(index = 0) {
  return {
    animation: `rise ${DURATION.enter}ms ${EASING.out} both`,
    animationDelay: staggerDelay(index),
  } as const;
}

/** Fade only. For content swapping inside a container that is already there. */
export function fadeIn(index = 0) {
  return {
    animation: `fade ${DURATION.enter}ms ${EASING.out} both`,
    animationDelay: staggerDelay(index),
  } as const;
}

/** Land with a slight overshoot. Map markers and status pills. */
export function popIn(index = 0) {
  return {
    animation: `pop ${DURATION.enter}ms ${EASING.overshoot} both`,
    animationDelay: staggerDelay(index),
  } as const;
}

/**
 * Draw a path from its start to its end.
 *
 * The caller has to know the path length so the dash pattern can cover it;
 * `pathLength={1}` on the SVG element normalises that to 1 and lets this work
 * without measuring anything.
 */
export function drawPath(delayMs = 0, durationMs: number = DURATION.draw) {
  return {
    strokeDasharray: 1,
    strokeDashoffset: 1,
    animation: `draw ${durationMs}ms ${EASING.inOut} both`,
    animationDelay: `${delayMs}ms`,
  } as const;
}

/** Presses feel connected when the surface gives a little. */
export const PRESSABLE = {
  transition: `transform ${DURATION.instant}ms ${EASING.out}`,
  "&:active": { transform: "scale(0.985)" },
} as const;

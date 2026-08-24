/**
 * The driver's daily log, drawn.
 *
 * A redraw of the paper form rather than a chart that resembles one: the same
 * header fields in the same places, the black hour strip, four duty rows over
 * a quarter-hour grid, the totals column, the remarks with a tick at the time
 * each one happened, and the recap boxes. What a driver draws by hand, the
 * planner draws from the plan.
 *
 * It renders as SVG for three reasons. It stays sharp when printed, which is
 * the point of a log sheet. The duty line is one path, so it can draw itself.
 * And it exports to PNG through a canvas without a screenshot library.
 */

import { DUTY_INK, DUTY_ROWS, PAPER } from "../../theme/tokens";
import { DURATION, EASING } from "../../theme/motion";
import type { DutyStatus, LogSheet, TripInputs } from "../../types/trip";
import {
  GRID,
  GRID_BOTTOM,
  GRID_X1,
  REMARKS,
  SHEET,
  SHEET_X1,
  dutyLinePath,
  formatHours,
  hourX,
  layOutRemarks,
  rowCentre,
  rowTop,
} from "./sheet-layout";

const ROW_LABELS = [
  "1. Off Duty",
  "2. Sleeper Berth",
  "3. Driving",
  "4. On Duty (not driving)",
];

/** Short text. Defaults match the small print on the form. */
function T({
  x,
  y,
  size = 9,
  weight = 400,
  anchor = "start",
  fill = PAPER.ink,
  mono = false,
  children,
}: {
  x: number;
  y: number;
  size?: number;
  weight?: number;
  anchor?: "start" | "middle" | "end";
  fill?: string;
  mono?: boolean;
  children: React.ReactNode;
}) {
  return (
    <text
      x={x}
      y={y}
      fontSize={size}
      fontWeight={weight}
      textAnchor={anchor}
      fill={fill}
      fontFamily={
        mono
          ? "'Fira Code', ui-monospace, Menlo, monospace"
          : "'Fira Sans', Helvetica, Arial, sans-serif"
      }
    >
      {children}
    </text>
  );
}

/** A labelled rule with a value written above it, as on the paper form. */
function Field({
  x,
  y,
  width,
  label,
  value,
}: {
  x: number;
  y: number;
  width: number;
  label: string;
  value?: string;
}) {
  return (
    <g>
      {value && (
        <T x={x + width / 2} y={y - 5} size={11} weight={500} anchor="middle" mono>
          {value}
        </T>
      )}
      <line x1={x} y1={y} x2={x + width} y2={y} stroke={PAPER.rule} strokeWidth={1} />
      <T x={x + width / 2} y={y + 11} size={8} anchor="middle" fill={PAPER.rule}>
        {label}
      </T>
    </g>
  );
}

/** A boxed value with its caption underneath. The two mileage boxes. */
function ValueBox({
  x,
  y,
  width,
  height,
  label,
  value,
}: {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  value: string;
}) {
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill="none"
        stroke={PAPER.rule}
        strokeWidth={1.1}
      />
      <T x={x + width / 2} y={y + height / 2 + 5} size={14} weight={600} anchor="middle" mono>
        {value}
      </T>
      <T x={x + width / 2} y={y + height + 11} size={8} anchor="middle" fill={PAPER.rule}>
        {label}
      </T>
    </g>
  );
}

function Header({ sheet, inputs }: { sheet: LogSheet; inputs: TripInputs }) {
  const [year, month, day] = sheet.date.split("-");
  const M = SHEET.margin;

  return (
    <g>
      <T x={M} y={46} size={23} weight={700}>
        Driver&apos;s Daily Log
      </T>
      <T x={M} y={61} size={9} fill={PAPER.rule}>
        (24 hours)
      </T>

      {/* Date, one rule per part, as the form splits it. */}
      <Field x={300} y={44} width={60} label="(month)" value={month} />
      <T x={368} y={44} size={13}>
        /
      </T>
      <Field x={378} y={44} width={54} label="(day)" value={day} />
      <T x={440} y={44} size={13}>
        /
      </T>
      <Field x={450} y={44} width={70} label="(year)" value={year} />

      <T x={SHEET_X1} y={32} size={8.5} anchor="end" fill={PAPER.rule}>
        Original - File at home terminal.
      </T>
      <T x={SHEET_X1} y={46} size={8.5} anchor="end" fill={PAPER.rule}>
        Duplicate - Driver retains in his/her possession for 8 days.
      </T>
      <T x={SHEET_X1} y={62} size={8.5} anchor="end" weight={500}>
        Sheet {sheet.sheet_number} of {sheet.of}
      </T>

      {/* Where the day started and where it ended. */}
      <T x={M} y={96} size={10} weight={600}>
        From:
      </T>
      <T x={M + 40} y={96} size={10.5} mono>
        {sheet.from_label}
      </T>
      <line x1={M + 36} y1={100} x2={470} y2={100} stroke={PAPER.rule} />
      <T x={500} y={96} size={10} weight={600}>
        To:
      </T>
      <T x={528} y={96} size={10.5} mono>
        {sheet.to_label}
      </T>
      <line x1={524} y1={100} x2={SHEET_X1} y2={100} stroke={PAPER.rule} />

      <ValueBox
        x={M}
        y={118}
        width={148}
        height={34}
        label="Total Miles Driving Today"
        value={Math.round(sheet.total_miles_driving).toLocaleString()}
      />
      <ValueBox
        x={188}
        y={118}
        width={148}
        height={34}
        label="Total Mileage Today"
        value={Math.round(sheet.total_mileage).toLocaleString()}
      />
      <g>
        <rect
          x={M}
          y={176}
          width={312}
          height={26}
          fill="none"
          stroke={PAPER.rule}
          strokeWidth={1.1}
        />
        <T x={M + 156} y={193} size={10} anchor="middle" mono>
          {inputs.truck_number}
        </T>
        <T x={M + 156} y={213} size={7.5} anchor="middle" fill={PAPER.rule}>
          Truck/Tractor and Trailer Numbers or License Plate(s)/State (show each unit)
        </T>
      </g>

      <Field
        x={400}
        y={140}
        width={SHEET_X1 - 400}
        label="Name of Carrier or Carriers"
        value={inputs.carrier_name}
      />
      {/* The office address is not something the planner is told, so its
          rule stays empty rather than being filled with the pickup. The home
          terminal is known: the trip starts there and every time on the sheet
          is in its zone, which is what the form asks for. */}
      <Field x={400} y={176} width={SHEET_X1 - 400} label="Main Office Address" />
      <Field
        x={400}
        y={212}
        width={SHEET_X1 - 400}
        label="Home Terminal Address"
        value={inputs.current_location.label}
      />
    </g>
  );
}

/** The 24-hour grid: hour strip, four rows, quarter-hour ticks, totals column. */
function Grid({ sheet }: { sheet: LogSheet }) {
  const hours = Array.from({ length: GRID.hours + 1 }, (_, hour) => hour);

  return (
    <g>
      {/* The black strip. Hour numbers sit on the lines, not between them. */}
      <rect
        x={GRID.x0 - GRID.headerOverhang}
        y={GRID.headerTop}
        width={SHEET_X1 - GRID.x0 + GRID.headerOverhang}
        height={GRID.headerHeight}
        fill={PAPER.strip}
      />
      {hours.map((hour) => {
        const label =
          hour === 0 || hour === 24 ? "Mid-\nnight" : hour === 12 ? "Noon" : String(hour % 12);
        const lines = label.split("\n");
        return (
          <text
            key={hour}
            x={hourX(hour)}
            y={GRID.headerTop + (lines.length > 1 ? 11 : 17)}
            fontSize={lines.length > 1 ? 7.5 : 9}
            fontWeight={600}
            textAnchor="middle"
            fill={PAPER.stripInk}
            fontFamily="'Fira Sans', Helvetica, Arial, sans-serif"
          >
            {lines.map((line, index) => (
              <tspan key={line} x={hourX(hour)} dy={index === 0 ? 0 : 9}>
                {line}
              </tspan>
            ))}
          </text>
        );
      })}
      <T
        x={(GRID_X1 + SHEET_X1) / 2}
        y={GRID.headerTop + 11}
        size={7.5}
        weight={600}
        anchor="middle"
        fill={PAPER.stripInk}
      >
        Total
      </T>
      <T
        x={(GRID_X1 + SHEET_X1) / 2}
        y={GRID.headerTop + 20}
        size={7.5}
        weight={600}
        anchor="middle"
        fill={PAPER.stripInk}
      >
        Hours
      </T>

      {/* Row labels, outside the grid on the left. */}
      {ROW_LABELS.map((label, index) => (
        <T key={label} x={SHEET.margin} y={rowCentre((index + 1) as 1) + 3} size={8.5} weight={500}>
          {label}
        </T>
      ))}

      {/* Quarter-hour ticks, drawn down from the top of each row. The
          half-hour tick runs longer, which is how a driver finds 30 past. */}
      {DUTY_ROWS.map((_, rowIndex) =>
        Array.from({ length: GRID.hours }, (_, hour) =>
          [1, 2, 3].map((quarter) => {
            const x = hourX(hour) + (quarter * GRID.hourWidth) / 4;
            const top = rowTop((rowIndex + 1) as 1);
            return (
              <line
                key={`${rowIndex}-${hour}-${quarter}`}
                x1={x}
                y1={top}
                x2={x}
                y2={top + (quarter === 2 ? 9 : 5)}
                stroke={PAPER.hairline}
                strokeWidth={0.6}
              />
            );
          }),
        ),
      )}

      {/* Hour lines, then the row lines over them. */}
      {hours.map((hour) => (
        <line
          key={`h${hour}`}
          x1={hourX(hour)}
          y1={GRID.top}
          x2={hourX(hour)}
          y2={GRID_BOTTOM}
          stroke={PAPER.rule}
          strokeWidth={hour % 24 === 0 ? 1.2 : 0.8}
        />
      ))}
      {Array.from({ length: GRID.rows + 1 }, (_, index) => (
        <line
          key={`r${index}`}
          x1={GRID.x0}
          y1={GRID.top + index * GRID.rowHeight}
          x2={SHEET_X1}
          y2={GRID.top + index * GRID.rowHeight}
          stroke={PAPER.rule}
          strokeWidth={index === 0 || index === GRID.rows ? 1.2 : 0.8}
        />
      ))}
      <line
        x1={GRID_X1}
        y1={GRID.top}
        x2={GRID_X1}
        y2={GRID_BOTTOM}
        stroke={PAPER.rule}
        strokeWidth={1.2}
      />
      <line
        x1={SHEET_X1}
        y1={GRID.top}
        x2={SHEET_X1}
        y2={GRID_BOTTOM}
        stroke={PAPER.rule}
        strokeWidth={1.2}
      />

      {/* The totals column, one figure per row, coloured to its status. */}
      {DUTY_ROWS.map((status, index) => (
        <T
          key={status}
          x={(GRID_X1 + SHEET_X1) / 2}
          y={rowCentre((index + 1) as 1) + 4}
          size={11}
          weight={600}
          anchor="middle"
          fill={DUTY_INK[status]}
          mono
        >
          {formatHours(sheet.totals[status] ?? 0)}
        </T>
      ))}

      {/* The day has to add up to 24. Printing the sum says so. */}
      <T
        x={(GRID_X1 + SHEET_X1) / 2}
        y={GRID_BOTTOM + 12}
        size={9}
        weight={600}
        anchor="middle"
        mono
      >
        = {formatHours(Object.values(sheet.totals).reduce((sum, hours) => sum + hours, 0))}
      </T>
    </g>
  );
}

/**
 * The duty line, and the shading under the driving hours.
 *
 * The shading is the one departure from the paper form. On paper the driving
 * row is found by counting rows; on screen a wash under the driving runs
 * makes the day's shape readable at a glance, and it prints as a light grey
 * that does not fight the line.
 */
function DutyLine({ sheet, animate }: { sheet: LogSheet; animate: boolean }) {
  const path = dutyLinePath(sheet.entries);

  return (
    <g>
      {sheet.entries.map((entry, index) => (
        <rect
          key={`${entry.start_hour}-${index}`}
          x={hourX(entry.start_hour)}
          y={rowTop(entry.row) + 1}
          width={hourX(entry.end_hour) - hourX(entry.start_hour)}
          height={GRID.rowHeight - 2}
          fill={DUTY_INK[entry.status]}
          opacity={0.1}
        />
      ))}

      <path
        data-duty-line
        d={path}
        fill="none"
        stroke={PAPER.ink}
        strokeWidth={2.4}
        strokeLinejoin="round"
        strokeLinecap="round"
        pathLength={1}
        style={
          animate
            ? {
                strokeDasharray: 1,
                strokeDashoffset: 1,
                animation: `draw ${DURATION.draw}ms ${EASING.inOut} both`,
                animationDelay: "260ms",
              }
            : undefined
        }
      />
    </g>
  );
}

function Remarks({ sheet }: { sheet: LogSheet }) {
  const ticks = layOutRemarks(sheet.remarks);

  return (
    <g>
      <rect
        x={SHEET.margin}
        y={REMARKS.top}
        width={SHEET_X1 - SHEET.margin}
        height={REMARKS.height}
        fill="none"
        stroke={PAPER.rule}
        strokeWidth={1.1}
      />
      <T x={SHEET.margin + 8} y={REMARKS.top + 16} size={11} weight={700}>
        Remarks
      </T>

      {/* The same hour scale as the grid, so a tick sits under its own change
          of duty status. */}
      <line
        x1={GRID.x0}
        y1={REMARKS.ruleY}
        x2={GRID_X1}
        y2={REMARKS.ruleY}
        stroke={PAPER.hairline}
        strokeWidth={0.8}
      />

      {ticks.map((tick, index) => {
        const labelY = REMARKS.ruleY + 4 + tick.lane * 5;
        return (
          <g key={`${tick.hour}-${index}`}>
            <line
              x1={tick.x}
              y1={REMARKS.ruleY - 7}
              x2={tick.x}
              y2={labelY}
              stroke={DUTY_INK.on_duty}
              strokeWidth={1.1}
            />
            <text
              x={tick.x + 3}
              y={labelY + 3}
              fontSize={8}
              fill={PAPER.ink}
              fontFamily="'Fira Sans', Helvetica, Arial, sans-serif"
              transform={`rotate(52 ${tick.x + 3} ${labelY + 3})`}
            >
              {tick.location}
            </text>
          </g>
        );
      })}
    </g>
  );
}

function ShippingAndInstructions({ inputs }: { inputs: TripInputs }) {
  const top = REMARKS.top + REMARKS.height + 12;

  return (
    <g>
      <T x={SHEET.margin} y={top + 12} size={9.5} weight={600}>
        Shipping Documents:
      </T>
      <T x={SHEET.margin} y={top + 34} size={8.5} fill={PAPER.rule}>
        DVL or Manifest No.
      </T>
      <line
        x1={SHEET.margin + 110}
        y1={top + 36}
        x2={340}
        y2={top + 36}
        stroke={PAPER.rule}
        strokeWidth={0.8}
      />
      <T x={SHEET.margin} y={top + 50} size={8.5} fill={PAPER.rule}>
        or
      </T>
      <T x={SHEET.margin} y={top + 66} size={8.5} fill={PAPER.rule}>
        Shipper &amp; Commodity
      </T>
      <line
        x1={SHEET.margin + 110}
        y1={top + 68}
        x2={340}
        y2={top + 68}
        stroke={PAPER.rule}
        strokeWidth={0.8}
      />

      <T x={640} y={top + 34} size={8.5} anchor="middle" fill={PAPER.rule}>
        Enter name of place you reported and where released from work and when
      </T>
      <T x={640} y={top + 47} size={8.5} anchor="middle" fill={PAPER.rule}>
        and where each change of duty occurred.
      </T>
      <T x={640} y={top + 64} size={8.5} anchor="middle" weight={600}>
        Use time standard of home terminal.
      </T>

      {/* The driver signs the sheet. The form is a certification, not a
          report, and the optional name the trip form collects belongs here
          rather than nowhere. */}
      <Field
        x={SHEET.margin}
        y={top + 104}
        width={316}
        label="Driver's signature (in full)"
        value={inputs.driver_name}
      />
    </g>
  );
}

/**
 * The recap boxes.
 *
 * The captions follow the regulation rather than the scanned blank, which
 * prints a 70-hour limit measured over 7 days in one box and 5 days in the
 * next. The 70-hour cycle runs over 8 days, so box A carries the 8-day total,
 * box B carries what is left of the 70, and box C carries the 7-day total.
 *
 * Box C stays empty until the trip has run 7 days. The driver gives one
 * cycle figure with no day-by-day breakdown, so before then there is nothing
 * to put in it but a guess.
 */
function Recap({ sheet }: { sheet: LogSheet }) {
  const top = SHEET.height - 108;
  const boxes: Array<{ x: number; letter: string; caption: string[]; value: number | null }> = [
    {
      x: 338,
      letter: "A",
      caption: ["Total hours on duty", "last 8 days including today."],
      value: sheet.recap.on_duty_last_8,
    },
    {
      x: 500,
      letter: "B",
      caption: ["Total hours available", "tomorrow. 70 hr. minus A."],
      value: sheet.recap.available_tomorrow,
    },
    {
      x: 662,
      letter: "C",
      caption: ["Total hours on duty", "last 7 days including today."],
      value: sheet.recap.on_duty_last_7,
    },
  ];

  return (
    <g>
      <line
        x1={SHEET.margin}
        y1={top}
        x2={SHEET_X1}
        y2={top}
        stroke={PAPER.ink}
        strokeWidth={2}
      />

      <T x={SHEET.margin} y={top + 16} size={9} weight={600}>
        Recap:
      </T>
      <T x={SHEET.margin} y={top + 28} size={8.5} fill={PAPER.rule}>
        Complete at end of day
      </T>

      <ValueBox
        x={126}
        y={top + 14}
        width={110}
        height={30}
        label="On duty hours today, total lines 3 & 4"
        value={formatHours(sheet.recap.on_duty_today)}
      />

      <T x={262} y={top + 20} size={9} weight={700}>
        70 Hour /
      </T>
      <T x={262} y={top + 32} size={9} weight={700}>
        8 Day Drivers
      </T>

      {boxes.map((box) => (
        <g key={box.letter}>
          <T x={box.x} y={top + 20} size={11} weight={700}>
            {box.letter}.
          </T>
          <T x={box.x + 26} y={top + 20} size={13} weight={600} mono>
            {box.value === null ? "" : formatHours(box.value)}
          </T>
          <line
            x1={box.x + 20}
            y1={top + 24}
            x2={box.x + 140}
            y2={top + 24}
            stroke={PAPER.rule}
            strokeWidth={1}
          />
          {box.caption.map((line, index) => (
            <T key={line} x={box.x} y={top + 38 + index * 11} size={8} fill={PAPER.rule}>
              {line}
            </T>
          ))}
        </g>
      ))}

      {sheet.recap.on_duty_last_7 === null && (
        <T x={662} y={top + 62} size={7.5} fill={PAPER.rule}>
          Left blank: the trip has not yet run 7 days.
        </T>
      )}

      <T x={824} y={top + 20} size={7.5} fill={PAPER.rule}>
        *If you took 34 consecutive
      </T>
      <T x={824} y={top + 31} size={7.5} fill={PAPER.rule}>
        hours off duty you have
      </T>
      <T x={824} y={top + 42} size={7.5} fill={PAPER.rule}>
        60/70 hours available.
      </T>
    </g>
  );
}

export function LogSheetSvg({
  sheet,
  inputs,
  animate = true,
}: {
  sheet: LogSheet;
  inputs: TripInputs;
  animate?: boolean;
}) {
  const summary = DUTY_ROWS.map(
    (status: DutyStatus) => `${status.replace("_", " ")} ${formatHours(sheet.totals[status] ?? 0)}h`,
  ).join(", ");

  return (
    <svg
      viewBox={`0 0 ${SHEET.width} ${SHEET.height}`}
      width="100%"
      role="img"
      aria-label={`Driver's daily log for ${sheet.date}, sheet ${sheet.sheet_number} of ${sheet.of}. ${summary}.`}
      style={{ display: "block", background: PAPER.sheet }}
    >
      <rect width={SHEET.width} height={SHEET.height} fill={PAPER.sheet} />
      <Header sheet={sheet} inputs={inputs} />
      <Grid sheet={sheet} />
      <DutyLine sheet={sheet} animate={animate} />
      <Remarks sheet={sheet} />
      <ShippingAndInstructions inputs={inputs} />
      <Recap sheet={sheet} />
    </svg>
  );
}

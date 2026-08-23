import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";

import { fadeIn } from "../theme/motion";

/**
 * Placeholders shaped like what is coming.
 *
 * Planning takes a second or two, almost all of it the routing call, and a
 * spinner over an empty column makes that feel longer than it is. These match
 * the real layout so nothing jumps when the answer lands.
 */
export function TripSkeleton() {
  return (
    <Stack spacing={3} sx={{ ...fadeIn(0) }} aria-busy aria-label="Planning the trip">
      <Box
        sx={{
          display: "grid",
          gap: 1.5,
          gridTemplateColumns: {
            xs: "repeat(2, minmax(0, 1fr))",
            md: "repeat(3, minmax(0, 1fr))",
            xl: "repeat(6, minmax(0, 1fr))",
          },
        }}
      >
        {Array.from({ length: 6 }, (_, index) => (
          <Paper key={index} elevation={0} sx={{ p: 2, borderRadius: 2.5 }}>
            <Skeleton variant="text" width="55%" height={14} />
            <Skeleton variant="text" width="72%" height={34} />
            <Skeleton variant="text" width="85%" height={12} />
          </Paper>
        ))}
      </Box>

      <Skeleton
        variant="rounded"
        sx={{ height: { xs: 320, sm: 400, lg: 460 }, borderRadius: 3 }}
      />

      <Paper elevation={0} sx={{ p: 2.5, borderRadius: 3 }}>
        <Skeleton variant="text" width={180} height={26} />
        <Stack spacing={2} sx={{ mt: 2 }}>
          {Array.from({ length: 4 }, (_, index) => (
            <Stack key={index} direction="row" spacing={1.75}>
              <Skeleton variant="circular" width={26} height={26} />
              <Box sx={{ flex: 1 }}>
                <Skeleton variant="text" width="45%" height={16} />
                <Skeleton variant="text" width="30%" height={14} />
              </Box>
            </Stack>
          ))}
        </Stack>
      </Paper>
    </Stack>
  );
}

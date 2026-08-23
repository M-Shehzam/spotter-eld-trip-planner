import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import { usePlaceSuggestions } from "../hooks/usePlaceSuggestions";
import { SURFACE } from "../theme/tokens";

interface Props {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  icon: React.ReactNode;
  helperText?: string;
  error?: string;
  required?: boolean;
}

/**
 * A location input backed by the offline gazetteer.
 *
 * Free text is allowed rather than forced onto a selection: the server
 * accepts "Dallas", "Dallas, TX" and a raw coordinate pair, and refusing
 * anything not in the list would make the field feel broken for a driver
 * typing a place the list ranks low.
 */
export function LocationField({
  label,
  value,
  onChange,
  placeholder,
  icon,
  helperText,
  error,
  required,
}: Props) {
  const [typed, setTyped] = useState(value);
  const { options, loading } = usePlaceSuggestions(typed);

  return (
    <Autocomplete
      freeSolo
      autoHighlight
      options={options}
      filterOptions={(everything) => everything} // the server already ranked them
      inputValue={typed}
      value={value || null}
      loading={loading}
      onInputChange={(_, next) => {
        setTyped(next);
        onChange(next);
      }}
      onChange={(_, picked) => {
        const label = typeof picked === "string" ? picked : (picked?.label ?? "");
        setTyped(label);
        onChange(label);
      }}
      getOptionLabel={(option) =>
        typeof option === "string" ? option : option.label
      }
      isOptionEqualToValue={(option, selected) =>
        option.label === (typeof selected === "string" ? selected : selected?.label)
      }
      renderOption={(props, option) => {
        const { key, ...rest } = props as { key: string } & Record<string, unknown>;
        return (
          <Box
            component="li"
            key={key}
            {...rest}
            sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}
          >
            <Typography variant="body2">{option.name}</Typography>
            <Typography
              variant="caption"
              sx={{ color: SURFACE.inkMuted, flexShrink: 0 }}
            >
              {option.state}
              {option.population > 0 && (
                <Box component="span" className="tabular" sx={{ ml: 1, opacity: 0.7 }}>
                  {option.population.toLocaleString()}
                </Box>
              )}
            </Typography>
          </Box>
        );
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          placeholder={placeholder}
          required={required}
          error={Boolean(error)}
          helperText={error ?? helperText}
          slotProps={{
            ...params.slotProps,
            input: {
              ...params.slotProps.input,
              startAdornment: (
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    color: SURFACE.inkMuted,
                    mr: 1,
                    ml: 0.5,
                  }}
                >
                  {icon}
                </Box>
              ),
              endAdornment: (
                <>
                  {loading && <CircularProgress size={15} thickness={5} />}
                  {params.slotProps.input.endAdornment}
                </>
              ),
            },
          }}
        />
      )}
      slotProps={{
        paper: {
          sx: {
            mt: 0.5,
            border: `1px solid ${SURFACE.line}`,
            backgroundColor: SURFACE.raised,
            backgroundImage: "none",
          },
        },
      }}
    />
  );
}

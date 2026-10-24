import { Paper, Typography, Box } from "@mui/material";
import React from "react";

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon?: React.ReactNode;
}

export default function MetricCard({
  title,
  value,
  unit,
  icon,
}: MetricCardProps) {
  return (
    <Paper
      elevation={2}
      sx={{
        p: 3,
        borderRadius: 2,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: "100%",
      }}
    >
      <Box>
        <Typography
          variant="subtitle2"
          color="text.secondary"
          gutterBottom
          sx={{ fontWeight: "bold", textTransform: "uppercase" }}
        >
          {title}
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: "bold", color: "#166534" }}>
          {value}{" "}
          {unit && (
            <Typography component="span" variant="h6" color="text.secondary">
              {unit}
            </Typography>
          )}
        </Typography>
      </Box>
      {icon && <Box sx={{ color: "#166534", opacity: 0.8 }}>{icon}</Box>}
    </Paper>
  );
}

import { Box, Typography } from "@mui/material";

export default function Footer() {
  return (
    <Box
      component="footer"
      sx={{
        py: 3,
        px: 2,
        mt: "auto",
        backgroundColor: "#f3f4f6",
        textAlign: "center",
        borderTop: "1px solid #e5e7eb",
      }}
    >
      <Typography variant="body2" color="text.secondary">
        &copy; {new Date().getFullYear()} Smart Agriculture Monitoring System
        Project by Group 4.
      </Typography>
    </Box>
  );
}

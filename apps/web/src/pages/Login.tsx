import { Box, Typography, Button } from "@mui/material";

export default function Login() {
  return (
    <Box>
      <Typography>THIS IS THE LOGIN PAGE</Typography>
      <Button
        type="submit"
        variant="contained"
        sx={{ mt: 3, mb: 2, py: 1.5, fontWeight: "bold" }}
      >
        Sign In
      </Button>
    </Box>
  );
}

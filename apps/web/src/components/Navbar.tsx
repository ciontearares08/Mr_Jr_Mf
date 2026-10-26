import { Link as RouterLink } from "react-router-dom";
import { AppBar, Toolbar, Typography, Button, Box } from "@mui/material";
// import AgricultureIcon from "@mui/icons-material/Agriculture";

export default function Navbar() {
  return (
    <AppBar position="static" color="primary">
      <Toolbar sx={{ justifyContent: "space-between" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography sx={{ fontWeight: "bold" }} variant="h6" component="div">
            <Button
              color="inherit"
              component={RouterLink}
              to="/"
              sx={{ fontWeight: "bold" }}
            >
              Smart Agriculture
            </Button>
            {/* <AgricultureIcon /> */}
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 2 }}>
          <Button color="inherit" component={RouterLink} to="/dashboard">
            Dashboard
          </Button>
          <Button color="inherit" component={RouterLink} to="/login">
            Login
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
}

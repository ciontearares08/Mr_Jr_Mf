import { Outlet } from "react-router-dom";
import { Box } from "@mui/material";
import Navbar from "./Navbar";
import Footer from "./Footer";

export default function MainLayout() {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <Navbar />
      <Box
        component="main"
        sx={{
          flex: 1,
          p: 3,
          maxWidth: "1200px",
          mx: "auto",
          width: "100%",
          boxSizing: "border-box",
        }}
      >
        <Outlet />
      </Box>
      <Footer />
    </Box>
  );
}

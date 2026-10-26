import { Typography, Button, Container } from "@mui/material";
import { useNavigate } from "react-router-dom";

export default function Landing() {
  const navigate = useNavigate();

  return (
    <Container maxWidth="md" sx={{ textAlign: "center", py: 8 }}>
      <Typography
        variant="h3"
        component="h1"
        gutterBottom
        sx={{ fontWeight: "bold", color: "primary" }}
      >
        Smart Agriculture Monitoring System
      </Typography>
      <Typography variant="h6" sx={{ color: "text.secondary", mb: 4 }}>
        Using a combination of NDVI Satellite images and IRL metrics using IoT
        and a cloud backend to track crop health and predictive yields.
      </Typography>
      <Button
        variant="contained"
        size="large"
        onClick={() => navigate("/dashboard")}
        sx={{
          fontWeight: "bold",
          px: 4,
          py: 1.5,
        }}
      >
        View Live Dashboard
      </Button>
    </Container>
  );
}

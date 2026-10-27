import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import MainLayout from "./components/MainLayout";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Dashboard from "./components/Dashboard";

// 3. The Main App component wrapping your Dashboard in React Router
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* MainLayout supplies the Navbar (Header) and Footer */}
        <Route element={<MainLayout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

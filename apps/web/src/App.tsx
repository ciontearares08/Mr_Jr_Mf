import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import MainLayout from "./components/MainLayout";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Dashboard from "./components/Dashboard";
import { Spinner } from "@/components/ui/spinner";
import FieldMap from "./components/map/FieldMap";
import {
  GetField,
  JoinField,
  NewField,
  FieldSettings,
  FieldTimeline,
  FieldTrends,
  FieldTechnical,
} from "./pages/fields/FieldExport";

const DataExplorer = lazy(() => import("./pages/dev/DataExplorer"));
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
          <Route
            path="/dev/data"
            element={
              <Suspense
                fallback={
                  <div className="flex min-h-50 items-center justify-center">
                    <Spinner className="size-8 text-primary" />
                  </div>
                }
              >
                <DataExplorer />
              </Suspense>
            }
          />
          <Route path="/fieldmap" element={<FieldMap />} />
          {/* FIELD ROUTES */}
          <Route path="/fields/:id" element={<GetField />} />
          <Route path="/fields/join" element={<JoinField />} />
          <Route path="/fields/new" element={<NewField />} />
          <Route path="/fields/:id/settings" element={<FieldSettings />} />
          <Route path="/fields/:id/timeline" element={<FieldTimeline />} />
          <Route path="/fields/:id/trends" element={<FieldTrends />} />
          <Route path="/fields/:id/technical" element={<FieldTechnical />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

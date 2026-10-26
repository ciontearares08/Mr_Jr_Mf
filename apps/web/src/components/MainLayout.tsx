import { Outlet } from "react-router-dom";
import Navbar from "./Navbar";
import Footer from "./Footer";

export default function MainLayout() {
  return (
    // min-h-screen + flex-col + flex-1 on <main> keeps the footer at the bottom
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto w-full max-w-6xl flex-1 p-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

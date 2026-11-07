import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";
import ThemeToggle from "./ThemeToggle";

export default function Navbar() {
  return (
    <header className="border-b bg-background">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/" className="text-lg font-bold text-primary">
          Smart Agriculture
        </Link>

        <div className="flex gap-2">
          {/* buttonVariants() gives a normal link the same look as a <Button> */}
          <Link to="/fieldmap" className={buttonVariants({ variant: "ghost" })}>
            Field Map
          </Link>

          <Link
            to="/fields/new"
            className={buttonVariants({ variant: "ghost" })}
          >
            New Field
          </Link>
          <Link
            to="/fields/join"
            className={buttonVariants({ variant: "ghost" })}
          >
            Join Field
          </Link>
          <Link
            to="/dashboard"
            className={buttonVariants({ variant: "ghost" })}
          >
            Dashboard
          </Link>
          <Link to="/login" className={buttonVariants({ variant: "ghost" })}>
            Login
          </Link>
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}

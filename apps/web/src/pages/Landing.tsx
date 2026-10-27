import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";

export default function Landing() {
  return (
    <section className="mx-auto max-w-3xl py-16 text-center">
      <h1 className="mb-4 text-4xl font-bold text-primary">
        Smart Agriculture Monitoring System
      </h1>
      <p className="mb-8 text-lg text-muted-foreground">
        Using a combination of NDVI Satellite images and IRL metrics using IoT
        and a cloud backend to track crop health and predictive yields.
      </p>
      {/* buttonVariants() gives a normal link the same look as a <Button> */}
      <Link to="/dashboard" className={buttonVariants({ size: "lg" })}>
        View Live Dashboard
      </Link>
    </section>
  );
}

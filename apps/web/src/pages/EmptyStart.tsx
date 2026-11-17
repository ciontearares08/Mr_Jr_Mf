import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from "@/components/ui/card";

export default function EmptyStart() {
  return (
    <section className="mx-auto max-w-5xl px-6 py-16">
      <div className="mb-10 text-center">
        <h1 className="mb-4 text-3xl font-bold text-primary">
          Welcome to your farm!
        </h1>

        <p className="text-lg text-muted-foreground">
          Get started by creating a new field or joining an existing one.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Create a field</CardTitle>
            <CardDescription>
              Register a new agricultural field and start monitoring your crops.
            </CardDescription>
          </CardHeader>

          <CardFooter>
            <Link
              to="/fields/new"
              className={buttonVariants({ className: "w-full" })}
            >
              Create a field
            </Link>
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Join a field</CardTitle>
            <CardDescription>
              Join an existing agricultural field using an invitation.
            </CardDescription>
          </CardHeader>

          <CardFooter>
            <Link
              to="/fields/join"
              className={buttonVariants({ className: "w-full" })}
            >
              Join a field
            </Link>
          </CardFooter>
        </Card>
      </div>
    </section>
  );
}

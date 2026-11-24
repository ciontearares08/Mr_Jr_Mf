import {
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "cn";

function getNameValidationMessage(name: string): string | null {
  const trimmed = name.trim();
  if (trimmed.length === 0) {
    return "Field name is required (1 to 50 characters).";
  }
  if (trimmed.length > 50) {
    return "Field name must be 50 characters or fewer.";
  }
  return null;
}

type NameStepProps = {
  name: string;
  onChange: (name: string) => void;
};

export default function NameStep({ name, onChange }: NameStepProps) {
  const nameError = getNameValidationMessage(name);
  const showError = nameError !== null && name.length > 0;

  return (
    <>
      <CardHeader>
        <CardTitle>Step 1: Name</CardTitle>
        <CardDescription>
          Give your field a name between 1 and 50 characters.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="field-name">Field Name</Label>
          <Input
            id="field-name"
            name="fieldName"
            type="text"
            maxLength={50}
            value={name}
            placeholder="e.g. North Wheat Field"
            aria-invalid={showError}
            aria-describedby="field-name-help"
            onChange={(e) => onChange(e.target.value)}
          />
        </div>
        <div
          id="field-name-help"
          className="flex items-center justify-between text-xs"
        >
          <span
            className={cn(
              showError ? "text-destructive" : "text-muted-foreground",
            )}
          >
            {showError ? nameError : "1 to 50 characters."}
          </span>
          <span className="text-muted-foreground">{name.length}/50</span>
        </div>
      </CardContent>
    </>
  );
}

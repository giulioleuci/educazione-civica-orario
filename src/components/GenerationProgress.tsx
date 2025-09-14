import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface GenerationProgressProps {
  status: string;
  progress: number;
}

export function GenerationProgress({ status, progress }: GenerationProgressProps) {
  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Elaborazione in Corso...</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">{status}</p>
        <Progress value={progress} />
        <p className="text-sm font-medium text-center">{Math.round(progress)}%</p>
      </CardContent>
    </Card>
  );
}

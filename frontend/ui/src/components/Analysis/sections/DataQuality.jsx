import { Badge } from "shadcn/badge";
import { Card, CardContent, CardHeader, CardTitle } from "shadcn/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "shadcn/table";

const scoreBadge = (score) => {
  if (score >= 80) {
    return {
      label: "Good",
      className: "bg-emerald-600 text-white hover:bg-emerald-600",
    };
  }
  if (score >= 50) {
    return {
      label: "Fair",
      className: "bg-amber-500 text-white hover:bg-amber-500",
    };
  }
  return {
    label: "Poor",
    className: "bg-destructive text-white hover:bg-destructive",
  };
};

const severityBadge = (severity) => {
  if (severity === "high") {
    return (
      <Badge className="bg-destructive text-white hover:bg-destructive">
        High
      </Badge>
    );
  }
  if (severity === "medium") {
    return (
      <Badge className="bg-amber-500 text-white hover:bg-amber-500">
        Medium
      </Badge>
    );
  }
  return <Badge variant="outline">Low</Badge>;
};

const DataQuality = ({ report }) => {
  const badge = scoreBadge(report.score);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Data quality</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <span className="text-4xl font-bold">{report.score}</span>
          <Badge className={badge.className}>{badge.label}</Badge>
        </div>
        <p className="text-muted-foreground">{report.summary}</p>

        {report.issues.length === 0 ? (
          <p className="text-sm text-muted-foreground">No issues found.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Severity</TableHead>
                <TableHead>Column</TableHead>
                <TableHead>Kind</TableHead>
                <TableHead>Affected rows</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Suggestion</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {report.issues.map((issue, index) => (
                <TableRow key={index}>
                  <TableCell>{severityBadge(issue.severity)}</TableCell>
                  <TableCell>{issue.column ?? "—"}</TableCell>
                  <TableCell>{issue.kind}</TableCell>
                  <TableCell>{issue.affected_rows ?? "—"}</TableCell>
                  <TableCell className="whitespace-normal">
                    {issue.description}
                  </TableCell>
                  <TableCell className="whitespace-normal">
                    {issue.suggestion}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {report.cleaning_steps.length > 0 && (
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">Cleaning steps</h3>
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {report.cleaning_steps.map((step, index) => (
                <li key={index}>{step}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DataQuality;

import { Badge } from "shadcn/badge";
import { Card, CardContent, CardHeader, CardTitle } from "shadcn/card";

const Exploration = ({ report }) => (
  <Card>
    <CardHeader>
      <CardTitle>Exploratory analysis</CardTitle>
    </CardHeader>
    <CardContent className="flex flex-col gap-4">
      <p className="text-muted-foreground">{report.summary}</p>

      {report.findings.length === 0 ? (
        <p className="text-sm text-muted-foreground">No findings yet.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {report.findings.map((finding, index) => (
            <div key={index} className="flex flex-col gap-1.5">
              <p className="font-semibold">{finding.title}</p>
              <p className="text-sm text-muted-foreground">{finding.detail}</p>
              {finding.columns.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {finding.columns.map((column) => (
                    <Badge key={column} variant="outline">
                      {column}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </CardContent>
  </Card>
);

export default Exploration;

import { Badge } from "shadcn/badge";
import { Card, CardContent, CardHeader, CardTitle } from "shadcn/card";

const priorityBadge = (priority) => {
  if (priority === "high") {
    return (
      <Badge className="bg-destructive text-white hover:bg-destructive">
        High
      </Badge>
    );
  }
  if (priority === "medium") {
    return (
      <Badge className="bg-amber-500 text-white hover:bg-amber-500">
        Medium
      </Badge>
    );
  }
  return <Badge variant="outline">Low</Badge>;
};

const Summary = ({ report }) => (
  <Card>
    <CardHeader>
      <CardTitle className="text-xl">Executive summary</CardTitle>
    </CardHeader>
    <CardContent className="flex flex-col gap-6">
      <p className="text-lg leading-relaxed">{report.executive_summary}</p>

      {report.key_insights.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">Key insights</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {report.key_insights.map((insight, index) => (
              <li key={index}>{insight}</li>
            ))}
          </ul>
        </div>
      )}

      {report.recommendations.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">Recommendations</h3>
          <div className="flex flex-col gap-2">
            {report.recommendations.map((recommendation, index) => (
              <div
                key={index}
                className="flex items-start justify-between gap-3 rounded-lg border p-3"
              >
                <div>
                  <p className="font-semibold">{recommendation.title}</p>
                  <p className="text-sm text-muted-foreground">
                    {recommendation.detail}
                  </p>
                </div>
                {priorityBadge(recommendation.priority)}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-muted-foreground">
            Open questions
          </h3>
          {report.open_questions.length === 0 ? (
            <p className="text-sm text-muted-foreground">None.</p>
          ) : (
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {report.open_questions.map((question, index) => (
                <li key={index}>{question}</li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-muted-foreground">
            Limitations
          </h3>
          {report.limitations.length === 0 ? (
            <p className="text-sm text-muted-foreground">None.</p>
          ) : (
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {report.limitations.map((limitation, index) => (
                <li key={index}>{limitation}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </CardContent>
  </Card>
);

export default Summary;

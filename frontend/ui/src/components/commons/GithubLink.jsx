import { Github } from "lucide-react";

import { REPO_URL } from "constants/analysis";
import { Button } from "shadcn/button";

const GithubLink = () => (
  <Button asChild variant="ghost" size="icon">
    <a
      href={REPO_URL}
      target="_blank"
      rel="noreferrer noopener"
      aria-label="View the source on GitHub"
      title="View the source on GitHub"
    >
      <Github className="size-4" />
    </a>
  </Button>
);

export default GithubLink;

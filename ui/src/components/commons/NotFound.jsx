import { Button } from "shadcn/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "shadcn/empty";
import { Home } from "lucide-react";
import { HOME_ROUTE } from "../routeConstants";

export function NotFound() {
  return (
    <div className="flex min-h-svh items-center justify-center bg-standard px-4">
      <Empty className="border-0">
        <EmptyHeader>
          <div className="text-8xl font-bold text-white">404</div>
          <EmptyTitle className="text-2xl text-slate-200">
            Page not found!
          </EmptyTitle>
          <EmptyDescription className="text-slate-400">
            The page you're looking for doesn't exist.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              onClick={() => (window.location.href = HOME_ROUTE)}
              className="flex items-center gap-2 button-primary"
            >
              <Home className="size-4" />
              Go home
            </Button>
          </div>
        </EmptyContent>
      </Empty>
    </div>
  );
}

export default NotFound;

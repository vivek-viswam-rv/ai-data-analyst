import { useState } from "react";

import { Button } from "shadcn/button";
import { useFetchGreeting } from "hooks/reactQuery/useGreetingsApi";

function Home() {
  const [name, setName] = useState("world");
  const { data, isLoading, refetch } = useFetchGreeting(name);

  return (
    <div className="flex min-h-svh items-center justify-center bg-standard px-4">
      <div className="w-full max-w-md space-y-4 rounded-lg bg-white p-10 shadow-lg">
        <h1 className="text-3xl font-bold text-gray-900 mb-1">Wheel</h1>
        <p className="text-gray-600">React + FastAPI starter</p>

        <input
          value={name}
          onChange={event => setName(event.target.value)}
          className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />

        <p className="text-gray-600">{isLoading ? "Loading..." : data?.message}</p>

        <p className="text-sm text-gray-500">
          This page calls GET /api/greetings through the Vite proxy. Replace it
          with your app.
        </p>

        <Button onClick={() => refetch()} className="w-full button-primary">
          Reload
        </Button>
      </div>
    </div>
  );
}

export default Home;

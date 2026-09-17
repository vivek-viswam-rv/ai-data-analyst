import axios from "axios";

const fetch = params => axios.get("/greetings", { params });

export const greetingsApi = {
  fetch,
};

export default greetingsApi;

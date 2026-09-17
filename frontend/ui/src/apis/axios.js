import axios from "axios";
import { toast } from "sonner";

import { BASE_URL } from "./constants";

axios.defaults.baseURL = BASE_URL;
axios.defaults.headers.common.Accept = "application/json";

const handleErrorResponse = (error) => {
  toast.error(error.response?.data?.detail || error.message);

  return Promise.reject(error);
};

const registerIntercepts = () => {
  axios.interceptors.response.use((response) => response, handleErrorResponse);
};

export { registerIntercepts };

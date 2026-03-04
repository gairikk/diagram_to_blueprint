import axios from "axios";
import { ORCH_API } from "../config";

export async function startRun(payload) {
  const res = await axios.post(`${ORCH_API}/runs/start`, payload);
  return res.data;
}

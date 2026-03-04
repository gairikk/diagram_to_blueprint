import axios from "axios";
import { UPLOAD_API } from "../config";

export async function uploadDiagram(file) {
  const form = new FormData();
  form.append("file", file);

  const res = await axios.post(`${UPLOAD_API}/upload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return res.data; // Envelope from upload agent
}

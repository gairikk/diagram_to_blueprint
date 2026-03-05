import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadDiagram } from "../api/uploadApi";

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleUpload() {
    if (!file) return alert("Select a draw.io file");

    setLoading(true);
    try {
      const env = await uploadDiagram(file);

      navigate("/review", {
        state: {
          runId: env.run_id,
          storageUri: env.output.storage_uri,
          artifactType: env.output.artifact_type,
          extractedLabels: env.output.extracted_labels || [],
          llm: env.output.llm_suggestions || {},
        },
      });
    } catch (e) {
      alert("Upload failed");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 40 }}>
      <h1>Upload Architecture Diagram</h1>

      <input
        type="file"
        accept=".drawio,.xml"
        onChange={(e) => setFile(e.target.files[0])}
      />

      <br /><br />

      <button onClick={handleUpload} disabled={loading}>
        {loading ? "Uploading..." : "Upload"}
      </button>
    </div>
  );
}
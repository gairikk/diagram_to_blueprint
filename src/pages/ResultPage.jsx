import React from "react";
import { useLocation, useNavigate } from "react-router-dom";

export default function ResultPage() {
  const { state } = useLocation();
  const navigate = useNavigate();

  // Handle refresh/direct navigation where state may be missing
  if (!state) {
    return (
      <div style={{ padding: 40 }}>
        <h1>Result</h1>
        <p>No result data found. Please run validation again.</p>
        <button type="button" onClick={() => navigate("/")}>
          Go Back
        </button>
      </div>
    );
  }

  const { run_id, validation_status, download } = state;

  return (
    <div style={{ padding: 40 }}>
      <h1>Result</h1>

      <p>
        <b>Run ID:</b> {run_id}
      </p>
      <p>
        <b>Validation Status:</b> {validation_status}
      </p>

      <br />

      <a
        href={`http://localhost:8000${download?.repo ?? ""}`}
        target="_blank"
        rel="noreferrer noopener"
      >
        Download Terraform Repo
      </a>

      <br />
      <br />

      <a
        href={`http://localhost:8000${download?.report ?? ""}`}
        target="_blank"
        rel="noreferrer noopener"
      >
        Download Validation Report
      </a>
    </div>
  );
}
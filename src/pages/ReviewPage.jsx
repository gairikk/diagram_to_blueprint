import { useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { startRun } from "../api/orchestratorApi";

import TagEditor from "../components/TagEditor";
import MappingOverrideEditor from "../components/MappingOverrideEditor";
import QuestionsPanel from "../components/QuestionsPanel";

export default function ReviewPage() {
  const { state } = useLocation();
  const navigate = useNavigate();

  const [prefix, setPrefix] = useState(state.llm?.naming?.prefix || "proj");
  const [env, setEnv] = useState(state.llm?.naming?.env || "dev");
  const [tags, setTags] = useState(state.llm?.tags || {});
  const [location, setLocation] = useState(state.llm?.azure?.location || "eastus");
  const [overrides, setOverrides] = useState(state.llm?.mapping_overrides || []);
  const [loading, setLoading] = useState(false);

  async function handleRun() {
    setLoading(true);
    try {
      const result = await startRun({
        run_id: state.runId,
        storage_uri: state.storageUri,
        artifact_type: state.artifactType,
        naming: { prefix, env },
        tags,
        azure: { location },
        mapping_overrides: overrides,
      });

      navigate("/result", { state: result });
    } catch (e) {
      alert("Run failed");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 40 }}>
      <h1>Review & Configure</h1>

      <QuestionsPanel questions={state.llm?.questions} />

      <h3>Naming</h3>
      Prefix: <input value={prefix} onChange={e => setPrefix(e.target.value)} />
      Env: <input value={env} onChange={e => setEnv(e.target.value)} />

      <h3>Azure Location</h3>
      <select value={location} onChange={e => setLocation(e.target.value)}>
        <option value="eastus">eastus</option>
        <option value="centralindia">centralindia</option>
        <option value="westeurope">westeurope</option>
      </select>

      <h3>Tags</h3>
      <TagEditor tags={tags} setTags={setTags} />

      <h3>Mapping Overrides</h3>
      <MappingOverrideEditor overrides={overrides} setOverrides={setOverrides} />

      <br />
      <button onClick={handleRun} disabled={loading}>
        {loading ? "Running..." : "Generate Terraform"}
      </button>
    </div>
  );
}
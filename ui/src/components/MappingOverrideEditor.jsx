export default function MappingOverrideEditor({ overrides, setOverrides }) {
  function update(i, field, value) {
    const copy = [...overrides];
    copy[i][field] = value;
    setOverrides(copy);
  }

  function add() {
    setOverrides([...overrides, {
      label_contains: "",
      resource_type: "",
      module: ""
    }]);
  }

  function remove(i) {
    setOverrides(overrides.filter((_, idx) => idx !== i));
  }

  return (
    <>
      {overrides.map((o, i) => (
        <div key={i} style={{ border: "1px solid #ccc", margin: 5, padding: 5 }}>
          <input placeholder="Label contains"
                 value={o.label_contains}
                 onChange={e => update(i, "label_contains", e.target.value)} />
          <input placeholder="Resource type"
                 value={o.resource_type}
                 onChange={e => update(i, "resource_type", e.target.value)} />
          <input placeholder="Module"
                 value={o.module}
                 onChange={e => update(i, "module", e.target.value)} />
          <button onClick={() => remove(i)}>Remove</button>
        </div>
      ))}
      <button onClick={add}>+ Add Override</button>
    </>
  );
}
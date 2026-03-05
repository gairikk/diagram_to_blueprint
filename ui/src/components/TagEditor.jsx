import React from "react";

export default function TagEditor({ tags = {}, setTags }) {
  function update(key, value) {
    setTags((prev) => ({
      ...prev,
      [key]: value,
    }));
  }

  function remove(key) {
    setTags((prev) => {
      const copy = { ...prev };
      delete copy[key];
      return copy;
    });
  }

  function addTag() {
    // Create a unique default key to avoid overwriting existing tags
    let base = "new_key";
    let key = base;
    let i = 1;

    while (Object.prototype.hasOwnProperty.call(tags, key)) {
      key = `${base}_${i++}`;
    }

    update(key, "value");
  }

  return (
    <>
      {Object.entries(tags).map(([k, v]) => (
        <div key={k} style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <input value={k} disabled />
          <input
            value={v}
            onChange={(e) => update(k, e.target.value)}
            placeholder="Tag value"
          />
          <button type="button" onClick={() => remove(k)}>
            x
          </button>
        </div>
      ))}

      <button type="button" onClick={addTag}>
        + Add Tag
      </button>
    </>
  );
}
``
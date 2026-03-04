export default function QuestionsPanel({ questions }) {
  if (!questions || questions.length === 0) return null;

  return (
    <div style={{ background: "#fff3cd", padding: 10 }}>
      <h4>LLM Questions</h4>
      <ul>
        {questions.map((q, i) => <li key={i}>{q}</li>)}
      </ul>
    </div>
  );
}
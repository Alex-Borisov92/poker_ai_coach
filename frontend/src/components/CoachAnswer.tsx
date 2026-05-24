type CoachAnswerProps = {
  content: string;
};

export function CoachAnswer({ content }: CoachAnswerProps) {
  const lines = content.split(/\r?\n/);
  return (
    <div className="coach-answer">
      {lines.map((line, index) => renderLine(line, index))}
    </div>
  );
}

function renderLine(line: string, index: number) {
  const trimmed = line.trim();
  if (!trimmed) {
    return <div className="coach-answer-gap" key={index} />;
  }

  const heading = trimmed.match(/^#{1,3}\s+(.+)$/);
  if (heading) {
    return <h3 key={index}>{renderInline(heading[1])}</h3>;
  }

  const numberedHeading = trimmed.match(/^\d+\.\s+([A-ZА-Я].{2,42})$/);
  if (numberedHeading) {
    return <h3 key={index}>{renderInline(numberedHeading[1])}</h3>;
  }

  const bullet = trimmed.match(/^[-*]\s+(.+)$/);
  if (bullet) {
    return (
      <p className="coach-answer-bullet" key={index}>
        {renderInline(bullet[1])}
      </p>
    );
  }

  const ordered = trimmed.match(/^\d+\.\s+(.+)$/);
  if (ordered) {
    return (
      <p className="coach-answer-bullet" key={index}>
        {renderInline(ordered[1])}
      </p>
    );
  }

  return <p key={index}>{renderInline(trimmed)}</p>;
}

function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <span key={index}>{part}</span>;
  });
}

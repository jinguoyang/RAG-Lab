import { useState } from "react";

interface Option {
  label: string;
  text: string;
}

interface ChoiceQuestionProps {
  question: string;
  options: Option[];
  onAnswer: (answer: string) => void;
  disabled?: boolean;
}

export function ChoiceQuestion({ question, options, onAnswer, disabled }: ChoiceQuestionProps) {
  const [selected, setSelected] = useState<string | null>(null);

  function handleSelect(label: string) {
    if (disabled) return;
    setSelected(label);
    onAnswer(label);
  }

  return (
    <div className="choice-question">
      <p>{question}</p>
      <div className="choice-grid">
        {options.map((opt) => (
          <button
            key={opt.label}
            onClick={() => handleSelect(opt.label)}
            disabled={disabled}
            className={`choice-option ${
              selected === opt.label
                ? "selected"
                : ""
            } ${disabled ? "disabled" : ""}`}
          >
            <span>{opt.label}.</span>
            {opt.text}
          </button>
        ))}
      </div>
    </div>
  );
}
